"""Complete fixed-pose trial replay and independent route audit, zero trajectories."""
from pathlib import Path
from datetime import datetime,timezone
import copy,os,time,traceback
import numpy as np
import authenticate_failed_system_v1 as source
import two_contact_cone_feasibility_v1 as candidate
import audit_cone_feasibility_v1 as auditor
job,api,ROOT,frozen=source.job,source.api,source.ROOT,source.frozen
OUT=ROOT/'stage206_evaluations/contact_failure_20260930/outer_qualification_01'
CONTRACT=ROOT/'stage206_designs/contact_failure_20260930/local_qualification_01.json'

def run():
    d=api.read(job.DESIGN);job.verify(d);contract=api.read(CONTRACT)
    held=ROOT/'stage206_evaluations/contact_failure_20260930/held_qualification_01/results.json'
    api.require(api.read(held)['passed'] and api.read(held.parent/'completion.json')['results_sha256']==api.sha(held),'held covariance prerequisite')
    packs=[ROOT/'stage201_evaluations/contact_repair_20260928/failed_evidence_01/failed_systems.json',
           ROOT/'stage201_evaluations/contact_repair_20260928/extension_failure_audit_01/failed_systems.json',source.OUT/'failed_systems.json']
    trials=[t for p in packs for t in api.read(p)['failed_outer_trials']]
    api.require(len(trials)==contract['maximum_fixed_pose_outer_calls']==28,'fixed-pose zero-trajectory bound')
    inputs={str(p):api.sha(p) for p in packs+[CONTRACT,held,job.DESIGN,Path(__file__),Path(candidate.__file__),Path(auditor.__file__)]}
    stop=time.time()+1800;stop_iso=datetime.fromtimestamp(stop,timezone.utc).isoformat()
    runtime=job.parent.engine.runtime;job.parent.b.old.parent.configure();frozen.pre.candidate.warm()
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),new_trajectory_steps=0,inputs=inputs))
    rows=[];failed=None
    try:
        for index,t in enumerate(trials):
            api.require(time.time()<stop,'bounded fixed-pose work')
            job.clear_telemetry();runtime._calls.clear();candidate.telemetry.clear();job.fast.capture_systems=True;runtime.probe.RECOVERY.portfolio.set_recovery_mode(False)
            with candidate.scope(runtime,True,stop),frozen.pre.candidate.scope('compiled_direct'),frozen.pre.previous.baseline.repair.scope(runtime,True,stop),job.prior.p.hot.scope(),job.parent.fix.scope(),job.deadline.scope(runtime,stop_iso,True),job.capture.scope(runtime,True),runtime.repair_scope(),job.observer.scope(runtime,True) as log:
                q=job.observer.backend.inertial_contact_step(*copy.deepcopy(t['outer_inputs']))
                fixture={'contact_trial_trace':copy.deepcopy(log),'rows':[{'velocity_generalized':q[0].tolist(),'active_contact_ids':[int(c[0]) for c in t['outer_inputs'][6]]}],
                         'sweep_certificates':[{'dt_s':t['outer_inputs'][8]}],'early_attempts':copy.deepcopy(job.fast.attempts),'fallback_systems':copy.deepcopy(job.capture.records),
                         'result':{'stage119_repair_calls':copy.deepcopy(runtime._calls)},'repairs':copy.deepcopy(job.fast.old.telemetry)}
            before={'state':{'q':t['outer_inputs'][0]}};check=auditor.evaluate(fixture,before)
            exact=True
            if index<27:
                old=api.read(ROOT/'stage201_evaluations/contact_repair_20260928/polish_qualification_04'/('fixture_%02d.json'%index))['fixture']
                exact=fixture['rows']==old['rows']
            row=dict(index=index,passed=check['passed'] and exact,old_velocity_exact=exact,audit=check)
            rows.append(row);job.commit(OUT/('fixture_%02d.json'%index),dict(fixture=fixture,before=before,outer_trial_sha256=api.digest(t)))
            print('OUTER_FEASIBILITY',index,row['passed'],flush=True)
        api.require(len(rows)==28 and all(r['passed'] for r in rows),'all fixed-pose original gates')
    except Exception as error:
        failed=dict(error=repr(error),traceback=traceback.format_exc());job.commit(OUT/'failure.json',failed)
    api.verify_mapping(inputs);job.verify(d)
    result=dict(passed=failed is None and len(rows)==28 and all(r['passed'] for r in rows),new_trajectory_steps=0,inputs=inputs,outer=rows,failure=failed,
                auditor_structure=auditor.STRUCTURAL_IDENTITY,claim='Fixed-pose qualification only. Negative/provenance controls and separately authorized trajectory qualification remain pending. Stage205 failure retained.')
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(passed=result['passed'],results_sha256=api.sha(OUT/'results.json')))
    print('OUTER_QUALIFICATION_COMPLETE',result['passed'],flush=True)

if __name__=='__main__':run()
