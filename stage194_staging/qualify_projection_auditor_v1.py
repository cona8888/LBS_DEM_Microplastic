"""Zero-step exact route/physical audit fixtures from fixed-pose outer replay."""
from pathlib import Path
import copy,os,sys,time
import numpy as np
import qualify_failure_codec_v1 as q
import sliding_projection_repair_v3 as repair
import audit_projection_routes_v1 as auditor
job,api=q.job,q.api;BASE=q.ROOT/'stage194_evaluations/evidence_repair_20260924';OUT=BASE/'route_audit_qualification_01'


def run():
    work=api.read(q.WORK);end=job.policy.utc(work['work_end_utc']).timestamp();api.require(time.time()<end,'work clock')
    source=BASE/'diagnostic_replay_01/failure_details.json';trials=api.read(source)['failed_outer_trials'];runtime=job.parent.engine.runtime
    qual=BASE/'sliding_qualification_03';api.require(api.read(qual/'results.json')['passed'],'matrix qualification')
    closure=q.ROOT/'stage194_designs/evidence_repair_20260924/sliding_qualification_03_sources.json';api.verify_mapping(api.read(closure)['source_sha256'])
    job.verify(api.read(job.DESIGN));OUT.mkdir(parents=True,exist_ok=False)
    inputs={str(p):api.sha(p) for p in (Path(__file__),Path(auditor.__file__),q.WORK,source,closure,qual/'results.json')}
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'inputs':inputs,'new_trajectory_steps':0,'max_outer_calls':5,'auditor_structure':auditor.STRUCTURAL_IDENTITY})
    reports=[];fixtures=[];job.parent.b.old.parent.configure()
    for i,t in enumerate(trials):
        api.require(time.time()<end,'work clock');job.clear_telemetry();runtime._calls.clear();job.fast.capture_systems=True
        runtime.probe.RECOVERY.portfolio.set_recovery_mode(False)
        with repair.scope(runtime,True,end),job.prior.p.hot.scope(),job.parent.fix.scope(),job.deadline.scope(runtime,work['work_end_utc'],True),job.capture.scope(runtime,True),runtime.repair_scope(),job.observer.scope(runtime,True) as log:
            answer=job.observer.backend.inertial_contact_step(*copy.deepcopy(t['outer_inputs']))
            fixture={'contact_trial_trace':copy.deepcopy(log),'rows':[{'velocity_generalized':answer[0].tolist(),'active_contact_ids':[int(c[0]) for c in t['outer_inputs'][6]]}],
                     'sweep_certificates':[{'dt_s':t['outer_inputs'][8]}],'early_attempts':copy.deepcopy(job.fast.attempts),'fallback_systems':copy.deepcopy(job.capture.records),
                     'result':{'stage119_repair_calls':copy.deepcopy(runtime._calls)},'repairs':copy.deepcopy(job.fast.old.telemetry)}
        before={'state':{'q':copy.deepcopy(t['outer_inputs'][0])}}
        check=auditor.evaluate(fixture,before);fixtures.append({'fixture':fixture,'before':before});reports.append(check)
        print('ROUTE_AUDIT',i,check['passed'],check['fallback_records'],flush=True)
    good=fixtures[0];guards=[]
    modifications=[('unrecognized_solver',lambda r:r['fallback_systems'][0]['health'].update(solver='unknown')),
      ('false_old_success',lambda r:r['repairs'][0].update(reduced_accepted=True)),
      ('missing_failure_cause',lambda r:r['result']['stage119_repair_calls'][0].pop('original_exception')),
      ('dropped_fallback',lambda r:r['fallback_systems'].pop()),
      ('changed_velocity',lambda r:r['contact_trial_trace']['detailed_trials'][0]['inner_systems'][0]['velocity'].__setitem__(0,1.)),
      ('negative_force',lambda r:r['contact_trial_trace']['detailed_trials'][0]['inner_systems'][0]['health']['reactions'].__setitem__(0,-1.)),
      ('false_trial_count',lambda r:r['contact_trial_trace']['trial_inner_counts'].append(1)),
      ('changed_gap',lambda r:r['contact_trial_trace']['detailed_trials'][0]['inner_systems'][0]['gaps_m'].__setitem__(0,1.))]
    for name,edit in modifications:
        bad=copy.deepcopy(good['fixture']);edit(bad)
        try:auditor.evaluate(bad,good['before'])
        except (RuntimeError,ValueError,KeyError):guards.append({'test':name,'passed':True})
        else:guards.append({'test':name,'passed':False})
    # Kernel and all non-routing scientific checks retain the same code object.
    api.require(auditor.kernel.__code__ is job.kernel.evaluate.__code__,'unchanged original numerical audit kernel')
    api.verify_mapping(inputs);job.verify(api.read(job.DESIGN));job.commit(OUT/'fixtures.json',fixtures)
    result={'passed':all(x['passed'] for x in reports+guards),'new_trajectory_steps':0,'fixed_pose_solve_fixtures':5,'guards':guards,'reports':reports,
            'kernel_bytecode_identical':True,'routing_structure':auditor.STRUCTURAL_IDENTITY,'inputs':inputs,'fixtures_sha256':api.sha(OUT/'fixtures.json'),
            'claim':'Fixed-pose force-solve fixtures only; synthetic row associations contain no advanced trajectory.'}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':result['passed'],'results_sha256':api.sha(OUT/'results.json')})
    print('ROUTE_AUDITOR_QUALIFIED',result['passed'],flush=True)


if __name__=='__main__':run()
