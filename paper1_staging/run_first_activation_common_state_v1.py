"""Unlaunched administration for one prospectively selected first actual selector activation.

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
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'paper1_staging'))
import run_support_common_state_v3 as frozen

SELF = Path(__file__).resolve()
FROZEN_SHA = '229589bcf20dec6c2c1bbd92ff7d5974f12c6f16a2ce18dc85826116717ea867'
PREPARATION_NAME = 'prepare_first_activation_common_state_v1'
DESIGNS = ROOT / 'paper1_designs/first_activation_common_state_20261018'
OUT = ROOT / 'paper1_runs/first_activation_common_state_20261018'
PLAN, AUTH = DESIGNS / 'design_01.json', DESIGNS / 'authorization_01.json'
PHYSICAL, PROPOSAL = DESIGNS / 'physical_cases_01.json', DESIGNS / 'proposal_01.json'
APPROVAL = DESIGNS / 'human_approval_01/results.json'
PREPARED = DESIGNS / 'preparation_01/results.json'
PREPARATION_EXIT = DESIGNS / 'preparation_execution_receipt_01/results.json'
DEADLINE = '2026-10-18T02:59:34.905691+00:00'
STEP_CAP, CALL_CAP = 30908, 17
LOCAL_STEPS, LOCAL_CALLS = (4500, 9000), (2, 3)
PRIOR_STEPS, PRIOR_CALLS = 10283231, 2159
CASE_STEPS, CASE_CALLS = 11300000, 2400
SHARED_STEPS, SHARED_CALLS = 5632768, 1217
PRIOR_SHARED_STEPS, PRIOR_SHARED_CALLS = 4635319, 989
PRIOR_DIAGNOSTIC_STEPS, PRIOR_DIAGNOSTIC_CALLS = 116534, 51
TOTAL_DIAGNOSTIC_STEPS, TOTAL_DIAGNOSTIC_CALLS = 147442, 68
PRIOR_NUMERICAL_WINDOWS, MAXIMUM_TOTAL_NUMERICAL_WINDOWS = 4, 5
BASELINE_PINS = {
    ROOT / 'paper1_runs/first_persistent_common_state_20261017/final_execution_receipt_01/results.json': '9e63a1abc10801cbd566e61438d1c704c6918fbb7d591f2cfd5d93af94107db3',
    ROOT / 'paper1_designs/full_horizon_timecap_20261016/design_01.json': 'aead45d9b3983c928f9f5eabd0c77c21c23084ff7e9d9c185c520ed59380f41f',
    ROOT / 'paper1_runs/full_horizon_timecap_20261016/final_execution_receipt_01/results.json': 'd23b764b5d5c3769ee2607aca7c0107e424352641306b6575a9b2522f943bf1f',
    ROOT / 'paper1_runs/full_horizon_timecap_20261016/comparison_fine/results.json': '15d48be2710368ad8499a2998b53f0c31c085b6f1880116fc317d47b1ad048d7',
    ROOT / 'paper1_runs/support_common_state_20261017_v2/final_execution_receipt_01/results.json': 'd34c607f6278235173470f1778826e4320320b48cd565f9eb975d31d551511cb',
    ROOT / 'paper1_evaluations/support_exact_window_context_20261017/execution_receipt_01/results.json': '83a32c06e079cf63ad1bd6f47985c5d43b85cd442d3ebb1f7afc0059dbc85015',
}


def need(value, message):
    if not value:
        raise RuntimeError('First-activation administration: ' + message)


def activation_protocol():
    return dict(first_accepted_trigger_restart_required=True,
        first_trigger_must_be_in_accepted_rows=True, first_trigger_index_must_be_positive=True,
        initial_activation_stops=True, pending_activation_stops=True,
        first_active_record_maximum_rows=4096, extra_active_steps_per_branch_maximum=8192,
        extra_active_calls_per_branch=3, exact_serial_split_original_rows_and_FULL_checkpoint=True,
        trigger_required_in_split_successor=True, restore_original_accepted_output_after_probes=True,
        require_local_grain15_positive_normal_reaction=True,
        saved_accepted_cycle_prepare_final_inner_association_required=True,
        unknown_loading_coverage_stops=True, positive_reaction_predicate='lambda_n > 0',
        later_easier_record_selection_authorized=False, implicit_active_restart_waiver=False)


def active_plan(record, label):
    n = len(record['rows'])
    journal = record['onset_timecap']['journal']
    j = next((i for i, value in enumerate(journal) if value['trigger_grain_ids']), None)
    need(j is not None and 0 < j < n <= 4096
         and record['result']['checkpoint']['state']['pending_trial'] is None,
         'FIRST accepted active record has positive exact split and no pending trial')
    return dict(original_production_label=label, original_row_count=n, first_trigger_index=j,
        discarded_diagnostic_steps=2*n, extra_integration_calls=3)


def verify_active(record, serial, left, right, label):
    plan = active_plan(record, label)
    n, j = plan['original_row_count'], plan['first_trigger_index']
    need(len(serial['rows']) == n and len(left['rows']) == j and len(right['rows']) == n-j
         and private.api.digest(serial['rows']) == private.api.digest(left['rows'] + right['rows'])
             == private.api.digest(record['rows'])
         and private.api.digest(serial['result']['checkpoint']) == private.api.digest(right['result']['checkpoint'])
             == private.api.digest(record['result']['checkpoint'])
         and any(value['trigger_grain_ids'] for value in right['onset_timecap']['journal'][:len(right['rows'])]),
         'first actual active serial/split exactly reproduces original rows and FULL checkpoint/history; split successor triggers')
    return plan


def evidence_parent(index, label, active):
    if label == f'branch{index}_split_b':
        return f'branch{index}_split_a'
    if label == f'branch{index}_active_split_b':
        return f'branch{index}_active_split_a'
    if label in (f'branch{index}_active_serial', f'branch{index}_active_split_a'):
        original_label = active['original_production_label']
        number = int(original_label.rsplit('_', 1)[1])
        return f'branch{index}_local_{number-1:05d}' if number > 1 else None
    if '_local_' in label:
        number = int(label.rsplit('_', 1)[1])
        return f'branch{index}_local_{number-1:05d}' if number > 1 else None
    need(label in (f'branch{index}_serial', f'branch{index}_split_a'), 'known exact diagnostic label')
    return None


def coverage_from_record(record):
    """Saved operands only; a coverage check, never a new mechanical solve."""
    rows = record['rows']
    journal = record['onset_timecap']['journal']
    trace = record['contact_trial_trace']
    cycles, counts = trace['cycle_guard_trials'], trace['trial_inner_counts']
    prepared = record['normal_gap_operand_policy']['prepare_calls']
    need(record['result']['rejected'] == 0
         and record['result']['checkpoint']['state']['pending_trial'] is None
         and len(rows) == len(journal) == len(cycles) == len(counts) == len(prepared),
         'complete zero-rejection, no-pending accepted row/outer-cycle/prepare/journal association')
    first_selector = first_bearing = None
    a = record['spec']['config']['prolate_semiaxes_m'][0]
    for index, row in enumerate(rows):
        entry, cycle, call = journal[index], cycles[index], prepared[index]
        inner = cycle['records']
        need(cycle['trial_index'] == call['index'] == index
             and len(inner) == counts[index] > 0
             and all(value['inner_index'] == i for i, value in enumerate(inner))
             and inner[-1]['map_output'] == row['velocity_generalized']
             and [int(c[0]) for c in call['contacts']] == row['active_contact_ids'],
             'complete original outer/inner ordering and LAST map output binds accepted velocity/contact order')
        reactions = inner[-1]['health']['reactions']
        need(len(reactions) == 3*len(call['contacts']), 'last accepted inner reaction vector has native contact ordering')
        if first_selector is None and entry['trigger_grain_ids']:
            q = entry['velocity_generalized']
            witnesses = []
            for grain, gap, normal, lever in entry['near']:
                if grain in entry['trigger_grain_ids']:
                    cross = [lever[1]*normal[2]-lever[2]*normal[1],
                             lever[2]*normal[0]-lever[0]*normal[2],
                             lever[0]*normal[1]-lever[1]*normal[0]]
                    closing = -(sum(normal[k]*q[k] for k in range(3))
                                + sum(cross[k]*q[k+3] for k in range(3))/a)
                    witnesses.append(dict(grain_id=int(grain), gap_m=gap, normal=normal, lever=lever,
                        derived_closing_m_s=closing))
            need(sorted(x['grain_id'] for x in witnesses) == sorted(entry['trigger_grain_ids']),
                 'first selector witness retains every actual trigger grain/operand')
            first_selector = dict(accepted_row_index=index, old_time_s=entry['time_s'],
                accepted_time_s=row['time_s'], trigger_grain_ids=entry['trigger_grain_ids'],
                old_velocity_generalized=q, body_semimajor_axis_m=a, witnesses=witnesses,
                closing_is_derived_saved_operand_diagnostic_only=True)
        if first_bearing is None:
            for k, contact in enumerate(call['contacts']):
                if int(contact[0]) == 15 and reactions[3*k] > 0:
                    first_bearing = dict(accepted_row_index=index, old_time_s=entry['time_s'],
                        accepted_time_s=row['time_s'], grain_id=15, normal_reaction_N=reactions[3*k],
                        raw_gap_m=contact[1], last_inner_index=inner[-1]['inner_index'],
                        predicate='lambda_n > 0', provenance='last accepted cycle inner health.reactions in native prepare contact order')
                    break
    return dict(first_selector=first_selector, first_positive_normal_reaction_grain15=first_bearing,
        association_verified=True, new_physical_calls=0)


def combine_coverage(previous, current, label):
    need(current['association_verified'] is True, 'unknown loading coverage stops')
    for key in ('first_selector', 'first_positive_normal_reaction_grain15'):
        if previous.get(key) is None and current[key] is not None:
            previous[key] = dict(label=label, **current[key])
    return previous


def approval_scope():
    return dict(first_activation_common_state_diagnostic_authorized=True,
        supplemental_diagnostic_allocation_authorized=True,
        maximum_new_saved_steps=STEP_CAP, maximum_new_integration_calls=CALL_CAP,
        maximum_discarded_diagnostic_steps=TOTAL_DIAGNOSTIC_STEPS,
        maximum_diagnostic_integration_calls=TOTAL_DIAGNOSTIC_CALLS,
        existing_case_saved_step_cap=CASE_STEPS, existing_case_call_cap=CASE_CALLS,
        original_shared_saved_step_cap=SHARED_STEPS, original_shared_call_cap=SHARED_CALLS,
        prior_numerical_windows=PRIOR_NUMERICAL_WINDOWS,
        maximum_total_numerical_windows=MAXIMUM_TOTAL_NUMERICAL_WINDOWS,
        additional_independent_numerical_windows=1, maximum_window_minutes=60,
        original_shared_end_utc=DEADLINE)


def validate_approval(approval, proposal_sha):
    need(approval.get('passed') is True and approval.get('proposal_sha256') == proposal_sha,
         'NEW passing human approval binds this exact prospective proposal')
    need(all(isinstance(approval.get(key), str) and approval[key].strip()
             for key in ('human_reply', 'question_reference')),
         'verbatim NEW direct human reply and trusted question provenance required')
    need(approval.get('human_reviewed_exact_proposal') is True,
         'this allocation needs a NEW explicit reply to the concrete reviewed proposal')
    seal = approval.get('preparation_execution_receipt_sha256')
    need(isinstance(seal, str) and len(seal) == 64 and all(x in '0123456789abcdef' for x in seal),
         'closed prepared evidence explicitly pinned')
    scope = approval.get('scope', {})
    need(all(type(scope.get(key)) is type(value) and scope[key] == value
             for key, value in approval_scope().items()), 'exact fifth independent window and allocations')
    return True


class LazyPreparation:
    __file__ = str(ROOT / 'paper1_staging' / (PREPARATION_NAME + '.py'))

    def __getattr__(self, name):
        return getattr(importlib.import_module(PREPARATION_NAME), name)


def build_private_namespace(source):
    """Clone the complete original module function graph, retaining code objects."""
    private = ModuleType('_paper1_first_activation_common_state_private')
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
    private.private = private
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
    persistent = private.s.fields.sealed(ROOT / 'paper1_runs/first_persistent_common_state_20261017/final_execution_receipt_01/results.json')
    need(persistent['passed'] and persistent['core_result_admitted'] is False, 'fourth numerical window closed without admission')
    a, b, c = full['ledger'], local['ledger'], persistent['ledger']
    need(c['ledger_authenticated'] and not c['admission_failures']
         and c['known_unaccepted_saved_steps'] == c['unknown_reserved_steps_upper_bound'] == 0, 'latest closed diagnostic has no unresolved work')
    need(b['ledger_authenticated'] is True and not b['admission_failures']
         and a['known_unaccepted_saved_steps'] == a['unknown_reserved_steps_upper_bound'] == 0
         and b['known_unaccepted_saved_steps'] == b['unknown_reserved_steps_upper_bound'] == 0,
         'no unresolved prior work')
    totals = (old['baseline']['conservative_prospective_baseline_saved_steps'] + a['saved_steps'] + b['accepted_diagnostic_steps'] + c['accepted_diagnostic_steps'],
              old['baseline']['conservative_prospective_baseline_integration_calls'] + a['calls'] + b['conservative_call_charges'] + c['conservative_call_charges'],
              a['saved_steps'] + b['accepted_diagnostic_steps'] + c['accepted_diagnostic_steps'], a['calls'] + b['conservative_call_charges'] + c['conservative_call_charges'],
              a['diagnostic_steps'] + b['accepted_diagnostic_steps'] + c['accepted_diagnostic_steps'], a['diagnostic_calls'] + b['conservative_call_charges'] + c['conservative_call_charges'])
    need(totals == (PRIOR_STEPS, PRIOR_CALLS, PRIOR_SHARED_STEPS, PRIOR_SHARED_CALLS,
                   PRIOR_DIAGNOSTIC_STEPS, PRIOR_DIAGNOSTIC_CALLS), 'exact latest cumulative/shared/diagnostic baselines')
    launches = [row['launch'] for row in full['identity_inspections_after_hashing']]
    launches += list(local['exact_launches'].values()) + list(persistent['exact_launches'].values()) + [analysis['exact_analysis_launch']]
    for launch in launches:
        need(private.inspect(launch)['retired'], 'earlier exact birth/full command remains retired')
    return totals


def authorize(expected_permission_sha256):
    """Root administration only; creates no human reply and never launches."""
    private.s.environment()
    need(isinstance(expected_permission_sha256, str) and len(expected_permission_sha256) == 64
         and all(x in '0123456789abcdef' for x in expected_permission_sha256), 'exact caller-pinned permission SHA')
    need(not PLAN.exists() and not AUTH.exists() and not OUT.exists(), 'fresh create-only independent fifth window')
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
         and proposal['status'] == 'PREPARED_AWAITING_EXPLICIT_HUMAN_APPROVAL'
         and proposal['original_shared_end_utc'] == DEADLINE
         and proposal['physics_changes'] == proposal['accuracy_gate_changes']
             == proposal['contact_route_changes'] == proposal['selector_policy_changes'] == []
         and proposal['required_human_approval_scope'] == approval_scope(), 'prospective exact human-reviewed administrative scope')
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
         and proposal['local_stop_s'] == physical['local_stop_s'] == physical['seed_time_s'] + .0025
         and proposal['factors'] == [.0625, .03125]
         and physical['seed_time_s'] == .15280694670867345
         and policy == activation_protocol(),
         'fixed same-FULL2.5ms pair and mandatory first accepted activation qualification')
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
        permission_receipt_sha256=expected_permission_sha256, exact_allocations_agent_selected=False,
        human_reviewed_exact_proposal=True, original_shared_end_utc=DEADLINE,
        prior_numerical_windows=4, maximum_total_numerical_windows=5, independent_numerical_window_ordinal=5,
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
        permission_receipt_sha256=expected_permission_sha256, human_reviewed_exact_proposal=True,
        new_transport_steps=0, new_native_solver_calls=0, original_shared_end_utc=DEADLINE, utc=private.s.utc()))
    print(json.dumps(dict(authorized=True, design_sha256=private.sha(PLAN), numerical_cutoff_utc=cutoff.isoformat(),
                         end_utc=end.isoformat(), human_reviewed_exact_proposal=True)), flush=True)


def invoke(ctx, transaction, p, physical, case, branch, label, cap, before, prefix, previous):
    authority(True)
    need(time.time() + 90 < datetime.fromisoformat(p['simulation_cutoff_utc']).timestamp(),
         'native45s plus complete audit/retirement reserve before numerical cutoff')
    current = ledger()
    need(len(current['labels']) == current['conservative_call_charges']
         and not current['admission_failures']
         and current['accepted_diagnostic_steps'] + cap <= STEP_CAP
         and current['conservative_call_charges'] < CALL_CAP, 'one unverified record and bounded next reservation')
    budget_guard(current['accepted_diagnostic_steps'] + cap, current['conservative_call_charges'] + 1)
    index = current['conservative_call_charges'] + 1
    reservation = dict(index=index, branch=branch, label=label, kind='discarded_diagnostic',
        maximum_saved_steps=cap, input_checkpoint_sha256=api.digest(before), previous_result_sha256=previous,
        design_sha256=sha(PLAN), utc=s.utc())
    reserve_path = OUT / 'reservations' / f'{index:03d}.json'
    commit(reserve_path, reservation)
    record, updated, row = transaction(ctx, p, physical, case, label, cap, before, prefix, previous)
    folder = OUT / 'records' / label
    restored, state = ctx.job.codec.read_record(folder / 'call.json.xz', sha(PHYSICAL), prefix)
    need(api.digest(restored) == api.digest(record) and state.reference() == updated.reference(),
         'lossless original full raw/history reconstruction before next dispatch')
    count = len(record['rows'])
    need(0 < count <= cap and record['result']['rejected'] == 0, 'bounded original zero-rejection increment')
    gate = s.fields.sealed(folder / 'guard_completion/results.json')
    extra = s.fields.sealed(folder / 'timecap_guard/results.json')
    api.verify_mapping(gate['artifacts'])
    need(gate['passed'] and extra['passed'] and gate['full_checkpoint_sha256'] == api.digest(record['result']['checkpoint'])
         and extra['raw_sha256'] == sha(folder / 'call.json.xz')
         and extra['original_physical_guard_sha256'] == sha(folder / 'guard_completion/results.json'),
         'unchanged independent physical and selector gates bind this raw/full checkpoint')
    seal(OUT / 'admissions' / f'{index:03d}', dict(passed=True, label=label, branch=branch,
        saved_steps=count, reservation_sha256=sha(reserve_path), full_checkpoint_sha256=api.digest(record['result']['checkpoint']),
        raw_sha256=sha(folder / 'call.json.xz'), physical_guard_sha256=sha(folder / 'guard_completion/results.json'),
        timecap_guard_sha256=sha(folder / 'timecap_guard/results.json'), utc=s.utc()))
    print('SUPPORT_DIAGNOSTIC_ACCEPTED', index, label, count, record['result']['checkpoint']['state']['t'], flush=True)
    journal = record['onset_timecap']['journal']
    first = activation_index(journal)
    pending_trigger = any(x['trigger_grain_ids'] for x in journal[count:])
    initial_trigger = '_local_' not in label and '_active_' not in label and first is not None
    if pending_trigger or initial_trigger:
        stopped = OUT / 'activation_stop_01'
        store_checkpoint(stopped / 'checkpoint.json', record['result']['checkpoint'], sha(PHYSICAL))
        commit(stopped / 'prefix.json', updated.reference())
        seal(stopped, dict(passed=False, label=label, first_trigger_index=first,
            pending_witness=pending_trigger, initial_restart_activation=initial_trigger,
            raw_sha256=sha(folder / 'call.json.xz'), completed_output_preserved=True,
            completed_saved_steps_charged=count, successor_dispatch_stopped=True,
            implicit_active_restart_waiver=False, full_path_accuracy_passed=False,
            core_result_admitted=False, utc=s.utc()))
        raise RuntimeError('Initial or pending activation stops; authenticated completed output retained and charged')
    return record, updated, row

def run():
    p = authority(True)
    expected_design_sha = sha(PLAN)
    registration_deadline = min(time.time() + 5, datetime.fromisoformat(p['simulation_cutoff_utc']).timestamp())
    while not (OUT / 'controller_01/worker_launch.json').exists() and time.time() < registration_deadline:
        time.sleep(.02)
    expected = read(OUT / 'controller_01/worker_launch.json')
    me = psutil.Process()
    need(expected['pid'] == me.pid and expected['created'] == me.create_time()
         and expected['command'] == me.cmdline(), 'only exact supervisor-owned numerical worker')
    me.cpu_affinity([14])
    commit(OUT / 'worker_launch.json', {**expected, 'utc': s.utc()})
    ctx, transaction = context()
    physical = read(PHYSICAL)
    branches, error, latest, finalization_failures, worker_passed = [], None, {}, [], False
    try:
        s.q.reference.JOB.parent.b.old.parent.configure()
        s.q.kernel.warm()
        s.q.kernel.reset()
        for index, case in enumerate(physical['cases']):
            initial, _ = preparation.seed_for(index)
            serial, _, _ = invoke(ctx, transaction, p, physical, case, index, f'branch{index}_serial',
                                  256, copy.deepcopy(initial), None, None)
            left, left_prefix, _ = invoke(ctx, transaction, p, physical, case, index, f'branch{index}_split_a',
                                         128, copy.deepcopy(initial), None, None)
            right, _, _ = invoke(ctx, transaction, p, physical, case, index, f'branch{index}_split_b',
                                 128, left['result']['checkpoint'], left_prefix,
                                 sha(OUT / 'records' / f'branch{index}_split_a/results.json'))
            need(len(serial['rows']) == 256 and len(left['rows']) == len(right['rows']) == 128
                 and api.digest(serial['rows']) == api.digest(left['rows'] + right['rows'])
                 and api.digest(serial['result']['checkpoint']) == api.digest(right['result']['checkpoint']),
                 'exact fresh late-seed256 versus128+128 rows and FULL checkpoint/history')
            seal(OUT / f'restart_branch{index}', dict(passed=True, branch=index,
                labels=dict(serial=f'branch{index}_serial', split_a=f'branch{index}_split_a', split_b=f'branch{index}_split_b'),
                discarded_diagnostic_steps=512, exact_rows=True, exact_full_checkpoint_history=True,
                original_seed_full_checkpoint_sha256=api.digest(initial), utc=s.utc()))
            del serial, left, right, left_prefix
            before, prefix, previous, labels, steps = copy.deepcopy(initial), None, None, [], 0
            active_qualified = False
            coverage = {}
            for number in range(1, LOCAL_CALLS[index] + 1):
                cap = min(5000 if active_qualified else 4096, LOCAL_STEPS[index] - steps)
                need(cap > 0, 'positive prospective branch remainder')
                label = f'branch{index}_local_{number:05d}'
                original_before, original_prefix, original_previous = before, prefix, previous
                record, prefix, _ = invoke(ctx, transaction, p, physical, case, index, label, cap, before, prefix, previous)
                steps += len(record['rows'])
                before = record['result']['checkpoint']
                labels.append(label)
                previous = sha(OUT / 'records' / label / 'results.json')
                latest[index] = (before, prefix)
                combine_coverage(coverage, coverage_from_record(record), label)
                triggers = [i for i, value in enumerate(record['onset_timecap']['journal'][:len(record['rows'])])
                            if value['trigger_grain_ids']]
                if triggers and not active_qualified:
                    # The admitted original path is authoritative and already in latest.
                    # Discard every probe; never let a probe become the local ancestor.
                    plan = active_plan(record, label)
                    n, j = plan['original_row_count'], plan['first_trigger_index']
                    probe_labels = {key: f'branch{index}_active_{key}' for key in ('serial', 'split_a', 'split_b')}
                    replay, _, _ = invoke(ctx, transaction, p, physical, case, index, probe_labels['serial'],
                        n, copy.deepcopy(original_before), original_prefix, original_previous)
                    a, aprefix, _ = invoke(ctx, transaction, p, physical, case, index, probe_labels['split_a'],
                        j, copy.deepcopy(original_before), original_prefix, original_previous)
                    b, _, _ = invoke(ctx, transaction, p, physical, case, index, probe_labels['split_b'],
                        n-j, a['result']['checkpoint'], aprefix,
                        sha(OUT / 'records' / probe_labels['split_a'] / 'results.json'))
                    verified = verify_active(record, replay, a, b, label)
                    seal(OUT / f'restart_active_branch{index}', dict(passed=True, branch=index,
                        **verified, labels=probe_labels, exact_rows=True, exact_full_checkpoint_history=True,
                        input_checkpoint_sha256=api.digest(original_before), previous_result_sha256=original_previous,
                        original_result_sha256=sha(OUT / 'records' / label / 'results.json'),
                        original_output_checkpoint_sha256=api.digest(before),
                        original_output_prefix_sha256=api.digest(prefix.reference()),
                        trigger_required_in_split_successor=True, original_accepted_output_restored=True, utc=s.utc()))
                    active_qualified = True
                    del replay, a, b, aprefix
                if record['result']['status'] in ('present_at_horizon', 'full_window_exit'):
                    break
            complete = record['result']['status'] in ('present_at_horizon', 'full_window_exit')
            need(complete and active_qualified and coverage.get('first_positive_normal_reaction_grain15') is not None,
                 'complete local interval, FIRST active restart and actual accepted positive grain15 reaction coverage')
            folder = OUT / f'recoverable_branch{index}'
            store_checkpoint(folder / 'checkpoint.json', before, sha(PHYSICAL))
            commit(folder / 'prefix.json', prefix.reference())
            branches.append(dict(branch=index, labels=labels, saved_steps=steps,
                terminal_status=record['result']['status'], terminal_time_s=before['state']['t'],
                full_checkpoint_sha256=api.digest(before), reset_from_original_common_seed=True,
                first_actual_active_restart_qualified=True, loading_coverage=coverage))
    except Exception as exc:
        error = dict(message=repr(exc), traceback=traceback.format_exc())
        print(json.dumps(error), flush=True)
    finally:
        for index, (checkpoint, prefix) in latest.items():
            folder = OUT / f'recoverable_branch{index}'
            try:
                if not folder.exists():
                    store_checkpoint(folder / 'checkpoint.json', checkpoint, p['physical_design_sha256'])
                    commit(folder / 'prefix.json', prefix.reference())
            except Exception as exc:
                finalization_failures.append(dict(kind='last_checkpoint_materialization', error=repr(exc)))
        try:
            authority(False)
        except Exception as exc:
            finalization_failures.append(dict(kind='final_source_input_resource_gate', error=repr(exc)))
        try:
            counts = ledger()
        except Exception as exc:
            counts = failed_ledger(exc)
            finalization_failures.append(dict(kind='ledger_authentication', error=repr(exc)))
        need(datetime.now(timezone.utc) < datetime.fromisoformat(p['end_utc'])
             <= datetime.fromisoformat(DEADLINE), 'worker finalization remains within held original deadline')
        worker_passed = (error is None and not finalization_failures and len(branches) == 2
            and counts['ledger_authenticated'] and not counts['admission_failures']
            and counts['known_unaccepted_saved_steps'] == counts['unknown_reserved_steps_upper_bound'] == 0)
        # Raw chains remain authoritative even if cutoff interrupts checkpoint materialization.
        seal(OUT / 'worker_disposition_01', dict(passed=worker_passed,
            error=error, finalization_failures=finalization_failures,
            native_complete=worker_passed and len(branches) == 2, branches=branches, ledger=counts,
            accepted_physical_steps=0, all_saved_steps_discarded_diagnostics=True,
            full_path_accuracy_passed=False, core_result_admitted=False, design_sha256=expected_design_sha,
            expected_source_files=p['source_files'], observed_control_files=control_hash_snapshot(), utc=s.utc()))
    if not worker_passed:
        raise SystemExit(2)

def evaluate():
    """Post-worker local evidence/metrics only; no original full-path gate call."""
    p = authority(False)
    me = psutil.Process()
    me.cpu_affinity([14])
    registration_deadline = min(time.time() + 5, datetime.fromisoformat(p['end_utc']).timestamp())
    while not (OUT / 'evaluator_01/launch.json').exists() and time.time() < registration_deadline:
        time.sleep(.02)
    expected = read(OUT / 'evaluator_01/launch.json')
    need(expected['pid'] == me.pid and expected['created'] == me.create_time()
         and expected['command'] == me.cmdline(), 'only exact supervisor-owned post-exit evaluator')
    exit_path = OUT / 'controller_01/exit.json'
    exited = read(exit_path)
    need(exited['returncode'] == 0 and exited['forced'] is False
         and inspect(read(OUT / 'controller_01/worker_launch.json'))['retired'], 'numerical worker actually exited0 and retired')
    api.verify_mapping(exited['logs'])
    final = s.fields.sealed(OUT / 'worker_disposition_01/results.json')
    counts = ledger()
    need(final['passed'] and final['native_complete'] and final['ledger'] == counts,
         'complete two-branch all-diagnostic ledger without unresolved work')
    physical = read(PHYSICAL)
    ctx, _ = context(False)
    decoded, prefixes, artifacts, local = {}, {}, {}, [[], []]
    for reservation in counts['reservations']:
        authority(False)
        index, label = reservation['branch'], reservation['label']
        case = physical['cases'][index]
        initial, _ = preparation.seed_for(index)
        active = s.fields.sealed(OUT / f'restart_active_branch{index}/results.json')
        parent_label = evidence_parent(index, label, active)
        before = initial if parent_label is None else decoded[parent_label]['result']['checkpoint']
        prefix = None if parent_label is None else prefixes[parent_label]
        previous = None if parent_label is None else sha(OUT / 'records' / parent_label / 'results.json')
        need(reservation['input_checkpoint_sha256'] == api.digest(before)
             and reservation['previous_result_sha256'] == previous, 'independent exact branch FULL seed/ancestry')
        folder = OUT / 'records' / label
        guard, policy = [s.fields.sealed(folder / name / 'results.json') for name in ('guard_completion', 'timecap_guard')]
        need(guard['passed'] and policy['passed'], 'unchanged passed independent record gates')
        api.verify_mapping(guard['artifacts'])
        record, updated = ctx.job.codec.read_record(folder / 'call.json.xz', sha(PHYSICAL), prefix)
        need(record['spec'] == case['spec'] and record['input_checkpoint_sha256'] == api.digest(before)
             and guard['full_checkpoint_sha256'] == api.digest(record['result']['checkpoint'])
             and len(record['rows']) == guard['saved_steps'] <= reservation['maximum_saved_steps'],
             'complete original raw/checkpoint and work associations')
        receipt = DOC.read(folder / 'results.json')
        need(read(folder / 'completion.json')['results_sha256'] == sha(folder / 'results.json')
             and receipt['passed'] and receipt['summary']['passed']
             and receipt['transport_design_sha256'] == sha(PLAN)
             and receipt['physical_design_sha256'] == sha(PHYSICAL)
             and receipt['input_checkpoint_sha256'] == api.digest(before)
             and receipt['previous_receipt_sha256'] == previous
             and receipt['output_checkpoint_sha256'] == api.digest(record['result']['checkpoint'])
             and receipt['new_saved_steps'] == len(record['rows'])
             and receipt['role'] == 'restart_diagnostic'
             and receipt['original_binding'] == ctx.job.binding(physical, case)
             and receipt['numerical_policy_contract_sha256'] == record['numerical_policy_contract_sha256'] == sha(ctx.job.WORK),
             'original complete physics receipt binds identical design, policy, seed and predecessor')
        api.verify_mapping(receipt['artifacts'])
        admission = s.fields.sealed(OUT / 'admissions' / f'{reservation["index"]:03d}' / 'results.json')
        need(admission['raw_sha256'] == sha(folder / 'call.json.xz')
             and admission['full_checkpoint_sha256'] == api.digest(record['result']['checkpoint'])
             and admission['physical_guard_sha256'] == sha(folder / 'guard_completion/results.json')
             and admission['timecap_guard_sha256'] == sha(folder / 'timecap_guard/results.json')
             and policy['raw_sha256'] == sha(folder / 'call.json.xz')
             and policy['original_physical_guard_sha256'] == sha(folder / 'guard_completion/results.json'),
             'complete owner admission and original policy/physics gates bind identical raw')
        launch = read(folder / 'launch.json')
        command = launch.get('command', launch.get('argv'))
        worker_launch = read(OUT / 'controller_01/worker_launch.json')
        need(launch['pid'] == worker_launch['pid'] and launch['created'] == worker_launch['created']
             and command == worker_launch['command']
             and launch['transport_design_sha256'] == sha(PLAN)
             and launch['physical_design_sha256'] == sha(PHYSICAL)
             and launch['input_checkpoint_sha256'] == api.digest(before)
             and inspect({**launch, 'command': command})['retired'],
             'actual exact retired numerical producer and full command bind this record')
        geometry = ctx.geometry_for(case)
        physical_check = ctx.baseline.kernel(record, case['spec'], ctx.job.binding(physical, case),
            before, geometry, sha(PHYSICAL), physical['minimum_gap_semantics'])
        guard_check = s.q.guard.audit(record)
        policy_check = policy_auditor.audit(record, before, case, CONFIG, ctx)
        need(physical_check['passed'] and guard_check['passed'] and policy_check['passed'],
             'original independent post-exit physics, guard and fixed-selector replay')
        trace = np.asarray([[r['time_s'], *r['position_m'], *r['orientation'], *r['velocity_generalized']]
                            for r in record['rows']], dtype=np.float64)
        need(np.array_equal(trace, np.load(folder / 'trace.npy', mmap_mode='r', allow_pickle=False)),
             'every original raw row matches the saved trace')
        need(not any(v['trigger_grain_ids'] for v in record['onset_timecap']['journal'][len(record['rows']):]),
             'no pending activation was silently accepted')
        if '_local_' not in label and '_active_' not in label:
            need(activation_index(record['onset_timecap']['journal']) is None, 'initial restart was inactive')
        decoded[label], prefixes[label] = record, updated
        if '_local_' in label:
            local[index].append(label)
        for path in folder.rglob('*'):
            if path.is_file():
                artifacts[str(path)] = sha(path)
    for index in (0, 1):
        serial, left, right = [decoded[f'branch{index}_{name}'] for name in ('serial', 'split_a', 'split_b')]
        restart = s.fields.sealed(OUT / f'restart_branch{index}/results.json')
        need(restart['passed'] and len(serial['rows']) == 256 and len(left['rows']) == len(right['rows']) == 128
             and api.digest(serial['rows']) == api.digest(left['rows'] + right['rows'])
             and api.digest(serial['result']['checkpoint']) == api.digest(right['result']['checkpoint']),
             'post-exit exact256 versus128+128 FULL checkpoint/history restart')
        active = s.fields.sealed(OUT / f'restart_active_branch{index}/results.json')
        first_active = next((label for label in local[index]
            if any(value['trigger_grain_ids'] for value in decoded[label]['onset_timecap']['journal'][:len(decoded[label]['rows'])])), None)
        need(active['passed'] and first_active is not None and active['original_production_label'] == first_active,
             'sealed active restart belongs to FIRST actual accepted local trigger, never a later easier record')
        probe_labels = {key: f'branch{index}_active_{key}' for key in ('serial', 'split_a', 'split_b')}
        verified = verify_active(decoded[first_active], *[decoded[probe_labels[k]] for k in ('serial', 'split_a', 'split_b')], first_active)
        original_reservation = next(r for r in counts['reservations'] if r['label'] == first_active)
        need(active['labels'] == probe_labels and all(active[key] == value for key, value in verified.items())
             and active['input_checkpoint_sha256'] == original_reservation['input_checkpoint_sha256']
             and active['previous_result_sha256'] == original_reservation['previous_result_sha256']
             and active['original_result_sha256'] == sha(OUT / 'records' / first_active / 'results.json')
             and active['original_output_checkpoint_sha256'] == api.digest(decoded[first_active]['result']['checkpoint'])
             and active['original_output_prefix_sha256'] == api.digest(prefixes[first_active].reference())
             and active['original_accepted_output_restored'] is True,
             'complete active receipt original input/output/FULL/history/prefix associations')
        for name in (f'restart_branch{index}', f'restart_active_branch{index}'):
            for filename in ('results.json', 'completion.json'):
                path = OUT / name / filename; artifacts[str(path)] = sha(path)
        branch = final['branches'][index]
        need(branch['branch'] == index and branch['labels'] == local[index]
             and len(local[index]) <= LOCAL_CALLS[index]
             and sum(len(decoded[label]['rows']) for label in local[index]) == branch['saved_steps'] <= LOCAL_STEPS[index],
             'complete ordered local branch calls/steps, diagnostics excluded')
        coverage = {}
        for label in local[index]:
            combine_coverage(coverage, coverage_from_record(decoded[label]), label)
        need(coverage == branch['loading_coverage']
             and coverage.get('first_selector') is not None
             and coverage.get('first_positive_normal_reaction_grain15') is not None,
             'post-exit saved accepted loading/selector association and actual grain15 reaction coverage')
        cp = DOC.read(OUT / f'recoverable_branch{index}/checkpoint.json')
        need(api.digest(cp) == api.digest(decoded[local[index][-1]]['result']['checkpoint']) == branch['full_checkpoint_sha256']
             and read(OUT / f'recoverable_branch{index}/prefix.json') == prefixes[local[index][-1]].reference(),
             'standalone final FULL checkpoint/raw prefix identical to admitted local chain')
    seeds = [preparation.seed_for(i)[0]['state'] for i in (0, 1)]
    need(seeds[0] == seeds[1], 'both branches reset to the identical original FULL physical state/history')
    initial = [[v['t'], *v['x'], *v['p'], *v['q']] for v in seeds]
    terminal = [decoded[labels[-1]]['result'] for labels in local]
    stops = [value['checkpoint']['state']['t'] for value in terminal]
    def blocks(index):
        for label in local[index]:
            yield np.load(OUT / 'records' / label / 'trace.npy', mmap_mode='r', allow_pickle=False)
    spec = physical['cases'][0]['spec']
    cfg = spec['config']
    metrics = s.q.job.path_metrics.metrics(blocks(0), blocks(1), initial[0], initial[1], stops[0], stops[1],
        cfg['prolate_semiaxes_m'][1], cfg['target_mean_interstitial_velocity_m_s'])
    gates = s.q.job.policy.GATES
    need(read(PROPOSAL)['original_accuracy_gates'] == gates, 'original accuracy gates unchanged')
    limits = {key: gates[key] for key in ('whole_position_over_b_max', 'whole_axis_vector_norm_max',
                                        'endpoint_q_over_U_max', 'mean_L1_q_over_U_max')}
    checks = {key: bool(np.isfinite(metrics[key]) and 0 <= metrics[key] <= value) for key, value in limits.items()}
    complete = all(t == physical['local_stop_s'] for t in stops)
    events = terminal[0]['status'] == terminal[1]['status'] and terminal[0]['persistent_contact_observed'] == terminal[1]['persistent_contact_observed']
    def event_time(key, limit):
        a, b = [value[key] for value in terminal]
        return (a is None and b is None) or (a is not None and b is not None and abs(a - b) <= gates[limit])
    dwell = event_time('first_contact_dwell_time_s', 'first_dwell_time_difference_s_max')
    exits = [value['time_s'] if value['status'] == 'full_window_exit' else None for value in terminal]
    exit_times = (exits[0] is None and exits[1] is None) or (exits[0] is not None and exits[1] is not None
        and abs(exits[0] - exits[1]) <= gates['exit_time_difference_s_max'])
    need(metrics['common_start_s'] == physical['seed_time_s'] and metrics['common_stop_s'] == min(stops),
         'original held-velocity metric and absolute nonzero local clock')
    authority(False)
    api.verify_mapping(artifacts)
    seal(OUT / 'evaluation_01', dict(passed=True, local_only=True,
        local_screen_passed=all(checks.values()) and complete and events and dwell and exit_times,
        metrics=metrics, original_numeric_limits=limits, local_numeric_checks=checks,
        complete_declared_local_interval=complete, local_events_equal=events, local_dwell_times_pass=dwell,
        local_exit_times_pass=exit_times, ledger=counts, artifacts=artifacts, source_files=p['source_files'],
        physical_inputs=p['physical_inputs'], design_sha256=sha(PLAN), original_full_path_admission=False,
        full_path_accuracy_passed=False, core_result_admitted=False, publication_case_count_increment=0,
        two_factors_do_not_establish_convergence_order=True, new_native_solver_calls=0, new_transport_steps=0,
        exact_numerical_worker_retired=True, administrative_evaluator_live_when_written=True,
        external_final_exit_log_receipt_required=True, utc=s.utc()))


REUSED = ('context', 'ledger', 'failed_ledger', 'child', 'supervise', 'authority', 'bound',
          'verify_inputs', 'resources', 'bounds', 'budget_guard', 'activation_index', 'inspect',
          'stop_exact', 'recapture_owned_launch', 'store_checkpoint', 'retirement_snapshot', 'control_hash_snapshot')
ADAPTED = ('invoke', 'run', 'evaluate')
HELPERS = ('active_plan', 'verify_active', 'evidence_parent', 'activation_protocol', 'coverage_from_record', 'combine_coverage')


def controls():
    need(private.sha(frozen.__file__) == FROZEN_SHA, 'original frozen runner bytes unchanged')
    for name in REUSED:
        need(getattr(private, name).__code__ is getattr(frozen, name).__code__
             and getattr(private, name).__globals__ is vars(private), 'private unchanged code: ' + name)
    for name in ADAPTED:
        need(getattr(private, name).__code__ is globals()[name].__code__
             and getattr(private, name).__globals__ is vars(private), 'new administrative code privately bound: ' + name)
    need(private.context.__code__ is frozen.context.__code__
         and private.context.__globals__['original'] is frozen.original
         and private.context.__globals__['timecap'] is frozen.timecap,
         'exact original physical/context/fixed-selector transaction graph')
    need(frozen.PRIOR_STEPS == 10184681 and frozen.PRIOR_CALLS == 2125 and frozen.OUT != OUT
         and frozen.SELF != SELF and private.CONFIG == frozen.CONFIG and private.CONFIG is not frozen.CONFIG,
         'old source globals, selector policy and bindings untouched')
    need(private.budget_guard.__kwdefaults__ == dict(prior_case_saved=PRIOR_STEPS, prior_case_calls=PRIOR_CALLS,
         prior_shared_saved=PRIOR_SHARED_STEPS, prior_shared_calls=PRIOR_SHARED_CALLS)
         and frozen.budget_guard.__kwdefaults__['prior_case_saved'] == 10184681,
         'latest all-attempt case/shared keyword defaults')
    need(sum(LOCAL_STEPS) + 1024 + 2*8192 == STEP_CAP
         and sum(LOCAL_CALLS) + 6 + 6 == CALL_CAP
         and PRIOR_DIAGNOSTIC_STEPS + STEP_CAP == TOTAL_DIAGNOSTIC_STEPS
         and PRIOR_DIAGNOSTIC_CALLS + CALL_CAP == TOTAL_DIAGNOSTIC_CALLS,
         'complete local, initial, active-probe and cumulative diagnostic arithmetic')
    private.budget_guard(STEP_CAP, CALL_CAP)
    rejected = 0
    for args, kwargs in (((STEP_CAP+1, CALL_CAP), {}), ((STEP_CAP, CALL_CAP+1), {}),
        ((STEP_CAP, CALL_CAP), dict(prior_case_saved=CASE_STEPS-STEP_CAP+1)),
        ((STEP_CAP, CALL_CAP), dict(prior_case_calls=CASE_CALLS-CALL_CAP+1)),
        ((STEP_CAP, CALL_CAP), dict(prior_shared_saved=SHARED_STEPS-STEP_CAP+1)),
        ((STEP_CAP, CALL_CAP), dict(prior_shared_calls=SHARED_CALLS-CALL_CAP+1))):
        try:
            private.budget_guard(*args, **kwargs)
        except RuntimeError:
            rejected += 1
        else:
            raise RuntimeError('Budget overflow admitted')
    for start in (datetime.fromisoformat(DEADLINE), datetime.fromisoformat(DEADLINE)-timedelta(minutes=30)):
        try:
            private.bounds(start)
        except RuntimeError:
            rejected += 1
        else:
            raise RuntimeError('Expired/no-finalizer-reserve clock admitted')
    return dict(passed=True, zero_transport_steps=0, zero_native_solver_calls=0, mocked_rejections=rejected,
        unchanged_physical_context_fixed_selector_ledger_child_supervisor_code=True,
        first_actual_active_restart_required=True, initial_and_pending_activation_stop=True,
        no_default_dispatch=True, numerical_window_ordinal=5,
        fresh_explicit_human_approval_required=True, publication_case_count_increment=0)


for _name in (*ADAPTED, *HELPERS):
    _function = globals()[_name]
    _clone = FunctionType(_function.__code__, vars(private), _function.__name__, _function.__defaults__, _function.__closure__)
    _clone.__kwdefaults__ = copy.copy(_function.__kwdefaults__)
    setattr(private, _name, _clone)
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
        raise SystemExit('Explicit controls, authorize EXACT_NEW_HUMAN_APPROVAL_SHA, or separately authorized supervise/run/evaluate only; no default dispatch.')
