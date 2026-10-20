"""Frozen 8-matrix, 72-transform, 75-control same-system seed qualification."""
from pathlib import Path
import copy,itertools,os,time,traceback
import numpy as np
import qualify_sliding_projection_v1 as tests
import semismooth_rejected_seed_v1 as repair
q=tests.q;job,api=q.job,q.api;BASE=tests.BASE;OUT=BASE/'semismooth_seed_qualification_01'
DESIGN=q.ROOT/'stage194_designs/evidence_repair_20260924/semismooth_seed_qualification_01.json'

def run():
    end=job.policy.utc(api.read(q.WORK)['work_end_utc']).timestamp();api.require(time.time()<end,'work clock');d=api.read(job.DESIGN);job.verify(d)
    source1=BASE/'contact_diagnosis_01/results.json';source2=BASE/'dispatch_failure_audit_01/failure_details.json'
    systems=api.read(source1)['captured_systems']+api.read(source2)['captured_systems']
    matrix_design=q.ROOT/'stage172_designs/four_hour_work_20260923/solver_design_01.json';matrices=api.read(matrix_design)['matrices']
    paths=[q.WORK,source1,source2,matrix_design]+list(Path(__file__).parent.glob('*.py'))+[Path(x) for x in matrices]
    p={'stage':'Stage194 same-system analytic seed qualification','inputs':{str(x):api.sha(x) for x in paths},'sources':d['sources'],'new_trajectory_steps':0,
       'matrix_cases':8,'transforms_per_case':9,'normalized_velocity_difference_max':1e-10,'changed_physics_timesteps_horizons_gates':[],
       'exact_prior_reduced_successes_required':True,'maximum_seeds_per_matrix':8,'maximum_nfev_per_seed':2000,'production_authorized':False}
    job.commit(DESIGN,p);OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'protocol_sha256':api.sha(DESIGN),'new_trajectory_steps':0})
    cases=[];transforms=[];controls=[];failure=None;job.parent.b.old.parent.configure()
    try:
        with job.prior.p.hot.scope(),job.parent.fix.scope():
            for i,s in enumerate(systems):
                api.require(time.time()<end,'work clock');a=tests.args(s);start=time.perf_counter()
                try:answer=repair.solve(*a,stop_epoch=end);check,row=tests.audit(a,answer)
                except Exception as e:cases.append({'index':i,'passed':False,'error':repr(e)});continue
                cases.append({'index':i,'passed':True,'audit':check,'saved_system':row,'seconds':time.perf_counter()-start});v,M,J,g,dt,mu,tol,maxiter=a;base=answer[0]
                variants=[]
                for perm in itertools.permutations(range(3)):
                    idx=[3*k+j for k in perm for j in range(3)];variants.append((f'perm_{perm}',v,M,J[idx],g[list(perm)],np.eye(6),1.))
                for scale in (.1,10.):variants.append((f'scale_{scale}',v*scale,M,J,g*scale,np.eye(6),scale))
                R,_=np.linalg.qr(np.random.default_rng(194+i).normal(size=(3,3)))
                if np.linalg.det(R)<0:R[:,0]*=-1
                Q=np.zeros((6,6));Q[:3,:3]=R;Q[3:,3:]=R;variants.append(('frame',Q@v,Q@M@Q.T,J@Q.T,g,Q,1.))
                for name,vi,Mi,Ji,gi,Q,scale in variants:
                    try:
                        aa=(vi,Mi,Ji,gi,dt,mu,tol,maxiter);answer=repair.solve(*aa,stop_epoch=end);check,_=tests.audit(aa,answer)
                        error=float(np.linalg.norm(Q.T@answer[0]/scale-base)/max(np.linalg.norm(v),1e-15));transforms.append({'index':i,'test':name,'passed':error<=1e-10,'error_normalized':error,'audit':check})
                    except Exception as e:transforms.append({'index':i,'test':name,'passed':False,'error':repr(e)})
                print('SEMISMOOTH_CASE',i,cases[-1]['passed'],sum(not t['passed'] for t in transforms if t['index']==i),flush=True)
            runtime=job.parent.engine.runtime
            for path in matrices:
                s=api.read(path);aa=(*[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps')],s['dt'],s['friction'],1e-10,25000)
                try:
                    with job.fast.old.scope(runtime,True):expected=runtime.mixed.solve(*aa)
                except (RuntimeError,ValueError,np.linalg.LinAlgError):controls.append({'path':path,'reference_passed':False});continue
                with repair.scope(runtime,True,end),job.fast.old.scope(runtime,True):got=runtime.mixed.solve(*aa)
                trim=lambda h:{k:v for k,v in h.items() if k!='certificate_seconds'};check,_=tests.audit(aa,got)
                controls.append({'path':path,'reference_passed':True,'passed':bool(np.array_equal(expected[0],got[0]) and trim(expected[1])==trim(got[1])),'audit':check})
            with repair.scope(runtime,True,end):toys=tests.analytical.toys()
    except Exception as e:failure={'error':repr(e),'traceback':traceback.format_exc()};job.commit(OUT/'failure.json',failure);toys=[]
    api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
    for name,value in [('cases',cases),('transforms',transforms),('controls',controls),('analytical',toys)]:job.commit(OUT/(name+'.json'),value)
    checked=cases+transforms+toys+[c for c in controls if c.get('reference_passed')]
    passed=failure is None and len(cases)==8 and len(transforms)==72 and all(c['passed'] for c in checked)
    r={'passed':passed,'new_trajectory_steps':0,'cases':len(cases),'transforms':len(transforms),'controls_exact':sum(c.get('passed',False) for c in controls),
       'analytical_checks':len(toys),'failed':[c for c in checked if not c['passed']],'failure':failure,'protocol_sha256':api.sha(DESIGN),
       'artifacts':{str(x):api.sha(x) for x in OUT.glob('*.json')},'production_authorized':False}
    job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'passed':passed,'results_sha256':api.sha(OUT/'results.json')});print('SEMISMOOTH_QUALIFIED',passed,len(r['failed']),flush=True)

if __name__=='__main__':run()
