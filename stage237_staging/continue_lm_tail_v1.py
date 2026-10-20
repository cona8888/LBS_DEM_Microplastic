"""One separately bounded continuation; original transactions and physical gates.

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
PLAN=Path(os.environ.get('DEM_CASE_PLAN',str(ROOT/'stage237_designs/lm_tail_20261009/design_01.json'))).resolve()
AUTH=PLAN.with_name('authorization_01.json')
RUN=ROOT/'stage237_runs'/PLAN.parent.name/'run_01'
OUT=ROOT/'stage237_evaluations'/PLAN.parent.name
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
    integer('maximum_new_physical_steps',1,30000);integer('maximum_new_production_calls',1,20)
    integer('maximum_saved_steps_including_diagnostics',1025,31024)
    api.require(p['maximum_saved_steps_including_diagnostics']==p['maximum_new_physical_steps']+1024
        and p['qualification_steps_per_case']==1024 and p['step_cap_per_call']==10000
        and p['maximum_cumulative_physical_steps_per_case']==5000000 and p['maximum_cumulative_calls_per_case']==1500,
        'Fresh diagnostics plus original cumulative ceilings')
    start=datetime.fromisoformat(p['start_utc']);end=datetime.fromisoformat(p['end_utc']);cut=datetime.fromisoformat(p['simulation_cutoff_utc'])
    api.require(start.tzinfo is not None and end.tzinfo is not None and cut.tzinfo is not None
        and 0<(end-start).total_seconds()<=3600 and start<cut<end-timedelta(seconds=30),'One new bounded hour including retirement')
    api.require(p['workers']==p['threads']==p['maximum_unverified_records']==1 and p['logical_cpu']==14
        and p['minimum_free_disk_bytes']>=20*1024**3 and p['finalizer_retirement_reserve_seconds']>=30,
        'One qualified worker/thread and retained disk/retirement reserve')
    integer('maximum_new_output_bytes',4*job.codec.base.MAX_COMPRESSED+1,1024**3)
    api.require(p['only_case']==NAME and not p['successor_dispatch_authorized'] and p['candidate_production_authorized']
        and p['physical_changes']==p['numerical_changes']==p['accuracy_gate_changes']==[],'One residual-only continuation; unchanged physical equations and gates')
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
    for key in ('artifacts','closure_artifacts','closed_logs'):mappings.update(r.get(key,{}))
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

def prepare_design(candidate_gate=None,candidate_retirement=None):
    """Parent-invoked pure preparation. Never run an optimizer or integrator."""
    c.environment();clone_checks();pure=controls()
    api.require(not AUTH.exists() and not PLAN.exists() and not RUN.exists() and not OUT.exists(),'Fresh separate admission only')
    candidate_gate=Path(candidate_gate or ROOT/'stage236_evaluations/lm_residual_20261009/results.json').resolve()
    candidate_retirement=Path(candidate_retirement or ROOT/'stage236_evaluations/lm_residual_20261009/final_disposition_01/results.json').resolve()
    screen=c.sealed(candidate_gate);gate_checks(screen)
    screen_design=ROOT/'stage236_designs'/candidate_gate.parent.name/'design_01.json'
    screen_plan=c.read(screen_design)
    api.require(c.sha(screen_design)==screen['design_sha256'] and screen_plan['source_files'][str(Path(kernel.__file__).resolve())]==c.sha(kernel.__file__),
        'Screen measured this exact candidate source')
    retired_candidate=c.sealed(candidate_retirement)
    api.require(retired_candidate['passed'] and retired_candidate.get('exact_launch_identities_retired') is True,
        'Positive retired Stage236 screen required before fresh authority')
    oldplan=c.read(source.PLAN)
    closed=source.OUT/'final_disposition_01/results.json';retired_file=source.OUT/'retirement_01/results.json'
    api.require(c.sha(closed)=='4838ebe085a059a78f6d5ab99bb7d1aee4f5cbb6dd5fef4a5c1bc86748d2d995'
        and c.sha(retired_file)=='538a9dec4d41a00ec5bcfd82c964c8bf0f1c74e957b2ee969dc66a245ced2e5b'
        and c.sha(source.PLAN)=='63eb2a1705ee15471a1ac91be8f31b83bbd7581550d5d1c9e699cd1490c2a31d',
        'Exact separately closed Stage233 seed and original plan')
    final=c.sealed(closed);retired_seed=c.sealed(retired_file)
    cpfile=closed.parent/'recoverable/checkpoint.json';prefixfile=closed.parent/'recoverable/prefix.json'
    cp=c.read(cpfile);prefix=c.read(prefixfile)
    api.require(final['accounting_authenticated'] and final['qualification_passed'] and final['accepted_physical_steps']==1041366
        and final['discarded_diagnostic_steps']==512 and final['known_unaccepted_saved_steps']==final['unknown_saved_steps_reservation_upper_bound']==0
        and not final['scientific_full_path_passed'] and retired_seed['all_exact_launch_identities_retired'],'Accepted incomplete original seed only')
    inherited_inputs=merge_frozen(final['artifacts'],retired_seed['closure_artifacts'],retired_seed['closed_logs'])
    for path in (closed,closed.parent/'completion.json',retired_file,retired_file.parent/'completion.json',source.PLAN,source.AUTH,cpfile,prefixfile):
        inherited_inputs=merge_frozen(inherited_inputs,{str(path):c.sha(path)})
    inherited=dict(checkpoint_file=str(cpfile),checkpoint_sha256=api.digest(cp),prefix=prefix,
        inherited_segments=114,inherited_physical_steps=1041366,prior_saved_steps=1041878,
        last_receipt_sha256=c.sha(source.RUN/NAME/'segment_00114/results.json'),
        trace_paths=[str(source.RUN/NAME/f'segment_{i:05d}/trace.npy') for i in range(1,115)],
        closure_file=str(closed),retirement_file=str(retired_file),inputs=inherited_inputs)
    sources=merge_frozen(oldplan['source_files'],screen_plan['source_files'])
    for path in (SELF,Path(kernel.__file__).resolve(),Path(reader.__file__).resolve()):
        expected=c.sha(path);api.require(str(path) not in sources or sources[str(path)]==expected,'Never replace an inherited source hash')
        sources=merge_frozen(sources,{str(path):expected})
    inputs=merge_frozen(oldplan['inputs'],screen_plan['inputs'],inherited_inputs,screen['artifacts'])
    for key in ('artifacts','closure_artifacts','closed_logs'):inputs=merge_frozen(inputs,retired_candidate.get(key,{}))
    for path in (candidate_gate,candidate_gate.parent/'completion.json',candidate_retirement,candidate_retirement.parent/'completion.json',screen_design,screen_design.with_name('authorization_01.json')):
        inputs=merge_frozen(inputs,{str(path):c.sha(path)})
    start=datetime.now(timezone.utc);end=start+timedelta(minutes=60)
    authority=dict(stage='Stage237 short original-equation LM callback transfer gate',
        human_authorization='Fresh human9October: resolve bottleneck and move on. One bounded independently qualified original difficult-fibre continuation; no closed window reopened.',
        start_utc=start.isoformat(),end_utc=end.isoformat(),simulation_cutoff_utc=(start+timedelta(minutes=40)).isoformat(),
        only_case=NAME,maximum_new_physical_steps=30000,maximum_saved_steps_including_diagnostics=31024,
        maximum_new_production_calls=20,maximum_cumulative_physical_steps_per_case=5000000,maximum_cumulative_calls_per_case=1500,
        step_cap_per_call=10000,qualification_steps_per_case=1024,workers=1,threads=1,logical_cpu=14,maximum_unverified_records=1,
        minimum_free_disk_bytes=20*1024**3,maximum_new_output_bytes=1024**3,finalizer_retirement_reserve_seconds=30,
        successor_dispatch_authorized=False,candidate_production_authorized=True,old_windows_remain_closed=True,
        physical_changes=[],numerical_changes=[],accuracy_gate_changes=[],source_files=sources,inputs=inputs,
        master_plan_sha256_at_authorization=c.sha(ROOT/'MASTER_PLAN.md'),
        claim='Short local equation/restart/physical transfer verification at one labelled difficult placement and one packing/flow. Incomplete original horizon means no full-path accuracy or population shape/flow claim.',
        retention='Retain all current diagnostic/production raw chains, failures, FULL checkpoints/history and independent audits. 1GiB new output including original512MiB compressed-record reserve plus20GiB disk reserve; one worker/thread, no successor.')
    budget_checks(authority);c.commit(AUTH,authority)
    try:
        c.verify(sources);c.verify(inputs);retirement_checks(retired_candidate);retirement_checks(retired_seed)
        d,case=original_case();binding=job.binding(d,case)
        contract=job.parent.engine.prior.contracts.expected_contract(case['spec'],job.parent.model.binding_for(binding,True))
        p={**authority,'authorization_sha256':c.sha(AUTH),'authorized_end_utc':authority['end_utc'],
            'physical_design_sha256':c.sha(job.DESIGN),'numerical_policy_contract_sha256':c.sha(job.WORK),
            'physical_inputs':oldplan['physical_inputs'],'original_binding':binding,'checkpoint_contract':contract,
            'matched_physics':source.matched_physics(d,case),'reference_case':case['reference_case'],'inherited':inherited,
            'candidate_gate':dict(path=str(candidate_gate),sha256=c.sha(candidate_gate)),
            'candidate_screen_design':dict(path=str(screen_design),sha256=c.sha(screen_design)),
            'candidate_retirement':dict(path=str(candidate_retirement),sha256=c.sha(candidate_retirement)),
            'implementation_changes':['Private observer enters separately frozen Stage236 LM callback scope after original hot scope; no persistent install.'],
            'controls':pure,'production_admission':'Original and candidate256vs128+128 FULL-checkpoint exact; original/candidate256 rows/FULL-checkpoint exact. All1024 diagnostics discarded; original Stage233 seed restored.'}
        seed_state(p);p['binding']=c.digest(p);c.commit(PLAN,p)
        receipt=dict(passed=True,design_sha256=c.sha(PLAN),authorization_sha256=c.sha(AUTH),controls=pure,
            inherited_physical_steps=1041366,inherited_production_calls=114,candidate_gate_sha256=c.sha(candidate_gate),
            independent_physical_gates_unchanged=True,original_full_path_reference_retained=True,numerical_calls=0,new_trajectory_steps=0,utc=c.utc())
        c.commit(OUT/'preparation_01/results.json',receipt);c.commit(OUT/'preparation_01/completion.json',dict(passed=True,results_sha256=c.sha(OUT/'preparation_01/results.json')))
        verify();print('LM_TAIL_PREPARED',c.sha(PLAN),authority['end_utc'],flush=True);return p
    except Exception as error:
        c.commit(OUT/'preparation_failure_01.json',dict(passed=False,error=repr(error),traceback=traceback.format_exc(),
            no_numerical_calls=True,dependent_dispatch_stopped=True,frozen_failed_attempt_preserved=True,utc=c.utc()));raise

def seed_state(p):
    s=p['inherited'];cp=c.read(s['checkpoint_file'])
    api.require(s['inherited_segments']==114 and s['inherited_physical_steps']==1041366 and s['prior_saved_steps']==1041878
        and len(s['trace_paths'])==114 and cp['state']['steps']==1041366 and cp['state']['t']==1.2949866444205167,
        'Exact closed Stage233 physical/call/diagnostic ancestry')
    api.require(api.digest(cp)==s['checkpoint_sha256']=='20889305308a8e28387afc4917beb8e52591bbe594e6079da760903590c963e2'
        and api.digest(cp['state'])==cp['state_sha256'] and cp['contract']==p['checkpoint_contract'],'Original complete seed and state contract')
    prefix=job.codec.HistoryState(**s['prefix'],history_bytes=job.codec.packed_history(cp['state']['history']))
    api.require(job.codec.digest(prefix.history_bytes)==prefix.history_sha256 and prefix.design_sha256==p['physical_design_sha256'],
        'Exact full inherited history/reference binding')
    return cp,prefix,s['last_receipt_sha256']

def verify():
    a=c.bound();c.environment();p=c.read(PLAN);budget_checks(p);clone_checks()
    api.require(p['binding']==c.digest({k:v for k,v in p.items() if k!='binding'}) and p['authorization_sha256']==c.sha(AUTH),'Frozen fresh admission')
    for key,value in a.items():api.require(p[key]==value,'Exact new authority '+key)
    c.verify(p['source_files']);c.verify(p['inputs']);c.verify(p['inherited']['inputs'])
    api.require(p['source_files'][str(SELF)]==c.sha(SELF) and p['source_files'][str(Path(kernel.__file__).resolve())]==c.sha(kernel.__file__)
        and p['source_files'][str(Path(reader.__file__).resolve())]==c.sha(reader.__file__),'Actual candidate and offline reader source bindings')
    d,case=original_case()
    api.require(p['original_binding']==job.binding(d,case) and p['physical_design_sha256']==c.sha(job.DESIGN)
        and p['numerical_policy_contract_sha256']==c.sha(job.WORK) and p['reference_case']==case['reference_case']
        and p['matched_physics']==source.matched_physics(d,case),'Original physical and matched-case controls')
    seed_state(p)
    gate=p['candidate_gate'];api.require(c.sha(gate['path'])==gate['sha256'],'Immutable positive candidate screen')
    screened=c.sealed(Path(gate['path']));gate_checks(screened);c.verify(screened['artifacts'])
    screen_design=p['candidate_screen_design'];api.require(c.sha(screen_design['path'])==screen_design['sha256']==screened['design_sha256'],
        'Unchanged screen design/source association')
    screened_plan=c.read(screen_design['path'])
    api.require(screened_plan['source_files'][str(Path(kernel.__file__).resolve())]==c.sha(kernel.__file__),
        'Transport candidate identical to measured candidate')
    retirement=p['candidate_retirement'];api.require(c.sha(retirement['path'])==retirement['sha256'],'Candidate screen retirement receipt')
    retired=c.sealed(Path(retirement['path']));retirement_checks(retired)
    closure=c.sealed(Path(p['inherited']['closure_file']));retired_seed=c.sealed(Path(p['inherited']['retirement_file']))
    api.require(closure['accounting_authenticated'] and closure['qualification_passed'] and not closure['scientific_full_path_passed']
        and closure['accepted_physical_steps']==1041366 and closure['discarded_diagnostic_steps']==512
        and closure['known_unaccepted_saved_steps']==closure['unknown_saved_steps_reservation_upper_bound']==0
        and retired_seed['passed'] and retired_seed['all_exact_launch_identities_retired'],'Closed original incomplete seed; no failed work promoted')
    retirement_checks(retired_seed)
    preparation=c.sealed(OUT/'preparation_01/results.json')
    api.require(preparation['passed'] and preparation['design_sha256']==c.sha(PLAN) and preparation['authorization_sha256']==c.sha(AUTH),
        'Passing frozen preparation before worker dispatch')
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

def scientific_record(value):
    # Exact existing Stage236 scientific exclusions. Physical time_s, residuals,
    # route/counter records and every other field remain in the exact comparison.
    if isinstance(value,dict):return {k:scientific_record(v) for k,v in value.items() if k not in TIMING_FIELDS}
    if isinstance(value,list):return [scientific_record(v) for v in value]
    if isinstance(value,tuple):return tuple(scientific_record(v) for v in value)
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
            exact_complete_scientific_record=True,excluded_timing_fields=list(TIMING_FIELDS),candidate_scope_telemetry=telemetry,
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
                    if (root/label/'launch.json').exists():unknown+=cap;records.append(dict(folder=str(root/label),status='unknown',saved_step_upper_bound=cap,error='Split parent unavailable'))
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
            and admission['candidate_scope_telemetry']['scopes']==3 and admission['candidate_scope_telemetry']['compiled_callbacks']>0,
            'Sealed independent admission pair and actual candidate callback use')
    except Exception as error:errors.append(dict(error=repr(error)));qualified=False
    qualified=bool(qualified and paired and diag==1024 and unaccepted==unknown==0)
    cp,prefix,previous=seed_cp,seed_prefix,seed_previous;offline.prime(prefix);entries=[];blocked=not qualified
    FINAL_PROGRESS=dict(checkpoint=cp,prefix=prefix.reference(),accepted_physical_steps=0,discarded_diagnostic_steps=diag,
        known_unaccepted_saved_steps=unaccepted,unknown_saved_steps_reservation_upper_bound=unknown)
    folders=sorted((RUN/NAME).glob('segment_*'))
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
                and comp['reference_case']==p['reference_case'] and comp['inherited_segments']==114
                and comp['new_segments']==len(entries) and comp['full_original_start_to_terminal_path']
                and comp['transport_design_sha256']==c.sha(PLAN) and comp['physical_design_sha256']==p['physical_design_sha256'],
                'Original complete-path comparison requires entire114-segment inherited prefix')
    scientific=bool(result and comp and qualified and not blocked and result['passed'] and comp['passed']
        and comp['full_path_gates']['passed'] and all(comp['full_path_gates']['checks'].values())
        and result['case']['complete_observation'] and comp['observation']['complete_observation']
        and comp['observation']['steps']==cp['state']['steps'] and comp['observation']['stop_s']==cp['state']['t']
        and exit_record['returncode']==0 and not exit_record['forced_cutoff_stop'])
    api.require(physical+unaccepted<=p['maximum_new_physical_steps']+1024-diag
        and physical+diag+unaccepted+unknown<=p['maximum_saved_steps_including_diagnostics']
        and cp['state']['steps']<=5000000 and 114+len(entries)<=1500,'Accepted/known/unknown diagnostic-inclusive bounds')
    destination=OUT/'final_disposition_01';c.bound();c.commit(destination/'recoverable/checkpoint.json',cp)
    c.bound();c.commit(destination/'recoverable/prefix.json',prefix.reference())
    artifacts={}
    for root in (RUN,destination/'recoverable',OUT/NAME/'comparison_01'):
        for q in root.rglob('*'):
            c.bound()
            if q.is_file():artifacts[str(q)]=c.sha(q)
    final=dict(passed=True,accounting_authenticated=True,scientific_full_path_passed=scientific,qualification_passed=qualified,
        exact_original_candidate_serial_passed=paired,accepted_physical_steps=physical,discarded_diagnostic_steps=diag,
        known_unaccepted_saved_steps=unaccepted,unknown_saved_steps_reservation_upper_bound=unknown,
        cumulative_physical_steps=cp['state']['steps'],cumulative_production_calls=114+len(entries),new_production_segments=len(entries),
        time_s=cp['state']['t'],reason='worker_failure' if result is None else result['reason'],worker_exit=exit_record,
        final_checkpoint_sha256=api.digest(cp),inherited_seed_sha256=p['inherited']['checkpoint_sha256'],records=records,evidence_errors=errors,
        reader_stats=offline.stats,artifacts=artifacts,source_files=p['source_files'],successor_cases_started=0,contact_prototype_promoted=False,
        lm_callback_candidate_used=physical>0,claim=p['claim'],utc=c.utc())
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

def launch():
    os.environ['DEM_CASE_PLAN']=str(PLAN);verify()
    fn=clone(controller.launch,{**vars(controller),'c':c,'worker':sys.modules[__name__]});fn()

def controls():
    """No optimizer/integrator calls: code identity and restart/budget negatives."""
    checks=[clone_checks()]
    cp={'state':{'steps':256,'history':[[1,2]]},'contract':'same'}
    records={k:({'rows':v,'result':{'checkpoint':copy.deepcopy(cp)}},None) for k,v in
        [('serial_01',list(range(256))),('split_a_01',list(range(128))),('split_b_01',list(range(128,256)))]}
    proof=dict(passed=True,diagnostic_saved_steps=512,production_seed_sha256='seed',transport_design_sha256='design',
        exact_serial_split_rows=True,exact_full_checkpoint=True,all_three_independent_physical_audits_passed=True,
        production_seed_unchanged=True,diagnostic_trajectory_promoted=False)
    assert qualification_equal(records,proof,'seed','design')
    for key,value in [('passed',False),('production_seed_sha256','changed'),('transport_design_sha256','changed'),('diagnostic_trajectory_promoted',True)]:
        assert not qualification_equal(records,{**proof,key:value},'seed','design');checks.append('qualification_tamper_'+key)
    bad=copy.deepcopy(records);bad['split_b_01'][0]['result']['checkpoint']['state']['history']=[[9,2]]
    assert not qualification_equal(bad,proof,'seed','design');checks.append('full_history_restart_mismatch_blocks_production')
    assert not pair_equal(records['serial_01'][0],bad['split_b_01'][0]);checks.append('candidate_full_checkpoint_mismatch_blocks_production')
    assert not qualification_equal(records,None,'seed','design');checks.append('absent_qualification_seal_blocks_production')
    proposed=dict(start_utc='2026-10-09T12:00:00+00:00',end_utc='2026-10-09T13:00:00+00:00',simulation_cutoff_utc='2026-10-09T12:40:00+00:00',
        maximum_new_physical_steps=30000,maximum_new_production_calls=20,maximum_saved_steps_including_diagnostics=31024,
        qualification_steps_per_case=1024,step_cap_per_call=10000,maximum_cumulative_physical_steps_per_case=5000000,
        maximum_cumulative_calls_per_case=1500,workers=1,threads=1,maximum_unverified_records=1,logical_cpu=14,
        minimum_free_disk_bytes=20*1024**3,maximum_new_output_bytes=1024**3,finalizer_retirement_reserve_seconds=30,
        only_case=NAME,successor_dispatch_authorized=False,candidate_production_authorized=True,
        physical_changes=[],numerical_changes=[],accuracy_gate_changes=[])
    assert budget_checks(proposed)
    for key,value in [('maximum_new_production_calls',21),('maximum_new_physical_steps',30001),('maximum_saved_steps_including_diagnostics',31025),
        ('qualification_steps_per_case',512),('maximum_new_output_bytes',512*1024**2),('end_utc','2026-10-09T13:00:01+00:00')]:
        try:budget_checks({**proposed,key:value})
        except RuntimeError:checks.append('budget_tamper_rejected_'+key)
        else:raise AssertionError('Out-of-scope budget accepted')
    assert output_reserve_fits(0,1024**3) and not output_reserve_fits(0,512*1024**2)
    checks.append('empty_output_fits_original_four_record_reserve_only_at_positive_margin')
    assert job.codec.read_record is old.job.codec.read_record;checks.append('offline_reader_not_installed_in_transport')
    a=copy.deepcopy(records['serial_01'][0]);b=copy.deepcopy(a)
    a['timing']={'wall_s':1.,'certificate_seconds':2.,'physical_time_s':3.,'residual':4.};a['compute_call_wall_s']=5.
    b['timing']={'wall_s':9.,'certificate_seconds':8.,'physical_time_s':3.,'residual':4.};b['compute_call_wall_s']=7.
    assert pair_equal(a,b);checks.append('only_three_declared_recursive_timing_fields_ignored')
    b['timing']['residual']=4.0000000001;assert not pair_equal(a,b);checks.append('any_residual_difference_blocks_pair')
    b['timing']['residual']=4.;b['timing']['physical_time_s']=3.0000000001;assert not pair_equal(a,b);checks.append('physical_time_difference_blocks_pair')
    try:merge_frozen({'same':'a'},{'same':'b'})
    except RuntimeError:checks.append('conflicting_frozen_input_hash_rejected')
    else:raise AssertionError('Conflicting manifest accepted')
    order=[];state={'original':False,'candidate':False}
    @contextmanager
    def mock_original(runtime,enabled):
        state['original']=True;order.append('original_enter')
        try:yield 'trace'
        finally:state['original']=False;order.append('original_exit')
    @contextmanager
    def mock_candidate():
        assert state['original'];state['candidate']=True;order.append('candidate_enter')
        try:yield
        finally:state['candidate']=False;order.append('candidate_exit')
    try:
        with observed_scope(mock_original,mock_candidate,None,True) as trace:
            assert trace=='trace' and all(state.values());raise ValueError('test failure')
    except ValueError:pass
    assert not any(state.values()) and order==['original_enter','candidate_enter','candidate_exit','original_exit']
    checks.append('candidate_entered_after_original_and_restored_on_exception')
    return dict(passed=True,checks=checks,numerical_calls=0,new_trajectory_steps=0)

if __name__=='__main__':{'prepare':prepare_design,'launch':launch,'run':run,'finalize':finalize,'controls':lambda:print(controls())}[sys.argv[1]]()
