"""One immutable 10,000-step compiled-arithmetic diagnostic, no production."""
from pathlib import Path
from types import FunctionType
from datetime import timedelta
import copy, importlib.util, os, psutil, shutil, sys, time, traceback
import performance_stack_preflight_v1 as inherited
import compiled_analytic_pair_v2 as candidate
ROOT=inherited.ROOT;api=inherited.api;q=inherited.q
PROTOCOL=ROOT/'stage196_designs/deadline_recovery_20260925/compiled_contact_01.json'
RUN=Path('D:/MATDEM_MICROPLASTIC/stage196_runs/deadline_recovery_20260925/compiled_contact_01')
OUT=ROOT/'stage196_evaluations/deadline_recovery_20260925/compiled_contact_01'
QUAL=OUT.parent/'compiled_pair_02/results.json'
HARNESS=ROOT/'stage196_designs/eight_hour_deadline_recovery_20260925/compiled_pair_02_harness.json'
OLD=OUT.parent/'long_transactions_01/results.json'
spec=importlib.util.spec_from_file_location('_stage196_compiled_diagnostic_lifecycle',q.campaign.qualified.instance.historical.__file__)
job=importlib.util.module_from_spec(spec);sys.modules[spec.name]=job;spec.loader.exec_module(job)
job.DESIGN=PROTOCOL;job.ROOT=Path('D:/MATDEM_MICROPLASTIC')
job.codec=inherited.job.codec;job.kernel=inherited.job.kernel;job.observer=inherited.job.observer
raw_execute=FunctionType(inherited.raw_execute.__code__,dict(job.__dict__),'execute_segment',inherited.raw_execute.__defaults__,inherited.raw_execute.__closure__)


def verify(d):
    prior=api.read(inherited.job.DESIGN);inherited.verify(prior)
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'new diagnostic self binding')
    api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    api.require(d['cases']==prior['cases'] and d['numerical_gates']==prior['numerical_gates'] and d['budget']==prior['budget'],'all original physics, timestep, gates and ceiling')
    api.require(d['diagnostic_steps']==10000 and d['window_prior_steps']==30241 and not d['production_authorized'],'bounded diagnostic only')
    api.require(raw_execute.__code__ is inherited.raw_execute.__code__,'unchanged integration code')
    for k in ('parent','fast','prior','deadline','capture','observer','codec'):
        api.require(raw_execute.__globals__[k] is inherited.raw_execute.__globals__[k],'unchanged dependency '+k)
    api.require(raw_execute.__globals__['DESIGN']==PROTOCOL,'new record lineage path')


def prepare():
    d=copy.deepcopy(api.read(inherited.job.DESIGN));inherited.verify(d);d.pop('binding')
    r=api.read(QUAL);old=api.read(OLD);h=api.read(HARNESS)
    api.require(r['passed'] and r['pointwise_checks']==3696 and len(r['held_comparisons'])==462,'exact compiled prerequisite')
    api.require(api.read(QUAL.parent/'completion.json')['results_sha256']==api.sha(QUAL),'qualification seal')
    api.verify_mapping(r['inputs']);api.verify_mapping(h['existing_dependency_files'])
    api.require(old['window_new_accepted_steps']==30241 and not old['passed'],'preserved failed original cap')
    oldraw=Path(old['measurements'][0]['path'])
    inputs=[inherited.job.DESIGN,QUAL,QUAL.parent/'completion.json',HARNESS,OLD,oldraw,oldraw.with_suffix('.seal.json')]
    d.update(stage='Stage196 compiled arithmetic local diagnostic',window_prior_steps=30241,diagnostic_steps=10000,
        maximum_window_steps=40241,production_authorized=False,preflight={},
        sources={**d['sources'],str(Path(__file__).resolve()):api.sha(__file__),str(Path(candidate.__file__).resolve()):api.sha(candidate.__file__)},
        inputs={**d['inputs'],**{str(x):api.sha(x) for x in inputs},**h['existing_dependency_files']},
        earlier_incomplete_probe=str(oldraw),prior_stage196_steps=30241,
        claim='One bounded local repaired-contact cost/identity test; not full-stack readiness or a complete observation.')
    d['binding']=api.digest(d);job.commit(PROTOCOL,d);verify(d);print('COMPILED_DIAGNOSTIC_FROZEN',api.sha(PROTOCOL),flush=True)


def run():
    d=api.read(PROTOCOL);verify(d);w=api.read(inherited.WORK)
    api.require(job.utc()<job.policy.utc(w['last_diagnostic_launch_utc'])-timedelta(minutes=10),'launch clock')
    api.require(d['maximum_window_steps']<=w['maximum_new_qualification_accepted_steps'],'window step reserve')
    for proc in psutil.process_iter(['pid','name','cmdline']):
        if proc.pid!=os.getpid() and 'python' in (proc.info['name'] or '').lower():
            api.require('matdem_microplastic' not in ' '.join(proc.info['cmdline'] or []).lower(),'one diagnostic worker')
    affinity=inherited.affinity.bind(14)
    api.require(shutil.disk_usage(RUN.parent).free>w['minimum_free_disk_bytes']+4*job.codec.base.MAX_COMPRESSED,'D reserve')
    RUN.mkdir(parents=True,exist_ok=False);OUT.mkdir(parents=True,exist_ok=False)
    stop=min(job.utc()+timedelta(minutes=10),job.policy.utc(w['last_diagnostic_launch_utc']))
    job.commit(RUN/'launch.json',{'pid':os.getpid(),'argv':sys.argv,'utc':job.utc().isoformat(),'stop_utc':stop.isoformat(),
        'design_sha256':api.sha(PROTOCOL),'reserved_steps':10000,'window_prior_steps':30241,'owned_affinity':affinity})
    try:
        case=next(c for c in d['cases'] if c['id']==d['stress_case'])
        seed=q.independent_file(Path(d['stress_seed_raw']),api.sha(d['stress_seed_design']))
        cp=job.parent.model.checkpoint(case['spec'],job.binding(d,case),seed['result']['checkpoint'],True)
        api.require(cp['state']==seed['result']['checkpoint']['state'],'unchanged diagnostic initial state')
        job.parent.b.old.parent.configure()
        # Compile with the exact same data types before timing any trajectory.
        # This zero-step evaluation does not call the contact optimizer.
        fixture=api.read(ROOT/'stage194_evaluations/evidence_repair_20260924/early_semismooth_qualification_01/fixtures.json')[0]
        system=fixture['fixture']['contact_trial_trace']['detailed_trials'][0]['inner_systems'][0]
        import numpy as np
        args=(*[np.asarray(system[k]) for k in ('vfree','mobility','jacobian','gaps_m')],system['dt_s'],system['friction'])
        both,*_=candidate.optimized_system(*args);both(np.zeros(len(system['gaps_m'])*3))
        path=RUN/'record.json.xz'
        with job.prior.snapshot.scope(api,case['spec']['field_metadata']),candidate.scope(True),inherited.baseline.repair.scope(job.parent.engine.runtime,True,stop.timestamp()):
            rec,state,_,tx=raw_execute(d,case,copy.deepcopy(cp),path,10000,None,stop.isoformat())
        count=len(rec['rows']);job.commit(RUN/'accounting.json',{'accepted_steps':count,'rejected':rec['result']['rejected'],'raw_sha256':api.sha(path)})
        decoded,_=job.codec.read_record(path,api.sha(PROTOCOL));independent=q.independent_file(path,api.sha(PROTOCOL))
        api.require(job.codec.base.raw_bytes(rec)==job.codec.base.raw_bytes(decoded)==job.codec.base.raw_bytes(independent),'independent lossless identity')
        with job.prior.snapshot.scope(api,case['spec']['field_metadata']):
            import qualify_repaired_stack_v1 as original_pre
            summary=job.kernel.evaluate(independent,case['spec'],job.binding(d,case),cp,original_pre.geometry(),api.sha(PROTOCOL),d['minimum_gap_semantics'])
        oldraw=Path(d['earlier_incomplete_probe']);oracle=q.independent_file(oldraw,api.sha(inherited.job.DESIGN));overlap=min(count,len(oracle['rows']))
        exact=rec['rows'][:overlap]==oracle['rows'][:overlap]
        api.require(exact and summary['passed'],'exact full known path and unchanged numerical gates')
        passed=count==10000 and rec['result']['status']=='paused_checkpoint'
        r={'passed':passed,'new_accepted_steps':count,'window_prior_steps':30241,'window_new_accepted_steps':30241+count,
           'status':rec['result']['status'],'exact_previous_rows':overlap,'compute_seconds':rec['compute_call_wall_s'],'transaction_seconds':tx,
           'simulated_seconds':summary['stop_s']-summary['start_s'],'audit':summary,'complete_observation':False,'production_authorized':False,
           'protocol_sha256':api.sha(PROTOCOL),'artifacts':{str(x):api.sha(x) for x in RUN.rglob('*') if x.is_file()}}
        verify(d);job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'passed':passed,'results_sha256':api.sha(OUT/'results.json')})
        print('COMPILED_DIAGNOSTIC',passed,count,rec['result']['status'],'compute',rec['compute_call_wall_s'],'tx',tx,flush=True)
    except Exception as e:
        account=api.read(RUN/'accounting.json') if (RUN/'accounting.json').exists() else None
        job.commit(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'accounting':account,'unresolved':account is None});raise


if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
