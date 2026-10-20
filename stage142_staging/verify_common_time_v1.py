"""Common-time verification of the numerical revision, not solver equivalence.

The preceding strict replay remains a failed qualification if its adaptive
decisions change. This separately frozen test allows changed work/retries but
retains the previously declared physical-state tolerances at common clocks.
"""
from pathlib import Path
import copy
import time
import sys
ROOT = Path(__file__).resolve().parents[1]
import verify_short_replays_v1 as short
import sphere_roundoff_candidate_v1 as revised
api, parent, engine, hot = short.api, short.parent, short.engine, short.hot
OUT = ROOT/'stage142_evaluations/sphere_roundoff_contract_20260919/common_time_01'


def main():
    pd = api.read(parent.DESIGN); parent.verify(pd)
    old = api.read(short.OUT/'results.json')
    api.require(api.sha(short.OUT/'results.json') == api.read(short.OUT/'completion.json')['results_sha256'], 'strict replay seal')
    api.verify_mapping(old['artifacts'])
    api.verify_mapping(api.read(short.OUT/'protocol.json')['sources'])
    OUT.mkdir(parents=True, exist_ok=False)
    cases = [c for c in pd['cases'] if len(set(c['spec']['config']['prolate_semiaxes_m'])) == 1]
    refs = {c['id']: parent.OUT/(c['id']+'.json') for c in cases}
    inputs = [parent.DESIGN, short.OUT/'results.json', short.OUT/'completion.json']+list(refs.values())
    d = {'question': 'Are position, orientation and velocity preserved at matched physical times after explicitly revising the geometric roundoff contract?',
         'distinction': 'Not a drop-in performance optimization. Retry/step equality is not an acceptance requirement for this separate numerical-method test. The failed strict-equivalence evidence remains unchanged.',
         'limits': pd['limits'], 'reference_cases': [c['id'] for c in cases],
         'refinement': {'factors': [1., .5, .25], 'common_horizon': api.read(refs['sphere_12_terminal'])['result']['time_s'],
                        'spatial_error_multipliers': [16, 32, 64]},
         'budget': 'Short saved-state windows, at most 64 accepted steps per window and existing 45 s cooperative budget; no longer dispatch.',
         'sources': {str(p): api.sha(p) for p in [Path(__file__), Path(revised.__file__), Path(short.__file__)]},
         'inputs': {str(p): api.sha(p) for p in inputs},
         'claim': 'Local state and endpoint verification only; no full-duration dwell convergence, fibre repair, full-path release or validation claim.'}
    api.write(OUT/'protocol.json', d)
    parent.old.prior.prior.configure(); hot.warmup()
    certificates = []; original = revised.candidate
    def checked(*args, **kwargs):
        q, h = original(*args, **kwargs)
        check = revised.independently_check(*args[:6], q, h)
        certificates.append({'passed': check, 'health': h, 'dt_s': args[4]})
        api.require(check, 'independent candidate certificate')
        return q, h
    revised.candidate = checked
    def run(label, c, target, factor=1., multiplier=64):
        spec = copy.deepcopy(c['spec']); spec['horizon_s'] = target
        spec['horizon_pv'] = target*spec['field_metadata']['pv_per_second']
        for k in api.DT_CONTROLS: spec['config']['numerics'][k] *= factor
        cp = copy.deepcopy(api.read(c['source'])['result']['checkpoint'])
        api.require(cp['state_sha256'] == api.digest(cp['state']), 'source state')
        bound = api.digest([api.sha(OUT/'protocol.json'), label])
        cp['contract'] = engine.prior.contracts.expected_contract(spec, bound)
        with hot.scope(), revised.scope(spec, multiplier):
            r, rows = engine.runtime.execute(spec, bound, checkpoint=cp, pause=cp['state']['steps']+64)
        h = engine.prior.reference.independent_health(r, spec)
        closure = abs(sum(row['dt_s'] for row in rows)-(r['time_s']-cp['state']['t'])) <= 1e-15
        ready = r['status'] == 'present_at_horizon' and r['time_s'] == target and h['passed'] and closure
        record = {'result': r, 'rows': rows, 'health': h, 'passed': ready, 'integrated_clock_closure': closure,
                  'source': c['source'], 'source_sha256': api.sha(c['source']), 'spec': spec, 'binding': bound,
                  'checkpoint_input_sha256': api.digest(cp), 'spatial_multiplier': multiplier, 'temporal_factor': factor}
        api.write(OUT/(label+'.json'), record, raw=True)
        print(label, ready, r['status'], len(rows), r['time_s'], flush=True)
        return record
    comparisons = []; refinements = []; starts = time.perf_counter()
    try:
        for c in cases:
            ref = api.read(refs[c['id']])['result']
            record = run('reference_'+c['id'], c, ref['time_s'])
            cmp = parent.old.prior.compare_results(ref, record['result'], c['spec'], d['limits'])
            cmp.update(case=c['id'], passed=cmp['passed'] and record['passed'],
                       original_rejected=ref['rejected'], revised_rejected=record['result']['rejected'])
            comparisons.append(cmp)
        c = next(c for c in cases if c['id'] == 'sphere_12_terminal')
        baseline = api.read(OUT/'reference_sphere_12_terminal.json')
        for factor in [.5, .25]:
            for multiplier in [16, 32, 64]:
                record = run(f'refine_{factor:g}_spatial_{multiplier}', c, d['refinement']['common_horizon'], factor, multiplier)
                cmp = parent.old.prior.compare_results(baseline['result'], record['result'], c['spec'], d['limits'])
                cmp.update(factor=factor, spatial_multiplier=multiplier, passed=cmp['passed'] and record['passed'])
                refinements.append(cmp)
    finally:
        revised.candidate = original
    api.verify_mapping(d['sources']); api.verify_mapping(d['inputs']); parent.verify(pd)
    passed = all(c['passed'] for c in comparisons+refinements+certificates)
    result = {'passed': passed, 'common_time_reference_comparisons': comparisons, 'common_time_refinement': refinements,
        'contact_certificates': certificates, 'prior_strict_replay_passed': old['passed'], 'wall_s': time.perf_counter()-starts,
        'claim': d['claim'], 'long_trajectory_authorized': False,
        'artifacts': {str(p): api.sha(p) for p in OUT.iterdir() if p.is_file()}}
    api.write(OUT/'results.json', result, raw=True)
    api.write(OUT/'completion.json', {'results_sha256': api.sha(OUT/'results.json'), 'protocol_sha256': api.sha(OUT/'protocol.json')})
    print('COMMON_TIME_PASS', passed, flush=True)


if __name__ == '__main__':
    main()
