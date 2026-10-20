"""Zero-step closure and blocked prelaunch handoff; grants no run authority."""
from pathlib import Path
from datetime import timedelta
import os
import platform
import shutil
import psutil
import qualify_broader_early_dispatch_v1 as test
q = test.q; job, api = q.job, q.api
OUT = test.BASE / 'repair_readiness_01'


def run():
    w = api.read(q.WORK); now = job.utc()
    api.require(now < job.policy.utc(w['work_end_utc']), 'work clock')
    d = api.read(job.DESIGN); job.verify(d)
    closure = test.sealed(test.BASE / 'broader_early_dispatch_independent_02')
    api.require(closure['passed'] and closure['window_total_new_steps'] == 40589, 'independent broader closure')
    broad = test.sealed(test.OUT); api.verify_mapping(broad['artifacts'])
    p = api.read(test.DESIGN); api.verify_mapping(p['inputs']); api.verify_mapping(p['sources'])
    numerical = test.sealed(test.BASE / 'early_restart_independent_closure_01')
    fine = test.sealed(test.BASE / 'conditional_fine_independent_audit_01')
    api.require(numerical['diagnostic_numerical_and_evidence_audit_passed'] and not numerical['launcher_metadata_schema_passed'], 'preserved numerical/schema distinction')
    api.require(fine['passed'] and not fine['full_pair_gate_passed'], 'local-only refinement evidence')
    ledger = {**test.PRIOR, 'broader_early_dispatch_01': 16841}
    for name, count in ledger.items():
        api.require(api.read(test.BASE / name / 'results.json')['new_accepted_steps'] == count, 'resolved step count ' + name)
    api.require(sum(ledger.values()) == 40589 and 40589 <= w['maximum_new_accepted_trajectory_steps'], 'full bounded ledger')
    for path in test.RUN.parent.rglob('launch.json'):
        if api.read(path).get('reserved_new_accepted_steps', 0):
            api.require(path.parent.name in ledger, 'no hidden/unresolved reservation')
    workers = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if proc.info['pid'] == os.getpid() or 'python' not in (proc.info['name'] or '').lower(): continue
        cmd = ' '.join(proc.info['cmdline'] or []).lower()
        if 'matdem_microplastic' in cmd or 'stage194_staging' in cmd: workers.append(proc.info)
    api.require(not workers, 'no owned simulation/audit worker remains')
    free = shutil.disk_usage(q.ROOT).free
    api.require(free > w['minimum_free_disk_bytes'], 'disk reserve')
    historical = job.OUT / 'terminal_closure_01/results.json'
    terminal = job.OUT / 'evaluation_01/results.json'
    api.require(api.sha(historical) == w['stage193_terminal_closure_sha256'] and api.sha(terminal) == w['stage193_terminal_result_sha256'], 'historical terminal failure unchanged')
    old_pre = q.ROOT / 'stage192_evaluations/qualified_provenance_campaign_20260924/preflight_01/results.json'
    old = api.read(old_pre)
    api.require(old['new_steps'] == 18200, 'original full-stack qualification cost remains disclosed')
    # This is a retained gate floor, NOT a new performance forecast or a claim
    # that the repaired stack has inherited the old parallel qualification.
    floor_hours = max(d['resource_scenario']['hours_with_margin'], d['provenance_transaction_hours_with_margin'], old['refreshed_hours_with_margin'])
    cutoff = job.policy.utc(d['simulation_cutoff_utc'])
    available_now = (cutoff-now).total_seconds()/3600
    available_at_work_end = (cutoff-job.policy.utc(w['work_end_utc'])).total_seconds()/3600
    comparisons = []
    for report in broad['calls']:
        if report['kind'] == 'healthy':
            previous = api.read(test.BASE/'trajectory_qualification_01/call_01.audit.json')
            old_bytes = test.PREFIX_RAW.stat().st_size
            comparisons.append({'tag': report['tag'], 'same_rows_and_state': True,
                'old_transaction_s': previous['transaction_seconds'], 'new_transaction_s': report['transaction_seconds'],
                'transaction_ratio': report['transaction_seconds']/previous['transaction_seconds'],
                'old_raw_bytes': old_bytes, 'new_raw_bytes': report['raw_bytes'],
                'storage_ratio': report['raw_bytes']/old_bytes,
                'limitation': 'Separate wall-time samples, not a controlled simultaneous benchmark or full-path estimate.'})
        else:
            path = test.FRESH_ROOT / (report['tag'] + '.json.preflight_audit.json')
            previous = api.read(path)
            old_path = test.FRESH_ROOT / (report['tag'] + '.json.xz')
            comparisons.append({'tag': report['tag'], 'same_rows_and_state': True,
                'old_transaction_s': previous['transaction_seconds'], 'new_transaction_s': report['transaction_seconds'],
                'transaction_ratio': report['transaction_seconds']/previous['transaction_seconds'],
                'old_raw_bytes': old_path.stat().st_size, 'new_raw_bytes': report['raw_bytes'],
                'storage_ratio': report['raw_bytes']/old_path.stat().st_size,
                'limitation': 'Short archived control, not whole-campaign cost coverage.'})
    inputs = [Path(__file__), q.WORK, job.DESIGN, test.DESIGN, historical, terminal, old_pre,
              test.OUT/'results.json', test.OUT/'completion.json']
    for name in ('broader_early_dispatch_independent_02', 'conditional_fine_independent_audit_01',
                 'early_restart_independent_closure_01', 'semismooth_seed_qualification_01',
                 'early_semismooth_qualification_01', 'codec_qualification_01', 'failed_history_01'):
        inputs += [test.BASE/name/'results.json', test.BASE/name/'completion.json']
    for report in broad['calls']:
        if report['kind'] != 'healthy': inputs.append(test.FRESH_ROOT/(report['tag']+'.json.preflight_audit.json'))
    bindings = {str(x): api.sha(x) for x in inputs}
    sources = {str(x): api.sha(x) for x in Path(__file__).parent.glob('*.py')}
    candidate_paths = ('early_semismooth_dispatch_v1.py', 'semismooth_rejected_seed_v1.py',
        'audit_early_semismooth_v1.py', 'lossless_trial_references_v2.py')
    blockers = [
        'The changed solver/codec/auditor stack has no new three-worker full-stack qualification; old Stage192 parallel readiness is not inherited.',
        'This contract allows one simulation worker and no production campaign; renewed three-worker qualification and production require new authority.',
        'Only 9,411 steps remain in this window, less than the original 18,200-step full-stack preflight. Do not silently shrink its acceptance contract.',
        'The original 0.1-PV fresh selected/fine observation, dwell/exit gates and release observables remain uncompleted.',
        'The retained runtime-gate floor is not a repaired-stack forecast. After the work window ends the time remaining is already below that floor; deadline fit cannot be certified.'
    ]
    result = {'status': 'LOCAL_REPAIR_QUALIFIED_PRELAUNCH_BLOCKED', 'utc': now.isoformat(),
        'zero_new_trajectory_steps_in_this_review': True, 'step_ledger': ledger, 'window_new_steps': 40589,
        'remaining_step_allowance': 9411, 'unresolved_new_reservations': [], 'old_unsaved_block174_steps_unknown': True,
        'owned_workers': workers, 'free_disk_bytes': free, 'python': platform.python_version(),
        'numerical_repair_and_local_verification_passed': True, 'healthy_and_six_case_regression_exact': True,
        'production_ready': False, 'production_authorized': False, 'fresh_complete_observation': False,
        'population_release_claim': False, 'empirical_validation_claim': False,
        'candidate_sources': {name: sources[str(Path(__file__).parent/name)] for name in candidate_paths},
        'original_cases': d['cases'], 'original_numerical_gates': d['numerical_gates'],
        'prohibited_future_use': ['Restart/overwrite Stage193', 'Reuse misspelled metadata wrapper as a production launcher',
                                  'Treat the conditional short pair as a fresh full-path pass', 'Inherit old parallel readiness without new qualification'],
        'blockers': blockers,
        'next_authority_needed': 'A new contract for the original three-worker 18,200-step full-stack preflight and, only if all unchanged gates pass, a new immutable fresh six-case campaign. Reassess the deadline from current measured costs; no launch is authorized by this handoff.',
        'runtime_gate_floor_hours_not_new_forecast': floor_hours,
        'available_until_simulation_cutoff_hours': available_now,
        'available_if_wait_until_work_end_hours': available_at_work_end,
        'latest_start_under_retained_floor_no_preflight_allowance_utc': (cutoff-timedelta(hours=floor_hours)).isoformat(),
        'simulation_cutoff_utc_unchanged': d['simulation_cutoff_utc'], 'final_audit_deadline_utc_unchanged': d['final_audit_deadline_utc'],
        'fresh_parallel_readiness_demonstrated': False, 'cost_samples': broad['calls'], 'archived_cost_comparisons': comparisons,
        'readiness_stop_reason': 'Reported scope and qualification gate blocker; preserve remaining steps rather than run tests that cannot authorize production.',
        'inputs': bindings, 'sources': sources}
    api.verify_mapping(bindings); api.verify_mapping(sources); api.verify_mapping(broad['artifacts']); job.verify(d)
    OUT.mkdir(parents=True, exist_ok=False)
    job.commit(OUT/'results.json', result); job.commit(OUT/'completion.json', {'results_sha256': api.sha(OUT/'results.json'), 'status': result['status']})
    print('REPAIR_READINESS', result['status'], 'steps', 40589, 'floor_h', floor_hours, 'hours_after_window', available_at_work_end, flush=True)


if __name__ == '__main__': run()
