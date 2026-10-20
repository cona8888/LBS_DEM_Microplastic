"""Bounded nonadvancing algebraic probes; no solver installation or trajectory."""
from pathlib import Path
import copy
import importlib.util
import os
import time
import traceback
import numpy as np
from scipy.optimize import least_squares
import inspect_failed_contact_v1 as source

job, api, ROOT = source.job, source.api, source.ROOT
OUT = ROOT / 'stage201_evaluations/contact_repair_20260928/two_contact_diagnosis_01'
spec = importlib.util.spec_from_file_location('_stage201_frozen_analytic_equations', ROOT / 'stage194_staging/probe_analytic_contact_v1.py')
analytic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analytic)


def run():
    work = api.read(source.WORK)
    stop = job.policy.utc(work['work_end_utc']).timestamp()
    api.require(time.time() < stop, 'work window')
    d = api.read(job.DESIGN); job.verify(d)
    resultpath = source.OUT / 'results.json'
    result = api.read(resultpath)
    api.require(api.read(source.OUT / 'completion.json')['results_sha256'] == api.sha(resultpath), 'source seal')
    systems_path = source.OUT / 'failed_systems.json'
    api.require(api.sha(systems_path) == result['failed_systems_sha256'], 'failed systems binding')
    systems = api.read(systems_path)['failed_inner_systems']
    api.require(len(systems) == 22, 'all failures included')
    OUT.mkdir(parents=True, exist_ok=False)
    inputs = {str(p): api.sha(p) for p in (source.WORK, Path(__file__), Path(analytic.__file__), resultpath, systems_path, job.DESIGN)}
    job.commit(OUT / 'launch.json', {'pid': os.getpid(), 'utc': job.utc().isoformat(), 'inputs': inputs, 'new_trajectory_steps': 0, 'maximum_systems': 22, 'maximum_optimizers_per_system': 8, 'maximum_nfev': 2000})
    reports = []
    try:
        with job.parent.fix.scope():
            gate = job.fast.gate
            original_finish = gate._finish
            for index, bound in enumerate(systems):
                api.require(time.time() < stop, 'work cutoff')
                s = bound['system']; api.require(api.digest(s) == bound['system_sha256'], 'system digest')
                v, M, J, g = [np.asarray(s[k], float) for k in ('vfree', 'mobility', 'jacobian', 'gaps_m')]
                api.require(J.shape == (6, 6) and len(g) == 2 and s['tolerance'] == 1e-10, 'two-contact original contract')
                dt, mu = s['dt_s'], s['friction']
                both, A, z, steps, scales, vs = analytic.system(v, M, J, g, dt, mu)
                candidates = []
                def observed_finish(vv, MM, JJ, f, zz, AA, gg, dtt, friction, ss, it, name, extra):
                    entry = {'solver': name, 'force': np.asarray(f).tolist(), 'extra': copy.deepcopy(extra), 'residual': float(gate._residual(f, zz, AA, gg, dtt, friction, ss) / max(np.linalg.norm(vv), 1e-15))}
                    try:
                        answer = original_finish(vv, MM, JJ, f, zz, AA, gg, dtt, friction, ss, it, name, extra)
                    except RuntimeError as error:
                        entry.update(accepted=False, error=str(error)); raise
                    else:
                        entry.update(accepted=True, health=answer[1]); return answer
                    finally:
                        candidates.append(entry)
                start = time.perf_counter()
                gate._finish = observed_finish
                try:
                    answer = job.parent.engine.runtime.mixed.solve(v, M, J, g, dt, mu, s['tolerance'], s['maxiter'])
                except RuntimeError as error:
                    baseline = {'accepted': False, 'error': str(error)}
                else:
                    baseline = {'accepted': True, 'velocity': answer[0].tolist(), 'health': answer[1]}
                finally:
                    gate._finish = original_finish
                seeds = [('zero', np.zeros(len(z)))]
                seeds += [('candidate_' + str(k), np.asarray(c['force']) * scales / vs) for k, c in sorted(enumerate(candidates), key=lambda item: item[1]['residual'])[:3]]
                probes = []
                for method in ('trf', 'lm'):
                    for label, seed in seeds:
                        api.require(time.time() < stop, 'work cutoff')
                        opt = least_squares(lambda y: both(y)[0], seed, jac=lambda y: both(y)[1], method=method, xtol=1e-14, ftol=1e-14, gtol=1e-14, max_nfev=2000, x_scale='jac')
                        f = opt.x * vs / scales
                        probe = {'method': method, 'seed': label, 'nfev': int(opt.nfev), 'cost': float(opt.cost), 'force': f.tolist(), 'residual': float(gate._residual(f, z, A, g, dt, mu, steps) / vs)}
                        try:
                            answer = original_finish(v, M, J, f, z, A, g, dt, mu, steps, int(opt.nfev), 'stage201_held_analytic_probe', {})
                        except RuntimeError as error:
                            probe.update(accepted=False, error=str(error))
                        else:
                            probe.update(accepted=True, velocity=answer[0].tolist(), health=answer[1])
                        probes.append(probe)
                report = {'index': index, 'input_sha256': bound['system_sha256'], 'baseline_mixed': baseline, 'baseline_candidates': candidates, 'probes': probes, 'dt_s': dt, 'gaps_m': g.tolist(), 'vfree_norm': float(np.linalg.norm(v)), 'jacobian_singular_values': np.linalg.svd(J, compute_uv=False).tolist(), 'mobility_condition': float(np.linalg.cond(M)), 'seconds': time.perf_counter()-start}
                reports.append(report)
                job.commit(OUT / ('system_%02d.json' % index), report)
                print('HELD', index, 'baseline', baseline['accepted'], 'analytic', sum(p['accepted'] for p in probes), '/', len(probes), flush=True)
        api.verify_mapping(inputs); job.verify(d)
        summary = {'new_trajectory_steps': 0, 'original_gates_unchanged': True, 'inputs': inputs, 'systems': reports, 'systems_with_accepted_analytic_candidate': sum(any(p['accepted'] for p in r['probes']) for r in reports), 'systems_total': len(reports), 'claim': 'Held-system verification only; no trajectory repair or production acceptance.'}
        job.commit(OUT / 'results.json', summary)
        job.commit(OUT / 'completion.json', {'results_sha256': api.sha(OUT / 'results.json'), 'new_trajectory_steps': 0})
        print('DIAGNOSIS_COMPLETE', summary['systems_with_accepted_analytic_candidate'], '/', len(reports), flush=True)
    except Exception as error:
        job.commit(OUT / 'failure.json', {'error': repr(error), 'traceback': traceback.format_exc(), 'new_trajectory_steps': 0, 'completed_systems': len(reports)})
        raise


if __name__ == '__main__':
    run()
