"""Separately versioned recovery within the ORIGINAL approved qualification clock.

Import, ``prepare`` and ``controls`` do not import a physical runtime, create
authority, warm a kernel, or dispatch numerical work.  A separate exact human
approval, fixed clock and source-only preparation must precede ``authorize``.
The native window worker is a registered child of the owner.  The owner watches
each actual native packet from its immutable start/finish markers, admits at
most one packet after independent mechanical/cap/raw reconstruction, and keeps
all shadow, rejected, partial and unknown work in one conservative ledger.

This file grants no successor-case or publication admission.  Even a positive
owner disposition needs a separate caller-authenticated post-supervisor exit
and closed-log receipt.  Missing native interfaces or source qualifications are
readiness failures, never replaceable by a passing producer Boolean.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import FunctionType
import argparse
import ast
import copy
import hashlib
import importlib
import json
import lzma
import math
import os
import shutil
import struct
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
STAGING = ROOT / 'paper1_staging'
ORIGINAL_DESIGNS = ROOT / 'paper1_designs/full_horizon_repair_20261018'
DESIGNS = ORIGINAL_DESIGNS / 'recovery_02'
INITIAL_OUT = ROOT / 'paper1_runs/full_horizon_repair_20261018'
OUT = ROOT / 'paper1_runs/full_horizon_repair_20261018_recovery02'
PROPOSAL = DESIGNS / 'qualification_recovery_02.json'
PREPARED = DESIGNS / 'preparation_02/results.json'
APPROVAL = ORIGINAL_DESIGNS / 'human_approval_qualification_01/results.json'
CLOCK = ORIGINAL_DESIGNS / 'qualification_clock_01/results.json'
PHYSICAL = ORIGINAL_DESIGNS / 'physical_cases_qualification_01.json'
PLAN = DESIGNS / 'design_02.json'
AUTH = DESIGNS / 'authorization_02.json'
ORIGINAL_PLAN = ORIGINAL_DESIGNS / 'design_qualification_01.json'
ORIGINAL_AUTH = ORIGINAL_DESIGNS / 'authorization_qualification_01.json'
ORIGINAL_PROPOSAL = ORIGINAL_DESIGNS / 'qualification_proposal_01.json'
ORIGINAL_PREPARED = ORIGINAL_DESIGNS / 'preparation_qualification_01/results.json'
INITIAL_CLOSURE = INITIAL_OUT / 'final_execution_receipt_01/results.json'
DIAGNOSIS = ORIGINAL_DESIGNS / 'failure_diagnosis_qualification_01/results.json'
ORIGINAL_DRIVER = STAGING / 'run_stepdoubling_qualification_v1.py'
ORIGINAL_DRIVER_SHA = 'b21f22446ccbf8a00551f738a9cf116d8a208ad86b5a42521e1ea5b1afabe006'
INITIAL_CLOSURE_SHA = 'ebed1438521447cb4fffda16a0784140118456487bc3b9626479b4907d5bce66'
DIAGNOSIS_SHA = 'bc5c1a5665b4dd8ad984465f4918d121cb8991f7e1d677e3e2d5ef742801916b'
ORIGINAL_PROPOSAL_SHA = '61d84fb8797fb95b8e4fc7918304d98ae60afc64253eff6d9a26afcc7fd4869d'
INITIAL_SPENT = dict(all_work_rows=32, integration_records=2, numerical_windows=1,
    production_records=0, accepted_committed_half_rows=0,
    synthetic_nonadvancing_kernel_invocations=2)
PYTHON = Path('C:/Users/wonjuncha-admin/AppData/Local/Programs/Python/Python312/python.exe')
RUNTIME = STAGING / 'full_state_integration_adapter_v2.py'
AUDITOR = STAGING / 'audit_full_state_stepdoubling_v1.py'
RESTART = STAGING / 'prepare_stepdoubling_restart_v1.py'
POLICY = STAGING / 'full_state_stepdoubling_v1.py'
OLD_IDENTITIES = STAGING / 'cost_screen_v1.py'
OLD_IDENTITY_SHA = '9897a836792563e909dcec585e5cc83c8917151d6a8ad984055a900e34f9e5b4'
LEVELS = ('f0p0625', 'f0p03125', 'f0p125')
FACTORS = {'f0p125': .125, 'f0p0625': .0625, 'f0p03125': .03125}
SUCCESS_CAPS = {'f0p125': 2400000, 'f0p0625': 4800000, 'f0p03125': 9600000}
COMMITTED_HALF_CAPS = {'f0p125': 1600000, 'f0p0625': 3200000, 'f0p03125': 6400000}
ORIGINAL_BASELINE = dict(case_work_rows=10312778, case_records=2174,
                shared_work_rows=4664866, shared_records=1004,
                diagnostic_work_rows=146081, diagnostic_records=66)
BASELINE = dict(case_work_rows=10312810, case_records=2176,
                shared_work_rows=4664898, shared_records=1006,
                diagnostic_work_rows=146113, diagnostic_records=68)
MAX_WORK, MAX_RECORDS = 17999968, 3998
MAX_REJECTED, MAX_STANDALONE = 1000000, 199968
MAX_PRODUCTION_RECORDS, MAX_STANDALONE_RECORDS = 3850, 148
MAX_NONADVANCING_KERNEL_INVOCATIONS = 20
CASE_WORK, CASE_RECORDS = 28312778, 6174
SHARED_WORK, SHARED_RECORDS = 22664866, 5004
DIAGNOSTIC_WORK, DIAGNOSTIC_RECORDS = 18146081, 4066
MAX_WINDOWS, MAX_WINDOW_S, MAX_SHARED_S = 10, 12 * 3600, 132 * 3600
NATIVE_S, PACKET_CAP = 45., 4998
OWN_BYTES, RETENTION_BYTES, FREE_BYTES = 12 * 1024**3, 21 * 1024**3, 20 * 1024**3
OUTPUT_RESERVE = 64 * 1024**2
SCREEN_S, HORIZON_S = .255, .9364396280429768
ORIGINAL_GATES = dict(endpoint_q_over_U_max=.005, mean_L1_q_over_U_max=.005,
    whole_position_over_b_max=.02, whole_axis_vector_norm_max=.01,
    exit_time_difference_s_max=.0025, first_dwell_time_difference_s_max=.0025,
    same_terminal_label=True, same_dwell_flag=True)
PREFIX_FIELDS = {'path', 'design_sha256', 'compressed_sha256',
                 'original_sha256', 'history_sha256', 'history_length'}
_RESOURCE_LAST = [0., None]


def need(value, message):
    if not value:
        raise RuntimeError('Step-doubling qualification: ' + message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def instant(value):
    result = datetime.fromisoformat(value)
    need(result.tzinfo is not None and result.utcoffset() is not None, 'aware fixed UTC bounds')
    return result.timestamp()


def is_sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(1024 * 1024):
            result.update(block)
    return result.hexdigest()


def packed(value):
    return json.dumps(value, sort_keys=True, allow_nan=True, separators=(',', ':')).encode()


def digest(value):
    """Administrative comparison digest; never called an original FULL digest."""
    return hashlib.sha256(packed(value)).hexdigest()


def original_digest(value):
    # Literal Stage115 default JSON spacing; inputs have already been made plain.
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=True).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def commit(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, sort_keys=True, indent=2, allow_nan=True) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(data)
    return sha(path)


def seal(folder, value):
    folder = Path(folder)
    need(not folder.exists(), 'create-only receipt, including partial directories')
    folder.mkdir(parents=True, exist_ok=False)
    result = folder / 'results.json'
    commit(result, value)
    commit(folder / 'completion.json', dict(passed=value.get('passed') is True,
        results_sha256=sha(result), utc=utc()))
    return value


def sealed(path, *, positive=False):
    path = Path(path)
    result, completion = read(path), read(path.with_name('completion.json'))
    need(completion['results_sha256'] == sha(path)
         and completion['passed'] is (result.get('passed') is True), 'complete immutable receipt pair')
    if positive:
        need(result.get('passed') is True, 'positive prerequisite receipt')
    return result


def verify_mapping(mapping):
    need(isinstance(mapping, dict), 'explicit source/input/evidence map')
    for name, expected in mapping.items():
        need(is_sha(expected) and sha(name) == expected, 'immutable bytes: ' + str(name))


def merge_maps(*mappings):
    result = {}
    for mapping in mappings:
        for name, expected in mapping.items():
            need(name not in result or result[name] == expected, 'nonconflicting frozen file identity')
            result[name] = expected
    return result


def environment():
    need(Path(sys.executable).resolve() == PYTHON.resolve(), 'qualified Python executable')
    need(all(os.environ.get(k) == '1' for k in
             ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS')), 'one BLAS/OpenMP thread')


def approval_scope():
    return dict(three_fresh_full_t0_paths=True, maximum_new_all_work_rows=MAX_WORK,
        maximum_new_integration_records=MAX_RECORDS, maximum_success_work_by_level=SUCCESS_CAPS,
        maximum_committed_half_rows_by_level=COMMITTED_HALF_CAPS,
        maximum_accuracy_rejected_work_rows=MAX_REJECTED,
        maximum_standalone_native_control_work_rows=MAX_STANDALONE,
        maximum_production_records=MAX_PRODUCTION_RECORDS,
        maximum_standalone_native_control_records=MAX_STANDALONE_RECORDS,
        maximum_nonadvancing_synthetic_kernel_invocations=MAX_NONADVANCING_KERNEL_INVOCATIONS,
        case_all_work_ceiling=CASE_WORK, case_record_ceiling=CASE_RECORDS,
        shared_all_work_ceiling=SHARED_WORK, shared_record_ceiling=SHARED_RECORDS,
        conservative_discarded_diagnostic_ceiling=DIAGNOSTIC_WORK,
        conservative_diagnostic_record_ceiling=DIAGNOSTIC_RECORDS,
        maximum_shared_hours=132, maximum_numerical_windows=MAX_WINDOWS,
        maximum_hours_per_numerical_window=12, maximum_packet_work_rows=PACKET_CAP,
        maximum_native_seconds_per_record=NATIVE_S, own_output_bytes=OWN_BYTES,
        total_retention_bytes=RETENTION_BYTES, minimum_free_bytes=FREE_BYTES,
        workers=1, threads=1, logical_cpu=14, maximum_unverified_packets=1,
        horizon_s=HORIZON_S, pore_volumes=.01, embedded_screen_s=SCREEN_S,
        original_accuracy_gate_values=ORIGINAL_GATES, successor_cases_authorized=False,
        publication_admission_authorized=False, shadow_rejected_partial_unknown_work_all_charged=True,
        all_source_and_tolerances_frozen=True, no_failed_path_or_late_seed_credit=True)


def validate_contract(proposal, physical, preparation):
    need(proposal.get('required_human_approval_scope') == approval_scope(), 'exact prospective approval scope')
    need(proposal.get('baseline') == BASELINE, 'actual closed all-attempt baseline')
    need(proposal.get('original_accuracy_gates') == ORIGINAL_GATES, 'original full-path accuracy/event gates')
    need(proposal.get('physical_equation_changes') == [] and proposal.get('gap_policy_changes') == []
         and proposal.get('route_order_changes') == [], 'no physical law/gap/route change')
    cases = physical['cases']
    need(len(cases) == 3 and {item['level_id'] for item in cases} == set(LEVELS), 'three independently fresh physical specs')
    for item in cases:
        key = item['level_id']; factor = FACTORS[key]
        need(item['factor'] == factor and item['spec']['horizon_s'] == HORIZON_S,
             'original factor and complete observation horizon')
    levels = proposal['levels']
    need({v['level_id'] for v in levels} == set(LEVELS), 'three frozen supplemental limit records')
    for item in levels:
        factor = FACTORS[item['level_id']]; scale = (factor / .125)**2; limits = item['limits']
        need(limits['position_defect_m'] == 1e-12 * scale
             and limits['director_defect'] == 1e-8 * scale
             and limits['velocity_defect_over_U'] == 5e-5 * scale
             and limits['maximum_halvings'] == 8 and limits['minimum_h_s'] > 0
             and is_sha(limits['numerical_binding']), 'prospectively frozen local indicators, no order/global-bound assertion')
    need(preparation.get('passed') is True and preparation.get('dispatch_authorized') is False
         and preparation.get('all_required_interfaces_present') is True,
         'source-only engineering readiness must bind actual interfaces')
    needed = {str(path): sha(path) for path in (SELF, RUNTIME, AUDITOR, RESTART, POLICY, OLD_IDENTITIES)}
    need(all(preparation['source_files'].get(path) == value for path, value in needed.items()), 'driver and actual original interface source pins')
    verify_mapping(merge_maps(proposal['source_files'], proposal['physical_inputs'], proposal['evidence_files'],
        proposal['historical_evidence_files'], preparation['source_files'], preparation['physical_inputs'],
        preparation['evidence_files'], preparation['historical_evidence_files']))
    return True


def validate_clock(clock, *, now=None):
    start, cutoff, end = (instant(clock[k]) for k in ('start_utc', 'simulation_cutoff_utc', 'end_utc'))
    need(0 < cutoff - start <= 124 * 3600 and 0 < end - start <= MAX_SHARED_S
         and end - cutoff >= 8 * 3600, 'one fixed fresh maximum132h clock with at least8h terminal reserve')
    need(clock.get('fresh_independent_authority') is True and clock.get('old_authorities_closed_unchanged') is True,
         'no old numerical clock reopened or reset')
    now = time.time() if now is None else now
    need(start <= now < cutoff < end, 'unexpired fixed approval clock, preparation consumes its time')
    return start, cutoff, end


def inventory_bytes(root=ROOT):
    own = sum(p.stat().st_size for folder in (OUT, INITIAL_OUT) if folder.exists()
              for p in folder.rglob('*') if p.is_file())
    total = sum(p.stat().st_size for folder in ('paper1_designs', 'paper1_runs', 'paper1_evaluations')
                for p in (root / folder).rglob('*') if p.is_file())
    return own, total, shutil.disk_usage(root).free


def resource_guard(*, force_inventory=False, reserve=OUTPUT_RESERVE):
    need(type(reserve) is int and reserve >= 0, 'explicit nonnegative output reserve')
    free = shutil.disk_usage(ROOT).free
    need(free >= FREE_BYTES + reserve, 'free disk reserve includes pending output')
    now = time.monotonic()
    if force_inventory or _RESOURCE_LAST[1] is None or now - _RESOURCE_LAST[0] >= 60:
        own, total, free = inventory_bytes()
        _RESOURCE_LAST[:] = [now, (own, total, free)]
    own, total, _ = _RESOURCE_LAST[1]
    need(own + reserve <= OWN_BYTES and total + reserve <= RETENTION_BYTES,
         'own-output/total-retention ceilings include pending receipt/raw reserve')
    return dict(own_bytes=own, total_retained_bytes=total, free_bytes=free,
                conservative_output_reserve_bytes=reserve)


def private_identity_helpers():
    """Literal original identity/stop code, privately bound; never old authority."""
    import psutil
    need(sha(OLD_IDENTITIES) == OLD_IDENTITY_SHA, 'frozen original process-identity helper before compiling any action')
    tree = ast.parse(OLD_IDENTITIES.read_text(encoding='utf-8'))
    names = {'identity', 'stop_owned'}
    nodes = [copy.deepcopy(n) for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    need({n.name for n in nodes} == names, 'actual original birth/full-command helpers')
    namespace = dict(psutil=psutil, require=need)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(OLD_IDENTITIES), 'exec'), namespace)
    return namespace['identity'], namespace['stop_owned']


def inspect_identity(launch):
    identity, _ = private_identity_helpers()
    return identity(launch)


def exact_stop(process, launch):
    _, stop = private_identity_helpers()
    return stop(process, launch)


def assert_retired(identities):
    need(isinstance(identities, list), 'explicit old/child process inventory')
    return [dict(launch=item, inspection=inspect_identity(item)) for item in identities
            if need(inspect_identity(item)['retired'], 'fresh exact process retirement') is None]


def authority(numerical=False, *, refresh_sources=False):
    environment()
    p = read(PLAN)
    need(p['binding'] == digest({k: v for k, v in p.items() if k != 'binding'})
         and p['authorization_sha256'] == sha(AUTH)
         and p['physical_design_sha256'] == sha(PHYSICAL)
         and p['proposal_sha256'] == sha(PROPOSAL)
         and p['approval_sha256'] == sha(APPROVAL)
         and p['clock_sha256'] == sha(CLOCK), 'immutable fresh authority/control associations')
    now = time.time()
    need(instant(p['start_utc']) <= now < instant(p['end_utc']), 'absolute shared deadline')
    if numerical:
        need(now < instant(p['simulation_cutoff_utc']), 'absolute numerical cutoff')
    resource_guard(force_inventory=refresh_sources)
    if refresh_sources:
        verify_mapping(p['source_files']); verify_mapping(p['physical_inputs']); verify_mapping(p['evidence_files'])
    return p


def original_approval_scope():
    """Literal original grant scope; never relabel the remaining allocation human-reviewed."""
    value = approval_scope()
    value.update(maximum_new_all_work_rows=18000000, maximum_new_integration_records=4000,
        maximum_standalone_native_control_work_rows=200000,
        maximum_standalone_native_control_records=150,
        maximum_nonadvancing_synthetic_kernel_invocations=22, maximum_numerical_windows=11)
    return value


def prior_attempt_accounting():
    return dict(initial_execution_receipt_sha256=INITIAL_CLOSURE_SHA,
        initial_diagnosis_sha256=DIAGNOSIS_SHA, conservative_spent=copy.deepcopy(INITIAL_SPENT),
        prior_unknown_reserved_work_upper_bound=32, prior_known_unaccepted_work_rows=0,
        prior_actual_nonadvancing_kernel_invocations=2,
        initial_unknown_reservation_preserved_not_admitted=True,
        all_attempt_baseline=copy.deepcopy(BASELINE), original_absolute_clock_reused_unchanged=True)


def validate_recovery_origin(proposal, preparation, approval, clock, original_plan,
                             original_proposal, closed, failed, diagnosis):
    """Administrative derivation only; no new scientific acceptance or human reply."""
    old_scope = original_approval_scope()
    need(original_proposal.get('required_human_approval_scope') == old_scope
         and original_proposal.get('baseline') == ORIGINAL_BASELINE
         and original_plan.get('scope') == old_scope
         and original_plan.get('baseline') == ORIGINAL_BASELINE,
         'original approved full envelope and original baseline unchanged')
    need(approval.get('scope') == old_scope
         and approval.get('proposal_sha256') == ORIGINAL_PROPOSAL_SHA
         and approval.get('preparation_sha256') == sha(ORIGINAL_PREPARED)
         and approval.get('clock_sha256') == sha(CLOCK)
         and all(isinstance(approval.get(k), str) and approval[k].strip()
                 for k in ('human_reply', 'question_reference')),
         'actual ORIGINAL direct human grant, not a fabricated new approval')
    need(original_plan.get('binding') == digest({k: v for k, v in original_plan.items() if k != 'binding'})
         and original_plan.get('authorization_sha256') == sha(ORIGINAL_AUTH)
         and original_plan.get('proposal_sha256') == ORIGINAL_PROPOSAL_SHA
         and original_plan.get('approval_sha256') == sha(APPROVAL)
         and original_plan.get('clock_sha256') == sha(CLOCK)
         and original_plan.get('physical_design_sha256') == sha(PHYSICAL),
         'closed original authority/control associations')
    for key in ('start_utc', 'simulation_cutoff_utc', 'end_utc'):
        need(original_plan[key] == clock[key], 'same ORIGINAL absolute clock, no restart at recovery')
    need(proposal.get('original_scope') == old_scope
         and proposal.get('scope_remaining') == approval_scope()
         and preparation.get('scope_remaining') == approval_scope(),
         'remaining resource allocation derived inside original grant')
    need(all(proposal.get(key) == original_proposal.get(key) for key in (
        'levels', 'original_accuracy_gates', 'physical_equation_changes',
        'gap_policy_changes', 'route_order_changes', 'prefix_forecast_rule', 'replay_reserve_rule')),
         'unchanged numerical limits/bindings, physics, routes, gates and forecast policy')
    need(closed.get('passed') is True and closed.get('closure_complete') is True
         and closed.get('qualified') is False
         and closed.get('exact_process_retirement_authenticated') is True
         and closed.get('actual_supervisor_returncode') == 2
         and closed.get('design_sha256') == sha(ORIGINAL_PLAN)
         and closed.get('final_disposition_sha256') == sha(INITIAL_OUT / 'final_disposition_01/results.json'),
         'strict closed original negative and directly observed original supervisor exit')
    need(failed.get('passed') is False and failed.get('qualification_passed') is False
         and failed.get('full_path_accuracy_passed') is False
         and failed.get('core_result_admitted') is False
         and failed.get('successor_cases_dispatched') is False
         and not any(failed['level_native_complete'].values()), 'no initial path or checkpoint credit')
    old_counts = failed['ledger']
    expected_counts = dict(work_rows=32, records=2, standalone_work_rows=32, standalone_records=2,
        production_records=0, accepted_committed_half_rows=0, known_unaccepted_work_rows=0,
        unknown_reserved_work_upper_bound=32, known_nonadvancing_kernel_invocations=2,
        unknown_nonadvancing_kernel_invocations_upper_bound=0)
    need(old_counts.get('ledger_authenticated') is True
         and all(old_counts.get(key) == value for key, value in expected_counts.items())
         and len(old_counts.get('unresolved', [])) == 1
         and old_counts['unresolved'][0]['reservation']['maximum_work_rows'] == 32,
         'preserve the initial32 unknown rows,2 records,2 warms and zero production')
    need(diagnosis.get('passed') is True
         and diagnosis.get('closed_initial_receipt_sha256') == INITIAL_CLOSURE_SHA
         and diagnosis.get('old_failed_ledger') == old_counts
         and diagnosis.get('zero_target_substeps_proved') is True
         and diagnosis.get('target_outer_force_invocations') == 0
         and diagnosis.get('target_transport_substeps') == 0
         and diagnosis.get('new_native_calls') == diagnosis.get('new_transport_steps') == 0
         and diagnosis.get('clock_reset_or_budget_increase') is False
         and diagnosis.get('original_failed_unknown_reservation_preserved') is True
         and diagnosis.get('conservative_shared_spent_charge') == INITIAL_SPENT,
         'strict independently sealed pre-yield implementation diagnosis, no scientific waiver')
    need(all(diagnosis.get('same_approved_' + key) == clock[key]
             for key in ('start_utc', 'simulation_cutoff_utc', 'end_utc')),
         'diagnosis binds all original fixed clock bounds')
    need(all(preparation.get(key) == value for key, value in dict(
        original_approval_sha256=sha(APPROVAL), original_clock_sha256=sha(CLOCK),
        initial_closure_sha256=INITIAL_CLOSURE_SHA, diagnosis_sha256=DIAGNOSIS_SHA).items()),
         'fresh source preparation binds original grant, clock, negative closure and diagnosis')
    return old_counts


def authorize_recovery(expected_approval_sha256, expected_clock_sha256,
                       expected_initial_closure_sha256, expected_diagnosis_sha256,
                       expected_preparation_sha256):
    """Derive remaining authority from ORIGINAL approval; never create/reset a clock."""
    environment()
    need(not OUT.exists() and not PLAN.exists() and not AUTH.exists(),
         'never duplicate recovery authority, launcher or closed run')
    for path, expected in ((APPROVAL, expected_approval_sha256), (CLOCK, expected_clock_sha256),
            (INITIAL_CLOSURE, expected_initial_closure_sha256), (DIAGNOSIS, expected_diagnosis_sha256),
            (PREPARED, expected_preparation_sha256)):
        need(is_sha(expected) and sha(path) == expected, 'caller-pinned recovery association: ' + str(path))
    need(expected_initial_closure_sha256 == INITIAL_CLOSURE_SHA
         and expected_diagnosis_sha256 == DIAGNOSIS_SHA
         and sha(ORIGINAL_DRIVER) == ORIGINAL_DRIVER_SHA
         and sha(ORIGINAL_PROPOSAL) == ORIGINAL_PROPOSAL_SHA, 'fixed preserved first attempt and strict diagnosis')
    approval, clock, closed, diagnosis, prepared = (sealed(path, positive=True) for path in
        (APPROVAL, CLOCK, INITIAL_CLOSURE, DIAGNOSIS, PREPARED))
    failed = sealed(INITIAL_OUT / 'final_disposition_01/results.json')
    proposal, physical = read(PROPOSAL), read(PHYSICAL)
    old_plan, old_proposal = read(ORIGINAL_PLAN), read(ORIGINAL_PROPOSAL)
    validate_recovery_origin(proposal, prepared, approval, clock, old_plan, old_proposal,
                             closed, failed, diagnosis)
    validate_contract(proposal, physical, prepared)
    validate_clock(clock)
    verify_mapping(closed['artifacts'])
    verify_mapping(diagnosis['source_files']); verify_mapping(diagnosis['evidence_files'])
    prior_identities = [row['launch'] for row in closed['exact_retirement_after']]
    need(len(prior_identities) == 4, 'all four exact initial task actors explicitly closed')
    retired = assert_retired(prior_identities + prepared['prior_exact_process_identities'])
    resource_guard(force_inventory=True)
    sources = merge_maps(proposal['source_files'], prepared['source_files'], old_plan['source_files'],
        {str(ORIGINAL_DRIVER): ORIGINAL_DRIVER_SHA})
    inputs = merge_maps(proposal['physical_inputs'], prepared['physical_inputs'], old_plan['physical_inputs'],
        {str(PHYSICAL): sha(PHYSICAL)})
    evidence_paths = (PROPOSAL, PREPARED, APPROVAL, CLOCK, ORIGINAL_PLAN, ORIGINAL_AUTH,
        ORIGINAL_PROPOSAL, ORIGINAL_PREPARED, INITIAL_CLOSURE, DIAGNOSIS,
        INITIAL_OUT / 'final_disposition_01/results.json')
    evidence = merge_maps(proposal['evidence_files'], prepared['evidence_files'], old_plan['evidence_files'],
        {str(path): sha(path) for item in evidence_paths for path in
         ((item, item.with_name('completion.json')) if item.with_name('completion.json').exists() else (item,))})
    historical = merge_maps(proposal['historical_evidence_files'], prepared['historical_evidence_files'],
        old_plan['historical_evidence_files'])
    verify_mapping(sources); verify_mapping(inputs); verify_mapping(evidence); verify_mapping(historical)
    auth = dict(schema='paper1.stepdoubling.derived-recovery-authority.v2', passed=True,
        proposal_sha256=sha(PROPOSAL), approval_sha256=expected_approval_sha256,
        preparation_sha256=expected_preparation_sha256, clock_sha256=expected_clock_sha256,
        scope=approval_scope(), original_approved_scope=original_approval_scope(),
        initial_closure_sha256=INITIAL_CLOSURE_SHA, diagnosis_sha256=DIAGNOSIS_SHA,
        prior_attempt_accounting=prior_attempt_accounting(), derived_within_original_approval=True,
        new_human_approval_claimed=False, new_clock_created=False,
        start_utc=clock['start_utc'], simulation_cutoff_utc=clock['simulation_cutoff_utc'],
        end_utc=clock['end_utc'], no_automatic_extension=True, successor_cases_authorized=False,
        publication_admission_authorized=False, utc=utc())
    commit(AUTH, auth)
    plan = dict(**auth, authorization_sha256=sha(AUTH), physical_design_sha256=sha(PHYSICAL),
        source_files=sources, physical_inputs=inputs, evidence_files=evidence,
        historical_evidence_files=historical, logical_core_id=proposal['logical_core_id'], baseline=BASELINE,
        frozen_replay_reserve_rule=proposal['replay_reserve_rule'],
        old_exact_identities_freshly_retired=retired,
        native_prelude_required_before_production=True)
    plan['binding'] = digest(plan)
    commit(PLAN, plan)
    print(json.dumps(dict(authorized=True, derived_within_original_approval=True,
        design_sha256=sha(PLAN), numerical_work_started=False, fixed_end_utc=plan['end_utc'])), flush=True)
    return plan


def store_packet(folder, packet, parent_prefix, parent_history):
    """Lossless packet envelope; the growing accepted history is prefix encoded.

    Six-field prefixes use the original compact history JSON packing. This is
    an explicitly NEW packet envelope, never called the original Stage179 raw
    record codec or a mechanical audit. All trial observations remain literal.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    path = folder / 'packet.json.xz'
    value = copy.deepcopy(packet)
    full = packet['checkpoint']['physical_checkpoint']
    history = full['state']['history']
    need(history[:len(parent_history)] == parent_history, 'literal accepted FULL history ancestry')
    need(parent_prefix is None or set(parent_prefix) == PREFIX_FIELDS, 'complete six-field parent prefix')
    history_data = json.dumps(history, separators=(',', ':'), allow_nan=True).encode()
    raw = (json.dumps(packet, sort_keys=True, indent=2, allow_nan=True) + '\n').encode()
    history_sha = hashlib.sha256(history_data).hexdigest()
    value['checkpoint']['physical_checkpoint']['state']['history'] = dict(
        schema='paper1.accepted-history-prefix.v1', parent=parent_prefix,
        parent_length=len(parent_history), delta=history[len(parent_history):],
        length=len(history), sha256=history_sha)
    envelope = dict(schema='paper1.lossless-stepdoubling-packet-prefix.v1',
        physical_design_sha256=sha(PHYSICAL), original_uncompressed_sha256=hashlib.sha256(raw).hexdigest(),
        original_uncompressed_bytes=len(raw), packet=value)
    encoded = lzma.compress((json.dumps(envelope, sort_keys=True, indent=2, allow_nan=True) + '\n').encode(),
                            format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64, preset=6)
    resource_guard(force_inventory=True, reserve=max(OUTPUT_RESERVE, len(encoded) * 2))
    with path.open('xb') as stream:
        stream.write(encoded)
    prefix = dict(path=str(path.resolve()), design_sha256=sha(PHYSICAL), compressed_sha256=sha(path),
        original_sha256=envelope['original_uncompressed_sha256'], history_sha256=history_sha,
        history_length=len(history))
    commit(folder / 'prefix.json', prefix)
    commit(folder / 'raw_seal.json', dict(schema=envelope['schema'], raw_sha256=sha(path), prefix=prefix,
        original_FULL_output_sha256=original_digest(full), original_controller_checkpoint_sha256=digest(packet['checkpoint']),
        utc=utc()))
    return prefix


def load_packet(path, expected_prefix, parent_prefix, parent_history):
    path = Path(path)
    need(set(expected_prefix) == PREFIX_FIELDS and Path(expected_prefix['path']).resolve() == path.resolve()
         and expected_prefix['design_sha256'] == sha(PHYSICAL)
         and expected_prefix['compressed_sha256'] == sha(path), 'all raw prefix path/design/compressed fields')
    envelope = json.loads(lzma.decompress(path.read_bytes(), format=lzma.FORMAT_XZ))
    need(envelope['schema'] == 'paper1.lossless-stepdoubling-packet-prefix.v1'
         and envelope['physical_design_sha256'] == sha(PHYSICAL), 'new lossless packet envelope')
    packet = envelope['packet']
    marker = packet['checkpoint']['physical_checkpoint']['state']['history']
    need(marker['schema'] == 'paper1.accepted-history-prefix.v1'
         and marker['parent'] == parent_prefix and marker['parent_length'] == len(parent_history), 'exact complete parent prefix, never an easier history')
    history = parent_history + marker['delta']
    history_sha = hashlib.sha256(json.dumps(history, separators=(',', ':'), allow_nan=True).encode()).hexdigest()
    need(marker['length'] == len(history) == expected_prefix['history_length']
         and marker['sha256'] == history_sha == expected_prefix['history_sha256'], 'exact FULL accepted history bytes/length')
    packet['checkpoint']['physical_checkpoint']['state']['history'] = history
    raw = (json.dumps(packet, sort_keys=True, indent=2, allow_nan=True) + '\n').encode()
    need(hashlib.sha256(raw).hexdigest() == envelope['original_uncompressed_sha256'] == expected_prefix['original_sha256']
         and len(raw) == envelope['original_uncompressed_bytes'], 'original whole packet JSON losslessly reconstructed')
    need(packet['original_FULL_output_sha256'] == original_digest(packet['checkpoint']['physical_checkpoint']), 'original FULL output digest')
    return packet


def write_trace(path, rows):
    """Literal thirteen-column float64 NPY, without importing a physical stack."""
    need(all(len(row) == 13 and all(math.isfinite(x) for x in row) for row in rows), 'finite13-column accepted trace')
    header = repr(dict(descr='<f8', fortran_order=False, shape=(len(rows), 13)))
    padding = (64 - (10 + len(header) + 1) % 64) % 64
    data = (header + ' ' * padding + '\n').encode('latin1')
    path = Path(path)
    with path.open('xb') as stream:
        stream.write(b'\x93NUMPY\x01\x00' + struct.pack('<H', len(data)) + data)
        for row in rows:
            stream.write(struct.pack('<13d', *row))
    return sha(path)


def empty_counts():
    return dict(work_rows=0, records=0, standalone_work_rows=0, standalone_records=0,
        production_records=0, rejected_work_rows=0, accepted_committed_half_rows=0,
        discarded_diagnostic_work_rows=0, diagnostic_records=0,
        accepted_all_work_rows=0, known_unaccepted_work_rows=0,
        unknown_reserved_work_upper_bound=0, unresolved=[], labels=[], known_cap_overruns=[],
        nonadvancing_kernel_invocations=0, unknown_nonadvancing_kernel_invocations_upper_bound=0,
        known_nonadvancing_kernel_invocations=0,
        levels={key: dict(work_rows=0, success_or_pending_work_rows=0,
                         rejected_work_rows=0, committed_half_rows=0, labels=[]) for key in LEVELS})


def budget_guard(counts, level_id, kind, cap):
    need(level_id in LEVELS and kind in ('production', 'standalone')
         and type(cap) is int and 0 < cap <= PACKET_CAP, 'declared level/role and all-work packet cap')
    need(not counts['unresolved'], 'one unverified packet; no successor after unknown/failed admission')
    need(counts['nonadvancing_kernel_invocations'] <= MAX_NONADVANCING_KERNEL_INVOCATIONS,
         'separate new nonadvancing arithmetic-warm contact-kernel ceiling')
    work, calls = counts['work_rows'] + cap, counts['records'] + 1
    need(work <= MAX_WORK and calls <= MAX_RECORDS
         and BASELINE['case_work_rows'] + work <= CASE_WORK
         and BASELINE['case_records'] + calls <= CASE_RECORDS
         and BASELINE['shared_work_rows'] + work <= SHARED_WORK
         and BASELINE['shared_records'] + calls <= SHARED_RECORDS
         and BASELINE['diagnostic_work_rows'] + work <= DIAGNOSTIC_WORK
         and BASELINE['diagnostic_records'] + calls <= DIAGNOSTIC_RECORDS,
         'all-attempt work/call ceilings include every shadow, retry, partial and unknown reservation')
    if kind == 'standalone':
        need(counts['standalone_work_rows'] + cap <= MAX_STANDALONE
             and counts['standalone_records'] + 1 <= MAX_STANDALONE_RECORDS,
             'standalone native control/restart suballocation')
    else:
        need(counts['production_records'] + 1 <= MAX_PRODUCTION_RECORDS
             and counts['levels'][level_id]['success_or_pending_work_rows'] + cap <= SUCCESS_CAPS[level_id]
             and counts['rejected_work_rows'] + cap <= MAX_REJECTED,
             'shared production record pool, own-level successful-work and bounded rejection reserves')
    return True


def guard_bindings(plan=None):
    plan = read(PLAN) if plan is None else plan
    return dict(design_sha256=sha(PLAN), source_mapping_sha256=digest(plan['source_files']),
                physical_input_mapping_sha256=digest(plan['physical_inputs']))


def verify_guard_bindings(guard, plan=None):
    expected = guard_bindings(plan)
    need(all(guard.get(key) == value for key, value in expected.items()),
         'sealed guard binds immutable PLAN and complete source/input mapping digests')


def production_classification(packet):
    """One-packet exact classification; never retain a campaign branch map.

    Production may end only after a complete macro decision. Explicit phase or
    odd-row interruptions belong exclusively to discarded native controls.
    Every original C/F1/F2 observation and branch ID remains in the raw packet.
    """
    need(packet['status'] in ('paused_controller', 'present_at_horizon')
         and packet['cursor_before']['phase'] in ('idle', 'after_rejection')
         and packet['cursor_after']['phase'] in ('idle', 'after_rejection')
         and not packet['carried_branches'] and not packet['checkpoint']['pending_branches']
         and packet['checkpoint']['physical_checkpoint']['state']['pending_trial'] is None,
         'production requires complete pair/decision boundaries without carried or pending branches')
    branches = packet['work_branches']; by_id = {b['branch_id']: b for b in branches}
    need(len(by_id) == len(branches) and branches, 'unique nonempty current production branch inventory')
    classified, committed, rejected = {}, [], set()
    for trial in packet['trials']:
        ids, decision = trial['branch_ids'], trial['decision']
        need(len(ids) == 3 and decision is not None and all(key in by_id and key not in classified for key in ids)
             and [by_id[key]['role'] for key in ids] == ['C', 'F1', 'F2'],
             'complete unique original C/F1/F2 trial classification')
        action = decision['action']
        need(action in ('commit_literal_halves', 'discard_all_and_halve'), 'declared complete supplemental decision')
        for key in ids:
            b = by_id[key]
            need(b['error'] is None and b['work_rows'] == len(b['rows']) == 1,
                 'positive original physical branch is one complete zero-rejection step')
            classified[key] = 'accuracy_rejected' if action == 'discard_all_and_halve' else ('coarse_shadow' if b['role'] == 'C' else 'committed_half')
        if action == 'discard_all_and_halve':
            rejected.update(ids)
        else:
            committed.extend(ids[1:])
    need(set(classified) == set(by_id) and packet['committed_branch_ids'] == committed
         and len(packet['accepted_rows']) == len(committed), 'no unclassified, duplicated or promoted production branch')
    all_work = sum(b['work_rows'] for b in branches)
    rejected_work = sum(by_id[key]['work_rows'] for key in rejected)
    rows = [dict(branch_id=b['branch_id'], role=b['role'], work_rows=b['work_rows'],
                 accepted_rows=len(b['rows']), disposition=classified[b['branch_id']]) for b in branches]
    result = dict(all_work_rows=all_work, success_work_rows=all_work-rejected_work,
        rejected_work_rows=rejected_work, committed_half_rows=len(committed),
        coarse_shadow_work_rows=sum(b['work_rows'] for b in branches if b['role'] == 'C'),
        discarded_diagnostic_work_rows=all_work-len(committed),
        raw_branch_classification_sha256=digest(rows), complete_production_boundary=True)
    need(packet['work_rows'] == all_work, 'exact native all-work classification')
    validate_production_aggregate(result, all_work)
    return result


def validate_production_aggregate(value, work_rows):
    names = ('all_work_rows', 'success_work_rows', 'rejected_work_rows', 'committed_half_rows',
             'coarse_shadow_work_rows', 'discarded_diagnostic_work_rows')
    need(set(value) == {*names, 'raw_branch_classification_sha256', 'complete_production_boundary'}
         and all(type(value[key]) is int and 0 <= value[key] <= work_rows for key in names)
         and value['all_work_rows'] == work_rows
         and value['success_work_rows'] + value['rejected_work_rows'] == work_rows
         and 2 * value['success_work_rows'] == 3 * value['committed_half_rows']
         and 3 * value['coarse_shadow_work_rows'] == work_rows
         and value['discarded_diagnostic_work_rows'] == work_rows-value['committed_half_rows']
         and is_sha(value['raw_branch_classification_sha256'])
         and value['complete_production_boundary'] is True,
         'bounded compact production aggregates preserve exact row partition')


def verify_production_aggregate(packet, admission):
    actual = production_classification(packet)
    need(admission['production_aggregate'] == actual,
         'complete raw post-replay rederives exact admitted production aggregate and branch-classification digest')
    return actual


def ledger():
    """Authenticate decisions, exact packet bindings and all reservations.

    Production has complete pair/decision boundaries and sealed constant-size
    row partitions. FULL post-exit replay rederives every partition/digest from
    retained raw branches. Native controls alone may carry pending branches;
    their ALL work is discarded and does not require a global branch map.
    """
    counts = empty_counts()
    files = sorted((OUT / 'reservations').glob('*.json'))
    need([p.stem for p in files] == [f'{i:06d}' for i in range(1, len(files) + 1)], 'contiguous complete global reservation inventory')
    for index, path in enumerate(files, 1):
        reservation = read(path)
        key, kind, cap = (reservation[k] for k in ('level_id', 'kind', 'maximum_work_rows'))
        need(reservation['index'] == index and reservation['design_sha256'] == sha(PLAN)
             and key in LEVELS and kind in ('production', 'standalone')
             and type(cap) is int and 0 < cap <= PACKET_CAP, 'bounded original reservation metadata')
        label = reservation['label']
        need(isinstance(label, str) and Path(label).name == label and label not in counts['labels'], 'unique safe immutable record label')
        counts['labels'].append(label); counts['records'] += 1
        counts['production_records' if kind == 'production' else 'standalone_records'] += 1
        warm_cap = reservation.get('maximum_nonadvancing_kernel_invocations', 0)
        need(type(warm_cap) is int and warm_cap in (0, 2), 'explicit separate nonadvancing warm reservation')
        folder = OUT / 'records' / label
        admission_path = OUT / 'admissions' / path.stem / 'results.json'
        admission = None
        if admission_path.exists() or admission_path.with_name('completion.json').exists():
            try:
                admission = sealed(admission_path, positive=True)
                need(admission['reservation_sha256'] == sha(path)
                     and all(admission[k] == reservation[k] for k in ('index', 'level_id', 'kind', 'label')),
                     'admission belongs to exact reservation')
                # Prospective receipt-chain schedule: authenticate every prior
                # admission/completion and guard metadata now, immediate parent
                # raw before continuation, and EVERY raw in complete post-exit
                # mechanical replay. This is not an old finalizer promotion.
                verify_mapping(admission['chain_metadata'])
                need(all(Path(name).is_file() for name in admission['artifacts']), 'complete immutable raw inventory exists')
                guard = sealed(folder / 'policy_mechanical_audit_01/results.json', positive=True)
                verify_guard_bindings(guard)
                need(admission['audit_sha256'] == sha(folder / 'policy_mechanical_audit_01/results.json')
                     and guard['passed'] is True and (guard.get('independent_mechanical_replay_performed') is True
                         or guard.get('zero_particle_work_arithmetic_setup') is True and admission['work_rows'] == 0),
                     'actual independent mechanical/policy audit, not producer declaration')
                need(admission['work_rows'] == guard['work_rows']
                     and type(admission['work_rows']) is int and 0 <= admission['work_rows'] <= cap,
                     'exact all-work row charge')
                if kind == 'production':
                    validate_production_aggregate(admission['production_aggregate'], admission['work_rows'])
                    need(guard['production_aggregate_sha256'] == digest(admission['production_aggregate']),
                         'compact production partition is linked to actual independent current-packet audit')
            except Exception:
                admission = None
        if admission is None:
            known = None
            account = folder / 'accounting.json'
            try:
                value = read(account)
                if (value.get('actual_work_known') is True and type(value.get('work_rows')) is int
                        and 0 <= value['work_rows'] and value.get('packet_sha256') == sha(folder / 'packet.json.xz')):
                    wire = json.loads(lzma.decompress((folder / 'packet.json.xz').read_bytes(), format=lzma.FORMAT_XZ))
                    if wire['packet']['work_rows'] == value['work_rows']:
                        known = value['work_rows']
                elif (value.get('actual_work_known') is True and type(value.get('work_rows')) is int
                        and value['work_rows'] >= 0 and value.get('smoke_sha256') == sha(folder / 'smoke.json.xz')):
                    wire = json.loads(lzma.decompress((folder / 'smoke.json.xz').read_bytes(), format=lzma.FORMAT_XZ))
                    if wire['work_rows'] == value['work_rows']:
                        known = value['work_rows']
            except Exception:
                pass
            n = cap if known is None else known
            if known is not None and known > cap:
                counts['known_cap_overruns'].append(dict(label=label, actual_known_work_rows=known, reserved_cap=cap))
            counts['unknown_reserved_work_upper_bound' if known is None else 'known_unaccepted_work_rows'] += n
            counts['unresolved'].append(dict(reservation=reservation, known_work_rows=known,
                conservative_work_charge=n, admission_not_authenticated=True))
            counts['nonadvancing_kernel_invocations'] += warm_cap
            counts['unknown_nonadvancing_kernel_invocations_upper_bound'] += warm_cap
        else:
            need(not counts['unresolved'], 'no later admission may hide earlier unresolved work')
            n = admission['work_rows']; counts['accepted_all_work_rows'] += n
            warm = admission.get('nonadvancing_kernel_invocations', 0)
            need(type(warm) is int and warm == warm_cap, 'actual authenticated nonadvancing warm count')
            counts['nonadvancing_kernel_invocations'] += warm
            counts['known_nonadvancing_kernel_invocations'] += warm
            if kind == 'production':
                row = counts['levels'][key]; row['work_rows'] += n; row['labels'].append(label)
                aggregate = admission['production_aggregate']
                row['success_or_pending_work_rows'] += aggregate['success_work_rows']
                row['rejected_work_rows'] += aggregate['rejected_work_rows']
                row['committed_half_rows'] += aggregate['committed_half_rows']
                counts['discarded_diagnostic_work_rows'] += aggregate['discarded_diagnostic_work_rows']
        counts['work_rows'] += n
        if kind == 'standalone':
            counts['standalone_work_rows'] += n
    for key in LEVELS:
        row = counts['levels'][key]
        need(row['committed_half_rows'] <= COMMITTED_HALF_CAPS[key], 'explicit prospective committed-half ceiling')
        counts['accepted_committed_half_rows'] += row['committed_half_rows']
        counts['rejected_work_rows'] += row['rejected_work_rows']
    counts['discarded_diagnostic_work_rows'] += counts['standalone_work_rows']
    counts['diagnostic_records'] = counts['records']  # Conservative possible-discarded call allocation.
    counts['ledger_authenticated'] = True
    counts['conservative_nonadvancing_kernel_invocations_charge'] = counts['nonadvancing_kernel_invocations']
    counts['actual_nonadvancing_kernel_invocations'] = (counts['known_nonadvancing_kernel_invocations']
        if counts['unknown_nonadvancing_kernel_invocations_upper_bound'] == 0 else None)
    counts['nonadvancing_charge_semantics'] = 'known authenticated invocations plus unresolved reserved upper bounds; never an unobserved actual count'
    need(counts['nonadvancing_kernel_invocations'] <= MAX_NONADVANCING_KERNEL_INVOCATIONS,
         'separate maximum22 nonadvancing synthetic contact-kernel invocations')
    need(len(counts['unresolved']) <= 1, 'one unverified native packet')
    need({p.name for p in (OUT / 'records').iterdir() if p.is_dir()} <= set(counts['labels'])
         if (OUT / 'records').exists() else True, 'no unreserved native output')
    return counts


def failed_ledger(error):
    """Negative preservation only; never used to dispatch or admit evidence."""
    paths = sorted((OUT / 'reservations').glob('*.json'))
    readable, warm_upper, failures = 0, 0, []
    for path in paths:
        try:
            value = read(path); cap = value['maximum_work_rows']
            need(type(cap) is int and 0 < cap <= PACKET_CAP, 'readable bounded reservation')
            readable += cap
            warm_upper += value.get('maximum_nonadvancing_kernel_invocations', 0)
        except Exception as exc:
            failures.append(dict(path=str(path), error=repr(exc)))
    return dict(ledger_authenticated=False, error=repr(error), accepted_work_asserted=False,
        accepted_all_work_rows=0, known_unaccepted_work_rows=None,
        unknown_reserved_work_upper_bound=None,
        readable_reservation_cap_sum=readable, unknown_or_unverifiable_work=True,
        records=len(paths), unreadable_reservations=failures,
        actual_nonadvancing_kernel_invocations=None,
        unknown_nonadvancing_kernel_invocations_upper_bound=warm_upper if not failures else None,
        authorized_new_work_ceiling=MAX_WORK, authorized_record_ceiling=MAX_RECORDS,
        authorization_or_success_inference_forbidden=True)


def replay_reserve(counts, audited_levels=()):
    p = read(PLAN); rule = p['frozen_replay_reserve_rule']
    rate, fixed = effective_replay_rate(), rule['fixed_closure_seconds']
    need(type(rate) in (float, int) and rate >= .01 and type(fixed) in (float, int) and fixed >= 3600,
         'positive frozen independently justified complete-replay reserve rule')
    rows = sum(value['work_rows'] for key, value in counts['levels'].items() if key not in audited_levels)
    # Standalone paths also receive complete independent post-exit replay.
    return rows * rate + counts['standalone_work_rows'] * rate + fixed


def effective_replay_rate():
    rate = read(PLAN)['frozen_replay_reserve_rule']['seconds_per_unreplayed_all_work_row']
    need(type(rate) in (int, float) and rate >= .01, 'fixed conservative .01s/all-work replay-rate floor')
    for path in sorted((OUT / 'admissions').glob('*/results.json')):
        admission = sealed(path, positive=True)
        n, elapsed = admission['work_rows'], admission.get('independent_replay_seconds')
        reservation = read(OUT / 'reservations' / f"{admission['index']:06d}.json")
        if (admission['kind'] == 'production' and n >= reservation['maximum_work_rows'] / 2
                and n > 0 and elapsed is not None):
            need(type(elapsed) in (float, int) and math.isfinite(elapsed) and elapsed >= 0,
                 'actual complete same-source independent audit timing')
            rate = max(rate, 2 * elapsed / n)
    for path in sorted((OUT / 'cost_observations').glob('*/results.json')):
        observation = sealed(path, positive=True)
        need(observation['design_sha256'] == sha(PLAN), 'same-source observed replay reserve')
        rate = max(rate, observation['conservative_replay_seconds_per_work_row'])
    return rate


def window_bounds(plan, now, index, reserve_s):
    need(type(index) is int and 1 <= index <= MAX_WINDOWS, 'at most10 remaining numerical windows, plus the closed first window')
    start, cutoff, end = (instant(plan[k]) for k in ('start_utc', 'simulation_cutoff_utc', 'end_utc'))
    need(start <= now < cutoff < end and 0 < reserve_s < end - now, 'remaining shared replay/closure time')
    stop = min(now + MAX_WINDOW_S, cutoff, end - reserve_s)
    need(stop - now > 2 * NATIVE_S + 120, 'bounded native record and retirement before fixed window cutoff')
    return stop


def source_interfaces():
    """Source-only structural readiness, never synthetic native qualification."""
    wanted = {RUNTIME: ('build_runtime', 'controller_checkpoint', 'materialize_checkpoint', 'trace_rows',
                       'packet_summary', 'numeric_restart_signature', 'native_execution_scope',
                       'native_stack_prelude', 'native_single_branch_smoke'),
              AUDITOR: ('audit_runtime_packet', 'audit_original_smoke_record'),
              RESTART: ('first_active_split', 'observation', 'compare')}
    missing = []
    for path, names in wanted.items():
        if not path.exists():
            missing.append(str(path)); continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        present = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        missing.extend(str(path) + ':' + name for name in names if name not in present)
    return dict(all_required_interfaces_present=not missing, missing=missing,
        native_mechanical_qualification_claimed=False, native_restart_qualification_claimed=False,
        new_native_calls=0, numerical_launch_ready=False)


def load_engine():
    """Called only by an approved numerical worker or bounded independent replay."""
    if str(STAGING) not in sys.path:
        sys.path.insert(0, str(STAGING))
    return (importlib.import_module('full_state_integration_adapter_v2'),
            importlib.import_module('audit_full_state_stepdoubling_v1'),
            importlib.import_module('prepare_stepdoubling_restart_v1'),
            importlib.import_module('full_state_stepdoubling_v1'))


def definitions():
    proposal, physical = read(PROPOSAL), read(PHYSICAL)
    levels = {item['level_id']: item for item in proposal['levels']}
    cases = {item['level_id']: item for item in physical['cases']}
    return {key: dict(**levels[key], case=cases[key]) for key in LEVELS}


def show_state(phase, **extra):
    """Mutable UI projection only; immutable receipts/ledger remain authoritative."""
    path = OUT / 'state.json'; path.parent.mkdir(parents=True, exist_ok=True)
    value = dict(phase=phase, utc=utc(), **extra)
    temporary = path.with_suffix('.writing')
    temporary.write_text(json.dumps(value, sort_keys=True, allow_nan=True), encoding='utf-8')
    os.replace(temporary, path)


def load_reference(reference, cache=None):
    """Reconstruct a FULL controller boundary from its exact six-field chain."""
    if reference is None:
        return None, None, []
    cache = {} if cache is None else cache
    key = digest(reference)
    if key in cache:
        value = cache[key]
        need(sha(reference['path']) == reference['compressed_sha256'], 'fresh cached raw boundary identity')
        return value
    # Iterative chain reconstruction avoids Python recursion and retaining a
    # separate growing FULL history for every earlier packet in memory.
    pending, cursor, seen = [], reference, set()
    while cursor is not None and digest(cursor) not in cache:
        identity = digest(cursor)
        need(identity not in seen and len(pending) <= MAX_RECORDS, 'bounded acyclic raw prefix ancestry')
        seen.add(identity)
        path = Path(cursor['path'])
        need(path.resolve().is_relative_to(OUT.resolve()) and sha(path) == cursor['compressed_sha256'], 'fresh task-owned raw boundary')
        wire = json.loads(lzma.decompress(path.read_bytes(), format=lzma.FORMAT_XZ))
        marker = wire['packet']['checkpoint']['physical_checkpoint']['state']['history']
        pending.append(cursor); cursor = marker['parent']
    if cursor is None:
        result = (None, None, [])
    else:
        need(sha(cursor['path']) == cursor['compressed_sha256'], 'immediate cached parent raw bytes')
        result = cache[digest(cursor)]
    for current in reversed(pending):
        packet = load_packet(current['path'], current, result[1], result[2])
        result = (packet['checkpoint'], current, packet['checkpoint']['physical_checkpoint']['state']['history'])
        cache_put(cache, digest(current), result)
    return result


def cache_put(cache, key, value):
    cache.pop(key, None); cache[key] = value
    while len(cache) > 4:
        del cache[next(iter(cache))]


def process_identity(process, command):
    import psutil
    observed = psutil.Process(process.pid)
    birth, actual = observed.create_time(), observed.cmdline()
    need(process.poll() is None and actual == command, 'original live Popen handle and exact full command')
    return dict(pid=process.pid, created=birth, command=actual, design_sha256=sha(PLAN), utc=utc())


def start_child(arguments, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    command = [str(PYTHON), '-B', '-u', str(SELF), *arguments]
    stdout = (folder / 'stdout.log').open('xb'); stderr = (folder / 'stderr.log').open('xb')
    process = subprocess.Popen(command, cwd=ROOT, env=os.environ.copy(), stdout=stdout, stderr=stderr,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    launch, errors = None, []
    try:
        for _ in range(3):
            try:
                launch = process_identity(process, command); break
            except Exception as exc:
                errors.append(repr(exc))
                if process.poll() is not None:
                    break
                time.sleep(.05)
        need(launch is not None, 'exact child birth/full-command registration before any work')
        commit(folder / 'launch.json', launch)
        return dict(process=process, launch=launch, stdout=stdout, stderr=stderr, folder=folder,
                    identity_capture_errors=errors)
    except BaseException:
        # Recapture only through the ORIGINAL still-live Popen handle.  Denied
        # birth/command never becomes permission to terminate a PID blindly.
        try:
            launch = launch or process_identity(process, command)
            if process.poll() is None:
                exact_stop(process, launch)
        except Exception as exc:
            errors.append(repr(exc))
        stdout.close(); stderr.close()
        commit(folder / 'registration_failure.json', dict(passed=False, launch=launch,
            identity_errors=errors, direct_popen_returncode=process.poll(),
            unresolved_identity=launch is None or not inspect_identity(launch)['retired'],
            logs_intentionally_unsealed=True, utc=utc()))
        raise


def finish_child(handle, *, request_stop=False, timeout=15.):
    process, launch, folder = handle['process'], handle['launch'], handle['folder']
    forced, code, errors = False, None, []
    try:
        if process.poll() is None and request_stop:
            exact_stop(process, launch); forced = True
        code = process.wait(timeout=timeout)
    except Exception as exc:
        errors.append(repr(exc))
        if process.poll() is None:
            try:
                exact_stop(process, launch); forced = True
                code = process.wait(timeout=5)
            except Exception as stopping:
                errors.append(repr(stopping))
    finally:
        handle['stdout'].close(); handle['stderr'].close()
    try:
        identity = inspect_identity(launch)
    except Exception as exc:
        identity = dict(retired=False, unresolved_identity=True, error=repr(exc))
    retired = identity.get('retired') is True
    result = dict(returncode=code, forced=forced, launch=launch, inspection=identity,
        retirement_verified=retired, identity_errors=errors,
        actual_returncode_observed_from_original_popen_handle=code is not None,
        logs={str(p): sha(p) for p in folder.glob('*.log')} if retired else {},
        live_logs_intentionally_unsealed=not retired, utc=utc())
    commit(folder / 'exit.json', result)
    need(retired, 'unresolved exact child identity; no successor or final success')
    return result


def register_self(path):
    import psutil
    limit = time.time() + 5
    while not Path(path).exists() and time.time() < limit:
        time.sleep(.02)
    expected = read(path)
    me = psutil.Process()
    need(expected['pid'] == me.pid and expected['created'] == me.create_time()
         and expected['command'] == me.cmdline(), 'only exact owner-registered process may execute this role')
    me.cpu_affinity([14])
    return expected


def worker(index):
    """Persistent window worker: one bounded native packet, then wait for owner."""
    window = OUT / 'windows' / f'window_{index:03d}'
    register_self(window / 'launch.json')
    p = authority(True, refresh_sources=True)
    ready_until = time.time() + 5
    while not (window / 'window.json').exists() and time.time() < ready_until:
        time.sleep(.02)
    window_plan = read(window / 'window.json')
    need(window_plan['design_sha256'] == sha(PLAN)
         and instant(window_plan['cutoff_utc']) <= instant(p['simulation_cutoff_utc']), 'fixed source-bound numerical window')
    engine, auditor, restart, kernel = load_engine()
    cache = {}
    next_index = 1
    setup_authenticated = False
    while time.time() < instant(window_plan['cutoff_utc']):
        if (window / 'stop.json').exists():
            break
        request_path = window / 'requests' / f'{next_index:06d}.json'
        if not request_path.exists():
            time.sleep(.05); continue
        request = read(request_path)
        authority(True, refresh_sources=True)
        need(request['window'] == index and request['window_request_index'] == next_index
             and request['design_sha256'] == sha(PLAN)
             and sha(OUT / 'reservations' / f"{request['global_index']:06d}.json") == request['reservation_sha256'],
             'owner-reserved exact native request')
        record = OUT / 'records' / request['label']
        before, parent_prefix, parent_history = load_reference(request['input_prefix'], cache)
        need(digest(before) == request['input_controller_sha256'], 'FULL controller input, not a copied easier seed')
        operation = request.get('operation', 'packet')
        need(operation in ('prelude', 'packet', 'smoke_original', 'smoke_compiled'), 'declared bounded native operation')
        case = definitions()[request['level_id']]['case']
        limits = kernel.Limits(**definitions()[request['level_id']]['limits'])
        marker = window / 'markers' / f'{next_index:06d}'
        marker.mkdir(parents=True, exist_ok=False)
        started = False
        try:
            last_resource_check = [0.]
            def dispatch_gate():
                now = time.time()
                need(now < request['time_bound_epoch'] and now < instant(window_plan['cutoff_utc'])
                     and now < instant(p['simulation_cutoff_utc']), 'actual per-step native/window cutoff')
                if now - last_resource_check[0] >= 1.:
                    resource_guard(); last_resource_check[0] = now
                return dict(native_dispatch_authorized=True, design_sha256=request['design_sha256'],
                    reservation_sha256=request['reservation_sha256'], simulation_cutoff_utc=p['simulation_cutoff_utc'],
                    native_prelude_authorized=operation == 'prelude', native_stack_prelude_authenticated=setup_authenticated,
                    native_smoke_authorized=operation.startswith('smoke_'))
            if operation == 'prelude':
                need(before is None and request['kind'] == 'standalone' and not setup_authenticated,
                     'one explicit registered zero-particle arithmetic prelude per window')
                commit(marker / 'native_start.json', dict(request_sha256=sha(request_path),
                    monotonic=time.monotonic(), utc_epoch=time.time(), utc=utc()))
                started = True
                setup = engine.native_stack_prelude(dispatch_gate)
                commit(marker / 'native_finish.json', dict(request_sha256=sha(request_path),
                    monotonic=time.monotonic(), utc_epoch=time.time(), utc=utc()))
                need(setup['particle_steps'] == 0 and setup['native_qualification_passed'] is False,
                     'arithmetic setup is not physical/native qualification')
                need(setup['nonadvancing_contact_kernel_invocations'] == 2
                     and setup['target_outer_transport_calls'] == 0,
                     'original two synthetic contact warm invocations separately disclosed and charged')
                record.mkdir(parents=True, exist_ok=False)
                commit(record / 'arithmetic_setup.json', setup)
                commit(marker / 'response.json', dict(passed=True, zero_particle_work_arithmetic_setup=True,
                    setup_sha256=sha(record / 'arithmetic_setup.json'), request_sha256=sha(request_path), utc=utc()))
            elif operation.startswith('smoke_'):
                need(setup_authenticated and before is None and request['kind'] == 'standalone'
                     and request['maximum_work_rows'] == 32, 'fresh32-substep discarded original-bit smoke')
                commit(marker / 'native_start.json', dict(request_sha256=sha(request_path),
                    monotonic=time.monotonic(), utc_epoch=time.time(), utc=utc()))
                started = True
                smoke = engine.native_single_branch_smoke(case['spec'], case['binding'], dispatch_gate,
                    mode=operation.removeprefix('smoke_'), rows=32,
                    plan_path=PLAN, auth_path=AUTH, physical_path=PHYSICAL, limits=limits)
                commit(marker / 'native_finish.json', dict(request_sha256=sha(request_path),
                    monotonic=time.monotonic(), utc_epoch=time.time(), utc=utc()))
                need(smoke['work_rows'] == 32 and len(smoke['record']['rows']) == 32
                     and smoke['physical_checkpoint'] == smoke['record']['result']['checkpoint'], 'complete original single-branch smoke')
                record.mkdir(parents=True, exist_ok=False)
                with (record / 'smoke.json.xz').open('xb') as stream:
                    stream.write(lzma.compress((json.dumps(smoke, sort_keys=True, indent=2, allow_nan=True) + '\n').encode(),
                                              format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64, preset=6))
                commit(record / 'accounting.json', dict(actual_work_known=True, work_rows=32,
                    smoke_sha256=sha(record / 'smoke.json.xz'), operation=operation, utc=utc()))
                commit(marker / 'response.json', dict(passed=True, work_rows=32,
                    smoke_sha256=sha(record / 'smoke.json.xz'), request_sha256=sha(request_path), utc=utc()))
            else:
                need(setup_authenticated, 'registered arithmetic setup admitted before physical dispatch')
                with engine.native_execution_scope(case['spec'], case['binding'], dispatch_gate=dispatch_gate,
                        plan_path=PLAN, auth_path=AUTH, physical_path=PHYSICAL, numerical=True) as scope:
                    need(scope['native_setup_force_calls'] == 0,
                         'no hidden native warm/force calls outside separately charged verification packets')
                    runtime = scope['runtime']
                    need(time.time() + NATIVE_S < request['time_bound_epoch'],
                         'complete45s native allowance remains after scope/input preparation')
                    commit(marker / 'native_start.json', dict(request_sha256=sha(request_path),
                        monotonic=time.monotonic(), utc_epoch=time.time(), utc=utc()))
                    started = True
                    packet = runtime.advance_packet(before, limits,
                        max_work_rows=request['maximum_work_rows'],
                        pause_after_accepted_rows=request.get('pause_after_accepted_rows'),
                        pause_after_time_s=request.get('pause_after_time_s'),
                        time_bound=request['time_bound_epoch'], record_id=request['label'],
                        pause_at_phase=request.get('pause_at_phase'),
                        previous_packet_receipt_sha256=request.get('previous_packet_receipt_sha256'))
                    commit(marker / 'native_finish.json', dict(request_sha256=sha(request_path),
                        monotonic=time.monotonic(), utc_epoch=time.time(), utc=utc()))
                need(packet['record_id'] == request['label'] and packet['reservation']['maximum_work_rows'] == request['maximum_work_rows'],
                     'literal returned native packet identity/cap')
                prefix = store_packet(record, packet, parent_prefix, parent_history)
                write_trace(record / 'trace.npy', engine.trace_rows(packet))
                summary = engine.packet_summary(packet)
                commit(record / 'accounting.json', dict(actual_work_known=True, work_rows=summary['work_rows'],
                    packet_sha256=sha(record / 'packet.json.xz'), summary=summary,
                    native_force_attempt_count=summary['work_rows'], utc=utc()))
                cache_put(cache, digest(prefix), (packet['checkpoint'], prefix, packet['checkpoint']['physical_checkpoint']['state']['history']))
                commit(marker / 'response.json', dict(passed=packet['status'] != 'negative',
                    raw_sha256=sha(record / 'packet.json.xz'), prefix=prefix, summary=summary,
                    request_sha256=sha(request_path), native_started=started, utc=utc()))
        except BaseException as exc:
            # Missing raw means the full pre-reserved cap remains UNKNOWN.  A
            # partial producer exception never becomes a zero-work admission.
            commit(marker / 'failure.json', dict(passed=False, error=repr(exc), traceback=traceback.format_exc(),
                native_started=started, work_is_unknown_unless_authenticated_raw_exists=True,
                dependent_dispatch_stopped=True, utc=utc()))
            raise
        # No dependent native request is dispatched until the owner has sealed
        # the independent current-packet audit/admission or stopped this worker.
        decision = marker / 'owner_decision.json'
        while not decision.exists():
            if (window / 'stop.json').exists() or time.time() >= instant(window_plan['cutoff_utc']):
                return
            time.sleep(.05)
        need(read(decision).get('admitted') is True, 'owner independent audit failed; no next native packet')
        if operation == 'prelude':
            setup_authenticated = True
        next_index += 1


class Execution:
    """Administrative owner; no physical advancement occurs in this class."""
    def __init__(self):
        self.plan = authority(False, refresh_sources=True)
        self.handle = None
        self.window_index = 0
        self.window_request = 0
        self.window_stop = None
        self.audited_levels = set()
        self.reference_cache = {}
        self.engine = self.auditor = self.restart = self.kernel = None
        self.setup_complete = False

    def imports(self):
        if self.engine is None:
            self.engine, self.auditor, self.restart, self.kernel = load_engine()

    def close_window(self):
        if self.handle is None:
            return None
        folder = self.handle['folder']
        if not (folder / 'stop.json').exists():
            commit(folder / 'stop.json', dict(requested_by_owner=True, utc=utc()))
        marker = folder / 'markers' / f'{self.window_request:06d}'
        outstanding = ((folder / 'requests' / f'{self.window_request:06d}.json').exists()
                       and not (marker / 'native_finish.json').exists())
        result = finish_child(self.handle, request_stop=outstanding, timeout=15.)
        self.handle = None
        self.setup_complete = False
        need(result['returncode'] == 0 and result['forced'] is False, 'actual successful unforced window retirement')
        return result

    def ensure_window(self, level_id='f0p0625', kind='standalone', cap=1):
        counts = ledger()
        prospective = copy.deepcopy(counts)
        if kind == 'production':
            prospective['levels'][level_id]['work_rows'] += cap
        else:
            prospective['standalone_work_rows'] += cap
        reserve = replay_reserve(prospective, self.audited_levels)
        now = time.time()
        if self.handle is not None and (now + 2 * NATIVE_S + 180 >= self.window_stop
                or self.handle['process'].poll() is not None):
            self.close_window()
        if self.handle is None:
            # Even an idle new Popen is disallowed after resource exhaustion.
            # Reserve room for its explicit setup AND the intended first work.
            budget_guard(counts, level_id, 'standalone', 1)
            virtual = copy.deepcopy(counts)
            virtual['records'] += 1; virtual['standalone_records'] += 1
            virtual['work_rows'] += 1; virtual['standalone_work_rows'] += 1
            virtual['nonadvancing_kernel_invocations'] += 2
            budget_guard(virtual, level_id, kind, cap)
            self.window_index += 1
            self.window_request = 0
            self.window_stop = window_bounds(self.plan, now, self.window_index, reserve)
            folder = OUT / 'windows' / f'window_{self.window_index:03d}'
            # Child requires owner registration; the plan is written before it
            # can receive any native request. start_child owns folder creation.
            self.handle = start_child(['worker', str(self.window_index)], folder)
            commit(folder / 'window.json', dict(index=self.window_index, design_sha256=sha(PLAN),
                start_utc=utc(), cutoff_utc=datetime.fromtimestamp(self.window_stop, timezone.utc).isoformat(),
                maximum_duration_s=MAX_WINDOW_S, complete_replay_and_closure_reserve_s=reserve,
                unchanged_fixed_shared_end_utc=self.plan['end_utc']))
            self.setup_complete = False
        return self.handle['folder']

    def packet(self, level_id, kind, label, input_prefix=None, *, cap=PACKET_CAP,
               pause_rows=None, pause_time=None, phase=None, previous_receipt=None, operation='packet'):
        owner_started = time.perf_counter()
        authority(True, refresh_sources=True)
        counts = ledger(); budget_guard(counts, level_id, kind, cap)
        if operation == 'prelude':
            need(counts['nonadvancing_kernel_invocations'] + 2 <= MAX_NONADVANCING_KERNEL_INVOCATIONS,
                 'remaining separately authorized nonadvancing warm budget')
        folder = self.ensure_window(level_id, kind, cap)
        if not self.setup_complete and operation != 'prelude':
            self.packet(level_id, 'standalone', f'w{self.window_index:03d}_arithmetic_setup', cap=1, operation='prelude')
            counts = ledger(); budget_guard(counts, level_id, kind, cap)
        self.imports()
        before, parent_prefix, history = load_reference(input_prefix, self.reference_cache)
        index = counts['records'] + 1
        prospective = copy.deepcopy(counts)
        if kind == 'production':
            prospective['levels'][level_id]['work_rows'] += cap
        else:
            prospective['standalone_work_rows'] += cap
        reserve = replay_reserve(prospective, self.audited_levels)
        time_bound = min(self.window_stop, instant(self.plan['simulation_cutoff_utc']),
                         instant(self.plan['end_utc']) - reserve)
        need(time.time() + 2 * NATIVE_S + 120 < time_bound, 'native, audit and retirement reserve before every dispatch')
        reservation = dict(index=index, level_id=level_id, kind=kind, label=label,
            maximum_work_rows=cap, design_sha256=sha(PLAN), window=self.window_index,
            maximum_nonadvancing_kernel_invocations=2 if operation == 'prelude' else 0,
            input_prefix=input_prefix, input_controller_sha256=digest(before),
            previous_packet_receipt_sha256=previous_receipt, utc=utc())
        reserve_path = OUT / 'reservations' / f'{index:06d}.json'
        commit(reserve_path, reservation)
        self.window_request += 1
        request = dict(**reservation, global_index=index, window_request_index=self.window_request,
            reservation_sha256=sha(reserve_path), time_bound_epoch=time_bound,
            pause_after_accepted_rows=pause_rows, pause_after_time_s=pause_time, pause_at_phase=phase, operation=operation)
        request_path = folder / 'requests' / f'{self.window_request:06d}.json'
        commit(request_path, request)
        marker = folder / 'markers' / f'{self.window_request:06d}'
        response_path = marker / 'response.json'
        while not response_path.exists():
            now = time.time()
            need(self.handle['process'].poll() is None, 'native window exited before complete raw response; reserved work retained')
            if (marker / 'native_start.json').exists() and not (marker / 'native_finish.json').exists():
                began = read(marker / 'native_start.json')
                if now - began['utc_epoch'] >= NATIVE_S:
                    finish_child(self.handle, request_stop=True)
                    self.handle = None
                    raise RuntimeError('Actual native45s limit; exact worker stopped, raw/unresolved reservation preserved')
            if now >= time_bound:
                finish_child(self.handle, request_stop=True)
                self.handle = None; self.setup_complete = False
                raise RuntimeError('Packet/window/shared cutoff: exact worker stopped, all raw/unresolved work preserved')
            if (marker / 'failure.json').exists():
                raise RuntimeError('Native packet failure: ' + read(marker / 'failure.json')['error'])
            time.sleep(.05)
        response = read(response_path)
        start, stop = read(marker / 'native_start.json'), read(marker / 'native_finish.json')
        need(response['request_sha256'] == sha(request_path) == start['request_sha256'] == stop['request_sha256']
             and 0 <= stop['monotonic'] - start['monotonic'] <= NATIVE_S,
             'actual monotonic native45s markers bind exact request')
        raw_folder = OUT / 'records' / label
        if operation == 'prelude':
            setup_path = raw_folder / 'arithmetic_setup.json'; setup = read(setup_path)
            need(response['zero_particle_work_arithmetic_setup'] is True
                 and response['setup_sha256'] == sha(setup_path) and setup['particle_steps'] == 0
                 and setup['native_qualification_passed'] is False
                 and setup['nonadvancing_contact_kernel_invocations'] == 2 and setup['target_outer_transport_calls'] == 0,
                 'authenticated zero-particle arithmetic setup with two separately charged synthetic kernel invocations')
            seal(raw_folder / 'policy_mechanical_audit_01', dict(passed=True, work_rows=0,
                zero_particle_work_arithmetic_setup=True, independent_mechanical_replay_performed=False,
                setup_sha256=sha(setup_path), **guard_bindings(self.plan), utc=utc()))
            artifacts = {str(path): sha(path) for path in raw_folder.rglob('*') if path.is_file()}
            metadata = {name: value for name, value in artifacts.items() if not name.endswith('.xz')}
            seal(OUT / 'admissions' / f'{index:06d}', dict(passed=True, index=index, level_id=level_id,
                kind=kind, label=label, work_rows=0, reservation_sha256=sha(reserve_path),
                audit_sha256=sha(raw_folder / 'policy_mechanical_audit_01/results.json'),
                artifacts=artifacts, chain_metadata=metadata, charged_branches=[], rejected_branch_ids=[],
                committed_branch_ids=[], zero_particle_work_arithmetic_setup=True,
                nonadvancing_kernel_invocations=2, owner_packet_seconds=time.perf_counter() - owner_started, utc=utc()))
            commit(marker / 'owner_decision.json', dict(admitted=True,
                admission_sha256=sha(OUT / 'admissions' / f'{index:06d}' / 'results.json'), utc=utc()))
            self.setup_complete = True
            return None, None, sha(OUT / 'admissions' / f'{index:06d}' / 'results.json')
        if operation.startswith('smoke_'):
            path = raw_folder / 'smoke.json.xz'
            need(response['smoke_sha256'] == sha(path), 'fresh complete original smoke raw')
            smoke = json.loads(lzma.decompress(path.read_bytes(), format=lzma.FORMAT_XZ))
            case = definitions()[level_id]['case']
            def read_only_grant():
                authority(False)
                return dict(read_only_audit_authorized=True, native_dispatch_authorized=False,
                            simulation_cutoff_utc=self.plan['end_utc'])
            with self.engine.native_execution_scope(case['spec'], case['binding'], read_only_grant,
                    plan_path=PLAN, auth_path=AUTH, physical_path=PHYSICAL, numerical=False) as scope:
                proof = self.auditor.audit_original_smoke_record(smoke['record'], case['spec'], case['binding'],
                    scope['geometry'], sha(PHYSICAL), read(PHYSICAL)['minimum_gap_semantics'], field=scope['field'])
            need(proof['passed'] is True and smoke['work_rows'] == len(smoke['record']['rows']) == 32,
                 'original full-record mechanical/raw/gap/guard smoke audit')
            seal(raw_folder / 'policy_mechanical_audit_01', dict(passed=True, work_rows=32,
                independent_mechanical_replay_performed=True, smoke_mode=smoke['mode'], proof=proof,
                raw_sha256=sha(path), **guard_bindings(self.plan), utc=utc()))
            artifacts = {str(path): sha(path) for path in raw_folder.rglob('*') if path.is_file()}
            metadata = {name: value for name, value in artifacts.items() if not name.endswith('.xz')}
            seal(OUT / 'admissions' / f'{index:06d}', dict(passed=True, index=index, level_id=level_id,
                kind=kind, label=label, work_rows=32, reservation_sha256=sha(reserve_path),
                audit_sha256=sha(raw_folder / 'policy_mechanical_audit_01/results.json'), artifacts=artifacts,
                chain_metadata=metadata, charged_branches=[], rejected_branch_ids=[], committed_branch_ids=[],
                single_branch_smoke=True, operation=operation,
                owner_packet_seconds=time.perf_counter() - owner_started, utc=utc()))
            commit(marker / 'owner_decision.json', dict(admitted=True,
                admission_sha256=sha(OUT / 'admissions' / f'{index:06d}' / 'results.json'), utc=utc()))
            return smoke, None, sha(OUT / 'admissions' / f'{index:06d}' / 'results.json')
        prefix = read(raw_folder / 'prefix.json')
        need(prefix == response['prefix'] and sha(raw_folder / 'packet.json.xz') == response['raw_sha256'], 'fresh complete raw response')
        packet = load_packet(raw_folder / 'packet.json.xz', prefix, parent_prefix, history)
        aggregate = None
        if kind == 'production':
            need(pause_rows is None and phase is None, 'production never uses explicit-row or within-trial diagnostic pause')
            aggregate = production_classification(packet)
        case = definitions()[level_id]['case']
        limits = self.kernel.Limits(**definitions()[level_id]['limits'])
        def deny_native():
            authority(False)
            return dict(read_only_audit_authorized=True, native_dispatch_authorized=False,
                        simulation_cutoff_utc=self.plan['end_utc'])
        with self.engine.native_execution_scope(case['spec'], case['binding'], dispatch_gate=deny_native,
                plan_path=PLAN, auth_path=AUTH, physical_path=PHYSICAL, numerical=False,
                prior_receipt_authenticator=authenticate_prior_branch) as scope:
            need(scope['native_setup_force_calls'] == 0, 'independent audit has zero native setup force calls')
            need(all(self.plan['source_files'].get(path) == value for path, value in scope['source_bindings'].items()),
                 'actual mechanical/cap interface source map is caller-frozen')
            audit_started = time.perf_counter()
            audit = self.auditor.audit_runtime_packet(packet, limits,
                checkpoint_before=before, checkpoint_after=packet['checkpoint'],
                field=scope['field'], geometry=scope['geometry'], spec=case['spec'], binding=case['binding'],
                source_bindings=scope['source_bindings'], mechanical_stencil_adapter=scope['mechanical_stencil_adapter'],
                original_digest=original_digest, expected_policy_sha256=limits.numerical_binding,
                expected_previous_receipt_sha256=previous_receipt)
            audit_seconds = time.perf_counter() - audit_started
        need(audit['passed'] is True and packet['status'] != 'negative'
             and audit['all_work_rows'] == packet['work_rows'] <= cap,
             'unchanged independent mechanical/raw/history/controller gates before successor')
        trace = self.engine.trace_rows(packet)
        need(read_trace(raw_folder / 'trace.npy') == trace, 'every accepted13-column trace row is exact raw')
        guard = dict(passed=True, work_rows=packet['work_rows'], audit=audit,
            independent_mechanical_replay_performed=True, raw_lossless_reconstructed=True,
            original_FULL_input_sha256=original_digest(None if before is None else before['physical_checkpoint']),
            original_FULL_output_sha256=original_digest(packet['checkpoint']['physical_checkpoint']),
            input_controller_sha256=digest(before), output_controller_sha256=digest(packet['checkpoint']),
            raw_sha256=sha(raw_folder / 'packet.json.xz'), six_field_prefix=prefix,
            production_aggregate_sha256=digest(aggregate) if aggregate is not None else None,
            **guard_bindings(self.plan), utc=utc())
        seal(raw_folder / 'policy_mechanical_audit_01', guard)
        artifacts = {str(path): sha(path) for path in raw_folder.rglob('*') if path.is_file()}
        metadata = {name: value for name, value in artifacts.items() if not name.endswith(('.xz', '.npy'))}
        admission = dict(passed=True, index=index, level_id=level_id, kind=kind, label=label,
            work_rows=packet['work_rows'], reservation_sha256=sha(reserve_path),
            audit_sha256=sha(raw_folder / 'policy_mechanical_audit_01/results.json'), artifacts=artifacts, chain_metadata=metadata,
            production_aggregate=aggregate, output_prefix=prefix,
            previous_packet_receipt_sha256=previous_receipt, independent_replay_seconds=audit_seconds,
            owner_packet_seconds=time.perf_counter() - owner_started, utc=utc())
        seal(OUT / 'admissions' / f'{index:06d}', admission)
        verify_mapping(self.plan['source_files']); verify_mapping(self.plan['physical_inputs'])
        resource_guard(force_inventory=True)
        commit(marker / 'owner_decision.json', dict(admitted=True,
            admission_sha256=sha(OUT / 'admissions' / f'{index:06d}' / 'results.json'), utc=utc()))
        cache_put(self.reference_cache, digest(prefix), (packet['checkpoint'], prefix, packet['checkpoint']['physical_checkpoint']['state']['history']))
        return packet, prefix, sha(OUT / 'admissions' / f'{index:06d}' / 'results.json')


def read_trace(path):
    with Path(path).open('rb') as stream:
        need(stream.read(8) == b'\x93NUMPY\x01\x00', 'literal native float64 trace format')
        size = struct.unpack('<H', stream.read(2))[0]
        header = ast.literal_eval(stream.read(size).decode('latin1').strip())
        need(header['descr'] == '<f8' and header['fortran_order'] is False
             and len(header['shape']) == 2 and header['shape'][1] == 13, 'original13-column float64 layout')
        raw = stream.read()
    need(len(raw) == header['shape'][0] * 13 * 8, 'complete exact trace bytes')
    return [list(struct.unpack_from('<13d', raw, index * 13 * 8)) for index in range(header['shape'][0])]


def accepted_journal(packet):
    by_id = {b['branch_id']: b for b in packet.get('carried_branches', []) + packet['work_branches']}
    result = []
    for identity in packet['committed_branch_ids']:
        branch = by_id[identity]
        need(branch['role'] in ('F1', 'F2'), 'accepted selector events exclude every coarse shadow')
        need(len(branch['cap_entries']) >= len(branch['rows']), 'literal accepted branch cap association')
        result.extend(dict(entry, role=branch['role']) for entry in branch['cap_entries'][:len(branch['rows'])])
    need(len(result) == len(packet['accepted_rows']), 'complete accepted row/journal association')
    return result


def numeric_signature(packet):
    """Literal numerical state; administrative actual call counts stay external."""
    cp = packet['checkpoint']
    return dict(physical_checkpoint=cp['physical_checkpoint'], published_state_token=cp['published_state_token'],
        cursor=cp['cursor'], numeric_ledger=cp['numeric_ledger'], history_root=cp['history_root'],
        frames=cp['frames'], staged_history_nodes=cp['staged_history_nodes'],
        pending_branches=[restart_branch_projection(branch) for branch in cp['pending_branches']])


def restart_branch_projection(branch):
    """Exclude TWO explicit administrative fields; retain their raw evidence.

    Stage119 compact_result.runtime_seconds is an actual performance-clock
    observation, not physical/numerical state. A carried prior admission SHA is
    authenticated separately because split executions have distinct records.
    No reaction, state, iteration, cap, monitor, history or numerical decision
    field is dropped. Unknown future timing fields fail equality until reviewed.
    """
    result = copy.deepcopy(branch)
    result.pop('previous_packet_receipt_sha256', None)
    if 'compact_result' in result:
        result['compact_result'].pop('runtime_seconds', None)
    return result


def restart_equal(serial, parts, *, reference=None):
    """Compare all actual physical rows/observations, not merely endpoints."""
    need(parts and all(isinstance(p, dict) for p in parts), 'complete actual split packet list')
    branches = [restart_branch_projection(branch) for packet in parts for branch in packet['work_branches']]
    need([restart_branch_projection(branch) for branch in serial['work_branches']] == branches,
         'every coarse/half/rejected branch and original native observation is bit-identical')
    need(serial['accepted_rows'] == [row for packet in parts for row in packet['accepted_rows']],
         'all literal committed rows exactly equal')
    need(accepted_journal(serial) == [entry for packet in parts for entry in accepted_journal(packet)],
         'all accepted cap/trigger decisions exactly equal')
    need(sum(packet['work_rows'] for packet in parts) == serial['work_rows']
         and numeric_signature(serial) == numeric_signature(parts[-1]),
         'original FULL history/checkpoint, logical cursor, pending branches and numeric ledger exactly equal')
    if reference is not None:
        need([restart_branch_projection(branch) for branch in serial['work_branches']]
             == [restart_branch_projection(branch) for branch in reference['work_branches']]
             and serial['accepted_rows'] == reference['accepted_rows']
             and accepted_journal(serial) == accepted_journal(reference)
             and numeric_signature(serial) == numeric_signature(reference),
             'qualification repeats the FIRST actual original record, never an easier selected later record')
    return True


def qualify_restart(execution, level, anchor, input_prefix=None, previous_receipt=None,
                    *, original_packet=None, original_cap=None, phase=None, accepted_rows=256):
    """Discard every diagnostic and retain the ORIGINAL accepted parent/path."""
    need(anchor in ('initial', 'after_coarse', 'after_first_half', 'odd_accepted_half',
                    'first_actual_selector', 'late_FULL_history', 'window_handoff'), 'declared actual interruption anchor')
    tag = f'{level}_{anchor}'
    if anchor == 'window_handoff':
        tag += f'_w{execution.window_index:03d}'
    folder = OUT / 'levels' / level / 'restarts' / tag
    need(not folder.exists(), 'restart cannot be silently repeated after a failure')
    cap = PACKET_CAP if original_cap is None else original_cap
    serial, serial_prefix, serial_receipt = execution.packet(level, 'standalone', tag + '_serial', input_prefix,
        cap=cap, pause_rows=None if original_packet is not None else accepted_rows,
        previous_receipt=previous_receipt)
    if original_packet is not None:
        n = len(original_packet['accepted_rows'])
        need(n > 0 and n % 2 == 0 and original_packet['checkpoint']['physical_checkpoint']['state']['pending_trial'] is None,
             'FIRST actual trigger record has complete pair-boundary accepted rows and no original pending trial')
        execution.imports()
        split = execution.restart.first_active_split(accepted_journal(original_packet), n)
        j = split['j']
        need(phase is None, 'actual first trigger test uses its real even accepted boundary')
    else:
        n = accepted_rows
        j = 1 if anchor == 'odd_accepted_half' else n // 2
        split = None
    left, left_prefix, left_receipt = execution.packet(level, 'standalone', tag + '_left', input_prefix,
        cap=cap, pause_rows=None if phase is not None else j, phase=phase, previous_receipt=previous_receipt)
    consumed = left['work_rows']
    remaining_cap = cap - consumed
    need(0 < remaining_cap <= PACKET_CAP, 'remaining original work reservation for exact split successor')
    already = len(left['accepted_rows'])
    right, right_prefix, right_receipt = execution.packet(level, 'standalone', tag + '_right', left_prefix,
        cap=remaining_cap, pause_rows=None if original_packet is not None else n - already,
        previous_receipt=left_receipt)
    need(len(serial['accepted_rows']) == n and len(left['accepted_rows']) + len(right['accepted_rows']) == n,
         'exact planned accepted-row count, no implicit shortened native test')
    restart_equal(serial, [left, right], reference=original_packet)
    if anchor == 'initial':
        need(not any(item['trigger_grain_ids'] for packet in (serial, left, right) for item in accepted_journal(packet)),
             'initial test remains pretrigger; active qualification must use the later FIRST actual event')
    if anchor == 'first_actual_selector':
        need(split is not None and len(left['accepted_rows']) == split['j']
             and not any(x['trigger_grain_ids'] for x in accepted_journal(left))
             and any(x['trigger_grain_ids'] for x in accepted_journal(right)), 'first actual accepted trigger appears in exact split successor')
    if phase is not None:
        expected = {'C_done': 'after_coarse', 'F1_done': 'after_first_half'}[phase]
        need(left['cursor_after']['phase'] == expected and not left['accepted_rows'],
             'interruption is actual staged coarse/first-half cursor, never a falsely published stage')
    if anchor == 'odd_accepted_half':
        need(len(left['accepted_rows']) == 1 and left['cursor_after']['phase'] == 'publish_second_half',
             'actual odd accepted row has a separately bound uncommitted F2')
    if anchor == 'late_FULL_history':
        before, _, _ = load_reference(input_prefix, execution.reference_cache)
        need(before['physical_checkpoint']['state']['t'] >= .410 and before['cursor']['phase'] == 'idle',
             'first admitted late pair boundary; no invented second selector witness')
    artifacts = {}
    for label in (tag + '_serial', tag + '_left', tag + '_right'):
        artifacts.update({str(path): sha(path) for path in (OUT / 'records' / label).rglob('*') if path.is_file()})
    body = dict(passed=True, anchor=anchor, level_id=level, labels=[tag + suffix for suffix in ('_serial', '_left', '_right')],
        exact_all_trial_observations=True, exact_accepted_rows=True, exact_FULL_checkpoint_history=True,
        exact_semantic_controller_and_ledger=True, separate_actual_record_charges=3,
        excluded_administrative_fields=['branch.compact_result.runtime_seconds', 'carried_branch.previous_packet_receipt_sha256'],
        all_original_raw_timings_and_record_identities_preserved_and_authenticated=True,
        original_path_restored_unchanged=True, original_input_prefix=input_prefix,
        original_input_controller_sha256=digest(load_reference(input_prefix, execution.reference_cache)[0]),
        actual_first_trigger_split=split, discarded_all_work_rows=serial['work_rows'] + left['work_rows'] + right['work_rows'],
        artifact_files=artifacts, design_sha256=sha(PLAN), physical_design_sha256=sha(PHYSICAL),
        source_files=execution.plan['source_files'], utc=utc())
    seal(folder, body)
    return body


def authenticate_prior_branch(branch):
    """Exact prior staged source/raw/admission association for a resumed packet."""
    expected = branch.get('previous_packet_receipt_sha256')
    need(is_sha(expected), 'prior staged branch explicitly names its admission')
    for path in (OUT / 'admissions').glob('*/results.json'):
        if sha(path) != expected:
            continue
        admission = sealed(path, positive=True)
        verify_mapping(admission['chain_metadata'])
        reservation_path = OUT / 'reservations' / f"{admission['index']:06d}.json"
        reservation = read(reservation_path)
        need(admission['reservation_sha256'] == sha(reservation_path)
             and reservation['design_sha256'] == sha(PLAN)
             and all(admission[key] == reservation[key] for key in ('index', 'label', 'kind', 'level_id')),
             'prior staged admission binds its actual current-plan reservation')
        folder = OUT / 'records' / admission['label']
        guard = sealed(folder / 'policy_mechanical_audit_01/results.json', positive=True)
        need(admission['audit_sha256'] == sha(folder / 'policy_mechanical_audit_01/results.json')
             and guard['independent_mechanical_replay_performed'] is True,
             'prior actual original source/physical/mechanical audit association')
        verify_guard_bindings(guard)
        prefix = read(folder / 'prefix.json')
        need(sha(prefix['path']) == prefix['compressed_sha256'], 'prior staged raw bytes freshly authenticated')
        packet = load_packet(prefix['path'], prefix,
            read_wire_parent(prefix['path']), load_reference(read_wire_parent(prefix['path']), {})[2])
        candidates = packet['checkpoint']['pending_branches']
        stripped = lambda value: {key: item for key, item in value.items() if key != 'previous_packet_receipt_sha256'}
        need(any(stripped(value) == stripped(branch) for value in candidates), 'exact original retained pending branch, not new evidence under old receipt')
        return True
    raise RuntimeError('Prior staged branch admission is absent or changed')


def read_wire_parent(path):
    envelope = json.loads(lzma.decompress(Path(path).read_bytes(), format=lzma.FORMAT_XZ))
    return envelope['packet']['checkpoint']['physical_checkpoint']['state']['history']['parent']


def post_replay_record(execution, reservation, *, cache):
    """Complete fresh mechanical/raw/history replay, never just receipt hashes."""
    authority(False, refresh_sources=True)
    index, label, key = (reservation[k] for k in ('index', 'label', 'level_id'))
    admission = sealed(OUT / 'admissions' / f'{index:06d}' / 'results.json', positive=True)
    verify_mapping(admission['artifacts'])
    need(admission['reservation_sha256'] == sha(OUT / 'reservations' / f'{index:06d}.json'), 'post-replay exact reservation')
    folder = OUT / 'records' / label
    if admission.get('zero_particle_work_arithmetic_setup'):
        setup = read(folder / 'arithmetic_setup.json')
        need(admission['work_rows'] == 0 and setup['particle_steps'] == 0 and setup['native_qualification_passed'] is False,
             'arithmetic setup never promoted to native qualification')
        return None
    if admission.get('single_branch_smoke'):
        smoke = json.loads(lzma.decompress((folder / 'smoke.json.xz').read_bytes(), format=lzma.FORMAT_XZ))
        case = definitions()[key]['case']; execution.imports()
        def grant_smoke():
            authority(False)
            return dict(read_only_audit_authorized=True, native_dispatch_authorized=False,
                        simulation_cutoff_utc=execution.plan['end_utc'])
        with execution.engine.native_execution_scope(case['spec'], case['binding'], grant_smoke,
                plan_path=PLAN, auth_path=AUTH, physical_path=PHYSICAL, numerical=False) as scope:
            proof = execution.auditor.audit_original_smoke_record(smoke['record'], case['spec'], case['binding'],
                scope['geometry'], sha(PHYSICAL), read(PHYSICAL)['minimum_gap_semantics'], field=scope['field'])
        need(proof['passed'] and admission['work_rows'] == smoke['work_rows'] == 32, 'complete independent old-bit smoke replay')
        return None
    before, parent_prefix, history = load_reference(reservation['input_prefix'], cache)
    prefix = read(folder / 'prefix.json')
    packet = load_packet(folder / 'packet.json.xz', prefix, parent_prefix, history)
    need(digest(before) == reservation['input_controller_sha256'], 'fresh whole raw input controller ancestry')
    definition = definitions()[key]; case = definition['case']
    execution.imports(); limits = execution.kernel.Limits(**definition['limits'])
    def grant():
        authority(False)
        return dict(read_only_audit_authorized=True, native_dispatch_authorized=False,
                    simulation_cutoff_utc=execution.plan['end_utc'])
    with execution.engine.native_execution_scope(case['spec'], case['binding'], dispatch_gate=grant,
            plan_path=PLAN, auth_path=AUTH, physical_path=PHYSICAL, numerical=False,
            prior_receipt_authenticator=authenticate_prior_branch) as scope:
        need(scope['native_setup_force_calls'] == 0
             and all(execution.plan['source_files'].get(path) == value for path, value in scope['source_bindings'].items()),
             'actual original source-bound read-only replay, zero native setup calls')
        proof = execution.auditor.audit_runtime_packet(packet, limits,
            checkpoint_before=before, checkpoint_after=packet['checkpoint'],
            field=scope['field'], geometry=scope['geometry'], spec=case['spec'], binding=case['binding'],
            source_bindings=scope['source_bindings'], mechanical_stencil_adapter=scope['mechanical_stencil_adapter'],
            original_digest=original_digest, expected_policy_sha256=limits.numerical_binding,
            expected_previous_receipt_sha256=reservation['previous_packet_receipt_sha256'])
    need(proof['passed'] and proof['all_work_rows'] == admission['work_rows']
         and read_trace(folder / 'trace.npy') == execution.engine.trace_rows(packet),
         'all retained trial physics and accepted trace rows independently reconstructed')
    if reservation['kind'] == 'production':
        verify_production_aggregate(packet, admission)
    cache_put(cache, digest(prefix), (packet['checkpoint'], prefix, packet['checkpoint']['physical_checkpoint']['state']['history']))
    return packet


def replay_level(execution, key, *, prefix_only=False):
    execution.close_window()
    for path in (OUT / 'windows').glob('window_*/launch.json'):
        need(inspect_identity(read(path))['retired'], 'all numerical identities retired before full/prefix replay')
    counts = ledger()
    need(not counts['unresolved'], 'no unknown/unaccepted work before full replay')
    if prefix_only:
        return authenticate_prefix_and_benchmark(execution, key, counts)
    cache, paths, artifacts, production, last_prefix, terminal, work = {}, [], {}, [], None, None, 0
    started = time.perf_counter()
    for reserve_path in sorted((OUT / 'reservations').glob('*.json')):
        reservation = read(reserve_path)
        if reservation['level_id'] != key:
            continue
        before = last_prefix
        packet = post_replay_record(execution, reservation, cache=cache)
        folder = OUT / 'records' / reservation['label']
        artifacts.update({str(path): sha(path) for path in folder.rglob('*') if path.is_file()})
        if packet is None:
            continue
        work += packet['work_rows']
        if reservation['kind'] == 'production':
            need(reservation['input_prefix'] == before, 'fresh t0 contiguous production chain; no late reset/prefix substitution')
            prefix = read(folder / 'prefix.json')
            production.append(reservation['label']); paths.append(folder / 'trace.npy')
            last_prefix, terminal = prefix, packet
    need(terminal is not None and production, 'nonempty newly advanced path')
    elapsed = time.perf_counter() - started
    rate = max(.01, 2 * elapsed / max(1, work))
    for path in (OUT / 'cost_observations').glob('*/results.json'):
        rate = max(rate, sealed(path, positive=True)['conservative_replay_seconds_per_work_row'])
    index = len(list((OUT / 'cost_observations').glob('*'))) + 1
    seal(OUT / 'cost_observations' / f'{index:03d}', dict(passed=True, level_id=key,
        scope='complete retained prefix replay' if prefix_only else 'complete full-level replay',
        replay_seconds=elapsed, all_replayed_work_rows=work,
        conservative_replay_seconds_per_work_row=rate, proxy_is_not_a_proven_future_upper_bound=True,
        design_sha256=sha(PLAN), source_files=execution.plan['source_files'], utc=utc()))
    cp = terminal['checkpoint']['physical_checkpoint']
    need(cp['state']['pending_trial'] is None, 'original physical pending trial absent at replay boundary')
    if prefix_only:
        need(cp['state']['t'] >= SCREEN_S, 'same-H path reached prospective accepted-row prefix screen')
    else:
        need(terminal['status'] == 'present_at_horizon' and cp['state']['t'] == HORIZON_S
             and terminal['cursor_after']['phase'] == 'idle', 'ordinary original complete horizon, no terminal extension or staged-half promotion')
        execution.audited_levels.add(key)
    suffix = 'prefix_replay_01' if prefix_only else 'full_audit_01'
    result = dict(passed=True, level_id=key, prefix_only=prefix_only,
        complete_independent_mechanical_replay_performed=True, complete_lossless_raw_history_reconstructed=True,
        production_labels=production, production_prefix=last_prefix,
        original_FULL_output_sha256=original_digest(cp), controller_output_sha256=digest(terminal['checkpoint']),
        start_s=0., stop_s=cp['state']['t'], committed_half_rows=counts['levels'][key]['committed_half_rows'],
        all_replayed_work_rows=work, trace_paths=[str(path) for path in paths], artifacts=artifacts,
        source_files=execution.plan['source_files'], physical_inputs=execution.plan['physical_inputs'],
        design_sha256=sha(PLAN), physical_design_sha256=sha(PHYSICAL), utc=utc())
    seal(OUT / 'levels' / key / suffix, result)
    return result, terminal


def authenticate_prefix_and_benchmark(execution, key, counts):
    """Hash ALL prefix raw/trace; mechanically replay ONE fixed standard packet.

    Whole-path independent mechanical/cap/raw/FULL replay remains mandatory
    exactly once after completion. This is explicitly not a mechanical replay
    of the whole prefix. Selection is fixed by chronological inventory and
    packet size, never by a passing outcome, fast timing or contact activity.
    """
    artifacts, production, paths, chosen, last_prefix, last_reservation = {}, [], [], None, None, None
    authentication_started = time.perf_counter()
    for reserve_path in sorted((OUT / 'reservations').glob('*.json')):
        reservation = read(reserve_path)
        if reservation['level_id'] != key:
            continue
        index = reservation['index']
        admission = sealed(OUT / 'admissions' / f'{index:06d}' / 'results.json', positive=True)
        need(admission['reservation_sha256'] == sha(reserve_path), 'exact prefix reservation/admission')
        verify_mapping(admission['artifacts'])
        folder = OUT / 'records' / reservation['label']
        guard = sealed(folder / 'policy_mechanical_audit_01/results.json', positive=True)
        need(admission['audit_sha256'] == sha(folder / 'policy_mechanical_audit_01/results.json')
             and (guard.get('independent_mechanical_replay_performed') is True
                  or guard.get('zero_particle_work_arithmetic_setup') is True and admission['work_rows'] == 0),
             'every prefix record retains its exact executed independent online gate')
        artifacts.update(admission['artifacts'])
        if reservation['kind'] != 'production':
            continue
        need(reservation['input_prefix'] == last_prefix, 'same fresh production prefix, no source/state reset')
        prefix = read(folder / 'prefix.json')
        need(set(prefix) == PREFIX_FIELDS and prefix == admission['output_prefix']
             and prefix['compressed_sha256'] == sha(folder / 'packet.json.xz'), 'complete actual raw prefix identity')
        production.append(reservation['label']); paths.append(folder / 'trace.npy')
        last_prefix, last_reservation = prefix, reservation
        if admission['work_rows'] >= reservation['maximum_work_rows'] / 2:
            chosen = reservation
    need(chosen is not None and last_prefix is not None, 'last standard prefix packet exists for prospectively fixed cost benchmark')
    authentication_seconds = time.perf_counter() - authentication_started
    # Actual complete saved-record audit, after all numerical producers retire.
    started = time.perf_counter()
    benchmark = post_replay_record(execution, chosen, cache={})
    elapsed = time.perf_counter() - started
    need(benchmark is not None and benchmark['work_rows'] >= chosen['maximum_work_rows'] / 2,
         'benchmark is the fixed complete production packet, not a tiny pause/control')
    rate = max(.01, 2 * elapsed / benchmark['work_rows'])
    for path in (OUT / 'cost_observations').glob('*/results.json'):
        rate = max(rate, sealed(path, positive=True)['conservative_replay_seconds_per_work_row'])
    index = len(list((OUT / 'cost_observations').glob('*'))) + 1
    seal(OUT / 'cost_observations' / f'{index:03d}', dict(passed=True, level_id=key,
        scope='complete saved standard-packet post-replay benchmark; not whole-prefix mechanical replay',
        fixed_selection_rule='last admitted production packet work_rows>=reservation_cap/2 before prefix pause',
        benchmark_label=chosen['label'], benchmark_reservation_sha256=sha(OUT / 'reservations' / f"{chosen['index']:06d}.json"),
        replay_seconds=elapsed, all_replayed_work_rows=benchmark['work_rows'],
        conservative_replay_seconds_per_work_row=rate, proxy_is_not_a_proven_future_upper_bound=True,
        prefix_raw_trace_authentication_seconds=authentication_seconds,
        design_sha256=sha(PLAN), source_files=execution.plan['source_files'], utc=utc()))
    parent = last_reservation['input_prefix']
    _, parent_prefix, history = load_reference(parent, {})
    terminal = load_packet(last_prefix['path'], last_prefix, parent_prefix, history)
    cp = terminal['checkpoint']['physical_checkpoint']
    need(cp['state']['t'] >= SCREEN_S and cp['state']['pending_trial'] is None,
         'same-H firstaccepted-prefix boundary and exact FULL physical state')
    result = dict(passed=True, level_id=key, prefix_only=True,
        whole_prefix_independent_mechanical_replay_performed=False,
        all_prefix_raw_trace_hashes_and_executed_online_audits_authenticated=True,
        one_fixed_standard_packet_complete_mechanical_raw_FULL_replay_performed=True,
        benchmark_label=chosen['label'], fixed_selection_rule='last production packet work>=cap/2',
        production_labels=production, production_prefix=last_prefix,
        original_FULL_output_sha256=original_digest(cp), controller_output_sha256=digest(terminal['checkpoint']),
        start_s=0., stop_s=cp['state']['t'], trace_paths=[str(path) for path in paths],
        artifacts=artifacts, source_files=execution.plan['source_files'], physical_inputs=execution.plan['physical_inputs'],
        complete_whole_path_mechanical_replay_still_required=True,
        design_sha256=sha(PLAN), physical_design_sha256=sha(PHYSICAL), utc=utc())
    seal(OUT / 'levels' / key / 'prefix_authentication_and_packet_benchmark_01', result)
    return result, terminal


def native_initial_matrix(execution, key):
    """Actual source-compatibility and FULL-state restart prelude, all discarded."""
    original, _, _ = execution.packet(key, 'standalone', key + '_smoke_original32', cap=32, operation='smoke_original')
    compiled, _, _ = execution.packet(key, 'standalone', key + '_smoke_compiled32', cap=32, operation='smoke_compiled')
    need(original['record']['rows'] == compiled['record']['rows']
         and original['physical_checkpoint'] == compiled['physical_checkpoint'],
         'old-bit smoke compares original nominal32 with compiled C-chain32, never new accepted halves')
    seal(OUT / 'levels' / key / 'old_bits_smoke_01', dict(passed=True,
        original_label=key + '_smoke_original32', compiled_label=key + '_smoke_compiled32',
        compared_original_single_branch_steps=32, discarded_physical_work_rows=64,
        exact_rows=True, exact_FULL_checkpoint_history=True,
        stepdoubling_accepted_halves_same_factor_old_bits_claimed=False,
        source_files=execution.plan['source_files'], design_sha256=sha(PLAN), utc=utc()))
    qualify_restart(execution, key, 'initial')
    qualify_restart(execution, key, 'after_coarse', phase='C_done')
    qualify_restart(execution, key, 'after_first_half', phase='F1_done')
    qualify_restart(execution, key, 'odd_accepted_half')
    return True


def preserve_boundary(key, prefix, *, name='recoverable'):
    cp, _, _ = load_reference(prefix, {})
    folder = OUT / 'levels' / key / name
    need(not folder.exists(), 'create-only final recoverable FULL boundary')
    folder.mkdir(parents=True, exist_ok=False)
    payload = dict(schema='paper1.full-state-stepdoubling.recoverable.v1', checkpoint=cp,
        raw_six_field_prefix=prefix, original_FULL_sha256=original_digest(cp['physical_checkpoint']),
        controller_checkpoint_sha256=digest(cp), design_sha256=sha(PLAN))
    with (folder / 'controller_checkpoint.json.xz').open('xb') as stream:
        stream.write(lzma.compress((json.dumps(payload, sort_keys=True, indent=2, allow_nan=True) + '\n').encode(),
                                  format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64, preset=6))
    commit(folder / 'prefix.json', prefix)
    commit(folder / 'completion.json', dict(passed=True, payload_sha256=sha(folder / 'controller_checkpoint.json.xz'),
        original_FULL_sha256=payload['original_FULL_sha256'], controller_checkpoint_sha256=payload['controller_checkpoint_sha256'], utc=utc()))
    return payload


def latest_state():
    return dict(prefix=None, previous_receipt=None, packets=0, time_s=0., last_window=None,
                initial_qualified=False, active_qualified=False, late_FULL_qualified=False,
                native_complete=False)


def advance_level(execution, key, state, *, screen=False):
    if not state['initial_qualified']:
        native_initial_matrix(execution, key)
        state['initial_qualified'] = True
    target = SCREEN_S if screen else HORIZON_S
    while state['time_s'] < target:
        authority(True, refresh_sources=True)
        budget_guard(ledger(), key, 'production', PACKET_CAP)
        execution.ensure_window(key, 'production', PACKET_CAP)
        if state['prefix'] is not None and state['last_window'] != execution.window_index:
            qualify_restart(execution, key, 'window_handoff', state['prefix'], state['previous_receipt'])
        # An actual cap ≤4998 bounds every C/F1/F2/rejected/partial call. A
        # production record before first-active qualification finishes at a
        # real controller boundary; no easy shorter active test is substituted.
        state['packets'] += 1
        label = f'{key}_production_{state["packets"]:05d}'
        original_input, original_previous = state['prefix'], state['previous_receipt']
        packet, prefix, receipt = execution.packet(key, 'production', label, original_input,
            cap=PACKET_CAP, pause_time=SCREEN_S if screen else None, previous_receipt=original_previous)
        state.update(prefix=prefix, previous_receipt=receipt,
            time_s=packet['checkpoint']['physical_checkpoint']['state']['t'], last_window=execution.window_index)
        need(packet['work_rows'] > 0 or packet['accepted_rows'], 'actual work or previously charged F2 publication made progress')
        first = execution.auditor.first_accepted_selector(packet)
        if first is not None and not state['active_qualified']:
            # Retain the ORIGINAL admitted path before any diagnostic failure.
            qualify_restart(execution, key, 'first_actual_selector', original_input, original_previous,
                original_packet=packet, original_cap=PACKET_CAP)
            state['active_qualified'] = True
        cp = packet['checkpoint']
        if (state['time_s'] >= .410 and cp['cursor']['phase'] == 'idle'
                and not state['late_FULL_qualified']):
            qualify_restart(execution, key, 'late_FULL_history', prefix, receipt)
            state['late_FULL_qualified'] = True
        # Diagnostics are discarded: the next production call ALWAYS uses
        # original packet's prefix/receipt, never a diagnostic final checkpoint.
        need(state['prefix'] == prefix and state['previous_receipt'] == receipt,
             'original admitted production boundary restored after native probes')
        show_state('native_qualification_paths', level_id=key, time_s=state['time_s'],
            window=execution.window_index, counters=ledger())
        if packet['status'] == 'present_at_horizon':
            need(state['time_s'] == HORIZON_S and state['active_qualified'] and state['late_FULL_qualified'],
                 'complete observation plus actual first-active and late FULL native coverage')
            state['native_complete'] = True
            break
        need(packet['status'] == 'paused_controller', 'ordinary complete horizon or explicit controller pause only')
    if screen:
        need(state['time_s'] >= SCREEN_S, 'first complete accepted-pair boundary covering .255, same original full H')
    else:
        need(state['native_complete'], 'complete original full observation reached within fixed limits')
        preserve_boundary(key, state['prefix'])
        seal(OUT / 'levels' / key / 'native_completion_01', dict(passed=True, state=state,
            original_path_fresh_t0=True, first_actual_active_restart_qualified=True,
            late_FULL_history_restart_qualified=True, original_full_horizon_s=HORIZON_S,
            ledger=ledger(), design_sha256=sha(PLAN), source_files=execution.plan['source_files'], utc=utc()))
    return state


def metric_interface():
    if str(STAGING) not in sys.path:
        sys.path.insert(0, str(STAGING))
    shared = importlib.import_module('run_core_v2')
    comparator = importlib.import_module('compare_core_v2')
    return shared, comparator


def prefix_cost_gate(execution, states, replays):
    """Fixed-clock prefix screen; neither a new H nor full-path admission."""
    shared, comparator = metric_interface()
    import numpy as np
    a, b = (definitions()[key]['case'] for key in LEVELS[:2])
    initial = a['spec']['initial_state']
    row0 = [0., *initial['position_m'], *initial['orientation'], *initial['velocity_generalized']]
    blocks = lambda paths: (np.load(path, mmap_mode='r', allow_pickle=False) for path in paths)
    cfg = a['spec']['config']
    end_a, end_b = (replays[key][0]['stop_s'] for key in LEVELS[:2])
    need(min(end_a, end_b) >= SCREEN_S, 'both actual firstaccepted prefix ends cover prospective threshold')
    metrics = shared.s.q.job.path_metrics.metrics(blocks(replays[LEVELS[0]][0]['trace_paths']),
        blocks(replays[LEVELS[1]][0]['trace_paths']), row0, row0, end_a, end_b,
        cfg['prolate_semiaxes_m'][1], cfg['target_mean_interstitial_velocity_m_s'])
    need(metrics['common_stop_s'] == min(end_a, end_b), 'unchanged comparator earlier actual accepted boundary, no rewritten clock')
    checks = {key: metrics[key] <= ORIGINAL_GATES[key] for key in
        ('endpoint_q_over_U_max', 'mean_L1_q_over_U_max', 'whole_position_over_b_max', 'whole_axis_vector_norm_max')}
    counts = ledger(); p = execution.plan
    # Bounded conservative cost forecast, explicitly not a proof of future cost.
    # All remaining success/rejection/standalone allocations are included.
    online_rates, standalone_wall = [], []
    for path in (OUT / 'admissions').glob('*/results.json'):
        admission = sealed(path, positive=True)
        reservation = read(OUT / 'reservations' / f"{admission['index']:06d}.json")
        if (admission['kind'] == 'production' and admission['work_rows'] >= reservation['maximum_work_rows'] / 2
                and admission['work_rows'] > 0 and 'owner_packet_seconds' in admission):
            online_rates.append(admission['owner_packet_seconds'] / admission['work_rows'])
        elif admission['kind'] == 'standalone' and 'owner_packet_seconds' in admission:
            standalone_wall.append(admission['owner_packet_seconds'])
    need(online_rates, 'actual native-plus-current-record audit/raw/storage wall observations')
    online = max(online_rates)
    remaining_work = MAX_WORK - counts['work_rows']
    rate_rule = read(PROPOSAL)['prefix_forecast_rule']
    safety = rate_rule['online_observed_rate_multiplier']
    need(type(safety) in (int, float) and safety >= 1., 'frozen disclosed conservative online rate multiplier')
    replay_s = replay_reserve(counts, execution.audited_levels)
    future_replay_rate = effective_replay_rate()
    remaining_standalone_rows = MAX_STANDALONE - counts['standalone_work_rows']
    remaining_standalone_records = MAX_STANDALONE_RECORDS - counts['standalone_records']
    remaining_production_rows = remaining_work - remaining_standalone_rows
    need(min(remaining_standalone_rows, remaining_standalone_records, remaining_production_rows) >= 0,
         'disjoint remaining production/rejected versus standalone allocations')
    standalone_online = max(remaining_standalone_rows * online * safety,
        remaining_standalone_records * max(NATIVE_S, max(standalone_wall, default=0.)))
    seconds = (remaining_production_rows * online * safety + standalone_online
               + remaining_work * future_replay_rate + replay_s)
    resources = resource_guard(force_inventory=True)
    new_bytes = resources['own_bytes']
    row_bytes = new_bytes / max(1, counts['work_rows'])
    byte_safety = rate_rule['observed_bytes_per_work_multiplier']
    need(type(byte_safety) in (int, float) and byte_safety >= 1., 'frozen raw byte forecast multiplier')
    future_bytes = math.ceil(remaining_work * row_bytes * byte_safety) + OUTPUT_RESERVE
    fits = (time.time() + seconds < instant(p['end_utc'])
            and new_bytes + future_bytes <= OWN_BYTES
            and resources['total_retained_bytes'] + future_bytes <= RETENTION_BYTES
            and resources['free_bytes'] - future_bytes >= FREE_BYTES)
    body = dict(passed=all(checks.values()) and fits, common_physical_analysis_stop_s=min(end_a, end_b),
        prospective_prefix_rule='earlier actual first complete accepted-pair boundary covering0.255s; full-H unmodified',
        actual_FULL_state_stops_s={key: states[key]['time_s'] for key in LEVELS[:2]},
        original_full_horizons_unchanged=True, no_FULL_state_time_alignment=True,
        supplementary_prefix_checks=checks, metrics=metrics, full_path_accuracy_passed=False,
        cost_and_storage_fit=fits, projected_remaining_seconds=seconds,
        projected_additional_output_bytes=future_bytes, unproved_future_upper_bound=True,
        observed_online_seconds_per_work_row_max=online, counters=counts, resources=resources,
        remaining_production_rows=remaining_production_rows,
        remaining_standalone_rows=remaining_standalone_rows,
        remaining_standalone_records=remaining_standalone_records,
        projected_standalone_online_seconds=standalone_online,
        source_files=p['source_files'], design_sha256=sha(PLAN), utc=utc())
    seal(OUT / 'embedded_prefix_screen_01', body)
    need(body['passed'], 'supplementary prefix accuracy/cost/storage gate stops dependent full continuation')
    return body


def comparison_input(execution, key, replay, terminal):
    shared, _ = metric_interface()
    case = definitions()[key]['case']; cp = terminal['checkpoint']['physical_checkpoint']
    need(not replay['prefix_only'] and terminal['status'] == 'present_at_horizon'
         and cp['state']['t'] == HORIZON_S and cp['state']['pending_trial'] is None,
         'whole fresh start-to-terminal path required before original comparator')
    counts = ledger()
    need(not counts['unresolved'] and counts['known_unaccepted_work_rows'] == counts['unknown_reserved_work_upper_bound'] == 0,
         'no censored or unknown work in qualification set')
    last = {branch['branch_id']: branch for branch in terminal['carried_branches'] + terminal['work_branches']}
    final_branch = last[terminal['committed_branch_ids'][-1]]
    status = final_branch['compact_result']
    evidence = dict(status='present_at_horizon', steps=counts['levels'][key]['committed_half_rows'],
        start_s=0., stop_s=cp['state']['t'], rejected=0, failure_markers=[], pending_trial=None,
        first_dwell_s=status['first_contact_dwell_time_s'], export_verified=False,
        raw_hashes_verified=True, clock_steps_verified=True, physics_verified=True, fresh_start=True)
    observation = shared.s.q.job.policy.observation(evidence, HORIZON_S)
    need(observation['complete_observation'], 'unchanged original observation gate')
    folder = OUT / 'levels' / key
    files = {str(path): sha(path) for path in (PLAN, AUTH, PHYSICAL,
        folder / 'full_audit_01/results.json', folder / 'full_audit_01/completion.json',
        folder / 'native_completion_01/results.json', folder / 'native_completion_01/completion.json')}
    for path in (OUT / 'windows').glob('window_*/exit.json'):
        closed = read(path)
        need(closed['returncode'] == 0 and closed['forced'] is False
             and inspect_identity(closed['launch'])['retired'], 'exact observed numerical exits before comparison')
        verify_mapping(closed['logs']); files[str(path)] = sha(path)
    return dict(case=case, logical_core_id=execution.plan['logical_core_id'], observation=observation,
        paths=[Path(path) for path in replay['trace_paths']], receipts={}, evidence_files=files,
        final_sha256=sha(folder / 'native_completion_01/results.json'),
        retirement_sha256=sha(folder / 'full_audit_01/results.json'))


def compare_full_pair(execution, first_key, second_key, replays, destination):
    _, comparator = metric_interface()
    a = comparison_input(execution, first_key, *replays[first_key])
    b = comparison_input(execution, second_key, *replays[second_key])
    result = comparator.compare(a, b, destination)
    need(result['original_gate_values'] == ORIGINAL_GATES, 'literal unchanged original accuracy/event gate values')
    need(result['passed'], 'original whole-horizon adjacent pair accuracy/event gate FAILED; no dependent dispatch')
    return result


def registered_identities():
    result = []
    for path in (OUT / 'windows').glob('window_*/launch.json'):
        result.append(dict(path=str(path), sha256=sha(path), launch=read(path)))
    return result


def artifact_inventory(*, exclude_live=True):
    result = {}
    for path in OUT.rglob('*'):
        if not path.is_file() or path.name in ('state.json', 'state.writing'):
            continue
        if exclude_live and path.name in ('stdout.log', 'stderr.log'):
            if path.parent in (OUT / 'owner', OUT / 'supervisor', OUT / 'launcher'):
                continue
        result[str(path)] = sha(path)
    return result


def observed_pair_status(folder):
    path = Path(folder) / 'results.json'
    if not path.exists() and not path.with_name('completion.json').exists():
        return None
    result = sealed(path)
    need(result['original_gate_values'] == ORIGINAL_GATES
         and result['whole_start_to_terminal_paths'] is True, 'comparison is the immutable original complete-path gate')
    return result['passed'] is True


def owner():
    register_self(OUT / 'owner/launch.json')
    p = authority(False, refresh_sources=True)
    expected_design_sha = sha(PLAN)
    execution = None; states = {key: latest_state() for key in LEVELS}
    replays, errors, qualified, reason, finalization_errors = {}, None, False, 'incomplete', []
    try:
        need(source_interfaces()['all_required_interfaces_present'], 'actual native/auditor/restart interfaces installed before execution')
        execution = Execution()
        # Both partial paths are NEW fresh-t0 full-H cases. The screen never
        # creates an artificial .255 horizon or resets an accepted checkpoint.
        for key in LEVELS[:2]:
            advance_level(execution, key, states[key], screen=True)
        prefix_replays = {key: replay_level(execution, key, prefix_only=True) for key in LEVELS[:2]}
        prefix_cost_gate(execution, states, prefix_replays)
        for key in LEVELS[:2]:
            advance_level(execution, key, states[key], screen=False)
            replays[key] = replay_level(execution, key)
        compare_full_pair(execution, LEVELS[0], LEVELS[1], replays, OUT / 'comparison_fine')
        # No coarse production before BOTH complete fine paths, independent
        # post-exit mechanical/raw replay and unchanged original pair pass.
        key = LEVELS[2]
        advance_level(execution, key, states[key], screen=False)
        replays[key] = replay_level(execution, key)
        compare_full_pair(execution, key, LEVELS[0], replays, OUT / 'comparison_coarse')
        qualified, reason = True, 'both_original_whole_horizon_adjacent_gates_passed'
    except BaseException as exc:
        errors = dict(message=repr(exc), traceback=traceback.format_exc())
        reason = 'dependent_dispatch_stopped'
        print(traceback.format_exc(), flush=True)
    finally:
        if execution is not None and execution.handle is not None:
            try:
                execution.close_window()
            except BaseException as exc:
                finalization_errors.append(dict(stage='exact_window_retirement', error=repr(exc)))
        for key, state in states.items():
            if state['prefix'] is not None and not (OUT / 'levels' / key / 'recoverable').exists():
                try:
                    preserve_boundary(key, state['prefix'], name='last_sealed_partial_01')
                except BaseException as exc:
                    finalization_errors.append(dict(stage='preserve_' + key, error=repr(exc)))
        try:
            counts = ledger()
        except BaseException as exc:
            counts = failed_ledger(exc); finalization_errors.append(dict(stage='ledger', error=repr(exc)))
        identities = []
        for row in registered_identities():
            try:
                status = inspect_identity(row['launch'])
            except BaseException as exc:
                status = dict(retired=False, unresolved_identity=True, error=repr(exc))
            identities.append(dict(**row, inspection=status))
            if status.get('retired') is not True:
                finalization_errors.append(dict(stage='identity', path=row['path'], unresolved_identity=True))
        try:
            verify_mapping(p['source_files']); verify_mapping(p['physical_inputs']); verify_mapping(p['evidence_files'])
            verify_mapping(p['historical_evidence_files'])
            need(sha(PLAN) == expected_design_sha, 'held immutable design at final disposition')
            resources = resource_guard(force_inventory=True)
        except BaseException as exc:
            resources = dict(unavailable_or_failed=repr(exc))
            finalization_errors.append(dict(stage='final_source_or_resource_gate', error=repr(exc)))
        pair_status = {}
        for name in ('fine', 'coarse'):
            try:
                pair_status[name] = observed_pair_status(OUT / ('comparison_' + name))
            except BaseException as exc:
                pair_status[name] = None
                finalization_errors.append(dict(stage='comparison_' + name + '_authentication', error=repr(exc)))
        complete = (qualified and errors is None and not finalization_errors
            and pair_status['fine'] is True and pair_status['coarse'] is True
            and counts.get('ledger_authenticated') is True and not counts.get('unresolved')
            and counts.get('known_unaccepted_work_rows') == counts.get('unknown_reserved_work_upper_bound') == 0)
        seal(OUT / 'final_disposition_01', dict(passed=complete, reason=reason, error=errors,
            finalization_errors=finalization_errors, qualification_passed=complete,
            full_path_accuracy_passed=complete, original_fine_pair_passed=pair_status['fine'],
            original_coarse_pair_passed=pair_status['coarse'], core_result_admitted=False,
            eligible_case_count_if_separate_final_execution_receipt_passes=2 if complete else 1,
            paper1_dataset_complete=False, successor_cases_dispatched=False,
            states=states, level_native_complete={key: value['native_complete'] for key, value in states.items()},
            independently_full_replayed_levels=sorted(replays),
            ledger=counts, prior_attempt_accounting=prior_attempt_accounting(),
            exact_registered_numerical_identities=identities,
            source_files=p['source_files'], physical_inputs=p['physical_inputs'], evidence_files=p['evidence_files'],
            historical_evidence_files=p['historical_evidence_files'],
            artifacts=artifact_inventory(), resources=resources, design_sha256=expected_design_sha,
            owner_and_supervisor_live_logs_intentionally_unsealed=True,
            separate_actual_supervisor_exit_and_closed_log_receipt_required=True, utc=utc()))
        show_state('final_disposition', passed=complete, qualification_passed=complete,
                   core_result_admitted=False, reason=reason, errors=errors, finalization_errors=finalization_errors)
    if not complete:
        raise SystemExit(2)


def supervise():
    """Hidden absolute watchdog. Its OWN exit/logs belong to external closure."""
    import psutil
    p = authority(False, refresh_sources=True)
    expected_design_sha = sha(PLAN)
    folder = OUT / 'supervisor'
    folder.mkdir(parents=True, exist_ok=False)
    me = psutil.Process(); me.cpu_affinity([14])
    launch = dict(pid=me.pid, created=me.create_time(), command=me.cmdline(),
                  design_sha256=expected_design_sha, utc=utc())
    commit(folder / 'launch.json', launch)
    handle = start_child(['owner'], OUT / 'owner')
    forced, failure = False, None
    # Preserve fifteen minutes for the caller's actual supervisor exit/closed
    # log authentication and separate external final receipt. Never another run.
    administrative_cutoff = instant(p['end_utc']) - 900
    try:
        while handle['process'].poll() is None:
            if time.time() >= administrative_cutoff:
                forced = True
                break
            time.sleep(.5)
    except BaseException as exc:
        failure = dict(message=repr(exc), traceback=traceback.format_exc())
        forced = True
    finally:
        if forced or handle['process'].poll() is not None:
            # Never leave a registered task-owned native worker orphaned after
            # owner failure. Only BOTH exact birth/full accessible command
            # permits stopping it; AccessDenied remains unresolved evidence.
            for row in registered_identities():
                try:
                    if not inspect_identity(row['launch'])['retired']:
                        exact_stop(psutil.Process(row['launch']['pid']), row['launch'])
                except BaseException as exc:
                    failure = dict(message='unresolved exact native identity', path=row['path'], error=repr(exc))
        exited = finish_child(handle, request_stop=forced, timeout=15.)
    identities = []
    for row in registered_identities():
        try:
            status = inspect_identity(row['launch'])
        except Exception as exc:
            status = dict(retired=False, unresolved_identity=True, error=repr(exc))
        identities.append(dict(**row, inspection=status))
    try:
        counts = ledger()
    except BaseException as exc:
        counts = failed_ledger(exc)
        failure = failure or dict(message='strict ledger failed', error=repr(exc))
    final_path = OUT / 'final_disposition_01/results.json'
    final = sealed(final_path) if final_path.exists() and final_path.with_name('completion.json').exists() else None
    passed = (exited['returncode'] == 0 and not exited['forced'] and not forced and failure is None
        and final is not None and final.get('passed') is True
        and all(item['inspection'].get('retired') is True for item in identities))
    seal(folder / 'completion_01', dict(passed=passed, directly_observed_owner_returncode=exited['returncode'],
        directly_observed_owner_exit_sha256=sha(OUT / 'owner/exit.json'),
        owner_forced=exited['forced'], shared_watchdog_forced=forced, error=failure,
        final_disposition_sha256=sha(final_path) if final_path.exists() else None,
        ledger=counts, prior_attempt_accounting=prior_attempt_accounting(),
        numerical_identities=identities, source_files=p['source_files'],
        physical_inputs=p['physical_inputs'], held_design_sha256=expected_design_sha,
        supervisor_own_returncode_not_observed_here=True, supervisor_live_logs_intentionally_unsealed=True,
        external_actual_supervisor_exit_and_closed_log_receipt_required=True,
        core_result_admitted=False, utc=utc()))
    if not passed:
        raise SystemExit(2)


def prepare():
    """Report source/fixture readiness only. Never creates numerical authority."""
    need(not AUTH.exists() and not PLAN.exists() and not OUT.exists(), 'source-only inactive family before any numerical authority')
    result = controls()
    result.update(interfaces=source_interfaces(), source_sha256=sha(SELF),
        source_files={str(path): sha(path) for path in (SELF, RUNTIME, AUDITOR, RESTART, POLICY, OLD_IDENTITIES)},
        approval_scope=approval_scope(), numerical_authority_created=False,
        native_model_execution_performed=False, numerical_launch_ready=False)
    print(json.dumps(result, sort_keys=True, indent=2), flush=True)
    return result


def controls():
    """Meaningful pure negatives on actual administrative predicates.

    No model module, force call, physical field, checkpoint reconstruction or
    campaign output is imported/opened. Test fixtures are synthetic and never
    labelled native/restart/physical qualification.
    """
    rejected = []
    clean = empty_counts()
    budget_guard(clean, 'f0p0625', 'production', PACKET_CAP)
    cases = [('global_work', {'work_rows': MAX_WORK}, 'production'),
             ('global_records', {'records': MAX_RECORDS}, 'production'),
             ('rejected_work', {'rejected_work_rows': MAX_REJECTED}, 'production'),
             ('production_records', {'production_records': MAX_PRODUCTION_RECORDS}, 'production'),
             ('standalone_work', {'standalone_work_rows': MAX_STANDALONE}, 'standalone'),
             ('standalone_records', {'standalone_records': MAX_STANDALONE_RECORDS}, 'standalone'),
             ('unknown', {'unresolved': [{}]}, 'production')]
    for name, update, kind in cases:
        trial = copy.deepcopy(clean); trial.update(update)
        try:
            budget_guard(trial, 'f0p0625', kind, 1)
        except RuntimeError:
            rejected.append(name)
    for key in LEVELS:
        trial = copy.deepcopy(clean); trial['levels'][key]['success_or_pending_work_rows'] = SUCCESS_CAPS[key]
        try:
            budget_guard(trial, key, 'production', 1)
        except RuntimeError:
            rejected.append(key + '_success_work')
    need(len(rejected) == 10, 'all real resource exhaustion/unknown predicates reject')
    start = datetime(2030, 1, 1, tzinfo=timezone.utc)
    clock = dict(start_utc=start.isoformat(), simulation_cutoff_utc=(start + timedelta(hours=124)).isoformat(),
        end_utc=(start + timedelta(hours=132)).isoformat(), fresh_independent_authority=True,
        old_authorities_closed_unchanged=True)
    validate_clock(clock, now=start.timestamp() + 1)
    for name, update, now in (
        ('clock_extension', {'end_utc': (start + timedelta(hours=132, seconds=1)).isoformat()}, start.timestamp()+1),
        ('clock_reserve', {'simulation_cutoff_utc': (start + timedelta(hours=125)).isoformat()}, start.timestamp()+1),
        ('clock_naive', {'start_utc': '2030-01-01T00:00:00'}, start.timestamp()+1),
        ('clock_expired', {}, (start + timedelta(hours=132)).timestamp())):
        try:
            validate_clock({**clock, **update}, now=now)
        except (RuntimeError, ValueError):
            rejected.append(name)
    branch = dict(branch_id='m1_C', role='C', compact_result={'runtime_seconds': 1., 'total_contact_iterations': 7},
        after_state={'q': [1., 2., 3., 4., 5., 6.]}, reactions=[2., 0., 0.])
    changed = copy.deepcopy(branch); changed['compact_result']['runtime_seconds'] = 2.
    need(restart_branch_projection(branch) == restart_branch_projection(changed), 'explicit raw timing is not physical restart state')
    for name, mutate in (
        ('q_perturbation', lambda b: b['after_state']['q'].__setitem__(0, 1.1)),
        ('reaction_perturbation', lambda b: b['reactions'].__setitem__(0, 2.1)),
        ('iteration_perturbation', lambda b: b['compact_result'].__setitem__('total_contact_iterations', 8))):
        changed = copy.deepcopy(branch); mutate(changed)
        need(restart_branch_projection(branch) != restart_branch_projection(changed), 'restart exactness keeps ' + name)
        rejected.append(name)
    need(MAX_WORK == sum(SUCCESS_CAPS.values()) + MAX_REJECTED + MAX_STANDALONE
         and BASELINE['case_work_rows'] + MAX_WORK == CASE_WORK
         and BASELINE['case_records'] + MAX_RECORDS == CASE_RECORDS
         and BASELINE['shared_work_rows'] + MAX_WORK == SHARED_WORK
         and BASELINE['shared_records'] + MAX_RECORDS == SHARED_RECORDS,
         'exact all-attempt allocation arithmetic')
    return dict(passed=True, pure_negative_controls=rejected,
        source_only_no_native_or_field_imports=True, zero_transport_steps=0,
        zero_native_force_calls=0, native_restart_qualified=False,
        original_full_path_gates_changed=False, numerical_launch_ready=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('prepare'); sub.add_parser('controls')
    auth = sub.add_parser('authorize_recovery')
    auth.add_argument('approval_sha256'); auth.add_argument('clock_sha256')
    auth.add_argument('initial_closure_sha256'); auth.add_argument('diagnosis_sha256'); auth.add_argument('preparation_sha256')
    sub.add_parser('supervise'); sub.add_parser('owner')
    work = sub.add_parser('worker'); work.add_argument('index', type=int)
    args = parser.parse_args(argv)
    if args.action == 'controls':
        print(json.dumps(controls(), sort_keys=True), flush=True)
    elif args.action == 'prepare':
        prepare()
    elif args.action == 'authorize_recovery':
        authorize_recovery(args.approval_sha256, args.clock_sha256, args.initial_closure_sha256,
                           args.diagnosis_sha256, args.preparation_sha256)
    elif args.action == 'supervise':
        supervise()
    elif args.action == 'owner':
        owner()
    elif args.action == 'worker':
        worker(args.index)


if __name__ == '__main__':
    main()
