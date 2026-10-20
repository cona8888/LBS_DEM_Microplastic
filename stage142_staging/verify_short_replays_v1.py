"""Small CPU-only checkpoint and endpoint verification, no long dispatch."""
from pathlib import Path
import copy
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
import probe_signed_gap_systems_v1 as probe
import sphere_roundoff_candidate_v1 as revised
import verify_roundoff_candidate_v1 as primitive
import progress_guard_v1 as guard
api, parent, engine, hot = probe.api, probe.parent, probe.engine, probe.hot
np = api.np
OUT = ROOT/'stage142_evaluations/sphere_roundoff_contract_20260919/replay_01'


def main():
    pd = api.read(parent.DESIGN); parent.verify(pd)
    qualified = api.read(primitive.OUT/'results.json')
    api.require(qualified['passed'] and api.read(primitive.OUT/'completion.json')['results_sha256'] == api.sha(primitive.OUT/'results.json'), 'primitive qualification')
    pp = api.read(primitive.OUT/'protocol.json'); api.verify_mapping(pp['sources']); api.verify_mapping(pp['inputs'])
    OUT.mkdir(parents=True, exist_ok=False)
    protocol = {'question': 'Does the sphere-only numerical roundoff contract preserve successful replays, pass three short timestep levels, restart exactly, and finish the saved endpoints without a clock snap?',
        'acceptance': {'inherited_seven_case_tolerances': pd['limits'], 'refinement_local_drift_over_b': 1e-8, 'restart_exact_state': True,
                       'all_endpoint_times_exactly_1_3_s': True, 'all_candidate_certificates_independently_checked': True},
        'sources': {str(p): api.sha(p) for p in [Path(__file__), Path(revised.__file__), Path(guard.__file__)]},
        'inputs': {str(p): api.sha(p) for p in [parent.DESIGN, parent.OUT/'results.json', primitive.OUT/'results.json', primitive.OUT/'completion.json', primitive.OUT/'protocol.json', probe.OUT/'results.json']},
        'budget': 'At most eight accepted steps per local comparison, four+four restart, and two saved final remainders. Existing 45 s cooperative per-call guard. No population or full-dwell continuation.',
        'claim': 'Local implementation verification of an explicitly revised geometric error contract; not full-path convergence, retention, release, or experimental validation.'}
    api.write(OUT/'protocol.json', protocol)
    parent.old.prior.prior.configure(); hot.warmup()
    certificates = []; original = revised.candidate
    def checked(*args, **kwargs):
        q, h = original(*args, **kwargs)
        passed = revised.independently_check(*args[:6], q, h)
        certificates.append({'passed': passed, 'dt_s': args[4], 'health': h})
        api.require(passed, 'independent contact certificate')
        return q, h
    revised.candidate = checked
    pairs = []; refinements = []; endpoints = []
    def execute(label, spec, source_path, cp, bound, pause):
        cp = copy.deepcopy(cp)
        api.require(cp['state_sha256'] == api.digest(cp['state']), 'source state hash')
        cp['contract'] = engine.prior.contracts.expected_contract(spec, bound)
        before = dict(revised.work)
        with hot.scope(), revised.scope(spec):
            r, rows = engine.runtime.execute(spec, bound, checkpoint=cp, pause=pause)
        health = engine.prior.reference.independent_health(r, spec)
        api.require(r['checkpoint']['state_sha256'] == api.digest(r['checkpoint']['state']), 'output state hash')
        rec = {'source': str(source_path), 'source_sha256': api.sha(source_path), 'input_checkpoint_sha256': api.digest(cp),
            'result': r, 'rows': rows, 'health': health, 'spec': spec, 'binding': bound,
            'work': {k: revised.work[k]-before[k] for k in before}}
        api.write(OUT/(label+'.json'), rec, raw=True)
        print(label, r['status'], r['time_s'], health['passed'], rec['work'], flush=True)
        return rec
    started = time.perf_counter()
    try:
        for c in pd['cases']:
            cp = api.read(c['source'])['result']['checkpoint']; spec = c['spec']
            rec = execute('reference_replay_'+c['id'], spec, c['source'], cp, api.digest([api.sha(OUT/'protocol.json'), c['id']]), cp['state']['steps']+8)
            prior = api.read(parent.OUT/(c['id']+'.json')); r = rec['result']; ref = prior['result']
            cmp = parent.old.prior.compare_results(ref, r, spec, pd['limits'])
            same = all(r[k] == ref[k] for k in ['status', 'steps', 'rejected', 'contact_solver_retries', 'persistent_contact_observed'])
            interval = len(rec['rows']) == len(prior['rows']) == 8 and all(parent.old.prior.compare_results(a, b, spec, pd['limits'])['passed'] and a['dt_s'] == b['dt_s'] and a['active_contact_ids'] == b['active_contact_ids'] and a['supported_bearing_ids'] == b['supported_bearing_ids'] for a, b in zip(rec['rows'], prior['rows']))
            sphere = len(set(spec['config']['prolate_semiaxes_m'])) == 1
            fibre_exact = sphere or (rec['work']['calls'] == 0 and all(r[k] == ref[k] for k in ['position_m', 'orientation', 'velocity_generalized', 'time_s']))
            pairs.append({'id': c['id'], 'passed': cmp['passed'] and same and interval and fibre_exact and rec['health']['passed'],
                          'comparison': cmp, 'same_decisions': same, 'same_intervals': interval, 'non_sphere_exactly_unchanged': fibre_exact})
        c = next(c for c in pd['cases'] if c['id'] == 'sphere_12_terminal')
        cp = api.read(c['source'])['result']['checkpoint']
        for factor in [1., .5, .25]:
            spec = copy.deepcopy(c['spec'])
            for k in api.DT_CONTROLS: spec['config']['numerics'][k] *= factor
            bound = api.digest([api.sha(OUT/'protocol.json'), factor])
            whole = execute(f'factor_{factor:g}_whole', spec, c['source'], cp, bound, cp['state']['steps']+8)
            first = execute(f'factor_{factor:g}_first', spec, c['source'], cp, bound, cp['state']['steps']+4)
            split = execute(f'factor_{factor:g}_second', spec, OUT/f'factor_{factor:g}_first.json', first['result']['checkpoint'], bound, cp['state']['steps']+8)
            exact = whole['result']['checkpoint']['state'] == split['result']['checkpoint']['state']
            b = spec['config']['prolate_semiaxes_m'][1]
            drift = np.linalg.norm(np.array(whole['result']['position_m'])-np.array(cp['state']['x']))/b
            okay = exact and drift <= 1e-8 and all(r['result']['status'] == 'paused_checkpoint' and r['health']['passed'] for r in [whole, first, split])
            refinements.append({'factor': factor, 'passed': bool(okay), 'restart_exact_state': exact, 'drift_over_b': float(drift), 'time_s': whole['result']['time_s']})
        dd = api.read(probe.dwell.DESIGN); dc = next(c for c in dd['cases'] if c['factor'] == 1.)
        for segment in [2, 9]:
            source = probe.dwell.RUN/dc['id']/f'segment_{segment:02d}/record.json'
            cp = api.read(source)['result']['checkpoint']
            bound = api.digest([api.sha(OUT/'protocol.json'), 'endpoint', segment])
            rec = execute(f'endpoint_{segment:02d}', dc['spec'], source, cp, bound, cp['state']['steps']+8)
            r = rec['result']; elapsed = sum(x['dt_s'] for x in rec['rows'])
            integrated = abs((r['time_s']-cp['state']['t'])-elapsed) < 1e-15
            okay = r['status'] == 'present_at_horizon' and r['time_s'] == 1.3 and integrated and rec['health']['passed']
            endpoints.append({'segment': segment, 'passed': okay, 'accepted_steps': len(rec['rows']), 'time_s': r['time_s'], 'elapsed_from_intervals_s': elapsed, 'elapsed_closure': integrated})
    finally:
        revised.candidate = original
    guard_tests = []
    for name, args, expected in [
        ('stage140_like_stall', (1.299991786, 1.2999917864, 1.3, 2.05e-5, 'incomplete_budget'), False),
        ('useful_progress', (.78, .80, 1.3, 2.05e-5, 'incomplete_budget'), True),
        ('completed', (1.29999, 1.3, 1.3, 2.05e-5, 'present_at_horizon'), False),
        ('no_advance', (1.29, 1.29, 1.3, 2.05e-5, 'incomplete_budget'), False)]:
        decision = guard.assess(*args); guard_tests.append({'case': name, 'decision': decision, 'passed': decision['continue'] == expected})
    api.verify_mapping(protocol['sources']); api.verify_mapping(protocol['inputs']); parent.verify(pd)
    passed = all(row['passed'] for row in pairs+refinements+endpoints+certificates+guard_tests)
    result = {'passed': passed, 'reference_replays': pairs, 'short_refinements': refinements, 'endpoints': endpoints, 'guard_tests': guard_tests,
        'contact_certificates': certificates, 'wall_s': time.perf_counter()-started, 'claim': protocol['claim'], 'population_release_fraction': None,
        'fibre_acceleration_enabled': False, 'long_trajectory_authorized': False,
        'artifacts': {str(p): api.sha(p) for p in OUT.iterdir() if p.is_file()}}
    api.write(OUT/'results.json', result, raw=True)
    api.write(OUT/'completion.json', {'results_sha256': api.sha(OUT/'results.json'), 'protocol_sha256': api.sha(OUT/'protocol.json')})
    print('SHORT_REPLAYS_PASS', passed, flush=True)


if __name__ == '__main__':
    main()
