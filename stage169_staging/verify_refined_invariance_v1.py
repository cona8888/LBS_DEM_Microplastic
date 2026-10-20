"""Additional fixed-pose invariance tests for the two-stick force-nullspace branch."""
from pathlib import Path
import itertools, time
import numpy as np
import verify_reduced_repair_v2 as updated

base, api, repair = updated.base, updated.api, updated.revised
OUT = base.EVAL / 'refined_invariance_01'


def main():
    design = api.read(base.DESIGN)
    base.verify(design)
    folder = updated.OLD_EVAL / 'refined_failure_capture_01'
    report = api.read(folder / 'results.json')
    seal = api.read(folder / 'completion.json')
    api.require(seal['results_sha256'] == api.sha(folder / 'results.json'), 'capture seal')
    entry = report['systems'][0]
    api.require(api.sha(entry['path']) == entry['sha256'], 'original refined system')
    system = api.read(entry['path'])
    v, M, J, g = [np.asarray(system[k]) for k in ['vfree', 'mobility', 'jacobian', 'gaps']]
    dt, mu = system['dt'], system['friction']
    cases = [(f'scale_{s}', v*s, M, J, g*s, np.eye(6), s) for s in [1., 1e-3, 1e3]]
    for permutation in itertools.permutations(range(3)):
        indices = [3*k+j for k in permutation for j in range(3)]
        cases.append((f'permutation_{permutation}', v, M, J[indices], g[list(permutation)], np.eye(6), 1.))
    for seed in [169, 170, 171]:
        R, _ = np.linalg.qr(np.random.default_rng(seed).normal(size=(3,3)))
        if np.linalg.det(R) < 0: R[:, 0] *= -1
        Q = np.zeros((6,6)); Q[:3,:3] = R; Q[3:,3:] = R
        cases.append((f'frame_{seed}', Q@v, Q@M@Q.T, J@Q.T, g, Q, 1.))
    tests, reference = [], None
    saved = base.hot.s50._residual
    base.hot.s50._residual = base.hot.scalar.residual
    try:
        with base.parent.fix.scope():
            for name, vv, mm, jj, gg, Q, scale in cases:
                started = time.perf_counter()
                try:
                    q, h = repair.solve(vv, mm, jj, gg, dt, mu, 1e-10, 25000)
                    if reference is None: reference = q.copy()
                    checks = base.independent(vv, mm, jj, gg, dt, mu, q, h)
                    error = float(np.linalg.norm(Q.T@q/scale-reference)/np.linalg.norm(v))
                    tests.append({'id': name, 'passed': checks['passed'] and error <= 1e-10,
                                  'independent': checks, 'velocity_invariance_error': error,
                                  'health': h, 'wall_s': time.perf_counter()-started})
                except Exception as error:
                    tests.append({'id': name, 'passed': False, 'error': repr(error)})
    finally:
        base.hot.s50._residual = saved
    base.verify(design)
    OUT.mkdir(exist_ok=False)
    result = {'passed': len(tests)==12 and all(x['passed'] for x in tests), 'tests': tests,
              'trajectory_steps': 0, 'claim': 'Fixed-pose tests, not trajectory or full-path qualification.',
              'input_sha256': {str(p): api.sha(p) for p in [base.DESIGN, Path(entry['path']), folder/'results.json', folder/'completion.json']},
              'source_sha256': api.sha(__file__)}
    api.write(OUT/'results.json', result, raw=True)
    api.write(OUT/'completion.json', {'passed': result['passed'], 'results_sha256': api.sha(OUT/'results.json')})
    print('REFINED INVARIANCE', result['passed'], 'TESTS', len(tests),
          'FAILED', [x['id'] for x in tests if not x['passed']], flush=True)


if __name__ == '__main__': main()
