"""Read-only independent arithmetic recheck; never calls the pose replay."""
from pathlib import Path
from collections import Counter
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diagnose_inner_outer_association_v1 as prior

api = prior.api
OUT = prior.OUT.with_name('independent_audit_01')


def unmatched(record):
    available = Counter((p['dt_s'], *r['velocity_generalized'])
                        for r, p in zip(record['rows'], record['sweep_certificates']))
    failures = []
    for index, item in enumerate(record['early_attempts']):
        if item['accepted']:
            key = (item['dt_s'], *item['velocity'])
            if available[key] == 0:
                failures.append(index)
            else:
                available[key] -= 1
    return failures


def run():
    d = api.read(prior.DESIGN); prior.verify(d)
    r = api.read(prior.OUT / 'results.json')
    api.require(api.read(prior.OUT / 'completion.json')['results_sha256'] == api.sha(prior.OUT / 'results.json'), 'diagnostic seal')
    api.verify_mapping(r['artifacts'])
    a, b = api.read(prior.OUT / 'captured_finalizers.json')
    old = prior.load_payload(138)
    next_record = prior.load_payload(139)
    saved_early = old['early_attempts'][24]
    saved_final = old['rows'][2794]['velocity_generalized']
    residuals = []
    reconstructed = []
    for item in (a, b):
        v, M, J, f, q = [np.asarray(item[k], float) for k in ('vfree', 'mobility', 'jacobian', 'force', 'velocity')]
        increment = M @ J.T @ f
        reconstructed.append(np.array_equal(v + increment, q))
        # Separate 100-digit Decimal elimination of the rounded increment,
        # plus an independently rounded addition check (no production helper).
        residuals.append(prior.independent.decimal_closure(v, M, J, f, increment, q))
    delta_q = np.asarray(b['velocity']) - a['velocity']
    delta_free = np.asarray(b['vfree']) - a['vfree']
    checks = {
        'diagnostic_is_passed_and_zero_step': r['diagnosis_passed'] and r['trajectory_steps_advanced'] == 0,
        'only_original_unmatched_attempt': unmatched(old) == [24],
        'successor_has_no_same_local_mismatch': unmatched(next_record) == [],
        'exact_early_velocity': a['velocity'] == saved_early['velocity'],
        'exact_final_velocity': b['velocity'] == saved_final,
        'all_early_inputs_match': all(a[k] == saved_early[k] for k in ('vfree', 'mobility', 'jacobian', 'gaps_m', 'dt_s', 'friction')),
        'same_mobility_geometry_reactions_and_dt': all(a[k] == b[k] for k in ('mobility', 'jacobian', 'gaps_m', 'force', 'dt_s', 'friction')),
        'free_velocity_alone_explains_exact_delta': np.array_equal(delta_q, delta_free),
        'both_original_velocity_formulas_exact': all(reconstructed),
        'both_decimal_closures_pass': max(residuals) <= 1e-8,
        'later_solver_is_within_pose_reuse': b['solver'] == 'within_pose_verified_prior',
        'original_failure_not_promoted': not r['original_stage187_passed'] and not r['production_promotion'],
    }
    prior.verify(d)
    OUT.mkdir(parents=True, exist_ok=False)
    result = {'passed': all(checks.values()), 'checks': checks, 'trajectory_steps_advanced': 0,
              'decimal_force_residuals': residuals, 'exact_velocity_delta': delta_q.tolist(),
              'diagnosis_sha256': api.sha(prior.OUT / 'results.json'),
              'design_sha256': api.sha(prior.DESIGN), 'auditor_sha256': api.sha(__file__),
              'claim': 'Local cause and arithmetic independently rechecked. Neither failed segment is promoted; canonical prefix history is not reaudited.'}
    api.write(OUT / 'results.json', result, raw=True)
    api.write(OUT / 'completion.json', {'passed': result['passed'], 'results_sha256': api.sha(OUT / 'results.json')})
    print('AUDIT', checks, 'decimal', residuals, flush=True)
    api.require(result['passed'], 'independent diagnostic audit')


if __name__ == '__main__':
    run()
