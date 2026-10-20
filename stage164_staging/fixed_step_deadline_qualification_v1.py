"""Bounded full-window qualification of the unchanged uniform/modal fallback.

No Stage163 controller is imported or enabled. Three prospectively fixed levels
are compared on the original Stage155 clocks, using Stage158's qualified
arithmetic certificate. This is a finite-level conditional accuracy check, not
an asymptotic convergence proof or a fresh population-release simulation.
"""
from pathlib import Path
import copy
import datetime
import os
import sys
import time
import traceback
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage159_staging'))
import local_impact_refinement_v1 as prior
api, old, job, model, engine, diag, fix = (prior.api, prior.old, prior.job,
                                        prior.model, prior.engine, prior.diag, prior.fix)
BASE = 'fixed_step_deadline_qualification_20260922'
DESIGN = ROOT / 'stage164_designs' / BASE / 'design_01.json'
RUN = ROOT / 'stage164_runs' / BASE / 'run_01'
OUT = ROOT / 'stage164_evaluations' / BASE / 'evaluation_01'
AUDIT = OUT.parent / 'independent_audit_01'
FACTORS = [.125, .0625, .03125]
START = None


def sealed_input(folder, inputs):
    r, c = folder / 'results.json', folder / 'completion.json'
    api.require(api.read(c)['results_sha256'] == api.sha(r), 'upstream evidence seal')
    for p in [r, c]:
        inputs[str(p)] = api.sha(p)


def prepare():
    prior.verified.verify(api.read(prior.verified.DESIGN))
    parent = api.read(job.DESIGN)
    job.verify(parent)
    inputs = {}
    folders = [prior.verified.OUT, prior.verified.OUT.parent / 'independent_audit_01',
        ROOT / 'stage160_evaluations/endpoint_phase_diagnosis_20260922/independent_audit_01',
        ROOT / 'stage161_evaluations/contact_grid_phase_probe_20260922/independent_audit_01',
        ROOT / 'stage162_evaluations/contact_release_phase_probe_20260922/independent_audit_01',
        ROOT / 'stage163_evaluations/state_triggered_contact_refinement_20260922/failure_audit_01',
        ROOT / 'stage163_evaluations/state_triggered_contact_refinement_20260922/failure_diagnosis_01']
    for folder in folders:
        sealed_input(folder, inputs)
    api.require(api.read(prior.verified.OUT / 'results.json')['passed'], 'arithmetic qualification')
    for w in parent['windows']:
        p = old.RUN / w['id'] / 'seed.json'
        old.read_record(p)
        for x in [p, p.with_suffix('.seal.json')]:
            inputs[str(x)] = api.sha(x)
    # Only the completed, healthy engagement case is reused. The failed old
    # release trajectory is never resumed or relabelled.
    job.read_new(parent, 0)
    for p in (job.RUN / 'engagement').glob('segment_*.json'):
        inputs[str(p)] = api.sha(p)
    d = {
        'stage': 'Stage164', 'windows': parent['windows'], 'base_spec': parent['base_spec'],
        'factors': FACTORS, 'candidate_factors': FACTORS[:-1], 'reference_factor': FACTORS[-1],
        'reused_case': {'window': 'engagement', 'factor': .125, 'source': str(job.RUN / 'engagement')},
        'physical_changes': [], 'algorithm': 'Unchanged Stage153 modal/rigid integrator; uniform scaling of all existing timestep controls; Stage158 exact roundoff certificate opt-in. No state-triggered selector.',
        'limits': parent['accuracy']['limits'], 'impulse_windows_s': parent['impulse_windows_s'],
        'event_persistence_s': api.read(old.DESIGN)['event_acceptance']['persistence_s'],
        'event_timing_limit_candidate_steps': 4.,
        'acceptance': [
            'All six levels completed at their common original endpoints; all health, clock, hash, restart and no-new-rejection gates pass.',
            'Each candidate is judged against the finest reference in BOTH windows: whole interpolated pose <=1e-4 b/axis, endpoint q <=0.005 U, exact whole-clock piecewise mean velocity L1 <=0.005 U, each fixed contact impulse <=0.005 U-equivalent.',
            'Original 1-ms sustained bearing-indicator event present in all levels. Candidate versus finest midpoint shift <=4 candidate maximum accepted timesteps. No event-time alignment.',
            'Choose the largest timestep factor meeting every candidate gate in both windows, provided the finer candidate 0.0625 also meets every gate. The reference cannot certify itself.',
            'Report all adjacent differences. Strict monotonic adjacent endpoint ratios are diagnostic, not gates, following sealed Stage160-162 phase evidence. Absolute tolerances are unchanged.'
        ],
        'claim': 'Conditional finite-level solution verification of two full 25/30-ms development windows only. No uniform instantaneous impact-velocity, asymptotic order, fresh full trajectory, empirical validation, population release, or production accuracy claim.',
        'deadline': {'local': '2026-09-23T23:59:00+01:00', 'utc': '2026-09-23T22:59:00+00:00',
                     'audit_reserve_hours': 4, 'campaign': 'Freeze affordable paired sphere/fibre scope only after qualification and measured runtime. No promise of the original 180 trajectories.'},
        'budget': {'new_cases': 5, 'reused_cases': 1, 'step_cap': 2500,
                   'max_calls_per_case': 60, 'max_steps_per_case': 120000,
                   'max_new_steps_total': 330600, 'max_impulse_replays_per_window': 3600,
                   'cooperative_seconds_per_call': 45., 'workflow_wall_seconds': 7200.,
                   'threads': 1, 'workers': 1, 'restart_test_steps': [100, 37, 63]},
        'stop': 'Runtime/integrity/budget failure stops immediately and preserves all evidence. Finish the frozen three-level comparisons before selecting a factor; do not add levels or relax caps if neither candidate passes.',
        'sources': {str(Path(m.__file__).resolve()): api.sha(m.__file__)
                    for m in list(sys.modules.values()) if getattr(m, '__file__', None)
                    and Path(m.__file__).suffix == '.py' and ROOT in Path(m.__file__).resolve().parents},
        'inputs': inputs, 'prior_failures_unchanged': True, 'production_promotion': False,
    }
    d['binding'] = api.digest(d)
    DESIGN.parent.mkdir(parents=True, exist_ok=True)
    api.write(DESIGN, d)
    print('FROZEN', api.sha(DESIGN), flush=True)


def verify(d):
    api.require(d['binding'] == api.digest({k: v for k, v in d.items() if k != 'binding'}), 'design digest')
    api.verify_mapping(d['sources']); api.verify_mapping(d['inputs'])
    prior.verified.verify(api.read(prior.verified.DESIGN))
    api.require(d['factors'] == FACTORS and d['windows'] == api.read(job.DESIGN)['windows'], 'frozen cases')
    api.require(d['limits'] == api.read(job.DESIGN)['accuracy']['limits'], 'unchanged absolute limits')
    api.require(not any('state_triggered_dt' in k for k in sys.modules), 'rejected controller must not be loaded')


def budget(d):
    if START is not None:
        api.require(time.monotonic() - START <= d['budget']['workflow_wall_seconds'], 'two-hour workflow budget exhausted')


def setup(d, wi, factor, purpose='campaign'):
    w = d['windows'][wi]
    spec = copy.deepcopy(d['base_spec'])
    spec['horizon_s'] = w['horizon_s']
    spec['horizon_pv'] = w['horizon_s'] * spec['field_metadata']['pv_per_second']
    for k in api.DT_CONTROLS:
        spec['config']['numerics'][k] *= factor
    binding = api.digest([d['binding'], w['id'], factor, purpose])
    source = old.read_record(old.RUN / w['id'] / 'seed.json')['result']['checkpoint']
    return spec, binding, model.checkpoint(spec, binding, source, True)


def execute(d, spec, binding, cp, path, steps):
    budget(d)
    before = copy.deepcopy(cp); ncalls = len(model.calls); ncerts = len(fix.telemetry)
    with old.hot.scope(), old.parent.prior.candidate.scope(True), fix.scope():
        result, rows = engine.runtime.execute(spec, binding, checkpoint=cp, pause=cp['state']['steps'] + steps)
    r = {'result': result, 'rows': rows, 'spec': spec, 'input_checkpoint_sha256': api.digest(before),
         'design_sha256': api.sha(DESIGN), 'effective_binding': model.binding_for(binding, True),
         'backend_calls': copy.deepcopy(model.calls[ncalls:]), 'step_cap': steps,
         'certificates': copy.deepcopy(fix.telemetry[ncerts:])}
    r['checks'] = old.parent.prior.s.check_record(r, before, spec, r['effective_binding'])
    api.write(path, r, raw=True)
    api.write(path.with_suffix('.seal.json'), {'record_sha256': api.sha(path), 'design_sha256': api.sha(DESIGN)})
    prior.check(r, before, spec, binding)
    print(path.relative_to(RUN), result['status'], len(rows), 't=', result['time_s'], flush=True)
    return r


def read(p):
    api.require(api.read(p.with_suffix('.seal.json')) == {'record_sha256': api.sha(p), 'design_sha256': api.sha(DESIGN)}, 'record seal')
    r = api.read(p)
    api.require(r['design_sha256'] == api.sha(DESIGN), 'record design')
    return r


def restart(d, wi, create):
    spec, binding, cp = setup(d, wi, FACTORS[-1], 'restart')
    folder = RUN / d['windows'][wi]['id']
    if create:
        full = execute(d, spec, binding, cp, folder / 'restart_full.json', 100)
        first = execute(d, spec, binding, cp, folder / 'restart_first.json', 37)
        last = execute(d, spec, binding, first['result']['checkpoint'], folder / 'restart_last.json', 63)
    else:
        full, first, last = [read(folder / (name + '.json')) for name in ['restart_full', 'restart_first', 'restart_last']]
        prior.check(full, cp, spec, binding); prior.check(first, cp, spec, binding)
        prior.check(last, first['result']['checkpoint'], spec, binding)
    api.require([len(x['rows']) for x in [full, first, last]] == [100, 37, 63], 'complete restart tests')
    api.require(full['rows'] == first['rows'] + last['rows'] and full['result']['checkpoint']['state'] == last['result']['checkpoint']['state'], 'exact restart')


def joined(d, wi, factor):
    if wi == 0 and factor == .125:
        r = job.read_new(api.read(job.DESIGN), wi)
        return {**r, 'certificates': [], 'reused': True}
    spec, binding, cp = setup(d, wi, factor)
    folder = RUN / d['windows'][wi]['id'] / f'factor_{factor}'
    paths = sorted(folder.glob('segment_[0-9][0-9].json'))
    api.require(0 < len(paths) <= d['budget']['max_calls_per_case'], 'case call budget')
    rows = []; certs = []; cost = 0.
    for n, p in enumerate(paths, 1):
        api.require(p.name == f'segment_{n:02d}.json', 'contiguous segments')
        r = read(p); prior.check(r, cp, spec, binding)
        api.require(n == len(paths) or r['result']['status'] in ['paused_checkpoint', 'incomplete_budget'], 'no post-completion run')
        rows.extend(r['rows']); certs.extend(r['certificates']); cost += r['result']['runtime_seconds']
        cp = r['result']['checkpoint']
    api.require(r['result']['status'] == 'present_at_horizon' and len(rows) <= d['budget']['max_steps_per_case'], 'complete bounded case')
    api.require(old.parent.prior.w.prior.audit.clock_chain(d['windows'][wi]['seed_time_s'], rows, spec['horizon_s'])['passed'], 'joined clock')
    return {'result': r['result'], 'rows': rows, 'spec': spec, 'cost_s': cost, 'certificates': certs, 'reused': False}


def impulses(d, wi, recs, field, geometry):
    seed = old.read_record(old.RUN / d['windows'][wi]['id'] / 'seed.json')['result']['checkpoint']['state']
    cfg = d['base_spec']['config']; a, b, _ = cfg['prolate_semiaxes_m']; U = cfg['target_mean_interstitial_velocity_m_s']
    M, _ = diag.backend.generalized_mass_matrix(np.array(seed['p']), a, b, cfg['particle_density_kg_m3'], cfg['fluid_density_kg_m3'], cfg['added_mass_fraction'])
    windows = d['impulse_windows_s'][d['windows'][wi]['id']]; levels = []; calls = 0
    with old.hot.scope(), engine.runtime.repair_scope(), fix.scope():
        for factor, rec in zip(FACTORS, recs):
            samples = []; totals = [np.zeros(6) for _ in windows]
            for i, row in enumerate(rec['rows']):
                left = seed['t'] if i == 0 else rec['rows'][i-1]['time_s']
                spans = [max(0., min(row['time_s'], end) - max(left, start)) for start, end in windows]
                if not any(spans): continue
                if calls % 100 == 0: budget(d)
                prev = seed if i == 0 else {'t': left, 'x': rec['rows'][i-1]['position_m'],
                    'p': rec['rows'][i-1]['orientation'], 'q': rec['rows'][i-1]['velocity_generalized'], 'recovery': seed['recovery']}
                q, h = diag.replay(field, geometry, rec['spec'], prev, row['dt_s']); calls += 1
                api.require(calls <= d['budget']['max_impulse_replays_per_window'], 'impulse budget')
                err = float(np.linalg.norm(q-row['velocity_generalized']) / U)
                api.require(err <= 1e-8 and h['momentum_residual'] <= 1e-8 and h['work_balance_relative'] <= 1e-8, 'replay/balance')
                for k, span in enumerate(spans): totals[k] += np.array(h['impulse_generalized']) * span / row['dt_s']
                samples.append({'time_s': row['time_s'], 'dt_s': row['dt_s'], 'overlap_s': spans,
                    'replay_error_over_U': err, **{k: h[k] for k in ['impulse_generalized', 'momentum_residual', 'work_balance_relative']}})
            api.require(all(abs(sum(s['overlap_s'][k] for s in samples) - (end-start)) <= 1e-13 for k, (start, end) in enumerate(windows)), 'impulse coverage')
            levels.append({'factor': factor, 'totals': [x.tolist() for x in totals], 'samples': samples})
    return {'levels': levels, 'mass_at_entry': M.tolist(), 'U': U, 'windows_s': windows, 'calls': calls}


def summarize(d, wi, recs, imp):
    w = d['windows'][wi]; seedrec = old.read_record(old.RUN / w['id'] / 'seed.json'); seed = seedrec['result']['checkpoint']
    ref = recs[-1]; limits = d['limits']; U = d['base_spec']['config']['target_mean_interstitial_velocity_m_s']
    events = [old.observed_event(api.read(old.DESIGN), wi, r) for r in recs]
    impulse_error = lambda x, y: [float(np.linalg.norm(np.linalg.solve(np.array(imp['mass_at_entry']), np.array(a)-b))/U) for a, b in zip(x['totals'], y['totals'])]
    candidates = []
    for i, (factor, r) in enumerate(zip(FACTORS[:-1], recs[:-1])):
        endpoint = old.parent.prior.w.compare(r['result'], ref['result'], ref['spec'])
        trace = old.parent.prior.common_trace(ref['rows'], r, seed)
        l1 = diag.piecewise_l1(r['rows'], ref['rows'], seed['state']['t'], w['horizon_s'], U)['mean_norm_over_scale']
        ierr = impulse_error(imp['levels'][i], imp['levels'][-1])
        event_shift = abs(events[i]['midpoint_s']-events[-1]['midpoint_s']) if events[i] and events[-1] else None
        event_limit = d['event_timing_limit_candidate_steps'] * max(x['dt_s'] for x in r['rows'])
        checks = {'endpoint': all(endpoint[k] <= limit for k, limit in limits.items()),
                  'whole_pose': all(trace[k] <= limits[k] for k in ['position_over_b', 'axis_vector_norm']),
                  'mean_L1_velocity': l1 <= .005, 'impulses': max(ierr) <= .005,
                  'event': event_shift is not None and event_shift <= event_limit,
                  'same_verdict': all(r['result'][k] == ref['result'][k] for k in ['status', 'persistent_contact_observed', 'dwell_is_absorbing'])}
        candidates.append({'factor': factor, 'passed': all(checks.values()), 'checks': checks,
            'endpoint': endpoint, 'trace': trace, 'L1_over_U': l1, 'impulse_errors_over_U': ierr,
            'event_shift_s': event_shift, 'event_limit_s': event_limit})
    adjacent = [{'endpoint': old.parent.prior.w.compare(a['result'], b['result'], b['spec']),
                 'L1': diag.piecewise_l1(a['rows'], b['rows'], seed['state']['t'], w['horizon_s'], U)['mean_norm_over_scale'],
                 'impulse': impulse_error(imp['levels'][i], imp['levels'][i+1])} for i, (a, b) in enumerate(zip(recs, recs[1:]))]
    return {'id': w['id'], 'candidates': candidates, 'events': events, 'all_events': all(e is not None for e in events),
            'adjacent_diagnostic_only': adjacent,
            'cost': [{'factor': f, 'steps': len(r['rows']), 'runtime_s': r['cost_s'], 'reused': r['reused'],
                      'seconds_per_simulated_second': r['cost_s']/(w['horizon_s']-seed['state']['t']),
                      'exact_certificates': len(r['certificates'])} for f, r in zip(FACTORS, recs)]}


def select(reports):
    if not all(r['all_events'] and r['candidates'][-1]['passed'] for r in reports): return None
    return next((factor for i, factor in enumerate(FACTORS[:-1]) if all(r['candidates'][i]['passed'] for r in reports)), None)


def evaluate(d):
    spec = d['base_spec']; field, data, meta = api.fields.load(spec['seed'], spec['flow_factor'], spec['cpd'])
    geometry = diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'], data['sand_radii_m'], meta['cell_length_m'])
    reports = []
    for wi, w in enumerate(d['windows']):
        restart(d, wi, False)
        recs = [joined(d, wi, f) for f in FACTORS]
        imp = impulses(d, wi, recs, field, geometry)
        report = summarize(d, wi, recs, imp); reports.append(report)
        api.write(OUT / (w['id'] + '_impulses.json'), imp, raw=True)
        api.write(OUT / (w['id'] + '_summary.json'), report, raw=True)
        print('WINDOW', w['id'], [(c['factor'], c['checks']) for c in report['candidates']], flush=True)
    factor = select(reports); verify(d); budget(d)
    result = {'stage': 'Stage164', 'passed': factor is not None, 'selected_factor': factor, 'windows': reports,
        'design_sha256': api.sha(DESIGN), 'claim': d['claim'], 'production_promotion': False,
        'all_frozen_cases_completed': True, 'prior_failures_unchanged': True,
        'artifacts': {str(p): api.sha(p) for folder in [RUN, OUT] for p in folder.rglob('*') if p.is_file()}}
    api.write(OUT / 'results.json', result, raw=True)
    api.write(OUT / 'completion.json', {'results_sha256': api.sha(OUT / 'results.json'), 'passed': result['passed']})
    print('STAGE164', result['passed'], 'SELECTED', factor, flush=True)


def independent_l1(a, b, start, end, U):
    # Independent union-grid/searchsorted implementation; no shared sweep loop.
    ta = np.array([x['time_s'] for x in a]); tb = np.array([x['time_s'] for x in b])
    times = np.unique(np.r_[start, ta, tb, end]); mid = (times[1:]+times[:-1])/2
    qa = np.array([x['velocity_generalized'] for x in a])[np.searchsorted(ta, mid)]
    qb = np.array([x['velocity_generalized'] for x in b])[np.searchsorted(tb, mid)]
    return float(np.dot(np.diff(times), np.linalg.norm(qa-qb, axis=1)) / ((end-start)*U))


def audit(d):
    verify(d); budget(d); r = api.read(OUT / 'results.json')
    api.require(api.read(OUT / 'completion.json') == {'results_sha256': api.sha(OUT / 'results.json'), 'passed': r['passed']}, 'evaluation seal')
    api.verify_mapping(r['artifacts']); api.require(not (RUN / 'failure.json').exists(), 'no runtime failure')
    spec = d['base_spec']; field, data, meta = api.fields.load(spec['seed'], spec['flow_factor'], spec['cpd'])
    geometry = diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'], data['sand_radii_m'], meta['cell_length_m'])
    reports = []; independent_errors = []
    for wi, w in enumerate(d['windows']):
        restart(d, wi, False); recs = [joined(d, wi, f) for f in FACTORS]
        saved = api.read(OUT / (w['id'] + '_impulses.json'))
        api.require(impulses(d, wi, recs, field, geometry) == saved, 'independent rerun of every impulse sample')
        for level in saved['levels']:
            for k, (start, end) in enumerate(saved['windows_s']):
                total = sum((np.array(s['impulse_generalized'])*s['overlap_s'][k]/s['dt_s'] for s in level['samples']), np.zeros(6))
                api.require(np.allclose(total, level['totals'][k], rtol=1e-13, atol=1e-30), 'raw impulse sum')
                api.require(abs(sum(s['overlap_s'][k] for s in level['samples'])-(end-start)) <= 1e-13, 'independent coverage')
        report = summarize(d, wi, recs, saved); reports.append(report)
        for i, rec in enumerate(recs[:-1]):
            val = independent_l1(rec['rows'], recs[-1]['rows'], w['seed_time_s'], w['horizon_s'], saved['U'])
            difference = abs(val-report['candidates'][i]['L1_over_U']); independent_errors.append(difference)
            api.require(difference <= 1e-12, 'independent exact-clock L1')
    api.require(reports == r['windows'] and select(reports) == r['selected_factor'] and r['passed'] == (select(reports) is not None), 'raw evaluation and selection')
    new_steps = sum(c['steps'] for report in reports for c in report['cost'] if not c['reused'])+400
    api.require(new_steps <= d['budget']['max_new_steps_total'], 'global accepted-step budget')
    AUDIT.mkdir(parents=True, exist_ok=False)
    result = {'audit_integrity_passed': True, 'scientific_gates_passed': r['passed'],
        'selected_factor': r['selected_factor'], 'new_steps_including_preflight': new_steps,
        'independent_L1_max_difference': max(independent_errors), 'evaluation_sha256': api.sha(OUT / 'results.json'),
        'claim': d['claim'], 'production_promotion': False}
    api.write(AUDIT / 'results.json', result, raw=True)
    api.write(AUDIT / 'completion.json', {'results_sha256': api.sha(AUDIT / 'results.json'), 'audit_integrity_passed': True})
    print('AUDIT PASS; SCIENTIFIC', r['passed'], flush=True)


def run():
    global START
    START = time.monotonic(); d = api.read(DESIGN); verify(d)
    RUN.mkdir(parents=True, exist_ok=False); OUT.mkdir(parents=True, exist_ok=False)
    api.write(RUN / 'launch.json', {'pid': os.getpid(), 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'argv': sys.argv, 'python': sys.version, 'numpy': np.__version__, 'design_sha256': api.sha(DESIGN),
        'threads': {k: os.environ.get(k) for k in old.parent.THREADS}})
    old.parent.configure(); total = 0
    for wi, w in enumerate(d['windows']):
        folder = RUN / w['id']; folder.mkdir(exist_ok=False); restart(d, wi, True); total += 200
        for factor in FACTORS:
            if wi == 0 and factor == .125: continue
            case = folder / f'factor_{factor}'; case.mkdir(exist_ok=False)
            spec, binding, cp = setup(d, wi, factor); steps = 0
            for n in range(1, d['budget']['max_calls_per_case']+1):
                r = execute(d, spec, binding, cp, case / f'segment_{n:02d}.json', d['budget']['step_cap'])
                steps += len(r['rows']); total += len(r['rows'])
                api.require(steps <= d['budget']['max_steps_per_case'] and total <= d['budget']['max_new_steps_total'], 'accepted-step budgets')
                if r['result']['status'] == 'present_at_horizon': break
                cp = r['result']['checkpoint']
            api.require(r['result']['status'] == 'present_at_horizon', 'case-call budget exhausted')
    evaluate(d); audit(d)


if __name__ == '__main__':
    owned = False
    try:
        if sys.argv[1:] == ['prepare']: prepare()
        elif sys.argv[1:] == ['run']:
            api.require(not RUN.exists() and not OUT.exists() and not AUDIT.exists(), 'immutable destination exists')
            owned = True; run()
        elif sys.argv[1:] == ['audit']:
            old.parent.configure(); audit(api.read(DESIGN))
        else: raise ValueError('Use prepare, run, or audit')
    except Exception as exc:
        if owned and RUN.exists() and not (RUN / 'failure.json').exists():
            api.write(RUN / 'failure.json', {'error': repr(exc), 'traceback': traceback.format_exc(),
                'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()})
        raise
