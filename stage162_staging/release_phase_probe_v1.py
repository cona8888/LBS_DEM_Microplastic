"""Bounded contact-loss phase diagnostic; no production controller change."""
import copy
import datetime
import os
from pathlib import Path
import sys
import traceback
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage161_staging'))
import phase_grid_probe_v1 as phasejob

v, api, old = phasejob.v, phasejob.api, phasejob.old
model, engine, fix, diag = phasejob.model, phasejob.engine, phasejob.fix, phasejob.diag
BASE = 'contact_release_phase_probe_20260922'
DESIGN = ROOT / 'stage162_designs' / BASE / 'design_01.json'
RUN = ROOT / 'stage162_runs' / BASE / 'run_01'
OUT = ROOT / 'stage162_evaluations' / BASE / 'evaluation_01'
FACTORS = [.0625, .03125, .015625]
PHASES = [1., 1/3, 2/3]


def prepare():
    phasejob.verify(api.read(phasejob.DESIGN))
    v.verify(api.read(v.DESIGN))
    inputs = {str(p): api.sha(p) for p in [phasejob.DESIGN, v.DESIGN]}
    for folder in [phasejob.OUT, phasejob.OUT.parent / 'independent_audit_01']:
        result = api.read(folder / 'results.json')
        api.require(api.read(folder / 'completion.json')['results_sha256'] == api.sha(folder / 'results.json'), 'prior completion seal')
        api.require(result.get('diagnostic_integrity_passed', result.get('audit_integrity_passed')), 'prior integrity')
        for p in [folder / 'results.json', folder / 'completion.json']:
            inputs[str(p)] = api.sha(p)
    prior = api.read(v.DESIGN)
    window = copy.deepcopy(prior['windows'][1])
    srcp, nextp = [v.source_path(window, window[k]) for k in ['source_segment', 'next_segment']]
    src, nxt = api.read(srcp), api.read(nextp)
    api.require(src['checks']['passed'] and src['result']['status'] in ['paused_checkpoint', 'incomplete_budget'], 'healthy source')
    count = sum(r['time_s'] <= window['entry_cutoff_s'] for r in nxt['rows'])
    api.require(count == 910 and nxt['rows'][count-1]['time_s'] == prior['entries'][1]['exact_time_s'], 'frozen release entry')
    for p in [srcp, nextp]:
        seal = p.with_suffix('.seal.json')
        api.require(api.read(seal)['record_sha256'] == api.sha(p), 'archived source seal')
        inputs[str(p)], inputs[str(seal)] = api.sha(p), api.sha(seal)
    entry_steps = src['result']['checkpoint']['state']['steps'] + count
    order = [[FACTORS[-1], 1.]] + [[f, p] for f in FACTORS for p in PHASES if [f, p] != [FACTORS[-1], 1.]]
    d = {
        'stage': 'Stage162', 'question': 'Does the local contact-loss window meet unchanged absolute budgets across three sampled time-grid phases?',
        'window': window, 'entry': {'steps_to_replay': count, 'global_steps': entry_steps, 'exact_time_s': prior['entries'][1]['exact_time_s']},
        'source_segment': str(srcp), 'source_prefix': str(nextp), 'seed_source': str(RUN / 'seed.json'),
        'base_spec': prior['base_spec'], 'factors': FACTORS, 'first_step_fractions': PHASES, 'case_order': order,
        'reference': {'factor': FACTORS[-1], 'first_step_fraction': 1., 'selection': 'Fixed prospectively; finest unshifted case is executed first.'},
        'accuracy': {'limits': prior['accuracy']['limits'], 'error_reduction_ratio_max': .8, 'noise_floor': 1e-10},
        'velocity_L1_and_impulse_limit_over_U': .005,
        'local_event_persistence_s': .0001, 'event_midpoint_spread_coarse_steps': 4.,
        'method': 'New checkpoint from exact replay of a healthy archived prefix. Same complete entry state and clock for nine new runs. Only first-step fraction and three frozen timestep factors vary; no projection, time alignment, state reset or physical parameter changes. Stage158 exact arithmetic certificate is opt-in.',
        'primary_checks': ['Exact 910-row seed replay; fraction-one identity over 100 steps; fraction-1/3 exact 100 versus 37+63 restart.',
                           'All case health, provenance, clocks and no-new-rejection gates pass. All absolute pose, endpoint velocity, mean L1 velocity and impulse budgets to the fixed reference pass.',
                           'Recorded q replay error and discrete momentum/work residuals <=1e-8. Fixed impulse window fully covered.',
                           'Grain-2 supported-bearing indicator becomes absent for 100 microseconds in every case; all midpoint spread <=4 coarsest nominal steps.'],
        'diagnostic_not_acceptance': 'Report all phases and adjacent cross-phase endpoint envelopes, with the original 0.8 contraction test. No favorable-phase selection. This diagnostic does not retroactively change prior failed verdicts or qualify full-window accuracy.',
        'scope': 'Conditional local contact-reaction loss, not outlet escape, population release fraction, physical validation or a production adaptive controller. Indicator timing is sample-bracketed, not an exact continuous separation time; 100-us local persistence is not the previous 1-ms claim.',
        'budget': {'new_cases': 9, 'max_calls_per_case': 3, 'step_cap': 2500, 'seed_calls': 1, 'preflight_calls': 5,
                   'max_replays_per_new_case': 1800, 'workers': 1, 'threads': 1, 'cooperative_seconds_per_call': 45., 'estimated_integration_minutes': [3, 7]},
        'stop': 'Stop first primary scientific, numerical, integrity or resource failure. Preserve evidence, no retries or extra levels.',
        'phase_generated_source_digest': api.digest(phasejob.compile_phase(entry_steps, 1.)[1]),
        'inputs': inputs,
        'sources': {str(Path(m.__file__).resolve()): api.sha(m.__file__) for m in list(sys.modules.values()) if getattr(m, '__file__', None) and Path(m.__file__).suffix == '.py' and ROOT in Path(m.__file__).resolve().parents},
        'production_promotion': False, 'physical_changes': []}
    auditor = Path(__file__).with_name('audit_release_phase_probe_v1.py')
    d['sources'][str(auditor)] = api.sha(auditor)
    d['binding'] = api.digest(d)
    DESIGN.parent.mkdir(parents=True, exist_ok=True)
    api.write(DESIGN, d)
    print('FROZEN', api.sha(DESIGN), 'entry', d['entry'], flush=True)


def verify(d):
    api.require(d['binding'] == api.digest({k: x for k, x in d.items() if k != 'binding'}), 'design binding')
    api.verify_mapping(d['inputs']); api.verify_mapping(d['sources'])
    phasejob.verify(api.read(phasejob.DESIGN)); v.verify(api.read(v.DESIGN))
    api.require(d['factors'] == FACTORS and d['first_step_fractions'] == PHASES, 'selections')
    api.require(api.digest(phasejob.compile_phase(d['entry']['global_steps'], 1.)[1]) == d['phase_generated_source_digest'], 'generated integrator')


def read(p):
    api.require(api.read(p.with_suffix('.seal.json')) == {'record_sha256': api.sha(p), 'design_sha256': api.sha(DESIGN)}, 'record seal')
    return api.read(p)


def seed_setup(d):
    src = api.read(d['source_segment']); spec = copy.deepcopy(src['spec'])
    binding = api.digest([d['binding'], 'seed'])
    return spec, binding, model.checkpoint(spec, binding, src['result']['checkpoint'], True)


def setup(d, f, phase, purpose='campaign'):
    seed = read(Path(d['seed_source']))['result']['checkpoint']
    spec = copy.deepcopy(d['base_spec'])
    spec['horizon_s'] = d['window']['horizon_s']
    spec['horizon_pv'] = spec['horizon_s'] * spec['field_metadata']['pv_per_second']
    for k in api.DT_CONTROLS: spec['config']['numerics'][k] *= f
    binding = api.digest([d['binding'], f, phase, purpose])
    return spec, binding, model.checkpoint(spec, binding, seed, True)


def execute(d, spec, binding, cp, path, steps, phase=None):
    before = copy.deepcopy(cp); calls = len(model.calls); certs = len(fix.telemetry)
    scope = old.parent.prior.candidate.scope(True) if phase is None else phasejob.phase_scope(d['entry']['global_steps'], phase)
    with old.hot.scope(), scope, fix.scope():
        result, rows = engine.runtime.execute(spec, binding, checkpoint=cp, pause=cp['state']['steps'] + steps)
    r = {'result': result, 'rows': rows, 'spec': spec, 'input_checkpoint_sha256': api.digest(before),
         'effective_binding': model.binding_for(binding, True), 'design_sha256': api.sha(DESIGN),
         'backend_calls': copy.deepcopy(model.calls[calls:]), 'certificates': copy.deepcopy(fix.telemetry[certs:]),
         'step_cap': steps, 'first_step_fraction': phase}
    r['checks'] = old.parent.prior.s.check_record(r, before, spec, r['effective_binding'])
    api.write(path, r, raw=True)
    api.write(path.with_suffix('.seal.json'), {'record_sha256': api.sha(path), 'design_sha256': api.sha(DESIGN)})
    v.check(r, before, spec, binding)
    print(path.relative_to(RUN), result['status'], len(rows), 't=', result['time_s'], 'certs=', len(r['certificates']), flush=True)
    return r


def prepare_seed(d):
    spec, binding, cp = seed_setup(d)
    r = execute(d, spec, binding, cp, RUN / 'seed.json', d['entry']['steps_to_replay'])
    expected = api.read(d['source_prefix'])['rows'][:d['entry']['steps_to_replay']]
    api.require(r['rows'] == expected and r['result']['time_s'] == d['entry']['exact_time_s'], 'exact healthy prefix')
    api.require(r['result']['checkpoint']['state']['steps'] == d['entry']['global_steps'], 'global entry step')
    api.require(d['window']['grain_id'] in r['rows'][-1]['supported_bearing_ids'], 'initial bearing contact')


def preflight(d):
    f = FACTORS[-1]; spec, binding, cp = setup(d, f, 1., 'identity')
    normal = execute(d, spec, binding, cp, RUN / 'identity_normal.json', 100)
    phase = execute(d, spec, binding, cp, RUN / 'identity_phase.json', 100, 1.)
    api.require(normal['rows'] == phase['rows'] and normal['result']['checkpoint']['state'] == phase['result']['checkpoint']['state'], 'fraction-one identity')
    spec, binding, cp = setup(d, f, PHASES[1], 'restart')
    full = execute(d, spec, binding, cp, RUN / 'restart_full.json', 100, PHASES[1])
    first = execute(d, spec, binding, cp, RUN / 'restart_first.json', 37, PHASES[1])
    last = execute(d, spec, binding, first['result']['checkpoint'], RUN / 'restart_last.json', 63, PHASES[1])
    api.require(full['rows'] == first['rows'] + last['rows'] and full['result']['checkpoint']['state'] == last['result']['checkpoint']['state'], 'exact phase restart')
    api.require(full['rows'][0]['dt_s'] == normal['rows'][0]['dt_s'] * PHASES[1], 'initial phase fraction')


def case_id(f, phase): return phasejob.case_id(f, phase)


def joined(d, f, phase):
    spec, binding, cp = setup(d, f, phase)
    paths = sorted((RUN / case_id(f, phase)).glob('segment_[0-9][0-9].json'))
    api.require(0 < len(paths) <= d['budget']['max_calls_per_case'], 'bounded segments')
    rows, certs = [], []; cost = 0.
    for n, p in enumerate(paths, 1):
        api.require(p.name == f'segment_{n:02d}.json', 'segment order')
        r = read(p); v.check(r, cp, spec, binding)
        api.require(r['first_step_fraction'] == phase, 'phase binding')
        api.require(n == len(paths) or r['result']['status'] in ['paused_checkpoint', 'incomplete_budget'], 'no post-completion execution')
        rows += r['rows']; certs += r['certificates']; cost += r['result']['runtime_seconds']; cp = r['result']['checkpoint']
    api.require(r['result']['status'] == 'present_at_horizon', 'complete case')
    return {'result': r['result'], 'rows': rows, 'spec': spec, 'cost_s': cost, 'factor': f, 'phase': phase, 'certificates': certs}


def mass_at_entry(d):
    seed = read(Path(d['seed_source']))['result']['checkpoint']['state']; cfg = d['base_spec']['config']
    a, b, _ = cfg['prolate_semiaxes_m']
    mass, _ = diag.backend.generalized_mass_matrix(np.array(seed['p']), a, b, cfg['particle_density_kg_m3'], cfg['fluid_density_kg_m3'], cfg['added_mass_fraction'])
    return mass


def event(d, rec):
    seed = read(Path(d['seed_source'])); w = d['window']
    return old.event(rec['rows'], seed['rows'][-1]['supported_bearing_ids'], seed['result']['time_s'], w['grain_id'], w['after_present'], d['local_event_persistence_s'])


def run():
    d = api.read(DESIGN); verify(d)
    RUN.mkdir(parents=True, exist_ok=False); OUT.mkdir(parents=True, exist_ok=False)
    api.write(RUN / 'launch.json', {'pid': os.getpid(), 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'design_sha256': api.sha(DESIGN), 'python': sys.version})
    old.parent.configure(); prepare_seed(d); preflight(d)
    spec = d['base_spec']; field, data, meta = api.fields.load(spec['seed'], spec['flow_factor'], spec['cpd'])
    geometry = diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'], data['sand_radii_m'], meta['cell_length_m'])
    reports, cases = [], []; reference = None
    for f, phase in d['case_order']:
        folder = RUN / case_id(f, phase); folder.mkdir(exist_ok=False)
        spec, binding, cp = setup(d, f, phase)
        for n in range(1, d['budget']['max_calls_per_case'] + 1):
            r = execute(d, spec, binding, cp, folder / f'segment_{n:02d}.json', d['budget']['step_cap'], phase)
            if r['result']['status'] == 'present_at_horizon': break
            cp = r['result']['checkpoint']
        api.require(r['result']['status'] == 'present_at_horizon', 'case budget exhausted')
        rec = joined(d, f, phase); imp = phasejob.impulse(d, rec, field, geometry)
        if reference is None:
            api.require(f == FACTORS[-1] and phase == 1., 'fixed reference first')
            reference = rec
            reference_imp = {'mass_at_entry': mass_at_entry(d).tolist(), 'levels': [imp]}
            api.write(OUT / 'reference_impulse.json', reference_imp, raw=True)
        report = phasejob.case_metrics(d, rec, reference, imp, reference_imp)
        report['event'] = event(d, rec)
        report['checks']['local_event'] = report['event'] is not None
        report['passed'] = all(report['checks'].values())
        report['exact_certificates'] = len(rec['certificates'])
        api.write(OUT / (case_id(f, phase) + '_impulses.json'), imp, raw=True)
        api.write(OUT / (case_id(f, phase) + '_summary.json'), report, raw=True)
        api.require(report['passed'], 'primary local release accuracy/event gate failed')
        reports.append(report); cases.append(rec)
        print('CASE PASS', f, phase, 'L1=', report['whole_L1_over_U'], 'impulse=', report['impulse_error_over_U'], flush=True)
    for f in FACTORS:
        nominal = next(r['rows'][0]['dt_s'] for r in cases if r['factor'] == f and r['phase'] == 1.)
        api.require(all(r['rows'][0]['dt_s'] == nominal * r['phase'] for r in cases if r['factor'] == f), 'phase grid clocks')
    mids = [r['event']['midpoint_s'] for r in reports]
    spread = max(mids) - min(mids)
    spread_limit = d['event_midpoint_spread_coarse_steps'] * max(row['dt_s'] for r in cases if r['factor'] == FACTORS[0] for row in r['rows'])
    env = phasejob.envelopes(d, cases)
    result = {'stage': 'Stage162', 'diagnostic_integrity_passed': spread <= spread_limit, 'cases': reports,
              'event_midpoint_spread_s': spread, 'event_midpoint_spread_limit_s': spread_limit,
              'endpoint_phase_envelopes': env, 'all_endpoint_envelopes_contract': all(x['envelope_reduction_0p8'] for x in env.values()),
              'all_original_absolute_budgets_passed': True, 'production_promotion': False, 'full_window_accuracy': False,
              'prior_failures_unchanged': True, 'claim': d['scope'], 'design_sha256': api.sha(DESIGN),
              'artifacts': {str(p): api.sha(p) for folder in [RUN, OUT] for p in folder.rglob('*') if p.is_file()}}
    api.write(OUT / 'results.json', result, raw=True)
    api.require(spread <= spread_limit, 'local event midpoint spread')
    verify(d)
    api.write(OUT / 'completion.json', {'results_sha256': api.sha(OUT / 'results.json'), 'diagnostic_integrity_passed': True})
    print('RELEASE PHASE DIAGNOSTIC COMPLETE', env, flush=True)


if __name__ == '__main__':
    owned = False
    try:
        if sys.argv[1:] == ['prepare']: prepare()
        elif sys.argv[1:] == ['run']:
            api.require(not RUN.exists() and not OUT.exists(), 'immutable output exists'); owned = True; run()
        else: raise ValueError('Use prepare or run')
    except Exception as e:
        if owned and RUN.exists() and not (RUN / 'failure.json').exists():
            api.write(RUN / 'failure.json', {'error': repr(e), 'traceback': traceback.format_exc()})
        raise
