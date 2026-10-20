"""128 held fixed poses plus eight failure fixtures; zero trajectory steps."""
from pathlib import Path
import copy,os,time,traceback
import numpy as np
import qualify_sliding_projection_v1 as tests
import early_semismooth_dispatch_v1 as repair
import audit_early_semismooth_v1 as auditor
q=tests.q;job,api=q.job,q.api;BASE=tests.BASE;OUT=BASE/'early_semismooth_qualification_01'
DESIGN=q.ROOT/'stage194_designs/evidence_repair_20260924/early_semismooth_qualification_01.json'
PRIOR=DESIGN.with_name('semismooth_restart_01.json');RAW=q.ROOT/'stage194_runs/evidence_repair_20260924/semismooth_restart_01/call_01.json.xz'

def run():
    w=api.read(q.WORK);end=job.policy.utc(w['work_end_utc']).timestamp();api.require(time.time()<end,'work clock');d=api.read(job.DESIGN);job.verify(d)
    old=api.read(PRIOR);api.verify_mapping(old['inputs']);api.verify_mapping(old['sources']);r=api.read(BASE/'semismooth_restart_01/results.json')
    api.require(r['passed'] and r['artifacts'][str(RAW)]==api.sha(RAW),'sealed exact restart precursor')
    raw=q.independent_file(RAW,api.sha(PRIOR));fixture_path=BASE/'semismooth_outer_qualification_01/fixtures.json'
    matrix_design=q.ROOT/'stage172_designs/four_hour_work_20260923/solver_design_01.json';matrices=api.read(matrix_design)['matrices']
    paths=[q.WORK,PRIOR,RAW,fixture_path,matrix_design]+[Path(x) for x in matrices]+list(Path(__file__).parent.glob('*.py'))
    p={'stage':'Stage194 original near-rest guard dispatch qualification','new_trajectory_steps':0,'inputs':{str(x):api.sha(x) for x in paths},'sources':d['sources'],
       'maximum_fixed_outer_calls':136,'normalized_velocity_difference_max':1e-10,'changed_physics_timesteps_horizons_gates':[],
       'primary_general_ordering_changed_in_existing_guard':True,'no_inter_pose_state_reuse':True,'production_authorized':False}
    job.commit(DESIGN,p);OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'new_trajectory_steps':0,'protocol_sha256':api.sha(DESIGN)})
    trials=raw['contact_trial_trace']['detailed_trials']+[e['fixture']['contact_trial_trace']['detailed_trials'][0] for e in api.read(fixture_path)]
    api.require(len(trials)==136,'bounded exact held-pose count');runtime=job.parent.engine.runtime;job.parent.b.old.parent.configure();reports=[];fixtures=[];controls=[];guards=[];failure=None
    try:
        for i,t in enumerate(trials):
            api.require(time.time()<end,'work clock');job.clear_telemetry();runtime._calls.clear();job.fast.capture_systems=True;runtime.probe.RECOVERY.portfolio.set_recovery_mode(False);start=time.perf_counter()
            with repair.scope(runtime,True,end),job.prior.p.hot.scope(),job.parent.fix.scope(),job.deadline.scope(runtime,w['work_end_utc'],True),job.capture.scope(runtime,True),runtime.repair_scope(),job.observer.scope(runtime,True) as log:
                answer=job.observer.backend.inertial_contact_step(*copy.deepcopy(t['outer_inputs']))
                fixture={'contact_trial_trace':copy.deepcopy(log),'rows':[{'velocity_generalized':answer[0].tolist(),'active_contact_ids':[int(c[0]) for c in t['outer_inputs'][6]]}],
                   'sweep_certificates':[{'dt_s':t['outer_inputs'][8]}],'early_attempts':copy.deepcopy(job.fast.attempts),'fallback_systems':copy.deepcopy(job.capture.records),
                   'result':{'stage119_repair_calls':copy.deepcopy(runtime._calls)},'repairs':copy.deepcopy(job.fast.old.telemetry)}
            seconds=time.perf_counter()-start;before={'state':{'q':t['outer_inputs'][0]}};check=auditor.evaluate(fixture,before)
            scale=max(np.linalg.norm(t['inner_systems'][0]['vfree']),1e-15);error=float(np.linalg.norm(answer[0]-t['velocity'])/scale)
            reports.append({'index':i,'passed':check['passed'] and error<=1e-10,'seconds':seconds,'normalized_velocity_difference':error,'audit':check,'exact_velocity':answer[0].tolist()==t['velocity']})
            fixtures.append({'fixture':fixture,'before':before})
            if i%32==0:print('EARLY_FIXED_POSE',i,reports[-1]['passed'],seconds,error,flush=True)
        with job.prior.p.hot.scope(),job.parent.fix.scope():
            for path in matrices:
                s=api.read(path);a=(*[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps')],s['dt'],s['friction'],1e-10,25000)
                try:expected=job.fast.solve(*a)
                except (RuntimeError,ValueError,np.linalg.LinAlgError):controls.append({'path':path,'reference_passed':False});continue
                with repair.scope(runtime,True,end):got=job.fast.solve(*a)
                trim=lambda h:{k:v for k,v in h.items() if k!='certificate_seconds'};audit,_=tests.audit(a,got)
                controls.append({'path':path,'reference_passed':True,'passed':bool(np.array_equal(expected[0],got[0]) and trim(expected[1])==trim(got[1])),'audit':audit})
        good=next(f for f in fixtures if any(a.get('health',{}).get('solver')==repair.NAME and a['accepted'] for a in f['fixture']['early_attempts']))
        for name,mutate in [('drop_early',lambda r:r['early_attempts'].pop(0)),('change_early_acceptance',lambda r:r['early_attempts'][0].update(accepted=False)),
              ('false_seed_count',lambda r:r['early_attempts'][0]['health'].update(seed_candidate_count=100)),('bad_near_rest_velocity',lambda r:r['early_attempts'][0]['velocity'].__setitem__(0,1.))]:
            bad=copy.deepcopy(good['fixture']);mutate(bad)
            try:auditor.evaluate(bad,good['before'])
            except (RuntimeError,ValueError,KeyError,IndexError):guards.append({'test':name,'passed':True})
            else:guards.append({'test':name,'passed':False})
    except Exception as e:failure={'error':repr(e),'traceback':traceback.format_exc()};job.commit(OUT/'failure.json',failure)
    api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
    for name,value in [('reports',reports),('controls',controls),('guards',guards),('fixtures',fixtures)]:job.commit(OUT/(name+'.json'),value)
    passed=failure is None and len(reports)==136 and all(x['passed'] for x in reports+guards+[c for c in controls if c.get('reference_passed')])
    r={'passed':passed,'new_trajectory_steps':0,'outer_count':len(reports),'outer_total_seconds':sum(x['seconds'] for x in reports),'outer_exact':sum(x['exact_velocity'] for x in reports),
       'controls_exact':sum(c.get('passed',False) for c in controls),'guards':guards,'failure':failure,'protocol_sha256':api.sha(DESIGN),'production_authorized':False,
       'artifacts':{str(x):api.sha(x) for x in OUT.glob('*.json')}}
    job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'passed':passed,'results_sha256':api.sha(OUT/'results.json')});print('EARLY_QUALIFIED',passed,r['outer_total_seconds'],r['outer_exact'],r['controls_exact'],flush=True)

if __name__=='__main__':run()
