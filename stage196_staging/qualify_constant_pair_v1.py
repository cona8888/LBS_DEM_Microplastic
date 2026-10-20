"""Zero-step arithmetic and held-outer-call identity on old and stress data."""
from pathlib import Path
import copy, os, sys, time, traceback
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage194_staging'))
import early_semismooth_dispatch_v1 as repair
import audit_early_semismooth_v1 as auditor
import constant_analytic_pair_v1 as candidate
q=repair.prior.q;job,api=q.job,q.api
WORK=ROOT/'stage196_designs/eight_hour_deadline_recovery_20260925/contract_01.json'
DESIGN=WORK.with_name('constant_pair_01.json')
OUT=ROOT/'stage196_evaluations/deadline_recovery_20260925/constant_pair_01'
FIXTURES=ROOT/'stage194_evaluations/evidence_repair_20260924/early_semismooth_qualification_01/fixtures.json'
PROFILE=ROOT/'stage196_runs/deadline_recovery_20260925/segment_profile_01/record.json.xz'

def run():
    work=api.read(WORK);end=job.policy.utc(work['work_end_utc']).timestamp()
    api.require(time.time()<end,'work clock');job.verify(api.read(job.DESIGN))
    old=api.read(FIXTURES)
    rec=q.independent_file(PROFILE,api.read(PROFILE.with_suffix('.seal.json'))['design_sha256'])
    profile_result=api.read(ROOT/'stage196_evaluations/deadline_recovery_20260925/segment_profile_01/results.json')
    oracle_path=ROOT/'stage194_runs/evidence_repair_20260924/early_semismooth_restart_01/call_01.json.xz'
    oracle=q.independent_file(oracle_path,api.read(oracle_path.with_suffix('.seal.json'))['design_sha256'])
    api.require(rec['rows']==oracle['rows'][:326] and len(rec['rows'])==326 and profile_result['audit']['passed'],'profile exact accepted partial prefix')
    trials=[x['fixture']['contact_trial_trace']['detailed_trials'][0] for x in old]+rec['contact_trial_trace']['detailed_trials']
    api.require(len(trials)==462,'frozen held-trial count')
    inputs={str(p):api.sha(p) for p in [WORK,Path(__file__),Path(candidate.__file__),FIXTURES,PROFILE,PROFILE.with_suffix('.seal.json'),oracle_path,oracle_path.with_suffix('.seal.json')]}
    job.commit(DESIGN,{'stage':'Stage196 pure analytic optimization','inputs':inputs,'new_trajectory_steps':0,'maximum_outer_calls':924,
        'maximum_pointwise_evaluations':12000,'arithmetic_order_unchanged':True,'production_authorized':False})
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'design_sha256':api.sha(DESIGN),'new_trajectory_steps':0})
    runtime=job.parent.engine.runtime;job.parent.b.old.parent.configure();rng=np.random.default_rng(196);checks=0;reports=[]
    def call(trial,enabled):
        job.clear_telemetry();runtime._calls.clear();job.fast.capture_systems=True
        runtime.probe.RECOVERY.portfolio.set_recovery_mode(False)
        start=time.perf_counter()
        with candidate.scope(enabled),repair.scope(runtime,True,end),job.prior.p.hot.scope(),job.parent.fix.scope(),job.deadline.scope(runtime,work['work_end_utc'],True),job.capture.scope(runtime,True),runtime.repair_scope(),job.observer.scope(runtime,True) as log:
            ans=job.observer.backend.inertial_contact_step(*copy.deepcopy(trial['outer_inputs']))
            fixture={'contact_trial_trace':copy.deepcopy(log),'rows':[{'velocity_generalized':ans[0].tolist(),'active_contact_ids':[int(c[0]) for c in trial['outer_inputs'][6]]}],
                'sweep_certificates':[{'dt_s':trial['outer_inputs'][8]}],'early_attempts':copy.deepcopy(job.fast.attempts),'fallback_systems':copy.deepcopy(job.capture.records),
                'result':{'stage119_repair_calls':copy.deepcopy(runtime._calls)},'repairs':copy.deepcopy(job.fast.old.telemetry)}
        seconds=time.perf_counter()-start
        audit=auditor.evaluate(fixture,{'state':{'q':trial['outer_inputs'][0]}})
        return ans,audit,seconds
    try:
        for index,trial in enumerate(trials):
            api.require(time.time()<end,'work clock')
            s=trial['inner_systems'][0]
            args=(*[np.asarray(s[k]) for k in ('vfree','mobility','jacobian','gaps_m')],s['dt_s'],s['friction'])
            old_both,*_=repair.prior.analytic.system(*args);new_both,*_=candidate.optimized_system(*args)
            ys=[np.zeros(len(s['gaps_m'])*3),np.full(len(s['gaps_m'])*3,-0.),rng.normal(size=len(s['gaps_m'])*3),rng.normal(size=len(s['gaps_m'])*3)*1e4]
            for y in ys:
                a=old_both(y);b=new_both(y);checks+=1
                api.require(all(x.tobytes()==z.tobytes() for x,z in zip(a,b)),'bitwise residual/Jacobian')
                b[0][0]=999.;checks+=1
                api.require(all(x.tobytes()==z.tobytes() for x,z in zip(a,new_both(y))),'memo mutation isolation')
            a,aa,ta=call(trial,False);b,ba,tb=call(trial,True)
            trim=lambda h:{k:v for k,v in h.items() if k!='certificate_seconds'}
            exact=a[0].tobytes()==b[0].tobytes() and trim(a[1])==trim(b[1])
            api.require(exact and aa['passed'] and ba['passed'],'exact held solve and independent gates')
            reports.append({'index':index,'exact':True,'baseline_seconds':ta,'candidate_seconds':tb,'audits_passed':True})
            if index%64==0:print('CONSTANT_PAIR',index,round(ta,4),round(tb,4),flush=True)
        api.verify_mapping(inputs);job.verify(api.read(job.DESIGN))
        before=sum(x['baseline_seconds'] for x in reports);after=sum(x['candidate_seconds'] for x in reports)
        result={'passed':True,'new_trajectory_steps':0,'pointwise_checks':checks,'held_comparisons':reports,'inputs':inputs,
            'baseline_seconds':before,'candidate_seconds':after,'speedup':before/after,'production_authorized':False,
            'profile_adjudication':{'original_profile_passed':False,'accepted_steps':326,'exact_oracle_prefix':True,'numerical_audit_passed':True,'reason':'Profiling reached unchanged 45-second per-call wall limit, not requested 1000-step cap.'}}
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
        print('CONSTANT_PAIR_PASS',len(reports),checks,before/after,flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'new_trajectory_steps':0,'completed_checks':checks,'held_comparisons':reports});raise

if __name__=='__main__':run()
