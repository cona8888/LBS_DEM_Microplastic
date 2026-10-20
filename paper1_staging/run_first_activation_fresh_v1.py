"""Fresh fixed timing authority only; all first-activation numerical code is unchanged.

No dispatch occurs on import. Old sources, prepared FULL seed and closed authority
are immutable. Root must pin the actual NEW human timing grant and fresh checked
preparation before create-only authorization; no clock derives from authorize time.
"""
from datetime import datetime,timezone,timedelta
from pathlib import Path
from types import FunctionType,ModuleType
import copy,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'paper1_staging'))
import run_first_activation_common_state_v1 as frozen
SELF=Path(__file__).resolve()
FROZEN_SHA='aa10079519a36fc58c41a62b12861c5d6b7bc8372869be4f97532e1ea0f008dc'
DESIGNS=ROOT/'paper1_designs/first_activation_common_state_20261018_fresh'
OUT=ROOT/'paper1_runs/first_activation_common_state_20261018_fresh'
PLAN,AUTH=DESIGNS/'design_01.json',DESIGNS/'authorization_01.json'
APPROVAL=DESIGNS/'human_time_approval_01/results.json'
FRESH_PREPARED=DESIGNS/'preparation_01/results.json'
PHYSICAL,BASE_PROPOSAL=frozen.PHYSICAL,frozen.PROPOSAL
PROPOSAL=BASE_PROPOSAL
TIME_PROPOSAL=frozen.DESIGNS/'fresh_time_proposal_01.json'
PREPARED,PREPARATION_EXIT=frozen.PREPARED,frozen.PREPARATION_EXIT
START='2026-10-18T06:41:49+00:00'
CUTOFF='2026-10-18T07:11:49+00:00'
DEADLINE='2026-10-18T07:41:49+00:00'
OLD_DEADLINE='2026-10-18T02:59:34.905691+00:00'
GRANT_SHA='f7d39fb47ae8ebc22d02a1b80f8dc45ee0f7686a45f871e0bf9eeff751219c99'
BASE_SHA='0a654c01d83cc6340c4a49035d787545d3ceb98de8733a7c3b7dc25ac1a8f565'
AMEND_SHA='3091b268ce98e26c206ecd08ea1979d72c0fab57eb8c66518e0acc0858f93bec'
PREP_EXIT_SHA='526987cf4a16fee275c4010494a664f5ba6c3e45b5ff844f291a11783af4dc13'
PHYSICAL_SHA='3c6e41fec3e00fa262781dbb2020bd81bf85fe767a391c9f88553f562651cc5d'


def need(value,message):
    if not value:raise RuntimeError('Fresh first-activation time administration: '+message)


def approval_scope():return frozen.approval_scope()


def validate_approval(grant,proposal_sha):
    need(proposal_sha==BASE_SHA and grant.get('passed') is True
         and grant.get('proposal_sha256')==BASE_SHA
         and grant.get('fresh_time_proposal_sha256')==AMEND_SHA,
         'exact approved base experiment and NEW timing amendment')
    need(all(isinstance(grant.get(k),str) and grant[k].strip() for k in ('human_reply','question_reference'))
         and grant.get('human_reviewed_exact_proposal') is True,
         'actual NEW explicit timing reply and provenance')
    need(grant.get('start_utc')==START and grant.get('simulation_cutoff_utc')==CUTOFF
         and grant.get('end_utc')==DEADLINE and grant.get('observed_clock_first_utc')==START,
         'fixed timing begins at the actual approval clock; preparation consumes this same window')
    need(grant.get('new_independent_authority') is True and grant.get('old_authority_closed_unchanged') is True
         and grant.get('only_time_authority_changes') is True and grant.get('all_preparation_inside_this_fixed_window') is True
         and grant.get('old_absolute_end_utc')==OLD_DEADLINE
         and grant.get('preparation_execution_receipt_sha256')==PREP_EXIT_SHA
         and grant.get('scope_original_shared_end_is_preserved_historical') is True,
         'independent fresh grant never resets/reopens the closed old authority')
    need(grant.get('scope')==approval_scope(), 'all previously reviewed numerical/scientific/resource amounts unchanged')
    for key in ('physics_changes','accuracy_gate_changes','route_changes','selector_changes','case_shared_storage_budget_changes'):
        need(grant.get(key)==[], 'timing-only authority: '+key)
    return True


def bounds(start=None):
    need(start is None or start==datetime.fromisoformat(START), 'no renewed clock at authorize completion')
    return datetime.fromisoformat(CUTOFF),datetime.fromisoformat(DEADLINE)


def build_private_namespace(source):
    module=ModuleType('_first_activation_fresh_private');module.__dict__.update(vars(source))
    for key in ('ROOT','SELF','DESIGNS','OUT','PLAN','AUTH','APPROVAL','PHYSICAL','PROPOSAL','PREPARED','PREPARATION_EXIT','DEADLINE'):
        module.__dict__[key]=globals()[key]
    module.CONFIG=copy.deepcopy(source.CONFIG)
    for name,function in vars(source).items():
        if isinstance(function,FunctionType) and function.__globals__ is vars(source):
            clone=FunctionType(function.__code__,vars(module),function.__name__,function.__defaults__,function.__closure__)
            clone.__kwdefaults__=copy.copy(function.__kwdefaults__);setattr(module,name,clone)
    module.private=module
    module._original_authority=module.authority
    module.validate_approval,module.bounds=validate_approval,bounds
    return module


private=build_private_namespace(frozen.private)


def authority(numerical=False):
    p=private._original_authority(numerical)
    need(p['start_utc']==START and p['simulation_cutoff_utc']==p['worker_cutoff_utc']==CUTOFF
         and p['end_utc']==DEADLINE and p['fresh_time_authority'] is True
         and p['fresh_time_proposal_sha256']==AMEND_SHA
         and p['old_absolute_end_utc']==OLD_DEADLINE and p['old_authority_closed_unchanged'] is True
         and p['fresh_preparation_sha256']==private.sha(FRESH_PREPARED),
         'all runtime checks use the separately approved fixed NEW clock and preparation')
    return p


def authorize(expected_grant_sha256,expected_preparation_sha256):
    private.s.environment()
    need(expected_grant_sha256==GRANT_SHA and private.sha(APPROVAL)==GRANT_SHA,
         'root pinned actual NEW human timing grant')
    need(isinstance(expected_preparation_sha256,str) and len(expected_preparation_sha256)==64
         and private.sha(FRESH_PREPARED)==expected_preparation_sha256,
         'root pinned checked fresh preparation')
    need(not PLAN.exists() and not AUTH.exists() and not OUT.exists(), 'fresh create-only authority/output; never duplicate launch')
    need(datetime.fromisoformat(START)<=datetime.now(timezone.utc)
         <datetime.fromisoformat(CUTOFF)-timedelta(seconds=90), 'all preparation consumed inside fixed approval window')
    pins={str(Path(frozen.__file__).resolve()):FROZEN_SHA,str(BASE_PROPOSAL):BASE_SHA,
          str(TIME_PROPOSAL):AMEND_SHA,str(PREPARATION_EXIT):PREP_EXIT_SHA,str(PHYSICAL):PHYSICAL_SHA}
    private.api.verify_mapping(pins)
    grant=private.s.fields.sealed(APPROVAL);validate_approval(grant,BASE_SHA)
    old=private.read(BASE_PROPOSAL);amend=private.read(TIME_PROPOSAL)
    need(old['dispatch_authorized'] is False and old['status']=='PREPARED_AWAITING_EXPLICIT_HUMAN_APPROVAL'
         and old['original_shared_end_utc']==OLD_DEADLINE
         and old['prospective_selector_activation_policy']==frozen.activation_protocol()
         and amend['old_proposal_sha256']==BASE_SHA and amend['unchanged_budget']==old['budget']
         and amend['unchanged_activation_protocol']==old['prospective_selector_activation_policy']
         and amend['unchanged_diagnostic_suballocation']==old['diagnostic_suballocation']
         and amend['old_authority_is_closed_and_will_not_be_reset'] is True,
         'exact original science/cost/active/loading controls retained; only time changed')
    old_exit=private.s.fields.sealed(PREPARATION_EXIT)
    need(old_exit['passed'] and old_exit['actual_returncode']==0 and old_exit['exact_launch_retired']
         and old_exit['runner_source_sha256']==FROZEN_SHA
         and old_exit['original_shared_end_utc']==OLD_DEADLINE,
         'old seed reconstruction/exit provenance preserved at its original source and expired clock')
    fresh=private.s.fields.sealed(FRESH_PREPARED)
    need(fresh['passed'] is True and fresh['dispatch_authorized'] is False
         and fresh['old_preparation_execution_receipt_sha256']==PREP_EXIT_SHA
         and fresh['source_files'].get(str(SELF))==private.sha(SELF), 'fresh reviewed adapter/preparation source binding')
    for body in (old,fresh):
        private.api.verify_mapping(body['source_files']);private.api.verify_mapping(body['physical_inputs'])
    private.api.verify_mapping(grant['expected_source_evidence'])
    frozen.baseline_authentication()
    private.budget_guard(private.STEP_CAP,private.CALL_CAP)
    a=dict(start_utc=START,end_utc=DEADLINE,simulation_cutoff_utc=CUTOFF,worker_cutoff_utc=CUTOFF,
        maximum_saved_steps=private.STEP_CAP,maximum_new_integration_calls=private.CALL_CAP,
        maximum_discarded_diagnostic_steps=private.TOTAL_DIAGNOSTIC_STEPS,
        maximum_diagnostic_integration_calls=private.TOTAL_DIAGNOSTIC_CALLS,
        maximum_cumulative_physical_steps_per_case=private.CASE_STEPS,maximum_cumulative_calls_per_case=private.CASE_CALLS,
        original_shared_saved_step_cap=private.SHARED_STEPS,original_shared_call_cap=private.SHARED_CALLS,
        prior_shared_saved_steps=private.PRIOR_SHARED_STEPS,prior_shared_calls=private.PRIOR_SHARED_CALLS,
        workers=1,threads=1,maximum_unverified_records=1,logical_cpu=14,step_cap_per_call=5000,
        native_seconds_per_record=45,minimum_free_disk_bytes=20*1024**3,maximum_output_bytes=256*1024**2,
        unchanged_total_retention_bytes=20*1024**3,human_approval_sha256=GRANT_SHA,
        fresh_time_authority=True,old_authority_closed_unchanged=True,old_absolute_end_utc=OLD_DEADLINE,
        original_shared_end_utc=OLD_DEADLINE,fresh_preparation_sha256=expected_preparation_sha256,
        prior_numerical_windows=4,maximum_total_numerical_windows=5,independent_numerical_window_ordinal=5,
        failed_original_scheduler_window003_resumed=False,diagnostic_only=True,
        accuracy_promotion_authorized=False,successor_cases_authorized=False)
    private.resources(a)
    sources={**old['source_files'],**fresh['source_files'],str(SELF):private.sha(SELF)}
    inputs={**old['physical_inputs'],**fresh['physical_inputs'],**pins}
    for path in (APPROVAL,APPROVAL.with_name('completion.json'),FRESH_PREPARED,FRESH_PREPARED.with_name('completion.json')):
        inputs[str(path)]=private.sha(path)
    private.api.verify_mapping(sources);private.api.verify_mapping(inputs)
    private.commit(AUTH,a)
    design={**a,'authorization_sha256':private.sha(AUTH),'physical_design_sha256':PHYSICAL_SHA,
        'proposal_sha256':BASE_SHA,'base_proposal_sha256':BASE_SHA,'fresh_time_proposal_sha256':AMEND_SHA,
        'source_files':sources,'physical_inputs':inputs,
        'logical_core_id':old['logical_core_id'],'numerical_policy_contract_sha256':private.sha(private.s.q.job.WORK)}
    design['binding']=private.api.digest(design);private.commit(PLAN,design)
    private.seal(OUT/'authorization_01',dict(passed=True,design_sha256=private.sha(PLAN),
        actual_new_human_timing_grant_sha256=GRANT_SHA,fresh_preparation_sha256=expected_preparation_sha256,
        start_utc=START,simulation_cutoff_utc=CUTOFF,end_utc=DEADLINE,
        old_authority_closed_unchanged=True,new_transport_steps=0,new_native_solver_calls=0,utc=private.s.utc()))
    print(json.dumps(dict(authorized=True,design_sha256=private.sha(PLAN),fixed_start_utc=START,
        numerical_cutoff_utc=CUTOFF,end_utc=DEADLINE)),flush=True)


REUSED=tuple(dict.fromkeys((*frozen.REUSED,*frozen.ADAPTED,*frozen.HELPERS)))

def controls():
    need(private.sha(frozen.__file__)==FROZEN_SHA,'old frozen activation source unchanged')
    for name in REUSED:
        if name in ('authority','bounds'):continue
        old,new=getattr(frozen.private,name),getattr(private,name)
        need(old.__code__ is new.__code__ and new.__globals__ is vars(private), 'complete private unchanged numerical function graph: '+name)
    need(private._original_authority.__code__ is frozen.private.authority.__code__
         and private._original_authority.__globals__ is vars(private), 'original gate code plus strict new timing wrapper')
    need(frozen.private.DEADLINE==OLD_DEADLINE and frozen.private.SELF!=SELF
         and private.CONFIG==frozen.private.CONFIG and private.CONFIG is not frozen.private.CONFIG,
         'no mutable frozen original globals changed')
    need(private.budget_guard.__kwdefaults__==frozen.private.budget_guard.__kwdefaults__, 'unchanged actual all-attempt baselines')
    private.budget_guard(private.STEP_CAP,private.CALL_CAP)
    need(bounds(datetime.fromisoformat(START))==(datetime.fromisoformat(CUTOFF),datetime.fromisoformat(DEADLINE)), 'fixed grant clocks')
    rejected=0
    for start in (datetime.fromisoformat(START)+timedelta(seconds=1),datetime.fromisoformat(DEADLINE),datetime(2026,10,18,6,41,49)):
        try:bounds(start)
        except RuntimeError:rejected+=1
        else:raise RuntimeError('A reset/invalid fresh clock was admitted')
    return dict(passed=True,zero_transport_steps=0,zero_native_solver_calls=0,
        complete_private_numerical_code_objects_unchanged=True,fixed_clock_rejections=rejected,
        no_default_dispatch=True,old_authority_preserved_closed=True,new_explicit_time_grant_required=True)


private.authority=authority
private.authorize,private.controls=authorize,controls
for _name in REUSED:
    if _name not in ('authority','bounds'):globals()[_name]=getattr(private,_name)

if __name__=='__main__':
    action=sys.argv[1] if len(sys.argv)>1 else None
    if action=='controls' and len(sys.argv)==2:print(json.dumps(controls(),sort_keys=True),flush=True)
    elif action=='authorize' and len(sys.argv)==4:authorize(sys.argv[2],sys.argv[3])
    elif action in ('run','supervise','evaluate') and len(sys.argv)==2:getattr(private,action)()
    else:raise SystemExit('Explicit controls, authorize EXACT_GRANT_SHA EXACT_PREPARATION_SHA, or separately authorized supervise/run/evaluate only; no default dispatch.')
