"""External post-supervisor closure of the preserved timecap accuracy negative.

Reads existing sealed evidence only. Never dispatches a solver, evaluator or
comparator, changes a frozen binding, or admits the failed physical case.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import monitor_timecap_full_v1 as monitor
import run_timecap_qualification_v1 as scheduler

s = scheduler.s
OUT = scheduler.OUT
DEST = OUT / 'final_execution_receipt_01'
PINS = {
    'paper1_staging/run_timecap_qualification_v1.py': '2b4fcda67d6c52e42adf4411d18f17d0a0886cec28539f7b6b46d7f85fae7eba',
    'paper1_staging/monitor_timecap_full_v1.py': '5b082902c31fe5895e3c52db299f1bb62f053d7fa66a4a0a8855b77ff726ac3e',
    'paper1_designs/full_horizon_timecap_20261016/design_01.json': 'aead45d9b3983c928f9f5eabd0c77c21c23084ff7e9d9c185c520ed59380f41f',
    'paper1_designs/full_horizon_timecap_20261016/proposal_01.json': 'e293e344fedccfd5f47c8eca72fee3040b1caae9d71d4d708f7222cc09253f58',
    'paper1_runs/full_horizon_timecap_20261016/final_disposition_01/results.json': '06bf5ed53ee04d2c4f66e27e059ef23e92129ba32331fed5ee920cbdde251d21',
    'paper1_runs/full_horizon_timecap_20261016/final_retirement_01/results.json': '3eabaef8e93ec18046bd017bceceaa536ca00a38296fd679cd5a81f9961381ef',
    'paper1_runs/full_horizon_timecap_20261016/supervisor/completion_01/results.json': '88f130fff0ab121bceef419804dfd325e42b23fe90b4525c2cfcf666c9b8d4d6',
    'paper1_runs/full_horizon_timecap_20261016/comparison_fine/results.json': '15d48be2710368ad8499a2998b53f0c31c085b6f1880116fc317d47b1ad048d7',
    'paper1_runs/full_horizon_timecap_20261016/levels/f0p0625/full_audit_01/results.json': '227afecac4e74a63ab7698537e3eda99a1ca0e91af4569986b07e3ffa29b5dfd',
    'paper1_runs/full_horizon_timecap_20261016/levels/f0p03125/full_audit_01/results.json': '13d2c05e1469abe20f5c64d2582211438bd217ef6b58a83588bc15993d9e77b0',
}


def require(value, message):
    s.require(value, 'External failed-qualification closure: ' + message)


def main():
    s.environment()
    require(not DEST.exists(), 'create-only final execution receipt')
    for name, digest in PINS.items():
        require(s.sha(s.ROOT / name) == digest, 'exact frozen record: ' + name)
    plan = scheduler.shared_bound()
    scheduler.verify(plan)
    require(not (OUT / 'watchdog_failure_01').exists(), 'no watchdog failure')
    snapshot = monitor.monitor()
    require(snapshot['evidence_authentication_passed'] and not snapshot['pending_records']
            and not snapshot['observation_advanced_during_read']
            and snapshot['live_numerical_workers'] == 0 and snapshot['resources']['passed'],
            'complete immutable ledger, closed numerical workers and unchanged resources')
    # A scientific negative deliberately makes monitor.healthy false. This is
    # not replaced by a success flag: the negative is bound into this receipt.
    final = s.fields.sealed(OUT / 'final_disposition_01/results.json')
    retirement = s.fields.sealed(OUT / 'final_retirement_01/results.json')
    completion = s.fields.sealed(OUT / 'supervisor/completion_01/results.json')
    pair = s.fields.sealed(OUT / 'comparison_fine/results.json')
    require(final['passed'] is False and final['qualification_passed'] is False
            and final['full_path_accuracy_passed'] is False
            and final['core_result_admitted'] is False
            and final['reason'] == 'dependent_dispatch_stopped'
            and final['eligible_case_count_if_final_retirement_passes'] == 1
            and final['successor_cases_dispatched'] is False,
            'preserve the original accuracy-negative disposition and one qualified case')
    require(pair['passed'] is False and pair['whole_start_to_terminal_paths'] is True,
            'original complete-path accuracy negative')
    require(retirement['passed'] and not retirement['qualification_passed']
            and retirement['final_disposition_sha256'] == s.sha(OUT / 'final_disposition_01/results.json')
            and retirement['owner_identity_sha256'] == s.sha(OUT / 'owner_launch.json')
            and retirement['owner_exit_sha256'] == s.sha(OUT / 'owner/exit.json')
            and retirement['administrative_supervisor_still_live']
            and retirement['separate_supervisor_exit_receipt_required'],
            'internal retirement explicitly defers supervisor exit')
    owner_launch = s.read(OUT / 'owner_launch.json')
    parent_owner_launch = s.read(OUT / 'owner/launch.json')
    require(all(owner_launch[k] == parent_owner_launch[k] for k in ('pid', 'created', 'command')),
            'exact owner birth and full command; independent observation timestamps may differ')
    owner_exit = s.read(OUT / 'owner/exit.json')
    require(completion['passed'] and completion['owner_returncode'] == owner_exit['returncode'] == 0
            and not completion['forced'] and not owner_exit['forced']
            and owner_exit['identity']['retired'] and completion['no_task_numerical_worker_live']
            and completion['owner_exit_sha256'] == s.sha(OUT / 'owner/exit.json'),
            'directly observed owner code and unforced supervisor completion')
    counts = scheduler.ledger()
    require(counts == final['ledger'] == retirement['ledger'], 'identical final immutable ledgers')
    require(counts['accepted_new_physical_steps'] == 4518785
            and counts['accepted_discarded_diagnostic_steps'] == 17984
            and counts['saved_steps'] == counts['accepted_saved_steps'] == 4536769
            and counts['calls'] == 955 and counts['diagnostic_calls'] == 17
            and counts['known_unaccepted_saved_steps'] == counts['unknown_reserved_steps_upper_bound'] == 0
            and not counts['unresolved'], 'separate accepted, diagnostic, unaccepted and unknown totals')
    coarse = counts['levels']['f0p125']
    require(coarse['steps'] == coarse['calls'] == 0
            and not coarse['production_labels'] and not coarse['diagnostic_labels']
            and not (OUT / 'levels/f0p125').exists()
            and not (OUT / 'comparison_coarse').exists()
            and not (OUT / 'windows/window_003').exists(), 'no dependent coarse or successor dispatch')
    artifacts = {}

    def add(mapping):
        for path, digest in mapping.items():
            require(path not in artifacts or artifacts[path] == digest, 'consistent duplicate evidence hash')
            artifacts[path] = digest

    def sealed(path):
        row = s.fields.sealed(path)
        add({str(path): s.sha(path), str(path.with_name('completion.json')): s.sha(path.with_name('completion.json'))})
        return row

    add({str(s.ROOT / name): digest for name, digest in PINS.items()})
    for row in (plan, final, retirement):
        add(row['source_files']); add(row['physical_inputs'])
    add(final['artifacts']); add(final['closed_worker_logs'])
    add(retirement['closed_owner_logs']); add(owner_exit['logs'])
    for name in ('launch_authentication_01', 'final_disposition_01', 'final_retirement_01',
                 'supervisor/completion_01', 'comparison_fine'):
        sealed(OUT / name / 'results.json')
    for level in ('f0p0625', 'f0p03125'):
        base = OUT / 'levels' / level
        audit = sealed(base / 'full_audit_01/results.json')
        native = sealed(base / 'native_completion_01/results.json')
        recovered = sealed(base / 'recoverable/qualification/results.json')
        require(audit['passed'] and audit['fresh_t0'] and audit['original_physics_and_guard_replayed']
                and audit['full_selector_policy_replayed'] and audit['all_exact_numerical_producers_retired']
                and audit['native_completion_sha256'] == s.sha(base / 'native_completion_01/results.json')
                and native['passed'] and native['native_complete']
                and audit['full_checkpoint_sha256'] == native['full_checkpoint_sha256'] == recovered['full_checkpoint_sha256']
                and recovered['passed'] and recovered['design_sha256'] == s.sha(scheduler.PLAN)
                and recovered['prefix_sha256'] == s.sha(base / 'recoverable/prefix.json')
                and s.api.digest(scheduler.DOC.read(base / 'recoverable/checkpoint.json')) == recovered['full_checkpoint_sha256'],
                'completed full physical/raw/history/selector and lossless standalone FULL checkpoint evidence')
        for key in ('artifacts', 'receipts', 'source_files'):
            add(audit[key])
        add({str(path): s.sha(path) for path in (base / 'recoverable').rglob('*') if path.is_file()})
    for key in ('evidence_files', 'path_artifacts', 'source_files'):
        add(pair[key])
    launch_paths = [OUT / 'supervisor/launch.json', OUT / 'owner_launch.json']
    for folder in sorted((OUT / 'windows').glob('window_*')):
        launch_paths.append(folder / 'worker_launch.json')
        closed = s.read(folder / 'exit.json')
        require(closed['returncode'] == 0, 'directly observed numerical-worker exit zero')
        add(closed['logs'])
        require(sealed(folder / 'worker_disposition_01/results.json')['passed'], 'sealed normal numerical-worker disposition')
        sealed(folder / 'launch_authentication_01/results.json')

    def inspect():
        observations = []
        for path in launch_paths:
            launch = s.read(path)
            status = s.identity(launch)
            require(status['retired'], 'both exact birth/full-command identities retired: ' + str(path))
            observations.append(dict(path=str(path), sha256=s.sha(path), launch=launch, inspection=status))
        return observations

    before = inspect()
    for folder in (OUT / 'launcher', OUT / 'owner', OUT / 'supervisor'):
        for path in folder.rglob('*'):
            if path.is_file():
                add({str(path): s.sha(path)})
    require(set(str(OUT / 'launcher' / name) for name in ('stdout.log', 'stderr.log')) <= artifacts.keys(),
            'both deferred launcher logs now present')
    s.api.verify_mapping(artifacts)
    after = inspect()
    scheduler.shared_bound()
    require(datetime.now(timezone.utc) < datetime.fromisoformat(plan['end_utc']), 'external closure within SAME absolute authority')
    result = dict(schema='paper1.timecap-full.external-failed-qualification-closure.v1', passed=True,
        meaning='Post-supervisor execution/evidence closure only; the original full-horizon accuracy qualification FAILED.',
        qualification_passed=False, full_path_accuracy_passed=False, core_result_admitted=False,
        paper1_dataset_complete=False, qualified_case_count=1, dependent_dispatch_stopped=True,
        all_exact_owned_identities_retired=True, identity_inspections_before_hashing=before,
        identity_inspections_after_hashing=after, supervisor_completion_authenticated=True,
        supervisor_returncode=None,
        supervisor_returncode_provenance='No directly observed outer Python return code is available; exact retirement, sealed supervisor completion and closed logs authenticate. No own return code is inferred from the observed owner or launch-wrapper codes.',
        observed_launch_wrapper_completion=dict(root_exec_session_id=24541, tool_chunk_id='9330ef', returncode=0,
            scope='Original unified-exec launch handle; not asserted to propagate the outer supervisor Python return code.'),
        directly_observed_owner_returncode=owner_exit['returncode'], forced=False,
        original_shared_end_utc=plan['end_utc'], design_sha256=s.sha(scheduler.PLAN),
        final_disposition_sha256=s.sha(OUT / 'final_disposition_01/results.json'),
        final_retirement_sha256=s.sha(OUT / 'final_retirement_01/results.json'),
        supervisor_completion_sha256=s.sha(OUT / 'supervisor/completion_01/results.json'),
        negative_fine_comparison_sha256=s.sha(OUT / 'comparison_fine/results.json'),
        ledger=counts, accepted_physical_steps=4518785, discarded_diagnostic_steps=17984,
        known_unaccepted_saved_steps=0, unknown_reserved_steps_upper_bound=0,
        source_files=plan['source_files'], physical_inputs=plan['physical_inputs'],
        closure_source_files={str(Path(__file__).resolve()): s.sha(__file__)}, artifacts=artifacts,
        live_logs_deferred=False, new_native_solver_calls=0, new_transport_steps=0,
        numerical_process_actions=0, physics_or_accuracy_gate_changes=[], utc=s.utc())
    s.seal(DEST, result)
    print(json.dumps(dict(passed=True, qualification_passed=False, qualified_case_count=1,
        final_execution_receipt_sha256=s.sha(DEST / 'results.json'), authenticated_artifacts=len(artifacts))))


if __name__ == '__main__':
    main()
