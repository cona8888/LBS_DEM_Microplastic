"""Seal one source/actual-trace diagnosis; no model import or execution.

The old failed ledger remains unchanged.  A zero-target control-flow proof is
separate from its conservative UNKNOWN reservation and from native/restart
qualification.  This script reads only closed evidence and process identities.
"""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
DESIGN = ROOT / 'paper1_designs/full_horizon_repair_20261018'
OUT = ROOT / 'paper1_runs/full_horizon_repair_20261018'
DEST = DESIGN / 'failure_diagnosis_qualification_01'
CLOSURE = OUT / 'final_execution_receipt_01/results.json'
CLOSURE_SHA = 'ebed1438521447cb4fffda16a0784140118456487bc3b9626479b4907d5bce66'
PROPOSAL_SHA = '61d84fb8797fb95b8e4fc7918304d98ae60afc64253eff6d9a26afcc7fd4869d'
ADAPTER = ROOT / 'paper1_staging/full_state_integration_adapter_v1.py'
ADAPTER_SHA = '01001f8f74c42064da2dcb719aec6ba5670fbb3e060f59fac0c4b03579d8fd72'
DRIVER = ROOT / 'paper1_staging/run_stepdoubling_qualification_v1.py'
DRIVER_SHA = 'b21f22446ccbf8a00551f738a9cf116d8a208ad86b5a42521e1ea5b1afabe006'
ORIGINS = [
    'stage236_staging/lm_residual_kernel_v1.py',
    'stage243_staging/qualify_guard_v1.py',
    'stage243_staging/per_pose_guard_v1.py',
    'stage189_staging/contact_trial_trace_v1.py',
    'stage238_staging/continue_lm_case_v1.py',
    'stage104_staging/trajectory_failure_only_rescue_v1.py',
    'stage89_staging/trajectory_short_pgs_seed_v1.py',
    'stage81_staging/trajectory_combined_scalar_v1.py',
    'stage80_staging/trajectory_combined_pruning_v1.py',
    'stage136_staging/compiled_scalar_v1.py',
    'stage53_staging/inertial_contact_multistart_lm_v1.py',
    'stage50_staging/inertial_contact_seeded_lm_v1.py',
]


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
        need(sha(path) == expected, 'unchanged closed bytes: ' + path)


def sealed(path, expected=None):
    path = Path(path)
    if expected is not None:
        need(sha(path) == expected, 'caller-pinned closed receipt')
    result, completion = read(path), read(path.with_name('completion.json'))
    need(completion['results_sha256'] == sha(path)
         and completion['passed'] is (result.get('passed') is True), 'complete immutable seal')
    return result


def retired(launch):
    import psutil
    try:
        process = psutil.Process(launch['pid'])
        born = process.create_time()
        if born != launch['created']:
            return dict(retired=True, birth_mismatch=True, observed_created=born,
                        unrelated_reused_pid_excluded=True)
        command = process.cmdline()
        need(command == launch['command'], 'matching birth requires full accessible exact command')
        raise RuntimeError('Original exact task identity remains live')
    except psutil.NoSuchProcess:
        return dict(retired=True, no_such_process=True)


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, sort_keys=True, indent=2, allow_nan=True) + '\n')


def main():
    need(not DEST.exists(), 'one create-only material diagnosis')
    need(sha(ADAPTER) == ADAPTER_SHA and sha(DRIVER) == DRIVER_SHA, 'executed frozen V1 sources')
    closure = sealed(CLOSURE, CLOSURE_SHA)
    need(closure['passed'] is True and closure['closure_complete'] is True
         and closure['qualified'] is False and closure['actual_supervisor_returncode'] == 2
         and closure['actual_owner_returncode'] == 2, 'honest closed initial scientific failure')
    verify(closure['artifacts'])
    verify(closure['source_files'])
    verify(closure['physical_inputs'])
    verify(closure['evidence_files'])
    sources = dict(closure['source_files'])
    sources[str(SELF)] = sha(SELF)
    need(all(str(ROOT / relative) in sources for relative in ORIGINS), 'every actual observation/origin/wrapper source is pinned')
    verify({str(ROOT / relative): sources[str(ROOT / relative)] for relative in ORIGINS})
    identities = [row['launch'] for row in closure['exact_retirement_after']]
    need(len(identities) == 4 and all(row['inspection']['retired'] is True
         for row in closure['exact_retirement_before'] + closure['exact_retirement_after']), 'four closed exact actors')
    before = [dict(launch=value, inspection=retired(value)) for value in identities]
    final_path = OUT / 'final_disposition_01/results.json'
    final = sealed(final_path, closure['final_disposition_sha256'])
    ledger = final['ledger']
    need(ledger['work_rows'] == ledger['unknown_reserved_work_upper_bound'] == 32
         and ledger['records'] == ledger['standalone_records'] == 2
         and ledger['actual_nonadvancing_kernel_invocations'] == 2
         and ledger['known_nonadvancing_kernel_invocations'] == 2
         and ledger['known_unaccepted_work_rows'] == ledger['production_records'] == 0
         and ledger['accepted_committed_half_rows'] == 0 and len(ledger['unresolved']) == 1,
         'old conservative charge and unresolved reservation preserved literally')
    reserve = OUT / 'reservations/000002.json'
    request_path = OUT / 'windows/window_001/requests/000002.json'
    failure_path = OUT / 'windows/window_001/markers/000002/failure.json'
    start_path = failure_path.with_name('native_start.json')
    reservation, request, failure, start = map(read, (reserve, request_path, failure_path, start_path))
    need(request['reservation_sha256'] == sha(reserve)
         and start['request_sha256'] == sha(request_path)
         and request['operation'] == 'smoke_original' and request['maximum_work_rows'] == 32
         and request['input_prefix'] is None and request['index'] == 2
         and reservation == ledger['unresolved'][0]['reservation'], 'actual first32 smoke request and unchanged unresolved ancestry')
    need(failure['error'] == "RuntimeError('Frozen original solver/projection origins')"
         and failure['native_started'] is True and failure['dependent_dispatch_stopped'] is True,
         'exact observed origin-guard failure, not a hypothetical control')
    need(not (OUT / 'admissions/000002').exists()
         and not (OUT / 'records/f0p0625_smoke_original32').exists(), 'no failed smoke raw or admission created')
    need(len(list((OUT / 'reservations').glob('*.json'))) == 2
         and len(list((OUT / 'windows').glob('window_*'))) == 1, 'no subsequent dispatch or window')
    setup_path = OUT / 'records/w001_arithmetic_setup/arithmetic_setup.json'
    setup = read(setup_path)
    need(setup['nonadvancing_contact_kernel_invocations'] == 2
         and setup['target_outer_transport_calls'] == setup['particle_steps'] == setup['saved_work_rows'] == 0
         and setup['residual_callback_warm']['contact_solver_calls'] == 0
         and setup['residual_callback_warm']['outer_calls'] == 0, 'two separately admitted synthetic calls; not no-native-overall')
    warm_admission = sealed(OUT / 'admissions/000001/results.json')
    need(warm_admission['passed'] is True and warm_admission['nonadvancing_kernel_invocations'] == 2
         and warm_admission['work_rows'] == 0, 'warm work separately authenticated and charged')
    source = ADAPTER.read_text(encoding='utf-8')
    tree = ast.parse(source)
    smoke = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_native_smoke')
    scope = next(node for node in ast.walk(smoke) if isinstance(node, ast.With)
                 and ast.unparse(node.items[0].context_expr) == 'scope()')
    need('runtime.packet_work = 0' in ast.unparse(smoke)
         and 'with scope()' in ast.unparse(smoke), 'explicit zero before observer entry')
    actual = re.findall(r'File "([^"]+)", line (\d+), in ([^\n]+)', failure['traceback'])
    expected_frames = [('_native_smoke', str(ADAPTER), scope.lineno),
                       ('packet_scope', str(ADAPTER), None),
                       ('observation', str(ROOT / 'stage243_staging/qualify_guard_v1.py'), None),
                       ('scope', str(ROOT / 'stage236_staging/lm_residual_kernel_v1.py'), None),
                       ('build', str(ROOT / 'stage236_staging/lm_residual_kernel_v1.py'), None),
                       ('_origins', str(ROOT / 'stage236_staging/lm_residual_kernel_v1.py'), None)]
    selected = []
    for function, path, line in expected_frames:
        candidates = [(p, int(n), f) for p, n, f in actual if f == function and Path(p).resolve() == Path(path).resolve()]
        need(len(candidates) == 1 and (line is None or candidates[0][1] == line), 'actual trace exact authenticated pre-yield callsite')
        selected.append(dict(file=candidates[0][0], line=candidates[0][1], function=function))
    transport_calls = [node for node in ast.walk(scope) if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Name) and node.func.id == 'reference']
    need(len(transport_calls) == 1 and transport_calls[0].lineno > scope.lineno,
         'original reference invocation only inside unentered context body')
    clock_path = DESIGN / 'qualification_clock_01/results.json'
    clock = sealed(clock_path)
    need(clock['proposal_sha256'] == PROPOSAL_SHA
         and datetime.now(timezone.utc) < datetime.fromisoformat(clock['end_utc']), 'same approved absolute window')
    evidence = {str(path): sha(path) for path in (CLOSURE, CLOSURE.with_name('completion.json'),
                final_path, final_path.with_name('completion.json'), reserve, request_path, failure_path, start_path,
                setup_path, OUT / 'admissions/000001/results.json', OUT / 'admissions/000001/completion.json',
                clock_path, clock_path.with_name('completion.json'))}
    evidence.update(closure['artifacts'])
    after = [dict(launch=value, inspection=retired(value)) for value in identities]
    verify(evidence); verify(sources)
    need(digest(read(final_path)['ledger']) == digest(ledger), 'old failed ledger never edited/reclassified')
    result = dict(schema='paper1.stepdoubling.initial-origin-failure-diagnosis.v1', passed=True,
        scope='separate source-and-actual-trace zero-target proof; not original failed-ledger admission',
        actual_failure='frozen original solver/projection origin assertion at context entry',
        cause='V1 entered104/89/81/80 runtime bindings before Stage243 observation/kernel.scope; Stage89 replaces s53._solve and Stage81 replaces s50._project before the frozen-origin assertion.',
        minimal_repair='Separately version adapter; preserve exact original observation/kernel first, then enter identical inner runtime binding scopes before integrator body. Do not weaken origin guard or physical predicates.',
        proof_kind='control-flow inference from authenticated actual traceback and exact executed source, not a measured counter invented after failure',
        zero_target_substeps_proved=True, target_transport_substeps=0, target_outer_force_invocations=0,
        synthetic_nonadvancing_kernel_invocations=2, no_native_work_overall_claimed=False,
        native_start_is_timing_envelope_not_force_dispatch=True, observed_pre_yield_frames=selected,
        unentered_reference_invocation_line=transport_calls[0].lineno,
        old_failed_ledger=ledger, old_failed_ledger_sha256=digest(ledger),
        original_failed_unknown_reservation_preserved=True, original_unknown_reserved_rows=32,
        conservative_shared_spent_charge=dict(all_work_rows=32, integration_records=2,
            synthetic_nonadvancing_kernel_invocations=2, numerical_windows=1, production_records=0,
            accepted_committed_half_rows=0),
        no_unreserve_or_old_admission_written=True, recovery_dispatch_authorized=False,
        native_restart_qualified=False, physical_trajectory_qualified=False, full_path_accuracy_passed=False,
        new_native_calls=0, new_transport_steps=0, process_creation_or_stop_performed=False,
        exact_retirement_before=before, exact_retirement_after=after,
        same_approved_start_utc=clock['start_utc'], same_approved_simulation_cutoff_utc=clock['simulation_cutoff_utc'],
        same_approved_end_utc=clock['end_utc'], clock_reset_or_budget_increase=False,
        closed_initial_receipt_sha256=CLOSURE_SHA, source_files=sources, evidence_files=evidence,
        historical_raw_replay_performed=False,
        utc=datetime.now(timezone.utc).isoformat())
    DEST.mkdir(parents=True, exist_ok=False)
    write(DEST / 'results.json', result)
    write(DEST / 'completion.json', dict(passed=True, results_sha256=sha(DEST / 'results.json'),
          utc=datetime.now(timezone.utc).isoformat()))
    print(json.dumps(dict(passed=True,result_sha256=sha(DEST / 'results.json'),source_sha256=sha(SELF),
        conservative_charge=result['conservative_shared_spent_charge'],new_native_calls=0,new_transport_steps=0),sort_keys=True))


if __name__ == '__main__':
    main()
