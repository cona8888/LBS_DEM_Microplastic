"""Inactive four-saved-input outer-solve falsifier; no transport advancement.

Import and controls use stdlib only.  Native imports occur only in an exactly
approved worker.  The ROOT caller must own the controller Popen and provide
its observed exit/log manifest to the external ``close`` command after exit.
No command manufactures a clock, human approval, or publication admission.
"""
from __future__ import annotations

import argparse
import ast
import copy
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import lzma
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
from types import SimpleNamespace, FunctionType
import uuid

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
STAGING = ROOT / 'paper1_staging'
FAMILY = ROOT / 'paper1_designs/momentum_repair_20261020'
OUT = ROOT / 'paper1_runs/momentum_repair_20261020'
PROPOSAL = FAMILY / 'proposal_01.json'
PREPARED = FAMILY / 'preparation_01/results.json'
APPROVAL = FAMILY / 'human_approval_01/results.json'
CLOCK = FAMILY / 'window_clock_01/results.json'
PLAN = FAMILY / 'design_01.json'
AUTH = FAMILY / 'authorization_01.json'
FIXTURES = FAMILY / 'fixtures_01.json'
CONTROL_LOG_DIR = FAMILY / 'execution_logs_01'
CONTROL_LOGS = (CONTROL_LOG_DIR/'controller_stdout.log', CONTROL_LOG_DIR/'controller_stderr.log')
PHYSICAL = ROOT / 'paper1_designs/contact_event_diagnostic_20261019/runtime_config_01.json'
RUNTIME = STAGING / 'full_state_integration_adapter_v5.py'
RUNTIME_SHA = '1a9ff2828b0c313e7a90a99d8440387a79553114c65e648877f40f8c7a7ac7c2'
HELPER = STAGING / 'cancellation_safe_velocity_v1.py'
ARITHMETIC = STAGING / 'diagnose_saved_momentum_v1.py'
ARITHMETIC_SHA = 'd58efdccd29a21601199a5e3c9a3119d002cf15cd9a96bb7597c77a55938dea0'
OUTER_CLOCK = ROOT / 'paper1_designs/full_horizon_repair_20261018/qualification_clock_01/results.json'
OUTER_CLOCK_SHA = 'a2f1cffc1ca0ad235125487f316c6b124eac8b1df3f72bb191b8748ae8a22737'
ADMIN = STAGING / 'run_stepdoubling_qualification_v4.py'
ADMIN_SHA = '05447c49e219dfff6849f6b2c543037b894feaafa71be184db5f44133e69cf69'
PYTHON = Path('C:/Users/wonjuncha-admin/AppData/Local/Programs/Python/Python312/python.exe')
ABSOLUTE_END = '2026-10-24T07:43:33.769535+00:00'
ABSOLUTE_NUMERICAL_END = '2026-10-23T23:43:33.769535+00:00'
RAW = ROOT / 'paper1_runs/contact_event_diagnostic_20261019_recovery02/records/f0p0625_local_001/packet.json.xz'
RAW_SHA = '00d8eb70116e5a1ed8c58ff63b8241de312d9b211d78868dd019cc7dca11afc3'
MAX_WORK, MAX_RECORDS, MAX_NONADVANCING = 260, 5, 12
NATIVE_S, MAX_SECONDS, NUMERICAL_SECONDS, FINAL_SECONDS = 45., 4500., 900., 3600.
NEW_BYTES, JOINT_BYTES, OWN_BYTES = 16*1024**2, 512*1024**2, 12*1024**3
RETENTION_BYTES, FREE_BYTES = 21*1024**3, 20*1024**3
RESERVE_BYTES = 2*1024**2
PRIOR = dict(all_work_rows=757577, integration_records=202,
             synthetic_nonadvancing_kernel_invocations=10, numerical_windows=5,
             standalone_work_rows=16148, standalone_records=53,
             unknown_reserved_work_upper_bound=4838, known_unaccepted_work_rows=3371)
BASELINE = dict(case_work_rows=11070355, case_records=2376,
                shared_work_rows=5422443, shared_records=1206,
                diagnostic_work_rows=162229, diagnostic_records=119)
OLD_DIAGNOSTICS = tuple(ROOT / ('paper1_runs/' + x) for x in (
    'contact_event_diagnostic_20261019', 'contact_event_diagnostic_20261019_recovery02'))
OLD_QUALIFICATIONS = tuple(ROOT / ('paper1_runs/' + x) for x in (
    'full_horizon_repair_20261018', 'full_horizon_repair_20261018_recovery02',
    'full_horizon_repair_20261018_recovery03', 'full_horizon_repair_20261018_recovery04'))
OPERATIONS = (('setup', None, False), ('F1_original', 'F1', False),
              ('F1_guarded', 'F1', True), ('F1_guarded_repeat', 'F1', True),
              ('C_guarded', 'C', True))
_ADMIN = None


def need(value, message):
    if not value:
        raise RuntimeError('Saved momentum probe: ' + message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=True).encode()).hexdigest()


def commit(path, value):
    """Literal create-only atomic publication protocol; no parser retry."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, sort_keys=True, indent=2, allow_nan=True) + '\n').encode()
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.publishing')
    with temporary.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.link(temporary, path)
    need(os.path.samefile(temporary, path) and path.read_bytes() == data,
         'only complete owned sibling bytes may be published')
    temporary.unlink()
    return sha(path)


def seal(folder, value):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    commit(folder / 'results.json', value)
    commit(folder / 'completion.json', dict(passed=value.get('passed') is True,
        results_sha256=sha(folder / 'results.json'), utc=utc()))
    return value


def sealed(path, *, positive=False):
    value = read(path)
    completion = read(Path(path).with_name('completion.json'))
    need(completion['results_sha256'] == sha(path)
         and completion['passed'] is (value.get('passed') is True), 'complete immutable seal')
    need(not positive or value.get('passed') is True, 'positive prerequisite')
    return value


def verify_mapping(mapping):
    need(isinstance(mapping, dict), 'explicit immutable mapping')
    for path, expected in mapping.items():
        need(isinstance(expected, str) and len(expected) == 64 and sha(path) == expected,
             'frozen bytes ' + str(path))


def merge_maps(*mappings):
    result = {}
    for mapping in mappings:
        for path, expected in mapping.items():
            need(path not in result or result[path] == expected, 'nonconflicting immutable map')
            result[path] = expected
    return result


def load_file(path, name, expected=None):
    if expected is not None:
        need(sha(path) == expected, 'source before import ' + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    if expected is not None:
        need(sha(path) == expected, 'source after import ' + str(path))
    return module


def administration():
    global _ADMIN
    if _ADMIN is None:
        _ADMIN = load_file(ADMIN, '_saved_momentum_identity_only', ADMIN_SHA)
    return _ADMIN


def environment():
    need(Path(sys.executable).resolve() == PYTHON.resolve(), 'qualified Python')
    need(all(os.environ.get(k) == '1' for k in
             ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS')), 'one numerical thread')


def instant(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    need(parsed.tzinfo is not None and parsed.utcoffset() is not None, 'aware fixed UTC bounds')
    return parsed.timestamp()


def validate_clock(value, *, now=None, numerical=True):
    start, cutoff, end = [instant(value[k]) for k in ('start_utc', 'simulation_cutoff_utc', 'end_utc')]
    need(value.get('passed') is True and value.get('original_shared_end_utc') == ABSOLUTE_END,
         'positive subwindow under original absolute authority')
    need(0 < cutoff-start <= NUMERICAL_SECONDS and end-start <= MAX_SECONDS
         and end-cutoff >= FINAL_SECONDS and end <= instant(ABSOLUTE_END)
         and cutoff <= instant(ABSOLUTE_NUMERICAL_END), '15min native plus60min final maximum75min')
    now = time.time() if now is None else now
    need(start <= now < (cutoff if numerical else end), 'fixed unexpired clock; no renewal')
    return start, cutoff, end


def approval_scope():
    return dict(saved_input_momentum_probe_only=True, outer_calls=4,
        maximum_new_all_work_rows=MAX_WORK, maximum_new_integration_records=MAX_RECORDS,
        maximum_nonadvancing_units=MAX_NONADVANCING, maximum_numerical_windows=1,
        maximum_window_seconds=MAX_SECONDS, maximum_numerical_seconds=NUMERICAL_SECONDS,
        minimum_final_seconds=FINAL_SECONDS, maximum_native_seconds_per_record=NATIVE_S,
        setup_reservation_work_rows=256, outer_call_work_rows=1,
        nonadvancing_units_definition='two synthetic hot.phase warms; every prepared inner map including reuse; extra nested hot.phase beyond one per map',
        new_output_bytes=NEW_BYTES, joint_diagnostic_output_bytes=JOINT_BYTES,
        combined_all_attempt_output_bytes=OWN_BYTES, total_retention_bytes=RETENTION_BYTES,
        minimum_free_bytes=FREE_BYTES, workers=1, threads=1, logical_cpu=14,
        maximum_unverified_records=1, original_shared_end_utc=ABSOLUTE_END,
        all_work_discarded=True, original_momentum_threshold=1e-8,
        original_physics_contact_routes_and_accuracy_gates_unchanged=True,
        no_transport_advancement=True, no_FULL_restart_qualification=True,
        no_trajectory_or_full_horizon_qualification=True, qualified_core_cases_increment=0,
        required_external_controller_logs=[str(p) for p in CONTROL_LOGS])


def budget_guard(work, records, nonadvancing):
    need(all(type(v) is int and v >= 0 for v in (work, records, nonadvancing)), 'integer work accounting')
    need(work <= MAX_WORK and records <= MAX_RECORDS and nonadvancing <= MAX_NONADVANCING,
         'probe all-work/record/nonadvancing caps')
    need(PRIOR['all_work_rows']+work <= 18000000 and PRIOR['integration_records']+records <= 4000,
         'original shared all-attempt allocation')
    need(PRIOR['standalone_work_rows']+work <= 200000
         and PRIOR['standalone_records']+records <= 150,
         'original standalone allocation includes prior work')
    need(PRIOR['synthetic_nonadvancing_kernel_invocations']+nonadvancing <= 22
         and PRIOR['numerical_windows']+1 <= 11, 'no warm/window reset')
    need(BASELINE['case_work_rows']+work <= 28312778 and BASELINE['case_records']+records <= 6174
         and BASELINE['shared_work_rows']+work <= 22664866
         and BASELINE['shared_records']+records <= 5004, 'unchanged cumulative case/shared ceilings')


def tree_bytes(folder):
    return sum(p.stat().st_size for p in Path(folder).rglob('*') if p.is_file()) if Path(folder).exists() else 0


def resource_guard(reserve=RESERVE_BYTES):
    need(type(reserve) is int and reserve >= 0, 'bounded output reservation')
    new = tree_bytes(OUT) + tree_bytes(CONTROL_LOG_DIR)
    diagnostic = new + sum(tree_bytes(p) for p in OLD_DIAGNOSTICS)
    own = diagnostic + sum(tree_bytes(p) for p in OLD_QUALIFICATIONS)
    total = sum(tree_bytes(ROOT/p) for p in ('paper1_designs', 'paper1_runs', 'paper1_evaluations'))
    free = shutil.disk_usage(ROOT).free
    need(new+reserve <= NEW_BYTES and diagnostic+reserve <= JOINT_BYTES
         and own+reserve <= OWN_BYTES and total+reserve <= RETENTION_BYTES
         and free >= FREE_BYTES+reserve, 'joint new/old retained and free disk ceilings')
    return dict(new_bytes=new, joint_diagnostic_bytes=diagnostic, all_attempt_bytes=own,
                total_retained_bytes=total, free_bytes=free, reserve_bytes=reserve)


def source_interfaces():
    need(sha(ADMIN) == ADMIN_SHA and sha(RUNTIME) == RUNTIME_SHA
         and sha(ARITHMETIC) == ARITHMETIC_SHA, 'literal original administration/runtime/arithmetic')
    helper_tree = ast.parse(HELPER.read_text(encoding='utf-8'))
    names = {n.name for n in helper_tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    need({'scope', 'audit_journal'} <= names, 'actual guarded helper and independent audit interfaces')
    return {str(path): sha(path) for path in (SELF, ADMIN, RUNTIME, HELPER, ARITHMETIC)}


def fixture_geometry_context(item):
    call = item['reference_prepare_call']
    need(call['contacts'] == item['outer_inputs'][6] and call['ell_m'] == item['outer_inputs'][7]
         and call['metadata'] == item['normal_gap_prepare_metadata'] and call['metadata'],
         'literal saved normal-gap prepare input and complete metadata')
    contexts = [m['context'] for m in call['metadata']]
    context = contexts[0]
    keys = ('x', 'p', 'a', 'b', 'original_skin_m')
    need(all(all(c[k] == context[k] for k in keys) for c in contexts)
         and context['a'] == item['outer_inputs'][7], 'one exact original geometry query context')
    return context


def verify_fixtures(value):
    need(value.get('schema') == 'paper1.saved-momentum-probe-fixtures.v1', 'declared fixed input fixture schema')
    need(value['raw_source_path'] == str(RAW) and value['raw_source_sha256'] == RAW_SHA == sha(RAW),
         'literal closed failed raw; no replacement')
    f, c = value['F1'], value['C']
    need(f['branch_id'] == 'm000000547_t000000000_F1'
         and c['branch_id'] == 'm000000547_t000000000_C', 'fixed retained neighboring systems')
    need(f['expected_legacy_error'] == 'inertial momentum closure failed', 'specific expected original negative')
    need(len(f['outer_inputs']) == len(c['outer_inputs']) == 14
         and all(f['outer_inputs'][i] == c['outer_inputs'][i] for i in range(14) if i != 8)
         and 0 < f['outer_inputs'][8] < c['outer_inputs'][8]
         and c.get('derivation_same_origin_fields_verified') is True,
         'same literal saved origin; only requested duration differs')
    for item in (f, c):
        need(type(item.get('before_runtime_recovery_mode')) is bool, 'saved outer runtime recovery state')
        context = fixture_geometry_context(item)
        need(all(k in context for k in ('x', 'p', 'a', 'b', 'original_skin_m'))
             and context['a'] == item['outer_inputs'][7], 'literal saved normal-gap geometry context')
        records = item['reference_inner_maps']
        need(records and [r['inner_index'] for r in records] == list(range(len(records))),
             'complete ordered original inner maps')
        need(all(isinstance(r['input_sha256'], str) and len(r['input_sha256']) == 64 for r in records),
             'exact original Stage242 argument identities')
    need(c['exact_inner_input_digests'] == [r['input_sha256'] for r in c['reference_inner_maps']],
         'explicit independently reconstructed C identities')
    return True


def immutable_maps(value, *, historical=False):
    keys = ('source_files', 'physical_inputs', 'evidence_files') + (('historical_evidence_files',) if historical else ())
    return merge_maps(*(value[k] for k in keys))


def verify_preparation(prepared, proposal):
    need(prepared.get('passed') is True and prepared.get('dispatch_authorized') is False
         and prepared.get('all_required_interfaces_present') is True, 'source-only reviewed readiness')
    need(prepared['baseline'] == proposal['baseline'] == BASELINE
         and proposal['required_human_approval_scope'] == approval_scope(), 'actual baseline and exact new scope')
    need(Path(proposal['fixtures_file']) == FIXTURES and proposal['fixtures_sha256'] == sha(FIXTURES),
         'frozen prepared fixture identity')
    need(proposal['original_outer_clock_sha256'] == prepared['original_outer_clock_sha256']
         == OUTER_CLOCK_SHA == sha(OUTER_CLOCK), 'same frozen original outer authority')
    outer = sealed(OUTER_CLOCK, positive=True)
    need(outer['end_utc'] == ABSOLUTE_END and outer['simulation_cutoff_utc'] == ABSOLUTE_NUMERICAL_END,
         'literal original outer cutoffs')
    expected = source_interfaces()
    need(all(prepared['source_files'].get(k) == v for k, v in expected.items()), 'actual source interfaces frozen')
    verify_mapping(merge_maps(immutable_maps(prepared, historical=True), immutable_maps(proposal, historical=True)))
    verify_fixtures(read(FIXTURES))
    snapshots = []
    for launch in prepared['prior_exact_process_identities']:
        observed = administration().inspect_identity(launch)
        need(observed['retired'] is True, 'old exact birth/full-command identity retired')
        snapshots.append(dict(launch=launch, inspection=observed))
    return snapshots


def authorize(approval_sha256, preparation_sha256, clock_sha256):
    environment()
    need(not AUTH.exists() and not PLAN.exists() and not OUT.exists() and not CONTROL_LOG_DIR.exists(),
         'no reused authority/output/log/partial run')
    need(sha(APPROVAL) == approval_sha256 and sha(PREPARED) == preparation_sha256
         and sha(CLOCK) == clock_sha256, 'caller-pinned actual human/preparation/fixed clock')
    approval, prepared, clock = sealed(APPROVAL, positive=True), sealed(PREPARED, positive=True), sealed(CLOCK, positive=True)
    proposal = read(PROPOSAL)
    need(approval.get('human_origin') is True and approval.get('human_reply') and approval.get('question_reference')
         and approval['proposal_sha256'] == sha(PROPOSAL)
         and approval['scope'] == approval_scope(), 'new explicit human approved exact proposal/scope')
    need(clock['proposal_sha256'] == sha(PROPOSAL) and clock['approval_sha256'] == approval_sha256
         and clock['original_outer_clock_sha256'] == OUTER_CLOCK_SHA,
         'subwindow belongs to this actual human approval/proposal/original outer clock')
    validate_clock(clock)
    retired = verify_preparation(prepared, proposal)
    resource_guard()
    budget_guard(0, 0, 0)
    authorization = dict(passed=True, utc=utc(), proposal_sha256=sha(PROPOSAL),
        approval_sha256=approval_sha256, preparation_sha256=preparation_sha256,
        clock_sha256=clock_sha256, scope=approval_scope(), baseline=BASELINE,
        sources=source_interfaces(), old_identities=retired, no_dispatch_performed=True)
    need(all(prepared['source_files'].get(k) == v for k, v in authorization['sources'].items()),
         'same approved sources still current at authorization boundary')
    need(sha(APPROVAL) == approval_sha256 and sha(PREPARED) == preparation_sha256
         and sha(CLOCK) == clock_sha256, 'caller pins unchanged after complete preparation read')
    validate_clock(clock, numerical=True)
    commit(AUTH, authorization)
    plan = dict(schema='paper1.saved-momentum-probe.plan.v1', utc=utc(),
        authorization_sha256=sha(AUTH), proposal_sha256=sha(PROPOSAL),
        approval_sha256=approval_sha256, preparation_sha256=preparation_sha256,
        clock_sha256=clock_sha256, physical_sha256=sha(PHYSICAL), fixtures_sha256=sha(FIXTURES),
        scope=approval_scope(), baseline=BASELINE, prior=PRIOR,
        source_files=prepared['source_files'], physical_inputs=prepared['physical_inputs'],
        evidence_files=prepared['evidence_files'], historical_evidence_files=prepared['historical_evidence_files'],
        start_utc=clock['start_utc'], simulation_cutoff_utc=clock['simulation_cutoff_utc'], end_utc=clock['end_utc'])
    plan['binding'] = digest(plan)
    validate_clock(clock, numerical=True)
    commit(PLAN, plan)
    return dict(authorization_sha256=sha(AUTH), plan_sha256=sha(PLAN), no_dispatch_performed=True)


def authority(*, numerical=False, historical=False, allow_closed=False, refresh_sources=True):
    environment()
    plan = read(PLAN)
    need(plan['binding'] == digest({k:v for k,v in plan.items() if k != 'binding'}), 'immutable PLAN binding')
    for key, path in (('authorization_sha256', AUTH), ('proposal_sha256', PROPOSAL),
                      ('approval_sha256', APPROVAL), ('preparation_sha256', PREPARED),
                      ('clock_sha256', CLOCK), ('physical_sha256', PHYSICAL), ('fixtures_sha256', FIXTURES)):
        need(plan[key] == sha(path), 'authority association ' + key)
    need(plan['scope'] == approval_scope() and plan['baseline'] == BASELINE and plan['prior'] == PRIOR,
         'frozen same budget and numerical contract')
    approval, clock = sealed(APPROVAL, positive=True), sealed(CLOCK, positive=True)
    prepared = sealed(PREPARED, positive=True)
    need(approval['human_origin'] is True and approval['proposal_sha256'] == plan['proposal_sha256']
         and approval['scope'] == approval_scope()
         and clock['proposal_sha256'] == plan['proposal_sha256']
         and clock['approval_sha256'] == sha(APPROVAL)
         and clock['original_outer_clock_sha256'] == OUTER_CLOCK_SHA
         and prepared['baseline'] == BASELINE, 'fresh complete approval/preparation/clock associations')
    need(sha(OUTER_CLOCK) == OUTER_CLOCK_SHA, 'original clock never reset')
    if not allow_closed:
        validate_clock(read(CLOCK), numerical=numerical)
    if refresh_sources:
        verify_mapping(immutable_maps(plan, historical=historical))
    need(plan['source_files'][str(SELF)] == sha(SELF), 'self source pin')
    if not allow_closed:
        validate_clock(read(CLOCK), numerical=numerical)
    return plan


def launch_identity(role, process=None):
    import psutil
    process = psutil.Process() if process is None else psutil.Process(process.pid)
    return dict(role=role, pid=process.pid, created=process.create_time(),
                command=process.cmdline(), plan_sha256=sha(PLAN), utc=utc())


def same_actor(first, second):
    return all(first[k] == second[k] for k in ('pid', 'created', 'command', 'plan_sha256'))


def ledger():
    reservations = sorted((OUT/'reservations').glob('*.json')) if (OUT/'reservations').exists() else []
    work = accepted = known = unknown = units = 0
    entries = []
    for path in reservations:
        reservation = read(path)
        need(reservation['plan_sha256'] == sha(PLAN), 'reservation PLAN')
        folder = OUT/'admissions'/path.stem
        if (folder/'results.json').exists() and (folder/'completion.json').exists():
            row = sealed(folder/'results.json')
            need(row['reservation_sha256'] == sha(path), 'admission-reservation association')
            verify_mapping(row['artifacts'])
            charge = row['actual_work_rows']
            need(type(charge) is int and 0 <= charge <= reservation['work_cap'], 'literal known work count')
            unit_charge = row['nonadvancing_units']
            need(type(unit_charge) is int and 0 <= unit_charge <= reservation['nonadvancing_cap'], 'known operation count')
            physical = row.get('physical_work_accepted') is True
            accepted += charge if physical else 0
            known += charge if not physical else 0
        else:
            charge, unit_charge = reservation['work_cap'], reservation['nonadvancing_cap']
            unknown += charge
        work += charge
        units += unit_charge
        entries.append(dict(path=str(path), sha256=sha(path), charged_work_rows=charge,
                            charged_nonadvancing_units=unit_charge))
    budget_guard(work, len(reservations), units)
    return dict(all_work_rows=work, integration_records=len(reservations),
        accepted_discarded_work_rows=accepted, known_unaccepted_work_rows=known,
        unknown_reserved_work_upper_bound=unknown, nonadvancing_units=units,
        entries=entries, all_work_discarded=True, qualified_core_cases_increment=0)


def write_blob(path, value):
    data = json.dumps(value, sort_keys=True, allow_nan=True).encode()
    need(len(data) <= NEW_BYTES-RESERVE_BYTES, 'bounded literal complete probe evidence')
    with Path(path).open('xb') as stream:
        stream.write(lzma.compress(data, preset=6))
        stream.flush()
        os.fsync(stream.fileno())
    return sha(path)


def read_blob(path, expected):
    need(sha(path) == expected, 'lossless raw compressed hash')
    with lzma.open(path, 'rb') as stream:
        data = stream.read(NEW_BYTES+1)
    need(len(data) <= NEW_BYTES, 'bounded raw decompression')
    return json.loads(data)


class NonadvancingCounter:
    """Prepared maps include reuse; nested kernels beyond one/map add units."""
    def __init__(self, prior, gate=None):
        self.units = prior
        self.map_open = False
        self.map_kernels = 0
        self.prepared_maps = 0
        self.actual_hot_phase_calls = 0
        self.extra_hot_phase_units = 0
        self.events = []
        self.gate = gate

    def charge(self):
        need(self.units < MAX_NONADVANCING, 'nonadvancing budget exhausted BEFORE another operation')
        self.units += 1

    def before_inner(self, item):
        if self.gate is not None:
            self.gate()
        need(not self.map_open, 'sequential nonnested prepared map')
        self.charge()
        self.prepared_maps += 1
        self.map_open, self.map_kernels = True, 0
        self.events.append(dict(kind='prepared_inner_map', outer_index=item['outer_index'],
            inner_index=item['inner_index'], charged_unit=self.units))

    def after_inner(self, item):
        # A budget refusal before observer entry must not be replaced by a
        # cleanup exception. Such an incomplete map never passes the auditor.
        if not self.map_open:
            need(not item.get('observer_entered'), 'matching prepared map completion')
            return
        self.map_open = False

    def phase(self, original, *args, **kwargs):
        if self.gate is not None:
            self.gate()
        if not self.map_open or self.map_kernels >= 1:
            self.charge()
            self.extra_hot_phase_units += 1
            self.events.append(dict(kind='extra_hot_phase', charged_unit=self.units))
        self.actual_hot_phase_calls += 1
        if self.map_open:
            self.map_kernels += 1
        return original(*args, **kwargs)

    def snapshot(self):
        return dict(nonadvancing_units=self.units, prepared_inner_maps=self.prepared_maps,
                    actual_hot_phase_calls=self.actual_hot_phase_calls,
                    extra_nested_kernel_units=self.extra_hot_phase_units, unit_events=copy.deepcopy(self.events))


@contextmanager
def counted_phase_aliases(hot, counter):
    """Count actual compiled PGS aliases AND module-global SOR phase calls.

    Stage136.PRIMARY captured ``compiled_phase`` in a separate globals dict;
    replacing hot.phase alone misses it. The active Stage236 arity wrappers
    can have a second copied namespace. Traverse only their declared original
    and two-contact function pointers, require the same literal phase, dedupe
    namespaces, and restore every binding before the outer kernel exits.
    """
    original = hot.phase
    queue = [hot.PRIMARY, hot.s50._solve]
    seen_functions, namespaces = set(), {}
    while queue:
        fn = queue.pop()
        if not isinstance(fn, FunctionType) or id(fn) in seen_functions:
            continue
        seen_functions.add(id(fn))
        namespace = fn.__globals__
        if 'compiled_phase' in namespace:
            need(namespace['compiled_phase'] is original, 'original literal compiled phase alias')
            namespaces[id(namespace)] = namespace
        for key in ('_original_solver', '_two_contact_solver'):
            if isinstance(namespace.get(key), FunctionType):
                queue.append(namespace[key])
    need(namespaces, 'actual native PRIMARY compiled_phase alias must be observed')
    def phase(*args, **kwargs):
        return counter.phase(original, *args, **kwargs)
    hot.phase = phase
    for namespace in namespaces.values():
        namespace['compiled_phase'] = phase
    try:
        yield dict(distinct_compiled_phase_namespaces=len(namespaces), module_phase_counted=True)
    finally:
        exact = hot.phase is phase and all(ns['compiled_phase'] is phase for ns in namespaces.values())
        hot.phase = original
        for namespace in namespaces.values():
            namespace['compiled_phase'] = original
        need(exact, 'all original phase aliases restored exactly before kernel exit')


def native_probe(engine, helper, fixture, enabled, gate, *, prior_units):
    """One exact frozen pose, one outer call; no integrator/advance invocation."""
    import numpy as np
    physical = read(PHYSICAL)
    case = next(c for c in physical['cases'] if c['level_id'] == 'f0p0625')
    result = dict(outer_call_attempted=False, enabled=enabled, input_sha256=digest(fixture['outer_inputs']))
    counter = NonadvancingCounter(prior_units, gate)
    try:
        with engine.native_execution_scope(case['spec'], case['binding'], gate,
                plan_path=PLAN, auth_path=AUTH, physical_path=PHYSICAL) as env:
            need(env['native_setup_force_calls'] == 0, 'native scope adds no hidden setup force call')
            runtime = env['runtime']
            q = runtime.capture.q
            configure = q.reference.JOB.parent.b.old.parent.configure
            hot = configure.__globals__['hot']
            # Frozen origin assertions must see the original phase binding.
            # Counting starts only AFTER the original observer/kernel enters,
            # and restores BEFORE that observer/kernel exits.
            with runtime.capture.packet_scope():
                backend = q.job.observer.backend
                original_recovery = backend.recovery_mode()
                need(type(fixture['before_runtime_recovery_mode']) is bool, 'literal saved recovery Boolean')
                backend.set_recovery_mode(fixture['before_runtime_recovery_mode'])
                result.update(saved_recovery_mode=fixture['before_runtime_recovery_mode'],
                              prior_recovery_mode=original_recovery)
                try:
                    # Stage213 binds each prepared normal by OBJECT identity
                    # to an original geometry query inside this exact scope.
                    # Rehydrate identity, never alter a single saved operand.
                    context = fixture_geometry_context(fixture)
                    queried = env['geometry'].contacts(np.asarray(context['x'], float),
                        np.asarray(context['p'], float), context['a'], context['b'], context['original_skin_m'])
                    need(digest(engine.plain(queried)) == digest(fixture['outer_inputs'][6]),
                         'ENTIRE original live contact membership equals frozen input; no subset filtering')
                    with counted_phase_aliases(hot, counter) as alias_proof:
                        result['counter_alias_proof'] = alias_proof
                        with runtime.capture.scope('saved_outer_probe', None) as evidence:
                            with helper.scope(q.job.observer.backend.stage42, runtime.capture.trace,
                                    enabled=enabled, before_inner=counter.before_inner,
                                    after_inner=counter.after_inner) as journal:
                                result['outer_call_attempted'] = True
                                try:
                                    args = copy.deepcopy(fixture['outer_inputs'])
                                    args[:6] = [np.asarray(v, float) for v in args[:6]]
                                    args[6] = queried
                                    need(digest(engine.plain(args)) == digest(fixture['outer_inputs']),
                                         'rehydrated original contact identities preserve ALL14 operand values')
                                    velocity, health = q.job.observer.backend.inertial_contact_step(*args)
                                    result.update(returned=True, velocity=engine.plain(velocity), health=engine.plain(health))
                                except Exception as error:
                                    result.update(returned=False, error=repr(error), error_type=type(error).__name__)
                            result['journal'] = engine.plain(journal)
                        result['evidence'] = engine.plain(evidence)
                finally:
                    backend.set_recovery_mode(original_recovery)
                    result['recovery_mode_restored'] = backend.recovery_mode() == original_recovery
                    need(result['recovery_mode_restored'], 'exact recovery binding restored')
    except Exception as error:
        result.update(scope_error=repr(error), scope_traceback=traceback.format_exc())
    result.update(counter.snapshot())
    return result


def worker():
    authority(numerical=True)
    import psutil
    psutil.Process().cpu_affinity([14])
    need(psutil.Process().cpu_affinity() == [14], 'worker logical CPU14')
    commit(OUT/'worker'/'launch.json', launch_identity('worker'))
    engine = load_file(RUNTIME, 'full_state_integration_adapter_v5', RUNTIME_SHA)
    helper = load_file(HELPER, '_saved_momentum_safe_helper', read(PLAN)['source_files'][str(HELPER)])
    units, prelude = 0, False
    try:
        for number, (label, fixture_key, enabled) in enumerate(OPERATIONS, 1):
            request_path = OUT/'requests'/f'{number:03d}.json'
            while not request_path.exists():
                authority(numerical=True, refresh_sources=False)
                if (OUT/'controller'/'stop.json').exists():
                    return
                time.sleep(.05)
            request = read(request_path)
            authority(numerical=True)
            reservation = OUT/'reservations'/f'{number:03d}.json'
            need(request['reservation_sha256'] == sha(reservation)
                 and request['plan_sha256'] == sha(PLAN) and request['operation'] == label,
                 'sequential request/reservation/operation')
            markers = OUT/'markers'/f'{number:03d}'
            commit(markers/'native_start.json', dict(request_sha256=sha(request_path), utc=utc(),
                time=time.time(), worker_launch_sha256=sha(OUT/'worker'/'launch.json')))
            started = time.monotonic()
            def gate():
                plan = authority(numerical=True)
                return dict(native_dispatch_authorized=True, native_prelude_authorized=not prelude,
                    native_stack_prelude_authenticated=prelude, native_smoke_authorized=False,
                    simulation_cutoff_utc=plan['simulation_cutoff_utc'])
            try:
                if number == 1:
                    need(not prelude and units+2 <= MAX_NONADVANCING, 'one bounded synthetic prelude')
                    value = engine.native_stack_prelude(gate)
                    need(value['nonadvancing_contact_kernel_invocations'] == 2
                         and value['target_outer_transport_calls'] == 0, 'actual two warm/no target outer')
                    units, prelude = 2, True
                    payload = dict(kind='setup', telemetry=value, actual_work_rows=0,
                                   nonadvancing_units=2, prior_nonadvancing_units=0, passed_execution=True)
                else:
                    need(prelude, 'registered explicit prelude before native probe')
                    fixtures = read(FIXTURES)
                    verify_fixtures(fixtures)
                    payload = native_probe(engine, helper, fixtures[fixture_key], enabled, gate, prior_units=units)
                    previous_units, units = units, payload['nonadvancing_units']
                    payload.update(kind='outer', operation=label,
                        actual_work_rows=1 if payload['outer_call_attempted'] else 0,
                        prior_nonadvancing_units=previous_units)
                elapsed = time.monotonic()-started
                raw_path = OUT/'raw'/f'{number:03d}.json.xz'
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_sha = write_blob(raw_path, payload)
                commit(markers/'native_finish.json', dict(request_sha256=sha(request_path), utc=utc(), elapsed_s=elapsed,
                    raw_sha256=raw_sha, nonadvancing_units=units))
                commit(OUT/'responses'/f'{number:03d}.json', dict(request_sha256=sha(request_path),
                    reservation_sha256=sha(reservation), raw_path=str(raw_path), raw_sha256=raw_sha,
                    elapsed_s=elapsed, utc=utc()))
            except Exception as error:
                commit(markers/'failure.json', dict(error=repr(error), traceback=traceback.format_exc(),
                    request_sha256=sha(request_path), utc=utc(), known_nonadvancing_units_lower_bound=units))
                raise
    finally:
        commit(OUT/'worker'/'exit.json', dict(utc=utc(), known_nonadvancing_units_lower_bound=units,
            own_returncode_not_observed=True, no_transport_advancement=True))


def original_cycle_audit(trace, np, physical):
    """Execute the pinned ORIGINAL audit function, without importing its engine.

    This four-call one-contact protocol refuses canonical/early/fallback
    branches before this call. The original exact bits helper and original
    NAME constant are extracted from their pinned sources; no predicate is
    replaced by a producer Boolean or a tolerance.
    """
    plan = read(PLAN)
    audit_path = ROOT/'stage243_staging/per_pose_guard_v1.py'
    bits_path = ROOT/'stage239_staging/fixed_point_replay_v1.py'
    name_path = ROOT/'stage242_staging/contact_consistency_v1.py'
    for path in (audit_path, bits_path, name_path):
        need(plan['source_files'][str(path)] == sha(path), 'original cycle source pin')
    bits_node = next(n for n in ast.parse(bits_path.read_text(encoding='utf-8')).body
                     if isinstance(n, ast.FunctionDef) and n.name == 'bits')
    ns = dict(np=np)
    exec(compile(ast.Module(body=[bits_node], type_ignores=[]), str(bits_path), 'exec'), ns)
    name = next(ast.literal_eval(n.value) for n in ast.parse(name_path.read_text(encoding='utf-8')).body
                if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'NAME' for t in n.targets))
    prior = SimpleNamespace(bits=ns['bits'], physical=SimpleNamespace(physical=physical))
    ns.update(prior=prior, core=SimpleNamespace(NAME=name), require=need)
    audit_node = next(n for n in ast.parse(audit_path.read_text(encoding='utf-8')).body
                      if isinstance(n, ast.FunctionDef) and n.name == 'audit')
    exec(compile(ast.Module(body=[audit_node], type_ignores=[]), str(audit_path), 'exec'), ns)
    return ns['audit'](dict(contact_trial_trace=trace))


def independent_audit(payload, label, fixture, *, previous=None):
    """No engine import/force calls. Exact independent helper + original stencil."""
    if label == 'setup':
        need(payload['actual_work_rows'] == 0 and payload['nonadvancing_units'] == 2
             and payload['telemetry']['target_outer_transport_calls'] == 0, 'authenticated explicit warm only')
        return dict(passed=True, expected_negative=False, setup=True)
    need('scope_error' not in payload and payload['outer_call_attempted'] is True
         and payload['input_sha256'] == digest(fixture['outer_inputs'])
         and payload['saved_recovery_mode'] == fixture['before_runtime_recovery_mode']
         and payload['recovery_mode_restored'] is True, 'actual exact saved outer call/recovery state')
    helper = load_file(HELPER, '_saved_momentum_independent_helper', read(PLAN)['source_files'][str(HELPER)])
    arithmetic = load_file(ARITHMETIC, '_saved_momentum_pure_arithmetic', ARITHMETIC_SHA)
    physical_path = ROOT/'stage183_staging/audit_fallback_systems_v1.py'
    physical = load_file(physical_path, '_saved_momentum_original_contact', read(PLAN)['source_files'][str(physical_path)])
    pure = arithmetic.pure_original_functions()
    # audit_journal is independent arithmetic on actual complete native maps;
    # expected failure is returned distinctly, never treated as physical pass.
    audited = helper.audit_journal(payload['journal'], reynolds_number=pure['reynolds_number'],
        inertial_multiplier=pure['inertial_multiplier'], physical_audit=physical.physical,
        original_trace=payload['evidence']['contact_trial_trace'])
    need(len(payload['journal']['outer_calls']) == 1
         and payload['journal']['enabled'] is (label != 'F1_original')
         and payload['journal']['outer_calls'][0]['outer_inputs'] == fixture['outer_inputs'],
         'exact actual outer input journal, not a copied producer digest')
    systems = payload['journal']['outer_calls'][0]['inner_systems']
    need(payload['prepared_inner_maps'] == len(systems)
         and payload['nonadvancing_units']-payload['prior_nonadvancing_units']
             == payload['prepared_inner_maps']+payload['extra_nested_kernel_units']
         and len(payload['unit_events']) == payload['prepared_inner_maps']+payload['extra_nested_kernel_units'],
         'complete separate prepared-map and extra-kernel accounting')
    trace = payload['evidence']['contact_trial_trace']
    need(payload['evidence']['normal_gap_operand_policy']['prepare_calls'] == [fixture['reference_prepare_call']],
         'actual original raw/effective gap operands and full geometry provenance exactly equal saved system')
    # These literal retained one-contact systems have no fallback/early route.
    # Broader routing is deliberately incomplete for this smallest probe, never
    # a permission to omit the original route-provenance auditor.
    need(trace['trial_route_counts'] == [[0, 0]]
         and not payload['evidence']['early_attempts'] and not payload['evidence']['fallback_systems']
         and not payload['evidence']['repairs'] and not payload['evidence']['stage119_repair_calls']
         and all(not r['canonical_selected'] and not r['cycle_detected']
                 for r in trace['cycle_guard_trials'][0]['records']),
         'same original noncanonical one-contact route coverage; broader routes stop incomplete')
    cycle_audit = original_cycle_audit(trace, arithmetic.np, physical.physical)
    need(cycle_audit['passed'] is True, 'original independent Cycle provenance predicate')
    expected = label == 'F1_original'
    if expected:
        need(payload.get('returned') is False and payload.get('error') == "RuntimeError('inertial momentum closure failed')"
             and audited.get('original_negative_outer_calls') == 1
             and audited.get('successful_outer_calls') == 0
             and audited['outer_results'][0]['original_final_gate_passed'] is False,
             'specific reproduced original momentum negative; no generic exception waiver')
    else:
        need(payload.get('returned') is True and audited.get('passed') is True,
             'candidate complete native solve plus all independent unchanged gates')
        need(audited['original_negative_outer_calls'] == 0
             and audited['successful_outer_calls'] == 1, 'no negative result admitted as candidate pass')
    if label in ('F1_original', 'C_guarded'):
        actual = [digest([s[k] for k in ('vfree', 'mobility', 'jacobian', 'gaps_m', 'dt_s',
                                      'friction', 'tolerance', 'maxiter')]) for s in systems]
        need(actual == fixture['exact_inner_input_digests']
             and [s['velocity'] for s in systems] == [r['map_output'] for r in fixture['reference_inner_maps']]
             and [s['health'] for s in systems] == [r['health'] for r in fixture['reference_inner_maps']],
             'actual original/inactive maps equal every saved Stage242 digest/output/health')
    if label == 'C_guarded':
        need(payload['velocity'] == fixture['reference_legacy_velocity']
             and audited.get('increment_inner_maps') == 0, 'inactive C remains exactly saved native bits')
    if label in ('F1_guarded', 'F1_guarded_repeat'):
        need(audited['increment_inner_maps'] > 0, 'candidate actually exercises saved cancellation guard')
    if label == 'F1_guarded_repeat':
        need(previous is not None and payload['velocity'] == previous['velocity']
             and payload['health'] == previous['health'], 'fresh repeat exact q/contact/full outer health')
    return dict(passed=True, expected_negative=expected, physical_pass=not expected,
                audit=audited, cycle_audit=cycle_audit, no_trajectory_admission=True)


def retire_worker(child, launch, *, idle):
    """Bounded owned-handle cleanup; graceful wait ONLY after full response.

    A pending/native watchdog failure has no grace extension. Birth and full
    accessible command are still required before any terminate operation.
    """
    errors, forced, code = [], False, None
    if child is not None:
        if child.poll() is None and idle:
            stop = OUT/'controller'/'stop.json'
            if not stop.exists():
                commit(stop, dict(utc=utc(), reason='bounded idle diagnostic retirement'))
            try:
                code = child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            except Exception as error:
                errors.append(dict(idle_wait_failure=repr(error)))
        if child.poll() is None:
            if launch is None:
                try:
                    launch = launch_identity('worker_handle_recaptured', child)
                except Exception as error:
                    errors.append(dict(unresolved_worker_identity=repr(error)))
            if launch is not None:
                try:
                    forced = True
                    administration().exact_stop(child, launch)
                except Exception as error:
                    errors.append(dict(stop_failure=repr(error)))
        try:
            code = child.wait(timeout=15) if child.poll() is None else child.wait()
        except Exception as error:
            errors.append(dict(bounded_wait_failure=repr(error)))
    try:
        retired = administration().inspect_identity(launch) if launch is not None else dict(retired=False, unresolved_identity=True)
    except Exception as error:
        retired = dict(retired=False, unresolved_identity=True, error=repr(error))
        errors.append(dict(retirement_observation_failure=repr(error)))
    return dict(returncode=code, forced=forced, launch=launch, retirement=retired, errors=errors)


def worker_self_exit_evidence(final, available):
    if available:
        return dict(available=True, own_returncode_claimed=False)
    need(final.get('passed') is False and final.get('worker_forced') is True
         and type(final.get('observed_worker_returncode')) is int
         and final['worker_retirement'].get('retired') is True,
         'positive/nonforced/unretired execution cannot waive missing worker self-exit')
    return dict(available=False, reason='forced negative worker retired; self-exit unavailable',
                own_returncode_claimed=False, observed_returncode_from_owner_handle=True)


def controller():
    plan = authority(numerical=True, historical=True)
    need(not OUT.exists(), 'single controller; failed/partial OUT is never reused')
    import psutil
    psutil.Process().cpu_affinity([14])
    need(psutil.Process().cpu_affinity() == [14], 'controller logical CPU14')
    resource_guard()
    OUT.mkdir(parents=True, exist_ok=False)
    own = launch_identity('controller')
    commit(OUT/'controller'/'launch.json', own)
    child = None
    child_launch = None
    errors, results, previous_candidate = [], [], None
    forced = False
    child_code = None
    completed_response = False
    stdout = OUT/'worker'/'stdout.log'
    stderr = OUT/'worker'/'stderr.log'
    stdout.parent.mkdir(parents=True, exist_ok=True)
    try:
        with stdout.open('xb') as so, stderr.open('xb') as se:
            child_command = [str(PYTHON), '-B', str(SELF), 'worker']
            child = subprocess.Popen(child_command, cwd=str(ROOT),
                env=dict(os.environ), stdout=so, stderr=se,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            child_launch = launch_identity('worker_handle', child)
            need(child_launch['command'] == child_command, 'original child Popen command equals accessible registered command')
            commit(OUT/'controller'/'worker_handle_launch.json', child_launch)
            for number, (label, fixture_key, enabled) in enumerate(OPERATIONS, 1):
                authority(numerical=True)
                resource_guard()
                current = ledger()
                need(current['unknown_reserved_work_upper_bound'] == 0, 'one unverified record; no successor past unknown')
                cap = 256 if number == 1 else 1
                nonadv_cap = 2 if number == 1 else MAX_NONADVANCING-current['nonadvancing_units']
                need(nonadv_cap > 0, 'native operation cannot start with exhausted map allowance')
                budget_guard(current['all_work_rows']+cap, current['integration_records']+1,
                             current['nonadvancing_units']+nonadv_cap)
                reservation = OUT/'reservations'/f'{number:03d}.json'
                completed_response = False
                commit(reservation, dict(operation=label, work_cap=cap, nonadvancing_cap=nonadv_cap,
                    plan_sha256=sha(PLAN), prior_ledger=current, utc=utc()))
                request = OUT/'requests'/f'{number:03d}.json'
                commit(request, dict(operation=label, enabled=enabled, plan_sha256=sha(PLAN),
                    reservation_sha256=sha(reservation), utc=utc()))
                response = OUT/'responses'/f'{number:03d}.json'
                while not response.exists():
                    authority(numerical=True, refresh_sources=False)
                    need(child.poll() is None, 'worker exited before complete response')
                    start = OUT/'markers'/f'{number:03d}'/'native_start.json'
                    if start.exists():
                        marker = read(start)
                        need(marker['request_sha256'] == sha(request), 'native marker request identity')
                        need(time.time()-marker['time'] <= NATIVE_S, '45s native watchdog')
                    time.sleep(.05)
                reply = read(response)
                need(reply['request_sha256'] == sha(request) and reply['reservation_sha256'] == sha(reservation)
                     and reply['elapsed_s'] <= NATIVE_S, 'complete bounded request/response')
                payload = read_blob(reply['raw_path'], reply['raw_sha256'])
                completed_response = True
                fixture = read(FIXTURES)[fixture_key] if fixture_key else None
                audit_error = None
                try:
                    audit = independent_audit(payload, label, fixture, previous=previous_candidate)
                    authority(numerical=True)
                except Exception as error:
                    audit_error = error
                    audit = dict(passed=False, error=repr(error), traceback=traceback.format_exc())
                if label == 'F1_guarded':
                    previous_candidate = copy.deepcopy(payload)
                units = payload['nonadvancing_units']-payload.get('prior_nonadvancing_units', 0)
                admission = dict(passed=audit_error is None, operation=label, utc=utc(),
                    reservation_sha256=sha(reservation), actual_work_rows=payload['actual_work_rows'],
                    nonadvancing_units=units, audit=audit,
                    physical_work_accepted=audit_error is None and label != 'F1_original',
                    expected_original_negative_preserved=label == 'F1_original',
                    artifacts={str(response):sha(response), str(request):sha(request),
                        reply['raw_path']:reply['raw_sha256']})
                seal(OUT/'admissions'/f'{number:03d}', admission)
                results.append(admission)
                ledger()
                if audit_error is not None:
                    raise audit_error
            commit(OUT/'controller'/'stop.json', dict(utc=utc(), reason='all four probes complete'))
            child_code = child.wait(timeout=30)
            need(child_code == 0, 'actual worker exit0 required for successful execution')
    except Exception as error:
        errors.append(dict(error=repr(error), traceback=traceback.format_exc(), utc=utc()))
    finally:
        retired = retire_worker(child, child_launch, idle=completed_response)
        child_code, forced, child_launch, retirement = (retired[k] for k in ('returncode', 'forced', 'launch', 'retirement'))
        errors.extend(retired['errors'])
        try:
            charges = ledger()
        except Exception as error:
            charges = dict(ledger_authenticated=False, unresolved_work=True,
                conservative_work_upper_bound=MAX_WORK, conservative_records_upper_bound=MAX_RECORDS,
                conservative_nonadvancing_upper_bound=MAX_NONADVANCING, error=repr(error))
            errors.append(dict(ledger_failure=repr(error)))
        try:
            authority(numerical=False, historical=True)
            resources = resource_guard(reserve=0)
        except Exception as error:
            errors.append(dict(final_authentication_failure=repr(error)))
            resources = dict(verified=False)
        passed = not errors and len(results) == 5 and child_code == 0 and not forced and retirement.get('retired') is True
        final = dict(passed=passed, utc=utc(), errors=errors, ledger=charges, resources=resources,
            observed_worker_returncode=child_code, worker_forced=forced, worker_launch=child_launch,
            worker_retirement=retirement, plan_sha256=sha(PLAN), source_files=plan['source_files'],
            expected_original_negative_preserved=any(x.get('expected_original_negative_preserved') for x in results),
            guarded_saved_input_screen_passed=passed, controller_own_returncode_not_observed=True,
            full_restart_qualified=False, trajectory_qualified=False, full_horizon_qualified=False,
            qualified_core_cases_increment=0, all_work_discarded=True)
        final['artifacts'] = {str(p):sha(p) for p in OUT.rglob('*') if p.is_file()}
        seal(OUT/'final_disposition_01', final)
        commit(OUT/'controller'/'exit.json', dict(utc=utc(), observed_worker_returncode=child_code,
            worker_forced=forced, final_sha256=sha(OUT/'final_disposition_01/results.json'),
            worker_handle_launch=child_launch, observed_from_original_worker_popen_handle=child_code is not None,
            worker_closed_logs={str(p):sha(p) for p in (stdout, stderr) if p.is_file() and retirement.get('retired') is True},
            own_returncode_not_observed=True))
    return 0 if passed else 2


def close(manifest_path, expected_manifest_sha256):
    """External-only closure AFTER caller observed controller exit and retirement."""
    plan = authority(numerical=False, historical=True)
    need(sha(manifest_path) == expected_manifest_sha256, 'ROOT-pinned actual exit manifest')
    manifest = read(manifest_path)
    popen_observed = manifest.get('observed_from_original_popen_handle') is True
    direct_observed = manifest.get('observed_from_direct_native_command') is True
    need((popen_observed != direct_observed)
         and type(manifest.get('actual_controller_returncode')) is int
         and manifest.get('terminal_evidence_reference'), 'actual observed controller exit; no inferred0')
    controller_launch = read(OUT/'controller'/'launch.json')
    need(manifest['controller_launch'] == controller_launch
         and manifest['controller_launch_sha256'] == sha(OUT/'controller'/'launch.json'), 'exact owned controller identity')
    if popen_observed:
        need(same_actor(manifest['controller_handle_launch'], controller_launch),
             'ROOT original-Popen identity matches controller self-registration')
    else:
        need(manifest['executed_command'] == controller_launch['command']
             and Path(manifest['executed_command'][0]).resolve() == PYTHON.resolve()
             and Path(manifest['executed_command'][-2]).resolve() == SELF
             and manifest['executed_command'][-1] == 'launch',
             'actual direct qualified native command matches the exact controller identity')
    final = sealed(OUT/'final_disposition_01/results.json')
    child_launch = read(OUT/'controller'/'worker_handle_launch.json')
    registered_child = read(OUT/'worker'/'launch.json')
    owner_exit = read(OUT/'controller'/'exit.json')
    need(same_actor(child_launch, registered_child) and final['worker_launch'] == child_launch
         and final['plan_sha256'] == sha(PLAN) and child_launch['plan_sha256'] == sha(PLAN)
         and controller_launch['plan_sha256'] == sha(PLAN), 'child/owner/PLAN held identities all cross-bound')
    need(owner_exit['final_sha256'] == sha(OUT/'final_disposition_01/results.json')
         and owner_exit['worker_handle_launch'] == child_launch
         and owner_exit['observed_from_original_worker_popen_handle'] is True
         and owner_exit['observed_worker_returncode'] == final['observed_worker_returncode'],
         'controller original worker handle exit and final association')
    verify_mapping(owner_exit['worker_closed_logs'])
    actor_snapshots = []
    for launch in (controller_launch, child_launch):
        observed = administration().inspect_identity(launch)
        need(observed.get('retired') is True, 'birth AND full-command retirement before hashes')
        actor_snapshots.append(dict(launch=launch, inspection=observed))
    self_exit = worker_self_exit_evidence(final, (OUT/'worker/exit.json').exists())
    mandatory = [OUT/'worker/stdout.log', OUT/'worker/stderr.log', OUT/'worker/launch.json',
        OUT/'controller/exit.json', OUT/'controller/worker_handle_launch.json',
        OUT/'final_disposition_01/results.json', OUT/'final_disposition_01/completion.json']
    if self_exit['available']:
        mandatory.append(OUT/'worker/exit.json')
        need(read(OUT/'worker/exit.json')['own_returncode_not_observed'] is True,
             'worker self-exit never substitutes for actual owner-handle code')
    need(all(p.is_file() for p in mandatory), 'all mandatory closed logs and exit evidence')
    need(manifest['final_sha256'] == sha(OUT/'final_disposition_01/results.json'), 'manifest final association')
    verify_mapping(final['artifacts'])
    allowed_after_final = {str(p) for p in (
        OUT/'final_disposition_01/results.json', OUT/'final_disposition_01/completion.json',
        OUT/'controller/exit.json', Path(manifest_path))}
    need({str(p) for p in OUT.rglob('*') if p.is_file()}
         <= set(final['artifacts']) | allowed_after_final,
         'no unsealed post-final native/evidence files')
    artifacts = {str(p):sha(p) for p in OUT.rglob('*') if p.is_file()}
    artifacts[str(Path(manifest_path))] = expected_manifest_sha256
    need(not (OUT/'final_execution_receipt_01').exists(), 'one external receipt only')
    fresh_ledger = ledger()
    need(fresh_ledger == final['ledger'], 'no post-final reservation or ledger extension')
    verify_mapping(manifest['logs'])
    need(all(str(p) in manifest['logs'] for p in mandatory[:2]), 'ROOT observed closed worker logs')
    need(all(str(p) in owner_exit['worker_closed_logs'] for p in mandatory[:2]), 'owner observed closed worker logs')
    need(manifest.get('controller_stdout_path') in manifest['logs']
         and manifest.get('controller_stderr_path') in manifest['logs'], 'ROOT actual closed controller logs')
    need(manifest['controller_stdout_path'] == str(CONTROL_LOGS[0])
         and manifest['controller_stderr_path'] == str(CONTROL_LOGS[1])
         and all(p.is_file() and str(p) in manifest['logs'] for p in CONTROL_LOGS),
         'fixed declared external controller logs; no missing own logs')
    artifacts.update({str(p):sha(p) for p in CONTROL_LOGS})
    verify_mapping(artifacts)
    after = []
    for item in actor_snapshots:
        observed = administration().inspect_identity(item['launch'])
        need(observed.get('retired') is True, 'fresh retirement after all hashes')
        after.append(dict(launch=item['launch'], inspection=observed))
    authority(numerical=False, historical=True)
    passed = manifest['actual_controller_returncode'] == (0 if final['passed'] else 2)
    need(passed, 'actual controller returncode matches preserved disposition')
    receipt = dict(passed=True, execution_closed=True, utc=utc(),
        final_disposition_passed=final['passed'], actual_controller_returncode=manifest['actual_controller_returncode'],
        observed_worker_returncode=final['observed_worker_returncode'], worker_forced=final['worker_forced'],
        manifest_sha256=expected_manifest_sha256, terminal_evidence_reference=manifest['terminal_evidence_reference'],
        retirement_before=actor_snapshots, retirement_after=after, ledger=fresh_ledger,
        source_files=plan['source_files'], physical_inputs=plan['physical_inputs'],
        evidence_files=plan['evidence_files'], historical_evidence_files=plan['historical_evidence_files'],
        artifacts=artifacts, close_source_sha256=sha(SELF),
        saved_input_screen_passed=final['guarded_saved_input_screen_passed'],
        worker_self_exit_evidence=self_exit,
        full_restart_qualified=False, trajectory_qualified=False, full_horizon_qualified=False,
        qualified_core_cases_increment=0, all_work_discarded=True)
    return seal(OUT/'final_execution_receipt_01', receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('interfaces')
    p = sub.add_parser('authorize')
    for flag in ('approval-sha256', 'preparation-sha256', 'clock-sha256'):
        p.add_argument('--'+flag, required=True)
    sub.add_parser('launch')
    sub.add_parser('worker')
    p = sub.add_parser('close')
    p.add_argument('--manifest', required=True)
    p.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args()
    if args.command == 'interfaces':
        print(json.dumps(dict(source_files=source_interfaces(), scope=approval_scope(), native_calls=0)))
    elif args.command == 'authorize':
        print(json.dumps(authorize(args.approval_sha256, args.preparation_sha256, args.clock_sha256)))
    elif args.command == 'launch':
        raise SystemExit(controller())
    elif args.command == 'worker':
        worker()
    else:
        print(json.dumps(close(Path(args.manifest), args.manifest_sha256)))


if __name__ == '__main__':
    main()
