"""One configured, bounded original-model contact-regime feasibility case.

The original numerical transactions, restart qualification, full-path decision
and final accountant keep their exact code objects. The qualified history
reader is substituted only inside the retired-worker accountant's namespace.
No original module globals or transport reader are changed.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from types import FunctionType, ModuleType, SimpleNamespace
import math, os, sys, traceback

ROOT=Path(__file__).resolve().parents[1]
SELF=Path(__file__).resolve()
sys.path.insert(0,str(SELF.parent))
saved_plan=os.environ.pop('DEM_CASE_PLAN',None)
import single_case_v1 as old
if saved_plan is not None:os.environ['DEM_CASE_PLAN']=saved_plan
import verified_history_reader_v2 as reader
api,job,baseline=old.api,old.job,old.baseline
PLAN=ROOT/'stage233_designs/sample124_fibre_20261009/design_01.json'
AUTH=PLAN.with_name('authorization_01.json')
RUN=ROOT/'stage233_runs'/PLAN.parent.name/'run_01'
OUT=ROOT/'stage233_evaluations'/PLAN.parent.name
NAME='s2_i124_fibre_f0p125'
REFERENCE='s2_i124_fibre_f0p0625'
SOURCE_PLAN=ROOT/'stage232_designs/sample0_sphere_tail_20261008/design_01.json'
FIBRE=ROOT/'stage230_evaluations/sample0_fibre_terminal_20261008'
SPHERE=ROOT/'stage232_evaluations/sample0_sphere_tail_20261008'
EXPECTED={
    str(FIBRE/'final_disposition_01/results.json'):'52bf65f6390722ecb59ec0639ab853c762f8e5e98e2351e4b0ead0b81018380b',
    str(FIBRE/'retirement_01/results.json'):'05799ca292d0160bbea197fc50b685acf277325db9aaec4847073d99c8666d1a',
    str(SPHERE/'final_disposition_01/results.json'):'6d9b76c4e6bfdf72a7b5fa7904571e5da72fd14e0eda8b4c1448a8534eec6292',
    str(SPHERE/'retirement_01/results.json'):'c564328756eb4f0252998bb0a100617c9c61c0aca41d8a0a0221198d1b421b20',
    str(baseline.PREREQUISITE):'8ddadfdee04ec86a38e327103957dc6b09c47b1392d61a001b4f6046c391a884',
}
READER_SHA='3440cc0c282912ebf8a870adb5831db8b5f70f3f785b06d747a72bc84c1df3ec'
c=ModuleType('_configured_case_administration')
c.__dict__.update(vars(old.c))
c.ROOT=ROOT;c.PLAN=PLAN;c.AUTH=AUTH;c.DESIGNS=PLAN.parent;c.RUN=RUN;c.OUT=OUT
for key,fn in vars(old.c).items():
    if isinstance(fn,FunctionType) and fn.__globals__ is vars(old.c):
        setattr(c,key,FunctionType(fn.__code__,vars(c),fn.__name__,fn.__defaults__,fn.__closure__))
PRIVATE=dict(vars(old.prior),c=c,PLAN=PLAN,RUN=RUN,OUT=OUT,AUTH=AUTH)
for key in old.NAMES:
    fn=getattr(old.prior,key)
    PRIVATE[key]=FunctionType(fn.__code__,PRIVATE,fn.__name__,fn.__defaults__,fn.__closure__)

def matched_physics(d,case):
    sphere=next(x for x in d['cases'] if x['sample_id']==case['sample_id']
        and x['shape']=='equal_volume_sphere' and x['factor']==case['factor'])
    a,b=sphere['spec'],case['spec']
    for key in ('field_metadata','initial_state','seed','sample_id','cpd','flow_factor',
                'horizon_pv','horizon_s','nominal_speed_m_s','refinement'):
        api.require(a[key]==b[key],'Original matched labelled-placement control '+key)
    api.require({k:v for k,v in a['config'].items() if k!='prolate_semiaxes_m'}==
                {k:v for k,v in b['config'].items() if k!='prolate_semiaxes_m'},
                'Unchanged matched material, loading and numerical controls')
    va=4*math.pi*math.prod(a['config']['prolate_semiaxes_m'])/3
    vb=4*math.pi*math.prod(b['config']['prolate_semiaxes_m'])/3
    api.require(va>0 and math.isclose(va,vb,rel_tol=1e-12,abs_tol=0),'Original equal-volume shape pair')
    return dict(passed=True,outer_placement=case['sample_id'],original_inner_sample_id=b['sample_id'],
        original_inner_metadata_preserved=True,initial_state=b['initial_state'],sphere_volume_m3=va,
        fibre_volume_m3=vb,equal_volume_relative_tolerance=1e-12,same_field_material_initial_state_and_numerics=True,
        statistical_holdout=False,numerical_calls=0)

def original_case():
    d=PRIVATE['physical_design']();case=next(x for x in d['cases'] if x['id']==NAME)
    api.require(case['sample_id']==124 and case['shape']=='rigid_prolate_ar4' and case['factor']==.125
        and case['reference_case']==REFERENCE and case['spec']['sample_id']==0
        and case['spec']['initial_state']['position_m']==[.0017966984826921968,.0006936786554041544,.00037906400934810815],
        'Exact original outer-labelled placement124 and unmodified historical inner metadata')
    matched_physics(d,case);return d,case

def static_case(plan):
    d,case=original_case();binding=job.binding(d,case)
    contract=job.parent.engine.prior.contracts.expected_contract(case['spec'],job.parent.model.binding_for(binding,True))
    api.require(plan['only_case']==NAME and plan['reference_case']==REFERENCE and plan['fresh_start'] is True
        and plan['original_binding']==binding and plan['checkpoint_contract']==contract
        and plan['matched_physics']==matched_physics(d,case),'Frozen original labelled-placement contract')
    return d,case

def clone_checks():
    baseline.clone_check()
    for key in old.NAMES:
        api.require(PRIVATE[key].__code__ is getattr(old.prior,key).__code__ and PRIVATE[key].__globals__ is PRIVATE,
                    'Exact original transaction code and private namespace '+key)
    for key in RUNNER_NAMES:
        api.require(RUNNER[key].__code__ is getattr(old,key).__code__ and RUNNER[key].__globals__ is RUNNER,
                    'Exact original fresh-run/accountant administration '+key)
    api.require(job.codec.read_record is old.job.codec.read_record and old.prior.c is not c
        and old.PLAN!=PLAN and job.DESIGN==baseline.PLAN,'Original closed and transport bindings remain unchanged')
    return dict(passed=True,original_transaction_code_objects=list(old.NAMES),
        original_administrative_code_objects=list(RUNNER_NAMES),transport_reader_unchanged=True,numerical_calls=0)

def reference_inventory():
    proof=c.sealed(baseline.PREREQUISITE)
    api.require(c.sha(baseline.PREREQUISITE)==EXPECTED[str(baseline.PREREQUISITE)] and proof['passed'],
                'Original complete selected-reference evidence')
    selected=next(row for placement in proof['placements'] for row in placement['cases'] if row['case_id']==REFERENCE)
    api.require(selected['complete_observation'] and selected['start_s']==0.
        and selected['stop_s']==4.682166803491474 and selected['steps']==7530347,
        'Complete original selected124 observation, not an inferred reference')
    old_paths=sorted((baseline.old.RUN/REFERENCE).glob('segment_*.npy'))
    recovered=c.sealed(baseline.inherited.RUN/'production_01/results.json')
    api.require(baseline.inherited.NAME==REFERENCE and recovered['complete_observation']
        and recovered['cumulative_physical_steps']==selected['steps']
        and recovered['time_s']==selected['stop_s'],'Exact selected-reference recovery completion')
    entries=recovered['entries']
    api.require(len(old_paths)==1060 and [x['segment'] for x in entries]==list(range(1,542)),
                'Original1060 plus541 sequential recovery trace inventory')
    recovery_paths=[baseline.inherited.RUN/'production_01'/f"segment_{x['segment']:05d}"/'trace.npy' for x in entries]
    paths=old_paths+recovery_paths
    artifacts={str(path):proof['artifacts'][str(path)] for path in paths}
    api.require(len(artifacts)==1601 and all(path.is_file() for path in paths),'Every mandatory original-path reference exists')
    return dict(case=REFERENCE,original_trace_count=len(old_paths),recovery_trace_count=len(recovery_paths),
        complete_observation=selected,artifacts=artifacts,recovery_receipt=str(baseline.inherited.RUN/'production_01/results.json'))

def controls():
    checks=old.accounting_controls()
    for used,need,want in [(0,512,True),(1499488,512,True),(1499489,512,False),(1500000,1,False)]:
        assert (used+need<=1500000)==want;checks.append('prospective_saved_step_reservation')
    api.require(150*10000==1500000 and 512<1500000 and 150<=1500 and 1500000<5000000,
                'Strict prospective and unchanged original cumulative caps')
    d,case=original_case();matched=matched_physics(d,case)
    prior=c.sealed(FIBRE/'preflight_02/results.json')
    api.require(prior['passed'] and prior['numerical_calls']==prior['process_actions']==0,'Reviewed exact identity/resource controls')
    for path,h in prior['sources'].items():api.require(c.sha(path)==h,'Reviewed exact identity helper source')
    api.require(c.sha(reader.__file__)==READER_SHA,'Frozen qualified offline reader')
    return dict(passed=True,checks=checks,prior_exact_identity_controls=len(prior['controls']),
        clone_checks=clone_checks(),matched_physics=matched,reader_controls=reader.controls(job.codec),
        numerical_calls=0,new_trajectory_steps=0,process_actions=0)

def prepare():
    c.environment();api.require(not PLAN.exists() and not AUTH.exists() and not RUN.exists(),'Fresh configured case; no previous stage resume')
    pure=controls();p=c.read(SOURCE_PLAN);inventory=reference_inventory()
    for path,h in EXPECTED.items():api.require(c.sha(path)==h,'Exact prerequisite file '+path)
    for folder in (FIBRE,SPHERE):
        final=c.sealed(folder/'final_disposition_01/results.json');retired=c.sealed(folder/'retirement_01/results.json')
        api.require(final['passed'] and final['scientific_full_path_passed']
            and final['known_unaccepted_saved_steps']==final['unknown_saved_steps_reservation_upper_bound']==0
            and retired['passed'] and retired['scientific_full_path_passed']
            and retired['all_exact_launch_identities_retired'],'Preceding original sample0 numerical gates closed and retired')
        if folder==FIBRE:
            api.require(final['inherited_full_ancestry_reused'] and final['original_independent_physical_audits_reused']
                and final['new_raw_records_reconstructed']==5 and final['accepted_physical_steps']==4557
                and final['discarded_diagnostic_steps']==512 and final['new_known_saved_steps_including_diagnostics']==5069
                and final['unresolved']==[]
                and retired['independent_final_disposition_sha256']==EXPECTED[str(folder/'final_disposition_01/results.json')]
                and retired['full_path_comparison_sha256']==final['original_full_path_comparison_sha256']
                and retired['original_gates']['passed'] and all(retired['original_gates']['checks'].values()),
                'Exact original Stage230 full-ancestry/raw/count/event accounting schema')
        else:api.require(final['accounting_authenticated'],'Exact Stage232 raw-accounting schema')
    sources={**p['source_files'],str(SELF):c.sha(SELF),str(Path(reader.__file__).resolve()):READER_SHA}
    inputs={**p['inputs'],**EXPECTED,**inventory['artifacts'],str(SOURCE_PLAN):c.sha(SOURCE_PLAN),
        str(SOURCE_PLAN.with_name('authorization_01.json')):c.sha(SOURCE_PLAN.with_name('authorization_01.json'))}
    for path in EXPECTED:
        marker=Path(path).parent/'completion.json';inputs[str(marker)]=c.sha(marker)
    recovery=Path(inventory['recovery_receipt'])
    inputs[str(recovery)]=c.sha(recovery);inputs[str(recovery.parent/'completion.json')]=c.sha(recovery.parent/'completion.json')
    prior_negative=OUT/'preparation_01/admission_failure_01.json'
    if prior_negative.exists():inputs[str(prior_negative)]=c.sha(prior_negative)
    d,case=original_case();binding=job.binding(d,case)
    contract=job.parent.engine.prior.contracts.expected_contract(case['spec'],job.parent.model.binding_for(binding,True))
    start=datetime.now(timezone.utc);end=start+timedelta(hours=2)
    auth=dict(stage='Stage233 labelled124 original fibre contact-regime feasibility',
        human_authorization='Fresh human next9October after complete original sample0 sphere/fibre gates; one bounded original124 fibre prefix and cost decision only.',
        start_utc=start.isoformat(),end_utc=end.isoformat(),simulation_cutoff_utc=(end-timedelta(minutes=20)).isoformat(),
        only_case=NAME,maximum_saved_steps_including_diagnostics=1500000,maximum_new_production_calls=150,
        maximum_cumulative_physical_steps_per_case=5000000,maximum_cumulative_calls_per_case=1500,
        step_cap_per_call=10000,qualification_steps_per_case=512,workers=1,threads=1,logical_cpu=14,maximum_unverified_records=1,
        finalizer_retirement_reserve_seconds=30,minimum_free_disk_bytes=20*1024**3,maximum_new_output_bytes=4*1024**3,
        source_files=sources,inputs=inputs,physical_changes=[],numerical_changes=[],accuracy_gate_changes=[],
        successor_dispatch_authorized=False,candidate_production_authorized=False,automatic_continuation_authorized=False,
        next_cost_and_coverage_decision_required=True,prior_campaigns_remain_closed=True,
        retention='Retain this admitted raw/checkpoint/history, traces and required receipts, failures and unresolved work;4GiB new output cap and20GiB free reserve. No model copies or speculative outputs.',
        claim='Bounded contact-regime/cost feasibility and partial physical/restart verification at labelled placement124 in one packing/flow. Only an actual complete original start-to-terminal path with unchanged accuracy/event gates supports complete temporal verification. No statistical holdout, population shape/flow ranking, experimental/spatial validation or permanent retention.',
        planning_cost='Original complete selected124 producer22.5373h plus independent physical audit1.3531h equals23.8904h. Naive half-step projection11.945h includes those two costs but excludes restart, authentication, decoding and setup; not a speedup bound or completion promise.',
        master_plan_sha256_at_authorization=c.sha(ROOT/'MASTER_PLAN.md'))
    c.commit(AUTH,auth);c.bound();c.verify(sources);c.verify(inputs)
    plan={**auth,'authorization_sha256':c.sha(AUTH),'authorized_end_utc':auth['end_utc'],
        'physical_inputs':p['physical_inputs'],'physical_design_sha256':c.sha(job.DESIGN),
        'numerical_policy_contract_sha256':c.sha(job.WORK),'original_binding':binding,'checkpoint_contract':contract,
        'reference_case':REFERENCE,'reference_inventory':inventory,'fresh_start':True,'matched_physics':matched_physics(d,case),
        'inherited':dict(inherited_segments=0,inherited_physical_steps=0,trace_paths=[],inputs=inventory['artifacts']),
        'controls':pure}
    plan['binding']=c.digest(plan);c.commit(PLAN,plan)
    c.commit(OUT/'preparation_01/results.json',dict(passed=True,design_sha256=c.sha(PLAN),authorization_sha256=c.sha(AUTH),
        controls=pure,reference_trace_count=1601,source_count=len(sources),input_count=len(inputs),numerical_calls=0,new_trajectory_steps=0))
    c.commit(OUT/'preparation_01/completion.json',dict(passed=True,results_sha256=c.sha(OUT/'preparation_01/results.json')))
    print('CONFIGURED_CASE_PREPARED',NAME,end.isoformat(),flush=True)

def verify():
    a=c.bound();c.environment();clone_checks();p=c.read(PLAN)
    api.require(p['binding']==c.digest({k:v for k,v in p.items() if k!='binding'}) and p['authorization_sha256']==c.sha(AUTH),'Frozen configured authority')
    for key,value in a.items():api.require(p[key]==value,'Exact prospective authority '+key)
    api.require(p['only_case']==NAME and not p['successor_dispatch_authorized'] and not p['candidate_production_authorized']
        and not p['automatic_continuation_authorized'] and p['next_cost_and_coverage_decision_required']
        and p['physical_changes']==p['numerical_changes']==p['accuracy_gate_changes']==[],'Only original bounded prefix/cost decision')
    prep=c.sealed(OUT/'preparation_01/results.json')
    api.require(prep['passed'] and prep['design_sha256']==c.sha(PLAN),'Passing frozen preparation')
    c.verify(p['source_files']);c.verify(p['inputs']);static_case(p)
    return p

def output_bytes():
    return RUNNER['original_output_bytes']()

def stop_reason(p,used,needed):
    return RUNNER['original_stop_reason'](p,used,needed)

def update_plan(final=None):
    print('CONFIGURED_CASE_MATERIAL_GATE',NAME,'running' if final is None else final['reason'],flush=True)
    c.bound();p=c.read(PLAN)
    begin='<!-- STAGE233_FIBRE_FEASIBILITY_BEGIN -->';end='<!-- STAGE233_FIBRE_FEASIBILITY_END -->'
    if final is None:
        title='active'
        paragraph=(f"Stage233 is running only original labelled-placement124 fibre at factor0.125 under [design](stage233_designs/{PLAN.parent.name}/design_01.json). "
            f"Numerical cutoff:{p['simulation_cutoff_utc']}; absolute audit/retirement end:{p['end_utc']}, with a further120-second dispatch guard. "
            "Bound:1.5million new saved steps including512 discarded exact-restart diagnostics,150 production calls,10k per segment,one worker/thread,4GiB output and20GiB reserve. "
            "Original5million-physical-step/1500-call limits, equations, transport reader, independent auditor and full-path/event gates are unchanged. "
            "The complete selected0.0625 reference contains1060 originalD: traces plus541 recovery traces. The historical nested sample_id0 remains unchanged; outer placement124 and exact original initial state define this case. "
            "This is a bounded contact-regime/cost feasibility attempt; completion is conditional and the contact prototype remains unpromoted. Review achieved contact coverage and complete-case cost before further continuation. No successor or population campaign is authorized.")
    else:
        title='numerical worker retired; accounting saved'
        paragraph=(f"Stage233 [final accounting](stage233_evaluations/{PLAN.parent.name}/final_disposition_01/results.json):{final['reason']}; "
            f"complete original-path accuracy passed={final['scientific_full_path_passed']}. Accepted physical steps={final['accepted_physical_steps']}, "
            f"discarded diagnostics={final['discarded_diagnostic_steps']},known unaccepted={final['known_unaccepted_saved_steps']}, "
            f"unknown reserved upper bound={final['unknown_saved_steps_reservation_upper_bound']}; last accepted time={final['last_accepted_time_s']:.12g}s. "
            "Full readable raw/checkpoint/history ancestry and failures are preserved. Exact final controller retirement and closed launcher logs need a separate receipt. "
            "No continuation or successor is admitted: review achieved contact coverage and cost first. This labelled single-packing/flow prefix is not a statistical hold-out, population export comparison or permanent-retention result.")
    block=begin+'\n## Stage233 contact-regime feasibility — 9 October 2026\n\n'+paragraph+'\n'+end
    path=ROOT/'MASTER_PLAN.md';text=path.read_text(encoding='utf-8')
    if begin in text:
        left=text.index(begin);right=text.index(end,left)+len(end);text=text[:left]+block+text[right:]
    else:text=text.replace('<!-- STAGE232_SPHERE_TAIL_BEGIN -->',block+'\n\n<!-- STAGE232_SPHERE_TAIL_BEGIN -->',1)
    c.bound();path.write_text(text,encoding='utf-8',newline='\n')
    (ROOT/'CURRENT_PLAN.md').write_text('# Current execution: Stage233 '+title+'\n\n[MASTER_PLAN.md](MASTER_PLAN.md) is authoritative.\n\n'+paragraph+'\n',encoding='utf-8',newline='\n')

def authenticate(exit_record):
    offline=reader.Reader(job.codec,fresh_bound=c.bound,
        progress=lambda stats:print('RAW_RECONSTRUCTION_PROGRESS',stats,flush=True))
    private={**RUNNER,'job':SimpleNamespace(**{**vars(job),
        'codec':SimpleNamespace(**{**vars(job.codec),'read_record':offline.read_record})})}
    for key in ('record_checks','authenticate'):
        fn=getattr(old,key);private[key]=FunctionType(fn.__code__,private,fn.__name__,fn.__defaults__,fn.__closure__)
    api.require(private['authenticate'].__code__ is old.authenticate.__code__
        and job.codec.read_record is old.job.codec.read_record,'Exact retired accountant; original transport reader untouched')
    private['authenticate'](exit_record)

def failure_disposition(error):
    """An accountant exception never becomes a scientific or zero-work pass."""
    c.bound();ceiling=1500000;folder=OUT/'failure_disposition_01'
    row=dict(passed=False,accounting_authenticated=False,scientific_full_path_passed=False,
        nonpromoting=True,manual_closure_required=True,error=repr(error),traceback=traceback.format_exc(),
        accepted_physical_steps=None,discarded_diagnostic_steps=None,known_unaccepted_saved_steps=None,
        unknown_saved_steps_reservation_upper_bound=ceiling,conservative_possible_permitted_new_work_upper_bound=ceiling,
        upper_bound_meaning='Frozen possible permitted-work ceiling, not observed executed steps; independent closure failed.',
        raw_work_preserved=True,last_sealed_checkpoint_promotion=False,dependent_dispatch_stopped=True,
        successor_cases_started=0,contact_prototype_promoted=False,raw_directory=str(RUN),utc=c.utc())
    c.commit(folder/'results.json',row);c.commit(folder/'completion.json',dict(passed=False,nonpromoting=True,results_sha256=c.sha(folder/'results.json')))

def finalize():
    try:
        p=verify();old.psutil.Process().cpu_affinity([p['logical_cpu']])
        authenticate(c.read(RUN.with_name(RUN.name+'_controller')/'worker_exit.json'))
    except Exception as error:
        try:failure_disposition(error)
        except Exception as issue:print('CONFIGURED_CASE_NEGATIVE_CLOSURE_FAILED',repr(issue),flush=True)
        raise

RUNNER_NAMES=('run','record_checks','bounded_finalize','final_authentication','failed_authentication','launch')
RUNNER={**vars(old),'c':c,'PLAN':PLAN,'SELF':SELF,'EXPECTED':EXPECTED,'PRIVATE':PRIVATE,
    '__name__':__name__,'__file__':str(SELF),
    'clone_checks':clone_checks,'static_case':static_case,'verify':verify,'output_bytes':output_bytes,
    'stop_reason':stop_reason,'update_plan':update_plan,'authenticate':authenticate}
for key in RUNNER_NAMES:
    fn=getattr(old,key);RUNNER[key]=FunctionType(fn.__code__,RUNNER,fn.__name__,fn.__defaults__,fn.__closure__)
for name in ('output_bytes','stop_reason'):
    fn=getattr(old,name);RUNNER['original_'+name]=FunctionType(fn.__code__,RUNNER,fn.__name__,fn.__defaults__,fn.__closure__)
run=RUNNER['run'];bounded_finalize=RUNNER['bounded_finalize']
final_authentication=RUNNER['final_authentication'];failed_authentication=RUNNER['failed_authentication'];launch=RUNNER['launch']

if __name__=='__main__':{'prepare':prepare,'launch':launch,'run':run,'finalize':finalize}[sys.argv[1]]()
