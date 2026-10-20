"""Prospective local verification; preserves failed exact-gap Stage142 probe."""
from pathlib import Path
import sys
import time
import copy
ROOT = Path(__file__).resolve().parents[1]
import probe_signed_gap_systems_v1 as probe
import sphere_roundoff_candidate_v1 as revised
api, parent, engine, hot = probe.api, probe.parent, probe.engine, probe.hot
np = api.np
OUT = ROOT/'stage142_evaluations/sphere_roundoff_contract_20260919/qualification_01'


def main():
    parent.verify(api.read(parent.DESIGN))
    ev = api.read(probe.OUT/'results.json')
    api.require(api.sha(probe.OUT/'results.json') == api.read(probe.OUT/'completion.json')['results_sha256'], 'matrix seal')
    api.verify_mapping(ev['artifacts'])
    OUT.mkdir(parents=True, exist_ok=False)
    L = next(c for c in api.read(parent.DESIGN)['cases'] if c['id'] == 'sphere_12_terminal')['spec']['field_metadata']['cell_length_m']
    protocol = {'question': 'Does a declared sphere-only spatial roundoff budget resolve small-dt contact failures while retaining force, friction and energy gates?',
        'new_numerical_contract': 'Original candidate first. Otherwise allow a static sphere candidate with explicit per-contact gap perturbation <= gamma_n * cell_length, n=16,32,64. Raw gap and raw residual retained. This is NOT exact raw-gap verification.',
        'physical_changes': [], 'claim': 'Local numerical-contract verification only; no trajectory, release, retention or validation claim.',
        'acceptance': {'all_saved_matrices': True, 'independent_force_and_cone_gates': True, 'all_three_spatial_budgets': True,
                       'scaled_static_controls': True, 'outside_budget_rejected': True, 'non_sphere_untouched': True},
        'sources': {str(p): api.sha(p) for p in [Path(__file__), Path(revised.__file__), Path(probe.__file__)]},
        'inputs': {str(p): api.sha(p) for p in [probe.OUT/'results.json', probe.OUT/'completion.json', parent.DESIGN]},
        'cell_length_m': L, 'limitations': 'Local arithmetic allowance, not a rigorous accumulated trajectory error bound; exact contact mode at sub-roundoff gaps remains unresolved.'}
    api.write(OUT/'protocol.json', protocol)
    rows = []; started = time.perf_counter()
    for source in ev['rows']:
        v, M, J, g = map(np.array, source['system'][:4]); rest = source['system'][4:]
        for multiple in [16, 32, 64]:
            budget = revised.length_budget(L, multiple)
            q, h = parent.old.prior.scalar_scope._scoped(revised.candidate, v, M, J, g, *rest, gap_budget_m=budget)
            check = revised.independently_check(v, M, J, g, *rest[:2], q, h)
            rows.append({'case': source['id'], 'multiplier': multiple, 'q': q.tolist(), 'health': h, 'passed': check})
            print(source['id'], multiple, check, h['geometric_contract'], flush=True)
    toys = []; negatives = []
    J = np.array(ev['rows'][0]['system'][2]); M = np.eye(6); f = np.zeros(len(J)); f[::3] = 1.
    budget = revised.length_budget(L)
    for scale in [1e-7, 1., 1e3]:
        v = -J.T@f*scale
        for sign in [-1., 0., 1.]:
            g = np.zeros(len(J)//3); g[1] = sign*.5*budget
            q, h = revised.candidate(v, M, J, g, 1e-6, .3, 1e-10, 25000, gap_budget_m=budget)
            okay = revised.independently_check(v, M, J, g, 1e-6, .3, q, h) and np.linalg.norm(q)/np.linalg.norm(v) <= 1e-10
            toys.append({'force_scale': scale, 'gap_sign': sign, 'passed': okay, 'health': h})
    for sign in [-1., 1.]:
        g = np.zeros(len(J)//3); g[1] = sign*10*budget
        try:
            revised.candidate(-J.T@f*1e-7, M, J, g, 1e-6, .3, 1e-10, 25000, gap_budget_m=budget)
        except (ValueError, RuntimeError):
            rejected = True
        else:
            rejected = False
        negatives.append({'outside_budget_sign': sign, 'rejected': rejected})
    old = revised.fast.portfolio._solve
    fibre = next(c for c in api.read(parent.DESIGN)['cases'] if c['id'] == 'fibre_11_terminal')['spec']
    with revised.scope(fibre):
        excluded = old is revised.fast.portfolio._solve
    same_budgets = all(rows[k]['q'] == rows[k+1]['q'] == rows[k+2]['q'] for k in range(0, len(rows), 3))
    api.verify_mapping(protocol['sources']); api.verify_mapping(protocol['inputs'])
    passed = all(x['passed'] for x in rows+toys) and all(x['rejected'] for x in negatives) and excluded and same_budgets
    result = {'passed': passed, 'rows': rows, 'toys': toys, 'negative_controls': negatives, 'identical_across_spatial_budgets': same_budgets,
        'non_sphere_solver_untouched': excluded, 'wall_s': time.perf_counter()-started, 'claim': protocol['claim'],
        'requires_short_trajectory_refinement_and_restart_before_promotion': True}
    api.write(OUT/'results.json', result, raw=True)
    api.write(OUT/'completion.json', {'results_sha256': api.sha(OUT/'results.json'), 'protocol_sha256': api.sha(OUT/'protocol.json')})
    print('LOCAL_CONTRACT_PASS', passed, flush=True)


if __name__ == '__main__':
    main()
