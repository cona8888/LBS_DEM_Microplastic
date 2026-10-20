"""Re-read immutable evidence, rerun impulse solves, independently integrate L1."""
import math
import numpy as np
import release_phase_probe_v1 as job


def independent_l1(a, b, start, stop, scale):
    # Accepted q is right-endpoint velocity used over its preceding time interval.
    i = j = 0; left = start; pieces = []
    while left < stop:
        right = min(a[i]['time_s'], b[j]['time_s'], stop)
        pieces.append((right-left) * float(np.linalg.norm(np.array(a[i]['velocity_generalized']) - b[j]['velocity_generalized'])) / scale)
        left = right
        if a[i]['time_s'] <= right: i += 1
        if b[j]['time_s'] <= right: j += 1
    return math.fsum(pieces) / (stop-start)


def main():
    api = job.api; d = api.read(job.DESIGN); job.verify(d); result = api.read(job.OUT / 'results.json')
    api.require(api.read(job.OUT / 'completion.json')['results_sha256'] == api.sha(job.OUT / 'results.json'), 'completion seal')
    api.verify_mapping(result['artifacts']); api.require(not (job.RUN / 'failure.json').exists(), 'no failure')
    spec, binding, cp = job.seed_setup(d); seed = job.read(job.RUN / 'seed.json')
    job.v.check(seed, cp, spec, binding)
    api.require(seed['rows'] == api.read(d['source_prefix'])['rows'][:d['entry']['steps_to_replay']], 'exact archived prefix')
    api.require(seed['result']['time_s'] == d['entry']['exact_time_s'] and seed['result']['checkpoint']['state']['steps'] == d['entry']['global_steps'], 'complete entry')
    f = job.FACTORS[-1]; spec, binding, cp = job.setup(d, f, 1., 'identity')
    normal, phase = [job.read(job.RUN / f'identity_{s}.json') for s in ['normal', 'phase']]
    for r in [normal, phase]: job.v.check(r, cp, spec, binding)
    api.require(len(normal['rows']) == 100 and normal['rows'] == phase['rows'] and normal['result']['checkpoint']['state'] == phase['result']['checkpoint']['state'], 'phase-one identity')
    spec, binding, cp = job.setup(d, f, job.PHASES[1], 'restart')
    full, first, last = [job.read(job.RUN / f'restart_{s}.json') for s in ['full', 'first', 'last']]
    job.v.check(full, cp, spec, binding); job.v.check(first, cp, spec, binding); job.v.check(last, first['result']['checkpoint'], spec, binding)
    api.require([len(r['rows']) for r in [full, first, last]] == [100, 37, 63], 'restart counts')
    api.require(full['rows'] == first['rows'] + last['rows'] and full['result']['checkpoint']['state'] == last['result']['checkpoint']['state'], 'restart equality')
    api.require(full['rows'][0]['dt_s'] == normal['rows'][0]['dt_s'] * job.PHASES[1], 'first-step phase')
    saved = job.model.original.INTEGRATE
    try:
        with job.phasejob.phase_scope(cp['state']['steps'], 1/3): raise RuntimeError('scope test')
    except RuntimeError: pass
    api.require(job.model.original.INTEGRATE is saved, 'scope restoration')
    cases = [job.joined(d, f, p) for f, p in d['case_order']]
    api.require(len(cases) == 9 and len(list(job.RUN.glob('factor_*'))) == 9, 'complete frozen case set')
    reference = cases[0]; refimp = api.read(job.OUT / 'reference_impulse.json')
    api.require(refimp['mass_at_entry'] == job.mass_at_entry(d).tolist(), 'mass normalization')
    ref_saved = api.read(job.OUT / (job.case_id(reference['factor'], reference['phase']) + '_impulses.json'))
    api.require(refimp['levels'] == [ref_saved], 'fixed reference impulse')
    job.old.parent.configure(); spec = d['base_spec']; field, data, meta = api.fields.load(spec['seed'], spec['flow_factor'], spec['cpd'])
    geometry = job.diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'], data['sand_radii_m'], meta['cell_length_m'])
    cfg = d['base_spec']['config']; U = cfg['target_mean_interstitial_velocity_m_s']; reports = []; max_l1_discrepancy = 0.
    for rec in cases:
        name = job.case_id(rec['factor'], rec['phase']); imp = api.read(job.OUT / (name + '_impulses.json'))
        api.require(job.phasejob.impulse(d, rec, field, geometry) == imp, 'fresh replay of all impulse samples')
        totals = np.array([math.fsum(s['impulse_generalized'][k] * s['overlap_s'] / s['dt_s'] for s in imp['samples']) for k in range(6)])
        api.require(np.allclose(totals, imp['total_impulse'], rtol=1e-12, atol=1e-29), 'independent impulse components')
        report = job.phasejob.case_metrics(d, rec, reference, imp, refimp)
        report['event'] = job.event(d, rec); report['checks']['local_event'] = report['event'] is not None
        report['passed'] = all(report['checks'].values()); report['exact_certificates'] = len(rec['certificates'])
        api.require(report == api.read(job.OUT / (name + '_summary.json')) and report['passed'], 'case primary checks')
        l1 = independent_l1(rec['rows'], reference['rows'], d['entry']['exact_time_s'], d['window']['horizon_s'], U)
        discrepancy = abs(l1 - report['whole_L1_over_U']); max_l1_discrepancy = max(max_l1_discrepancy, discrepancy)
        api.require(discrepancy <= 1e-12, 'independent piecewise L1')
        reports.append(report)
        print('AUDIT CASE', name, flush=True)
    api.require(reports == result['cases'], 'all reports')
    for f in job.FACTORS:
        nominal = next(r['rows'][0]['dt_s'] for r in cases if r['factor'] == f and r['phase'] == 1.)
        api.require(all(r['rows'][0]['dt_s'] == nominal * r['phase'] for r in cases if r['factor'] == f), 'phase fractions')
    mids = [r['event']['midpoint_s'] for r in reports]; spread = max(mids)-min(mids)
    limit = 4 * max(row['dt_s'] for r in cases if r['factor'] == job.FACTORS[0] for row in r['rows'])
    api.require(spread == result['event_midpoint_spread_s'] and limit == result['event_midpoint_spread_limit_s'] and spread <= limit, 'event spread')
    envelopes = {}
    for key, label, scale in [('position_m', 'position_over_b', cfg['prolate_semiaxes_m'][1]), ('orientation', 'axis_vector_norm', 1.), ('velocity_generalized', 'generalized_velocity_relative', U)]:
        groups = [[np.array(r['rows'][-1][key]) for r in cases if r['factor'] == f] for f in job.FACTORS]
        within = [max(float(np.linalg.norm(x-y)/scale) for x in group for y in group) for group in groups]
        cross = [max(float(np.linalg.norm(x-y)/scale) for x in a for y in b) for a, b in zip(groups, groups[1:])]
        expected = result['endpoint_phase_envelopes'][label]
        api.require(np.allclose(within, expected['within_level_diameters'], rtol=1e-5, atol=1e-12) and np.allclose(cross, expected['adjacent_cross_phase_envelopes'], rtol=1e-5, atol=1e-12), 'independent endpoint envelope')
        envelopes[label] = {'cross_phase_envelopes': cross, 'ratio': cross[1]/cross[0], 'contracts': cross[1] <= .8*cross[0]}
    job.verify(d)
    out = job.OUT.parent / 'independent_audit_01'; out.mkdir(exist_ok=False)
    audit = {'audit_integrity_passed': True, 'all_primary_budgets_passed': True, 'independent_envelopes': envelopes,
             'independent_L1_max_difference': max_l1_discrepancy, 'event_spread_s': spread,
             'evaluation_sha256': api.sha(job.OUT / 'results.json'), 'auditor_sha256': api.sha(__file__),
             'all_endpoint_envelopes_contract': all(r['contracts'] for r in envelopes.values()),
             'prior_failures_unchanged': True, 'production_promotion': False, 'full_window_accuracy': False}
    api.write(out / 'results.json', audit, raw=True)
    api.write(out / 'completion.json', {'results_sha256': api.sha(out / 'results.json'), 'audit_integrity_passed': True})
    print('RELEASE PHASE AUDIT PASS', audit, flush=True)


if __name__ == '__main__': main()
