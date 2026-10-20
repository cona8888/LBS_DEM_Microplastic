"""Bounded alternate residual representation of the unchanged held equations.

The min normal complementarity residual has the same zero set as the old
Fischer-Burmeister residual. Positivity bounds constrain numerical search only;
every candidate must pass the unchanged original finalizer and physical audit.
No gap alteration, trajectory or production installation occurs here.
"""
from pathlib import Path
import os, time, traceback
import numpy as np
from scipy.optimize import least_squares
import authenticate_failed_system_v1 as source
import probe_exact_gap_modes_v1 as old_modes
job, api, ROOT, frozen = source.job, source.api, source.ROOT, source.frozen
OUT = ROOT / 'stage210_evaluations/three_contact_failure_20261001/min_complementarity_01'


def equations(v, M, J, g, dt, mu):
    A = J @ M @ J.T; z = J @ v; vs = max(np.linalg.norm(v), 1e-15)
    steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max() for k in range(len(g))])
    scales = np.repeat(steps, 3); scales[::3] = A.diagonal()[::3]
    H = A / scales[None, :]; zv = z/vs; gap = g/dt/vs; eye = np.eye(len(z))
    def both(y):
        vc = zv + H @ y; r = np.empty(len(y)); jac = np.empty_like(H)
        for k in range(len(g)):
            i = 3*k; vn = vc[i] + gap[k]
            if y[i] < vn: r[i] = y[i]; jac[i] = eye[i]
            else: r[i] = vn; jac[i] = H[i]
            x = y[i+1:i+3] - vc[i+1:i+3]; radius = mu*y[i]*steps[k]/scales[i]; speed = np.linalg.norm(x)
            dx = eye[i+1:i+3] - H[i+1:i+3]
            if radius <= 0: r[i+1:i+3] = y[i+1:i+3]; jac[i+1:i+3] = eye[i+1:i+3]
            elif speed <= radius: r[i+1:i+3] = vc[i+1:i+3]; jac[i+1:i+3] = H[i+1:i+3]
            else:
                direction = x/speed; dr = mu*steps[k]/scales[i]*eye[i]
                r[i+1:i+3] = y[i+1:i+3] - radius*direction
                jac[i+1:i+3] = eye[i+1:i+3] - np.outer(direction, dr) - radius/speed*(np.eye(2)-np.outer(direction, direction))@dx
        return r, jac
    return both, A, z, steps, scales, vs


def run():
    d = api.read(job.DESIGN); job.verify(d); fp = source.OUT/'failed_systems.json'; proofpath = source.OUT/'results.json'
    proof = api.read(proofpath)
    api.require(api.read(proofpath.parent/'completion.json')['results_sha256'] == api.sha(proofpath) and api.sha(fp) == proof['failed_systems_sha256'], 'authentication seal')
    held = ROOT/'stage210_evaluations/three_contact_failure_20261001/held_diagnosis_01/results.json'
    inputs = {str(p): api.sha(p) for p in (Path(__file__), source.WORK, job.DESIGN, fp, proofpath, held, Path(old_modes.mixed.tests.independent.__file__))}
    OUT.mkdir(parents=True, exist_ok=False); end = time.time()+900
    job.commit(OUT/'launch.json', dict(pid=os.getpid(), utc=job.utc().isoformat(), inputs=inputs, new_trajectory_steps=0, maximum_wall_seconds=900, maximum_systems=3, maximum_seeds_per_system=40, maximum_nfev_per_seed=3000))
    reports = []
    try:
        with job.parent.fix.scope():
            for index, item in enumerate(api.read(fp)['failed_inner_systems'][:3]):
                s = item['system']; api.require(api.digest(s) == item['system_sha256'], 'held system unchanged')
                v, M, J, g = [np.asarray(s[k], float) for k in ('vfree', 'mobility', 'jacobian', 'gaps_m')]
                dt, mu = s['dt_s'], s['friction']; both, A, z, steps, scales, vs = equations(v, M, J, g, dt, mu)
                seeds = []
                for c in api.read(held)['systems'][index]['finalizer_candidates']:
                    if np.all(np.asarray(c['force'])[::3] > 0): seeds.append(np.asarray(c['force'])*scales/vs)
                rng = np.random.default_rng(210)
                for scale in (.1, 1., 10., 100.):
                    for radius in (0., .5, 1., 1.5):
                        y = np.zeros(9); y[::3] = rng.uniform(.2, 2., 3)*scale
                        for k in range(3):
                            direction = rng.normal(size=2); direction /= np.linalg.norm(direction)
                            y[3*k+1:3*k+3] = direction*radius*mu*y[3*k]*steps[k]/scales[3*k]
                        seeds.append(y)
                lower = np.full(9, -np.inf); lower[::3] = 0.; upper = np.full(9, np.inf)
                candidates = []
                for seed_index, seed in enumerate(seeds):
                    api.require(time.time() < end, 'bounded algebraic deadline')
                    opt = least_squares(lambda y: both(y)[0], seed, jac=lambda y: both(y)[1], bounds=(lower, upper),
                                        method='trf', xtol=1e-14, ftol=1e-14, gtol=1e-14, max_nfev=3000, x_scale='jac')
                    f = opt.x*vs/scales
                    row = dict(seed_index=seed_index, nfev=int(opt.nfev), cost=float(opt.cost), force=f.tolist(), original_residual=float(job.fast.gate._residual(f,z,A,g,dt,mu,steps)/vs))
                    try:
                        answer = job.fast.gate._finish(v,M,J,f,z,A,g,dt,mu,steps,int(opt.nfev),'stage210_held_min_complementarity',dict(original_gaps_preserved=True))
                        audit, saved = old_modes.mixed.tests.audit(old_modes.mixed.tests.args(s), answer)
                    except RuntimeError as error: row.update(passed=False, error=str(error))
                    else: row.update(passed=True, audit=audit, saved_system=saved)
                    candidates.append(row)
                    if row['passed']: break
                report = dict(index=index, system_sha256=item['system_sha256'], passed=any(c['passed'] for c in candidates), candidates=candidates)
                reports.append(report); job.commit(OUT/('system_%02d.json'%index), report)
                print('MIN_COMPLEMENTARITY', index, report['passed'], len(candidates), min(c['original_residual'] for c in candidates), flush=True)
        api.verify_mapping(inputs); job.verify(d)
        result = dict(new_trajectory_steps=0, inputs=inputs, original_gates_unchanged=True, reports=reports, passed=all(r['passed'] for r in reports),
                      claim='Held equation search only. Equivalent normal complementarity representation and unchanged final/independent gates; not a production repair or trajectory qualification.')
        job.commit(OUT/'results.json', result); job.commit(OUT/'completion.json', dict(results_sha256=api.sha(OUT/'results.json'), new_trajectory_steps=0))
    except Exception as error:
        job.commit(OUT/'failure.json', dict(error=repr(error), traceback=traceback.format_exc(), new_trajectory_steps=0)); raise


if __name__ == '__main__': run()
