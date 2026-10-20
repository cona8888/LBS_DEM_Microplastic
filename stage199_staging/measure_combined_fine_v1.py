"""One 3580-step exact diagnostic; no production or automatic successor."""
from pathlib import Path
from types import FunctionType
from datetime import timedelta
import copy,os,psutil,shutil,sys,time,traceback
import exact_solver_dispatch_v1 as candidate
import native_storage_v2 as storage
ROOT=candidate.ROOT
sys.path.insert(0,str(ROOT/'stage198_staging'))
import probe_exact_fine_v1 as old
api,job,q=old.api,old.job,old.q
WORK=ROOT/'stage199_designs/eight_hour_optimization_20260926/contract_01.json'
DESIGN=WORK.with_name('combined_fine_01.json')
RUN=Path('D:/MATDEM_MICROPLASTIC/stage199_runs/eight_hour_optimization_20260926/combined_fine_01')
OUT=ROOT/'stage199_evaluations/eight_hour_optimization_20260926/combined_fine_01'
ORACLE=old.RUN/'serial.json.xz'
namespace={**old.execute.__globals__,'codec':storage.codec,'DESIGN':DESIGN}
execute=FunctionType(old.execute.__code__,namespace,old.execute.__name__,old.execute.__defaults__,old.execute.__closure__)

def verify(d):
    old.verify(api.read(old.DESIGN));api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'new immutable binding');api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    previous=api.read(old.DESIGN)
    api.require(all(d[k]==previous[k] for k in ('cases','budget','numerical_gates','minimum_gap_semantics')),'unchanged physics and numerical contract')
    api.require(execute.__code__ is old.execute.__code__ and execute.__globals__['codec'] is storage.codec and execute.__globals__['DESIGN']==DESIGN,'explicit new codec and unchanged integration')
    api.require(d['diagnostic_prior_recovery_steps']==53086 and d['diagnostic_maximum_new_steps']==3580 and 53086+3580<=100000,'bounded inclusive ledger');storage.verify_bindings()

def prepare():
    d=copy.deepcopy(api.read(old.DESIGN));old.verify(d);d.pop('binding');work=api.read(WORK)
    api.require(job.utc()<job.policy.utc(work['last_diagnostic_launch_utc']),'launch cutoff')
    prerequisite=[OUT.parent/x/'results.json' for x in ('canonical_native_01','native_storage_02','solver_dispatch_01')]
    for path in prerequisite:
        r=api.read(path);api.require(r['passed'] and api.read(path.parent/'completion.json')['results_sha256']==api.sha(path),'sealed zero-step qualification')
        if 'inputs' in r:api.verify_mapping(r['inputs'])
    speed=api.read(prerequisite[2])['timings'];api.require(speed['direct']/speed['compiled_direct']>1.1,'material same-solver measured gain before spending steps')
    sources=[Path(__file__),Path(candidate.__file__),Path(candidate.batch.__file__),Path(storage.__file__),Path(storage.canonical.__file__)]
    inputs=[WORK,old.DESIGN,ORACLE,ORACLE.with_suffix('.seal.json'),old.OUT.parent/'independent_closure_01/results.json',*prerequisite,OUT.parent/'solver_helper_edges_01.json',WORK.with_name('solver_dispatch_01.json'),WORK.with_name('native_storage_harness_02.json')]
    d.update(stage='Stage199 combined exact fine cost diagnostic',sources={**d['sources'],**{str(x):api.sha(x) for x in sources}},inputs={**d['inputs'],**{str(x):api.sha(x) for x in inputs}},
        diagnostic_prior_recovery_steps=53086,diagnostic_maximum_new_steps=3580,diagnostic_wall_seconds=1200,calls={'serial':3580},
        expected_oracle_status='paused_checkpoint',oracle_raw=str(ORACLE),oracle_design=str(old.DESIGN),production_authorized=False,
        criterion='Exactly 3580 original rows and complete original checkpoint state; original numerical audit and all raw/history seals. No production or full-stack qualification from this probe.')
    d['binding']=api.digest(d);job.commit(DESIGN,d);verify(d);print('COMBINED_FINE_PROTOCOL',api.sha(DESIGN),flush=True)

def run():
    d=api.read(DESIGN);verify(d);work=api.read(WORK);api.require(job.utc()<job.policy.utc(work['last_diagnostic_launch_utc']),'last diagnostic launch cutoff')
    for x in psutil.process_iter(['name','cmdline']):
        if x.pid!=os.getpid() and 'python' in (x.info['name'] or '').lower():api.require('matdem_microplastic' not in ' '.join(x.info['cmdline'] or []).lower(),'one owned worker')
    api.require(shutil.disk_usage(RUN.anchor).free>work['minimum_disk_reserve_bytes']+4*storage.base.MAX_COMPRESSED,'disk reserve')
    info=old.pre.wrapper.affinity.bind(14);RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    stop=min(job.utc()+timedelta(seconds=d['diagnostic_wall_seconds']),job.policy.utc(work['work_end_utc']))
    job.commit(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':job.utc().isoformat(),'stop_utc':stop.isoformat(),'reserved_steps':3580,'prior_recovery_steps':53086,'design_sha256':api.sha(DESIGN),'affinity':info})
    path=RUN/'serial.json.xz'
    try:
        oracle=q.independent_file(ORACLE,api.sha(old.DESIGN));case,initial=old.seed(d);job.commit(RUN/'initial.json',initial)
        import numpy as np
        candidate.batch.equation_arrays(np.zeros((1,9)),0,.3)
        s=oracle['contact_trial_trace']['detailed_trials'][0]['inner_systems'][0];args=(*[np.asarray(s[k]) for k in ('vfree','mobility','jacobian','gaps_m')],s['dt_s'],s['friction']);f,*_=candidate.compiled.optimized_system(*args);f(np.zeros(3*len(s['gaps_m'])))
        storage.raw_bytes({'warm':[0.,-0.]});job.parent.b.old.parent.configure()
        with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
            geo=old.pre.prior.geometry();job.commit(path.with_suffix('.launch.json'),{'reserved_steps':3580,'input_checkpoint_sha256':api.digest(initial),'utc':job.utc().isoformat()})
            with candidate.scope('compiled_direct'),old.pre.wrapper.baseline.repair.scope(job.parent.engine.runtime,True,stop.timestamp()):
                rec,state,_,tx=execute(d,case,copy.deepcopy(initial),path,3580,None,stop.isoformat())
            n=len(rec['rows']);job.commit(path.with_suffix('.accounting.json'),{'accepted_steps':n,'cumulative_recovery_steps':53086+n,'raw_sha256':api.sha(path)})
            tick=time.perf_counter();ind=q.independent_file(path,api.sha(DESIGN));read_s=time.perf_counter()-tick
            api.require(storage.base.raw_bytes(ind)==storage.base.raw_bytes(rec),'independent full canonical reconstruction')
            check=job.kernel.evaluate(ind,case['spec'],job.binding(d,case),initial,geo,api.sha(DESIGN),d['minimum_gap_semantics']);job.commit(path.with_suffix('.audit.json'),check)
        api.require(n==3580 and rec['result']['status']=='paused_checkpoint' and check['passed'] and not rec['result']['rejected'],'original numerical gates and full requested prefix')
        api.require(storage.base.raw_bytes(rec['rows'])==storage.base.raw_bytes(oracle['rows']) and storage.base.raw_bytes(rec['result']['checkpoint']['state'])==storage.base.raw_bytes(oracle['result']['checkpoint']['state']),'every original row and complete state exactly preserved')
        span=check['stop_s']-check['start_s'];factor=case['spec']['horizon_s']*work['runtime_and_storage_margin']/span/3600
        available=(job.policy.utc(work['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600
        result={'passed':True,'new_accepted_steps':n,'cumulative_recovery_steps':53086+n,'remaining_recovery_steps':100000-53086-n,'exact_full_known_fine_rows_and_state':True,'compute_seconds':rec['compute_call_wall_s'],'transaction_seconds':tx,'independent_read_seconds':read_s,'audit_seconds':check['audit_seconds'],'simulated_seconds':span,'audit':check,
            'fine_compute_hours_with_margin':rec['compute_call_wall_s']*factor,'fine_transaction_hours_with_margin':tx*factor,'available_simulation_hours':available,'local_fine_runtime_scenario_passed':tx*factor<=available,'full_stack_qualified':False,'production_authorized':False,'complete_observations':0,
            'claim':'Local exact implementation and lossless evidence verification only. Runtime values are conservative measured-regime scenarios, not hard lower bounds or full six-case predictions.',
            'protocol_sha256':api.sha(DESIGN),'artifacts':{str(x):api.sha(x) for x in RUN.rglob('*') if x.is_file()}}
        verify(d);job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('COMBINED_FINE_PASS',n,'compute',rec['compute_call_wall_s'],'transaction',tx,'hours',tx*factor,'available',available,flush=True)
    except Exception as e:
        account=path.with_suffix('.accounting.json');known=api.read(account)['accepted_steps'] if account.exists() else None
        job.commit(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'known_new_accepted_steps':known,'accepted_step_accounting_unresolved':known is None and path.with_suffix('.launch.json').exists()});raise

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
