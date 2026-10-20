"""Frozen zero-step qualification of the opt-in fast contact implementation."""
from pathlib import Path
import copy, datetime, itertools, sys, time, traceback
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage171_staging'))
import repaired_campaign_preflight_v1 as p
import reduced_contact_fast_v1 as fast
api,parent,unit=p.api,p.parent,p.job.unit
CONTRACT=ROOT/'stage172_designs/four_hour_work_20260923/contract_01.json'
DESIGN=CONTRACT.with_name('solver_design_01.json')
OUT=ROOT/'stage172_evaluations/fast_contact_20260923/units_01'


def check_time():
    api.require(time.time()<fast.END_UTC-60,'four-hour window with audit reserve')


def prepare():
    check_time();p.verify(api.read(p.DESIGN))
    inputs=[CONTRACT,p.DESIGN,p.OUT/'results.json',p.OUT/'completion.json']
    matrices=sorted((ROOT/'stage168_evaluations/sphere_three_contact_diagnosis_20260923/capture_01').glob('system_*.json'))
    matrices+=sorted((ROOT/'stage169_evaluations/original_gap_repair_20260923/refined_failure_capture_01').glob('system_*.json'))
    inputs+=matrices
    d={'stage':'Stage172','algorithm':'Batched original scalar scan plus stateless near-rest early candidate; unchanged fallback stack.',
       'early_guard':{'contacts':3,'max_gap_over_dt_free_speed':1e-5,'max_outgoing_over_free_speed':1e-4},
       'physics_changes':[],'matrix_equivalence_tolerance_free_speed':1e-10,
       'matrices':[str(x) for x in matrices], 'maximum_new_trajectory_steps':0,
       'sources':parent.source_map(),'inputs':{str(x):api.sha(x) for x in inputs}}
    d['binding']=api.digest(d);api.write(DESIGN,d);print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'frozen solver design')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs']);p.verify(api.read(p.DESIGN))


def run():
    check_time();d=api.read(DESIGN);verify(d);OUT.mkdir(parents=True,exist_ok=False)
    parent.b.old.parent.configure();tests=[];matrices=[];start=time.perf_counter()
    saved=p.hot.s50._residual;p.hot.s50._residual=p.hot.scalar.residual
    try:
        with parent.fix.scope():
            for path in d['matrices']:
                check_time();r=api.read(path)
                v,M,J,g=[np.asarray(r[k]) for k in ['vfree','mobility','jacobian','gaps']]
                if len(g)!=3:
                    matrices.append({'path':path,'tested':False,'reason':'outside three-contact candidate domain'});continue
                args=(v,M,J,g,r['dt'],r['friction'],1e-10,25000)
                try:
                    t=time.perf_counter();q0,h0=fast.old.solve(*args);base_s=time.perf_counter()-t
                except (RuntimeError,ValueError,np.linalg.LinAlgError) as e:
                    matrices.append({'path':path,'tested':False,'reason':'reference candidate rejected','error':str(e)});continue
                try:
                    t=time.perf_counter();q,h=fast.solve(*args);new_s=time.perf_counter()-t
                    audit=unit.independent(v,M,J,g,r['dt'],r['friction'],q,h)
                    error=float(np.linalg.norm(q-q0)/max(np.linalg.norm(v),1e-15))
                    matrices.append({'path':path,'tested':True,'passed':audit['passed'] and error<=1e-10,
                                     'audit':audit,'velocity_difference_free_scale':error,'old_s':base_s,'fast_s':new_s,'health':h})
                except Exception as e:
                    matrices.append({'path':path,'tested':True,'passed':False,'error':repr(e)})
            # Original and refined matrices exercise one-stick and redundant-stick branches.
            for source in [unit.c.OUT/'system_002.json',ROOT/'stage169_evaluations/original_gap_repair_20260923/refined_failure_capture_01/system_002.json']:
                r=api.read(source);v,M,J,g=[np.asarray(r[k]) for k in ['vfree','mobility','jacobian','gaps']]
                qbase,_=fast.solve(v,M,J,g,r['dt'],r['friction'],1e-10,25000)
                transformations=[]
                for scale in [1e-3,1.,1e3]:transformations.append((f'scale_{scale}',v*scale,M,J,g*scale,np.eye(6),scale))
                for perm in itertools.permutations(range(3)):
                    idx=[3*k+j for k in perm for j in range(3)]
                    transformations.append((f'permutation_{perm}',v,M,J[idx],g[list(perm)],np.eye(6),1.))
                for seed in [172,173,174]:
                    R,_=np.linalg.qr(np.random.default_rng(seed).normal(size=(3,3)))
                    if np.linalg.det(R)<0:R[:,0]*=-1
                    Q=np.zeros((6,6));Q[:3,:3]=R;Q[3:,3:]=R
                    transformations.append((f'frame_{seed}',Q@v,Q@M@Q.T,J@Q.T,g,Q,1.))
                for label,vi,Mi,Ji,gi,Q,scale in transformations:
                    try:
                        q,h=fast.solve(vi,Mi,Ji,gi,r['dt'],r['friction'],1e-10,25000)
                        a=unit.independent(vi,Mi,Ji,gi,r['dt'],r['friction'],q,h)
                        error=float(np.linalg.norm(Q.T@q/scale-qbase)/np.linalg.norm(v))
                        tests.append({'source':str(source),'test':label,'passed':a['passed'] and error<=1e-10,'audit':a,'error':error})
                    except Exception as e:tests.append({'source':str(source),'test':label,'passed':False,'error':repr(e)})
            for label,args in [('negative_mobility',(v,-M,J,g,r['dt'],r['friction'],1e-10,25000)),
                               ('zero_dt',(v,M,J,g,0.,r['friction'],1e-10,25000)),
                               ('wrong_shape',(v,M,J[:6],g[:2],r['dt'],r['friction'],1e-10,25000)),
                               ('nan_gap',(v,M,J,g*np.nan,r['dt'],r['friction'],1e-10,25000))]:
                try:fast.solve(*args)
                except (RuntimeError,ValueError,np.linalg.LinAlgError):tests.append({'test':label,'passed':True})
                else:tests.append({'test':label,'passed':False})
        api.write(OUT/'matrix_tests.json',matrices,raw=True);api.write(OUT/'invariance_tests.json',tests,raw=True)
        # Full wrapper tests. No accepted or rejected integrator step is taken.
        cd=api.read(unit.c.DESIGN);spec=cd['spec']
        field,data,meta=api.fields.load(spec['seed'],spec['flow_factor'],spec['cpd'])
        geometry=unit.c.diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
        probes=[]
        with p.hot.scope(),parent.fix.scope():
            for probe in cd['probes']:
                with fast.old.scope(parent.engine.runtime,True):
                    q0,h0=unit.c.diag.replay(field,geometry,spec,probe['state'],probe['dt_s'])
                with fast.scope(parent.engine.runtime,True):
                    n=len(fast.telemetry);q,h=unit.c.diag.replay(field,geometry,spec,probe['state'],probe['dt_s'])
                error=float(np.linalg.norm(q-q0)/spec['config']['target_mean_interstitial_velocity_m_s'])
                exact=probe['id']!='preceding_good' or q.tolist()==probe['expected_velocity']
                probes.append({'id':probe['id'],'passed':error<=1e-10 and exact and h['momentum_residual']<=1e-8 and h['contact_residual']<=1e-10,
                               'error_U':error,'exact_preceding_good':exact,'early_accepts':len(fast.telemetry)-n,'health':h})
        sys.path.insert(0,str(ROOT/'stage119_staging'));import verify_repair_v3 as legacy
        with fast.scope(parent.engine.runtime,True),parent.fix.scope():toys=legacy.toys()
        api.write(OUT/'wrapper_probes.json',probes,raw=True);api.write(OUT/'analytical_tests.json',toys,raw=True)
        checked=[x for x in matrices if x['tested']]
        passed=bool(checked) and all(x['passed'] for x in checked+tests+probes+toys)
        result={'passed':passed,'matrices_tested':len(checked),'matrices_not_candidate_domain_or_reference_failed':len(matrices)-len(checked),
                'invariance_invalid_tests':len(tests),'wrapper_probes':len(probes),'analytical_tests':len(toys),'new_trajectory_steps':0,
                'wall_s':time.perf_counter()-start,'design_sha256':api.sha(DESIGN),
                'failed':[x for x in checked+tests+probes+toys if not x['passed']],
                'artifacts':{str(x):api.sha(x) for x in OUT.glob('*.json')}}
        verify(d);api.write(OUT/'results.json',result,raw=True);api.write(OUT/'completion.json',{'passed':passed,'results_sha256':api.sha(OUT/'results.json')})
        print('UNITS',passed,'MATRICES',len(checked),'FAILED',result['failed'],flush=True)
    except Exception as e:
        api.write(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc()});raise
    finally:p.hot.s50._residual=saved


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
