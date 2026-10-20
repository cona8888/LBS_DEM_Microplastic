"""Create-only prospective local diagnostic package, with ZERO native work.

Import and pure controls create no files, clock or authority. ``prepare`` only
authenticates existing source/seed/retirement receipts, runs caller-pinned
source/mock controls, and writes reviewable proposal/config/preparation files.
It never imports the model, runner, evaluator or execution adapter.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import ast
import copy
import hashlib
import json
import lzma
import math
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT/'paper1_staging'
FAMILY = ROOT/'paper1_designs/contact_event_diagnostic_20261019'
OUT = ROOT/'paper1_runs/contact_event_diagnostic_20261019'
PHYSICAL = FAMILY/'runtime_config_01.json'
PROPOSAL = FAMILY/'proposal_01.json'
PREPARED = FAMILY/'preparation_01/results.json'
SOURCE2 = ROOT/'paper1_designs/contact_event_cap_20261019/source_preparation_02/results.json'
SOURCE2_SHA = 'bc9c2af8e97983287c1c22e4608b9b34369453362c2b214f4e0c2955742158fb'
SEEDS = SOURCE2.parent.parent/'seed_inputs_02'
ORIGINAL_PHYSICAL = ROOT/'paper1_designs/full_horizon_repair_20261018/physical_cases_qualification_01.json'
ORIGINAL_PHYSICAL_SHA = '952e3cf80c1b42ee86bd6402661085af367987c0015fff5c880f2ce4993f244a'
ORIGINAL_PROPOSAL = ORIGINAL_PHYSICAL.parent/'qualification_proposal_01.json'
ORIGINAL_PROPOSAL_SHA = '61d84fb8797fb95b8e4fc7918304d98ae60afc64253eff6d9a26afcc7fd4869d'
OUTER_CLOCK = ORIGINAL_PHYSICAL.parent/'qualification_clock_01/results.json'
CLOSED = ROOT/'paper1_runs/full_horizon_repair_20261018_recovery04/final_execution_receipt_01/results.json'
CLOSED_SHA = '6251eed02f4b3e5c3c4290f28f81cfd97edb364e2fc646866bc2234964045d25'
RUNNER = STAGING/'run_contact_event_diagnostic_v1.py'
RUNNER_TEST = STAGING/'check_contact_event_diagnostic_v1.py'
SELF_TEST = STAGING/'check_prepare_contact_event_diagnostic_v1.py'
PYTHON = Path('C:/Users/wonjuncha-admin/AppData/Local/Programs/Python/Python312/python.exe')
START_S = .15328271968165677
END_S = .15368271968165678
OUTER_START = '2026-10-18T19:43:33.769535+00:00'
OUTER_CUTOFF = '2026-10-23T23:43:33.769535+00:00'
OUTER_END = '2026-10-24T07:43:33.769535+00:00'
PREPARED_LEVELS = ('f0p125', 'f0p0625', 'f0p03125')
LEVELS = ('f0p0625', 'f0p03125')
FACTORS = dict(f0p125=.125, f0p0625=.0625, f0p03125=.03125)
PATH_CAPS = dict(f0p0625=20000, f0p03125=40000)
PATH_RECORD_CAPS = dict(f0p0625=8, f0p03125=14)
BASELINE = dict(case_work_rows=11065576, case_records=2360,
                shared_work_rows=5417664, shared_records=1190,
                diagnostic_work_rows=157450, diagnostic_records=103)
MAX_WORK, MAX_RECORDS, PACKET_CAP, INITIAL_CAP = 140000, 72, 4998, 768
MAX_WINDOW_MINUTES, MAX_NATIVE_MINUTES = 120, 60
NEW_BYTES, COMBINED_OWN_BYTES, TOTAL_BYTES, FREE_BYTES = 512*1024**2, 12*1024**3, 21*1024**3, 20*1024**3
FORBIDDEN = (OUT, FAMILY/'design_01.json', FAMILY/'authorization_01.json',
             FAMILY/'human_approval_01', FAMILY/'window_clock_01')


def need(condition, message):
    if not condition:
        raise ValueError('Contact-event diagnostic preparation: '+message)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(1024*1024): value.update(block)
    return value.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=True).encode()).hexdigest()


def token(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=True, separators=(',', ':')).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sealed(path, expected):
    path = Path(path)
    need(sha(path) == expected, 'caller-pinned receipt bytes: '+str(path))
    completion = read(path.with_name('completion.json'))
    need(completion.get('passed') is True and completion.get('results_sha256') == expected,
         'immutable passed completion: '+str(path))
    value = read(path)
    need(value.get('passed') is True, 'positive source/closure receipt')
    return value


def verify_mapping(mapping):
    need(isinstance(mapping, dict) and mapping, 'nonempty selected immutable map')
    for path, expected in mapping.items():
        need(isinstance(expected, str) and len(expected) == 64 and sha(path) == expected,
             'selected source/input bytes remain pinned: '+str(path))


def approval_scope():
    return dict(independent_contact_event_diagnostic_authorized=True,
        maximum_new_all_work_rows=MAX_WORK, maximum_new_integration_records=MAX_RECORDS,
        maximum_nonadvancing_kernel_invocations=2, maximum_numerical_windows=1,
        maximum_window_minutes=MAX_WINDOW_MINUTES, maximum_native_minutes=MAX_NATIVE_MINUTES,
        maximum_new_retained_bytes=NEW_BYTES, maximum_combined_own_retained_bytes=COMBINED_OWN_BYTES,
        maximum_total_retained_bytes=TOTAL_BYTES, minimum_free_bytes=FREE_BYTES,
        original_shared_end_utc=OUTER_END, original_shared_simulation_cutoff_utc=OUTER_CUTOFF,
        all_new_work_discarded=True, no_full_path_or_core_admission=True)


def diagnostic_contract():
    return dict(independent_common_state_contact_event_diagnostic=True,
        maximum_new_all_trial_work_rows=MAX_WORK, maximum_new_integration_records=MAX_RECORDS,
        maximum_nonadvancing_synthetic_kernel_invocations=2, maximum_numerical_windows=1,
        maximum_subwindow_seconds=7200, maximum_numerical_seconds=3600,
        minimum_audit_retirement_reserve_seconds=3600, original_shared_end_utc=OUTER_END,
        same_original_outer_clock=True, maximum_local_path_all_work_by_level=PATH_CAPS,
        maximum_local_path_records_by_level=PATH_RECORD_CAPS, start_time_s=START_S, stop_time_s=END_S,
        common_FULL_seed=True, old_bits_smoke_fresh_t0_source_compatibility_only=True,
        maximum_native_seconds_per_record=45., maximum_packet_all_work_rows=PACKET_CAP,
        initial_restart_record_work_cap=INITIAL_CAP, workers=1, threads=1, logical_cpu=14,
        maximum_unverified_records=1, new_output_bytes=NEW_BYTES, combined_old_new_output_bytes=COMBINED_OWN_BYTES,
        total_retention_bytes=TOTAL_BYTES, minimum_free_bytes=FREE_BYTES, all_work_discarded_diagnostics=True,
        shadows_rejects_partials_unknown_all_charged=True, exact_initial_C_F1_odd_restarts_required=True,
        first_actual_original_selector_restart_required=True, first_actual_event_cap_reduction_restart_required=True,
        positive_grain15_loading_required=True,
        loading_from_committed_independently_audited_native_branches_only=True,
        late_FULL_exact_record_replay_required=True, unchanged_physics_and_accuracy_gates=True,
        no_full_path_or_core_admission=True, no_old_failed_record_promotion=True,
        no_closed_stage_resumption=True, no_successor_case_dispatch=True)


def runner_metadata(source):
    """Read literal metadata AST only; never import or execute runner code."""
    def value(node, names):
        if isinstance(node, ast.Constant): return node.value
        if isinstance(node, ast.Name) and node.id in names: return names[node.id]
        if isinstance(node, (ast.Tuple, ast.List)): return [value(v,names) for v in node.elts]
        if isinstance(node, ast.Dict): return {value(k,names):value(v,names) for k,v in zip(node.keys,node.values)}
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'dict' and not node.args:
            need(all(k.arg is not None for k in node.keywords), 'no expanded callable metadata')
            return {k.arg:value(k.value,names) for k in node.keywords}
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow)):
            left,right=value(node.left,names),value(node.right,names)
            need(type(left) in (int,float) and type(right) in (int,float), 'numeric metadata expression')
            if isinstance(node.op,ast.Add): return left+right
            if isinstance(node.op,ast.Sub): return left-right
            if isinstance(node.op,ast.Mult): return left*right
            if isinstance(node.op,ast.Div): return left/right
            return left**right
        raise ValueError('Not literal source metadata')
    tree=ast.parse(source); names={}
    for node in tree.body:
        if not isinstance(node,ast.Assign) or len(node.targets)!=1: continue
        try: result=value(node.value,names)
        except (ValueError,KeyError,TypeError): continue
        target=node.targets[0]
        if isinstance(target,ast.Name): names[target.id]=result
        elif isinstance(target,(ast.Tuple,ast.List)) and all(isinstance(t,ast.Name) for t in target.elts):
            need(len(target.elts)==len(result), 'literal metadata tuple length')
            names.update({t.id:v for t,v in zip(target.elts,result)})
    scope=next((node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='approval_scope'),None)
    need(scope is not None and len(scope.body)==1 and isinstance(scope.body[0],ast.Return),
         'pure literal runner approval scope')
    contract=next((node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='diagnostic_contract'),None)
    if contract is not None:
        need(len(contract.body)==1 and isinstance(contract.body[0],ast.Return), 'pure literal runner diagnostic contract')
    return dict(approval_scope=value(scope.body[0].value,names), baseline=names.get('BASELINE'),
                diagnostic_contract=None if contract is None else value(contract.body[0].value,names))


def budget():
    """Success envelopes are conditional hard stops, never work forecasts.

    For each exact proof: serial <=cap AND left+right COMBINED <=cap.
    Rejection/partial/unknown work is charged within these same envelopes.
    """
    rows = dict(local_paths=sum(PATH_CAPS.values()), original32_smokes=2*2*32,
        initial_and_C_F1_odd_restarts=2*4*2*INITIAL_CAP,
        two_distinct_first_event_restarts=2*2*2*PACKET_CAP,
        last_record_FULL_restarts=2*2*PACKET_CAP, conservative_setup_reservation=256)
    records = dict(local_paths=sum(PATH_RECORD_CAPS.values()), original32_smokes=4,
        initial_and_C_F1_odd_restarts=2*4*3, two_distinct_first_event_restarts=2*2*3,
        last_record_FULL_restarts=2*3, separately_charged_two_warm_prelude=1)
    need(sum(rows.values()) == 132648 <= MAX_WORK <= 188631,
         'entire all-work envelope fits remaining standalone budget')
    need(sum(records.values()) == 69 <= MAX_RECORDS <= 113,
         'entire record envelope fits remaining standalone budget')
    return dict(all_work_categories=rows, integration_record_categories=records,
        constructive_success_envelope_work_rows=sum(rows.values()),
        constructive_success_envelope_records=sum(records.values()),
        within_same_caps_unallocated_work_rows=MAX_WORK-sum(rows.values()),
        within_same_caps_unallocated_records=MAX_RECORDS-sum(records.values()),
        maximum_new_all_work_rows=MAX_WORK, maximum_new_integration_records=MAX_RECORDS,
        all_new_work_is_discarded_diagnostic=True, baseline=copy.deepcopy(BASELINE),
        prior_four_attempts=dict(conservative_all_work_rows=752798, records=186,
            admitted_physical_half_rows=493074, admitted_discarded_rows=253158,
            known_unaccepted_rows=1728, unknown_reserved_rows=4838,
            nonadvancing_kernel_invocations=8, numerical_windows=4,
            standalone_all_work_rows=11369, standalone_records=37),
        remaining_before=dict(original_all_work_rows=17247202, original_records=3814,
            standalone_all_work_rows=188631, standalone_records=113,
            nonadvancing_kernel_invocations=14, numerical_windows=7),
        remaining_after_maximum=dict(original_all_work_rows=17247202-MAX_WORK,
            original_records=3814-MAX_RECORDS, standalone_all_work_rows=188631-MAX_WORK,
            standalone_records=113-MAX_RECORDS, nonadvancing_kernel_invocations=12, numerical_windows=6),
        exact_split_cap_rule='right maximum_work_rows = serial cap - ACTUAL charged left work; left+right combined<=serial cap',
        accepted_shadow_rejected_partial_unknown_all_charged=True,
        no_work_refund_from_reconstructed_zero_or_failed_admission=True,
        setup_reservation_is_conservative_not_claimed_actual_transport=True,
        successful_completion_guaranteed=False, native_cost_forecast_claimed=False,
        all_bounds_fail_closed_without_increase=True)


def validate_split_charge(cap, left, right):
    need(all(type(v) is int and v >= 0 for v in (cap, left, right)) and cap > 0,
         'integer nonnegative exact proof charge')
    need(left <= cap and right <= cap-left, 'split COMBINED cap, never a separate full right cap')
    return cap-left


def validate_clock(clock):
    need(clock.get('passed') is True and clock.get('start_utc') == OUTER_START
         and clock.get('simulation_cutoff_utc') == OUTER_CUTOFF and clock.get('end_utc') == OUTER_END
         and clock.get('maximum_shared_hours') == 132 and clock.get('no_automatic_extension') is True,
         'SAME original fixed 132-hour clock, no new origin or extension')


def validate_retirement(closed):
    need(closed.get('closure_complete') is True and closed.get('qualified') is False
         and closed.get('exact_process_retirement_authenticated') is True,
         'closed original negative is preserved, not qualification')
    for key in ('exact_retirement_before', 'exact_retirement_after'):
        rows = closed[key]
        need(isinstance(rows, list) and len(rows) == 4, 'all four exact closed actors retained')
        for row in rows:
            launch, observation = row['launch'], row['inspection']
            need(type(launch['pid']) is int and launch['pid'] > 0 and type(launch['created']) in (int, float)
                 and launch['created'] > 0 and isinstance(launch['command'], list) and launch['command']
                 and all(isinstance(part, str) and part for part in launch['command'])
                 and observation.get('retired') is True and observation.get('no_such_process') is True,
                 'receipt proves BOTH original birth/full command and exact retirement; denial is not retirement')


def fresh_identity_retirement(launch, process_api=None):
    """READ ONLY: exclude only a proven different identity, never deny=>dead.

    The complete expected birth and command come from the authenticated closed
    receipt. No terminate/kill/wait/priority/affinity method is ever called.
    """
    if process_api is None:
        import psutil
        process_api=psutil
    need(type(launch.get('pid')) is int and launch['pid']>0 and type(launch.get('created')) in (int,float)
         and math.isfinite(launch['created']) and launch['created']>0
         and isinstance(launch.get('command'),list) and launch['command']
         and all(isinstance(v,str) and v for v in launch['command']), 'pinned original full process identity')
    try:
        process=process_api.Process(launch['pid'])
    except process_api.NoSuchProcess:
        return dict(retired=True,no_such_process=True,identity_inspection_read_only=True)
    except Exception as exc:
        return dict(retired=False,identity_unresolved=True,error=repr(exc),identity_inspection_read_only=True)
    birth=None;birth_error=None
    try:
        birth=process.create_time()
    except process_api.NoSuchProcess:
        return dict(retired=True,no_such_process=True,identity_inspection_read_only=True)
    except Exception as exc:
        birth_error=repr(exc)
    if type(birth) in (int,float) and math.isfinite(birth) and birth>0 and birth!=launch['created']:
        return dict(retired=True,proven_birth_mismatch=True,observed_created=birth,
                    command_inspected=False,identity_inspection_read_only=True)
    try:
        command=process.cmdline()
    except process_api.NoSuchProcess:
        return dict(retired=True,no_such_process=True,identity_inspection_read_only=True)
    except Exception as exc:
        return dict(retired=False,identity_unresolved=True,observed_created=birth,
                    birth_error=birth_error,command_error=repr(exc),identity_inspection_read_only=True)
    if birth_error is not None or type(birth) not in (int,float) or not math.isfinite(birth) or birth<=0:
        return dict(retired=False,identity_unresolved=True,observed_created=birth,
                    birth_error=birth_error,observed_command=command,identity_inspection_read_only=True)
    if not isinstance(command,list) or not command or not all(isinstance(v,str) and v for v in command):
        return dict(retired=False,identity_unresolved=True,observed_created=birth,
                    observed_command=command,identity_inspection_read_only=True)
    if command!=launch['command']:
        return dict(retired=True,proven_full_command_mismatch=True,observed_created=birth,
                    observed_command=command,command_inspected=True,identity_inspection_read_only=True)
    return dict(retired=False,exact_original_identity_live=True,observed_created=birth,
                observed_command=command,command_inspected=True,identity_inspection_read_only=True)


def fresh_old_retirements(closed, process_api=None):
    validate_retirement(closed)
    observations=[dict(launch=copy.deepcopy(row['launch']),
                       inspection=fresh_identity_retirement(row['launch'],process_api))
                  for row in closed['exact_retirement_after']]
    need(all(row['inspection'].get('retired') is True for row in observations),
         'fresh original identity retirement unresolved/live; access denial never proves retirement')
    return observations


def validate_seed(data, case, summary, preview_digest):
    need(data.get('schema') == 'paper1.inactive-discarded-common-state-input.v1'
         and data.get('dispatch_authorized') is False and data.get('full_horizon_qualification_claimed') is False
         and data.get('source_mock_input_preparation_only') is True,
         'existing input is only source-prepared, not prior authority or qualification')
    need(data['case'] == case and data['physical_input_digest'] == preview_digest
         and data['limits'] == summary['limits'], 'EXACT frozen preview case/spec/binding/limits, no silent rebinding')
    cp = data['checkpoint']; physical = cp['physical_checkpoint']; state = physical['state']
    need(state['t'] == START_S and state['steps'] == 493074 and state.get('pending_trial') is None
         and len(state['history']) == 1972 and physical['state_sha256'] == digest(state) == summary['source_state_sha256'],
         'same authenticated complete physical state/history at real accepted boundary148')
    need(digest(physical) == summary['prospective_original_FULL_sha256']
         and token(cp) == summary['prospective_controller_sha256'], 'frozen prospective FULL/controller byte semantics')
    need(cp['physical_binding'] == case['binding'] and cp['spec_sha256'] == digest(case['spec'])
         and cp['policy_sha256'] == data['limits']['numerical_binding']
         and cp['limits_sha256'] == token(data['limits']), 'exact prepared contract/spec/physical/numerical binding ancestry')
    need(cp['cursor']['phase'] == 'idle' and cp['cursor']['event_cap_witness'] is None
         and cp['cursor']['macro_initial_cap_s'] is None and cp['pending_branches'] == []
         and cp['numeric_ledger'] == dict(all_work_rows=0, accepted_half_rows=0, rejected_trials=0),
         'no old work/controller/pending credit')
    descriptor = cp['history_root']; identity = cp['published_state_token']; frame = cp['frames'][identity]
    need(descriptor == dict(boundary_full_checkpoint_sha256=digest(physical), history_length=1972,
                            history_sha256=token(state['history']))
         and frame['parent'] == token(dict(kind='packet-boundary-original-FULL', sha256=digest(physical)))
         and frame['history_delta'] == [] and frame['contract'] == physical['contract'], 'literal COW root, no invented history')
    header = {k:copy.deepcopy(v) for k,v in state.items() if k != 'history'}
    header.update(history_node=token(descriptor), history_length=1972)
    need(frame['state'] == header and frame['token'] == identity
         == token(dict(kind='logical-state-history-token-not-full-checkpoint', parent_token=frame['parent'],
                       state_header=header, appended_history_rows=[])), 'original physical state mapped exactly to explicit logical token')
    return state


def build_documents(source2, preview, seeds, original_physical, original_proposal, source_files,
                    physical_inputs, evidence_files, outer_clock_sha, historical_evidence_files=None):
    """Pure reviewable documents; no disk writes or authority side effects."""
    need(source2.get('native_physical_or_restart_qualification_completed') is False
         and source2.get('new_force_calls') == source2.get('new_transport_steps') == 0
         and source2.get('numerical_launch_ready') is False, 'source2 is preparation only')
    need(source2.get('old_all_attempts_work_rows') == 752798
         and source2.get('old_all_attempts_integration_records') == 186
         and source2.get('old_known_unaccepted_work_rows') == 1728
         and source2.get('old_unknown_reserved_work_rows') == 4838
         and source2.get('remaining_original_grant_work_rows') == 17247202
         and source2.get('remaining_original_grant_integration_records') == 3814,
         'budget baseline and all accepted/known/unknown charges belong to authenticated closed accounting')
    need(set(seeds) == set(PREPARED_LEVELS), 'all three fixed factors remain source prepared')
    cases = {c['level_id']:c for c in preview['cases']}
    summaries = {c['level_id']:c for c in source2['prospective_seed_checks']}
    need(set(cases) == set(summaries) == set(PREPARED_LEVELS), 'no omitted source preparation or successor cases')
    states = [validate_seed(seeds[level], cases[level], summaries[level], digest(preview)) for level in PREPARED_LEVELS]
    need(all(state == states[0] for state in states) and preview['common_start_time_s'] == START_S
         and preview['common_end_time_s'] == END_S, 'EXACT SAME physical state/history and prospectively fixed interval')
    original_cases = {c['level_id']:c for c in original_physical['cases']}
    old_limits = {c['level_id']:c['limits'] for c in original_proposal['levels']}
    for level in PREPARED_LEVELS:
        need(cases[level]['factor'] == FACTORS[level] and cases[level]['spec']['horizon_s'] == END_S,
             'unchanged original factors and local endpoint')
        expected = copy.deepcopy(original_cases[level]['spec'])
        expected.update(case_id=cases[level]['id'], horizon_s=END_S)
        need(cases[level]['spec'] == expected, 'all physical/spec fields unchanged except already-declared local case ID/horizon')
        need({k:v for k,v in seeds[level]['limits'].items() if k != 'numerical_binding'}
             == {k:v for k,v in old_limits[level].items() if k != 'numerical_binding'}, 'all original accuracy/minimum/retry scales unchanged')
    semantics = original_physical['minimum_gap_semantics']
    need(isinstance(semantics, str) and semantics, 'literal original minimum-gap semantics is mandatory')
    config = dict(schema='paper1.contact-event-local-native-config.v1', cases=copy.deepcopy(preview['cases']),
        minimum_gap_semantics=semantics, common_start_time_s=START_S, common_end_time_s=END_S,
        duration_s=END_S-START_S, source_preview_file=str(SEEDS/'physical_cases_preview.json'),
        source_preview_sha256=source2['prospective_common_state_inputs'][str(SEEDS/'physical_cases_preview.json')],
        inherited_preview_binding=preview['binding'], inherited_preview_physical_input_digest=digest(preview),
        original_gap_semantics_source=str(ORIGINAL_PHYSICAL), original_gap_semantics_source_sha256=ORIGINAL_PHYSICAL_SHA,
        original_preview_seed_contracts_preserved_exactly=True, silently_rebound_seed=False,
        allowed_native_levels=list(LEVELS), source_prepared_undispatched_levels=['f0p125'],
        physical_equation_changes=[], gap_policy_changes=[], route_order_changes=[], accuracy_gate_changes=[],
        dispatch_authorized=False, numerical_launch_ready=False)
    manifest = []
    for level in LEVELS:
        manifest.append(dict(level_id=level, factor=FACTORS[level], limits=copy.deepcopy(seeds[level]['limits']),
            diagnostic_seed_file=str(SEEDS/(level+'.json.xz')),
            diagnostic_seed_sha256=source2['prospective_common_state_inputs'][str(SEEDS/(level+'.json.xz'))],
            maximum_local_path_all_work_rows=PATH_CAPS[level], maximum_local_path_records=PATH_RECORD_CAPS[level],
            inherited_state_sha256=summaries[level]['source_state_sha256'],
            inherited_history_rows=1972, no_core_or_old_prefix_credit=True))
    proposal = dict(schema='paper1.contact-event-local-diagnostic-proposal.v1',
        scientific_question='Can the fixed prospective event cap pass unchanged coupled local/restart/physical gates through the saved first-contact interval?',
        purpose='Bounded discarded common-FULL-state falsifier; source preparation is not scientific validation.',
        required_human_approval_scope=approval_scope(), baseline=copy.deepcopy(BASELINE), budget=budget(),
        diagnostic_contract=diagnostic_contract(), physical_equation_changes=[], gap_policy_changes=[], route_order_changes=[],
        levels=manifest, level_order=list(LEVELS), allowed_native_levels=list(LEVELS),
        source_prepared_undispatched_levels=['f0p125'], future_full_three_factor_qualification_still_required=True,
        original_accuracy_gates=copy.deepcopy(original_proposal['original_accuracy_gates']),
        fixed_local_interval_s=[START_S, END_S], no_smoothing_alignment_time_rewrite_or_gate_change=True,
        source_preparation_sha256=SOURCE2_SHA, closed_original_negative_sha256=CLOSED_SHA,
        original_outer_clock_sha256=outer_clock_sha, original_shared_start_utc=OUTER_START,
        original_shared_simulation_cutoff_utc=OUTER_CUTOFF, original_shared_end_utc=OUTER_END,
        prospective_window=dict(maximum_minutes=MAX_WINDOW_MINUTES, numerical_including_online_audit_minutes=MAX_NATIVE_MINUTES,
            minimum_reserved_postworker_audit_and_closure_minutes=60, start_created=False,
            fixed_clock_required_after_human_approval=True, original_outer_clock_never_reset=True,
            truncation_that_removes_required_postworker_reserve_is_rejected=True,
            dynamic_replay_reserve_only_grows=True,
            dynamic_replay_reserve_arithmetic=dict(
                minimum_tail_seconds=3600, variable_rate_floor_seconds_per_work=.01592,
                variable_rate_observation_multiplier=2, variable_rate_uses_only_records_with_work_at_least=128,
                fixed_small_uses_max_observed_seconds_for_records_with_work_in=[1,127],
                fixed_small_record_multiplier=MAX_RECORDS, source_hash_exit_log_external_margin_seconds=900,
                tail='max(3600, prior highwater, max(.01592, 2*observed_seconds/work for work>=128)*prospective_all_reserved_work + max(observed_seconds for 0<work<128)*72 + 900)',
                fixed_small_default_when_unobserved=0, unknown_and_next_reserved_caps_included=True),
            next_dispatch_cutoff='minimum(fixed numerical cutoff, original outer cutoff, fixed end minus growing measured replay/hash/exit/log/external reserve)'),
        resources=dict(cpu_index=14, workers=1, threads=1, maximum_unverified_records=1,
            maximum_packet_all_work_rows=PACKET_CAP, maximum_native_seconds_per_record=45,
            maximum_new_retained_bytes=NEW_BYTES, maximum_combined_own_retained_bytes=COMBINED_OWN_BYTES,
            maximum_total_retained_bytes=TOTAL_BYTES, minimum_free_bytes=FREE_BYTES,
            retained_byte_cap_can_stop_incomplete_without_deleting_evidence=True),
        restart_contract=dict(initial_serial_accepted_rows=256, initial_split_accepted_rows=[128,128],
            initial_staged_and_odd_serial_work_cap=INITIAL_CAP,
            all_required_anchors=['initial','after_coarse','after_first_half','odd_accepted_half',
                                 'first_actual_accepted_original_selector','first_actual_event_reduction','last_record_FULL_history'],
            every_serial_proof_work_cap=PACKET_CAP,
            split_combined_work_never_exceeds_serial_cap=True,
            right_cap_is_serial_cap_minus_actual_left_charge=True,
            old_selector_lookup_accepted_F1_F2_only=True,
            event_lookup_actual_positive_reduction_at_committed_pair_origin_only=True,
            first_event_j_is_largest_positive_even_boundary_before_actual_first_trigger=True,
            trigger_must_be_in_actual_successor=True,
            joint_first_event_qualification_only_when_both_firsts_are_in_same_actual_record_and_both_splits_proved=True,
            no_event_found_or_no_legal_even_split_is_incomplete_not_a_waiver=True,
            late_FULL_repeats_exact_last_local_record_and_restores_original_path=True),
        coverage_contract=dict(positive_grain15_loading_required_for_each_fine_level=True,
            requires_actual_committed_F1_F2_accepted_row_and_grain15_in_supported_bearing_ids=True,
            requires_original_accepted_contact_health_lambda_n_grain15_strictly_positive=True,
            prepared_contact_order_cycle_map_and_q_association_must_match_original_raw_and_guard=True,
            no_coarse_shadow_rejected_diagnostic_or_predicted_loading_credit=True,
            original_record_raw_and_independent_guard_hashes_bound_to_first_witness=True,
            full_postworker_replay_recomputes_coverage_and_exactly_matches_owner_states=True,
            missing_actual_loading_is_incomplete_not_success=True),
        validation_order=['all original per-record mechanics/raw/own-state cap/event/FULL-history audits before successor',
            'native source32 and common-state initial/C/F1/odd exact restart matrix',
            'first actual accepted old-selector and first actual event-reduction exact restart proofs',
            'actual committed independently audited positive grain15 normal loading and supported bearing in EACH fine level',
            'complete both fine bounded local paths and exact last-record FULL restart',
            'worker retirement followed by COMPLETE independent all-branch mechanical/raw/cap/event/history replay',
            'unchanged held-q unshifted-clock local pair metrics only',
            'exact supervisor/owner/worker retirement and separate closed-log exit receipt'],
        source_files=copy.deepcopy(source_files), physical_inputs=copy.deepcopy(physical_inputs),
        evidence_files=copy.deepcopy(evidence_files), historical_evidence_files=copy.deepcopy(historical_evidence_files or {}),
        historical_maps=dict(authenticated_source_receipt=str(SOURCE2), sha256=SOURCE2_SHA,
            original_file_count=source2['consumed_original_file_count'],
            original_map_digest=digest(source2['consumed_original_maps']),
            fresh_FULL_hash_authentication_required_at_preparation_authorize_and_final=True,
            hash_authentication_is_not_mechanical_replay=True, mechanical_replay_claimed=False),
        risks=['scalar release proxy is not a six-component velocity error bound',
               'tiny-h momentum cancellation, geometric quantization and representability can stop unchanged gates',
               'missing positive grain15 contact loading in either fine level is an incomplete experiment',
               'no finite-progress-through-contact or full-horizon completion/cost guarantee'],
        original_physics_and_all_accuracy_gates_unchanged=True, all_new_work_discarded=True,
        old_failed_records_admitted=False, existing_unknown_charges_preserved=True,
        qualified_core_cases=1, required_core_cases=12, full_path_accuracy_repaired=False,
        native_physical_or_restart_qualification_completed=False, numerical_launch_ready=False,
        human_approval_required_before_any_numerical_authority=True, authorization_created=False,
        clock_created=False, dispatch_authorized=False)
    return config, proposal


def no_future_authority(paths=FORBIDDEN):
    need(all(not Path(path).exists() for path in paths), 'no preapproval AUTH/design/clock/human receipt or run directory')


def create_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=True); stream.write('\n')


def prepare(pins_path, pins_sha):
    need(sys.version_info[:2] == (3,12) and Path(sys.executable).resolve() == PYTHON.resolve(), 'qualified Python312')
    need(all(os.environ.get(key) == '1' for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS')), 'one thread')
    no_future_authority()
    need(not PHYSICAL.exists() and not PROPOSAL.exists() and not PREPARED.parent.exists(), 'fresh create-only prospective package')
    need(sha(pins_path) == pins_sha, 'caller-pinned source/mock inventory')
    pins = read(pins_path); verify_mapping(pins)
    for path in (Path(__file__).resolve(), SELF_TEST, RUNNER, RUNNER_TEST):
        need(str(path) in pins and pins[str(path)] == sha(path), 'all new preparation/runner/control sources pinned')
        ast.parse(path.read_text(encoding='utf-8'))
    source2 = sealed(SOURCE2, SOURCE2_SHA); closed = sealed(CLOSED, CLOSED_SHA)
    validate_retirement(closed)
    need(sha(ORIGINAL_PHYSICAL) == ORIGINAL_PHYSICAL_SHA and sha(ORIGINAL_PROPOSAL) == ORIGINAL_PROPOSAL_SHA,
         'original physics, conservative gap semantics and thresholds')
    clock_sha = closed['evidence_files'].get(str(OUTER_CLOCK), source2['consumed_original_maps'].get(str(OUTER_CLOCK)))
    need(isinstance(clock_sha, str), 'original fixed clock belongs to authenticated old evidence')
    clock = sealed(OUTER_CLOCK, clock_sha); validate_clock(clock)
    need(datetime.now(timezone.utc) < datetime.fromisoformat(OUTER_END), 'original absolute end not elapsed')
    selected = dict(source2['source_files']); selected.update(source2['prospective_common_state_inputs']); selected.update(pins)
    selected[str(SOURCE2)] = SOURCE2_SHA; selected[str(SOURCE2.with_name('completion.json'))] = sha(SOURCE2.with_name('completion.json'))
    verify_mapping(selected)
    preview = read(SEEDS/'physical_cases_preview.json')
    seeds = {level:json.loads(lzma.decompress((SEEDS/(level+'.json.xz')).read_bytes())) for level in PREPARED_LEVELS}
    physical = read(ORIGINAL_PHYSICAL); original_proposal = read(ORIGINAL_PROPOSAL)
    physical_inputs = dict(closed['physical_inputs']); physical_inputs[str(ORIGINAL_PHYSICAL)] = ORIGINAL_PHYSICAL_SHA
    for case in preview['cases']:
        for value in case['spec']['field_metadata'].values():
            if isinstance(value, dict) and set(value) >= {'path','sha256'}:
                need(source2['consumed_original_maps'].get(value['path']) == value['sha256'],
                     'physical field/geometry association in already-authenticated full original map')
                physical_inputs[value['path']] = value['sha256']
    verify_mapping(physical_inputs)
    evidence = {str(SOURCE2):SOURCE2_SHA, str(SOURCE2.with_name('completion.json')):sha(SOURCE2.with_name('completion.json')),
        str(CLOSED):CLOSED_SHA, str(CLOSED.with_name('completion.json')):sha(CLOSED.with_name('completion.json')),
        str(OUTER_CLOCK):clock_sha, str(OUTER_CLOCK.with_name('completion.json')):sha(OUTER_CLOCK.with_name('completion.json')),
        str(ORIGINAL_PROPOSAL):ORIGINAL_PROPOSAL_SHA, **source2['prospective_common_state_inputs']}
    sources = dict(closed['source_files'])
    for mapping in (source2['source_files'], pins):
        for path, expected in mapping.items():
            need(path not in sources or sources[path] == expected, 'no conflicting frozen source associations')
            sources[path] = expected
    historical = dict(source2['consumed_original_maps'])
    for path, expected in closed['historical_evidence_files'].items():
        need(path not in historical or historical[path] == expected, 'no conflicting original historical associations')
        historical[path] = expected
    runner_functions = {node.name for node in ast.parse(RUNNER.read_text(encoding='utf-8')).body
                        if isinstance(node, ast.FunctionDef)}
    required = {'authorize', 'approval_scope', 'seed_reference', 'load_reference', 'qualify',
                'qualified_local_level', 'loading_coverage', 'post_replay_all', 'evaluate_local', 'close_execution'}
    need(required <= runner_functions, 'all explicit runner admission, local, replay and closure interfaces present')
    metadata=runner_metadata(RUNNER.read_text(encoding='utf-8'))
    need(metadata['approval_scope']==approval_scope() and metadata['baseline']==BASELINE
         and metadata['diagnostic_contract']==diagnostic_contract(),
         'runner and prospective proposal have EXACT same approved resource scope and conservative baseline')
    controls=[]
    for path in (SELF_TEST, RUNNER_TEST):
        result = subprocess.run([str(PYTHON), '-B', str(path)], cwd=ROOT, capture_output=True,
                                text=True, timeout=180, env=os.environ.copy())
        controls.append(dict(path=str(path), source_sha256=sha(path), returncode=result.returncode,
                             stdout=result.stdout, stderr=result.stderr, source_mock_only=True))
        need(result.returncode == 0, 'source/mock controls passed, no native authority: '+str(path))
    config, proposal = build_documents(source2, preview, seeds, physical, original_proposal, sources,
                                      physical_inputs, evidence, clock_sha, historical)
    retirement_before=fresh_old_retirements(closed)
    # Freshly authenticate EVERY original declared byte before any positive
    # prospective seal. This is hash authentication, never mechanical replay.
    verify_mapping(historical)
    verify_mapping(selected); verify_mapping(sources); verify_mapping(physical_inputs); verify_mapping(evidence)
    retirement_after=fresh_old_retirements(closed)
    need(datetime.now(timezone.utc) < datetime.fromisoformat(OUTER_END),
         'original absolute end still holds before positive prospective writes')
    no_future_authority()
    create_json(PHYSICAL, config)
    proposal['physical_design_sha256'] = sha(PHYSICAL)
    create_json(PROPOSAL, proposal)
    body = dict(schema='paper1.contact-event-local-source-preparation.v1', passed=True,
        source_preparation_sha256=SOURCE2_SHA, proposal_sha256=sha(PROPOSAL), physical_design_sha256=sha(PHYSICAL),
        all_required_interfaces_present=True, source_mock_controls=controls,
        explicit_interfaces_checked_source_only=sorted(required),
        source_files=sources, physical_inputs=physical_inputs, evidence_files=evidence,
        historical_evidence_files=historical,
        fresh_FULL_hash_authentication_performed=True, fresh_FULL_hash_authenticated_file_count=len(historical),
        fresh_FULL_hash_authentication_is_NOT_mechanical_replay=True,
        artifacts={str(PHYSICAL):sha(PHYSICAL), str(PROPOSAL):sha(PROPOSAL)},
        old_exact_retirement_receipt_authenticated=True, fresh_process_inspection_performed=True,
        fresh_exact_retirement_before_FULL_hash=retirement_before,
        fresh_exact_retirement_after_FULL_hash=retirement_after,
        process_inspection_read_only_no_action=True,
        all_three_prepared_FULL_states_and_histories_exact=True, minimum_gap_semantics_copied_without_seed_rebinding=True,
        all_new_work_discarded=True, native_physical_or_restart_qualification_completed=False,
        numerical_launch_ready=False, dispatch_authorized=False, execution_authority_created=False,
        new_clock_created=False, new_transport_steps=0, new_native_force_calls=0, new_integration_records=0,
        utc=datetime.now(timezone.utc).isoformat())
    create_json(PREPARED, body)
    create_json(PREPARED.with_name('completion.json'), dict(passed=True, results_sha256=sha(PREPARED)))
    no_future_authority()
    return body


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pins', required=True, type=Path)
    parser.add_argument('--pins-sha256', required=True)
    args = parser.parse_args()
    result = prepare(args.pins, args.pins_sha256)
    print(json.dumps(dict(passed=result['passed'], proposal_sha256=result['proposal_sha256'],
                         numerical_launch_ready=False, new_transport_steps=0), sort_keys=True))
