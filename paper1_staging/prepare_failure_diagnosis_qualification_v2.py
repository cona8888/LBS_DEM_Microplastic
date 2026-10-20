"""Create-only diagnosis of closed recovery02 pending-cursor audit failure.

Saved bytes and source/control-flow are inspected without native mechanics,
transport, worker creation or failed-record admission. The old ledgers stay
literal, including the first attempt's conservative unknown32 charge.
"""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import json
import lzma

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
DESIGN = ROOT / 'paper1_designs/full_horizon_repair_20261018'
OUT = ROOT / 'paper1_runs/full_horizon_repair_20261018_recovery02'
DEST = DESIGN / 'failure_diagnosis_qualification_02'
CLOSED = OUT / 'final_execution_receipt_01/results.json'
CLOSED_SHA = 'c117a2349cef6e9123e2a4df76de7694e1aa848eb967aa86693802ddf920370f'
FINAL_SHA = 'c11c4969122781d442e7e9c43fc63ad3799f6ed737fa8abe25ce9d43fae0204f'
FIRST = DESIGN / 'failure_diagnosis_qualification_01/results.json'
FIRST_SHA = 'bc5c1a5665b4dd8ad984465f4918d121cb8991f7e1d677e3e2d5ef742801916b'
RAW = OUT / 'records/f0p0625_odd_accepted_half_left/packet.json.xz'
RAW_SHA = '81354bc44afdad97647ef1c843a94b2c3bb54246309829ac5335deb36ec2e79f'
AUDIT1 = ROOT / 'paper1_staging/audit_full_state_stepdoubling_v1.py'
AUDIT2 = ROOT / 'paper1_staging/audit_full_state_stepdoubling_v2.py'
CHECKS = ROOT / 'paper1_staging/check_stepdoubling_audit_v2.py'


def need(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=True).encode()).hexdigest()


def verify(mapping):
    for path, expected in mapping.items():
        need(sha(path) == expected, 'immutable bytes: ' + path)


def sealed(path, expected):
    path = Path(path)
    need(sha(path) == expected, 'pinned sealed receipt')
    result, completion = read(path), read(path.with_name('completion.json'))
    need(completion['results_sha256'] == expected and completion['passed'] is (result.get('passed') is True), 'complete seal')
    return result


def retired(launch):
    import psutil
    try:
        process = psutil.Process(launch['pid']); born = process.create_time()
        if born != launch['created']:
            return dict(retired=True, birth_mismatch=True, observed_created=born)
        need(process.cmdline() == launch['command'], 'same birth requires exact accessible full command')
        raise RuntimeError('Exact old task identity remains live')
    except psutil.NoSuchProcess:
        return dict(retired=True, no_such_process=True)


def functions(path):
    return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(Path(path).read_text()).body if isinstance(n, ast.FunctionDef)}


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, sort_keys=True, indent=2, allow_nan=True) + '\n')


def main():
    need(not DEST.exists(), 'one material immutable failure02 diagnosis')
    closed = sealed(CLOSED, CLOSED_SHA)
    need(closed['passed'] is True and closed['closure_complete'] is True and closed['qualified'] is False
         and closed['actual_supervisor_returncode'] == closed['actual_owner_returncode'] == 2, 'honestly closed failed recovery02')
    for key in ('artifacts', 'source_files', 'physical_inputs', 'evidence_files'):
        verify(closed[key])
    first = sealed(FIRST, FIRST_SHA)
    need(first['original_failed_unknown_reservation_preserved'] is True
         and first['conservative_shared_spent_charge'] == dict(all_work_rows=32,integration_records=2,
             synthetic_nonadvancing_kernel_invocations=2,numerical_windows=1,production_records=0,accepted_committed_half_rows=0),
         'first attempt32 unknown remains charged without refund')
    final_path = OUT / 'final_disposition_01/results.json'
    need(closed['final_disposition_sha256'] == FINAL_SHA, 'pinned actual final failure')
    final = sealed(final_path, FINAL_SHA); ledger = final['ledger']
    need(ledger['work_rows'] == 2755 and ledger['accepted_all_work_rows'] == 2752
         and ledger['known_unaccepted_work_rows'] == 3 and ledger['unknown_reserved_work_upper_bound'] == 0
         and ledger['records'] == ledger['standalone_records'] == 14
         and ledger['actual_nonadvancing_kernel_invocations'] == 2
         and ledger['production_records'] == ledger['accepted_committed_half_rows'] == 0
         and len(ledger['unresolved']) == 1, 'actual2755/14/2warm all discarded; failed3 known not unknown')
    identities = [x['launch'] for x in closed['exact_retirement_after']]
    need(len(identities) == 4, 'all four exact old actors')
    before = [dict(launch=x, inspection=retired(x)) for x in identities]
    need(sha(RAW) == RAW_SHA and closed['artifacts'][str(RAW)] == RAW_SHA, 'actual saved odd-left raw')
    envelope = json.loads(lzma.decompress(RAW.read_bytes())); packet = envelope['packet']
    marker = packet['checkpoint']['physical_checkpoint']['state']['history']
    need(marker['parent'] is None and marker['parent_length'] == 0, 'fresh t0 standalone prefix')
    packet['checkpoint']['physical_checkpoint']['state']['history'] = marker['delta']
    raw = (json.dumps(packet, sort_keys=True, indent=2, allow_nan=True) + '\n').encode()
    need(hashlib.sha256(raw).hexdigest() == envelope['original_uncompressed_sha256']
         and len(raw) == envelope['original_uncompressed_bytes'], 'complete original packet reconstruction')
    need(packet['status'] == 'paused_controller' and packet['work_rows'] == 3
         and len(packet['accepted_rows']) == 1 and len(packet['work_branches']) == 3
         and packet['cursor_after']['phase'] == 'publish_second_half', 'exact observed odd-left phase')
    c,f1,f2 = packet['work_branches']; cursor = packet['cursor_after']
    need([b['role'] for b in (c,f1,f2)] == ['C','F1','F2']
         and all(b['work_rows'] == len(b['rows']) == 1 and b['error'] is None for b in (c,f1,f2))
         and packet['committed_branch_ids'] == [f1['branch_id']]
         and packet['output_state_token'] == packet['checkpoint']['published_state_token'] == f1['output_state_token']
         and f2['input_state_token'] == f1['output_state_token']
         and f2['before_state'] == f1['after_state']
         and cursor['pending_branch_id'] == f2['branch_id'] and cursor['published_half_count'] == 1
         and cursor['decision']['action'] == 'commit_literal_halves'
         and cursor['decision']['committed_state_token'] == f2['output_state_token']
         and cursor['decision']['scaled_defect'] <= 1., 'literal passed pair retains unpublished F2, never a physical failure')
    full = packet['checkpoint']['physical_checkpoint']
    header = {k:v for k,v in full['state'].items() if k != 'history'}
    f1_header = {k:v for k,v in f1['after_state'].items() if k not in ('history_node','history_length')}
    need(header == f1_header and full['state']['pending_trial'] is None
         and full['state_sha256'] == digest(full['state'])
         and packet['original_FULL_output_sha256'] == digest(full), 'actual FULL physical/history anchor is F1 exactly')
    need(final['error']['message'] == "ValueError('Step-doubling policy audit: staged F1/coarse bound but not committed')"
         and 'audit_full_state_stepdoubling_v1.py' in final['error']['traceback']
         and 'line 565' in final['error']['traceback'], 'actual post-stencil composition failure callsite')
    need(sha(AUDIT1) == '8210d3469c9e5b13a3b382fbf4b3c4db47482d1e999250c5e608af72ba72cb76', 'frozen failed auditor retained')
    old,new = functions(AUDIT1),functions(AUDIT2)
    changed = sorted(k for k in old if old[k] != new.get(k))
    need(changed == ['audit_packet','audit_runtime_packet','normalized_packet_view']
         and set(new)-set(old) == {'normalized_native_decision'}, 'only pending-schema/composition repair; all original physical/cap/decision math functions unchanged')
    need(not (OUT / 'admissions/000014').exists(), 'no failed old record admission')
    clock_path = DESIGN / 'qualification_clock_01/results.json'; clock = read(clock_path)
    need(datetime.now(timezone.utc) < datetime.fromisoformat(clock['end_utc']), 'original shared absolute end, no reset')
    sources = dict(closed['source_files'])
    sources.update({str(p):sha(p) for p in (SELF,AUDIT2,CHECKS)})
    evidence = dict(closed['artifacts'])
    for p in (CLOSED,CLOSED.with_name('completion.json'),FIRST,FIRST.with_name('completion.json'),clock_path,clock_path.with_name('completion.json')):
        evidence[str(p)] = sha(p)
    after = [dict(launch=x,inspection=retired(x)) for x in identities]
    verify(sources); verify(evidence)
    need(digest(read(final_path)['ledger']) == digest(ledger), 'old ledger unchanged')
    body = dict(schema='paper1.stepdoubling.pending-cursor-failure-diagnosis.v1', passed=True,
        previous_closed_receipt_sha256=CLOSED_SHA, previous_first_failure_diagnosis_sha256=FIRST_SHA,
        implementation_defect_confirmed=True,
        cause='V1 canonicalizes trial native decision but not cursor decision before exact pending comparison; its odd-resume domain incorrectly expected F2 only despite retained complete C/F1/F2 pair.',
        repair='Strict native decision fields/witness/F2-reference canonicalization for trial and both cursors; authenticate retained complete prior pair and FULL F1/history, independently repeat original cap/decision math, then publish only F2 exactly once with zero new work.',
        actual_failed_record_sha256=RAW_SHA, old_failed_ledger=ledger, old_failed_ledger_sha256=digest(ledger),
        actual_all_work_rows=2755, independently_admitted_discarded_rows=2752, known_unaccepted_rows=3,
        unknown_new_rows=0, integration_records=14, synthetic_nonadvancing_kernel_invocations=2,numerical_windows=1,
        original_physical_stencil_callbacks_completed_count_inferred=3,
        original_physical_stencil_callback_proof='Actual failure occurs after complete new-branch audit loop; each callback must return original mechanical/raw/cap/history pass before line565 is reached. This is exact source/trace inference, not newly rerun mechanical validation.',
        physical_failure_reported=False, native_pair_defect=cursor['decision'],
        pending_full_F1_sha256=digest(full), pending_F2_state_token=f2['output_state_token'],
        cumulative_conservative_spent_charge=dict(all_work_rows=2787,integration_records=16,
            synthetic_nonadvancing_kernel_invocations=4,numerical_windows=2,production_records=0,accepted_committed_half_rows=0),
        initial_unknown32_preserved_not_refunded=True, old_failed_record_admitted=False,
        controls=dict(test_count=29,observed_test_returncode=0,tool_chunk='e5007c',
            scope='source/mock plus authenticated saved native packet COMPOSITION only; expected F2 publication is a pure data projection, not executed native resume; root preparation reruns independently'),
        unchanged_physical_and_cap_and_scalar_decision_functions=True,changed_source_functions=changed,
        native_restart_qualified=False, full_path_accuracy_passed=False,dispatch_authorized=False,
        new_native_calls=0,new_transport_steps=0,mechanical_replay_performed=False,
        same_approved_start_utc=clock['start_utc'],same_approved_simulation_cutoff_utc=clock['simulation_cutoff_utc'],
        same_approved_end_utc=clock['end_utc'],clock_reset_or_budget_increase=False,
        exact_retirement_before=before,exact_retirement_after=after,
        source_files=sources,evidence_files=evidence,historical_raw_replay_performed=False,
        utc=datetime.now(timezone.utc).isoformat())
    DEST.mkdir(parents=True,exist_ok=False)
    write(DEST/'results.json',body)
    write(DEST/'completion.json',dict(passed=True,results_sha256=sha(DEST/'results.json'),utc=datetime.now(timezone.utc).isoformat()))
    print(json.dumps(dict(passed=True,result_sha256=sha(DEST/'results.json'),source_sha256=sha(SELF),
        audit_v2_sha256=sha(AUDIT2),control_sha256=sha(CHECKS),new_native_calls=0,new_transport_steps=0),sort_keys=True))


if __name__ == '__main__':
    main()
