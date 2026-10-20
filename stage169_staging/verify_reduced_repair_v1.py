"""Frozen unit and bounded local regression tests for the opt-in fallback."""
from pathlib import Path
import copy,sys,time,itertools,inspect
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage168_staging'),str(ROOT/'stage167_staging')]
import diagnose_frozen_contact_v3 as captured
import reduced_contact_repair_v1 as repair
c=captured.capture;parent=c.parent;api=c.api;hot=parent.b.old.hot
BASE='original_gap_repair_20260923'
DESIGN=ROOT/'stage169_designs'/BASE/'design_01.json'
EVAL=ROOT/'stage169_evaluations'/BASE
RUN=ROOT/'stage169_runs'/BASE/'local_01'


def prepare():
    c.verify(api.read(c.DESIGN))
    failed=api.read(parent.OUT.parent/'failure_assessment_01/results.json')
    raw=Path(failed['failed_segment']['path']);prior=raw.with_name('segment_00137.json.gz')
    old=parent.storage.read_record(prior,api.sha(parent.DESIGN))
    api.require(old['result']['rejected']==0,'clean predecessor')
    diagnosis=ROOT/'stage168_evaluations/sphere_three_contact_diagnosis_20260923/diagnosis_01'
    api.require(api.read(diagnosis/'completion.json')['results_sha256']==api.sha(diagnosis/'results.json'),'diagnosis seal')
    d={'stage':'Stage169','authorization':'User yes fix first: bounded repair and local verification only; no campaign restart.',
        'physics_changes':[],'gap_changes':[],'algorithm':'Failure-only scalar force-balance root for original one-stick/two-slide mode; original fallback remains if no admissible root.',
        'source_checkpoint':str(prior),'failed_segment':str(raw),'factors_relative_to_stage167_fine':[1.,.5,.25],
        'local_horizon_s':failed['first_rejection']['time_s']+1e-4,
        'limits':{'contact_residual':1e-10,'force_momentum':1e-8,'cone_relative':1e-12,
                  'pose_b':1e-4,'axis':1e-4,'endpoint_velocity_U':.005,'mean_L1_velocity_U':.005},
        'budget':{'threads':1,'workers':1,'maximum_total_local_steps':25000,'step_cap_per_call':1000,
                  'maximum_calls_per_level':20,'wall_seconds_local':600.,'max_frozen_rejected_probes':28},
        'tests':['21 analytical contacts','exact unchanged known-good solve','repaired first failure','all archived rejected trial poses',
                 'three force/velocity scales','six contact permutations','rotated coordinate frame','fail closed invalid inputs',
                 'exact local checkpoint split identity','three local timesteps: health, no rejected trial, pose, velocity and mean-L1 comparisons'],
        'stop':'Any primary verification failure stops promotion; immutable old campaign remains failed. No long-run restart.',
        'sources':parent.source_map(),
        'inputs':{str(p):api.sha(p) for p in [c.DESIGN,c.OUT/'results.json',c.OUT/'completion.json',prior,prior.with_suffix('.seal.json'),raw,raw.with_suffix('.seal.json'),diagnosis/'results.json',diagnosis/'completion.json']}}
    d['binding']=api.digest(d);DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d)
    print('FROZEN',api.sha(DESIGN),flush=True)


def verify(d):
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'design binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs']);c.verify(api.read(c.DESIGN))


def independent(v,M,J,g,dt,mu,q,h):
    f=np.asarray(h['reactions']);A=J@M@J.T;w=J@q;scale=max(np.linalg.norm(v),1e-15)
    terms=[]
    for k in range(len(g)):
        i=3*k;step=np.linalg.eigvalsh(A[i+1:i+3,i+1:i+3]).max()
        trial=f[i+1:i+3]-w[i+1:i+3]/step
        proj=trial*min(1.,mu*f[i]/max(np.linalg.norm(trial),1e-300))
        terms.extend([abs(min(A[i,i]*f[i],w[i]+g[k]/dt)),np.linalg.norm(f[i+1:i+3]-proj)*step])
    residual=max(terms,default=0.)/scale
    load=J.T@f;force=np.linalg.norm(np.linalg.solve(M,q-v)-load)/max(np.linalg.norm(load),1e-30)
    work=sum(f[3*k+1:3*k+3]@w[3*k+1:3*k+3] for k in range(len(g)))
    cone=all(np.linalg.norm(f[3*k+1:3*k+3])<=mu*f[3*k]+1e-12*max(np.linalg.norm(f),1e-30) for k in range(len(g)))
    return {'passed':bool(np.isfinite(q).all() and np.isfinite(f).all() and np.all(f[::3]>=0) and cone and residual<=1e-10 and force<=1e-8 and work<=1e-8*max(np.linalg.norm(f)*scale,1e-30)),
        'residual':float(residual),'force_residual':float(force),'friction_work_W':float(work),'cone_passed':cone}


def units():
    d=api.read(DESIGN);verify(d);out=EVAL/'units_01';out.mkdir(exist_ok=False)
    parent.b.old.parent.configure();reports=[]
    sys.path.insert(0,str(ROOT/'stage119_staging'))
    import verify_repair_v3 as legacy
    with repair.scope(parent.engine.runtime,True),parent.fix.scope():toy=legacy.toys()
    api.write(out/'analytical_contacts.json',toy)
    reports.append({'id':'analytical_21','passed':len(toy)==21 and all(x['passed'] for x in toy)})
    p=api.read(c.OUT/'system_002.json');v,M,J,g=[np.asarray(p[k]) for k in ['vfree','mobility','jacobian','gaps']]
    dt,mu=p['dt'],p['friction'];baseline=None
    saved=hot.s50._residual;hot.s50._residual=hot.scalar.residual
    with parent.fix.scope():
        try:
            cases=[]
            for scale in [1.,1e-3,1e3]:cases.append((f'scale_{scale}',v*scale,M,J,g*scale,np.eye(6),scale))
            for perm in itertools.permutations(range(3)):
                idx=np.array([3*k+j for k in perm for j in range(3)])
                cases.append((f'permutation_{perm}',v,M,J[idx],g[list(perm)],np.eye(6),1.))
            R,_=np.linalg.qr(np.random.default_rng(169).normal(size=(3,3)))
            if np.linalg.det(R)<0:R[:,0]*=-1
            Q=np.zeros((6,6));Q[:3,:3]=R;Q[3:,3:]=R
            cases.append(('rotated_frame',Q@v,Q@M@Q.T,J@Q.T,g,Q,1.))
            for name,v0,M0,J0,g0,Q,scale in cases:
                start=time.perf_counter()
                try:q,h=repair.solve(v0,M0,J0,g0,dt,mu,1e-10,25000)
                except Exception as error:reports.append({'id':name,'passed':False,'error':str(error)});continue
                if baseline is None:baseline=q.copy()
                audit=independent(v0,M0,J0,g0,dt,mu,q,h)
                error=float(np.linalg.norm(Q.T@q/scale-baseline)/np.linalg.norm(v))
                reports.append({'id':name,'passed':audit['passed'] and error<=1e-10,'audit':audit,'velocity_invariance_error':error,'health':h,'wall_s':time.perf_counter()-start})
            for name,args in [('negative_mobility',(v,-M,J,g,dt,mu,1e-10,25000)),('bad_dt',(v,M,J,g,0.,mu,1e-10,25000)),('wrong_count',(v,M,J[:6],g[:2],dt,mu,1e-10,25000))]:
                try:repair.solve(*args)
                except (RuntimeError,ValueError,np.linalg.LinAlgError):reports.append({'id':name,'passed':True})
                else:reports.append({'id':name,'passed':False})
        finally:hot.s50._residual=saved
    # Full existing wrapper chain plus new failure-only fallback; no time advance.
    cd=api.read(c.DESIGN);spec=cd['spec'];field,data,meta=api.fields.load(spec['seed'],spec['flow_factor'],spec['cpd'])
    geometry=c.diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'],data['sand_radii_m'],meta['cell_length_m'])
    local=[]
    with hot.scope(),parent.fix.scope(),repair.scope(parent.engine.runtime,True):
        for probe in cd['probes']:
            start=len(repair.telemetry)
            try:q,h=c.diag.replay(field,geometry,spec,probe['state'],probe['dt_s'])
            except RuntimeError as error:local.append({'id':probe['id'],'passed':False,'error':str(error)});continue
            exact=probe['id']!='preceding_good' or q.tolist()==probe['expected_velocity']
            no_fallback=probe['id']!='preceding_good' or len(repair.telemetry)==start
            local.append({'id':probe['id'],'passed':exact and no_fallback and h['momentum_residual']<=1e-8 and h['contact_residual']<=1e-10,'health':h,'velocity':q,'fallbacks':copy.deepcopy(repair.telemetry[start:])})
        record=parent.storage.read_record(Path(d['failed_segment']),api.sha(parent.DESIGN))
        trials=record['result']['rejected_trials'];api.require(len(trials)==28,'frozen rejection count')
        rows={row['time_s']:row for row in record['rows']}
        for i,trial in enumerate(trials):
            row=rows[trial['time_s']];state={'x':row['position_m'],'p':row['orientation'],'q':row['velocity_generalized'],'t':row['time_s'],'recovery':False}
            try:q,h=c.diag.replay(field,geometry,spec,state,trial['dt_s'])
            except RuntimeError as error:local.append({'id':f'archived_rejection_{i}','passed':False,'error':str(error)});continue
            local.append({'id':f'archived_rejection_{i}','passed':h['momentum_residual']<=1e-8 and h['contact_residual']<=1e-10,'health':h,'velocity':q})
    api.write(out/'fixed_pose_probes.json',local,raw=True)
    result={'passed':all(x['passed'] for x in reports+local),'tests':reports,'frozen_probe_passed':sum(x['passed'] for x in local),'frozen_probe_count':len(local),'trajectory_steps':0,'production_default_changed':False,
        'design_sha256':api.sha(DESIGN),'artifacts':{str(p):api.sha(p) for p in out.glob('*.json')}}
    verify(d);api.write(out/'results.json',result,raw=True);api.write(out/'completion.json',{'passed':result['passed'],'results_sha256':api.sha(out/'results.json')})
    print('UNITS',result['passed'],'PROBES',result['frozen_probe_passed'],'/',len(local),'FAILED',[x['id'] for x in reports+local if not x['passed']],flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['units']:units()
    else:raise ValueError('prepare or units')
