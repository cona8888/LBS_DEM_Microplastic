"""Prepare/audit a next-run specification; intentionally contains NO launcher.

Reads immutable evidence and creates new handoff artifacts. It cannot execute a
trajectory, start a process, promote an old run or confer new launch authority.
"""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage185_staging'))
import campaign_lifecycle_policy_v1 as policy

BASE = 'next_campaign_handoff_20260924'
OUT = ROOT / 'stage186_evaluations' / BASE / 'handoff_01'
MANIFEST = ROOT / 'stage186_designs' / BASE / 'preparation_01.json'
ORIGINAL = ROOT / 'stage167_designs/paired_full_path_deadline_20260922/design_01.json'
WORK = ROOT / 'stage172_designs/four_hour_work_20260923/contract_01.json'
RESOURCE = ROOT / 'stage179_evaluations/history_prefix_20260924/resource_independent_audit_01/results.json'
LEDGER = ROOT / 'stage184_evaluations/work_window_review_20260924/review_01/results.json'

# Named predicates keep original failed resource scenarios failed. No blanket
# relabelling of a stage as passed merely because one local check was successful.
EVIDENCE = [
    ('stage172_evaluations/fast_contact_20260923/independent_audit_01', ['audit_integrity_passed', 'integration_verified', 'exact_restart']),
    ('stage173_evaluations/immutable_field_20260923/independent_audit_01', ['passed', 'exact_all_rows_and_checkpoint_states']),
    ('stage174_evaluations/certified_sweep_20260924/independent_audit_01', ['audit_integrity_passed', 'integration_verified', 'exact_restart']),
    ('stage175_evaluations/combined_cost_20260924/independent_audit_01', ['integration_verified']),
    ('stage176_evaluations/lossless_storage_20260924/qualification_01', ['passed', 'all_original_json_bytes_exact']),
    ('stage177_evaluations/extended_optimized_20260924/independent_audit_01', ['integration_verified']),
    ('stage178_evaluations/resource_readiness_20260924/conditional_paths_01', ['passed']),
    ('stage179_evaluations/history_prefix_20260924/independent_audit_01', ['passed']),
    ('stage179_evaluations/history_prefix_20260924/resource_independent_audit_01', ['passed']),
    ('stage180_evaluations/incremental_audit_20260924/raw_audit_01', ['passed']),
    ('stage181_evaluations/explicit_resource_deadline_20260924/qualification_01', ['passed']),
    ('stage182_evaluations/bounded_live_audit_20260924/evaluation_01', ['passed']),
    ('stage183_evaluations/fallback_evidence_20260924/qualification_01', ['passed']),
    ('stage183_evaluations/fallback_evidence_20260924/audit_edge_units_01', ['passed']),
    ('stage184_evaluations/work_window_review_20260924/review_01', ['passed']),
    ('stage185_evaluations/campaign_lifecycle_20260924/qualification_01', ['passed']),
]
COMPONENTS = {
    'contact': 'stage172_staging/reduced_contact_fast_v1.py',
    'field_snapshot': 'stage173_staging/immutable_field_snapshot_v1.py',
    'swept_clearance': 'stage174_staging/certified_sweep_v2.py',
    'xz': 'stage176_staging/lossless_record_xz_v1.py',
    'history_prefix': 'stage179_staging/lossless_history_prefix_v1.py',
    'metrics': 'stage180_staging/streaming_path_metrics_v2.py',
    'deadline_binding': 'stage181_staging/explicit_runtime_deadline_v1.py',
    'fallback_observer': 'stage183_staging/capture_fallback_systems_v1.py',
    'independent_raw_auditor': 'stage183_staging/audit_optimized_record_v2.py',
    'lifecycle_and_terminal_policy': 'stage185_staging/campaign_lifecycle_policy_v1.py',
}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def now():
    return datetime.now(timezone.utc)


def check_work_clock():
    policy.require(now() < policy.utc(policy.read(WORK)['end_utc']), 'new development outside work window')


def validate_proposal(proposal, original):
    policy.require(proposal['mode'] == 'preparation_only' and proposal['launch_authorized'] is False,
                   'handoff is preparation, not launch authority')
    policy.require(proposal['cases'] == original['cases'], 'six original cases/order/specs/step ceilings unchanged')
    policy.require(proposal['numerical_gates'] == original['numerical_gates'] == policy.GATES,
                   'all numerical/event gates unchanged')
    policy.require(proposal['budget'] == original['budget'], 'no altered step ceilings, margin, workers or reserve')
    policy.require(proposal['simulation_cutoff_utc'] == '2026-09-25T18:59:00+00:00' and
                   proposal['final_audit_deadline_utc'] == '2026-09-25T22:59:00+00:00', 'revised approved deadline')
    policy.require((policy.utc(proposal['final_audit_deadline_utc']) -
                    policy.utc(proposal['simulation_cutoff_utc'])).total_seconds() == 4 * 3600,
                   'four final audit hours kept separate')
    policy.require(proposal['fresh_start_required'] is True and proposal['old_checkpoint_reuse_allowed'] is False,
                   'no migration/restart of failed or conditional paths')
    policy.require(proposal['full_path_qualified'] is False and proposal['population_release_estimate'] is None and
                   proposal['empirical_validation'] is False, 'no unsupported scientific claims')
    policy.require(proposal['new_trajectory_steps_in_current_window_allowed'] == 0,
                   'no more trajectory tests this work window')


def admission(proposal, current_utc, free_bytes, integrated_preflight, actual_stack_sha):
    """A future launcher may consult this; a pass STILL is not launch authority.

    Explicitly disallows the current work window. Requires a new, hash-bound
    integrated-stack preflight, not the old Stage167 or bounded Stage182 test.
    """
    blockers = []
    if policy.utc(current_utc) < policy.utc(proposal['work_window_end_utc']):
        blockers.append('current_window_prohibits_campaign')
    if proposal['mode'] == 'preparation_only' or proposal['launch_authorized'] is not True:
        blockers.append('preparation_is_not_execution_authority')
    if not integrated_preflight:
        blockers.append('new_integrated_parallel_preflight_missing')
    else:
        for key in ('passed', 'fresh_and_contact_identity', 'exact_restart', 'all_six_bindings',
                    'raw_audit_v2', 'cutoff_and_failure_drain', 'late_history_storage',
                    'independent_audit_passed'):
            if integrated_preflight.get(key) is not True:
                blockers.append('preflight_' + key)
        if integrated_preflight.get('stack_sha256') != actual_stack_sha:
            blockers.append('preflight_stack_mismatch')
        ratios = integrated_preflight.get('parallel_slowdown_ratios', [])
        if len(ratios) != 3 or any(not policy.finite(v) or v <= 0 or v > 1.3 for v in ratios):
            blockers.append('parallel_slowdown_outside_original_margin')
    hours = (policy.utc(proposal['simulation_cutoff_utc']) - policy.utc(current_utc)).total_seconds() / 3600
    if hours < proposal['resource_scenario']['hours_with_margin']:
        blockers.append('conservative_runtime_scenario_no_longer_fits')
    reserve = proposal['budget']['minimum_free_disk_bytes']
    if type(free_bytes) is not int or free_bytes - reserve < proposal['resource_scenario']['bytes_with_margin']:
        blockers.append('conservative_storage_scenario_no_longer_fits')
    return {'admissible': not blockers, 'blockers': blockers,
            'available_simulation_hours': hours, 'launch_authority_conferred': False}


def prepare():
    check_work_clock()
    started = time.perf_counter()
    policy.require(not MANIFEST.exists() and not OUT.exists(), 'new immutable handoff targets')
    original = policy.read(ORIGINAL)
    policy.require(policy.sha(ORIGINAL) == '79834baa71a68a7e9a20901763a8779481d1a620dc0f48a13bca3fe884b1de84',
                   'original six-case frozen design')
    ledger, resource = policy.read(LEDGER), policy.read(RESOURCE)
    policy.require(ledger['work_window_total_steps'] == 249675 and ledger['new_trajectory_steps'] == 0,
                   'unchanged work ledger')
    verified = {}
    details = []
    byte_count = 0

    def verify_path(path, expected=None):
        nonlocal byte_count
        p = Path(path).resolve()
        key = str(p)
        stat = p.stat()
        fingerprint = (stat.st_size, stat.st_mtime_ns)
        if key in verified:
            item = verified[key]
            policy.require(tuple(item['fingerprint']) == fingerprint, 'evidence changed during audit')
            digest = item['sha256']
        else:
            digest = policy.sha(p)
            after = p.stat()
            policy.require(fingerprint == (after.st_size, after.st_mtime_ns), 'unstable input file')
            verified[key] = {'sha256': digest, 'fingerprint': fingerprint}
            byte_count += stat.st_size
        if expected is not None:
            policy.require(digest == expected, 'hash drift: ' + key)
        return digest

    # Audit named terminal result seals, their directly declared sources, inputs
    # and artifact maps, and their frozen design maps. No claim of re-integrating
    # or redoing every physical calculation is made by this hash inventory.
    for folder_name, predicates in EVIDENCE:
        check_work_clock()
        folder = ROOT / folder_name
        report, seal = folder / 'results.json', folder / 'completion.json'
        r, s = policy.read(report), policy.read(seal)
        verify_path(report, s['results_sha256']); verify_path(seal)
        policy.require(all(r.get(k) is True for k in predicates), 'named numerical prerequisites: ' + folder_name)
        count_before = len(verified)
        for source in (r,):
            for field in ('sources', 'inputs', 'artifacts', 'raw_artifacts'):
                mapping = source.get(field, {})
                if isinstance(mapping, dict):
                    for path, digest in mapping.items():
                        if isinstance(digest, str) and len(digest) == 64:
                            verify_path(path, digest)
        details.append({'result': str(report), 'result_sha256': verify_path(report),
                        'required_true_fields': predicates, 'new_files_hashed': len(verified) - count_before})
    # Every local design participating in the qualified stack is read and its
    # explicit source/input mappings are rehashed once, with shared paths deduped.
    design_counts = {}
    for stage in range(172, 186):
        folder = ROOT / f'stage{stage}_designs'
        count = 0
        if folder.is_dir():
            for path in folder.rglob('*.json'):
                document = policy.read(path)
                if not isinstance(document, dict):
                    continue
                verify_path(path)
                for key in ('sources', 'inputs'):
                    for source, digest in document.get(key, {}).items():
                        policy.require(isinstance(digest, str) and len(digest) == 64, 'explicit SHA mapping')
                        verify_path(source, digest)
                count += 1
        design_counts[str(stage)] = count
    components = {name: {'path': str(ROOT / path), 'sha256': verify_path(ROOT / path)} for name, path in COMPONENTS.items()}
    proposal = {
        'stage': 'Stage186 immutable next-run handoff, not execution', 'mode': 'preparation_only',
        'launch_authorized': False, 'prepared_utc': now().isoformat(),
        'original_design': {'path': str(ORIGINAL), 'sha256': verify_path(ORIGINAL)},
        'work_window_end_utc': policy.read(WORK)['end_utc'],
        'simulation_cutoff_utc': '2026-09-25T18:59:00+00:00',
        'final_audit_deadline_utc': '2026-09-25T22:59:00+00:00',
        'cases': copy.deepcopy(original['cases']), 'numerical_gates': copy.deepcopy(original['numerical_gates']),
        'budget': copy.deepcopy(original['budget']), 'components': components,
        'fresh_start_required': True, 'old_checkpoint_reuse_allowed': False,
        'new_trajectory_steps_in_current_window_allowed': 0,
        'full_path_qualified': False, 'population_release_estimate': None, 'empirical_validation': False,
        'resource_scenario': {'hours_with_margin': resource['time_hours_with_margin'],
                              'bytes_with_margin': resource['storage_bytes_with_margin'],
                              'source_sha256': verify_path(RESOURCE),
                              'hard_bound_or_completion_guarantee': False},
        'production_integration_still_required': [
            'New launcher: fixed six-case order, fresh starts, three BLAS1 producers and fair independent auditor; never call old run commands.',
            'Record fallback observer output in every new record; use audit_optimized_record_v2, not Stage182 kernel v1.',
            'Bind deadline adapter to 25 September cutoff; keep work cutoff and final audit deadline separate.',
            'Check stop/disk before every bounded call with safe resource reserve; drain already sealed records after producer stop.',
            'Persist raw failure/zero-step evidence before classifying it incomplete; never retry to hide rejection or discard an accepted prefix.',
            'Wire independent raw prefix decoding/receipt ancestry, exact horizon/export replay and final six-case inventory.',
            'Use Stage180 v2 full-clock metrics and Stage185 original terminal/dwell gates; no conditional-prefix promotion.',
            'Qualify the entire new stack once with bounded serial/parallel identity, exact restart, failure/cutoff/drain and refreshed cost checks before launch.'
        ],
        'claim': 'Two labelled placements, fixed sand and one-way stationary flow. Conditional verification is not full-path accuracy, population release or empirical validation.',
    }
    validate_proposal(proposal, original)
    source_maps = {str(Path(__file__).resolve()): verify_path(Path(__file__).resolve()),
                   str(Path(policy.__file__)): verify_path(Path(policy.__file__))}
    proposal['preparation_sources'] = source_maps
    stack_sha = hashlib.sha256(json.dumps(components, sort_keys=True).encode()).hexdigest()
    proposal['qualified_component_map_sha256'] = stack_sha
    free = shutil.disk_usage(ROOT).free
    hold = admission(proposal, now().isoformat(), free, None, stack_sha)
    policy.require(not hold['admissible'] and 'new_integrated_parallel_preflight_missing' in hold['blockers'],
                   'no premature launch eligibility')
    tests = []
    def reject(name, edit):
        bad = copy.deepcopy(proposal); edit(bad)
        try:
            validate_proposal(bad, original)
        except ValueError:
            tests.append(name)
        else:
            raise AssertionError('accepted changed handoff: ' + name)
    reject('reorder', lambda p: p['cases'].reverse())
    reject('omit_case', lambda p: p['cases'].pop())
    reject('short_horizon', lambda p: p['cases'][0]['spec'].update(horizon_s=.1))
    reject('coarse_dt', lambda p: p['cases'][0]['spec']['config']['numerics'].update(max_dt_s=.1))
    reject('relaxed_gate', lambda p: p['numerical_gates'].update(endpoint_q_over_U_max=.01))
    reject('old_deadline', lambda p: p.update(simulation_cutoff_utc='2026-09-24T18:59:00+00:00'))
    reject('lost_audit_reserve', lambda p: p.update(final_audit_deadline_utc='2026-09-25T20:59:00+00:00'))
    reject('checkpoint_reuse', lambda p: p.update(old_checkpoint_reuse_allowed=True))
    reject('production_authority', lambda p: p.update(launch_authorized=True))
    reject('new_steps', lambda p: p.update(new_trajectory_steps_in_current_window_allowed=325))
    reject('false_qualification', lambda p: p.update(full_path_qualified=True))
    reject('false_population_claim', lambda p: p.update(population_release_estimate=0.))
    # Admission sensitivity is tested on a hypothetical FUTURE execution contract
    # in memory, never written as an authorized protocol or used to launch.
    hypothetical = copy.deepcopy(proposal); hypothetical.update(mode='future_test_fixture', launch_authorized=True)
    preflight = {key: True for key in ('passed', 'fresh_and_contact_identity', 'exact_restart', 'all_six_bindings',
                 'raw_audit_v2', 'cutoff_and_failure_drain', 'late_history_storage', 'independent_audit_passed')}
    preflight.update(stack_sha256=stack_sha, parallel_slowdown_ratios=[1.1, 1.2, 1.3])
    when = '2026-09-24T03:00:00Z'
    policy.require(admission(hypothetical, when, free, preflight, stack_sha)['admissible'], 'synthetic future admission control')
    for key in ('passed', 'fresh_and_contact_identity', 'exact_restart', 'all_six_bindings', 'raw_audit_v2',
                'cutoff_and_failure_drain', 'late_history_storage', 'independent_audit_passed'):
        bad = {**preflight, key: False}
        policy.require(not admission(hypothetical, when, free, bad, stack_sha)['admissible'], 'missing preflight gate ' + key)
        tests.append('admission_' + key)
    for label, at, disk, trial in [
        ('current_work_window', '2026-09-24T01:00:00Z', free, preflight),
        ('deadline_infeasible', '2026-09-25T12:00:00Z', free, preflight),
        ('disk_insufficient', when, 21474836480, preflight),
        ('wrong_stack', when, free, {**preflight, 'stack_sha256': '0'*64}),
        ('slowdown', when, free, {**preflight, 'parallel_slowdown_ratios': [1.1, 1.2, 1.30001]}),
        ('nan_slowdown', when, free, {**preflight, 'parallel_slowdown_ratios': [1., 1., float('nan')]}),
    ]:
        policy.require(not admission(hypothetical, at, disk, trial, stack_sha)['admissible'], label)
        tests.append('admission_' + label)
    check_work_clock()
    for path, item in verified.items():
        stat = Path(path).stat()
        policy.require(tuple(item['fingerprint']) == (stat.st_size, stat.st_mtime_ns), 'stable evidence throughout audit')
    OUT.mkdir(parents=True, exist_ok=False)
    write(MANIFEST, proposal)
    results = {'passed': True, 'preparation_complete': True, 'production_ready': False,
               'new_trajectory_steps': 0, 'work_window_total_steps': 249675,
               'manifest_sha256': policy.sha(MANIFEST), 'manifest_path': str(MANIFEST),
               'verified_prerequisites': details, 'design_counts': design_counts,
               'verified_files': verified, 'files_hashed': len(verified), 'bytes_hashed': byte_count,
               'proposal_and_admission_guards': tests, 'current_launch_hold': hold,
               'disk_free_bytes': free, 'wall_seconds': time.perf_counter() - started,
               'sources': source_maps, 'cutoff_utc': proposal['work_window_end_utc'],
               'claim': 'Hash/protocol/zero-step preparation audit; no new physics execution or full-path observation.'}
    write(OUT / 'results.json', results)
    write(OUT / 'completion.json', {'passed': True, 'results_sha256': policy.sha(OUT / 'results.json')})
    print('HANDOFF_PREPARED', len(verified), byte_count, len(tests), flush=True)
    print('PRODUCTION_NOT_READY', hold['blockers'], flush=True)


if __name__ == '__main__':
    if sys.argv[1:] != ['prepare']:
        raise ValueError('Only prepare is implemented; no run, worker or preflight command exists.')
    prepare()
