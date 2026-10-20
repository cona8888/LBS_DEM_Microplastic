"""Create-only, zero-solve closure and recovery dispatch evidence for Stage229."""
from pathlib import Path
import ast
import sys
import psutil
import campaign_common_v1 as c

HERE = Path(__file__).resolve().parent
OLD = c.RUN / 'run_01'
SUP = c.RUN / 'supervisor_01'
FINAL = c.OUT / 'final_disposition_01/results.json'
PLAN = c.DESIGNS / 'transport_design_02.json'
WORKER = HERE / 'continue_baseline_v2.py'
CASE = 's2_i0_fibre_f0p125'
CP = 'b3521bb95f478e0eaf8c80c324d0d142f22cddb13966ea411feccf48da4c83fa'
RECEIPT = '187a88dfb3cac85e65c65cf25558ea3f84409aa7aa849c33c197f866def35dfe'


def need(value, message):
    if not value:
        raise RuntimeError(message)


def identity_retired(record):
    record = dict(record)
    if 'command' not in record and 'argv' in record:
        record['command'] = record['argv']
    need(type(record['pid']) is int and isinstance(record['created'], (int, float))
         and isinstance(record['command'], list), 'Exact recorded process identity')
    try:
        process = psutil.Process(record['pid'])
        birth = process.create_time()
        command = process.cmdline()
    except psutil.NoSuchProcess:
        return dict(pid=record['pid'], created=record['created'], command=record['command'],
                    exact_identity_retired=True, observed='pid_absent')
    need(birth != record['created'] or command != record['command'], 'Old exact task process still live')
    return dict(pid=record['pid'], created=record['created'], command=record['command'],
                exact_identity_retired=True, observed='different_birth_or_command',
                observed_birth=birth, observed_command=command, unrelated_process_untouched=True)


def seal(folder, row):
    c.bound()
    c.commit(folder / 'results.json', row)
    c.commit(folder / 'completion.json', dict(passed=True, results_sha256=c.sha(folder / 'results.json')))


def close_initial():
    c.environment()
    authority = c.bound()
    c.verify(authority['sources'])
    c.verify(authority['inputs'])
    design = c.read(c.DESIGNS / 'supervisor_design_01.json')
    c.verify(design['sources'])
    c.verify(design['inputs'])
    plan = c.read(PLAN)
    c.verify(plan['source_files'])
    c.verify(plan['inputs'])
    c.verify(plan['physical_inputs'])
    final = c.sealed(FINAL)
    c.verify(final['artifacts'])
    need(final['passed'] and final['final_accounting_authenticated']
         and final['new_audited_physical_steps'] == 1304148
         and final['diagnostic_audited_steps'] == 512
         and final['known_unaccepted_saved_steps'] == 0
         and final['unknown_saved_steps_reservation_upper_bound'] == 0
         and final['new_known_saved_steps_including_diagnostics'] == 1304660,
         'Independent initial raw-chain accounting')
    end = c.read(SUP / 'exit.json')
    need(end['final_authentication_completed'] and end['authorization_sha256'] == c.sha(c.AUTH),
         'Initial supervisor completed authentication before retirement')
    for name, code in [('cost_screen', 0), ('baseline', 1), ('final_authentication', 0)]:
        row = c.read(SUP / (name + '_exit.json'))
        need(row['exit_code'] == code and row['exact_owned_identity_retired']
             and not row['forced_deadline_stop'], 'Initial phase retirement disposition')
    identities = []
    launches = [c.RUN / 'launcher_01/launch.json', SUP / 'launch.json', OLD / 'launch.json']
    launches += sorted(SUP.glob('*_worker_launch.json'))
    for path in launches:
        c.bound()
        identities.append(dict(receipt=str(path), **identity_retired(c.read(path))))
    artifacts = {str(FINAL): c.sha(FINAL), str(FINAL.parent / 'completion.json'): c.sha(FINAL.parent / 'completion.json'),
                 str(Path(__file__).resolve()): c.sha(__file__)}
    for folder in [SUP, c.RUN / 'launcher_01']:
        for path in sorted(folder.rglob('*')):
            c.bound()
            if path.is_file():
                artifacts[str(path)] = c.sha(path)
    retirement = c.OUT / 'initial_retirement_01'
    seal(retirement, dict(passed=True, utc=c.utc(), authorization_sha256=c.sha(c.AUTH),
        all_exact_launch_identities_retired=True, identities=identities, artifacts=artifacts,
        initial_attempt_failed_and_preserved=True, new_trajectory_steps=0, numerical_calls=0))

    failure = c.read(OLD / 'failure.json')
    reservation = failure['unresolved_reservation']
    need(failure['transport_design_sha256'] == c.sha(PLAN)
         and failure['last_verified_checkpoint_sha256'] == CP
         and failure['verified_saved_steps'] == 1304660 and failure['diagnostics_verified_steps'] == 512
         and reservation == dict(case=CASE, role='production', segment=471,
                                maximum_saved_steps=10000, input_checkpoint_sha256=CP), 'Failed reservation exactly identified')
    source = WORKER.read_text(encoding='utf-8')
    tree = ast.parse(source)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'segment')
    guards = [(index, node) for index, node in enumerate(function.body)
              if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
              and ast.unparse(node.value) == 'verify_scientific_inputs(plan)']
    need(len(guards) == 1, 'One exact direct scientific guard in segment')
    guard_index, guard_node = guards[0]
    for node in function.body[:guard_index]:
        need(isinstance(node, ast.Expr)
             and ((isinstance(node.value, ast.Constant) and isinstance(node.value.value, str))
                  or (isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == 'api.require')),
             'Only a docstring or cap assertion may precede the scientific guard')
    guard = guard_node.lineno
    mkdir = next(node.lineno for node in ast.walk(function) if isinstance(node, ast.Call)
                 and ast.unparse(node.func) == 'folder.mkdir')
    execute = next(node.lineno for node in ast.walk(function) if isinstance(node, ast.Call)
                   and ast.unparse(node.func) == 'baseline.execute')
    need(guard < mkdir < execute and f'line {guard}, in segment' in failure['traceback']
         and 'FileNotFoundError' in failure['traceback'], 'Failure occurred in guard before any segment launch/solve')
    missing = Path(r'D:\MATDEM_MICROPLASTIC\stage197_runs\deadline_extension_20260926\continuation_01\conditional_fine.json.seal.json')
    expected = plan['physical_inputs'][str(missing)]
    need(expected == '884ef829a6e3f41ce32e8c9c821266d6af60c3e06baa0c3cc0f1c1ed0e18b2aa'
         and c.sha(missing) == expected, 'The same mandatory historical path and bytes are available again')
    root = OLD / CASE
    folders = sorted(root.glob('segment_*'))
    need([p.name for p in folders] == [f'segment_{i:05d}' for i in range(1, 471)]
         and not (root / 'segment_00471').exists(), 'Exactly 470 original segments; failed segment never created')
    inventory = sorted(str(p) for p in OLD.rglob('*') if p.is_file())
    need(all(path in final['artifacts'] and c.sha(path) == final['artifacts'][path] for path in inventory),
         'Every original raw/log/header/checkpoint file inventoried in final disposition')
    last = c.sealed(root / 'segment_00470/results.json')
    need(last['passed'] and last['output_checkpoint_sha256'] == CP
         and c.sha(root / 'segment_00470/results.json') == RECEIPT,
         'Authenticated last accepted endpoint')
    proof_paths = [OLD / 'failure.json', SUP / 'baseline_exit.json', WORKER, PLAN, missing,
                   root / 'segment_00470/results.json', root / 'segment_00470/completion.json',
                   retirement / 'results.json', retirement / 'completion.json', FINAL, FINAL.parent / 'completion.json']
    artifacts = {str(path): c.sha(path) for path in proof_paths}
    stat = missing.stat()
    seal(c.OUT / 'failure_diagnosis_01', dict(passed=True, utc=c.utc(), authorization_sha256=c.sha(c.AUTH),
        transport_design_sha256=c.sha(PLAN), failed_case=CASE, failed_segment=471,
        pre_dispatch_reservation_saved_steps=0, unknown_saved_steps_reservation_upper_bound=0,
        last_verified_checkpoint_sha256=CP, exact_worker_identity_retired=True,
        frozen_pre_dispatch_source_order_verified=True, failed_segment_folder_absent=True,
        all_orphan_work_inventoried=True, original_file_inventory=inventory, artifacts=artifacts,
        same_path_current_sha256=expected, historical_input_path=str(missing),
        current_file_stat=dict(size=stat.st_size, created=stat.st_ctime, modified=stat.st_mtime),
        cause='Observed historical-path read failure; cause unproven; current exact immutable bytes reauthenticated.',
        old_failure_preserved=True, scientific_or_physical_pass_not_inferred_from_file_return=True,
        new_trajectory_steps=0, numerical_calls=0))
    print('STAGE229_INITIAL_CLOSURE_AND_FAILURE_DIAGNOSIS_AUTHENTICATED', flush=True)


def dispatch():
    c.environment()
    authority = c.bound()
    c.verify(authority['sources'])
    c.verify(authority['inputs'])
    import continue_baseline_v3 as worker
    plan = worker.verify(c.read(worker.PLAN))
    for name in ['initial_retirement_01', 'failure_diagnosis_01', 'recovery_seed_01', 'transport_preparation_03']:
        proof = c.sealed(c.OUT / name / 'results.json')
        need(proof['passed'] and proof.get('authorization_sha256', c.sha(c.AUTH)) == c.sha(c.AUTH), 'Specific frozen recovery proof')
        c.verify(proof.get('artifacts', {}))
    old = c.sealed(c.OUT / 'dispatch_decision_01/results.json')
    c.verify(old['inputs'])
    need(old['physical_evidence_gates_passed'] and old['baseline_allowed']
         and not old['candidate_production_authorized'], 'Original independent baseline authority')
    paths = [c.AUTH, worker.PLAN, c.OUT / 'dispatch_decision_01/results.json',
             c.OUT / 'dispatch_decision_01/completion.json', FINAL, FINAL.parent / 'completion.json']
    for name in ['initial_retirement_01', 'failure_diagnosis_01', 'recovery_seed_01', 'transport_preparation_03', 'recovery_guard_controls_01', 'supervisor_identity_controls_03', 'recovery_finalizer_controls_01', 'supervisor_identity_source_archive_02']:
        paths += [c.OUT / name / 'results.json', c.OUT / name / 'completion.json']
    controls = c.sealed(c.OUT / 'recovery_guard_controls_01/results.json')
    need(controls['passed'] and controls['numerical_calls'] == 0, 'Pure new access guard qualification')
    c.verify(controls.get('sources', {}))
    c.verify(controls.get('inputs', {}))
    c.verify(controls.get('artifacts', {}))
    for name in ['supervisor_identity_controls_03', 'recovery_finalizer_controls_01', 'supervisor_identity_source_archive_02']:
        controls = c.sealed(c.OUT / name / 'results.json')
        need(controls['passed'] and controls['numerical_calls'] == 0, 'Pure new controller/accounting qualification')
        c.verify(controls.get('sources', {}))
        c.verify(controls.get('inputs', {}))
        c.verify(controls.get('artifacts', {}))
    controls = c.sealed(c.OUT / 'recovery_finalizer_controls_01/results.json')
    need(controls['source_sha256'] == c.sha(HERE / 'finalize_recovery_v2.py'), 'Actual finalizer is the qualified source')
    seal(c.OUT / 'dispatch_decision_02', dict(passed=True, baseline_allowed=True,
        candidate_production_authorized=False, authorization_sha256=c.sha(c.AUTH), utc=c.utc(),
        scientific_evidence_gates_reauthenticated=True, initial_failed_attempt_remains_failed=True,
        mandatory_path_and_hash_unchanged=True, new_exact_late_restart_gate_required=True,
        original_physical_and_full_path_gates_unchanged=True, prior_shared_saved_steps=1304660,
        reason='Separately frozen same-window equation-preserving recovery; preserved transient-access negative and authenticated accepted prefix.',
        inputs={str(path): c.sha(path) for path in paths}, new_trajectory_steps=0, numerical_calls=0))
    print('STAGE229_RECOVERY_DISPATCH_SEALED', c.sha(c.OUT / 'dispatch_decision_02/results.json'), flush=True)


if __name__ == '__main__':
    {'close_initial': close_initial, 'dispatch': dispatch}[sys.argv[1]]()
