"""Bounded held-equation diagnostics; no trajectory or production installation."""
from pathlib import Path
import os, time, traceback
import numpy as np
import authenticate_failed_system_v1 as source
frozen, job, api, ROOT = source.frozen, source.job, source.api, source.ROOT
solver = frozen.stack.repair.prior.algebra.job.early.analytic if False else None
import semismooth_rejected_seed_v1 as analytic
OUT = ROOT / 'stage210_evaluations/three_contact_failure_20261001/held_diagnosis_01'


def run():
    d = api.read(job.DESIGN); job.verify(d); w = api.read(source.WORK)
    proofpath = source.OUT / 'results.json'; proof = api.read(proofpath)
    api.require(api.read(proofpath.parent / 'completion.json')['results_sha256'] == api.sha(proofpath), 'authentication seal')
    fp = source.OUT / 'failed_systems.json'
    api.require(proof['evidence_authentication_passed'] and not proof['numerical_gate_passed'] and api.sha(fp) == proof['failed_systems_sha256'], 'authenticated failure binding')
    systems = api.read(fp)['failed_inner_systems'][:3]
    inputs = {str(p): api.sha(p) for p in (source.WORK, job.DESIGN, Path(__file__), Path(analytic.__file__), fp, proofpath)}
    OUT.mkdir(parents=True, exist_ok=False)
    end = time.time() + 900
    job.commit(OUT / 'launch.json', dict(pid=os.getpid(), utc=job.utc().isoformat(), argv=__import__('sys').argv, inputs=inputs, new_trajectory_steps=0, maximum_held_systems=3, maximum_wall_seconds=900))
    reports = []
    try:
        with job.parent.fix.scope():
            gate = job.fast.gate
            api.require(gate is analytic.gate, 'same original finalizer module')
            finish = gate._finish
            for item in systems:
                api.require(time.time() < end, 'bounded held-equation clock')
                s = item['system']; api.require(api.digest(s) == item['system_sha256'], 'exact held input')
                v, M, J, g = [np.asarray(s[k], float) for k in ('vfree', 'mobility', 'jacobian', 'gaps_m')]
                dt, mu = s['dt_s'], s['friction']; observed = []; candidates = []
                def observe(*values):
                    vv, MM, JJ, f, z, A, gg, dtt, friction, steps, it, name, extra = values
                    f = np.asarray(f, float)
                    row = dict(solver=name, force=f.tolist(), original_residual=float(gate._residual(f, z, A, gg, dtt, friction, steps) / max(np.linalg.norm(vv), 1e-15)))
                    try:
                        answer = finish(*values)
                    except RuntimeError as error:
                        row.update(accepted=False, error=str(error)); candidates.append(values); raise
                    else:
                        row.update(accepted=True, velocity=answer[0].tolist(), health=answer[1]); return answer
                    finally: observed.append(row)
                gate._finish = observe
                try:
                    try:
                        velocity, health = analytic.solve(v, M, J, g, dt, mu, s['tolerance'], s['maxiter'], end)
                        baseline = dict(accepted=True, velocity=velocity.tolist(), health=health)
                    except (RuntimeError, ValueError, np.linalg.LinAlgError, FloatingPointError) as error:
                        baseline = dict(accepted=False, error=repr(error))
                finally: gate._finish = finish
                retractions = []
                for index, values in enumerate(candidates):
                    vv, MM, JJ, f, z, A, gg, dtt, friction, steps, it, name, extra = values
                    f = np.asarray(f, float); projected = f.copy()
                    if np.any(f[::3] < 0) or not np.isfinite(f).all(): continue
                    for k in range(len(gg)):
                        i = 3*k; radius = friction*f[i]; length = np.linalg.norm(f[i+1:i+3])
                        if length > radius: projected[i+1:i+3] *= radius/length
                    delta = float(np.linalg.norm(projected-f) / max(np.linalg.norm(f), 1e-30))
                    if not 0 < delta <= 1e-10: continue
                    row = dict(candidate_index=index, original_solver=name, relative_force_retraction=delta, projected_force=projected.tolist())
                    try:
                        velocity, health = finish(vv, MM, JJ, projected, z, A, gg, dtt, friction, steps, it, name, dict(extra, held_diagnostic_projection=True))
                    except RuntimeError as error: row.update(accepted=False, error=str(error))
                    else: row.update(accepted=True, velocity=velocity.tolist(), health=health)
                    retractions.append(row)
                row = dict(system_sha256=item['system_sha256'], dt_s=dt, baseline=baseline, finalizer_candidates=observed, bounded_force_retractions=retractions,
                           rank=int(np.linalg.matrix_rank(J)), singular_values=np.linalg.svd(J, compute_uv=False).tolist(), mobility_condition=float(np.linalg.cond(M)))
                reports.append(row); job.commit(OUT / ('system_%02d.json' % (len(reports)-1)), row)
                print('HELD', len(reports)-1, 'baseline', baseline['accepted'], 'projected_passes', sum(x['accepted'] for x in retractions), 'candidates', len(observed), flush=True)
        api.verify_mapping(inputs); job.verify(d)
        result = dict(new_trajectory_steps=0, inputs=inputs, systems=reports, original_gates_unchanged=True,
                      claim='Held three-contact equations only. Projection is a diagnostic candidate and only the original finalizer can accept. No installed repair, qualification or production pass.')
        job.commit(OUT / 'results.json', result); job.commit(OUT / 'completion.json', dict(results_sha256=api.sha(OUT / 'results.json'), new_trajectory_steps=0))
    except Exception as error:
        job.commit(OUT / 'failure.json', dict(error=repr(error), traceback=traceback.format_exc(), new_trajectory_steps=0)); raise


if __name__ == '__main__': run()
