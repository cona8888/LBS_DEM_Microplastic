"""One original45s difficult-fine cost observation, capped at10000 steps.

A healthy incomplete_budget checkpoint is an explicitly censored measurement,
not a completed physical observation or passing former exact10000-step test.
No production or automatic successor is launched here.
"""
from pathlib import Path
from types import FunctionType
from datetime import timedelta
import copy,os,psutil,shutil,sys,time,traceback
import exact_dense_dispatch_v1 as candidate
import transaction_json_memo_v1 as storage
import measure_combined_fine_v1 as prior
ROOT,api,job,q=prior.ROOT,prior.api,prior.job,prior.q
WORK=prior.WORK;DESIGN=WORK.with_name('long_fine_01.json')
RUN=prior.RUN.with_name('long_fine_01');OUT=prior.OUT.with_name('long_fine_01')
ORACLE=prior.ORACLE
namespace={**prior.execute.__globals__,'codec':storage.codec,'DESIGN':DESIGN}
execute=FunctionType(prior.execute.__code__,namespace,prior.execute.__name__,prior.execute.__defaults__,prior.execute.__closure__)

def verify(d):
    prior.verify(api.read(prior.DESIGN));api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'immutable new protocol');api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    previous=api.read(prior.DESIGN)
    api.require(all(d[k]==previous[k] for k in ('cases','budget','numerical_gates','minimum_gap_semantics')),'all original scientific and runtime controls')
    api.require(execute.__code__ is prior.execute.__code__ and execute.__globals__['codec'] is storage.codec and execute.__globals__['DESIGN']==DESIGN,'original integration, explicit qualified transport')
    api.require(d['diagnostic_prior_recovery_steps']==56666 and d['diagnostic_maximum_new_steps']==10000 and 56666+10000+17000+4000+96<=100000,'reserve full-stack/restart budget');storage.verify_bindings()

def prepare():
    d=copy.deepcopy(api.read(prior.DESIGN));prior.verify(d);d.pop('binding');work=api.read(WORK)
    api.require(job.utc()<job.policy.utc(work['last_diagnostic_launch_utc']),'launch cutoff')
    refs=[OUT.parent/x/'results.json' for x in ('solver_brackets_01','trf_helpers_01','dense_dispatch_01','transaction_json_01','combined_fine_01')]
    for path in refs:
        r=api.read(path);api.require(r['passed'] and api.read(path.parent/'completion.json')['results_sha256']==api.sha(path),'sealed prerequisites')
    bench=OUT.parent/'transaction_json_01/benchmark.json';b=api.read(bench)
    api.require(b['passed'] and b['mean_speedup']>1.1 and api.read(bench.parent/'benchmark_completion.json')['benchmark_sha256']==api.sha(bench),'material verified storage speedup')
    dense=api.read(WORK.with_name('dense_dispatch_01.json'))
    files=[Path(__file__),Path(candidate.__file__),Path(storage.__file__),Path(storage.native.__file__)]
    inputs=[*refs,bench,bench.parent/'benchmark_completion.json',WORK,prior.DESIGN,WORK.with_name('dense_dispatch_01.json'),WORK.with_name('transaction_json_harness_01.json'),OUT.parent/'dense_helper_edges_01.json']
    d.update(stage='Stage199 one-call original-budget fine-contact cost measurement',sources={**d['sources'],**dense['sources'],**{str(x):api.sha(x) for x in files}},inputs={**d['inputs'],**{str(x):api.sha(x) for x in inputs}},
        diagnostic_prior_recovery_steps=56666,diagnostic_maximum_new_steps=10000,diagnostic_wall_seconds=1200,calls={'serial':10000},
        criterion='One unchanged45-second integration call capped at10000 accepted steps; at least3580 exact archived rows, every new row independently audited. Healthy positive-step incomplete_budget is measured and reported as censored, never full observation or success of an earlier exact-cap contract.',
        production_authorized=False,expected_oracle_status='paused_checkpoint',expected_statuses=['paused_checkpoint','incomplete_budget'])
    d['binding']=api.digest(d);job.commit(DESIGN,d);verify(d);print('LONG_FINE_PROTOCOL',api.sha(DESIGN),flush=True)

def run():
    d=api.read(DESIGN);verify(d);work=api.read(WORK);api.require(job.utc()<job.policy.utc(work['last_diagnostic_launch_utc']),'last diagnostic launch')
    for x in psutil.process_iter(['name','cmdline']):
        if x.pid!=os.getpid() and 'python' in (x.info['name'] or '').lower():api.require('matdem_microplastic' not in ' '.join(x.info['cmdline'] or []).lower(),'one owned worker')
    api.require(shutil.disk_usage(RUN.anchor).free>work['minimum_disk_reserve_bytes']+4*storage.base.MAX_COMPRESSED,'disk reserve')
    info=prior.old.pre.wrapper.affinity.bind(14);RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    stop=min(job.utc()+timedelta(seconds=d['diagnostic_wall_seconds']),job.policy.utc(work['work_end_utc']))
    job.commit(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':job.utc().isoformat(),'stop_utc':stop.isoformat(),'reserved_steps':10000,'prior_recovery_steps':56666,'design_sha256':api.sha(DESIGN),'affinity':info})
    path=RUN/'serial.json.xz'
    try:
        oracle=q.independent_file(ORACLE,api.sha(prior.old.DESIGN));case,initial=prior.old.seed(d);job.commit(RUN/'initial.json',initial)
        import numpy as np
        candidate.batch.equation_arrays(np.zeros((1,9)),0,.3);candidate.batch.bracket_indices(np.zeros(1))
        candidate.prior.column_norms(np.eye(9));candidate.prior.max_abs(np.zeros(9));candidate.prior.all_finite(np.zeros(9));candidate.prior.all_finite(np.eye(9))
        s=oracle['contact_trial_trace']['detailed_trials'][0]['inner_systems'][0];args=(*[np.asarray(s[k]) for k in ('vfree','mobility','jacobian','gaps_m')],s['dt_s'],s['friction']);f,*_=candidate.compiled.optimized_system(*args);f(np.zeros(3*len(s['gaps_m'])))
        storage.raw_bytes({'warm':[0.,-0.]});job.parent.b.old.parent.configure()
        with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
            geo=prior.old.pre.prior.geometry();job.commit(path.with_suffix('.launch.json'),{'reserved_steps':10000,'input_checkpoint_sha256':api.digest(initial),'utc':job.utc().isoformat()})
            with candidate.scope('compiled_direct'),prior.old.pre.wrapper.baseline.repair.scope(job.parent.engine.runtime,True,stop.timestamp()):
                rec,state,_,tx=execute(d,case,copy.deepcopy(initial),path,10000,None,stop.isoformat())
            stats=copy.deepcopy(storage.last_stats);n=len(rec['rows']);job.commit(path.with_suffix('.accounting.json'),{'accepted_steps':n,'cumulative_recovery_steps':56666+n,'raw_sha256':api.sha(path)})
            tick=time.perf_counter();ind=q.independent_file(path,api.sha(DESIGN));read_s=time.perf_counter()-tick
            api.require(storage.base.raw_bytes(ind)==storage.base.raw_bytes(rec),'independent full original bytes')
            check=job.kernel.evaluate(ind,case['spec'],job.binding(d,case),initial,geo,api.sha(DESIGN),d['minimum_gap_semantics']);job.commit(path.with_suffix('.audit.json'),check)
        status=rec['result']['status'];api.require(3580<=n<=10000 and status in d['expected_statuses'] and check['passed'] and not rec['result']['rejected'],'complete saved prefix, original numerical/budget gates')
        api.require(storage.base.raw_bytes(rec['rows'][:3580])==storage.base.raw_bytes(oracle['rows']),'every archived known row exact')
        span=check['stop_s']-check['start_s'];factor=case['spec']['horizon_s']*work['runtime_and_storage_margin']/span/3600
        available=(job.policy.utc(work['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600
        result={'passed':True,'measurement_passed':True,'numerics_passed':True,'status':status,'requested_cap':10000,'complete_requested_cap':n==10000 and status=='paused_checkpoint','complete_observation':False,
            'new_accepted_steps':n,'cumulative_recovery_steps':56666+n,'remaining_recovery_steps':100000-56666-n,'exact_known_rows':3580,'new_rows_beyond_reference':n-3580,
            'compute_seconds':rec['compute_call_wall_s'],'transaction_seconds':tx,'independent_read_seconds':read_s,'audit_seconds':check['audit_seconds'],'simulated_seconds':span,'audit':check,'serialization_memo_stats':stats,
            'fine_compute_hours_with_margin':rec['compute_call_wall_s']*factor,'fine_transaction_hours_with_margin':tx*factor,'available_simulation_hours':available,'local_fine_runtime_scenario_passed':tx*factor<=available,'full_stack_qualified':False,'production_authorized':False,
            'claim':'Single original45-second cap observation only. Censored budget stops remain incomplete; timing is a conservative measured-regime scenario, not a hard lower bound, full six-case forecast, release result or empirical validation.',
            'protocol_sha256':api.sha(DESIGN),'artifacts':{str(x):api.sha(x) for x in RUN.rglob('*') if x.is_file()}}
        verify(d);job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('LONG_FINE_MEASUREMENT',n,status,'compute',rec['compute_call_wall_s'],'tx',tx,'scenario',tx*factor,'available',available,flush=True)
    except Exception as e:
        account=path.with_suffix('.accounting.json');known=api.read(account)['accepted_steps'] if account.exists() else None
        job.commit(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'known_new_accepted_steps':known,'accepted_step_accounting_unresolved':known is None and path.with_suffix('.launch.json').exists()});raise

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
