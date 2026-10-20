"""Independent functional checks for compiled Stage53; no trajectory timing claim.

The six captured systems include three original inputs and three algebraic
gap/dt probes. The latter do not rebuild inertia or free velocity, and therefore
are deliberately not described as physical timestep refinement.
"""
import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from compiled_stage53 import CompiledStage53
import inertial_contact_multistart_lm_v1 as stage53
import inertial_contact_seeded_lm_v1 as stage50
import compiled_sor
import numba


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes():
    paths = {Path(__file__).resolve()}
    for module in list(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename:
            path = Path(filename).resolve()
            if path.is_relative_to(ROOT) and path.suffix == '.py' and 'deps' not in path.parts:
                paths.add(path)
    return {str(path): sha(path) for path in sorted(paths)}


def call(solver, args):
    try:
        velocity, health = solver(*args)
    except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
        return {'status': 'rejected', 'reason': str(exc)}
    return {'status': 'accepted', 'velocity': np.asarray(velocity).tolist(), 'health': health}


def verify_original_gate(result, args):
    if result['status'] != 'accepted':
        return None
    vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter = args
    force = np.asarray(result['health']['reactions'])
    velocity = np.asarray(result['velocity'])
    if not len(gaps):
        return bool(np.array_equal(velocity, vfree) and np.isfinite(velocity).all())
    A = jacobian @ mobility @ jacobian.T
    z = jacobian @ vfree
    steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max()
                      for k in range(len(gaps))])
    try:
        checked_velocity, health = stage50._finish(
            vfree, mobility, jacobian, force, z, A, gaps, dt, friction,
            steps, 0, 'independent_original_gate', {})
    except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError):
        return False
    return bool(np.isfinite(force).all() and np.isfinite(velocity).all()
                and np.array_equal(velocity, checked_velocity)
                and all(np.isfinite(health[k]) for k in
                        ('residual', 'force_residual', 'dissipation')))


def compare(name, args, candidate, expected=None):
    baseline = call(stage53._solve, args)
    before = candidate.stats()
    revised = call(candidate, args)
    after = candidate.stats()
    row = {'name': name, 'baseline': baseline, 'candidate': revised,
           'same_acceptance_status': baseline['status'] == revised['status'],
           'candidate_original_gate': verify_original_gate(revised, args),
           'work': {key: after[key]-before[key] for key in after}}
    if baseline['status'] == revised['status'] == 'accepted':
        v0, v1 = np.asarray(baseline['velocity']), np.asarray(revised['velocity'])
        f0 = np.asarray(baseline['health']['reactions'])
        f1 = np.asarray(revised['health']['reactions'])
        load0, load1 = args[2].T @ f0, args[2].T @ f1
        velocity_scale = max(float(np.linalg.norm(args[0])), 1e-15)
        load_scale = max(float(np.linalg.norm(load0)), 1e-30)
        row.update(velocity_difference=float(np.linalg.norm(v1-v0)),
                   relative_velocity_difference=float(np.linalg.norm(v1-v0)/velocity_scale),
                   reaction_difference=float(np.linalg.norm(f1-f0)),
                   net_generalized_load_difference=float(np.linalg.norm(load1-load0)),
                   relative_net_generalized_load_difference=float(np.linalg.norm(load1-load0)/load_scale),
                   same_solver=baseline['health']['solver'] == revised['health']['solver'],
                   same_iterations=baseline['health']['iterations'] == revised['health']['iterations'],
                   bitwise_same_velocity=bool(np.array_equal(v0, v1)),
                   bitwise_same_reactions=bool(np.array_equal(f0, f1)))
    if expected is not None:
        row['analytic_velocity_pass'] = bool(revised['status'] == 'accepted' and
            np.allclose(revised['velocity'], expected, rtol=1e-12, atol=1e-12))
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    before_hashes = source_hashes()
    warmup = compiled_sor.warmup()
    solver = CompiledStage53()
    J = np.c_[np.eye(3), np.zeros((3, 3))]
    M = np.eye(6)
    rows = []
    one_contact = [
        ('normal', [-1, 0, 0, 0, 0, 0], 0., .3, [0, 0, 0, 0, 0, 0]),
        ('frictionless_slip', [-1, .2, -.1, 0, 0, 0], 0., 0., [0, .2, -.1, 0, 0, 0]),
        ('sticking', [-1, .2, -.1, 0, 0, 0], 0., .3, [0, 0, 0, 0, 0, 0]),
        ('sliding', [-1, 1, 0, 0, 0, 0], 0., .3, [0, .7, 0, 0, 0, 0]),
        ('normal_gap', [-1, 0, 0, 0, 0, 0], .025, .3, [-.25, 0, 0, 0, 0, 0]),
        ('separating', [.2, 0, 0, 0, 0, 0], 0., .3, [.2, 0, 0, 0, 0, 0]),
        ('rest', [0, 0, 0, 0, 0, 0], 0., .3, [0, 0, 0, 0, 0, 0]),
    ]
    for name, v, gap, mu, expected in one_contact:
        prepared = (np.array(v, float), M, J, np.array([gap]), .1, mu, 1e-10, 25000)
        rows.append(compare(name, prepared, solver, expected))
    free = np.array([.2, -.1, .3, .01, .02, -.03])
    rows.append(compare('no_contact', (free, M, np.empty((0, 6)), np.empty(0),
                        .1, .3, 1e-10, 25000), solver, free))
    rows.append(compare('four_contact_rest', (np.zeros(6), M, np.tile(J, (4, 1)),
                        np.ones(4), .1, .3, 1e-10, 25000), solver, np.zeros(6)))
    inputs = {}
    for seed in (1, 2, 3):
        source = (ROOT/'stage56_runs/stage55_fibre_failure_capture_20260912/diagnostic_02'
                  /f's{seed}_prolate_ar4/failure_state.npz')
        inputs[str(source)] = sha(source)
        with np.load(source) as data:
            for factor in (1., .5):
                prepared = (data['vfree'].copy(), data['mobility'].copy(),
                            data['jacobian'].copy(), data['gaps'].copy(),
                            float(data['dt'])*factor, float(data['friction']),
                            float(data['tol']), int(data['maxiter']))
                row = compare(f'captured_seed{seed}_dt_factor{factor}', prepared, solver)
                row['algebraic_dt_factor'] = factor
                rows.append(row)
    after_hashes = source_hashes()
    common = [row for row in rows if 'relative_velocity_difference' in row]
    checks = {
        'all_analytic_velocities': all(row.get('analytic_velocity_pass', True) for row in rows),
        'all_accepted_candidates_pass_original_gate': all(row['candidate_original_gate'] is not False for row in rows),
        'no_reference_pass_became_rejection': all(not (row['baseline']['status'] == 'accepted'
            and row['candidate']['status'] != 'accepted') for row in rows),
        'common_accepted_velocity_agreement_1e8_relative': all(row['relative_velocity_difference'] <= 1e-8 for row in common),
        'common_accepted_net_load_agreement_1e8_relative': all(row['relative_net_generalized_load_difference'] <= 1e-8 for row in common),
        'source_files_unchanged': before_hashes == after_hashes,
    }
    result = {'passed': all(checks.values()), 'checks': checks, 'rows': rows,
              'accepted_candidate_count': sum(row['candidate']['status'] == 'accepted' for row in rows),
              'same_status_count': sum(row['same_acceptance_status'] for row in rows),
              'work': solver.stats(), 'compile_or_cache_warmup_s': warmup,
              'timestamp_utc': datetime.now(timezone.utc).isoformat(),
              'environment': {'python': platform.python_version(), 'numpy': np.__version__,
                              'scipy': scipy.__version__, 'numba': numba.__version__},
              'source_hashes': before_hashes, 'source_hashes_after': after_hashes,
              'input_hashes': inputs,
              'claim_boundary': 'Primitive and captured algebraic systems only. Changed reactions, solver paths or outcomes require trajectory qualification. No physical timestep convergence or performance claim.'}
    path = output/'results.json'
    path.write_text(json.dumps(result, indent=2))
    (output/'completion.json').write_text(json.dumps({'status': 'complete_passed' if result['passed']
        else 'complete_failed', 'results_sha256': sha(path)}, indent=2))
    print(json.dumps({'passed': result['passed'], 'checks': checks,
                      'accepted_candidate_count': result['accepted_candidate_count'],
                      'same_status_count': result['same_status_count']}, indent=2))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
