"""Unlaunched administration for one prospectively selected persistent episode.

The prior numerical/physical/selector/evaluator/ledger code is cloned into a
private namespace.  No old module global is edited.  Permission is prospective
and must truthfully distinguish the user's direct instruction from the exact
limits selected by the agent.  Importing this module confers no authority.
"""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import FunctionType, ModuleType
import copy
import importlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'paper1_staging'))
import run_support_common_state_v3 as frozen

SELF = Path(__file__).resolve()
FROZEN_SHA = '229589bcf20dec6c2c1bbd92ff7d5974f12c6f16a2ce18dc85826116717ea867'
PREPARATION_NAME = 'prepare_persistent_common_state_v1'
DESIGNS = ROOT / 'paper1_designs/first_persistent_common_state_20261017'
OUT = ROOT / 'paper1_runs/first_persistent_common_state_20261017'
PLAN, AUTH = DESIGNS / 'design_01.json', DESIGNS / 'authorization_01.json'
PHYSICAL, PROPOSAL = DESIGNS / 'physical_cases_01.json', DESIGNS / 'proposal_01.json'
APPROVAL = DESIGNS / 'permission_01/results.json'
PREPARED = DESIGNS / 'preparation_01/results.json'
PREPARATION_EXIT = DESIGNS / 'preparation_execution_receipt_01/results.json'
DEADLINE = '2026-10-18T02:59:34.905691+00:00'
STEP_CAP, CALL_CAP = 52024, 17
LOCAL_STEPS, LOCAL_CALLS = (17000, 34000), (4, 7)
PRIOR_STEPS, PRIOR_CALLS = 10233956, 2142
CASE_STEPS, CASE_CALLS = 11300000, 2400
SHARED_STEPS, SHARED_CALLS = 5632768, 1217
PRIOR_SHARED_STEPS, PRIOR_SHARED_CALLS = 4586044, 972
PRIOR_DIAGNOSTIC_STEPS, PRIOR_DIAGNOSTIC_CALLS = 67259, 34
TOTAL_DIAGNOSTIC_STEPS, TOTAL_DIAGNOSTIC_CALLS = 119283, 51
PRIOR_NUMERICAL_WINDOWS, MAXIMUM_TOTAL_NUMERICAL_WINDOWS = 3, 4
BASELINE_PINS = {
    ROOT / 'paper1_designs/full_horizon_timecap_20261016/design_01.json': 'aead45d9b3983c928f9f5eabd0c77c21c23084ff7e9d9c185c520ed59380f41f',
    ROOT / 'paper1_runs/full_horizon_timecap_20261016/final_execution_receipt_01/results.json': 'd23b764b5d5c3769ee2607aca7c0107e424352641306b6575a9b2522f943bf1f',
    ROOT / 'paper1_runs/full_horizon_timecap_20261016/comparison_fine/results.json': '15d48be2710368ad8499a2998b53f0c31c085b6f1880116fc317d47b1ad048d7',
    ROOT / 'paper1_runs/support_common_state_20261017_v2/final_execution_receipt_01/results.json': 'd34c607f6278235173470f1778826e4320320b48cd565f9eb975d31d551511cb',
    ROOT / 'paper1_evaluations/support_exact_window_context_20261017/execution_receipt_01/results.json': '83a32c06e079cf63ad1bd6f47985c5d43b85cd442d3ebb1f7afc0059dbc85015',
}


def need(value, message):
    if not value:
        raise RuntimeError('Persistent common-state administration: ' + message)


def approval_scope():
    return dict(support_common_state_diagnostic_authorized=True,
        supplemental_diagnostic_allocation_authorized=True,
        agent_selected_exact_limits_under_direct_instruction=True,
        maximum_new_saved_steps=STEP_CAP, maximum_new_integration_calls=CALL_CAP,
        maximum_discarded_diagnostic_steps=TOTAL_DIAGNOSTIC_STEPS,
        maximum_diagnostic_integration_calls=TOTAL_DIAGNOSTIC_CALLS,
        existing_case_saved_step_cap=CASE_STEPS, existing_case_call_cap=CASE_CALLS,
        original_shared_saved_step_cap=SHARED_STEPS, original_shared_call_cap=SHARED_CALLS,
        prior_numerical_windows=PRIOR_NUMERICAL_WINDOWS,
        maximum_total_numerical_windows=MAXIMUM_TOTAL_NUMERICAL_WINDOWS,
        additional_independent_numerical_windows=1, maximum_window_minutes=60,
        original_shared_end_utc=DEADLINE)


permission_scope = approval_scope


def validate_approval(permission, proposal_sha):
    need(permission.get('passed') is True and permission.get('proposal_sha256') == proposal_sha,
         'caller-pinned permission binds the exact prospective proposal')
    need(permission.get('actual_human_reply') == 'allowed and next'
         and isinstance(permission.get('direct_user_instruction_reference'), str)
         and bool(permission['direct_user_instruction_reference'].strip()), 'actual direct instruction and provenance')
    need(permission.get('human_reviewed_exact_proposal') is False
         and permission.get('exact_bounded_allocations_selected_by_agent') is True,
         'never claim human review of previously unseen exact allocations')
    seal = permission.get('preparation_execution_receipt_sha256')
    need(isinstance(seal, str) and len(seal) == 64 and all(x in '0123456789abcdef' for x in seal),
         'closed prepared evidence is explicitly pinned')
    scope = permission.get('scope', {})
    need(all(type(scope.get(key)) is type(value) and scope[key] == value
             for key, value in approval_scope().items()), 'exact bounded independent window/allocation scope')
    return True


class LazyPreparation:
    __file__ = str(ROOT / 'paper1_staging' / (PREPARATION_NAME + '.py'))

    def __getattr__(self, name):
        return getattr(importlib.import_module(PREPARATION_NAME), name)


def build_private_namespace(source):
    """Clone the complete original module function graph, retaining code objects."""
    private = ModuleType('_paper1_persistent_common_state_private')
    private.__dict__.update(vars(source))
    for key in ('ROOT', 'SELF', 'DESIGNS', 'OUT', 'PLAN', 'AUTH', 'PHYSICAL', 'PROPOSAL', 'APPROVAL',
                'PREPARED', 'PREPARATION_EXIT', 'DEADLINE', 'STEP_CAP', 'CALL_CAP', 'LOCAL_STEPS', 'LOCAL_CALLS',
                'PRIOR_STEPS', 'PRIOR_CALLS', 'CASE_STEPS', 'CASE_CALLS', 'SHARED_STEPS', 'SHARED_CALLS',
                'PRIOR_SHARED_STEPS', 'PRIOR_SHARED_CALLS', 'TOTAL_DIAGNOSTIC_STEPS', 'TOTAL_DIAGNOSTIC_CALLS'):
        private.__dict__[key] = globals()[key]
    private.preparation = LazyPreparation()
    private.CONFIG = copy.deepcopy(source.CONFIG)
    for name, function in vars(source).items():
        if isinstance(function, FunctionType) and function.__globals__ is vars(source):
            clone = FunctionType(function.__code__, vars(private), function.__name__, function.__defaults__, function.__closure__)
            clone.__kwdefaults__ = copy.copy(function.__kwdefaults__)
            setattr(private, name, clone)
    private.budget_guard.__kwdefaults__ = dict(prior_case_saved=PRIOR_STEPS, prior_case_calls=PRIOR_CALLS,
        prior_shared_saved=PRIOR_SHARED_STEPS, prior_shared_calls=PRIOR_SHARED_CALLS)
    private.approval_scope, private.validate_approval = approval_scope, validate_approval
    return private


private = build_private_namespace(frozen)


def baseline_authentication():
    private.api.verify_mapping({str(path): digest for path, digest in BASELINE_PINS.items()})
    full = private.s.fields.sealed(ROOT / 'paper1_runs/full_horizon_timecap_20261016/final_execution_receipt_01/results.json')
    old = private.read(ROOT / 'paper1_designs/full_horizon_timecap_20261016/design_01.json')
    local = private.s.fields.sealed(ROOT / 'paper1_runs/support_common_state_20261017_v2/final_execution_receipt_01/results.json')
    analysis = private.s.fields.sealed(ROOT / 'paper1_evaluations/support_exact_window_context_20261017/execution_receipt_01/results.json')
    negative = private.s.fields.sealed(ROOT / 'paper1_runs/full_horizon_timecap_20261016/comparison_fine/results.json')
    need(full['passed'] and local['passed'] and analysis['passed'] and negative['passed'] is False
         and full['qualification_passed'] is False and full['dependent_dispatch_stopped'] is True
         and local['core_result_admitted'] is False and analysis['core_result_admitted'] is False,
         'all earlier attempts closed; original whole-path failure remains stopped')
    a, b = full['ledger'], local['ledger']
    need(b['ledger_authenticated'] is True and not b['admission_failures']
         and a['known_unaccepted_saved_steps'] == a['unknown_reserved_steps_upper_bound'] == 0
         and b['known_unaccepted_saved_steps'] == b['unknown_reserved_steps_upper_bound'] == 0,
         'no unresolved prior work')
    totals = (old['baseline']['conservative_prospective_baseline_saved_steps'] + a['saved_steps'] + b['accepted_diagnostic_steps'],
              old['baseline']['conservative_prospective_baseline_integration_calls'] + a['calls'] + b['conservative_call_charges'],
              a['saved_steps'] + b['accepted_diagnostic_steps'], a['calls'] + b['conservative_call_charges'],
              a['diagnostic_steps'] + b['accepted_diagnostic_steps'], a['diagnostic_calls'] + b['conservative_call_charges'])
    need(totals == (PRIOR_STEPS, PRIOR_CALLS, PRIOR_SHARED_STEPS, PRIOR_SHARED_CALLS,
                   PRIOR_DIAGNOSTIC_STEPS, PRIOR_DIAGNOSTIC_CALLS), 'exact latest cumulative/shared/diagnostic baselines')
    launches = [row['launch'] for row in full['identity_inspections_after_hashing']]
    launches += list(local['exact_launches'].values()) + [analysis['exact_analysis_launch']]
    for launch in launches:
        need(private.inspect(launch)['retired'], 'earlier exact birth/full command remains retired')
    return totals


def authorize(expected_permission_sha256):
    """Root administration only; creates no human reply and never launches."""
    private.s.environment()
    need(isinstance(expected_permission_sha256, str) and len(expected_permission_sha256) == 64
         and all(x in '0123456789abcdef' for x in expected_permission_sha256), 'exact caller-pinned permission SHA')
    need(not PLAN.exists() and not AUTH.exists() and not OUT.exists(), 'fresh create-only independent fourth window')
    need(private.sha(APPROVAL) == expected_permission_sha256, 'trusted root-supplied actual permission receipt')
    permission = private.s.fields.sealed(APPROVAL)
    validate_approval(permission, private.sha(PROPOSAL))
    proposal, prepared = private.read(PROPOSAL), private.s.fields.sealed(PREPARED)
    exited = private.s.fields.sealed(PREPARATION_EXIT)
    launch = private.read(private.preparation.PREPARATION_LAUNCH)
    need(permission['preparation_execution_receipt_sha256'] == private.sha(PREPARATION_EXIT)
         and exited['passed'] is True and type(exited['actual_returncode']) is int and exited['actual_returncode'] == 0
         and exited['exact_launch_retired'] is True
         and exited['preparation_launch_sha256'] == private.sha(private.preparation.PREPARATION_LAUNCH)
         and exited['preparation_source_sha256'] == private.sha(private.preparation.__file__) == launch['preparation_source_sha256']
         and exited['runner_source_sha256'] == private.sha(SELF) == launch['runner_source_sha256']
         and exited['original_shared_end_utc'] == launch['original_shared_end_utc'] == DEADLINE
         and private.inspect(launch)['retired'], 'exact closed seed preparation and immutable runner association')
    need(prepared['passed'] and prepared['dispatch_authorized'] is False
         and prepared['proposal_sha256'] == private.sha(PROPOSAL)
         and prepared['physical_design_sha256'] == private.sha(PHYSICAL), 'complete reviewable closed preparation')
    need(proposal['dispatch_authorized'] is False
         and proposal['status'] == 'PREPARED_AWAITING_EXPLICIT_SCOPE_RECORD'
         and proposal['original_shared_end_utc'] == DEADLINE
         and proposal['physics_changes'] == proposal['accuracy_gate_changes']
             == proposal['contact_route_changes'] == proposal['selector_policy_changes'] == []
         and proposal['required_permission_scope'] == approval_scope(), 'prospective exact agent-selected administrative scope')
    for row in (proposal, prepared):
        private.api.verify_mapping(row['source_files']); private.api.verify_mapping(row['physical_inputs'])
    baseline_authentication()
    budget = proposal['budget']
    need(proposal['source_files'].get(str(SELF)) == private.sha(SELF)
         and (budget['maximum_additional_saved_steps'], budget['maximum_additional_calls']) == (STEP_CAP, CALL_CAP)
         and (budget['prior_conservative_case_saved_steps'], budget['prior_conservative_case_calls']) == (PRIOR_STEPS, PRIOR_CALLS)
         and (budget['prior_shared_saved_steps'], budget['prior_shared_calls']) == (PRIOR_SHARED_STEPS, PRIOR_SHARED_CALLS)
         and (budget['original_shared_saved_step_cap'], budget['original_shared_call_cap']) == (SHARED_STEPS, SHARED_CALLS)
         and (budget['maximum_case_saved_steps_after'], budget['maximum_case_calls_after']) == (PRIOR_STEPS + STEP_CAP, PRIOR_CALLS + CALL_CAP)
         and (budget['maximum_shared_saved_steps_after'], budget['maximum_shared_calls_after']) == (PRIOR_SHARED_STEPS + STEP_CAP, PRIOR_SHARED_CALLS + CALL_CAP)
         and budget['branch_local_step_caps'] == list(LOCAL_STEPS) and budget['branch_local_call_caps'] == list(LOCAL_CALLS)
         and budget['exact_restart_steps_per_branch'] == 512 and budget['exact_restart_calls_per_branch'] == 3
         and proposal['diagnostic_suballocation']['already_used_diagnostic_steps'] == PRIOR_DIAGNOSTIC_STEPS
         and proposal['diagnostic_suballocation']['already_used_diagnostic_calls'] == PRIOR_DIAGNOSTIC_CALLS
         and proposal['diagnostic_suballocation']['requested_revised_total_diagnostic_step_allocation'] == TOTAL_DIAGNOSTIC_STEPS
         and proposal['diagnostic_suballocation']['requested_revised_total_diagnostic_call_allocation'] == TOTAL_DIAGNOSTIC_CALLS,
         'exact frozen new costs and all prior charges')
    physical = private.read(PHYSICAL)
    policy = proposal['prospective_selector_activation_policy']
    need(proposal['seed_time_s'] == physical['seed_time_s']
         and proposal['local_stop_s'] == physical['local_stop_s'] == physical['seed_time_s'] + .01
         and proposal['factors'] == [.0625, .03125]
         and policy['stop_on_any_activation'] is True and policy['including_pending_journal_witnesses'] is True
         and policy['applies_to_restart_and_local_records'] is True
         and policy['extra_restart_steps_authorized'] == 0 and policy['implicit_active_restart_waiver'] is False
         and policy['later_easier_seed_selection_authorized'] is False,
         'fixed same-state10ms pair and unchanged ANY activation STOP; no easier seed or active waiver')
    start = datetime.now(timezone.utc)
    cutoff, end = private.bounds(start)
    authorization = dict(start_utc=start.isoformat(), end_utc=end.isoformat(), simulation_cutoff_utc=cutoff.isoformat(),
        worker_cutoff_utc=cutoff.isoformat(), maximum_saved_steps=STEP_CAP, maximum_new_integration_calls=CALL_CAP,
        maximum_discarded_diagnostic_steps=TOTAL_DIAGNOSTIC_STEPS, maximum_diagnostic_integration_calls=TOTAL_DIAGNOSTIC_CALLS,
        maximum_cumulative_physical_steps_per_case=CASE_STEPS, maximum_cumulative_calls_per_case=CASE_CALLS,
        original_shared_saved_step_cap=SHARED_STEPS, original_shared_call_cap=SHARED_CALLS,
        prior_shared_saved_steps=PRIOR_SHARED_STEPS, prior_shared_calls=PRIOR_SHARED_CALLS,
        workers=1, threads=1, maximum_unverified_records=1, logical_cpu=14, step_cap_per_call=5000,
        native_seconds_per_record=45, minimum_free_disk_bytes=20 * 1024**3, maximum_output_bytes=256 * 1024**2,
        unchanged_total_retention_bytes=20 * 1024**3, human_approval_sha256=expected_permission_sha256,
        permission_receipt_sha256=expected_permission_sha256, exact_allocations_agent_selected=True,
        human_reviewed_exact_proposal=False, original_shared_end_utc=DEADLINE,
        prior_numerical_windows=3, maximum_total_numerical_windows=4, independent_numerical_window_ordinal=4,
        failed_original_scheduler_window003_resumed=False, diagnostic_only=True,
        accuracy_promotion_authorized=False, successor_cases_authorized=False)
    private.resources(authorization)
    sources = {**proposal['source_files'], str(SELF): private.sha(SELF), str(Path(frozen.__file__).resolve()): FROZEN_SHA}
    inputs = dict(proposal['physical_inputs'])
    for path in (PROPOSAL, APPROVAL, APPROVAL.with_name('completion.json'), PREPARATION_EXIT,
                 PREPARATION_EXIT.with_name('completion.json'), PREPARED, PREPARED.with_name('completion.json')):
        inputs[str(path)] = private.sha(path)
    private.api.verify_mapping(sources); private.api.verify_mapping(inputs)
    private.commit(AUTH, authorization)
    design = {**authorization, 'authorization_sha256': private.sha(AUTH), 'physical_design_sha256': private.sha(PHYSICAL),
        'proposal_sha256': private.sha(PROPOSAL), 'source_files': sources, 'physical_inputs': inputs,
        'logical_core_id': proposal['logical_core_id'], 'numerical_policy_contract_sha256': private.sha(private.s.q.job.WORK)}
    design['binding'] = private.api.digest(design)
    private.commit(PLAN, design)
    private.seal(OUT / 'authorization_01', dict(passed=True, design_sha256=private.sha(PLAN),
        permission_receipt_sha256=expected_permission_sha256, human_reviewed_exact_proposal=False,
        new_transport_steps=0, new_native_solver_calls=0, original_shared_end_utc=DEADLINE, utc=private.s.utc()))
    print(json.dumps(dict(authorized=True, design_sha256=private.sha(PLAN), numerical_cutoff_utc=cutoff.isoformat(),
                         end_utc=end.isoformat(), human_reviewed_exact_proposal=False)), flush=True)


REUSED = ('run', 'invoke', 'context', 'evaluate', 'ledger', 'failed_ledger', 'child', 'supervise', 'authority',
          'bound', 'verify_inputs', 'resources', 'bounds', 'budget_guard', 'activation_index', 'inspect',
          'stop_exact', 'recapture_owned_launch', 'store_checkpoint', 'retirement_snapshot', 'control_hash_snapshot')


def controls():
    need(private.sha(frozen.__file__) == FROZEN_SHA, 'unchanged original frozen runner bytes')
    for name in REUSED:
        need(getattr(private, name).__code__ is getattr(frozen, name).__code__
             and getattr(private, name).__globals__ is vars(private), 'private unchanged function code: ' + name)
    need(frozen.PRIOR_STEPS == 10184681 and frozen.PRIOR_CALLS == 2125
         and frozen.OUT != OUT and frozen.SELF != SELF and frozen.preparation is not private.preparation,
         'original globals are untouched')
    need(private.budget_guard.__kwdefaults__ == dict(prior_case_saved=PRIOR_STEPS, prior_case_calls=PRIOR_CALLS,
         prior_shared_saved=PRIOR_SHARED_STEPS, prior_shared_calls=PRIOR_SHARED_CALLS)
         and frozen.budget_guard.__kwdefaults__['prior_case_saved'] == 10184681, 'new budget defaults without old mutation')
    need(private.run.__globals__['invoke'] is private.invoke and private.invoke.__globals__['context'] is private.context
         and private.context.__globals__['PLAN'] == PLAN and private.context.__globals__['SELF'] == SELF,
         'actual producer/evaluator call graph and contextual new paths')
    need(private.CONFIG == frozen.CONFIG and private.CONFIG is not frozen.CONFIG
         and private.preparation.__file__.endswith(PREPARATION_NAME + '.py'), 'private policy copy and lazy selected seed')
    private.budget_guard(STEP_CAP, CALL_CAP)
    rejected = 0
    for args, kwargs in (((STEP_CAP + 1, CALL_CAP), {}), ((STEP_CAP, CALL_CAP + 1), {}),
        ((STEP_CAP, CALL_CAP), dict(prior_case_saved=CASE_STEPS - STEP_CAP + 1)),
        ((STEP_CAP, CALL_CAP), dict(prior_case_calls=CASE_CALLS - CALL_CAP + 1)),
        ((STEP_CAP, CALL_CAP), dict(prior_shared_saved=SHARED_STEPS - STEP_CAP + 1)),
        ((STEP_CAP, CALL_CAP), dict(prior_shared_calls=SHARED_CALLS - CALL_CAP + 1))):
        try:
            private.budget_guard(*args, **kwargs)
        except RuntimeError:
            rejected += 1
        else:
            raise RuntimeError('Budget overflow control admitted')
    permission = dict(passed=True, proposal_sha256='a' * 64, actual_human_reply='allowed and next',
        direct_user_instruction_reference='Synthetic fixture only', human_reviewed_exact_proposal=False,
        exact_bounded_allocations_selected_by_agent=True, preparation_execution_receipt_sha256='b' * 64,
        scope=approval_scope())
    validate_approval(permission, 'a' * 64)
    for key, value in (('human_reviewed_exact_proposal', True), ('exact_bounded_allocations_selected_by_agent', False),
                       ('actual_human_reply', 'Approve exact numbers'), ('preparation_execution_receipt_sha256', None)):
        bad = copy.deepcopy(permission); bad[key] = value
        try:
            validate_approval(bad, 'a' * 64)
        except RuntimeError:
            rejected += 1
        else:
            raise RuntimeError('Untrue permission provenance admitted')
    for start in (datetime.fromisoformat(DEADLINE), datetime.fromisoformat(DEADLINE) - timedelta(minutes=30)):
        try:
            private.bounds(start)
        except RuntimeError:
            rejected += 1
        else:
            raise RuntimeError('Expired or audit-reserve-exhausted clock admitted')
    need(private.activation_index([dict(trigger_grain_ids=[]), dict(trigger_grain_ids=[182])]) == 1,
         'pending activation keeps unchanged STOP policy')
    return dict(passed=True, zero_transport_steps=0, zero_native_solver_calls=0, mocked_rejections=rejected,
        unchanged_numerical_physical_selector_evaluator_code_objects=True, private_global_graph_isolated=True,
        current_budget_keyword_defaults_exact=True, no_default_dispatch=True,
        numerical_window_ordinal=4, human_review_of_exact_numbers_not_claimed=True)


private.authorize, private.controls = authorize, controls
for _name in REUSED:
    globals()[_name] = getattr(private, _name)


if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else None
    if action == 'controls' and len(sys.argv) == 2:
        print(json.dumps(controls(), sort_keys=True), flush=True)
    elif action == 'authorize' and len(sys.argv) == 3:
        authorize(sys.argv[2])
    elif action in ('run', 'supervise', 'evaluate') and len(sys.argv) == 2:
        getattr(private, action)()
    else:
        raise SystemExit('Explicit controls, authorize EXACT_PERMISSION_SHA, or separately authorized supervise/run/evaluate only; no default dispatch.')
