"""Hash-bound zero-step dispatch regression: 60 outer solves and old controls."""
from pathlib import Path
from types import SimpleNamespace
import copy,os,time,traceback
import numpy as np
import qualify_sliding_projection_v1 as tests
import projection_fallback_dispatch_v1 as repair
import audit_projection_routes_v2 as auditor
q=tests.q;job,api=q.job,q.api;BASE=tests.BASE
OUT=BASE/'fallback_dispatch_qualification_01'
DESIGN=q.ROOT/'stage194_designs/evidence_repair_20260924/fallback_dispatch_qualification_01.json'
RAW=q.ROOT/'stage194_runs/evidence_repair_20260924/trajectory_qualification_01/call_02.json.xz'
RAW_DESIGN=q.ROOT/'stage194_designs/evidence_repair_20260924/trajectory_qualification_01.json'

def run():
    w=api.read(q.WORK);end=job.policy.utc(w['work_end_utc']).timestamp();api.require(time.time()<end,'work clock')
    p=api.read(RAW_DESIGN);api.verify_mapping(p['inputs']);api.verify_mapping(p['sources'])
    rr=api.read(BASE/'trajectory_qualification_01/results.json');api.require(rr['passed'] and rr['artifacts'][str(RAW)]==api.sha(RAW),'sealed raw')
    raw=q.independent_file(RAW,api.sha(RAW_DESIGN));d=api.read(job.DESIGN);job.verify(d)
    matrix_design=q.ROOT/'stage172_designs/four_hour_work_20260923/solver_design_01.json';matrices=api.read(matrix_design)['matrices']
    paths=[q.WORK,RAW,RAW_DESIGN,matrix_design,BASE/'outer_qualification_01/results.json',BASE/'dispatch_profile_01/results.json']
    paths+=list(Path(__file__).parent.glob('*.py'))+[Path(x) for x in matrices]
    protocol={'stage':'Stage194 fallback order numerical qualification','inputs':{str(x):api.sha(x) for x in paths},'sources':d['sources'],
       'new_trajectory_steps':0,'maximum_outer_calls':60,'normalized_velocity_difference_max':1e-10,
       'prior_primary_and_reduced_paths_unchanged':True,'general_fallback_priority_changed':True,
       'physical_timestep_horizon_gate_changes':[],'production_authorized':False}
    job.commit(DESIGN,protocol);OUT.mkdir(parents=True,exist_ok=False)
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'protocol_sha256':api.sha(DESIGN),'new_trajectory_steps':0})
    runtime=job.parent.engine.runtime;job.parent.b.old.parent.configure();controls=[];reports=[];fixtures=[];guards=[];failure=None
    try:
        with job.prior.p.hot.scope(),job.parent.fix.scope():
            for path in matrices:
                api.require(time.time()<end,'work clock');s=api.read(path)
                aa=(*[np.asarray(s[k],float) for k in ('vfree','mobility','jacobian','gaps')],s['dt'],s['friction'],1e-10,25000)
                try:
                    with job.fast.old.scope(runtime,True):expected=runtime.mixed.solve(*aa)
                except (RuntimeError,ValueError,np.linalg.LinAlgError):controls.append({'path':path,'reference_passed':False,'not_promoted':True});continue
                with repair.scope(runtime,True,end),job.fast.old.scope(runtime,True):got=runtime.mixed.solve(*aa)
                trim=lambda h:{k:v for k,v in h.items() if k!='certificate_seconds'}
                check,_=tests.audit(aa,got)
                controls.append({'path':path,'reference_passed':True,'passed':bool(np.array_equal(expected[0],got[0]) and trim(expected[1])==trim(got[1])),'audit':check})
        trials=[('healthy',t,t['velocity']) for t in raw['contact_trial_trace']['detailed_trials']]
        trials += [('repaired_failure',r['observed_trial'],r['velocity']) for r in api.read(BASE/'outer_qualification_01/results.json')['reports']]
        api.require(len(trials)==60,'55 healthy and five previously failed fixed poses')
        for i,(label,t,expected) in enumerate(trials):
            api.require(time.time()<end,'work clock');job.clear_telemetry();runtime._calls.clear();job.fast.capture_systems=True
            runtime.probe.RECOVERY.portfolio.set_recovery_mode(False);start=time.perf_counter()
            with repair.scope(runtime,True,end),job.prior.p.hot.scope(),job.parent.fix.scope(),job.deadline.scope(runtime,w['work_end_utc'],True),job.capture.scope(runtime,True),runtime.repair_scope(),job.observer.scope(runtime,True) as log:
                answer=job.observer.backend.inertial_contact_step(*copy.deepcopy(t['outer_inputs']))
                fixture={'contact_trial_trace':copy.deepcopy(log),'rows':[{'velocity_generalized':answer[0].tolist(),'active_contact_ids':[int(c[0]) for c in t['outer_inputs'][6]]}],
                   'sweep_certificates':[{'dt_s':t['outer_inputs'][8]}],'early_attempts':copy.deepcopy(job.fast.attempts),'fallback_systems':copy.deepcopy(job.capture.records),
                   'result':{'stage119_repair_calls':copy.deepcopy(runtime._calls)},'repairs':copy.deepcopy(job.fast.old.telemetry)}
            seconds=time.perf_counter()-start;before={'state':{'q':t['outer_inputs'][0]}}
            audit=auditor.evaluate(fixture,before);inn=fixture['contact_trial_trace']['detailed_trials'][0]['inner_systems']
            checks=[tests.independent.physical(s) for s in inn]
            scale=max(np.linalg.norm(inn[0]['vfree']),1e-15)
            error=float(np.linalg.norm(answer[0]-np.asarray(expected))/scale)
            reports.append({'index':i,'label':label,'passed':audit['passed'] and error<=1e-10,'seconds':seconds,'normalized_velocity_difference':error,
                 'exact_velocity':answer[0].tolist()==expected,'audit':audit,'inner_physical_checks':checks})
            fixtures.append({'fixture':fixture,'before':before})
            if i%10==0:print('DISPATCH_OUTER',i,reports[-1]['passed'],seconds,error,flush=True)
        for i,fixture in enumerate(fixtures):
            if fixture['fixture']['fallback_systems']:good=fixture;break
        modifications=[('false_reduced_success',lambda r:r['repairs'][0].update(reduced_accepted=True)),
            ('missing_primary_failure',lambda r:r['result']['stage119_repair_calls'][0].pop('original_exception')),
            ('unknown_solver',lambda r:r['fallback_systems'][0]['health'].update(solver='unknown')),
            ('changed_velocity',lambda r:r['fallback_systems'][0]['velocity'].__setitem__(0,1.)),
            ('dropped_fallback',lambda r:r['fallback_systems'].pop()),
            ('changed_gap',lambda r:r['fallback_systems'][0]['gaps_m'].__setitem__(0,1.))]
        for name,edit in modifications:
            bad=copy.deepcopy(good['fixture']);edit(bad)
            try:auditor.evaluate(bad,good['before'])
            except (RuntimeError,ValueError,KeyError):guards.append({'test':name,'passed':True})
            else:guards.append({'test':name,'passed':False})
        a=tests.args(api.read(BASE/'contact_diagnosis_01/results.json')['captured_systems'][0]);sentinel=(object(),object())
        mock=SimpleNamespace(mixed=SimpleNamespace(solve=lambda *a:sentinel));orig=mock.mixed.solve
        bad=list(a);bad[3]=np.ones(3)
        with repair.scope(mock,True,end):guards.append({'test':'outside_guard_original_identity','passed':mock.mixed.solve(*bad) is sentinel})
        guards.append({'test':'scope_restored','passed':mock.mixed.solve is orig})
    except Exception as e:
        failure={'error':repr(e),'traceback':traceback.format_exc()};job.commit(OUT/'failure.json',failure)
    api.verify_mapping(protocol['inputs']);api.verify_mapping(protocol['sources'])
    for name,value in [('controls',controls),('reports',reports),('guards',guards),('fixtures',fixtures)]:job.commit(OUT/(name+'.json'),value)
    passed=failure is None and len(reports)==60 and all(x['passed'] for x in reports+guards+[x for x in controls if x['reference_passed']])
    result={'passed':passed,'new_trajectory_steps':0,'controls_exact':sum(x.get('passed',False) for x in controls),'outer_exact':sum(x['exact_velocity'] for x in reports),
       'outer_count':len(reports),'outer_total_seconds':sum(x['seconds'] for x in reports),'guards':guards,'failure':failure,
       'protocol_sha256':api.sha(DESIGN),'artifacts':{str(x):api.sha(x) for x in OUT.glob('*.json')},'production_authorized':False}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':passed,'results_sha256':api.sha(OUT/'results.json')})
    print('DISPATCH_QUALIFIED',passed,result['controls_exact'],result['outer_exact'],result['outer_total_seconds'],flush=True)

if __name__=='__main__':run()
