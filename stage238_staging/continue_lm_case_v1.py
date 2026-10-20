"""Maintained single-case continuation; original transactions and physical gates.

The candidate changes only the LM callback inside the actual original observer
scope. Original bytecode, operands, checkpoint contract and archive reader remain
unchanged. The faster history reader is used only after worker retirement.
Configuration and authority are frozen by the admitting parent, not this module.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from types import FunctionType, ModuleType, SimpleNamespace
from contextlib import contextmanager
import copy, os, shutil, subprocess, sys, time, traceback
import numpy as np
import psutil

ROOT=Path(__file__).resolve().parents[1];SELF=Path(__file__).resolve()
PLAN=Path(os.environ.get('DEM_CASE_PLAN',str(ROOT/'stage238_designs/fibre_lm_20261009/design_01.json'))).resolve()
AUTH=PLAN.with_name('authorization_01.json')
RUN=ROOT/'stage238_runs'/PLAN.parent.name/'run_01'
OUT=ROOT/'stage238_evaluations'/PLAN.parent.name
sys.path[:0]=[str(ROOT/'stage231_staging'),str(ROOT/'stage236_staging')]
saved_plan=os.environ.pop('DEM_CASE_PLAN',None)
import single_case_v3 as source
if saved_plan is not None:os.environ['DEM_CASE_PLAN']=saved_plan
import verified_history_reader_v2 as reader
import lm_residual_kernel_v1 as kernel
old=source.old;api,job,baseline=source.api,source.job,source.baseline
controller=old.controller
NAME='s2_i124_fibre_f0p125'

def clone(fn,namespace):
    return FunctionType(fn.__code__,namespace,fn.__name__,fn.__defaults__,fn.__closure__)

def merge_frozen(*mappings):
    result={}
    for mapping in mappings:
        for path,expected in mapping.items():
            api.require(path not in result or result[path]==expected,'Conflicting frozen file binding: '+path)
            result[path]=expected
    return result

def context(run):
    result=ModuleType('_bounded_lm_tail_context');result.__dict__.update(vars(old.c))
    result.ROOT=ROOT;result.RUN=run;result.OUT=OUT;result.PLAN=PLAN;result.AUTH=AUTH;result.DESIGNS=PLAN.parent
    for key,fn in vars(old.c).items():
        if isinstance(fn,FunctionType) and fn.__globals__ is vars(old.c):setattr(result,key,clone(fn,vars(result)))
    return result

c=context(RUN)
FINAL_PROGRESS=None
RAW=baseline.execute.__globals__['frozen'].raw_execute
ORIGINAL_OBSERVER=RAW.__globals__['observer']

@contextmanager
def observed_scope(original_scope,candidate_scope,runtime,enabled):
    with original_scope(runtime,enabled) as trace:
        with candidate_scope():yield trace

@contextmanager
def candidate_observation(runtime,enabled):
    api.require(runtime is job.parent.engine.runtime and enabled is True,'Exact original observed runtime')
    with observed_scope(ORIGINAL_OBSERVER.scope,kernel.scope,runtime,enabled) as trace:yield trace

# The Stage214 adapter constructs its raw function from job.__dict__ and checks
# dependencies against frozen.raw_execute. Both private views must agree. No
# original module, code object, physical dependency or reader is modified.
candidate_observer=SimpleNamespace(**{**vars(ORIGINAL_OBSERVER),'scope':candidate_observation})
candidate_job=ModuleType('_private_lm_tail_numerical_namespace');candidate_job.__dict__.update(vars(job))
candidate_job.observer=candidate_observer
candidate_raw=clone(RAW,{**RAW.__globals__,'observer':candidate_observer})
candidate_frozen=SimpleNamespace(**{**vars(baseline.execute.__globals__['frozen']),'raw_execute':candidate_raw})
candidate_execute=clone(baseline.execute,{**baseline.execute.__globals__,'job':candidate_job,'frozen':candidate_frozen})
candidate_baseline=SimpleNamespace(**{**vars(baseline),'execute':candidate_execute})

def transactions(run,candidate=False):
    private=dict(vars(old.prior),c=context(run),PLAN=PLAN,RUN=run,OUT=OUT,AUTH=AUTH,
                 baseline=candidate_baseline if candidate else baseline)
    for key in old.NAMES:private[key]=clone(getattr(old.prior,key),private)
    return private

PRIVATE=transactions(RUN,True)
DIAGNOSTIC={mode:transactions(RUN/('diagnostic_'+mode),mode=='candidate') for mode in ('original','candidate')}


KERNEL_SHA='535b75aa3975c5fee1a4b056c6c2bed5d0283e29093005867e27d095f42c0ccf'
READER_SHA='3440cc0c282912ebf8a870adb5831db8b5f70f3f785b06d747a72bc84c1df3ec'
DEFAULT_CONFIG=dict(
    seed_plan=str(ROOT/'stage237_designs/lm_tail_20261009/design_02.json'),
    seed_plan_sha256='5a709731286c229ec1f3804336ea92fddb4806adba8e4efb6d3fd13a4185190b',
    seed_run=str(ROOT/'stage237_runs/lm_tail_20261009/run_02'),
    seed_closure=str(ROOT/'stage237_evaluations/lm_tail_20261009/repair_02/final_disposition_01/results.json'),
    seed_closure_sha256='bfb4481cbd2ed372eb22c40eaba9288fa655871563d30a12c50d210845cffb7f',
    seed_retirement=str(ROOT/'stage237_evaluations/lm_tail_20261009/repair_02/retirement_01/results.json'),
    seed_retirement_sha256='fe9684388f778a331e91c370b03383bac25d35d36cf63fa11186b9b46dc5ac3b',
    checkpoint_sha256='2c0e85909826de6070f97e08f6ef8b7811291e7c658efbf3bd95e7f9889c6562',
    inherited_physical_steps=1070342,inherited_production_calls=121,inherited_time_s=1.331019636673643,
    prior_saved_steps=1072902,maximum_new_physical_steps=600000,maximum_new_production_calls=80,
    wall_window_seconds=7200,numerical_retirement_reserve_seconds=1200,
    maximum_new_output_bytes=2*1024**3)

def original_case():
    d=PRIVATE['physical_design']();case=next(x for x in d['cases'] if x['id']==NAME)
    api.require(case['factor']==.125 and case['sample_id']==124 and case['shape']=='rigid_prolate_ar4'
        and case['spec']['sample_id']==0 and case['reference_case']=='s2_i124_fibre_f0p0625','Exact original labelled fibre metadata')
    source.matched_physics(d,case);baseline.clone_check()
    return d,case

def clone_checks():
    for private in [PRIVATE,*DIAGNOSTIC.values()]:
        for key in old.NAMES:api.require(private[key].__code__ is getattr(old.prior,key).__code__,'Exact original transaction '+key)
    api.require(candidate_execute.__code__ is baseline.execute.__code__ and candidate_raw.__code__ is RAW.__code__,
        'Exact original integration and operand adapter code')
    api.require({k for k in candidate_execute.__globals__ if candidate_execute.__globals__[k] is not baseline.execute.__globals__[k]}=={'job','frozen'},
        'Only private job/observer identity views differ in original adapter')
    api.require({k for k in candidate_raw.__globals__ if candidate_raw.__globals__[k] is not RAW.__globals__[k]}=={'observer'},
        'Only private observation scope differs in raw integration namespace')
    api.require(all(candidate_job.__dict__[k] is v for k,v in vars(job).items() if k!='observer')
        and candidate_job.codec is job.codec and RAW.__globals__['observer'] is ORIGINAL_OBSERVER
        and job.observer is ORIGINAL_OBSERVER,'Original physical objects and transport reader untouched')
    return dict(passed=True,original_transaction_code_objects=list(old.NAMES),
        integration_code_unchanged=True,scope_after_original_hot_scope=True,transport_reader_unchanged=True,numerical_calls=0)

def budget_checks(p):
    def integer(key,lo,hi):api.require(type(p[key]) is int and lo<=p[key]<=hi,'Bounded integer '+key)
    integer('maximum_new_physical_steps',1,600000);integer('maximum_new_production_calls',1,80)
    api.require(p['maximum_saved_steps_including_diagnostics']==p['maximum_new_physical_steps']+1024
        and p['qualification_steps_per_case']==1024 and p['step_cap_per_call']==10000
        and p['maximum_cumulative_physical_steps_per_case']==5000000 and p['maximum_cumulative_calls_per_case']==1500,
        'Fresh discarded diagnostics and unchanged cumulative ceilings')
    start,end,cut=[datetime.fromisoformat(p[k]) for k in ('start_utc','end_utc','simulation_cutoff_utc')]
    api.require(all(x.utcoffset() is not None for x in (start,end,cut)) and 1200<(end-start).total_seconds()<=7200
        and cut==end-timedelta(seconds=1200) and start<cut,'One fresh bounded window and20minute retirement reserve')
    api.require(p['workers']==p['threads']==p['maximum_unverified_records']==1 and p['logical_cpu']==14
        and p['minimum_free_disk_bytes']>=20*1024**3 and p['finalizer_retirement_reserve_seconds']>=30,
        'One qualified worker/thread and original exact-identity retirement')
    integer('maximum_new_output_bytes',4*job.codec.base.MAX_COMPRESSED+1,2*1024**3)
    api.require(p['only_case']==NAME and p['candidate_production_authorized'] and not p['successor_dispatch_authorized']
        and not p['automatic_continuation_authorized'] and p['physical_changes']==p['numerical_changes']==p['accuracy_gate_changes']==[],
        'One unchanged physical case; no automatic repeated continuation or successor')
    return True

def gate_checks(r):
    api.require(r['passed'] and r['scientific_passed'] and r['performance_passed']
        and r['original_independent_physical_audits_passed'] and r['exact_pairs_including_residuals']
        and r['synthetic_controls_passed'] and r['unknown_outer_calls']==0
        and r['attempted_outer_calls']==r['completed_outer_calls']
        and r['new_trajectory_steps']==r['new_saved_transport_steps']==0
        and len(r['costs'])==3 and all(x['performance_passed'] for x in r['costs']),
        'Passing fixed-pose scientific/evidence/physical and fixture-specific complete-cost prerequisite')
    api.require(sum(x['stratum']=='recorded_fallback' for x in r['costs'])==2
        and sum(x['stratum']=='healthy_early_success' for x in r['costs'])==1,'Both difficult strata and original healthy cost control')
    for cost in r['costs']:
        limit=.95 if cost['stratum']=='recorded_fallback' else 1.05
        api.require(all(cost[key]['ratio']<=limit for key in ('seconds','scoped_transaction_seconds')),
            'No favorable aggregate or stale passing flag overrides fixture-specific cost gate')
    return True

def retirement_checks(r):
    api.require(r['passed'],'Passing prerequisite retirement')
    mappings={}
    for key in ('artifacts','closure_artifacts','closed_logs'):mappings=merge_frozen(mappings,r.get(key,{}))
    api.require(mappings,'Retirement binds closed evidence')
    c.verify(mappings)
    if 'all_exact_launch_identities_retired' in r:
        api.require(r['all_exact_launch_identities_retired'] and r.get('launches'),'Original Stage233 retirement schema')
        launches=list(r['launches'].values()) if isinstance(r['launches'],dict) else r['launches']
    else:
        api.require(r.get('exact_launch_identities_retired') is True and r.get('identities'),'Stage236 retirement schema')
        launches=[]
        for identity in r['identities']:
            path=identity['launch_path'];api.require(c.sha(path)==identity['launch_sha256'],'Sealed actual candidate screen launch')
            launches.append(c.read(path))
    for record in launches:
        command=record.get('argv',record.get('command'))
        api.require(command and controller.inspect(record['pid'],record['created'],command)['retired'],
            'Fresh exact prerequisite birth/command retirement')
    return True

def plain_authenticate(mapping):
    for path,expected in mapping.items():api.require(c.sha(path)==expected,'Mandatory immutable source/input: '+path)


def prior_saved_work(prior,closed,retired,expected):
    total=prior['prior_saved_steps']+retired['shared_saved_steps_including_diagnostics']
    api.require(expected==total and retired['shared_saved_steps_including_diagnostics']==closed['accepted_physical_steps']
        +closed['discarded_diagnostic_steps']+retired['prior_attempt_discarded_diagnostic_steps'],
        'Prior saved work derives from the sealed inherited ledger and both closed attempts including failed diagnostics')
    return total


def seed_inventory(config):
    paths=[Path(config[k]).resolve() for k in ('seed_plan','seed_closure','seed_retirement')]
    plan_path,closed_path,retired_path=paths
    for path,key in zip(paths,('seed_plan_sha256','seed_closure_sha256','seed_retirement_sha256')):
        api.require(c.sha(path)==config[key],'Exact selected closed prerequisite: '+str(path))
    parent_plan=c.read(plan_path);closed=c.sealed(closed_path);retired=c.sealed(retired_path)
    api.require(parent_plan['binding']==c.digest({k:v for k,v in parent_plan.items() if k!='binding'})
        and closed['passed'] and closed['accounting_authenticated'] and closed['qualification_passed']
        and closed['exact_original_candidate_serial_passed'] and closed['known_unaccepted_saved_steps']==closed['unknown_saved_steps_reservation_upper_bound']==0
        and not closed['scientific_full_path_passed'] and retired['passed'] and retired['all_exact_launch_identities_retired']
        and retired['short_numerical_transfer_passed'] and retired['final_disposition_sha256']==c.sha(closed_path),
        'Closed short transfer, no unresolved work and no inferred complete-path accuracy')
    api.require(retired['excluded_timing_fields']==list(TIMING_FIELDS) and retired['excluded_timing_paths']==TIMING_PATHS
        and closed['excluded_timing_paths']==TIMING_PATHS and retired['wall_timer_proof']==closed['wall_timer_proof'],
        'Exactly declared scientific comparison exclusions retained')
    run=Path(config['seed_run']).resolve();case_result=c.sealed(run/NAME/'results.json')
    entries=case_result['entries'];prior=parent_plan['inherited']
    api.require([x['segment'] for x in entries]==list(range(1,len(entries)+1))
        and len(entries)==closed['new_production_segments'] and sum(x['new_saved_steps'] for x in entries)==closed['accepted_physical_steps'],
        'Every sealed sequential current production segment')
    traces=[*prior['trace_paths'],*[str(run/NAME/f"segment_{e['segment']:05d}"/'trace.npy') for e in entries]]
    api.require(len(traces)==len(set(traces))==config['inherited_production_calls']==closed['cumulative_production_calls']
        and prior['inherited_physical_steps']+closed['accepted_physical_steps']==config['inherited_physical_steps']==closed['cumulative_physical_steps'],
        'All inherited production traces in order; diagnostics excluded')
    prior_saved_work(prior,closed,retired,config['prior_saved_steps'])
    cpfile=closed_path.parent/'recoverable/checkpoint.json';prefixfile=closed_path.parent/'recoverable/prefix.json'
    cp=c.read(cpfile);prefix=c.read(prefixfile)
    api.require(api.digest(cp)==config['checkpoint_sha256']==closed['final_checkpoint_sha256']==retired['final_checkpoint_sha256']
        and cp['state']['steps']==config['inherited_physical_steps'] and cp['state']['t']==config['inherited_time_s']==closed['time_s']
        and c.sha(cpfile)==retired['final_checkpoint_file_sha256'],'Exact FULL late seed and physical clock')
    inputs=merge_frozen(parent_plan['inputs'],closed['artifacts'],retired['artifacts'],retired['closed_logs'])
    for path in (*paths,plan_path.with_name('authorization_01.json'),closed_path.parent/'completion.json',
                 retired_path.parent/'completion.json',cpfile,prefixfile,run/NAME/'results.json',run/NAME/'completion.json'):
        inputs=merge_frozen(inputs,{str(path):c.sha(path)})
    for path in traces:api.require(path in inputs,'Every production-only trace has an inherited original hash')
    plain_authenticate(parent_plan['source_files']);plain_authenticate(inputs)
    for launch in retired['launches'].values():
        api.require(controller.inspect(launch['pid'],launch['created'],launch.get('argv',launch.get('command')))['retired'],
            'Fresh exact prerequisite birth AND full-command retirement')
    previous=c.sha(run/NAME/f"segment_{entries[-1]['segment']:05d}"/'results.json')
    inherited=dict(checkpoint_file=str(cpfile),checkpoint_sha256=api.digest(cp),prefix=prefix,
        inherited_segments=config['inherited_production_calls'],inherited_physical_steps=config['inherited_physical_steps'],
        inherited_time_s=config['inherited_time_s'],prior_saved_steps=config['prior_saved_steps'],
        last_receipt_sha256=previous,trace_paths=traces,closure_file=str(closed_path),retirement_file=str(retired_path),
        seed_plan_file=str(plan_path),seed_plan_sha256=c.sha(plan_path),closure_sha256=c.sha(closed_path),
        retirement_sha256=c.sha(retired_path),inputs=inputs)
    return parent_plan,inherited,closed


def seed_state(p):
    s=p['inherited'];cp=c.read(s['checkpoint_file'])
    api.require(len(s['trace_paths'])==len(set(s['trace_paths']))==s['inherited_segments']
        and cp['state']['steps']==s['inherited_physical_steps'] and cp['state']['t']==s['inherited_time_s']
        and api.digest(cp)==s['checkpoint_sha256'] and api.digest(cp['state'])==cp['state_sha256']
        and cp['contract']==p['checkpoint_contract'],'Frozen FULL seed, clock and all inherited production ancestry')
    prefix=job.codec.HistoryState(**s['prefix'],history_bytes=job.codec.packed_history(cp['state']['history']))
    api.require(job.codec.digest(prefix.history_bytes)==prefix.history_sha256 and prefix.design_sha256==p['physical_design_sha256'],
        'Exact FULL history and original physical design binding')
    return cp,prefix,s['last_receipt_sha256']


def wall_timer_proof():
    import ast
    path=ROOT/'stage119_staging/checkpoint_core_v3.py';tree=ast.parse(path.read_text(encoding='utf-8'))
    integrate=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='integrate')
    started=[n for n in integrate.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='started' for t in n.targets)]
    finish=next(x for x in integrate.body if isinstance(x,ast.FunctionDef) and x.name=='finish')
    returns=[x for x in finish.body if isinstance(x,ast.Return) and isinstance(x.value,ast.Dict)]
    fields={k.value:v for k,v in zip(returns[0].value.keys,returns[0].value.values) if isinstance(k,ast.Constant)}
    api.require(len(started)==len(returns)==1 and ast.unparse(started[0].value)=='time.perf_counter()'
        and ast.unparse(fields['runtime_seconds'])=='time.perf_counter() - started' and ast.unparse(fields['time_s'])=='t',
        'Additional exact result.runtime_seconds exclusion is only the original wall timer')
    return dict(passed=True,source=str(path),source_sha256=c.sha(path),start_line=started[0].lineno,
        finish_wall_timer_line=fields['runtime_seconds'].lineno,exact_additional_exclusion_path=['result','runtime_seconds'],
        physical_clock_and_FULL_checkpoint_unchanged=True)


def prepare(config=None,start_utc=None):
    """Create-only fresh admission; parent chooses clock. No numerical calls."""
    c.environment();clone_checks();pure=controls()
    api.require(not AUTH.exists() and not PLAN.exists() and not RUN.exists() and not OUT.exists(),'Fresh create-only numerical stage')
    api.require(PLAN.parent.parent==ROOT/'stage238_designs','Current Stage238 design stays in its workspace family')
    cfg={**DEFAULT_CONFIG,**(config or {})};api.require(set(cfg)==set(DEFAULT_CONFIG),'Explicit maintained configuration schema')
    parent_plan,inherited,closed=seed_inventory(cfg);d,case=original_case();binding=job.binding(d,case)
    api.require(inherited['inherited_physical_steps']<5000000 and inherited['inherited_segments']<1500,'Original cumulative capacity remains')
    sources=merge_frozen(parent_plan['source_files'],{str(SELF):c.sha(SELF)})
    api.require(sources[str(Path(kernel.__file__).resolve())]==c.sha(kernel.__file__)==KERNEL_SHA
        and sources[str(Path(reader.__file__).resolve())]==c.sha(reader.__file__)==READER_SHA,'Exact qualified kernel and offline reader unchanged')
    inputs=inherited['inputs'];plain_authenticate(sources);plain_authenticate(inputs)
    start=datetime.now(timezone.utc) if start_utc is None else datetime.fromisoformat(start_utc)
    api.require(start.utcoffset() is not None and abs(start.timestamp()-time.time())<=60,'Fresh parent-selected aware admission time')
    end=start+timedelta(seconds=cfg['wall_window_seconds']);cut=end-timedelta(seconds=cfg['numerical_retirement_reserve_seconds'])
    authority=dict(stage='Stage238 maintained difficult-fibre LM continuation',
        human_authorization='Human next on9October after verified closed Stage237 authorizes continuing this same original case; the agent selects a conservative bound of at most2hours for this fresh stage, not a new12hour campaign.',
        start_utc=start.isoformat(),end_utc=end.isoformat(),simulation_cutoff_utc=cut.isoformat(),only_case=NAME,
        maximum_new_physical_steps=cfg['maximum_new_physical_steps'],maximum_saved_steps_including_diagnostics=cfg['maximum_new_physical_steps']+1024,
        maximum_new_production_calls=cfg['maximum_new_production_calls'],maximum_cumulative_physical_steps_per_case=5000000,
        maximum_cumulative_calls_per_case=1500,step_cap_per_call=10000,qualification_steps_per_case=1024,
        workers=1,threads=1,logical_cpu=14,maximum_unverified_records=1,minimum_free_disk_bytes=20*1024**3,
        maximum_new_output_bytes=cfg['maximum_new_output_bytes'],finalizer_retirement_reserve_seconds=30,
        successor_dispatch_authorized=False,candidate_production_authorized=True,automatic_continuation_authorized=False,
        old_windows_remain_closed=True,physical_changes=[],numerical_changes=[],accuracy_gate_changes=[],source_files=sources,inputs=inputs,
        configuration=cfg,master_plan_sha256_at_authorization=c.sha(ROOT/'MASTER_PLAN.md'),
        claim='Bounded local original-equation numerical continuation at one labelled placement and one packing/flow. Only complete original start-to-terminal accuracy/event gates support full-path acceptance; no population shape/flow or physical-validation claim.',
        retention='Retain every diagnostic/production raw chain, failure, FULL checkpoint/history and original independent audit under2GiB new output including512MiB record reserve and20GiB disk reserve.')
    budget_checks(authority);c.commit(AUTH,authority)
    try:
        c.verify(sources);c.verify(inputs)
        contract=job.parent.engine.prior.contracts.expected_contract(case['spec'],job.parent.model.binding_for(binding,True))
        p={**authority,'authorization_sha256':c.sha(AUTH),'authorized_end_utc':authority['end_utc'],
            'physical_design_sha256':c.sha(job.DESIGN),'numerical_policy_contract_sha256':c.sha(job.WORK),
            'physical_inputs':parent_plan['physical_inputs'],'original_binding':binding,'checkpoint_contract':contract,
            'matched_physics':source.matched_physics(d,case),'reference_case':case['reference_case'],'inherited':inherited,
            'candidate_gate':parent_plan['candidate_gate'],'candidate_screen_design':parent_plan['candidate_screen_design'],
            'candidate_retirement':parent_plan['candidate_retirement'],'wall_timer_proof':wall_timer_proof(),'controls':pure,
            'scientific_timing_exclusions':dict(recursive_fields=list(TIMING_FIELDS),exact_paths=TIMING_PATHS),
            'production_admission':'Fresh original/candidate256vs128+128 FULL restart and cross-complete-science equality; all1024diagnostics discarded; sealed production seed restored.',
            'implementation_changes':['Qualified immutable Stage236 two-contact LM callback entered only inside original observation scope; original transactions/force/accuracy gates unchanged.']}
        seed_state(p);p['binding']=c.digest(p);c.commit(PLAN,p)
        receipt=dict(passed=True,design_sha256=c.sha(PLAN),authorization_sha256=c.sha(AUTH),controls=pure,
            inherited_physical_steps=inherited['inherited_physical_steps'],inherited_production_calls=inherited['inherited_segments'],
            original_full_path_reference_and_entire_production_ancestry_retained=True,numerical_calls=0,new_trajectory_steps=0,utc=c.utc())
        c.commit(OUT/'preparation_01/results.json',receipt);c.commit(OUT/'preparation_01/completion.json',dict(passed=True,results_sha256=c.sha(OUT/'preparation_01/results.json')))
        verify();print('LM_CASE_PREPARED',c.sha(PLAN),authority['end_utc'],flush=True);return p
    except Exception as error:
        c.commit(OUT/'preparation_failure_01.json',dict(passed=False,error=repr(error),traceback=traceback.format_exc(),
            no_numerical_calls=True,dependent_dispatch_stopped=True,utc=c.utc()));raise


def verify():
    a=c.bound();c.environment();p=c.read(PLAN);budget_checks(p);clone_checks()
    api.require(p['binding']==c.digest({k:v for k,v in p.items() if k!='binding'}) and p['authorization_sha256']==c.sha(AUTH),'Frozen fresh authority/design')
    for key,value in a.items():api.require(p[key]==value,'Exact fresh authority '+key)
    c.verify(p['source_files']);c.verify(p['inputs']);c.verify(p['inherited']['inputs'])
    api.require(p['source_files'][str(SELF)]==c.sha(SELF) and c.sha(kernel.__file__)==KERNEL_SHA and c.sha(reader.__file__)==READER_SHA,
        'Exact current administrative source and qualified implementations')
    d,case=original_case();api.require(p['original_binding']==job.binding(d,case) and p['physical_design_sha256']==c.sha(job.DESIGN)
        and p['numerical_policy_contract_sha256']==c.sha(job.WORK) and p['matched_physics']==source.matched_physics(d,case)
        and p['reference_case']==case['reference_case'],'Original physical/case/route/gap policy binding')
    seed_state(p);seed=p['inherited'];api.require(c.sha(seed['closure_file'])==seed['closure_sha256']
        and c.sha(seed['retirement_file'])==seed['retirement_sha256'] and c.sha(seed['seed_plan_file'])==seed['seed_plan_sha256'],
        'Immutable closed seed receipts and design')
    retirement_checks(c.sealed(Path(seed['retirement_file'])))
    gate=p['candidate_gate'];api.require(c.sha(gate['path'])==gate['sha256'],'Immutable passing cost/physical gate')
    screened=c.sealed(Path(gate['path']));gate_checks(screened);c.verify(screened['artifacts'])
    screen_design=p['candidate_screen_design'];api.require(c.sha(screen_design['path'])==screen_design['sha256']==screened['design_sha256']
        and c.read(screen_design['path'])['source_files'][str(Path(kernel.__file__).resolve())]==KERNEL_SHA,'Measured exact candidate source')
    candidate_retirement=p['candidate_retirement'];api.require(c.sha(candidate_retirement['path'])==candidate_retirement['sha256'],'Immutable candidate retirement')
    retirement_checks(c.sealed(Path(candidate_retirement['path'])))
    api.require(p['wall_timer_proof']==wall_timer_proof() and p['scientific_timing_exclusions']==dict(recursive_fields=list(TIMING_FIELDS),exact_paths=TIMING_PATHS),
        'Only declared timing exclusions; all physical clocks/scientific fields exact')
    prep=c.sealed(OUT/'preparation_01/results.json');api.require(prep['passed'] and prep['design_sha256']==c.sha(PLAN)
        and prep['authorization_sha256']==c.sha(AUTH),'Sealed fresh preparation before dispatch')
    return p

def output_bytes():
    roots=(RUN,OUT,PLAN.parent,RUN.with_name(RUN.name+'_controller'))
    return sum(q.stat().st_size for q in {q.resolve() for root in roots for q in root.rglob('*') if q.is_file()})

def stop_reason(p,used,needed):
    c.bound()
    if time.time()>=datetime.fromisoformat(p['simulation_cutoff_utc']).timestamp()-120:return 'simulation_cutoff'
    if used+needed>p['maximum_saved_steps_including_diagnostics']:return 'saved_step_ceiling'
    if not output_reserve_fits(output_bytes(),p['maximum_new_output_bytes']):return 'output_cap'
    if shutil.disk_usage(ROOT).free<=p['minimum_free_disk_bytes']+4*job.codec.base.MAX_COMPRESSED:return 'disk_reserve'
    return None

def output_reserve_fits(retained,ceiling):
    return retained+4*job.codec.base.MAX_COMPRESSED<ceiling

def qualification_equal(records,proof,seed_digest,design_digest):
    serial,a,b=[records[k][0] for k in ('serial_01','split_a_01','split_b_01')]
    exact=(len(serial['rows'])==256 and len(a['rows'])==len(b['rows'])==128 and serial['rows']==a['rows']+b['rows']
        and api.digest(serial['result']['checkpoint'])==api.digest(b['result']['checkpoint']))
    sealed=bool(proof and proof.get('passed') is True and proof.get('diagnostic_saved_steps')==512
        and proof.get('production_seed_sha256')==seed_digest and proof.get('transport_design_sha256')==design_digest
        and proof.get('exact_serial_split_rows') is True and proof.get('exact_full_checkpoint') is True
        and proof.get('all_three_independent_physical_audits_passed') is True
        and proof.get('production_seed_unchanged') is True and proof.get('diagnostic_trajectory_promoted') is False)
    return exact and sealed

TIMING_FIELDS=('compute_call_wall_s','wall_s','certificate_seconds')
TIMING_PATHS=[['result','runtime_seconds']]

def scientific_record(value,path=()):
    if isinstance(value,dict):return {k:scientific_record(v,path+(k,)) for k,v in value.items()
        if k not in TIMING_FIELDS and path+(k,)!=('result','runtime_seconds')}
    if isinstance(value,list):return [scientific_record(v,path+(i,)) for i,v in enumerate(value)]
    if isinstance(value,tuple):return tuple(scientific_record(v,path+(i,)) for i,v in enumerate(value))
    return value

def pair_equal(a,b):
    return bool(a['rows']==b['rows'] and api.digest(a['result']['checkpoint'])==api.digest(b['result']['checkpoint'])
        and api.digest(scientific_record(a))==api.digest(scientific_record(b)))

def run():
    p=verify();d,case=original_case();process=psutil.Process();process.cpu_affinity([p['logical_cpu']]);RUN.mkdir(parents=True,exist_ok=False)
    c.commit(RUN/'launch.json',dict(pid=process.pid,created=process.create_time(),argv=process.cmdline(),utc=c.utc(),authorization_sha256=c.sha(AUTH)))
    cp,prefix,previous=seed_state(p);entries=[];used=diag=0;reservation=None;stage='qualification';rec=None
    try:
        geometry=baseline.geometry_for(case);kernel.warm();kernel.reset()
        for mode in ('original','candidate'):
            api.require(stop_reason(p,used,512) is None,'Complete independent restart reservation fits')
            reservation=dict(role='restart_diagnostic',mode=mode,maximum_saved_steps=512)
            n=DIAGNOSTIC[mode]['qualify'](p,d,case,geometry,cp,prefix,previous);used+=n;diag+=n;reservation=None
            print('LM_TAIL_RESTART_VERIFIED',mode,n,flush=True)
        serial={}
        for mode in ('original','candidate'):
            serial[mode],_=job.codec.read_record(RUN/('diagnostic_'+mode)/NAME/'qualification_01/serial_01/call.json.xz',p['physical_design_sha256'],prefix)
        api.require(pair_equal(serial['original'],serial['candidate']),'Exact original/candidate256 accepted rows and FULL checkpoint')
        telemetry=kernel.telemetry();api.require(telemetry['scopes']==3 and telemetry['compiled_callbacks']>0,
            'Candidate actually reached the qualified callback in all three diagnostic transactions')
        admission=dict(passed=True,discarded_diagnostic_steps=diag,original_and_candidate_exact_restarts=True,
            exact_original_candidate_serial_rows_and_full_checkpoint=True,production_seed_sha256=api.digest(cp),
            production_seed_unchanged=True,diagnostic_trajectory_promoted=False,design_sha256=c.sha(PLAN),
            exact_complete_scientific_record=True,excluded_timing_fields=list(TIMING_FIELDS),excluded_timing_paths=TIMING_PATHS,
            wall_timer_proof=p['wall_timer_proof'],candidate_scope_telemetry=telemetry,
            artifacts={str(q):c.sha(q) for mode in ('original','candidate') for q in (RUN/('diagnostic_'+mode)).rglob('*') if q.is_file()})
        c.commit(RUN/'qualification_pair_01/results.json',admission);c.commit(RUN/'qualification_pair_01/completion.json',dict(passed=True,results_sha256=c.sha(RUN/'qualification_pair_01/results.json')))
        stage='production';reason='call_limit';physical=0
        for index in range(1,p['maximum_new_production_calls']+1):
            reason=stop_reason(p,used,1)
            if reason:break
            if len(entries)+p['inherited']['inherited_segments']>=p['maximum_cumulative_calls_per_case']:reason='cumulative_call_ceiling';break
            remaining=min(p['maximum_new_physical_steps']-physical,p['maximum_saved_steps_including_diagnostics']-used,
                p['maximum_cumulative_physical_steps_per_case']-cp['state']['steps'])
            if remaining<=0:reason='new_physical_step_ceiling';break
            cap=min(p['step_cap_per_call'],remaining);folder=RUN/NAME/f'segment_{index:05d}'
            reservation=dict(role='production',segment=index,maximum_saved_steps=cap,input_checkpoint_sha256=api.digest(cp))
            before_counts=kernel.telemetry();rec,prefix,row=PRIVATE['segment'](p,d,case,geometry,cp,prefix,folder,cap,previous,'production')
            after_counts=kernel.telemetry();api.require(after_counts['scopes']-before_counts['scopes']==1,
                'The actual production transaction entered exactly one qualified callback scope')
            c.commit(folder/'implementation_scope.json',dict(candidate_source_sha256=c.sha(kernel.__file__),candidate_gate_sha256=p['candidate_gate']['sha256'],
                telemetry_before=before_counts,telemetry_after=after_counts,original_transaction_receipt_sha256=c.sha(folder/'results.json'),
                interpretation='Receipt candidate_production_authorized=False refers to old Stage229 prototype. This explicit fresh LM callback admission is separately frozen.',utc=c.utc()))
            cp=rec['result']['checkpoint'];used+=row['new_saved_steps'];physical+=row['new_saved_steps'];previous=c.sha(folder/'results.json')
            entries.append(dict(segment=index,new_saved_steps=row['new_saved_steps'],results_sha256=previous,stop_s=cp['state']['t']));reservation=None
            print('LM_TAIL_SEGMENT_VERIFIED',index,physical,cp['state']['t'],rec['result']['status'],flush=True)
            if rec['result']['status'] in job.policy.COMPLETE:reason='observation_complete';break
        result=dict(case=NAME,complete_observation=reason=='observation_complete',reason=reason,entries=entries,
            cumulative_physical_steps=cp['state']['steps'],cumulative_calls=p['inherited']['inherited_segments']+len(entries),
            diagnostic_saved_steps=diag,final_checkpoint_sha256=api.digest(cp),time_s=cp['state']['t'],horizon_s=case['spec']['horizon_s'],
            final_status='paused_checkpoint' if rec is None else rec['result']['status'])
        c.commit(RUN/NAME/'checkpoint.json',cp);c.commit(RUN/NAME/'prefix.json',prefix.reference());c.commit(RUN/NAME/'results.json',result)
        c.commit(RUN/NAME/'completion.json',dict(results_sha256=c.sha(RUN/NAME/'results.json')));comp=None
        if result['complete_observation']:
            stage='original_full_path_comparison';comp=PRIVATE['compare'](p,d,case,rec['result'],entries,p['inherited']['trace_paths'])
            reason='full_path_accuracy_passed' if comp['passed'] else 'full_path_accuracy_failed'
        c.commit(RUN/'results.json',dict(finished=True,passed=reason=='full_path_accuracy_passed',reason=reason,case=result,
            accepted_physical_steps=physical,discarded_diagnostic_steps=diag,saved_steps_including_diagnostics=used,
            comparison_sha256=None if comp is None else c.sha(OUT/NAME/'comparison_01/results.json'),design_sha256=c.sha(PLAN),
            known_unaccepted_saved_steps=0,unknown_saved_steps_reservation_upper_bound=0,successor_cases_started=0,
            contact_prototype_promoted=False,lm_callback_candidate_used=True,utc=c.utc()))
        c.commit(RUN/'completion.json',dict(results_sha256=c.sha(RUN/'results.json')))
    except Exception as error:
        c.commit(RUN/'failure.json',dict(stage=stage,error=repr(error),traceback=traceback.format_exc(),verified_new_saved_steps=used,
            accepted_entries=entries,unresolved_reservation=reservation,last_verified_checkpoint_sha256=api.digest(cp),utc=c.utc(),dependent_dispatch_stopped=True))
        raise

def authenticate(exit_record):
    global FINAL_PROGRESS
    p=verify();d,case=original_case();seed_cp,seed_prefix,seed_previous=seed_state(p)
    control=RUN.with_name(RUN.name+'_controller');worker=c.read(control/'worker_launch.json')
    api.require(exit_record['retired_exact_identity'] and exit_record['launch_sha256']==c.sha(control/'worker_launch.json')
        and worker['argv']==[str(controller.PYTHON),'-B','-u',str(SELF),'run']
        and controller.inspect(worker['pid'],worker['created'],worker['argv'])['retired'],'Exact retired numerical worker association')
    offline=reader.Reader(job.codec,fresh_bound=c.bound);records=[];errors=[];diag=physical=unaccepted=unknown=0
    identities=dict(authorization_sha256=p['authorization_sha256'],transport_design_sha256=c.sha(PLAN),physical_design_sha256=p['physical_design_sha256'],simulation_cutoff_utc=p['simulation_cutoff_utc'])
    def read_record(folder,parent,parent_prefix,previous,role,cap):
        c.bound();item=dict(folder=str(folder),role=role,reserved_steps=cap);records.append(item)
        if not (folder/'launch.json').exists():
            if any((folder/name).exists() for name in ('call.json.xz','accounting.json','results.json','completion.json')):
                item.update(status='unknown',saved_step_upper_bound=cap,error='Saved body/evidence without authenticated dispatch marker')
            else:item['status']='not_dispatched'
            return None
        try:
            rec,checked=offline.read_record(folder/'call.json.xz',p['physical_design_sha256'],parent_prefix)
            cp=rec['result']['checkpoint'];n=len(rec['rows']);old.saved_count(n,cp['state']['steps']-parent['state']['steps'],n,cap)
            api.require(rec['spec']==case['spec'] and rec['effective_binding']==job.parent.model.binding_for(p['original_binding'],True)
                and rec['numerical_policy_contract_sha256']==p['numerical_policy_contract_sha256']
                and cp['contract']==p['checkpoint_contract'] and api.digest(cp['state'])==cp['state_sha256']
                and rec['input_checkpoint_sha256']==api.digest(parent),'Original raw/spec/full-checkpoint association')
        except Exception as error:
            c.bound();item.update(status='unknown',saved_step_upper_bound=cap,error=repr(error));return None
        accepted=True
        try:
            old.marker_checks(c.read(folder/'launch.json'),role,cap,api.digest(parent),identities,p,worker)
            receipt=c.sealed(folder/'results.json');c.verify(receipt['artifacts'])
            api.require(receipt['passed'] and receipt['summary']['passed'] and receipt['role']==role
                and receipt['new_saved_steps']==n and receipt['input_checkpoint_sha256']==api.digest(parent)
                and receipt['output_checkpoint_sha256']==api.digest(cp) and receipt['previous_receipt_sha256']==previous
                and receipt['original_binding']==p['original_binding'] and receipt['transport_design_sha256']==c.sha(PLAN)
                and receipt['physical_design_sha256']==p['physical_design_sha256']
                and receipt['numerical_policy_contract_sha256']==p['numerical_policy_contract_sha256'],'Original sealed physical/raw/checkpoint ancestry')
            metadata=c.read(folder/'accounting.json');old.saved_count(n,cp['state']['steps']-parent['state']['steps'],metadata['saved_steps'],cap)
            api.require(metadata['saved_steps_known'] and metadata['raw_sha256']==c.sha(folder/'call.json.xz') and metadata['role']==role,'Bounded raw count metadata')
            trace=np.asarray([[r['time_s'],*r['position_m'],*r['orientation'],*r['velocity_generalized']] for r in rec['rows']],dtype=np.float64)
            api.require(np.array_equal(trace,np.load(folder/'trace.npy',allow_pickle=False)),'Exact raw-derived original trace')
        except Exception as error:accepted=False;item['receipt_error']=repr(error)
        item.update(status=('discarded_diagnostic' if role=='restart_diagnostic' else 'accepted') if accepted else 'known_unaccepted',saved_steps=n)
        return rec,checked,n,accepted
    diagnostic_records={};qualified=True
    for mode in ('original','candidate'):
        root=RUN/('diagnostic_'+mode)/NAME/'qualification_01';decoded={};mode_pass=True
        for label,cap in (('serial_01',256),('split_a_01',128),('split_b_01',128)):
            if label=='split_b_01':
                if 'split_a_01' not in decoded:
                    if any((root/label/name).exists() for name in ('launch.json','call.json.xz','accounting.json','results.json','completion.json')):
                        unknown+=cap;records.append(dict(folder=str(root/label),status='unknown',saved_step_upper_bound=cap,error='Split parent unavailable'))
                    mode_pass=False;continue
                parent,prefix=decoded['split_a_01'][0]['result']['checkpoint'],decoded['split_a_01'][1]
                previous=c.sha(root/'split_a_01/results.json') if (root/'split_a_01/results.json').exists() else None
            else:parent,prefix,previous=seed_cp,seed_prefix,seed_previous;offline.prime(prefix)
            got=read_record(root/label,parent,prefix,previous,'restart_diagnostic',cap)
            if got is None:
                if records[-1]['status']=='unknown':unknown+=cap
                mode_pass=False;continue
            rec,checked,n,accepted=got;decoded[label]=(rec,checked)
            if accepted:diag+=n
            else:unaccepted+=n;mode_pass=False
        proof=None
        try:proof=c.sealed(root/'results.json');c.verify(proof['artifacts'])
        except Exception as error:errors.append(dict(mode=mode,error=repr(error)));mode_pass=False
        qualified=qualified and mode_pass and len(decoded)==3 and qualification_equal(decoded,proof,api.digest(seed_cp),c.sha(PLAN))
        diagnostic_records[mode]=decoded
    paired=False
    if all('serial_01' in diagnostic_records[m] for m in ('original','candidate')):
        paired=pair_equal(diagnostic_records['original']['serial_01'][0],diagnostic_records['candidate']['serial_01'][0])
    try:
        admission=c.sealed(RUN/'qualification_pair_01/results.json');c.verify(admission['artifacts'])
        api.require(admission['passed'] and admission['discarded_diagnostic_steps']==1024 and admission['production_seed_sha256']==api.digest(seed_cp)
            and admission['production_seed_unchanged'] and not admission['diagnostic_trajectory_promoted']
            and admission['design_sha256']==c.sha(PLAN) and admission['original_and_candidate_exact_restarts']
            and admission['exact_original_candidate_serial_rows_and_full_checkpoint']
            and admission['exact_complete_scientific_record'] and admission['excluded_timing_fields']==list(TIMING_FIELDS)
            and admission['excluded_timing_paths']==TIMING_PATHS and admission['wall_timer_proof']==p['wall_timer_proof']
            and admission['candidate_scope_telemetry']['scopes']==3 and admission['candidate_scope_telemetry']['compiled_callbacks']>0,
            'Sealed independent admission pair and actual candidate callback use')
    except Exception as error:errors.append(dict(error=repr(error)));qualified=False
    qualified=bool(qualified and paired and diag==1024 and unaccepted==unknown==0)
    cp,prefix,previous=seed_cp,seed_prefix,seed_previous;offline.prime(prefix);entries=[];blocked=not qualified
    FINAL_PROGRESS=dict(checkpoint=cp,prefix=prefix.reference(),accepted_physical_steps=0,discarded_diagnostic_steps=diag,
        known_unaccepted_saved_steps=unaccepted,unknown_saved_steps_reservation_upper_bound=unknown)
    folders=sorted((RUN/NAME).glob('segment_*'))
    api.require(len(folders)<=p['maximum_new_production_calls'],'No dispatch beyond the fresh production-call ceiling')
    for ordinal,folder in enumerate(folders,1):
        c.bound();index=int(folder.name.removeprefix('segment_'))
        cap=min(p['step_cap_per_call'],p['maximum_new_physical_steps']-physical-unaccepted,
            p['maximum_saved_steps_including_diagnostics']-physical-diag-unaccepted-unknown,
            p['maximum_cumulative_physical_steps_per_case']-cp['state']['steps'])
        api.require(index==ordinal and cap>0,'Consecutive bounded new production ancestry')
        got=read_record(folder,cp,prefix,previous,'production',cap)
        if got is None:
            if records[-1]['status']=='unknown':unknown+=cap
            blocked=True
            # Exact parent history is unavailable. Preserve every later record
            # and reserve only the remaining frozen global saved-step ceiling.
            for later in folders[ordinal:]:
                c.bound();remaining=p['maximum_saved_steps_including_diagnostics']-physical-diag-unaccepted-unknown
                if not any(later.iterdir()):continue
                reserve=min(p['step_cap_per_call'],max(0,remaining));unknown+=reserve
                records.append(dict(folder=str(later),status='unknown',saved_step_upper_bound=reserve,error='Earlier unreadable parent blocks independent reconstruction'))
            break
        rec,checked,n,accepted=got
        if not accepted or blocked:
            records[-1]['status']='known_unaccepted_dependency_barrier';unaccepted+=n;blocked=True
            for later in folders[ordinal:]:
                c.bound();remaining=p['maximum_saved_steps_including_diagnostics']-physical-diag-unaccepted-unknown
                reserve=min(p['step_cap_per_call'],max(0,remaining));unknown+=reserve
                records.append(dict(folder=str(later),status='unknown',saved_step_upper_bound=reserve,error='Unaccepted ancestor blocks promotion and independent next-parent proof'))
            break
        try:
            scope=c.read(folder/'implementation_scope.json')
            api.require(scope['candidate_source_sha256']==c.sha(kernel.__file__) and scope['candidate_gate_sha256']==p['candidate_gate']['sha256']
                and scope['original_transaction_receipt_sha256']==c.sha(folder/'results.json')
                and scope['telemetry_after']['scopes']-scope['telemetry_before']['scopes']==1,'Fresh explicit implementation provenance and actual scope hit')
        except Exception as error:
            records[-1].update(status='known_unaccepted_implementation_evidence',scope_error=repr(error));unaccepted+=n;blocked=True
            for later in folders[ordinal:]:
                c.bound();remaining=p['maximum_saved_steps_including_diagnostics']-physical-diag-unaccepted-unknown
                reserve=min(p['step_cap_per_call'],max(0,remaining));unknown+=reserve
                records.append(dict(folder=str(later),status='unknown',saved_step_upper_bound=reserve,error='Implementation evidence failure blocks dependent ancestry'))
            break
        cp,prefix=rec['result']['checkpoint'],checked;previous=c.sha(folder/'results.json');physical+=n
        entries.append(dict(segment=index,new_saved_steps=n,results_sha256=previous,stop_s=cp['state']['t']))
        FINAL_PROGRESS=dict(checkpoint=cp,prefix=prefix.reference(),accepted_physical_steps=physical,discarded_diagnostic_steps=diag,
            known_unaccepted_saved_steps=unaccepted,unknown_saved_steps_reservation_upper_bound=unknown)
        print('LM_TAIL_FINAL_RECORD_VERIFIED',index,physical,flush=True)
    result=None;comp=None
    if (RUN/'completion.json').exists() and not blocked:
        result=c.sealed(RUN/'results.json')
        api.require(not blocked and unaccepted==unknown==0 and result['case']['entries']==entries and result['accepted_physical_steps']==physical
            and result['discarded_diagnostic_steps']==diag and result['saved_steps_including_diagnostics']==physical+diag
            and result['case']['final_checkpoint_sha256']==api.digest(cp)==api.digest(c.read(RUN/NAME/'checkpoint.json'))
            and prefix.reference()==c.read(RUN/NAME/'prefix.json'),'Complete inherited-plus-new raw/checkpoint ledger')
        if result['comparison_sha256']:
            comp=c.sealed(OUT/NAME/'comparison_01/results.json');c.verify(comp['path_artifacts'])
            api.require(c.sha(OUT/NAME/'comparison_01/results.json')==result['comparison_sha256'] and comp['case']==NAME
                and comp['reference_case']==p['reference_case'] and comp['inherited_segments']==p['inherited']['inherited_segments']
                and comp['new_segments']==len(entries) and comp['full_original_start_to_terminal_path']
                and comp['transport_design_sha256']==c.sha(PLAN) and comp['physical_design_sha256']==p['physical_design_sha256'],
                'Original complete-path comparison requires every inherited production trace')
    scientific=bool(result and comp and qualified and not blocked and result['passed'] and comp['passed']
        and comp['full_path_gates']['passed'] and all(comp['full_path_gates']['checks'].values())
        and result['case']['complete_observation'] and comp['observation']['complete_observation']
        and comp['observation']['steps']==cp['state']['steps'] and comp['observation']['stop_s']==cp['state']['t']
        and exit_record['returncode']==0 and not exit_record['forced_cutoff_stop'])
    api.require(physical+unaccepted<=p['maximum_new_physical_steps']+1024-diag
        and physical+diag+unaccepted+unknown<=p['maximum_saved_steps_including_diagnostics']
        and len(entries)<=p['maximum_new_production_calls'] and cp['state']['steps']<=p['maximum_cumulative_physical_steps_per_case']
        and p['inherited']['inherited_segments']+len(entries)<=p['maximum_cumulative_calls_per_case'],'Accepted/known/unknown diagnostic-inclusive bounds')
    destination=OUT/'final_disposition_01';c.bound();c.commit(destination/'recoverable/checkpoint.json',cp)
    c.bound();c.commit(destination/'recoverable/prefix.json',prefix.reference())
    artifacts={}
    for root in (RUN,destination/'recoverable',OUT/NAME/'comparison_01'):
        for q in root.rglob('*'):
            c.bound()
            if q.is_file():artifacts[str(q)]=c.sha(q)
    parent_marker=OUT/'launcher_01/launch.json'
    artifacts[str(parent_marker)]=c.sha(parent_marker)
    final=dict(passed=True,accounting_authenticated=True,scientific_full_path_passed=scientific,qualification_passed=qualified,
        exact_original_candidate_serial_passed=paired,accepted_physical_steps=physical,discarded_diagnostic_steps=diag,
        known_unaccepted_saved_steps=unaccepted,unknown_saved_steps_reservation_upper_bound=unknown,
        cumulative_physical_steps=cp['state']['steps'],cumulative_production_calls=p['inherited']['inherited_segments']+len(entries),new_production_segments=len(entries),
        time_s=cp['state']['t'],reason='worker_failure' if result is None else result['reason'],worker_exit=exit_record,
        final_checkpoint_sha256=api.digest(cp),inherited_seed_sha256=p['inherited']['checkpoint_sha256'],records=records,evidence_errors=errors,
        reader_stats=offline.stats,artifacts=artifacts,source_files=p['source_files'],successor_cases_started=0,contact_prototype_promoted=False,
        lm_callback_candidate_used=physical>0,excluded_timing_fields=list(TIMING_FIELDS),excluded_timing_paths=TIMING_PATHS,
        wall_timer_proof=p['wall_timer_proof'],inherited_production_calls=p['inherited']['inherited_segments'],
        inherited_physical_steps=p['inherited']['inherited_physical_steps'],prior_saved_steps=p['inherited']['prior_saved_steps'],claim=p['claim'],utc=c.utc())
    api.require(output_bytes()<p['maximum_new_output_bytes'],'Final retained-output cap');c.bound();c.commit(destination/'results.json',final)
    c.bound();c.commit(destination/'completion.json',dict(passed=True,results_sha256=c.sha(destination/'results.json')))
    print('LM_TAIL_AUTHENTICATED',qualified,scientific,physical,unaccepted,unknown,flush=True)

def negative_finalization(exit_record,error):
    """Conservative failed-accountant receipt; never fabricate zero unknown work."""
    p=c.read(PLAN);c.bound();cp,prefix,_=seed_state(p);destination=OUT/'failure_disposition_01'
    checked=FINAL_PROGRESS or {};cp=checked.get('checkpoint',cp);prefix_reference=checked.get('prefix',prefix.reference())
    c.commit(destination/'recoverable/checkpoint.json',cp);c.commit(destination/'recoverable/prefix.json',prefix_reference)
    row=dict(passed=False,accounting_authenticated=False,scientific_full_path_passed=False,qualification_passed=False,
        finalizer_error=repr(error),worker_exit=exit_record,accepted_physical_steps=None,discarded_diagnostic_steps=None,
        known_unaccepted_saved_steps=None,unknown_saved_steps_reservation_upper_bound=p['maximum_saved_steps_including_diagnostics'],
        last_independently_authenticated_full_checkpoint_sha256=api.digest(cp),inherited_original_seed_sha256=p['inherited']['checkpoint_sha256'],
        last_original_full_checkpoint_history_preserved=True,
        previous_independently_reconstructed_progress={k:v for k,v in checked.items() if k not in ('checkpoint','prefix')},
        interpretation='Conservative possible permitted work bound, not observed executed steps. New raw records remain unpromoted and require fresh bounded closure.',
        dependent_dispatch_stopped=True,manual_closure_required=True,successor_cases_started=0,utc=c.utc())
    row['artifacts']={str(q):c.sha(q) for q in (destination/'recoverable').glob('*.json')}
    c.bound();c.commit(destination/'results.json',row);c.bound();c.commit(destination/'completion.json',dict(passed=False,results_sha256=c.sha(destination/'results.json')))

def finalize():
    exit_record=None
    try:
        p=verify();psutil.Process().cpu_affinity([p['logical_cpu']])
        exit_record=c.read(RUN.with_name(RUN.name+'_controller')/'worker_exit.json');authenticate(exit_record)
    except Exception as error:
        try:negative_finalization(exit_record,error)
        except Exception as issue:print('LM_TAIL_NEGATIVE_ACCOUNTING_FAILED',repr(issue),flush=True)
        raise

bounded_finalize=clone(old.bounded_finalize,globals())
def final_authentication(exit_record):bounded_finalize(exit_record)
def failed_authentication(exit_record):bounded_finalize(exit_record)

def parent_launch_checks(marker,p,pid,birth,command):
    api.require(marker['pid']==pid and marker['created']==birth
        and marker['argv']==command==[str(controller.PYTHON),'-B','-u',str(SELF),'launch']
        and marker['design_sha256']==p['design_sha256'] and marker['authorization_sha256']==p['authorization_sha256']
        and marker['numerical_cutoff_utc']==p['simulation_cutoff_utc'] and marker['hard_end_utc']==p['end_utc']
        and type(marker['parent_pid']) is int and marker['parent_created']>0 and bool(marker['parent_argv']),
        'Immutable parent launch proof before any numerical worker dispatch')
    return True


def launch():
    os.environ['DEM_CASE_PLAN']=str(PLAN);verify();process=psutil.Process()
    marker_path=OUT/'launcher_01/launch.json';until=min(time.time()+30,datetime.fromisoformat(c.read(PLAN)['simulation_cutoff_utc']).timestamp())
    while not marker_path.exists() and time.time()<until:c.bound();time.sleep(.05)
    marker=c.read(marker_path)
    plan=c.read(PLAN)
    parent_launch_checks(marker,{**plan,'design_sha256':c.sha(PLAN)},process.pid,process.create_time(),process.cmdline())
    controller.inspect(marker['parent_pid'],marker['parent_created'],marker['parent_argv'])
    fn=clone(controller.launch,{**vars(controller),'c':c,'worker':sys.modules[__name__]});fn()

def controls():
    """Pure identity, budget, checkpoint and exact comparator negatives."""
    checks=[clone_checks()];d,case=original_case()
    api.require(c.sha(kernel.__file__)==KERNEL_SHA and c.sha(reader.__file__)==READER_SHA,'Frozen qualified implementation sources')
    p=dict(start_utc='2026-10-09T13:00:00+00:00',end_utc='2026-10-09T15:00:00+00:00',simulation_cutoff_utc='2026-10-09T14:40:00+00:00',
        maximum_new_physical_steps=600000,maximum_new_production_calls=80,maximum_saved_steps_including_diagnostics=601024,
        qualification_steps_per_case=1024,step_cap_per_call=10000,maximum_cumulative_physical_steps_per_case=5000000,
        maximum_cumulative_calls_per_case=1500,workers=1,threads=1,maximum_unverified_records=1,logical_cpu=14,
        minimum_free_disk_bytes=20*1024**3,maximum_new_output_bytes=2*1024**3,finalizer_retirement_reserve_seconds=30,
        only_case=NAME,successor_dispatch_authorized=False,candidate_production_authorized=True,automatic_continuation_authorized=False,
        physical_changes=[],numerical_changes=[],accuracy_gate_changes=[])
    budget_checks(p)
    for key,value in [('maximum_new_physical_steps',600001),('maximum_new_production_calls',81),('maximum_saved_steps_including_diagnostics',601025),
        ('qualification_steps_per_case',512),('maximum_new_output_bytes',2*1024**3+1),('end_utc','2026-10-09T15:00:01+00:00'),
        ('simulation_cutoff_utc','2026-10-09T14:40:01+00:00'),('automatic_continuation_authorized',True),('successor_dispatch_authorized',True)]:
        try:budget_checks({**p,key:value})
        except Exception:checks.append('budget_negative_'+key)
        else:raise AssertionError('Budget mutation accepted: '+key)
    cp={'state':{'t':1.,'steps':256,'history':[[1,2]]},'contract':'same'}
    records={key:({'rows':rows,'result':{'checkpoint':copy.deepcopy(cp)}},None) for key,rows in
        [('serial_01',list(range(256))),('split_a_01',list(range(128))),('split_b_01',list(range(128,256)))]}
    proof=dict(passed=True,diagnostic_saved_steps=512,production_seed_sha256='seed',transport_design_sha256='design',
        exact_serial_split_rows=True,exact_full_checkpoint=True,all_three_independent_physical_audits_passed=True,
        production_seed_unchanged=True,diagnostic_trajectory_promoted=False)
    api.require(qualification_equal(records,proof,'seed','design'),'Original512restart evidence schema')
    wrong=copy.deepcopy(records);wrong['split_b_01'][0]['result']['checkpoint']['state']['history']=[[9,2]]
    api.require(not qualification_equal(wrong,proof,'seed','design'),'FULL checkpoint history mismatch blocks dispatch')
    api.require(not qualification_equal(records,None,'seed','design'),'Missing qualification seal blocks dispatch')
    checks+=['full_checkpoint_history_restart_negative','absent_restart_proof_negative']
    a={'rows':[1,2],'result':{'checkpoint':copy.deepcopy(cp),'time_s':1.,'runtime_seconds':1.,'residual':0.},'other':{'runtime_seconds':5.}}
    b=copy.deepcopy(a);b['result']['runtime_seconds']=2.;api.require(pair_equal(a,b),'Only exact proved wall timer differs')
    for key in ('residual','time_s'):
        b=copy.deepcopy(a);b['result'][key]+=1e-12;api.require(not pair_equal(a,b),'Scientific '+key+' remains exact');checks.append('scientific_negative_'+key)
    b=copy.deepcopy(a);b['other']['runtime_seconds']=6.;api.require(not pair_equal(a,b),'Outside-path timer field remains exact')
    checks+=['exact_path_wall_timer_only','outside_path_same_name_negative']
    try:merge_frozen({'path':'old'},{'path':'changed'})
    except RuntimeError:checks.append('source_input_hash_conflict_negative')
    else:raise AssertionError('Changed original input admitted')
    api.require(job.codec.read_record is old.job.codec.read_record and PRIVATE['segment'].__globals__ is PRIVATE,'Original transport storage/transaction namespace')
    api.require(prior_saved_work({'prior_saved_steps':1041878},{'accepted_physical_steps':28976,'discarded_diagnostic_steps':1024},
        {'shared_saved_steps_including_diagnostics':31024,'prior_attempt_discarded_diagnostic_steps':1024},1072902)==1072902,'Complete prior failed-diagnostic ledger')
    try:prior_saved_work({'prior_saved_steps':1041878},{'accepted_physical_steps':28976,'discarded_diagnostic_steps':1024},
        {'shared_saved_steps_including_diagnostics':31024,'prior_attempt_discarded_diagnostic_steps':1024},1071878)
    except RuntimeError:checks.append('prior_failed_diagnostic_omission_negative')
    else:raise AssertionError('Prior failed diagnostics omitted')
    proof_plan={**p,'design_sha256':'design','authorization_sha256':'auth'}
    command=[str(controller.PYTHON),'-B','-u',str(SELF),'launch']
    marker=dict(pid=11,created=1.,argv=command,design_sha256='design',authorization_sha256='auth',
        numerical_cutoff_utc=p['simulation_cutoff_utc'],hard_end_utc=p['end_utc'],parent_pid=22,parent_created=2.,parent_argv=['parent'])
    parent_launch_checks(marker,proof_plan,11,1.,command)
    for key,value in [('pid',12),('created',1.1),('argv',command+['changed']),('design_sha256','changed'),('authorization_sha256','changed'),
                      ('numerical_cutoff_utc',p['end_utc']),('hard_end_utc',p['simulation_cutoff_utc']),('parent_argv',[])]:
        try:parent_launch_checks({**marker,key:value},proof_plan,11,1.,command)
        except RuntimeError:checks.append('parent_launch_negative_'+key)
        else:raise AssertionError('Parent launch mutation admitted: '+key)
    return dict(passed=True,checks=checks,wall_timer_proof=wall_timer_proof(),offline_reader_controls=reader.controls(job.codec),
        exact_kernel_sha256=KERNEL_SHA,inherited_counts_configuration_driven=True,
        numerical_calls=0,new_trajectory_steps=0,process_actions=0)


def detach():
    """One hidden bounded controller; no extra supervisor or automation."""
    p=verify();folder=OUT/'launcher_01';folder.mkdir(parents=True,exist_ok=False)
    command=[str(controller.PYTHON),'-B','-u',str(SELF),'launch'];env=os.environ.copy();env['DEM_CASE_PLAN']=str(PLAN)
    for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):env[key]='1'
    parent=psutil.Process();child=None;birth=None;actual=None;proven=False
    try:
        with (folder/'stdout.log').open('xb') as stdout,(folder/'stderr.log').open('xb') as stderr:
            child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            birth=psutil.Process(child.pid).create_time();actual=psutil.Process(child.pid).cmdline()
            api.require(actual==command,'Exact hidden current controller command');proven=True
            marker=dict(pid=child.pid,created=birth,argv=command,utc=c.utc(),design_sha256=c.sha(PLAN),authorization_sha256=c.sha(AUTH),
                parent_pid=parent.pid,parent_created=parent.create_time(),parent_argv=parent.cmdline(),numerical_cutoff_utc=p['simulation_cutoff_utc'],hard_end_utc=p['end_utc'])
            c.commit(folder/'launch.json',marker)
    except Exception as error:
        retired=None;retirement_error=None
        if proven:
            try:retired=clone(controller.stop_owned,{**vars(controller),'c':c})(child,birth,command,folder)
            except Exception as issue:retirement_error=repr(issue)
        c.commit(folder/'startup_failure.json',dict(passed=False,error=repr(error),traceback=traceback.format_exc(),
            child_pid=None if child is None else child.pid,observed_birth=birth,observed_command=actual,expected_command=command,
            exact_command_was_proven=proven,exact_child_retirement=retired,retirement_error=retirement_error,
            worker_dispatch_requires_parent_marker=True,unknown_identity_preserved=not proven or retirement_error is not None,
            closed_logs={str(q):c.sha(q) for q in folder.glob('*.log')},utc=c.utc()))
        raise
    print('LM_CASE_HIDDEN_CONTROLLER',child.pid,birth,c.sha(folder/'launch.json'),flush=True);return marker


if __name__=='__main__':{'prepare':prepare,'launch':launch,'detach':detach,'run':run,'finalize':finalize,'controls':lambda:print(controls())}[sys.argv[1]]()
