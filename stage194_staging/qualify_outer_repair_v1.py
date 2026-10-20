"""Replay five fixed-pose outer solves; zero trajectory steps and no state advance."""
from pathlib import Path
import copy,os,sys,time
import numpy as np
import qualify_failure_codec_v1 as q
import sliding_projection_repair_v3 as repair
sys.path.insert(0,str(q.ROOT/'stage183_staging'))
import audit_fallback_systems_v1 as independent
job,api=q.job,q.api;BASE=q.ROOT/'stage194_evaluations/evidence_repair_20260924';OUT=BASE/'outer_qualification_01'


def run():
    work=api.read(q.WORK);end=job.policy.utc(work['work_end_utc']).timestamp();api.require(time.time()<end,'work clock')
    qual=BASE/'sliding_qualification_03';r=api.read(qual/'results.json');api.require(r['passed'] and api.read(qual/'completion.json')['results_sha256']==api.sha(qual/'results.json'),'matrix qualification')
    api.verify_mapping(api.read(q.ROOT/'stage194_designs/evidence_repair_20260924/sliding_qualification_03_sources.json')['source_sha256'])
    job.verify(api.read(job.DESIGN));details=api.read(BASE/'diagnostic_replay_01/failure_details.json');runtime=job.parent.engine.runtime
    OUT.mkdir(parents=True,exist_ok=False);inputs={str(p):api.sha(p) for p in (Path(__file__),Path(repair.__file__),q.WORK,qual/'results.json',BASE/'diagnostic_replay_01/failure_details.json')}
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'inputs':inputs,'new_trajectory_steps':0,'max_outer_calls':5})
    reports=[];job.parent.b.old.parent.configure()
    for i,t in enumerate(details['failed_outer_trials']):
        api.require(time.time()<end,'work clock');job.clear_telemetry();job.fast.capture_systems=True
        runtime.probe.RECOVERY.portfolio.set_recovery_mode(details['rejected_trials'][i]['attempt']>0)
        start=time.perf_counter();entry={'index':i,'source_trial_sha256':api.digest(t)}
        with repair.scope(runtime,True,end),job.prior.p.hot.scope(),job.parent.fix.scope(),job.deadline.scope(runtime,work['work_end_utc'],True),job.capture.scope(runtime,True),runtime.repair_scope(),job.observer.scope(runtime,True) as log:
            try:
                answer=job.observer.backend.inertial_contact_step(*copy.deepcopy(t['outer_inputs']))
                observed=copy.deepcopy(log['detailed_trials'][0]);original=t['inner_systems'][0];first=observed['inner_systems'][0]
                for key in ('vfree','mobility','jacobian','gaps_m','dt_s','friction','tolerance','maxiter'):api.require(first[key]==original[key],'exact original failed first-inner input '+key)
                audits=[independent.physical(s) for s in observed['inner_systems']]
                vel,h=answer;old,bg,body,R,L,mass=[np.asarray(x,float) for x in t['outer_inputs'][:6]];dt=t['outer_inputs'][8]
                drag=R.copy();drag[:3,:3]*=h['finite_re_multiplier'];J=np.asarray(observed['inner_systems'][-1]['jacobian']);f=np.asarray(h['contact']['reactions'])
                acc=mass@(vel-old)/dt;slip=drag@(vel-bg);lub=L@vel;reaction=J.T@f
                residual=acc+slip+lub-body-reaction;den=max(*(np.linalg.norm(x) for x in (acc,slip,lub,body,reaction,drag@bg)),1e-30)
                balance=float(np.linalg.norm(residual)/den);api.require(balance<=1e-8,'independent full outer momentum')
                entry.update(passed=True,velocity=vel.tolist(),health=h,inner_audits=audits,independent_outer_momentum=balance,
                             exact_first_failed_input_reproduced=True,observed_trial=observed,fallback_systems=copy.deepcopy(job.capture.records))
            except Exception as e:entry.update(passed=False,error=repr(e),observed_log=copy.deepcopy(log))
        entry['seconds']=time.perf_counter()-start;reports.append(entry);print('OUTER_REPLAY',i,entry['passed'],entry.get('error'),flush=True)
    api.verify_mapping(inputs);job.verify(api.read(job.DESIGN))
    result={'passed':all(e['passed'] for e in reports),'new_trajectory_steps':0,'reports':reports,'inputs':inputs,
            'claim':'Fixed-pose nonlinear solve verification only; trajectory/restart/cost still unqualified.'}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':result['passed'],'results_sha256':api.sha(OUT/'results.json')})


if __name__=='__main__':run()
