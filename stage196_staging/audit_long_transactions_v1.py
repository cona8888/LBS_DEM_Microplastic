"""Independent closure of the incomplete cost probe; never production authority."""
from pathlib import Path
import os, psutil, time, traceback
import measure_long_transactions_v1 as measured
import constant_analytic_pair_v1 as constant
import batch_analytic_pair_v1 as batch
import numpy as np
pre=measured.pre;job,api,q=pre.job,pre.api,pre.q
OUT=measured.OUT.parent/'deadline_blocker_01'


def run():
    w=api.read(pre.wrapper.WORK);api.require(job.utc()<job.policy.utc(w['work_end_utc']),'work clock')
    p=api.read(measured.DESIGN);measured.verify(p);d=api.read(job.DESIGN)
    r=api.read(measured.OUT/'results.json')
    api.require(api.read(measured.OUT/'completion.json')['results_sha256']==api.sha(measured.OUT/'results.json'),'sealed failed measurement')
    api.verify_mapping(r['artifacts'])
    api.require(not r['passed'] and r['new_accepted_steps']==4915 and r['window_new_accepted_steps']==30241,'failed probe exact ledger')
    api.require(len(r['measurements'])==1 and r['unlaunched_calls']==[{'label':'healthy_prefix','steps':9641}],'unexecuted reservation not counted')
    launch=api.read(measured.RUN/'launch.json');api.require(not psutil.pid_exists(launch['pid']),'measurement worker retired')
    affinity=pre.wrapper.affinity.bind(14)
    OUT.mkdir(parents=True,exist_ok=False)
    job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'source_sha256':api.sha(__file__),'new_trajectory_steps':0,'owned_affinity':affinity})
    try:
        item=r['measurements'][0];path=Path(item['path']);independent=q.independent_file(path,api.sha(job.DESIGN))
        decoded,state=job.codec.read_record(path,api.sha(job.DESIGN))
        api.require(job.codec.base.raw_bytes(independent)==job.codec.base.raw_bytes(decoded),'independent complete compressed/raw/history reconstruction')
        rec=independent;case,cp=pre.stress_seed(d)
        api.require(len(rec['rows'])==4915 and rec['result']['status']=='incomplete_budget' and rec['result']['rejected']==0,'incomplete requested cap with zero rejected trials')
        api.require(rec['step_cap']==10000 and rec['input_checkpoint_sha256']==api.digest(cp),'frozen requested cap and input')
        job.parent.b.old.parent.configure()
        with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
            check=job.kernel.evaluate(rec,case['spec'],job.binding(d,case),cp,pre.prior.geometry(),api.sha(job.DESIGN),d['minimum_gap_semantics'])
        api.require(check['passed'] and not check['complete_observation'],'only accepted prefix is numerically healthy')
        trim=lambda x:{k:v for k,v in x.items() if k!='audit_seconds'}
        api.require(trim(check)==trim(item['numerical_audit']),'independent complete summary reproduction')
        oracle=q.independent_file(Path(d['stress_oracle_raw']),api.sha(d['stress_oracle_design']))
        api.require(rec['rows'][:len(oracle['rows'])]==oracle['rows'],'exact archived repaired prefix')
        account=api.read(path.with_suffix('.accounting.json'));reservation=api.read(path.with_suffix('.launch.json'))
        api.require(account['accepted_steps']==4915 and reservation['reserved_steps']==10000 and account['raw_sha256']==api.sha(path),'reservation resolved without inventing missing steps')
        # Same inputs and owned core compare both arithmetic implementations;
        # this avoids comparing CPU-affinity effects across earlier timings.
        fixtures=api.read(pre.ROOT/'stage194_evaluations/evidence_repair_20260924/early_semismooth_qualification_01/fixtures.json')
        systems=[x['fixture']['contact_trial_trace']['detailed_trials'][0]['inner_systems'][0] for x in fixtures[:16]]
        rng=np.random.default_rng(19602);timings=[];pointwise=0
        for s in systems:
            args=(*[np.asarray(s[k]) for k in ('vfree','mobility','jacobian','gaps_m')],s['dt_s'],s['friction'])
            f,*_=constant.optimized_system(*args);g,*_=batch.optimized_system(*args)
            ys=rng.normal(size=(16,len(s['gaps_m'])*3));ys[0]*=0
            for y in ys:
                a=f(y);b=g(y);api.require(all(x.tobytes()==z.tobytes() for x,z in zip(a,b)),'direct candidate arithmetic identity');pointwise+=1
            times=[]
            for fn in (f,g,g,f):
                tick=time.perf_counter()
                for _ in range(16):
                    for y in ys:fn(y)
                times.append(time.perf_counter()-tick)
            timings.append({'constant_seconds':times[0]+times[3],'batch_seconds':times[1]+times[2]})
        ca=sum(x['constant_seconds'] for x in timings);ba=sum(x['batch_seconds'] for x in timings)
        horizon=case['spec']['horizon_s'];dt=item['simulated_seconds'];margin=w['preserve_runtime_margin']
        compute_hours=item['compute_seconds']/dt*horizon*margin/3600
        transaction_hours=item['transaction_seconds']/dt*horizon*margin/3600
        serial_accounted_hours=(item['transaction_seconds']+item['read_seconds']+item['audit_seconds'])/dt*horizon*margin/3600
        available=(job.policy.utc(w['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600
        api.require(compute_hours>available,'even repaired-regime compute-only conservative scenario misses deadline')
        batch_result=pre.ROOT/'stage196_evaluations/deadline_recovery_20260925/batch_pair_01/results.json'
        br=api.read(batch_result);api.require(br['passed'] and api.read(batch_result.parent/'completion.json')['results_sha256']==api.sha(batch_result),'sealed zero-step batch verification')
        api.verify_mapping(br['inputs'])
        inputs=[measured.DESIGN,measured.OUT/'results.json',measured.OUT/'completion.json',job.DESIGN,pre.wrapper.WORK,batch_result,
            Path(constant.__file__),Path(batch.__file__),Path(__file__),path,path.with_suffix('.seal.json'),path.with_suffix('.accounting.json')]
        result={'passed':True,'purpose':'Independent audit of failed/incomplete resource qualification, not production readiness',
            'production_ready':False,'requested_call_passed':False,'deadline_gate_passed':False,'new_trajectory_steps':0,
            'window_new_accepted_steps':30241,'unresolved_reservations':[],
            'accepted_prefix_steps':4915,'accepted_prefix_numerical_audit':check,'complete_observation':False,
            'original_call_wall_cap_seconds':45,'actual_compute_seconds':item['compute_seconds'],
            'compute_only_hours_if_measured_regime_persists_with_margin':compute_hours,
            'transaction_hours_if_measured_regime_persists_with_margin':transaction_hours,
            'serial_transaction_read_audit_hours_with_margin':serial_accounted_hours,
            'available_simulation_hours':available,'scenario_case':case['id'],'horizon_s':horizon,'runtime_margin':margin,
            'scenario_caveat':'Worst measured contact-regime extrapolation, not a mathematical lower bound or a prediction of every future contact. No verified full-campaign fit exists.',
            'additional_batch_candidate':{'pointwise_checks':pointwise,'timings':timings,'constant_seconds':ca,'batch_seconds':ba,'speedup_over_current_constant':ca/ba,
                'adopted':False,'reason':'No trajectory or full-stack qualification; held-call speed is not production readiness.'},
            'measured_worker_retired':True,'old_failed_evidence_unchanged':True,'inputs':{str(x):api.sha(x) for x in inputs},
            'next_boundary':'No fresh production launch under failed runtime/call-cap gates. Preserve original physics, horizons and six cases; requires further authorized, independently qualified solver/hardware improvement or deadline decision.'}
        measured.verify(p);job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
        print('INDEPENDENT_BLOCKER_CONFIRMED',4915,'window',30241,'compute_only_h',compute_hours,'available_h',available,'batch_vs_constant',ca/ba,flush=True)
    except Exception as e:
        job.commit(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0});raise


if __name__=='__main__':run()
