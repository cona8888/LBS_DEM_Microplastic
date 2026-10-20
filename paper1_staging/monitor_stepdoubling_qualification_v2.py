"""Compact read-only monitor for recovery inside the ORIGINAL qualification grant.

No authority, numerical runtime, force, field, process launch/stop, receipt or
campaign file is created.  The frozen driver is byte-pinned BEFORE import.
Historical raw evidence is retained in the pinned PLAN map but is deliberately
not rehashed here; current physics/code and small baseline receipts ARE hashed.
The numerical owner and final closer retain the full historical/raw audits.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import time


DRIVER = Path(__file__).with_name('run_stepdoubling_qualification_v2.py')
DRIVER_SHA = 'f3790e3876b5b1972c9c662490f7000c9c0a55de3cf66fbf3357345346d0de06'


def need(value, message):
    if not value:
        raise RuntimeError('Read-only qualification monitor: ' + message)


def file_sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(1024 * 1024):
            result.update(block)
    return result.hexdigest()


def frozen_driver():
    need(file_sha(DRIVER) == DRIVER_SHA, 'frozen driver source pin before import')
    spec = importlib.util.spec_from_file_location('frozen_read_only_stepdoubling_driver', DRIVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def identity_key(value):
    return value['pid'], value['created'], value['command']


def metadata_inventory(run):
    """Bounded metadata stamp, excluding intentionally mutable/live logs."""
    root = run.OUT
    candidates = set()
    patterns = (
        'reservations/*.json', 'admissions/*/completion.json',
        'records/*/accounting.json', 'records/*/policy_mechanical_audit_01/completion.json',
        'windows/window_*/launch.json', 'windows/window_*/window.json', 'windows/window_*/exit.json',
        'windows/window_*/requests/*.json', 'windows/window_*/markers/*/*.json',
        'launcher/*.json', 'launcher/*/completion.json', 'owner/*.json',
        'supervisor/*.json', 'supervisor/*/completion.json',
        'levels/*/restarts/*/completion.json', 'levels/*/*/completion.json',
        'comparison_*/completion.json', 'embedded_prefix_screen_01/completion.json',
        'final_disposition_01/completion.json', 'final_execution_receipt_01/completion.json')
    for pattern in patterns:
        candidates.update(root.glob(pattern))
    result = {}
    for path in candidates:
        try:
            stat = path.stat()
            result[str(path.relative_to(root))] = (stat.st_size, stat.st_mtime_ns)
        except FileNotFoundError:
            # A file disappearing is preserved in the subsequent observation;
            # it is not silently asserted to be a completed sealed artifact.
            result[str(path.relative_to(root))] = None
    return result


def completed_receipts(run):
    roots = [run.OUT / name for name in ('comparison_fine', 'comparison_coarse',
        'embedded_prefix_screen_01', 'final_disposition_01', 'final_execution_receipt_01',
        'supervisor/completion_01', 'launcher/completion_01')]
    roots += list((run.OUT / 'levels').glob('*/old_bits_smoke_01'))
    roots += list((run.OUT / 'levels').glob('*/restarts/*'))
    roots += [path for pattern in ('*/native_completion_01', '*/full_audit_01',
        '*/prefix_authentication_and_packet_benchmark_01')
        for path in (run.OUT / 'levels').glob(pattern)]
    result, errors = {}, []
    for folder in roots:
        if not (folder / 'completion.json').exists():
            continue
        name = str(folder.relative_to(run.OUT))
        try:
            body = run.sealed(folder / 'results.json')
            item = dict(passed=body.get('passed') is True,
                results_sha256=run.sha(folder / 'results.json'))
            for key in ('qualification_passed', 'full_path_accuracy_passed', 'qualified', 'closure_complete',
                        'original_fine_pair_passed', 'original_coarse_pair_passed',
                        'actual_supervisor_returncode', 'directly_observed_owner_returncode',
                        'forced', 'owner_forced', 'shared_watchdog_forced', 'reason'):
                if key in body:
                    item[key] = body[key]
            result[name] = item
        except Exception as exc:
            errors.append(dict(kind='completed_receipt_authentication', path=name, error=repr(exc)))
    return result, errors


def process_inventory(run):
    paths = [('launcher', run.OUT / 'launcher/launch.json'),
             ('supervisor_parent_record', run.OUT / 'launcher/supervisor_launch.json'),
             ('supervisor', run.OUT / 'supervisor/launch.json'),
             ('owner', run.OUT / 'owner/launch.json')]
    paths += [('window:' + path.parent.name, path) for path in sorted((run.OUT / 'windows').glob('window_*/launch.json'))]
    result, alerts, read_errors = [], [], []
    for role, path in paths:
        if not path.exists():
            continue
        try:
            launch = run.read(path)
        except Exception as exc:
            read_errors.append(dict(kind='process_launch_metadata_read', role=role, error=repr(exc)))
            continue
        try:
            need(launch.get('design_sha256') == run.sha(run.PLAN), 'process belongs to caller-pinned design')
            # Literal original driver helper checks birth FIRST. Only a proved
            # mismatch excludes an unrelated reused PID. Matching/unreadable
            # birth never excuses an inaccessible or different full command.
            inspected = run.inspect_identity(launch)
            result.append(dict(role=role, launch_path=str(path), launch_sha256=run.sha(path),
                launch=launch, inspection=inspected,
                exact_live_identity=inspected.get('retired') is False))
        except Exception as exc:
            result.append(dict(role=role, launch_path=str(path), retirement_unproven=True, error=repr(exc)))
            alerts.append(dict(kind='process_identity_unverifiable', role=role, error=repr(exc)))
    by_role = {item['role']: item for item in result}
    if all(role in by_role and 'launch' in by_role[role] for role in ('supervisor_parent_record', 'supervisor')):
        if identity_key(by_role['supervisor_parent_record']['launch']) != identity_key(by_role['supervisor']['launch']):
            alerts.append(dict(kind='supervisor_launch_association_mismatch'))
    return result, alerts, read_errors


def pending_classification(counts, *, live_owner, live_worker, failed_execution, final_seen, advanced,
                           completed_admission_for_pending=False):
    if not counts or not counts.get('unresolved'):
        return dict(status='none', alert=False)
    if advanced:
        return dict(status='observation_advanced_during_read', alert=False)
    if completed_admission_for_pending:
        return dict(status='completed_admission_failed_authentication', alert=True)
    if failed_execution or final_seen and not live_owner and not live_worker:
        return dict(status='abandoned_or_failed_reservation', alert=True)
    if live_owner or live_worker:
        return dict(status='in_flight_independent_audit_or_native_work', alert=False)
    return dict(status='unresolved_without_verified_live_owner_or_worker', alert=True)


def native_snapshot(run):
    windows = sorted((run.OUT / 'windows').glob('window_*'))
    if not windows:
        return None, []
    folder = windows[-1]
    requests = sorted((folder / 'requests').glob('*.json'))
    if not requests:
        return dict(window=folder.name, state='awaiting_first_registered_request'), []
    request_path = requests[-1]
    marker = folder / 'markers' / request_path.stem
    request = run.read(request_path)
    request_sha = run.sha(request_path)
    reservation = run.OUT / 'reservations' / f"{request['global_index']:06d}.json"
    need(request['design_sha256'] == run.sha(run.PLAN)
         and request['reservation_sha256'] == run.sha(reservation),
         'native progress belongs to the exact reserved request and pinned design')
    for name in ('native_start.json', 'native_finish.json', 'response.json'):
        path = marker / name
        if path.exists():
            need(run.read(path)['request_sha256'] == request_sha,
                 'native progress marker belongs to exact request bytes: ' + name)
    value = dict(window=folder.name, label=request['label'], level_id=request['level_id'],
        operation=request.get('operation', 'packet'), kind=request['kind'],
        reserved_all_work_rows=request['maximum_work_rows'],
        reserved_nonadvancing_kernel_invocations=request.get('maximum_nonadvancing_kernel_invocations', 0))
    alerts = []
    if (marker / 'failure.json').exists():
        failure = run.read(marker / 'failure.json')
        value.update(state='actual_native_or_preparation_failure', error=failure.get('error'))
        alerts.append(dict(kind='native_request_failure', label=request['label'], error=failure.get('error')))
    elif (marker / 'owner_decision.json').exists():
        value['state'] = 'independently_admitted'
    elif (marker / 'response.json').exists():
        response = run.read(marker / 'response.json')
        value['state'] = 'native_finished_awaiting_independent_admission'
        if response.get('passed') is False:
            alerts.append(dict(kind='negative_native_response', label=request['label']))
    elif (marker / 'native_finish.json').exists():
        value['state'] = 'native_finished_encoding_raw'
    elif (marker / 'native_start.json').exists():
        value['state'] = 'native_packet_running'
        start = run.read(marker / 'native_start.json')
        value['observed_native_elapsed_s'] = max(0., time.time() - start['utc_epoch'])
    else:
        value['state'] = 'registered_input_or_scope_preparation'
    return value, alerts


def observe(run, expected_plan_sha256, expected_proposal_sha256):
    run.environment()
    need(run.is_sha(expected_plan_sha256) and run.sha(run.PLAN) == expected_plan_sha256,
         'caller-pinned immutable PLAN')
    need(run.is_sha(expected_proposal_sha256) and run.sha(run.PROPOSAL) == expected_proposal_sha256,
         'caller-pinned approved proposal')
    plan = run.read(run.PLAN)
    need(plan['binding'] == run.digest({key: value for key, value in plan.items() if key != 'binding'})
         and plan['proposal_sha256'] == expected_proposal_sha256
         and plan['authorization_sha256'] == run.sha(run.AUTH)
         and plan['physical_design_sha256'] == run.sha(run.PHYSICAL)
         and plan['approval_sha256'] == run.sha(run.APPROVAL)
         and plan['clock_sha256'] == run.sha(run.CLOCK), 'exact approved control associations')
    # Never downgrade a code/current-input mismatch because native inventory
    # happened to grow at the same time. These immutable maps cannot advance.
    run.verify_mapping(plan['source_files'])
    run.verify_mapping(plan['physical_inputs'])
    run.verify_mapping(plan['evidence_files'])
    need(isinstance(plan['historical_evidence_files'], dict), 'historical immutable map preserved in pinned PLAN')
    before = metadata_inventory(run)
    alerts, observational_errors = [], []
    try:
        identities, identity_alerts, identity_read_errors = process_inventory(run)
        alerts += identity_alerts
        observational_errors += identity_read_errors
    except Exception as exc:
        identities = []; observational_errors.append(dict(kind='process_inventory_read', error=repr(exc)))
    try:
        counts = run.ledger()
        ledger_error = None
    except Exception as exc:
        counts = None; ledger_error = repr(exc)
    try:
        receipts, receipt_errors = completed_receipts(run)
        observational_errors += receipt_errors
    except Exception as exc:
        receipts = {}; observational_errors.append(dict(kind='receipt_inventory_read', error=repr(exc)))
    try:
        native, native_alerts = native_snapshot(run)
        alerts += native_alerts
    except Exception as exc:
        native = None; observational_errors.append(dict(kind='native_metadata_read', error=repr(exc)))
    exits, failed_execution = {}, False
    for path in sorted((run.OUT / 'windows').glob('window_*/exit.json')) + [run.OUT / 'owner/exit.json']:
        if not path.exists():
            continue
        try:
            closed = run.read(path)
            exits[str(path.relative_to(run.OUT))] = dict(returncode=closed.get('returncode'), forced=closed.get('forced'))
            if closed.get('forced') is True or closed.get('returncode') not in (0, None):
                failed_execution = True
                alerts.append(dict(kind='actual_owned_process_failure', path=str(path),
                                   returncode=closed.get('returncode'), forced=closed.get('forced')))
        except Exception as exc:
            observational_errors.append(dict(kind='exit_metadata_read', path=str(path), error=repr(exc)))
    after = metadata_inventory(run)
    advanced = before != after
    if observational_errors and not advanced:
        alerts += observational_errors
    if ledger_error is not None and not advanced:
        alerts.append(dict(kind='ledger_authentication_failure', error=ledger_error))
    for name, receipt in receipts.items():
        if receipt.get('passed') is False:
            alerts.append(dict(kind='sealed_gate_negative', receipt=name, results_sha256=receipt['results_sha256']))
    live_owner = any(item.get('exact_live_identity') and item['role'] == 'owner' for item in identities)
    live_worker = any(item.get('exact_live_identity') and item['role'].startswith('window:') for item in identities)
    completed_pending = False
    if counts and counts.get('unresolved'):
        index = counts['unresolved'][0]['reservation']['index']
        completed_pending = (run.OUT / 'admissions' / f'{index:06d}' / 'completion.json').exists()
    pending = pending_classification(counts, live_owner=live_owner, live_worker=live_worker,
        failed_execution=failed_execution, final_seen='final_disposition_01' in receipts,
        advanced=advanced, completed_admission_for_pending=completed_pending)
    if pending['alert']:
        alerts.append(dict(kind=pending['status']))
    if counts and counts.get('known_cap_overruns'):
        alerts.append(dict(kind='known_native_cap_overrun', records=counts['known_cap_overruns']))
    now = time.time()
    if now >= run.instant(plan['simulation_cutoff_utc']) and native and native.get('state') == 'native_packet_running':
        alerts.append(dict(kind='native_work_observed_after_numerical_cutoff'))
    if now >= run.instant(plan['end_utc']) and any(item.get('exact_live_identity') for item in identities):
        alerts.append(dict(kind='task_identity_still_live_after_absolute_end'))
    wrapper = receipts.get('launcher/completion_01')
    final_execution = receipts.get('final_execution_receipt_01')
    required_roles = {'launcher', 'supervisor_parent_record', 'supervisor', 'owner'}
    retirement_verified = required_roles <= {item['role'] for item in identities} and all(
        item.get('inspection', {}).get('retired') is True for item in identities)
    # Root still needs its own original-handle/terminal evidence; this monitor
    # reports no invented wrapper return code and creates no exit receipt.
    ready_to_close = wrapper is not None and retirement_verified and final_execution is None and not advanced
    summary = None if counts is None else {key: counts.get(key) for key in (
        'work_rows', 'records', 'production_records', 'standalone_records',
        'accepted_all_work_rows', 'accepted_committed_half_rows', 'rejected_work_rows',
        'discarded_diagnostic_work_rows', 'known_unaccepted_work_rows', 'unknown_reserved_work_upper_bound',
        'known_nonadvancing_kernel_invocations', 'unknown_nonadvancing_kernel_invocations_upper_bound',
        'actual_nonadvancing_kernel_invocations', 'conservative_nonadvancing_kernel_invocations_charge')}
    if summary is not None:
        summary['levels'] = {key: {name: value for name, value in row.items() if name != 'labels'}
                             for key, row in counts['levels'].items()}
        summary['unverified_record_count'] = len(counts['unresolved'])
    return dict(passed=not alerts, read_only=True, alerts=alerts,
        observation_advanced_during_read=advanced, observational_errors=observational_errors,
        ledger_snapshot=summary, ledger_error=ledger_error, pending=pending, latest_native=native,
        completed_receipts=receipts, process_identities=identities, observed_child_exits=exits,
        all_registered_exact_identities_retired=retirement_verified,
        ready_for_separate_external_close=ready_to_close,
        wrapper_completion_sha256=None if wrapper is None else wrapper['results_sha256'],
        wrapper_own_returncode_observed_by_monitor=False,
        final_execution_receipt_required=final_execution is None,
        historical_raw_hashes_rechecked=False,
        historical_map_preserved_by_pinned_PLAN=True,
        immutable_current_source_input_evidence_hashes_verified=True,
        prior_attempt_accounting=plan.get('prior_attempt_accounting'),
        derived_within_original_approval=plan.get('derived_within_original_approval') is True,
        plan_sha256=expected_plan_sha256, proposal_sha256=expected_proposal_sha256,
        frozen_driver_sha256=DRIVER_SHA, utc=run.utc())


def controls():
    counts = {'unresolved': [{'reservation': {'index': 1}}]}
    pending = pending_classification(counts, live_owner=True, live_worker=True,
        failed_execution=False, final_seen=False, advanced=False)
    need(not pending['alert'], 'healthy native/audit pending record is not a gate negative')
    need(pending_classification(counts, live_owner=False, live_worker=False,
        failed_execution=True, final_seen=True, advanced=False)['alert'], 'failed abandoned reservation alerts')
    need(not pending_classification(counts, live_owner=False, live_worker=False,
        failed_execution=True, final_seen=True, advanced=True)['alert'], 'concurrent advancing metadata is explicitly deferred')
    need(pending_classification(counts, live_owner=True, live_worker=False, failed_execution=False,
        final_seen=False, advanced=False, completed_admission_for_pending=True)['alert'], 'sealed invalid admission is not healthy pending')
    tree = __import__('ast').parse(Path(__file__).read_text(encoding='utf-8'))
    forbidden = {'Popen', 'terminate', 'kill', 'exact_stop', 'start_child', 'authorize', 'commit', 'seal',
                 'advance_packet', 'native_stack_prelude', 'load_engine'}
    called = {node.func.attr for node in __import__('ast').walk(tree)
              if isinstance(node, __import__('ast').Call) and isinstance(node.func, __import__('ast').Attribute)}
    need(not called.intersection(forbidden), 'monitor contains no numerical/mutation/process-control call sites')
    return dict(passed=True, pure_controls=5, no_native_calls=True, no_campaign_file_writes=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan-sha256')
    parser.add_argument('--proposal-sha256')
    parser.add_argument('--controls', action='store_true')
    args = parser.parse_args()
    if args.controls:
        print(json.dumps(controls(), sort_keys=True), flush=True)
        return 0
    if not (args.plan_sha256 and args.proposal_sha256):
        parser.error('--plan-sha256 and --proposal-sha256 are required')
    try:
        run = frozen_driver()
        result = observe(run, args.plan_sha256, args.proposal_sha256)
    except Exception as exc:
        result = dict(passed=False, read_only=True, immutable_control_or_monitor_error=repr(exc),
                      frozen_driver_sha256=DRIVER_SHA, no_process_control_or_numerical_action=True)
    print(json.dumps(result, sort_keys=True, allow_nan=True), flush=True)
    return 0 if result['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
