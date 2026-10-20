"""Inactive, separately approved COMMON-STATE event-cap falsifier.

This module imports no physical engine and creates nothing on import.  The
frozen administrative worker/packet auditor is cloned into private globals;
old authority, full-path owner and case-admission functions are never used.
``authorize`` requires caller-pinned NEW human approval and a prospectively
fixed subwindow inside the ORIGINAL outer clock.  No command here resets it.
All new work, including useful local halves, is discarded diagnostic work.
"""
from __future__ import annotations

import argparse
import ast
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import lzma
import math
import os
from pathlib import Path
import shutil
import sys
import time
import traceback
from types import FunctionType, ModuleType

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
STAGING = ROOT / 'paper1_staging'
PARENT_FAMILY = ROOT / 'paper1_designs/contact_event_diagnostic_20261019'
FAMILY = ROOT / 'paper1_designs/contact_event_diagnostic_20261019_recovery02'
OUT = ROOT / 'paper1_runs/contact_event_diagnostic_20261019_recovery02'
PHYSICAL = PARENT_FAMILY / 'runtime_config_01.json'
PROPOSAL = PARENT_FAMILY / 'proposal_01.json'
PREPARED = FAMILY / 'preparation_01/results.json'
APPROVAL = PARENT_FAMILY / 'human_approval_01/results.json'
CLOCK = PARENT_FAMILY / 'window_clock_01/results.json'
PLAN = FAMILY / 'design_01.json'
AUTH = FAMILY / 'authorization_01.json'
OUTER_CLOCK = ROOT / 'paper1_designs/full_horizon_repair_20261018/qualification_clock_01/results.json'
SOURCE2 = ROOT / 'paper1_designs/contact_event_cap_20261019/source_preparation_02/results.json'
SOURCE2_SHA = 'bc9c2af8e97983287c1c22e4608b9b34369453362c2b214f4e0c2955742158fb'
SEEDS = ROOT / 'paper1_designs/contact_event_cap_20261019/seed_inputs_02'
SOURCE_PINS = SEEDS.parent / 'source_pins_02.json'
SOURCE_PINS_SHA = '5682367c823fbd705f7322e52b58300987760460a2fb6faa706f43e4eb623f61'
ADMIN = STAGING / 'run_stepdoubling_qualification_v4.py'
ADMIN_SHA = '05447c49e219dfff6849f6b2c543037b894feaafa71be184db5f44133e69cf69'
LAUNCH_SOURCE = STAGING / 'launch_stepdoubling_qualification_v4.py'
LAUNCH_SOURCE_SHA = '233da36e2dba696d328a1efa0f9dd7d9c13329371c49f05ac1a5ef75599b2725'
RUNTIME = STAGING / 'full_state_integration_adapter_v5.py'
AUDITOR = STAGING / 'audit_full_state_stepdoubling_v4.py'
RUNTIME_SHA = '1a9ff2828b0c313e7a90a99d8440387a79553114c65e648877f40f8c7a7ac7c2'
AUDITOR_SHA = '46e89f33f0a7c21ee502d2d8c8cae937f00b88b757099371ff2e1f8eed891430'
ORIGINAL_PHYSICAL = ROOT / 'paper1_designs/full_horizon_repair_20261018/physical_cases_qualification_01.json'
ORIGINAL_PHYSICAL_SHA = '952e3cf80c1b42ee86bd6402661085af367987c0015fff5c880f2ce4993f244a'
CLOSED = ROOT / 'paper1_runs/full_horizon_repair_20261018_recovery04/final_execution_receipt_01/results.json'
CLOSED_SHA = '6251eed02f4b3e5c3c4290f28f81cfd97edb364e2fc646866bc2234964045d25'
ABSOLUTE_END = '2026-10-24T07:43:33.769535+00:00'
START_T, STOP_T = .15328271968165677, .15368271968165678
LEVELS = ('f0p0625', 'f0p03125')
LOCAL_CAPS = dict(f0p0625=20000, f0p03125=40000)
LOCAL_CALL_CAPS = dict(f0p0625=8, f0p03125=14)
MAX_WORK, MAX_RECORDS, PACKET_CAP = 140000, 72, 4998
INITIAL_CAP, NATIVE_S = 768, 45.
NEW_BYTES, OWN_BYTES, RETENTION_BYTES, FREE_BYTES = 512*1024**2, 12*1024**3, 21*1024**3, 20*1024**3
PRIOR = dict(all_work_rows=752798, integration_records=186, numerical_windows=4,
             synthetic_nonadvancing_kernel_invocations=8,
             standalone_work_rows=11369, standalone_records=37,
             unknown_reserved_work_upper_bound=4838, known_unaccepted_work_rows=1728)
REMAINING = dict(all_work_rows=17247202, integration_records=3814,
                 standalone_work_rows=188631, standalone_records=113,
                 synthetic_nonadvancing_kernel_invocations=14, numerical_windows=7)
BASELINE = dict(case_work_rows=11065576, case_records=2360,
                shared_work_rows=5417664, shared_records=1190,
                diagnostic_work_rows=157450, diagnostic_records=103)
OLD_OUTPUTS = tuple(ROOT / ('paper1_runs/' + name) for name in (
    'full_horizon_repair_20261018', 'full_horizon_repair_20261018_recovery02',
    'full_horizon_repair_20261018_recovery03', 'full_horizon_repair_20261018_recovery04'))
SEED_SCHEMA = 'paper1.contact-event-diagnostic.external-seed.v1'
_PRIVATE = None
_RESERVE_HIGHWATER = [3600.]


def need(value, message):
    if not value:
        raise RuntimeError('Contact-event diagnostic: ' + message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=True,
                                     separators=(',', ':')).encode()).hexdigest()


def original_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=True).encode()).hexdigest()


def instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def utc():
    return datetime.now(timezone.utc).isoformat()


def approval_scope():
    return dict(independent_contact_event_diagnostic_authorized=True,
        maximum_new_all_work_rows=MAX_WORK, maximum_new_integration_records=MAX_RECORDS,
        maximum_nonadvancing_kernel_invocations=2, maximum_numerical_windows=1,
        maximum_window_minutes=120, maximum_native_minutes=60,
        maximum_new_retained_bytes=NEW_BYTES, maximum_combined_own_retained_bytes=OWN_BYTES,
        maximum_total_retained_bytes=RETENTION_BYTES, minimum_free_bytes=FREE_BYTES,
        original_shared_end_utc=ABSOLUTE_END,
        original_shared_simulation_cutoff_utc='2026-10-23T23:43:33.769535+00:00',
        all_new_work_discarded=True, no_full_path_or_core_admission=True)


def diagnostic_contract():
    return dict(independent_common_state_contact_event_diagnostic=True,
        maximum_new_all_trial_work_rows=MAX_WORK, maximum_new_integration_records=MAX_RECORDS,
        maximum_nonadvancing_synthetic_kernel_invocations=2, maximum_numerical_windows=1,
        maximum_subwindow_seconds=7200, maximum_numerical_seconds=3600,
        minimum_audit_retirement_reserve_seconds=3600,
        original_shared_end_utc=ABSOLUTE_END, same_original_outer_clock=True,
        maximum_local_path_all_work_by_level=LOCAL_CAPS,
        maximum_local_path_records_by_level=LOCAL_CALL_CAPS,
        start_time_s=START_T, stop_time_s=STOP_T, common_FULL_seed=True,
        old_bits_smoke_fresh_t0_source_compatibility_only=True,
        maximum_native_seconds_per_record=NATIVE_S, maximum_packet_all_work_rows=PACKET_CAP,
        initial_restart_record_work_cap=INITIAL_CAP, workers=1, threads=1, logical_cpu=14,
        maximum_unverified_records=1, new_output_bytes=NEW_BYTES,
        combined_old_new_output_bytes=OWN_BYTES, total_retention_bytes=RETENTION_BYTES,
        minimum_free_bytes=FREE_BYTES, all_work_discarded_diagnostics=True,
        shadows_rejects_partials_unknown_all_charged=True,
        exact_initial_C_F1_odd_restarts_required=True,
        first_actual_original_selector_restart_required=True,
        first_actual_event_cap_reduction_restart_required=True,
        late_FULL_exact_record_replay_required=True, unchanged_physics_and_accuracy_gates=True,
        positive_grain15_loading_required=True,
        loading_from_committed_independently_audited_native_branches_only=True,
        no_full_path_or_core_admission=True, no_old_failed_record_promotion=True,
        no_closed_stage_resumption=True, no_successor_case_dispatch=True)


def _clone_function(fn, namespace):
    result = FunctionType(fn.__code__, namespace, fn.__name__, fn.__defaults__, fn.__closure__)
    result.__kwdefaults__ = copy.copy(fn.__kwdefaults__)
    result.__annotations__ = copy.copy(fn.__annotations__)
    return result


def private_administration():
    """Clone every old function/class method; never rebind old module globals."""
    global _PRIVATE
    if _PRIVATE is not None:
        return _PRIVATE
    need(sha(ADMIN) == ADMIN_SHA, 'frozen administrative implementation')
    name = '_frozen_contact_event_admin_source'
    spec = importlib.util.spec_from_file_location(name, ADMIN)
    old = importlib.util.module_from_spec(spec)
    sys.modules[name] = old
    spec.loader.exec_module(old)  # stdlib definitions only; no engine or dispatch
    ns = dict(vars(old))
    for key, value in list(ns.items()):
        if isinstance(value, FunctionType) and value.__globals__ is vars(old):
            ns[key] = _clone_function(value, ns)
    cls = old.Execution
    attrs = {key: (_clone_function(value, ns) if isinstance(value, FunctionType)
                   else value) for key, value in vars(cls).items()
             if key not in ('__dict__', '__weakref__')}
    ns['Execution'] = type('Execution', cls.__bases__, attrs)
    ns['_DIAGNOSTIC_ORIGINAL_PACKET'] = ns['Execution'].packet
    ns['Execution'].packet = _clone_function(_diagnostic_packet, ns)
    saved = {key: ns[key] for key in ('load_reference', 'load_packet', 'store_packet', 'ledger',
        'budget_guard', 'source_interfaces', 'supervise', 'native_initial_matrix',
        'post_replay_record', 'preserve_boundary')}
    ns.update(ROOT=ROOT, SELF=SELF, OUT=OUT, DESIGNS=FAMILY, PROPOSAL=PROPOSAL,
        PREPARED=PREPARED, APPROVAL=APPROVAL, CLOCK=CLOCK, PHYSICAL=PHYSICAL, PLAN=PLAN, AUTH=AUTH,
        RUNTIME=RUNTIME, AUDITOR=AUDITOR, LEVELS=LEVELS, MAX_WORK=MAX_WORK,
        MAX_RECORDS=MAX_RECORDS, PACKET_CAP=PACKET_CAP, BASELINE=BASELINE,
        MAX_STANDALONE=MAX_WORK, MAX_STANDALONE_RECORDS=MAX_RECORDS,
        MAX_PRODUCTION_RECORDS=0, MAX_NONADVANCING_KERNEL_INVOCATIONS=2,
        MAX_WINDOWS=1, MAX_WINDOW_S=7200, OWN_BYTES=OWN_BYTES,
        RETENTION_BYTES=RETENTION_BYTES, FREE_BYTES=FREE_BYTES,
        OUTPUT_RESERVE=4*1024**2, _RESOURCE_LAST=[0., None], _DIAGNOSTIC_SAVED=saved,
        _RESERVE_HIGHWATER=[3600.])
    # Our replacement functions are also privately cloned, preserving one
    # cohesive recursive call graph for worker, Execution and source gates.
    replacements = ('authority', 'resource_guard', 'inventory_bytes', 'budget_guard', 'ledger',
        'load_engine', 'load_reference', 'store_packet', 'load_packet', 'definitions',
        'window_bounds', 'replay_reserve', 'prior_attempt_accounting', 'owner',
        'source_interfaces', 'local_path_usage', 'seed_reference', 'load_seed',
        'verify_seed_reference', 'verify_source_preparation', 'validate_contract',
        'validate_window', 'approval_scope', 'diagnostic_contract', 'post_replay_all', 'qualify',
        'event_journal', 'event_split', 'loading_coverage', 'qualified_local_level', 'evaluate_local',
        'verify_approval', 'original_outer_clock', 'held_failure_disposition')
    for key in replacements:
        ns[key] = _clone_function(globals()[key], ns)
    # Data referenced by the replacement code lives only in the new namespace.
    for key in ('FAMILY', 'OUTER_CLOCK', 'SOURCE2', 'SOURCE2_SHA', 'SOURCE_PINS',
        'SOURCE_PINS_SHA', 'SEEDS', 'RUNTIME_SHA', 'AUDITOR_SHA', 'ORIGINAL_PHYSICAL',
        'ORIGINAL_PHYSICAL_SHA', 'CLOSED', 'CLOSED_SHA', 'ABSOLUTE_END', 'START_T', 'STOP_T',
        'LOCAL_CAPS', 'LOCAL_CALL_CAPS', 'INITIAL_CAP', 'NEW_BYTES', 'PRIOR', 'REMAINING',
        'OLD_OUTPUTS', 'SEED_SCHEMA', 'ADMIN', 'ADMIN_SHA'):
        ns[key] = copy.deepcopy(globals()[key])
    module = ModuleType('_contact_event_diagnostic_private')
    module.__dict__.update(ns)
    # Functions must share the actual namespace rather than a copied module dict.
    module._namespace = ns
    _PRIVATE = module
    return module


def _diagnostic_packet(self, level_id, kind, label, input_prefix=None, *, cap=PACKET_CAP,
                       pause_rows=None, pause_time=None, phase=None, previous_receipt=None, operation='packet'):
    """Prospective role/seed/path ceilings BEFORE the literal old transaction."""
    need(level_id in LEVELS and kind=='standalone', 'only two fine levels; coarse/production unapproved')
    need(operation in ('packet','prelude','smoke_original','smoke_compiled'), 'bounded declared native operation')
    if operation=='packet':
        need(input_prefix is not None,'all local/restart paths start at explicit frozen common FULL seed, never t0')
        if isinstance(input_prefix,dict) and input_prefix.get('schema')==SEED_SCHEMA:
            need(input_prefix==seed_reference(level_id),'correct factor-specific seeded contract')
    else:
        need(input_prefix is None,'fresh t0 source compatibility/prelude carries no local prefix credit')
    if '_local_' in label:
        usage=local_path_usage()[level_id]
        need(operation=='packet' and label.startswith(level_id+'_local_')
             and usage['records']<LOCAL_CALL_CAPS[level_id]
             and usage['work_rows']+cap<=LOCAL_CAPS[level_id]
             and pause_rows is None and phase is None and pause_time==STOP_T,
             'local all-work/record bounds and pair-only fixed administrative pause BEFORE dispatch')
    return _DIAGNOSTIC_ORIGINAL_PACKET(self,level_id,kind,label,input_prefix,cap=cap,
        pause_rows=pause_rows,pause_time=pause_time,phase=phase,previous_receipt=previous_receipt,operation=operation)


def original_outer_clock():
    clock = sealed(OUTER_CLOCK, positive=True)
    need(clock['end_utc'] == ABSOLUTE_END and clock['maximum_shared_hours'] == 132,
         'original132h absolute end cannot be reopened or reset')
    return clock


def verify_source_preparation():
    need(sha(SOURCE2) == SOURCE2_SHA and sha(SOURCE_PINS) == SOURCE_PINS_SHA,
         'immutable corrected source/mock preparation02 and pins')
    source = sealed(SOURCE2, positive=True)
    need(source['new_force_calls'] == source['new_transport_steps'] == source['new_integration_records'] == 0
         and source['dispatch_authorized'] is False
         and source['execution_authority_created'] is False
         and source['closed_negative_sha256'] == CLOSED_SHA, 'source/mock preparation is not authority')
    need(sha(CLOSED) == CLOSED_SHA and sealed(CLOSED, positive=True)['passed'] is True,
         'old negative administrative closure preserved')
    need(sha(RUNTIME) == RUNTIME_SHA and sha(AUDITOR) == AUDITOR_SHA,
         'exact corrected producer/independent consumer factory pairing')
    verify_mapping(source['source_files'])
    verify_mapping(source['prospective_common_state_inputs'])
    return source


def seed_reference(level):
    need(level in LEVELS, 'prospective frozen seed level')
    source = verify_source_preparation()
    path = SEEDS / (level + '.json.xz')
    expected = source['prospective_common_state_inputs'][str(path)]
    need(sha(path) == expected, 'seed compressed bytes match source preparation')
    return dict(schema=SEED_SCHEMA, level_id=level, path=str(path), compressed_sha256=expected,
                source_preparation_sha256=SOURCE2_SHA, no_core_prefix_credit=True)


def verify_seed_reference(reference):
    need(isinstance(reference, dict) and reference.get('schema') == SEED_SCHEMA
         and reference == seed_reference(reference.get('level_id')), 'exact explicit diagnostic seed root')


def load_seed(reference):
    verify_seed_reference(reference)
    value = json.loads(lzma.decompress(Path(reference['path']).read_bytes(), format=lzma.FORMAT_XZ))
    cp = value['checkpoint']
    need(value['case']['level_id'] == reference['level_id']
         and cp['physical_checkpoint']['state']['t'] == START_T
         and len(cp['physical_checkpoint']['state']['history']) == 1972
         and cp['physical_checkpoint']['state']['steps'] == 493074
         and cp['physical_checkpoint']['state']['pending_trial'] is None
         and cp['cursor']['phase'] == 'idle' and not cp['pending_branches'],
         'literal accepted FULL common origin, idle NEW diagnostic controller')
    need(cp['physical_checkpoint']['state_sha256'] == original_digest(cp['physical_checkpoint']['state']),
         'original FULL state checksum before any diagnostic use')
    need(value['source_pins'] == read(SOURCE_PINS), 'seed source provenance is unchanged')
    return cp, value


def load_reference(reference, cache=None):
    if isinstance(reference, dict) and reference.get('schema') == SEED_SCHEMA:
        cp, _ = load_seed(reference)
        # A seed root is never a six-field accepted prefix. Its entire literal
        # history is embedded once in the first NEW packet root.
        return cp, None, cp['physical_checkpoint']['state']['history']
    return _DIAGNOSTIC_SAVED['load_reference'](reference, cache)


def store_packet(folder, packet, parent_prefix, parent_history):
    return _DIAGNOSTIC_SAVED['store_packet'](folder, packet, parent_prefix,
        [] if parent_prefix is None else parent_history)


def load_packet(path, expected_prefix, parent_prefix, parent_history):
    return _DIAGNOSTIC_SAVED['load_packet'](path, expected_prefix, parent_prefix,
        [] if parent_prefix is None else parent_history)


def definitions():
    proposal, physical = read(PROPOSAL), read(PHYSICAL)
    levels = {x['level_id']: x for x in proposal['levels']}
    cases = {x['level_id']: x for x in physical['cases']}
    return {key: dict(**levels[key], case=cases[key]) for key in LEVELS}


def validate_contract(proposal, physical, preparation):
    need(proposal['required_human_approval_scope'] == approval_scope()
         and proposal['baseline'] == BASELINE, 'exact diagnostic allocation and conservative prior baseline')
    need(proposal['diagnostic_contract'] == diagnostic_contract(), 'all bounded restart, path and native constraints frozen')
    need(proposal['physical_equation_changes'] == proposal['gap_policy_changes']
         == proposal['route_order_changes'] == [], 'unchanged original physics, gap and route order')
    need(proposal['original_accuracy_gates'] == ORIGINAL_GATES, 'original thresholds cannot be replaced by proxy bounds')
    source = verify_source_preparation()
    preview = read(SEEDS / 'physical_cases_preview.json')
    need(sha(ORIGINAL_PHYSICAL) == ORIGINAL_PHYSICAL_SHA
         and physical['minimum_gap_semantics'] == read(ORIGINAL_PHYSICAL)['minimum_gap_semantics'],
         'original literal minimum-gap semantics explicitly copied to native design')
    need(physical['cases'] == preview['cases'], 'frozen seed contract/spec/binding preserved; no silent seed rebind')
    need({x['level_id'] for x in proposal['levels']} == set(LEVELS), 'only two fine factors; prepared coarse seed stays undispatched')
    for definition in proposal['levels']:
        _, seed = load_seed(seed_reference(definition['level_id']))
        need(definition['limits'] == seed['limits'], 'original supplemental limits and numerical binding')
    need(preparation['passed'] is True and preparation['dispatch_authorized'] is False
         and preparation['all_required_interfaces_present'] is True, 'source-only readiness, no native claim')
    need(all(preparation['source_files'].get(str(p)) == sha(p) for p in (SELF, RUNTIME, AUDITOR, ADMIN)),
         'actual source interfaces are bound by preparation')
    for value in (proposal, preparation):
        for name in ('source_files', 'physical_inputs', 'evidence_files', 'historical_evidence_files'):
            verify_mapping(value[name])
    return True


def validate_window(clock, *, now=None):
    start, cutoff, end = (instant(clock[k]) for k in ('start_utc', 'simulation_cutoff_utc', 'end_utc'))
    need(0 < cutoff-start <= 3600 and 0 < end-start <= 7200 and end-cutoff >= 3600
         and cutoff <= instant('2026-10-23T23:43:33.769535+00:00')
         and end <= instant(ABSOLUTE_END), 'fixed<=120min inclusive/60min native/60min final reserve inside old cutoff/end')
    need(clock['original_shared_end_utc'] == ABSOLUTE_END
         and clock['original_outer_clock_sha256'] == sha(OUTER_CLOCK)
         and clock['proposal_sha256'] == sha(PROPOSAL), 'new subwindow binds unchanged original outer clock and exact proposal')
    when = time.time() if now is None else now
    need(start <= when < cutoff, 'subwindow is already running; preparation time is not reset/refunded')
    return start, cutoff, end


def verify_approval(approval, clock):
    need(approval['passed'] is True and approval['proposal_sha256'] == sha(PROPOSAL)
         and approval['required_human_approval_scope'] == approval_scope()
         and approval['independent_contact_event_diagnostic_authorized'] is True
         and approval['human_origin'] is True
         and isinstance(approval['verbatim_direct_human_reply'], str) and approval['verbatim_direct_human_reply'].strip()
         and isinstance(approval['approval_provenance'], dict) and approval['approval_provenance']
         and approval['window_clock_sha256'] == sha(CLOCK)
         and approval['original_outer_clock_sha256'] == sha(OUTER_CLOCK),
         'caller-pinned new explicit direct human approval, exact scope and fixed time evidence')
    validate_window(clock)


def authority(numerical=False, *, refresh_sources=False):
    environment()
    p, a = read(PLAN), read(AUTH)
    need(p['binding'] == digest({k:v for k,v in p.items() if k != 'binding'})
         and p['authorization_sha256'] == sha(AUTH)
         and all(p[k] == sha(path) for k,path in (
             ('physical_design_sha256', PHYSICAL), ('proposal_sha256', PROPOSAL),
             ('approval_sha256', APPROVAL), ('clock_sha256', CLOCK), ('preparation_sha256', PREPARED),
             ('original_outer_clock_sha256', OUTER_CLOCK)))
         and a['required_human_approval_scope'] == approval_scope(), 'immutable independent diagnostic authority only')
    need(all(p[k] == read(CLOCK)[k] for k in ('start_utc','simulation_cutoff_utc','end_utc'))
         and p['original_shared_end_utc'] == ABSOLUTE_END, 'no administrative clock replacement')
    now = time.time()
    need(instant(p['start_utc']) <= now < instant(p['end_utc']) <= instant(ABSOLUTE_END), 'unchanged absolute cutoff')
    if numerical:
        need(now < instant(p['simulation_cutoff_utc']), 'fixed native cutoff')
    resource_guard(force_inventory=refresh_sources)
    if refresh_sources:
        for name in ('source_files','physical_inputs','evidence_files','historical_evidence_files'):
            verify_mapping(p[name])
    return p


def authorize(expected_approval_sha256, expected_preparation_sha256, expected_outer_clock_sha256):
    """Explicit post-human action only. Creates no actor and no numerical work."""
    n = private_administration()._namespace
    n['environment']()
    need(not PLAN.exists() and not AUTH.exists() and not OUT.exists(), 'one create-only independent experiment')
    need(sha(APPROVAL) == expected_approval_sha256 and sha(PREPARED) == expected_preparation_sha256
         and sha(OUTER_CLOCK) == expected_outer_clock_sha256, 'three caller-supplied exact trusted evidence pins')
    approval = n['sealed'](APPROVAL, positive=True)
    clock = n['sealed'](CLOCK, positive=True)
    n['original_outer_clock']()
    n['verify_approval'](approval, clock)
    proposal, physical = read(PROPOSAL), read(PHYSICAL)
    preparation = n['sealed'](PREPARED, positive=True)
    n['validate_contract'](proposal, physical, preparation)
    n['resource_guard'](force_inventory=True)
    auth = dict(schema='paper1.contact-event-diagnostic.authorization.v1', passed=True,
        approval_sha256=expected_approval_sha256, preparation_sha256=expected_preparation_sha256,
        original_outer_clock_sha256=expected_outer_clock_sha256, proposal_sha256=sha(PROPOSAL),
        clock_sha256=sha(CLOCK), required_human_approval_scope=approval_scope(),
        full_path_or_core_admission_authorized=False, utc=utc())
    n['commit'](AUTH, auth)
    maps = {name:n['merge_maps'](proposal[name], preparation[name]) for name in
            ('source_files','physical_inputs','evidence_files','historical_evidence_files')}
    p = dict(schema='paper1.contact-event-diagnostic.design.v1',
        **{k:clock[k] for k in ('start_utc','simulation_cutoff_utc','end_utc')},
        original_shared_end_utc=ABSOLUTE_END, authorization_sha256=sha(AUTH),
        physical_design_sha256=sha(PHYSICAL), proposal_sha256=sha(PROPOSAL),
        approval_sha256=sha(APPROVAL), clock_sha256=sha(CLOCK), preparation_sha256=sha(PREPARED),
        original_outer_clock_sha256=sha(OUTER_CLOCK), prior_attempt_accounting=prior_attempt_accounting(), **maps)
    p['binding'] = digest(p)
    n['commit'](PLAN, p)
    return p


def inventory_bytes(root=ROOT):
    new = sum(p.stat().st_size for folder in (OUT, ROOT/'paper1_runs/contact_event_diagnostic_20261019')
              if folder.exists() for p in folder.rglob('*') if p.is_file())
    combined = new + sum(p.stat().st_size for folder in OLD_OUTPUTS if folder.exists()
                         for p in folder.rglob('*') if p.is_file())
    total = sum(p.stat().st_size for folder in ('paper1_designs','paper1_runs','paper1_evaluations')
                for p in (root/folder).rglob('*') if p.is_file())
    return new, combined, total, shutil.disk_usage(root).free


def resource_guard(*, force_inventory=False, reserve=4*1024**2):
    need(type(reserve) is int and reserve >= 0, 'nonnegative retention reservation')
    need(shutil.disk_usage(ROOT).free >= FREE_BYTES+reserve, '20GiB free plus pending output')
    now = time.monotonic()
    if force_inventory or _RESOURCE_LAST[1] is None or now-_RESOURCE_LAST[0] >= 60:
        _RESOURCE_LAST[:] = [now, inventory_bytes()]
    new, combined, total, free = _RESOURCE_LAST[1]
    need(new+reserve <= NEW_BYTES and combined+reserve <= OWN_BYTES and total+reserve <= RETENTION_BYTES,
         '512MiB new,12GiB all-attempt own and21GiB global retention ceilings')
    return dict(new_bytes=new, combined_old_new_bytes=combined, total_retained_bytes=total,
                free_bytes=free, conservative_output_reserve_bytes=reserve)


def prior_attempt_accounting():
    return dict(original_grant_spent=PRIOR, original_grant_remaining=REMAINING,
        old_unknown_work_never_refunded=True, old_failures_preserved=True,
        new_all_work_discarded_diagnostics=True, old_closed_stage_resumed=False)


def local_path_usage(counts=None):
    usage = {key:dict(work_rows=0,records=0) for key in LEVELS}
    for path in sorted((OUT/'reservations').glob('*.json')):
        row = read(path)
        if '_local_' not in row['label']:
            continue
        n = row['maximum_work_rows']
        admission = OUT/'admissions'/path.stem/'results.json'
        if admission.exists() and admission.with_name('completion.json').exists():
            n = sealed(admission, positive=True)['work_rows']
        usage[row['level_id']]['work_rows'] += n
        usage[row['level_id']]['records'] += 1
    return usage


def budget_guard(counts, level_id, kind, cap):
    need(kind == 'standalone', 'all experiment work is discarded standalone diagnostics')
    _DIAGNOSTIC_SAVED['budget_guard'](counts, level_id, kind, cap)
    need(PRIOR['all_work_rows']+counts['work_rows']+cap <= 18000000
         and PRIOR['integration_records']+counts['records']+1 <= 4000
         and PRIOR['standalone_work_rows']+counts['work_rows']+cap <= 200000
         and PRIOR['standalone_records']+counts['records']+1 <= 150,
         'original shared/standalone caps include all old unknown and current full reservations')
    return True


def ledger():
    result = _DIAGNOSTIC_SAVED['ledger']()
    need(result['production_records'] == 0 and result['accepted_committed_half_rows'] == 0
         and result['discarded_diagnostic_work_rows'] == result['work_rows'],
         'no numerical-core production credit; all charged work remains diagnostic')
    usage = local_path_usage(result)
    need(all(v['work_rows'] <= LOCAL_CAPS[k] and v['records'] <= LOCAL_CALL_CAPS[k]
             for k,v in usage.items()), 'explicit bounded local path suballocations')
    result['local_path_usage'] = usage
    return result


def replay_reserve(counts, audited_levels=()):
    """Only-growing measured replay reserve, checked before EVERY next cap.

    This is a conservative scheduling proxy, never a proven wall-time bound.
    All admitted trial work must still be replayed before the fixed deadline.
    At least15min of this tail is kept for exact retirement/log/exit closure.
    """
    reserved=sum(read(p)['maximum_work_rows'] for p in (OUT/'reservations').glob('*.json'))
    prospective=max(reserved,counts['work_rows'],counts['standalone_work_rows'])
    rate=.01592;small_record_seconds=0.
    for path in (OUT/'admissions').glob('*/results.json'):
        value=sealed(path,positive=True)
        n=value.get('work_rows',0)
        if n>0 and 'independent_replay_seconds' in value:
            seconds=value['independent_replay_seconds']
            need(math.isfinite(seconds) and seconds>=0,'finite measured independent replay wall')
            if n>=128:rate=max(rate,2*seconds/n)
            else:small_record_seconds=max(small_record_seconds,seconds)
    fixed_overhead=900.+MAX_RECORDS*small_record_seconds
    value=max(_RESERVE_HIGHWATER[0],3600.,fixed_overhead+rate*prospective)
    _RESERVE_HIGHWATER[0]=value
    index=len(list((OUT/'reserve_estimates').glob('*.json')))+1
    commit(OUT/'reserve_estimates'/f'{index:06d}.json',dict(
        minimum_postworker_tail_seconds=3600,postworker_reserve_seconds=value,
        prospective_reserved_all_trial_rows=prospective,seconds_per_row_proxy=rate,
        minimum_work_rows_for_per_row_estimate=128,
        maximum_observed_small_record_seconds=small_record_seconds,
        separately_reserved_small_record_and_exit_overhead_seconds=fixed_overhead,
        reserve_only_grows=True,proxy_is_not_guaranteed_completion=True,
        fixed_absolute_end_utc=ABSOLUTE_END,utc=utc()))
    return value


def window_bounds(plan, now, index, reserve_s):
    need(index == 1 and instant(plan['start_utc']) <= now < instant(plan['simulation_cutoff_utc'])
         and instant(plan['simulation_cutoff_utc'])-now > 2*NATIVE_S+120,
         'one fixed bounded worker window, no retry window or refunded setup')
    stop=min(instant(plan['simulation_cutoff_utc']),instant(plan['end_utc'])-reserve_s)
    need(stop-now>2*NATIVE_S+120,'growing replay reserve leaves a bounded actual native record and cleanup')
    return stop


def load_engine():
    need(sha(RUNTIME) == RUNTIME_SHA and sha(AUDITOR) == AUDITOR_SHA, 'exact paired independent factory')
    if str(STAGING) not in sys.path:
        sys.path.insert(0, str(STAGING))
    import importlib
    return (importlib.import_module('full_state_integration_adapter_v5'),
            importlib.import_module('audit_full_state_stepdoubling_v4'),
            importlib.import_module('prepare_stepdoubling_restart_v1'),
            importlib.import_module('full_state_stepdoubling_v1'))


def source_interfaces():
    answer = _DIAGNOSTIC_SAVED['source_interfaces']()
    answer.update(diagnostic_only=True, native_qualification_passed=False,
                  numerical_launch_ready=False, separate_new_human_approval_required=True)
    return answer


def supervise():
    """Only explicit CLI invocation after pinned authority; no implicit launch."""
    n=private_administration()._namespace
    n['authority'](False,refresh_sources=True)
    return n['supervise']()


def launch():
    """Literal qualified original Popen wrapper, privately paired to THIS run.

    No old wrapper module/import/authority is executed. Its one launch body is
    extracted only after the NEW approved authority passes. It records actual
    supervisor return and closes logs; its own exit belongs to external close.
    """
    private=private_administration()
    n=private._namespace
    n['authority'](False,refresh_sources=True)
    need(sha(LAUNCH_SOURCE)==LAUNCH_SOURCE_SHA,'frozen qualified launch wrapper source')
    tree=ast.parse(LAUNCH_SOURCE.read_text(encoding='utf-8'))
    fn=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='launch')
    namespace=dict(run=private,Path=Path,os=os,subprocess=n['subprocess'],sys=sys,time=time)
    exec(compile(ast.Module(body=[copy.deepcopy(fn)],type_ignores=[]),str(LAUNCH_SOURCE)+'::PRIVATE_LAUNCH','exec'),namespace)
    return namespace['launch']()


def worker(index):
    n=private_administration()._namespace
    n['authority'](True,refresh_sources=True)
    need(index==1,'only the one approved worker')
    return n['worker'](index)


def evaluate(execution, states):
    n=private_administration()._namespace
    n['authority'](False,refresh_sources=True)
    return n['evaluate_local'](execution,states)


def event_journal(packet, which):
    need(which in ('original_selector','event_reduction'), 'declared distinct first-event gate')
    if which == 'original_selector':
        return accepted_journal(packet)
    branches = {b['branch_id']:b for b in packet['work_branches']+packet['carried_branches']}
    events = {}
    for trial in packet['trials']:
        decision = trial['decision']
        if decision is None or decision['action'] != 'commit_literal_halves':
            continue
        reduced = trial['macro_initial_cap_s'] < trial['original_selected_cap_s']
        for bid in trial['branch_ids'][1:]:
            events[bid] = reduced
    # Each accepted row is matched to the literal committed branch, not the
    # coarseshadow or a rejected trial. All event operands are independently
    # replayed by the packet auditor before this administrative lookup.
    result = []
    for bid in packet['committed_branch_ids']:
        b = branches[bid]
        need(b['role'] in ('F1','F2') and bid in events, 'accepted event derives from its passed pair')
        result.append(dict(role=b['role'], trigger_grain_ids=[-1] if events[bid] else [], branch_id=bid))
    need(len(result) == len(packet['accepted_rows']), 'one accepted event lookup per literal row')
    return result


def event_split(packet, which):
    journal = event_journal(packet, which)
    n = len(packet['accepted_rows'])
    found = next((i for i,x in enumerate(journal) if x['trigger_grain_ids']), None)
    need(found is not None and n > 0 and n%2 == 0, 'actual complete first-event record required')
    j = 2*(found//2)
    need(0 < j < n and j <= found and not any(x['trigger_grain_ids'] for x in journal[:j]),
         'legal positive EVEN split before actual first accepted event, no later easier record')
    return dict(N=n,j=j,first_accepted_event_index=found,event=which)


def loading_coverage(packet):
    """Saved committed F1/F2 last-map reactions, AFTER independent raw audit.

    A selector, a coarse shadow, a discarded retry and an uncommitted pending
    branch cannot establish that grain15 was actually loaded on this path.
    This function does not solve contact or replace the mechanical stencil.
    """
    inventory=packet['work_branches']+packet['carried_branches']
    branches={b['branch_id']:b for b in inventory}
    need(len(branches)==len(inventory), 'unique raw branch inventory for loading coverage')
    need(len(packet['committed_branch_ids'])==len(packet['accepted_rows']), 'one actual committed branch per accepted row')
    first=None
    for index,bid in enumerate(packet['committed_branch_ids']):
        branch=branches[bid]
        need(branch['role'] in ('F1','F2') and branch['error'] is None
             and len(branch['rows'])==1 and branch['rows'][0]==packet['accepted_rows'][index]
             and branch['compact_result']['rejected']==0,
             'only literal accepted physical half rows with zero original rejection')
        row=branch['rows'][0];trace=branch['contact_trial_trace']
        cycles=trace['cycle_guard_trials'];counts=trace['trial_inner_counts']
        prepared=branch['normal_gap_operand_policy']['prepare_calls']
        need(len(cycles)==len(counts)==len(prepared)==1,'exact original one-row trial/prepare/cycle association')
        cycle,call=cycles[0],prepared[0];inner=cycle['records']
        need(cycle['trial_index']==call['index']==0 and len(inner)==counts[0]>0
             and all(value['inner_index']==i for i,value in enumerate(inner))
             and inner[-1]['map_output']==row['velocity_generalized']
             and [int(c[0]) for c in call['contacts']]==row['active_contact_ids'],
             'last accepted inner map and literal native prepare contact order')
        reactions=inner[-1]['health']['reactions']
        need(len(reactions)==3*len(call['contacts']) and all(math.isfinite(x) for x in reactions),
             'finite native ordered normal/tangential reactions')
        for k,contact in enumerate(call['contacts']):
            if int(contact[0])==15 and reactions[3*k]>0 and 15 in row['supported_bearing_ids'] and first is None:
                first=dict(accepted_row_index=index,branch_id=bid,role=branch['role'],
                    accepted_time_s=row['time_s'],normal_reaction_N=reactions[3*k],
                    raw_gap_m=contact[1],grain_id=15,last_inner_index=inner[-1]['inner_index'],
                    predicate='lambda_n > 0 and grain15 in actual accepted supported_bearing_ids',
                    raw_branch_sha256=digest(branch),mechanical_solve_performed_here=False)
    return dict(association_verified=True,first_positive_normal_reaction_grain15=first)


def qualify(execution, level, anchor, input_prefix, previous_receipt=None, *,
            original_packet=None, original_cap=INITIAL_CAP, phase=None, accepted_rows=256, event=None):
    """Actual serial/split, exact raw/FULL/cursor/history, never change path."""
    need(anchor in ('initial','after_coarse','after_first_half','odd_accepted_half',
                    'first_original_selector','first_event_reduction','late_FULL'), 'fixed qualification matrix')
    tag = level+'_'+anchor
    folder = OUT/'levels'/level/'restarts'/tag
    need(not folder.exists(), 'no repeated failed qualification or easier replacement')
    serial, _, _ = execution.packet(level,'standalone',tag+'_serial',input_prefix,cap=original_cap,
        pause_rows=None if original_packet is not None else accepted_rows,previous_receipt=previous_receipt)
    if original_packet is not None:
        n = len(original_packet['accepted_rows'])
        split = event_split(original_packet,event) if event else dict(N=n,j=n//2,event=None)
        j = split['j']
        need(n > 0 and n%2 == 0 and 0 < j < n and (event is None or j%2 == 0)
             and original_packet['checkpoint']['physical_checkpoint']['state']['pending_trial'] is None,
             'original full pair-boundary record and positive even exact split')
    else:
        n, j, split = accepted_rows, (1 if anchor == 'odd_accepted_half' else accepted_rows//2), None
    left, left_prefix, receipt = execution.packet(level,'standalone',tag+'_left',input_prefix,
        cap=original_cap,pause_rows=None if phase else j,phase=phase,previous_receipt=previous_receipt)
    remainder = original_cap-left['work_rows']
    need(0 < remainder <= PACKET_CAP, 'charged split successor bounded by ORIGINAL record cap')
    right, _, _ = execution.packet(level,'standalone',tag+'_right',left_prefix,cap=remainder,
        pause_rows=None if original_packet is not None else n-len(left['accepted_rows']),previous_receipt=receipt)
    need(serial['work_rows'] <= original_cap and left['work_rows']+right['work_rows'] <= original_cap,
         'combined split ALL-work cap, never three independently spendable proof caps')
    need(len(serial['accepted_rows']) == n == len(left['accepted_rows'])+len(right['accepted_rows']),
         'exact planned256 or originalN, finite retries cannot silently shorten qualification')
    restart_equal(serial,[left,right],reference=original_packet)
    if anchor == 'initial':
        need(not any(x['trigger_grain_ids'] for p in (serial,left,right) for x in accepted_journal(p)),
             'initial qualification must remain pre-FIRST-original-trigger')
        need(not any(x['trigger_grain_ids'] for p in (serial,left,right) for x in event_journal(p,'event_reduction')),
             'initial qualification must remain pre-FIRST-event-cap-reduction')
    if event:
        need(not any(x['trigger_grain_ids'] for x in event_journal(left,event))
             and any(x['trigger_grain_ids'] for x in event_journal(right,event)),
             'FIRST actual accepted event stays in split successor')
    if phase:
        need(left['cursor_after']['phase'] == {'C_done':'after_coarse','F1_done':'after_first_half'}[phase]
             and not left['accepted_rows'], 'actual staged uncommitted physical branch interruption')
    if anchor == 'odd_accepted_half':
        need(len(left['accepted_rows']) == 1 and left['cursor_after']['phase'] == 'publish_second_half',
             'passedpair F1 literalpublication/F2 staged, no prematurecommit')
    artifacts = {str(p):sha(p) for label in (tag+'_serial',tag+'_left',tag+'_right')
                 for p in (OUT/'records'/label).rglob('*') if p.is_file()}
    body = dict(passed=True,level_id=level,anchor=anchor,actual_first_event_split=split,
        exact_all_trial_observations=True,exact_accepted_rows=True,exact_FULL_checkpoint_history=True,
        exact_semantic_controller_and_ledger=True,original_path_restored_unchanged=True,
        original_input_prefix=input_prefix, original_input_controller_sha256=digest(load_reference(input_prefix,execution.reference_cache)[0]),
        discarded_all_work_rows=serial['work_rows']+left['work_rows']+right['work_rows'],
        separate_actual_record_charges=3,artifact_files=artifacts,source_files=execution.plan['source_files'],
        design_sha256=sha(PLAN),full_path_or_core_admission=False,utc=utc())
    seal(folder,body)
    return body


def qualified_local_level(execution, key, state=None):
    seed = seed_reference(key)
    state={} if state is None else state
    state.update(prefix=seed,previous_receipt=None,time_s=START_T,local_complete=False,
                 first_original_selector_qualified=False,first_event_reduction_qualified=False,
                 late_FULL_qualified=False,old_prefix_credit=False,local_labels=[],
                 first_positive_normal_reaction_grain15=None)
    original,_,_ = execution.packet(key,'standalone',key+'_smoke_original32',cap=32,operation='smoke_original')
    compiled,_,_ = execution.packet(key,'standalone',key+'_smoke_compiled32',cap=32,operation='smoke_compiled')
    need(original['record']['rows'] == compiled['record']['rows']
         and original['physical_checkpoint'] == compiled['physical_checkpoint'], 'exact old32 vs compiledC32 source compatibility')
    seal(OUT/'levels'/key/'old_bits_smoke_01',dict(passed=True,discarded_work_rows=64,
        original_fresh_t0_source_compatibility_only=True,local_seed_or_prefix_credit=False,
        exact_rows=True,exact_FULL_checkpoint_history=True,design_sha256=sha(PLAN),utc=utc()))
    for anchor,phase in (('initial',None),('after_coarse','C_done'),('after_first_half','F1_done'),('odd_accepted_half',None)):
        qualify(execution,key,anchor,seed,phase=phase)
    prefix, previous, t = seed, None, START_T
    old_qualified = event_qualified = False
    last = None
    for i in range(1,LOCAL_CALL_CAPS[key]+1):
        usage = local_path_usage()[key]
        remaining = LOCAL_CAPS[key]-usage['work_rows']
        cap = min(PACKET_CAP,remaining)
        need(cap >= 3, 'local all-trial path budget exhausted; never increase cap or choose easier seed')
        # Reserve worst-case TWO future event replays +late replay before any
        # new local record. Missing event coverage is an incomplete negative.
        future_replays = int(not old_qualified)+int(not event_qualified)+1
        counts = ledger()
        need(counts['work_rows']+cap+future_replays*2*cap <= MAX_WORK
             and counts['records']+1+3*future_replays <= MAX_RECORDS,
             'mandatory native replay room before dependent local work')
        before_prefix,before_receipt = prefix,previous
        packet,prefix,previous = execution.packet(key,'standalone',f'{key}_local_{i:03d}',prefix,
            cap=cap,pause_time=STOP_T,previous_receipt=previous)
        need(packet['cursor_after']['phase'] in ('idle','after_rejection') and not packet['checkpoint']['pending_branches']
             and packet['status'] != 'negative', 'completepair local boundaries only')
        next_t = packet['checkpoint']['physical_checkpoint']['state']['t']
        need(t < next_t and next_t <= STOP_T, 'local design ends at frozen stop, no external horizon advancement')
        state.update(prefix=prefix,previous_receipt=previous,time_s=next_t)
        state['local_labels'].append(f'{key}_local_{i:03d}')
        coverage=loading_coverage(packet)
        if state['first_positive_normal_reaction_grain15'] is None and coverage['first_positive_normal_reaction_grain15'] is not None:
            label=f'{key}_local_{i:03d}'
            state['first_positive_normal_reaction_grain15']=dict(
                **coverage['first_positive_normal_reaction_grain15'],label=label,
                raw_packet_sha256=sha(OUT/'records'/label/'packet.json.xz'),
                independent_mechanical_audit_sha256=sha(OUT/'records'/label/'policy_mechanical_audit_01/results.json'))
        if not old_qualified and any(x['trigger_grain_ids'] for x in event_journal(packet,'original_selector')):
            qualify(execution,key,'first_original_selector',before_prefix,before_receipt,
                    original_packet=packet,original_cap=cap,event='original_selector')
            old_qualified = True
            state['first_original_selector_qualified']=True
        if not event_qualified and any(x['trigger_grain_ids'] for x in event_journal(packet,'event_reduction')):
            qualify(execution,key,'first_event_reduction',before_prefix,before_receipt,
                    original_packet=packet,original_cap=cap,event='event_reduction')
            event_qualified = True
            state['first_event_reduction_qualified']=True
        last = (packet,before_prefix,before_receipt,cap)
        t = next_t
        if t == STOP_T:
            break
    need(t == STOP_T and old_qualified and event_qualified,
         'complete fixed interval and BOTH actual first-event qualifications required')
    need(state['first_positive_normal_reaction_grain15'] is not None,
         'targetgrain15 actual positive accepted normal loading required; event approach alone is incomplete')
    packet,before_prefix,before_receipt,cap = last
    qualify(execution,key,'late_FULL',before_prefix,before_receipt,original_packet=packet,original_cap=cap)
    _DIAGNOSTIC_SAVED['preserve_boundary'](key,prefix,name='discarded_local_full_boundary_01')
    state.update(local_complete=True,late_FULL_qualified=True)
    return state


def post_replay_all(execution,states):
    execution.close_window()
    for path in (OUT/'windows').glob('window_*/launch.json'):
        need(inspect_identity(read(path))['retired'] is True, 'window exactbirth+fullcommand retired before final full replay')
    cache, outputs = {}, []
    coverage={key:None for key in LEVELS}
    for path in sorted((OUT/'reservations').glob('*.json')):
        row = read(path)
        packet = _DIAGNOSTIC_SAVED['post_replay_record'](execution,row,cache=cache)
        if packet is not None and '_local_' in row['label']:
            actual=loading_coverage(packet)['first_positive_normal_reaction_grain15']
            if coverage[row['level_id']] is None and actual is not None:
                label=row['label']
                coverage[row['level_id']]=dict(**actual,label=label,
                    raw_packet_sha256=sha(OUT/'records'/label/'packet.json.xz'),
                    independent_mechanical_audit_sha256=sha(OUT/'records'/label/'policy_mechanical_audit_01/results.json'))
        outputs.append(dict(index=row['index'],label=row['label'],all_trial_mechanics_raw_FULL_replayed=True,
            original_FULL_output_sha256=None if packet is None else original_digest(packet['checkpoint']['physical_checkpoint'])))
    need(all(coverage[key] is not None and coverage[key]==states[key]['first_positive_normal_reaction_grain15']
             for key in LEVELS),'independently full-replayed local committed grain15 loading equals recorded coverage')
    seal(OUT/'all_discarded_records_replay_01',dict(passed=True,records=outputs,committed_loading_coverage=coverage,
        all_new_work_discarded_diagnostics=True,old_failed_records_admitted=False,
        full_path_or_core_admission=False,design_sha256=sha(PLAN),utc=utc()))
    return outputs


def evaluate_local(execution, states):
    """Literal original metric functions on NEW local traces; no whole-path claim."""
    shared, _ = metric_interface()
    metric = shared.s.q.job.path_metrics.metrics
    import numpy as np
    paths, endpoints = {}, {}
    for key in LEVELS:
        rows = []
        for file in sorted((OUT/'reservations').glob('*.json')):
            r = read(file)
            if r['level_id'] == key and '_local_' in r['label']:
                admission = sealed(OUT/'admissions'/file.stem/'results.json',positive=True)
                verify_mapping(admission['artifacts'])
                rows.extend(read_trace(OUT/'records'/r['label']/'trace.npy'))
        need(rows and rows[0][0] > START_T and rows[-1][0] == STOP_T, 'complete local raw trace coverage')
        paths[key] = rows
        cp,_,_=load_reference(states[key]['prefix'],execution.reference_cache)
        endpoints[key]=cp['physical_checkpoint']['state']
    # Original absolute-clock Cursor, norm/dot/fsum and endpoint rules.  No
    # time shift, rotation scaling, director sign alignment or event alignment.
    def pair(a,b):
        cp,_ = load_seed(seed_reference(a)); state=cp['physical_checkpoint']['state']
        initial=[state['t'],*state['x'],*state['p'],*state['q']]
        cfg=definitions()[a]['case']['spec']['config']
        values=metric(iter([np.asarray(paths[a],dtype=np.float64)]),
            iter([np.asarray(paths[b],dtype=np.float64)]),initial,initial,STOP_T,STOP_T,
            cfg['prolate_semiaxes_m'][1],cfg['target_mean_interstitial_velocity_m_s'])
        tests={name:values[name] <= ORIGINAL_GATES[name] for name in (
            'endpoint_q_over_U_max','mean_L1_q_over_U_max',
            'whole_position_over_b_max','whole_axis_vector_norm_max')}
        first,second=endpoints[a],endpoints[b]
        tests['same_terminal_label']=first['t']==second['t']==STOP_T
        tests['same_dwell_flag']=first['last_trap_state']['trapped']==second['last_trap_state']['trapped']
        da,db=first['first_contact_dwell_time'],second['first_contact_dwell_time']
        tests['first_dwell_time_difference']=((da is None and db is None) or
            (da is not None and db is not None and abs(da-db)<=ORIGINAL_GATES['first_dwell_time_difference_s_max']))
        tests['same_fixed_interval_end']=abs(first['t']-second['t'])<=ORIGINAL_GATES['exit_time_difference_s_max']
        return dict(first=a,second=b,metrics=values,original_gate_values=ORIGINAL_GATES,
                    local_gate_results=tests,passed=all(tests.values()))
    pairs=[pair('f0p0625','f0p03125')]
    result=dict(passed=all(p['passed'] for p in pairs),pairs=pairs,
        interval_s=[START_T,STOP_T],local_only=True,independent_old_fullpath_negative_preserved=True,
        order_or_global_accuracy_claimed=False,full_horizon_accuracy_repaired=False,
        metric_source=str(Path(metric.__code__.co_filename).resolve()),
        metric_source_sha256=sha(metric.__code__.co_filename),
        full_path_or_core_admission=False,design_sha256=sha(PLAN),utc=utc())
    seal(OUT/'local_comparison_01',result)
    return result


def held_failure_disposition(p, expected_design, states, errors, execution, success):
    """Failure-only accounting never opens a gate or relabels changed sources."""
    failures=[]
    if execution is not None and execution.handle is not None:
        try: execution.close_window()
        except BaseException as exc: failures.append(dict(stage='exact_worker_retirement',error=repr(exc)))
    for key,state in states.items():
        prefix=state.get('prefix')
        if prefix is not None and prefix.get('schema')!=SEED_SCHEMA:
            folder=OUT/'levels'/key/'last_sealed_partial_01'
            if not folder.exists():
                try:_DIAGNOSTIC_SAVED['preserve_boundary'](key,prefix,name='last_sealed_partial_01')
                except BaseException as exc:failures.append(dict(stage='preserve_last_sealed_FULL_'+key,error=repr(exc)))
    try: counts=ledger()
    except BaseException as exc:
        counts=failed_ledger(exc);failures.append(dict(stage='strict_ledger',error=repr(exc)))
    identities=[]
    for row in registered_identities():
        try: status=inspect_identity(row['launch'])
        except BaseException as exc: status=dict(retired=False,unresolved_identity=True,error=repr(exc))
        identities.append(dict(**row,inspection=status))
        if status.get('retired') is not True: failures.append(dict(stage='unresolved_identity',path=row['path']))
    try:
        for name in ('source_files','physical_inputs','evidence_files','historical_evidence_files'):verify_mapping(p[name])
        need(sha(PLAN)==expected_design,'held original PLAN binding')
        resources=resource_guard(force_inventory=True)
    except BaseException as exc:
        resources=dict(unavailable_or_failed=repr(exc));failures.append(dict(stage='source_or_resource',error=repr(exc)))
    passed=bool(success and errors is None and not failures and counts.get('ledger_authenticated')
        and not counts.get('unresolved'))
    body=dict(passed=passed,local_diagnostic_passed=passed,full_path_accuracy_passed=False,
        core_result_admitted=False,paper1_dataset_complete=False,qualified_core_cases=1,
        required_core_cases=12,successor_cases_dispatched=False,all_work_discarded_diagnostics=True,
        old_failed_records_admitted=False,old_closed_stage_resumed=False,states=states,error=errors,
        finalization_errors=failures,ledger=counts,prior_attempt_accounting=prior_attempt_accounting(),
        numerical_identities=identities,source_files=p['source_files'],physical_inputs=p['physical_inputs'],
        evidence_files=p['evidence_files'],historical_evidence_files=p['historical_evidence_files'],
        held_design_sha256=expected_design,observed_design_sha256=sha(PLAN) if PLAN.exists() else None,
        resources=resources,artifacts=artifact_inventory(),owner_and_supervisor_live_logs_intentionally_unsealed=True,
        separate_actual_supervisor_exit_and_closed_log_receipt_required=True,utc=utc())
    seal(OUT/'final_disposition_01',body)
    return passed


def owner():
    register_self(OUT/'owner/launch.json')
    p=authority(False,refresh_sources=True);expected=sha(PLAN)
    execution=None;states={key:{} for key in LEVELS};error=None;success=False
    try:
        execution=Execution()
        for key in LEVELS:qualified_local_level(execution,key,states[key])
        post_replay_all(execution,states)
        success=evaluate_local(execution,states)['passed']
    except BaseException as exc:
        error=dict(message=repr(exc),traceback=traceback.format_exc())
        print(traceback.format_exc(),flush=True)
    finally:
        passed=held_failure_disposition(p,expected,states,error,execution,success)
    if not passed:raise SystemExit(2)


def close_execution(manifest_path, expected_manifest_sha256):
    """Caller-held actual Popen receipt AFTER supervisor AND parent retirement.

    No process is launched or killed here. Manifest provenance is an explicit
    caller assertion pinned by SHA; no inferred wrapper return code is allowed.
    """
    n=private_administration()._namespace
    n['environment']()
    need(sha(manifest_path)==expected_manifest_sha256,'caller-pinned actual-exit manifest')
    m=read(manifest_path)
    p=read(PLAN);errors=[];identities=[];counts=final=supervisor=wrapper=owner_exit=None
    need(time.time()<min(instant(p['end_utc']),instant(ABSOLUTE_END)), 'external final receipt remains inside fixed approved end')
    def checked(stage,callback):
        try:return callback()
        except BaseException as exc:
            errors.append(dict(stage=stage,error=repr(exc)));return None
    checked('fresh_authority_all_source_input_historical_maps',lambda:n['authority'](False,refresh_sources=True))
    def manifest():
        need(m['actual_supervisor_exit_observed'] is True and type(m['actual_supervisor_returncode']) is int
             and m['actual_parent_terminal_exit_observed'] is True and type(m['actual_parent_terminal_returncode']) is int
             and isinstance(m['actual_exit_provenance'],dict) and m['actual_exit_provenance']
             and isinstance(m['actual_parent_terminal_handle_reference'],dict) and m['actual_parent_terminal_handle_reference']
             and m['design_sha256']==sha(PLAN), 'caller-observed actual Popen/terminal handles, never inferred own/wrapper exit')
    checked('caller_actual_exit_manifest',manifest)
    final=checked('sealed_original_final',lambda:n['sealed'](OUT/'final_disposition_01/results.json'))
    supervisor=checked('sealed_supervisor',lambda:n['sealed'](OUT/'supervisor/completion_01/results.json'))
    wrapper_path=OUT/'launcher/completion_01/results.json'
    wrapper=checked('sealed_wrapper_actual_Popen',lambda:n['sealed'](wrapper_path))
    owner_exit=checked('actual_owner_exit',lambda:read(OUT/'owner/exit.json'))
    def exits():
        need(wrapper is not None and supervisor is not None and final is not None and owner_exit is not None,
             'all four immutable owner/supervisor/wrapper/final receipts required')
        need(m['wrapper_completion_sha256']==sha(wrapper_path)
             and wrapper['supervisor_returncode_directly_observed'] is True
             and wrapper['actual_supervisor_returncode']==m['actual_supervisor_returncode']
             and owner_exit['actual_returncode_observed_from_original_popen_handle'] is True
             and owner_exit['retirement_verified'] is True
             and owner_exit['launch']==read(OUT/'owner/launch.json'), 'actual original Popen owner and supervisor associations')
        actual=read(OUT/'supervisor/launch.json')
        need(all(actual[k]==wrapper['supervisor_launch'][k] for k in ('pid','created','command'))
             and supervisor['held_design_sha256']==sha(PLAN)
             and supervisor['directly_observed_owner_exit_sha256']==sha(OUT/'owner/exit.json')
             and supervisor['directly_observed_owner_returncode']==owner_exit['returncode']
             and supervisor['final_disposition_sha256']==sha(OUT/'final_disposition_01/results.json')
             and final['held_design_sha256']==sha(PLAN)
             and m['actual_supervisor_returncode']==(0 if supervisor['passed'] else 2),
             'exact held design and final/owner/supervisor source-completion return associations')
        need(m['administrative_parent']==read(OUT/'launcher/launch.json'),
             'caller terminal handle belongs to exact registered administrative launch parent')
    checked('exit_and_final_associations',exits)
    def inventory():
        need(isinstance(m['closed_log_files'],dict) and m['closed_log_files'], 'nonempty mandatory closed logs')
        mandatory={str(OUT/name) for name in ('owner/stdout.log','owner/stderr.log',
                   'launcher/stdout.log','launcher/stderr.log')}
        for path in (OUT/'windows').glob('window_*/launch.json'):
            mandatory.update(str(path.parent/name) for name in ('stdout.log','stderr.log'))
            exit_doc=read(path.parent/'exit.json')
            need(exit_doc['actual_returncode_observed_from_original_popen_handle'] is True
                 and exit_doc['retirement_verified'] is True, 'every worker actual exit and mandatory closed-log inventory')
            n['verify_mapping'](exit_doc['logs'])
        need(mandatory<=set(m['closed_log_files']), 'owner, supervisor-held launcher and worker stdout/stderr cannot be omitted')
        n['verify_mapping'](m['closed_log_files'])
        n['verify_mapping'](wrapper['closed_logs']);n['verify_mapping'](owner_exit['logs'])
        need(set(wrapper['closed_logs'])=={str(OUT/'launcher/stdout.log'),str(OUT/'launcher/stderr.log')}
             and set(owner_exit['logs'])=={str(OUT/'owner/stdout.log'),str(OUT/'owner/stderr.log')},
             'source-observed closed logs exactly cover both administrative children')
        n['verify_mapping'](final['artifacts'])
        allowed={'owner/exit.json','owner/stdout.log','owner/stderr.log',
            'supervisor/completion_01/results.json','supervisor/completion_01/completion.json',
            'launcher/completion_01/results.json','launcher/completion_01/completion.json',
            'launcher/stdout.log','launcher/stderr.log',
            'final_disposition_01/results.json','final_disposition_01/completion.json'}
        extras=set(n['artifact_inventory'](exclude_live=False))-set(final['artifacts'])
        need(all(Path(path).relative_to(OUT).as_posix() in allowed for path in extras),
             'no raw/reservation/admission/clock work added after immutable final inventory')
    checked('mandatory_logs_and_immutable_final_inventory',inventory)
    counts=checked('strict_final_ledger',n['ledger'])
    checked('no_ledger_extension',lambda:need(counts is not None and final is not None and supervisor is not None
        and counts==final['ledger']==supervisor['ledger'], 'no changed work/admission ledger after final disposition'))
    try:
        identities=n['registered_identities']()+[
            dict(path=str(OUT/'owner/launch.json'),launch=read(OUT/'owner/launch.json')),
            dict(path=str(OUT/'supervisor/launch.json'),launch=read(OUT/'supervisor/launch.json')),
            dict(path=str(OUT/'launcher/launch.json'),launch=read(OUT/'launcher/launch.json'))]
    except BaseException as exc:errors.append(dict(stage='complete_actor_inventory',error=repr(exc)))
    observations=[]
    for row in identities:
        status=checked('fresh_exact_retirement_'+row['path'],lambda row=row:n['inspect_identity'](row['launch']))
        observations.append(dict(**row,inspection=status))
        checked('retirement_required_'+row['path'],lambda status=status:need(status is not None and status['retired'] is True,
            'birth mismatch or exact accessible fullcommand retirement; access denial remains unresolved'))
    checked('final_deadline',lambda:need(time.time()<min(instant(p['end_utc']),instant(ABSOLUTE_END)), 'fixed closure cutoff'))
    result=dict(passed=not errors,administrative_execution_closed=not errors,closure_errors=errors,
        local_diagnostic_passed=not errors and final is not None and final['passed'] is True
            and supervisor['passed'] is True and wrapper['actual_supervisor_returncode']==0
            and m['actual_parent_terminal_returncode']==0,
        actual_supervisor_returncode=m.get('actual_supervisor_returncode'),
        actual_parent_terminal_returncode=m.get('actual_parent_terminal_returncode'),
        manifest_sha256=expected_manifest_sha256,final_disposition_sha256=sha(OUT/'final_disposition_01/results.json') if final else None,
        supervisor_completion_sha256=sha(OUT/'supervisor/completion_01/results.json') if supervisor else None,ledger=counts,
        closed_log_files=m.get('closed_log_files',{}),identities=observations,
        full_path_accuracy_passed=False,core_result_admitted=False,old_negative_preserved=True,
        new_work_all_discarded_diagnostics=True,design_sha256=sha(PLAN),utc=utc())
    n['seal'](OUT/'final_execution_receipt_01',result)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('interfaces','authorize','launch','supervise','owner','worker','close'))
    parser.add_argument('arguments',nargs='*')
    args=parser.parse_args(argv)
    if args.mode=='interfaces':
        n=private_administration()._namespace
        print(json.dumps(n['source_interfaces'](),sort_keys=True));return
    if args.mode=='authorize':
        need(len(args.arguments)==3,'approval/preparation/originalclock exact SHAs required')
        print(json.dumps(authorize(*args.arguments),sort_keys=True));return
    if args.mode=='close':
        need(len(args.arguments)==2,'actualexit manifest path and exactcallerSHA')
        print(json.dumps(close_execution(*args.arguments),sort_keys=True));return
    if args.mode=='launch':
        need(not args.arguments,'one exact separately approved launch only')
        return launch()
    n=private_administration()._namespace
    n['authority'](args.mode=='worker',refresh_sources=True)
    if args.mode=='worker':
        need(args.arguments==['1'],'only one bounded persistent worker')
        n['worker'](1)
    else:
        need(not args.arguments,'no unreviewed command arguments')
        n[args.mode]()


if __name__=='__main__':
    raise SystemExit(main())
