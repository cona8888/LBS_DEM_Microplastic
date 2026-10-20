"""Zero-trajectory-step diagnosis of the five preserved failed contact systems."""
from pathlib import Path
import copy
import os
import sys
import time
import traceback
import numpy as np
import qualify_failure_codec_v1 as q

job, api = q.job, q.api
INPUT = q.ROOT / 'stage194_evaluations/evidence_repair_20260924/diagnostic_replay_01'
OUT = q.ROOT / 'stage194_evaluations/evidence_repair_20260924/contact_diagnosis_01'
DESIGN = q.ROOT / 'stage194_designs/evidence_repair_20260924/contact_diagnosis_01.json'


def run():
    w = api.read(q.WORK); api.require(job.utc() < job.policy.utc(w['work_end_utc']), 'work clock')
    report = api.read(INPUT / 'results.json')
    api.require(api.read(INPUT / 'completion.json')['results_sha256'] == api.sha(INPUT / 'results.json'), 'diagnostic seal')
    api.verify_mapping(report['raw_artifacts'])
    api.require(api.sha(INPUT / 'failure_details.json') == report['failure_details_sha256'], 'failed systems binding')
    details = api.read(INPUT / 'failure_details.json')
    systems = [s for t in details['failed_outer_trials'] for s in t['inner_systems'] if not s['accepted']]
    api.require(len(systems) == 5 and report['new_accepted_steps'] == 9645, 'exact bounded diagnostic ledger')
    d = api.read(job.DESIGN); job.verify(d)
    protocol = {'stage': 'Stage194 five captured contact-system diagnosis', 'new_trajectory_steps': 0,
                'physical_changes': [], 'gates_unchanged': True, 'maximum_solve_calls': 5,
                'inputs': {str(p): api.sha(p) for p in (q.WORK, job.DESIGN, Path(__file__), INPUT / 'results.json', INPUT / 'failure_details.json')},
                'sources': d['sources'], 'question': 'Which unchanged original gate rejects reduced-mode candidates for the exact captured matrices?'}
    job.commit(DESIGN, protocol); OUT.mkdir(parents=True, exist_ok=False)
    job.commit(OUT / 'launch.json', {'pid': os.getpid(), 'utc': job.utc().isoformat(), 'design_sha256': api.sha(DESIGN), 'new_trajectory_steps': 0})
    reports = []; gate = job.fast.gate; original = gate._finish; candidates = []
    def observed_finish(v, M, J, f, z, A, g, dt, mu, steps, iterations, solver, extra):
        scale = max(np.linalg.norm(v), 1e-15); fs = max(np.linalg.norm(f), 1e-30)
        entry = {'solver': solver, 'extra': copy.deepcopy(extra), 'force': np.asarray(f).tolist(),
                 'minimum_normal_over_force_norm': float(min(f[::3]) / fs),
                 'max_cone_excess_over_force_norm': float(max(np.linalg.norm(f[3*k+1:3*k+3]) - mu * f[3*k] for k in range(len(g))) / fs),
                 'original_residual': float(gate._residual(f, z, A, g, dt, mu, steps) / scale)}
        try:
            answer = original(v, M, J, f, z, A, g, dt, mu, steps, iterations, solver, extra)
        except Exception as error:
            entry.update(accepted=False, error=repr(error)); raise
        else:
            entry.update(accepted=True, velocity=np.asarray(answer[0]).tolist(), health=answer[1]); return answer
        finally:
            candidates.append(entry)
    gate._finish = observed_finish
    try:
        for index, s in enumerate(systems):
            api.require(job.utc() < job.policy.utc(w['work_end_utc']), 'work cutoff')
            candidates = []
            v, M, J, g = [np.asarray(s[k], float) for k in ('vfree', 'mobility', 'jacobian', 'gaps_m')]
            dt = s['dt_s']; scale = max(np.linalg.norm(v), 1e-15)
            target = np.zeros(9); target[::3] = -g / dt / scale
            velocity_ls = np.linalg.lstsq(J, target, rcond=1e-12)[0]
            mismatch = J @ velocity_ls - target
            entry = {'index': index, 'input_sha256': api.digest(s), 'dt_s': dt, 'gaps_m': g.tolist(),
                     'vfree_norm': float(np.linalg.norm(v)), 'mobility_condition': float(np.linalg.cond(M)),
                     'jacobian_singular_values': np.linalg.svd(J, compute_uv=False).tolist(),
                     'all_stick_target_norm': float(np.linalg.norm(target)), 'all_stick_kinematic_mismatch_norm': float(np.linalg.norm(mismatch)),
                     'all_stick_kinematic_relative_mismatch': float(np.linalg.norm(mismatch) / max(np.linalg.norm(target), 1e-15)),
                     'all_stick_target_components': target.tolist()}
            start = time.perf_counter()
            try:
                answer = job.fast.solve(v, M, J, g, dt, s['friction'], s['tolerance'], s['maxiter'])
            except Exception as error:
                entry.update(solve_passed=False, solve_error=repr(error))
            else:
                entry.update(solve_passed=True, velocity=np.asarray(answer[0]).tolist(), health=answer[1])
            entry.update(seconds=time.perf_counter()-start, final_gate_candidates=copy.deepcopy(candidates))
            reports.append(entry); print('MATRIX_DIAGNOSED', index, entry['solve_passed'], len(candidates), flush=True)
    finally:
        gate._finish = original
    api.verify_mapping(protocol['inputs']); api.verify_mapping(protocol['sources'])
    result = {'diagnosis_complete': True, 'new_trajectory_steps': 0, 'original_gates_unchanged': True,
              'captured_systems': systems, 'systems': reports, 'protocol_sha256': api.sha(DESIGN),
              'claim': 'Nonadvancing algebraic diagnostic only, not a production repair or accepted trajectory.'}
    job.commit(OUT / 'results.json', result); job.commit(OUT / 'completion.json', {'results_sha256': api.sha(OUT / 'results.json')})
    print('CONTACT_DIAGNOSIS_COMPLETE', flush=True)


if __name__ == '__main__': run()
