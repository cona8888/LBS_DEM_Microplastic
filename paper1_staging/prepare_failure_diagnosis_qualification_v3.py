"""Seal closed recovery03 JSON-publication race, preserving UNKNOWN work.

Only saved source/evidence/identities are read. No model, native, transport,
process creation/stop, parser waiver, old admission or ledger mutation occurs.
"""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
DESIGN = ROOT / 'paper1_designs/full_horizon_repair_20261018'
OUT = ROOT / 'paper1_runs/full_horizon_repair_20261018_recovery03'
DEST = DESIGN / 'failure_diagnosis_qualification_03'
CLOSED = OUT / 'final_execution_receipt_01/results.json'
PREVIOUS = DESIGN / 'failure_diagnosis_qualification_02/results.json'
PREVIOUS_SHA = 'b40dc5f0010460c2702cfbfe10a5ceb1be3204af414dea09f98e6c13a58884b5'
DRIVER = ROOT / 'paper1_staging/run_stepdoubling_qualification_v3.py'
HELPER = Path(__file__).with_name('prepare_failure_diagnosis_qualification_v2.py')
HELPER_SHA = 'e002756595e8fe940d999a0f721f35a67e3968bbc6b0977984aee4999a7fad97'


def main(expected_closed_sha256):
    need = lambda ok, message: None if ok else (_ for _ in ()).throw(RuntimeError(message))
    sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    need(sha(HELPER) == HELPER_SHA, 'pinned pure administrative helper source')
    spec = importlib.util.spec_from_file_location('preserved_pure_diagnosis_helpers', HELPER)
    h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
    need(not DEST.exists(), 'one create-only material diagnosis03')
    closed = h.sealed(CLOSED, expected_closed_sha256)
    need(closed['passed'] is True and closed['closure_complete'] is True and closed['qualified'] is False,
         'exact retired closed scientific-negative recovery03')
    for key in ('artifacts','source_files','physical_inputs','evidence_files'):
        h.verify(closed[key])
    need(sha(DRIVER) == closed['source_files'][str(DRIVER)], 'exact failed driver3 source')
    previous = h.sealed(PREVIOUS, PREVIOUS_SHA)
    need(previous['initial_unknown32_preserved_not_refunded'] is True
         and previous['cumulative_conservative_spent_charge']['all_work_rows'] == 2787,
         'prior attempt charges and unknown32 remain unchanged')
    final_path = OUT/'final_disposition_01/results.json'
    final = h.sealed(final_path, closed['final_disposition_sha256']); ledger = final['ledger']
    need(ledger['work_rows'] == ledger['standalone_work_rows'] == 5446
         and ledger['accepted_all_work_rows'] == 640 and ledger['known_unaccepted_work_rows'] == 0
         and ledger['unknown_reserved_work_upper_bound'] == 4806
         and ledger['records'] == ledger['standalone_records'] == 6
         and ledger['actual_nonadvancing_kernel_invocations'] == 2
         and ledger['production_records'] == ledger['accepted_committed_half_rows'] == 0
         and len(ledger['unresolved']) == 1, 'exact conservative known/unknown accounting, never refund unresolved work')
    pending = ledger['unresolved'][0]
    need(pending['known_work_rows'] is None and pending['conservative_work_charge'] == 4806
         and pending['reservation']['index'] == 6 and pending['reservation']['maximum_work_rows'] == 4806
         and pending['reservation']['label'] == 'f0p0625_initial_right', 'genuine unknown initial-right work remains censored')
    message, trace = final['error']['message'], final['error']['traceback']
    need(message == "JSONDecodeError('Expecting value: line 1 column 1 (char 0)')"
         and "began = read(marker / 'native_start.json')" in trace
         and 'run_stepdoubling_qualification_v3.py' in trace, 'actual owner JSON marker-read failure, not native timeout predicate')
    marker = OUT/'windows/window_001/markers/000006'
    start_path = marker/'native_start.json'; request_path = OUT/'windows/window_001/requests/000006.json'
    reservation_path = OUT/'reservations/000006.json'
    start, request, reservation = h.read(start_path),h.read(request_path),h.read(reservation_path)
    need(start['request_sha256'] == sha(request_path) and request['reservation_sha256'] == sha(reservation_path)
         and reservation == pending['reservation'] and request['operation'] == 'packet', 'same actual request and unknown reservation')
    need(not any((marker/name).exists() for name in ('native_finish.json','response.json'))
         and not (OUT/'records/f0p0625_initial_right').exists()
         and not (OUT/'admissions/000006').exists(), 'no authenticatable completion/raw/accounting/admission for failed request')
    need(len(list((OUT/'reservations').glob('*.json'))) == 6
         and len(list((OUT/'windows').glob('window_*'))) == 1, 'no later dispatch inferred or hidden')
    window_exit = h.read(OUT/'windows/window_001/exit.json')
    need(window_exit['forced'] is True and window_exit['retirement_verified'] is True,
         'actual cleanup forced worker retirement, not a declared native-timeout event')
    tree = ast.parse(DRIVER.read_text()); commit = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='commit')
    contexts = [n for n in ast.walk(commit) if isinstance(n,ast.With)]
    need(len(contexts) == 1 and ast.unparse(contexts[0].items[0].context_expr) == "path.open('xb')"
         and any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='write' for n in ast.walk(contexts[0])),
         'visible final pathname is created before payload write/close in failed source')
    need('json.loads' in ast.unparse(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='read')),
         'strict parser was not bypassed')
    identities = [x['launch'] for x in closed['exact_retirement_after']]
    need(len(identities) == 4, 'all four exact old task actors')
    before = [dict(launch=x,inspection=h.retired(x)) for x in identities]
    clock_path = DESIGN/'qualification_clock_01/results.json'; clock = h.read(clock_path)
    need(datetime.now(timezone.utc) < datetime.fromisoformat(clock['end_utc']), 'same approved end; no clock extension')
    sources = dict(closed['source_files']); sources[str(SELF)] = sha(SELF); sources[str(HELPER)] = HELPER_SHA
    evidence = dict(closed['artifacts'])
    for p in (CLOSED,CLOSED.with_name('completion.json'),PREVIOUS,PREVIOUS.with_name('completion.json'),clock_path,clock_path.with_name('completion.json')):
        evidence[str(p)] = sha(p)
    after = [dict(launch=x,inspection=h.retired(x)) for x in identities]
    h.verify(sources);h.verify(evidence)
    need(h.digest(h.read(final_path)['ledger']) == h.digest(ledger), 'failed old ledger never mutated')
    body = dict(schema='paper1.stepdoubling.journal-publication-failure-diagnosis.v1',passed=True,
        previous_closed_receipt_sha256=expected_closed_sha256,previous_failure_diagnosis_sha256=PREVIOUS_SHA,
        implementation_defect_confirmed=True,
        cause='Owner reads native_start.json after exists() while original commit opens the final path xb before buffered JSON write/close. Actual strict parser raised at char0; the same immutable marker is complete and request-associated after retirement.',
        repair='Separate controller4 source must publish complete closed JSON atomically/create-only. Preserve strict parsing, all source/evidence checks and original native45s ceiling; no parser waiver or timeout enlargement.',
        claim_boundary='Administrative publication/observation failure is observed. Missing native_finish/response/raw leaves actual request work UNKNOWN. No zero-target, physical-failure, native-timeout or completed-native-odd-restart claim follows.',
        actual_error=final['error'],old_failed_ledger=ledger,old_failed_ledger_sha256=h.digest(ledger),
        actual_all_work_rows=None,conservative_all_work_charge_rows=5446,
        independently_admitted_discarded_rows=640,known_unaccepted_rows=0,unknown_reserved_work_upper_bound=4806,
        integration_records=6,synthetic_nonadvancing_kernel_invocations=2,numerical_windows=1,
        cumulative_conservative_spent_charge=dict(all_work_rows=8233,integration_records=22,
            synthetic_nonadvancing_kernel_invocations=6,numerical_windows=3,production_records=0,accepted_committed_half_rows=0),
        cumulative_accepted_discarded_rows=3392,cumulative_known_unaccepted_rows=3,cumulative_unknown_reserved_work_upper_bound=4838,
        initial_unknown32_preserved_not_refunded=True,recovery03_unknown4806_preserved_not_refunded=True,
        work_refund_or_old_admission_written=False,old_failed_record_admitted=False,
        native_timeout_proved=False,physical_failure_reported=False,zero_target_work_proved=False,
        odd_native_restart_completed=False,prior_source_mock_odd_bridge_is_not_native_qualification=True,
        parser_waiver=False,native_time_limit_increase=False,native_restart_qualified=False,full_path_accuracy_passed=False,
        dispatch_authorized=False,new_native_calls=0,new_transport_steps=0,mechanical_replay_performed=False,
        same_approved_start_utc=clock['start_utc'],same_approved_simulation_cutoff_utc=clock['simulation_cutoff_utc'],
        same_approved_end_utc=clock['end_utc'],clock_reset_or_budget_increase=False,
        exact_retirement_before=before,exact_retirement_after=after,source_files=sources,evidence_files=evidence,
        historical_raw_replay_performed=False,utc=datetime.now(timezone.utc).isoformat())
    DEST.mkdir(parents=True,exist_ok=False)
    h.write(DEST/'results.json',body)
    h.write(DEST/'completion.json',dict(passed=True,results_sha256=sha(DEST/'results.json'),utc=datetime.now(timezone.utc).isoformat()))
    print(json.dumps(dict(passed=True,result_sha256=sha(DEST/'results.json'),source_sha256=sha(SELF),new_native_calls=0,new_transport_steps=0),sort_keys=True))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Supply exact externally closed recovery03 receipt SHA')
    main(sys.argv[1])
