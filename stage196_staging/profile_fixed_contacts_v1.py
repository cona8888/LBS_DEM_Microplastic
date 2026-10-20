"""Bounded held-pose profile and exact pure-cache comparison; no trajectory."""
from pathlib import Path
import copy, cProfile, io, os, pstats, sys, time, traceback
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage194_staging'))
import early_semismooth_dispatch_v1 as repair
import audit_early_semismooth_v1 as auditor
import memo_analytic_pair_v1 as candidate
q=repair.prior.q; job,api=q.job,q.api
WORK=ROOT/'stage196_designs/eight_hour_deadline_recovery_20260925/contract_01.json'
BASE=ROOT/'stage194_evaluations/evidence_repair_20260924/early_semismooth_qualification_01'
OUT=ROOT/'stage196_evaluations/deadline_recovery_20260925/fixed_profile_01'

def run():
    w=api.read(WORK); end=job.policy.utc(w['work_end_utc']).timestamp()
    api.require(time.time()<end,'work clock')
    api.require(all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')),'BLAS1')
    job.verify(api.read(job.DESIGN))
    old=api.read(BASE/'results.json'); seal=api.read(BASE/'completion.json')
    api.require(old['passed'] and seal['results_sha256']==api.sha(BASE/'results.json'),'fixed-pose prerequisite')
    api.verify_mapping(old['artifacts'])
    fixtures=api.read(BASE/'fixtures.json'); api.require(len(fixtures)==136,'frozen fixture count')
    inputs={str(p):api.sha(p) for p in [WORK,Path(__file__),Path(candidate.__file__),BASE/'fixtures.json',BASE/'results.json',BASE/'completion.json']}
    OUT.mkdir(parents=True,exist_ok=False)
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'inputs':inputs,'new_trajectory_steps':0,'maximum_fixed_pose_calls':544})
    runtime=job.parent.engine.runtime; job.parent.b.old.parent.configure()
    results=[]; failures=[]; prof=cProfile.Profile()
    def call(t,enabled,profile=False):
        job.clear_telemetry();runtime._calls.clear();job.fast.capture_systems=True
        runtime.probe.RECOVERY.portfolio.set_recovery_mode(False)
        start=time.perf_counter()
        if profile: prof.enable()
        with candidate.scope(enabled),repair.scope(runtime,True,end),job.prior.p.hot.scope(),job.parent.fix.scope(),job.deadline.scope(runtime,w['work_end_utc'],True),job.capture.scope(runtime,True),runtime.repair_scope(),job.observer.scope(runtime,True) as log:
            ans=job.observer.backend.inertial_contact_step(*copy.deepcopy(t['outer_inputs']))
            fixture={'contact_trial_trace':copy.deepcopy(log),'rows':[{'velocity_generalized':ans[0].tolist(),'active_contact_ids':[int(c[0]) for c in t['outer_inputs'][6]]}],
                'sweep_certificates':[{'dt_s':t['outer_inputs'][8]}],'early_attempts':copy.deepcopy(job.fast.attempts),'fallback_systems':copy.deepcopy(job.capture.records),
                'result':{'stage119_repair_calls':copy.deepcopy(runtime._calls)},'repairs':copy.deepcopy(job.fast.old.telemetry)}
        if profile: prof.disable()
        seconds=time.perf_counter()-start
        check=auditor.evaluate(fixture,{'state':{'q':t['outer_inputs'][0]}})
        return ans,fixture,check,seconds
    try:
        for i,source in enumerate(fixtures):
            api.require(time.time()<end,'work clock')
            t=source['fixture']['contact_trial_trace']['detailed_trials'][0]
            expected,_,ea,et=call(t,False)
            got,new,ga,gt=call(t,True)
            trim=lambda h:{k:v for k,v in h.items() if k!='certificate_seconds'}
            exact=np.array_equal(expected[0],got[0]) and trim(expected[1])==trim(got[1])
            rows={'index':i,'exact_velocity_and_health':bool(exact),'baseline_seconds':et,'candidate_seconds':gt,'audit_passed':ea['passed'] and ga['passed']}
            results.append(rows)
            api.require(exact and rows['audit_passed'],'exact pure-cache comparison')
            if i%32==0: print('FIXED_COMPARE',i,et,gt,flush=True)
        # Profile separate held-pose evaluations, excluded from timing comparisons.
        for source in fixtures[:32]:
            api.require(time.time()<end,'work clock')
            t=source['fixture']['contact_trial_trace']['detailed_trials'][0]
            call(t,False,True)
        # Mutation and distinct-input guards for the one-entry pure function cache.
        t=fixtures[0]['fixture']['contact_trial_trace']['detailed_trials'][0]
        s=t['inner_systems'][0]
        args=(*[np.asarray(s[k]) for k in ('vfree','mobility','jacobian','gaps_m')],s['dt_s'],s['friction'])
        with candidate.scope(True): f,*_=repair.prior.analytic.system(*args)
        y=np.zeros(9); a=f(y); expected=[v.copy() for v in a];a[0][0]=999.;api.require(all(np.array_equal(x,z) for x,z in zip(f(y),expected)),'returned array mutation isolation')
        y[0]=1e-3; fresh,*_=repair.prior.analytic.system(*args);api.require(all(np.array_equal(x,z) for x,z in zip(f(y),fresh(y))),'changed input not cached')
    except Exception as e:
        prof.disable();failures.append({'error':repr(e),'traceback':traceback.format_exc()})
        job.commit(OUT/'failure.json',failures[-1])
    api.verify_mapping(inputs);job.verify(api.read(job.DESIGN))
    stream=io.StringIO();pstats.Stats(prof,stream=stream).sort_stats('cumulative').print_stats(50)
    profile=stream.getvalue();job.commit(OUT/'profile.json',{'text':profile,'new_trajectory_steps':0})
    baseline=sum(x['baseline_seconds'] for x in results);new=sum(x['candidate_seconds'] for x in results)
    result={'passed':not failures and len(results)==136,'new_trajectory_steps':0,'fixed_comparisons':results,'failures':failures,'baseline_seconds':baseline,'candidate_seconds':new,
        'speedup':baseline/new if new else None,'inputs':inputs,'profile_sha256':api.sha(OUT/'profile.json'),'production_ready':False,'claim':'Held-pose performance/identity only; no full-path completion or throughput guarantee.'}
    job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':result['passed'],'results_sha256':api.sha(OUT/'results.json')})
    print('FIXED_PROFILE_DONE',result['passed'],result['speedup'],flush=True);print(profile,flush=True)

if __name__=='__main__':run()
