"""Final read-only evidence audit after the frozen timecap evaluator succeeds.

No native solver, integration, authorization, or previous-file mutation is
available here. The only output is a new create-only final retirement receipt.
Local scientific acceptance remains separate from full-path admission.
"""
from pathlib import Path
from datetime import datetime, timezone
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import onset_timecap_experiment_v1 as experiment

s = experiment.s
api = s.api
ROOT, OUT = experiment.ROOT, experiment.OUT
SELF = Path(__file__).resolve()
read, sha, require = experiment.read, experiment.sha, experiment.require
DESTINATION = OUT / 'retirement_01'


def _bind(path, artifacts):
    path = Path(path)
    require(path.is_file(), 'Final retirement requires existing evidence: ' + str(path))
    artifacts[str(path)] = sha(path)


def _document(path, expected, artifacts):
    """Authenticate a document reference, its exact payload and wire seal."""
    path = Path(path)
    value = experiment.DOC.read(path)
    require(api.digest(value) == api.digest(expected),
            'Standalone FULL checkpoint matches reconstructed raw ancestry')
    _bind(path, artifacts)
    reference = read(path)
    if isinstance(reference, dict) and reference.get('format') == 'dem-json-document-reference-v1':
        payload = path.with_name(path.stem + '.payload.json.xz')
        require(Path(reference['payload']).resolve() == payload.resolve(),
                'Same-directory complete document payload')
        require(reference['design_sha256'] == sha(experiment.PHYSICAL),
                'Standalone complete document numerical design binding')
        _bind(payload, artifacts)
        _bind(payload.with_suffix('.seal.json'), artifacts)
    return value


def _identity(path, action, artifacts):
    path = Path(path)
    launch = read(path)
    command = launch['command']
    require(isinstance(command, list) and len(command) == 5
            and Path(command[0]).resolve() == Path(experiment.PYTHON).resolve()
            and command[1:3] == ['-B', '-u']
            and Path(command[3]).resolve() == experiment.SELF.resolve()
            and command[4] == action,
            'Exact qualified Python/script/action launch command')
    observed = s.identity(launch)
    require(observed['retired'], 'Exact task-owned process birth AND command identity retired')
    _bind(path, artifacts)
    return dict(path=str(path), source_sha256=sha(path), launch=launch, inspection=observed)


def retire(observed_code, root_session):
    require(observed_code == 0 and type(root_session) is int and root_session > 0,
            'Externally observed successful supervisor exit and concrete root session')
    require(not DESTINATION.exists(), 'Create-only retirement; never overwrite an earlier receipt')
    plan = read(experiment.PLAN)
    require(datetime.now(timezone.utc) < datetime.fromisoformat(plan['end_utc']),
            'Final retirement stays inside the existing absolute window')
    api.verify_mapping(plan['source_files'])
    api.verify_mapping(plan['physical_inputs'])
    require(plan['binding'] == api.digest({k: v for k, v in plan.items() if k != 'binding'})
            and plan['authorization_sha256'] == sha(experiment.AUTH)
            and plan['physical_design_sha256'] == sha(experiment.PHYSICAL),
            'Frozen original design/authority binding')
    evaluation_path = OUT / 'evaluation_01/results.json'
    evaluation = s.fields.sealed(evaluation_path)
    final_path = OUT / 'final_disposition_01/results.json'
    final = s.fields.sealed(final_path)
    require(evaluation['passed'] and final['passed'] and final['native_complete'],
            'Frozen independent evaluator completed before retirement')
    require(evaluation['observed_supervisor_exit_code'] == observed_code
            and evaluation['root_exec_session_id'] == root_session,
            'Same externally observed supervisor exit/session')
    require(evaluation['original_full_path_admission'] is False
            and evaluation['publication_case_count_increment'] == 0
            and final['diagnostic_only'] is True
            and final['accepted_physical_steps'] == 0
            and final['core_result_admitted'] is False
            and final['full_path_accuracy_passed'] is False,
            'Local diagnostic never admits a publication/full-path case')
    api.verify_mapping(evaluation['source_files'])
    api.verify_mapping(evaluation['artifacts'])
    api.verify_mapping(evaluation['closed_logs'])
    artifacts = dict(evaluation['artifacts'])
    for path in (experiment.PLAN, experiment.AUTH, experiment.PHYSICAL,
                 experiment.PROPOSAL, evaluation_path, evaluation_path.with_name('completion.json'),
                 final_path, final_path.with_name('completion.json')):
        _bind(path, artifacts)
    identities = [_identity(OUT / 'controller_01/launch.json', 'supervise', artifacts),
                  _identity(OUT / 'controller_01/worker_launch.json', 'run', artifacts),
                  _identity(OUT / 'worker_launch.json', 'run', artifacts)]
    exit_path = OUT / 'controller_01/exit.json'
    exit_record = read(exit_path)
    require(exit_record['returncode'] == 0, 'Recorded numerical worker actually exited zero')
    api.verify_mapping(exit_record['logs'])
    require(exit_record['logs'] == evaluation['closed_logs'], 'Same final closed-log identities')
    artifacts.update(exit_record['logs'])
    _bind(exit_path, artifacts)

    physical = read(experiment.PHYSICAL)
    proposal = read(experiment.PROPOSAL)
    require(len(final['branches']) == 2 and len(physical['cases']) == 2,
            'Exactly the two prospectively frozen diagnostic branches')
    labels = final['production_labels']
    expected_labels = ['smoke']
    for i in (0, 1):
        branch = final['branches'][i]
        local_labels = branch['labels']
        require(local_labels and local_labels == [f'branch{i}_local_{k:05d}'
                for k in range(1, len(local_labels) + 1)]
                and len(local_labels) <= proposal['branch_nonrestart_call_caps'][i],
                'Complete ordered local chain with the original branch call cap')
        expected_labels.extend([f'branch{i}_prelude', f'branch{i}_serial',
                                f'branch{i}_split_a', f'branch{i}_split_b', *local_labels])
    require(labels == expected_labels and len(set(labels)) == len(labels),
            'No duplicate, skipped or unaccounted admitted diagnostic record')
    reservation_paths = list((OUT / 'reservations').glob('*.json'))
    require({path.stem for path in reservation_paths} == set(labels)
            and {path.name for path in (OUT / 'records').iterdir() if path.is_dir()} == set(labels),
            'All reservations and record folders are resolved exactly once')
    codec = experiment.original.archives.build(s.q.job.codec, preset=9)
    summaries = {}
    used = reserved_steps = 0
    branch_steps = [0, 0]
    for label in labels:
        i = 0 if label == 'smoke' else int(label[6])
        case = physical['cases'][i]
        seed, _ = experiment.seed_for(i)
        previous = None
        if label in ('smoke', f'branch{i}_prelude') or label == f'branch{i}_local_00001':
            before, prefix = seed, None
        elif label.endswith(('_serial', '_split_a')):
            ancestor = f'branch{i}_prelude'
            before, prefix = summaries[ancestor]['checkpoint'], summaries[ancestor]['prefix']
            previous = sha(OUT / 'records' / ancestor / 'results.json')
        elif label.endswith('_split_b'):
            ancestor = f'branch{i}_split_a'
            before, prefix = summaries[ancestor]['checkpoint'], summaries[ancestor]['prefix']
            previous = sha(OUT / 'records' / ancestor / 'results.json')
        else:
            ancestor = f'branch{i}_local_{int(label.rsplit("_", 1)[1]) - 1:05d}'
            before, prefix = summaries[ancestor]['checkpoint'], summaries[ancestor]['prefix']
            previous = sha(OUT / 'records' / ancestor / 'results.json')
        if label == 'smoke': cap = proposal['smoke_steps']
        elif label.endswith('_prelude'): cap = proposal['prelude_step_caps'][i]
        elif label.endswith('_serial'): cap = proposal['serial_steps']
        elif label.endswith(('_split_a', '_split_b')): cap = proposal['split_steps']
        else: cap = min(5000, proposal['branch_nonrestart_step_caps'][i] - branch_steps[i])
        reservation_path = OUT / 'reservations' / (label + '.json')
        reservation = read(reservation_path)
        require(reservation == dict(label=label, maximum_saved_steps=cap,
                input_checkpoint_sha256=api.digest(before), previous=previous),
                'Original pre-dispatch reservation, parent and exact cap')
        _bind(reservation_path, artifacts)
        reserved_steps += cap
        folder = OUT / 'records' / label
        guard = s.fields.sealed(folder / 'guard_completion/results.json')
        api.verify_mapping(guard['artifacts'])
        extra = s.fields.sealed(folder / 'timecap_guard/results.json')
        require(guard['passed'] and extra['passed']
                and extra['raw_sha256'] == sha(folder / 'call.json.xz')
                and extra['original_physical_guard_sha256'] == sha(folder / 'guard_completion/results.json'),
                'Exact raw original-physics and supplementary-policy admissions')
        record, next_prefix = codec.read_record(folder / 'call.json.xz', sha(experiment.PHYSICAL), prefix)
        rows, checkpoint = record['rows'], record['result']['checkpoint']
        require(record['spec'] == case['spec']
                and record['input_checkpoint_sha256'] == api.digest(before)
                and guard['full_checkpoint_sha256'] == api.digest(checkpoint)
                and 0 < len(rows) <= cap
                and checkpoint['state_sha256'] == api.digest(checkpoint['state']),
                'Complete exact raw/history/checkpoint ancestry and bounded saved rows')
        if '_local_' in label: branch_steps[i] += len(rows)
        used += len(rows)
        summaries[label] = dict(checkpoint=checkpoint, prefix=next_prefix,
            row_count=len(rows), trigger_count=sum(bool(entry['trigger_grain_ids'])
                for entry in record['onset_timecap']['journal']))
        if label.endswith(('_serial', '_split_a', '_split_b')):
            summaries[label]['restart_rows'] = rows
        artifacts.update(guard['artifacts'])
        for path in (folder / 'guard_completion/results.json', folder / 'guard_completion/completion.json',
                     folder / 'timecap_guard/results.json', folder / 'timecap_guard/completion.json'):
            _bind(path, artifacts)

    restarts, recoverable = [], []
    for i in (0, 1):
        serial, a, b = [summaries[f'branch{i}_{name}'] for name in ('serial', 'split_a', 'split_b')]
        require(serial['row_count'] == 4096 and a['row_count'] == b['row_count'] == 2048
                and serial['trigger_count'] > 0 and b['trigger_count'] > 0
                and api.digest(serial['restart_rows']) == api.digest(a['restart_rows'] + b['restart_rows'])
                and api.digest(serial['checkpoint']) == api.digest(b['checkpoint']),
                'Exact4096 versus2048+2048 restart exercises the real trigger in successor')
        receipt_path = OUT / f'restart_{i}/results.json'
        receipt = s.fields.sealed(receipt_path)
        require(receipt['passed'] and receipt['discarded_steps'] == 8192
                and receipt['exact_rows'] and receipt['exact_full_checkpoint_history']
                and receipt['trigger_in_serial_and_split_successor']
                and receipt['late_seed_time_s'] == summaries[f'branch{i}_prelude']['checkpoint']['state']['t'],
                'Bound original triggered restart receipt')
        _bind(receipt_path, artifacts)
        _bind(receipt_path.with_name('completion.json'), artifacts)
        restarts.append(dict(branch=i, serial_steps=4096, split_steps=[2048, 2048],
            trigger_count_serial=serial['trigger_count'], trigger_count_split_successor=b['trigger_count'],
            exact_rows=True, exact_full_checkpoint_history=True, receipt_sha256=sha(receipt_path)))
        branch = final['branches'][i]
        last = summaries[branch['labels'][-1]]
        require(branch['case_id'] == physical['cases'][i]['id']
                and branch['factor'] == physical['cases'][i]['factor']
                and branch['new_steps'] == branch_steps[i] <= proposal['branch_nonrestart_step_caps'][i]
                and branch['checkpoint_sha256'] == api.digest(last['checkpoint'])
                and last['checkpoint']['state']['t'] == physical['cases'][i]['spec']['horizon_s'],
                'Complete unchanged10ms local observation and branch saved-step accounting')
        checkpoint_path = OUT / f'recoverable_{i}/checkpoint.json'
        _document(checkpoint_path, last['checkpoint'], artifacts)
        prefix_path = OUT / f'recoverable_{i}/prefix.json'
        require(read(prefix_path) == last['prefix'].reference(),
                'Standalone final prefix matches exact reconstructed history ancestry')
        _bind(prefix_path, artifacts)
        recoverable.append(dict(branch=i, checkpoint_sha256=api.digest(last['checkpoint']),
            checkpoint_reference_sha256=sha(checkpoint_path), prefix_sha256=sha(prefix_path),
            full_checkpoint_and_history_ancestry_authenticated=True))

    calls = len(reservation_paths)
    require(final['known_unaccepted_saved_steps'] == final['unknown_reserved_steps_upper_bound'] == 0
            and final['conservative_call_charges'] == calls <= experiment.CALL_CAP
            and used == final['discarded_diagnostic_steps'] == evaluation['discarded_diagnostic_steps']
            and used <= reserved_steps <= experiment.STEP_CAP
            and final['prior_case_saved_steps'] == experiment.PRIOR_STEPS
            and final['cumulative_saved_steps'] == evaluation['cumulative_saved_steps'] == experiment.PRIOR_STEPS + used <= 6000000
            and final['cumulative_conservative_calls'] == evaluation['cumulative_conservative_calls'] == experiment.PRIOR_CALLS + calls <= 1500,
            'Complete accepted/known-unaccepted/unknown/shared saved-step and call ledger')
    source_files = {**plan['source_files'], str(SELF): sha(SELF)}
    api.verify_mapping(source_files)
    api.verify_mapping(plan['physical_inputs'])
    api.verify_mapping(artifacts)
    require(datetime.now(timezone.utc) < datetime.fromisoformat(plan['end_utc']),
            'Receipt finished inside the existing absolute window')
    result = dict(passed=True, diagnostic_only=True,
        local_screen_passed=evaluation['local_screen_passed'], metrics=evaluation['metrics'],
        original_full_path_admission=False, publication_case_count_increment=0,
        accepted_physical_steps=0, discarded_diagnostic_steps=used,
        known_unaccepted_saved_steps=0, unknown_reserved_steps_upper_bound=0,
        maximum_reserved_saved_steps=reserved_steps, conservative_call_charges=calls,
        cumulative_saved_steps=experiment.PRIOR_STEPS + used,
        cumulative_conservative_calls=experiment.PRIOR_CALLS + calls,
        exact_restarts=restarts, recoverable=recoverable, identities=identities,
        all_exact_owned_identities_retired=True, closed_logs=exit_record['logs'],
        observed_supervisor_exit_code=observed_code, root_exec_session_id=root_session,
        final_disposition_sha256=sha(final_path), evaluation_sha256=sha(evaluation_path),
        source_files=source_files, physical_inputs=plan['physical_inputs'], artifacts=artifacts,
        auditor_source_sha256=sha(SELF), native_solver_calls=0, new_saved_steps=0, utc=s.utc())
    experiment.seal(DESTINATION, result)
    print('TIMECAP_FINAL_RETIREMENT', sha(DESTINATION / 'results.json'),
          'LOCAL_SCREEN', result['local_screen_passed'], 'FULL_PATH', False, flush=True)
    return result


if __name__ == '__main__':
    retire(int(sys.argv[1]), int(sys.argv[2]))
