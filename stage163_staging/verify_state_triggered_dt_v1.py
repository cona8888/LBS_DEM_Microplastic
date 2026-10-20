"""Six short conditional tests, with unchanged physical/absolute-error budgets."""
import copy
import datetime
import os
from pathlib import Path
import sys
import traceback
import numpy as np
import state_triggered_dt_v1 as control

prior = control.prior; phasejob = prior.phasejob; v = prior.v
api, old, model, engine, fix, diag = prior.api, prior.old, prior.model, prior.engine, prior.fix, prior.diag
ROOT = control.ROOT
BASE = 'state_triggered_contact_refinement_20260922'
DESIGN = ROOT / 'stage163_designs' / BASE / 'design_01.json'
RUN = ROOT / 'stage163_runs' / BASE / 'run_01'
OUT = ROOT / 'stage163_evaluations' / BASE / 'evaluation_01'
FACTORS = [1., .5, .25]


def reference(w):
    if w['id'] == 'engagement': return {**v.joined(api.read(v.DESIGN), 0, v.FACTORS[-1]), 'factor': v.FACTORS[-1], 'phase': 1.}
    return prior.joined(api.read(prior.DESIGN), prior.FACTORS[-1], 1.)


def prepare():
    prior.verify(api.read(prior.DESIGN)); phasejob.verify(api.read(phasejob.DESIGN)); v.verify(api.read(v.DESIGN))
    inputs = {}
    for folder in [prior.OUT, prior.OUT.parent / 'independent_audit_01', phasejob.OUT, phasejob.OUT.parent / 'independent_audit_01']:
        r = api.read(folder / 'results.json')
        api.require(api.read(folder / 'completion.json')['results_sha256'] == api.sha(folder / 'results.json'), 'prerequisite seal')
        api.require(r.get('diagnostic_integrity_passed', r.get('audit_integrity_passed')), 'prerequisite integrity')
        for p in [folder / 'results.json', folder / 'completion.json']: inputs[str(p)] = api.sha(p)
    windows = []
    for i, w0 in enumerate(api.read(v.DESIGN)['windows']):
        w = copy.deepcopy(w0)
        folder = v.RUN / 'engagement' if i == 0 else prior.RUN
        w['seed_source'] = str(folder / 'seed.json')
        if i == 0:
            paths = list((folder / f'factor_{v.FACTORS[-1]}').glob('segment_*.json'))
        else:
            paths = list((folder / prior.case_id(prior.FACTORS[-1], 1.)).glob('segment_*.json'))
        for p in [Path(w['seed_source']), Path(w['seed_source']).with_suffix('.seal.json'), *paths]: inputs[str(p)] = api.sha(p)
        ref = reference(w)
        w['reference_steps'] = len(ref['rows']); w['entry_s'] = api.read(w['seed_source'])['result']['time_s']
        windows.append(w)
    for p in [prior.DESIGN, phasejob.DESIGN, v.DESIGN]: inputs[str(p)] = api.sha(p)
    d = {'stage': 'Stage163', 'question': 'Can a trial-state trigger meet local accuracy budgets using fewer contact solves than uniform finest stepping?',
         'windows': windows, 'base_spec': api.read(prior.DESIGN)['base_spec'], 'coarse_factors': FACTORS,
         'fine_fraction': control.REFINE_FRACTION, 'velocity_change_trigger_over_U': control.VELOCITY_CHANGE_OVER_U,
         'accuracy': api.read(prior.DESIGN)['accuracy'], 'local_event_persistence_s': .0001,
         'primary_accuracy': 'All six candidates versus preselected finest unshifted reference: position/b <=1e-4, axis <=1e-4, endpoint q/U <=0.005, whole-window mean L1 q/U <=0.005, fixed-window impulse error <=0.005 U-equivalent. No peak-velocity sup gate. Contact indicator event persists 100us, candidate-reference midpoint difference <=4 of the larger candidate fine-cap or reference timestep (same four-step timing rule).',
         'primary_cost': 'For each window the coarse-factor-1 state-selected run uses <=75% of the reference contact-solve count, including all discarded trial solves. Runtime is reported separately, not substituted for work.',
         'method': 'First form the unchanged modal-capped trial. If its touching grain set changes or q increment exceeds 0.0025 U, discard it and re-solve from identical old state at 1/16 unclipped nominal dt, clipped to remaining horizon afterwards. Otherwise accept through unchanged gates. No event times/target grain IDs are used by controller. No tolerance, force, pose or physical-parameter modification.',
         'limitations': 'Numerical heuristic, not a local truncation-error estimator or proof over unsampled phases. Shared conditional starts inherit upstream trajectory error. Local tests do not qualify full trajectories, population escape, physical validation or production defaults.',
         'preflight': 'Unit/analytical selector checks; each window: 100-step off identity, always-fine identity to archived finest, state-mode 100 versus 37+63 restart, and synthetic pending fine trial resumes without a second reduction. Scope restoration on exception checked.',
         'budget': {'new_cases': 6, 'max_calls_per_case': 3, 'step_cap': 2500, 'preflight_calls_per_window': 7,
                    'max_replays_per_new_case': 1800, 'workers': 1, 'threads': 1, 'cooperative_seconds_per_call': 45., 'estimated_minutes': [3, 8]},
         'stop': 'Stop at first failed integrity, health, accuracy, event, cost or resource gate. No retuning, added levels or physics.',
         'inputs': inputs, 'sources': {str(Path(m.__file__).resolve()): api.sha(m.__file__) for m in list(sys.modules.values()) if getattr(m, '__file__', None) and Path(m.__file__).suffix == '.py' and ROOT in Path(m.__file__).resolve().parents},
         'generated_source_digest': api.digest(control.compile_controller('state', 1.)[1]), 'physical_changes': [], 'production_promotion': False}
    auditor = Path(__file__).with_name('audit_state_triggered_dt_v1.py'); d['sources'][str(auditor)] = api.sha(auditor)
    d['binding'] = api.digest(d); DESIGN.parent.mkdir(parents=True, exist_ok=True); api.write(DESIGN, d)
    print('FROZEN', api.sha(DESIGN), flush=True)


def verify(d):
    api.require(d['binding'] == api.digest({k: x for k, x in d.items() if k != 'binding'}), 'design binding')
    api.verify_mapping(d['inputs']); api.verify_mapping(d['sources']); prior.verify(api.read(prior.DESIGN))
    api.require(api.digest(control.compile_controller('state', 1.)[1]) == d['generated_source_digest'], 'generated source')


def setup(d, wi, factor, mode='state', purpose='campaign'):
    w = d['windows'][wi]; seed = api.read(w['seed_source'])['result']['checkpoint']; spec = copy.deepcopy(d['base_spec'])
    spec['horizon_s'] = w['horizon_s']; spec['horizon_pv'] = w['horizon_s'] * spec['field_metadata']['pv_per_second']
    for k in api.DT_CONTROLS: spec['config']['numerics'][k] *= factor
    binding = api.digest([d['binding'], wi, factor, mode, purpose])
    return spec, binding, model.checkpoint(spec, binding, seed, True)


def execute(d, spec, binding, cp, path, steps, mode):
    before = copy.deepcopy(cp); nc = len(model.calls); nf = len(fix.telemetry); nt = len(control.telemetry); nd = len(control.discarded)
    U = spec['config']['target_mean_interstitial_velocity_m_s']
    scope = old.parent.prior.candidate.scope(True) if mode == 'baseline' else control.scope(mode, U)
    with old.hot.scope(), scope, fix.scope():
        result, rows = engine.runtime.execute(spec, binding, checkpoint=cp, pause=cp['state']['steps'] + steps)
    r = {'result': result, 'rows': rows, 'spec': spec, 'mode': mode, 'step_cap': steps,
         'input_checkpoint_sha256': api.digest(before), 'effective_binding': model.binding_for(binding, True),
         'backend_calls': copy.deepcopy(model.calls[nc:]), 'certificates': copy.deepcopy(fix.telemetry[nf:]),
         'controller_steps': copy.deepcopy(control.telemetry[nt:]), 'discarded_trials': copy.deepcopy(control.discarded[nd:]), 'design_sha256': api.sha(DESIGN)}
    r['checks'] = old.parent.prior.s.check_record(r, before, spec, r['effective_binding'])
    api.write(path, r, raw=True); api.write(path.with_suffix('.seal.json'), {'record_sha256': api.sha(path), 'design_sha256': api.sha(DESIGN)})
    check(r, before, spec, binding)
    print(path.relative_to(RUN), result['status'], len(rows), 'discarded=', len(r['discarded_trials']), flush=True)
    return r


def check(r, before, spec, binding):
    v.check(r, before, spec, binding)
    if r['mode'] != 'baseline':
        api.require(len(r['controller_steps']) == len(r['rows']), 'one accepted controller record per row')
        for c, row in zip(r['controller_steps'], r['rows']):
            api.require(c['time_s'] + c['accepted_dt_s'] == row['time_s'] and c['accepted_dt_s'] == row['dt_s'], 'controller clock')
            api.require(c['accepted_dt_s'] <= c['nominal_dt_s'], 'no coarsening beyond original cap')
            api.require(c['fine_floor_dt_s'] == min(c['nominal_dt_s']/16, spec['horizon_s']-c['time_s']), 'horizon-safe fine cap')
        for p in r['discarded_trials']:
            api.require(p['decision']['refine'] and p['replacement_dt_s'] < p['discarded_dt_s'], 'declared discarded trial')


def read(p):
    api.require(api.read(p.with_suffix('.seal.json')) == {'record_sha256': api.sha(p), 'design_sha256': api.sha(DESIGN)}, 'record seal')
    return api.read(p)


def preflight(d, wi):
    folder = RUN / d['windows'][wi]['id']; folder.mkdir(exist_ok=False)
    spec, binding, cp = setup(d, wi, .25, 'off', 'identity')
    baseline = execute(d, spec, binding, cp, folder / 'identity_baseline.json', 100, 'baseline')
    off = execute(d, spec, binding, cp, folder / 'identity_off.json', 100, 'off')
    api.require(baseline['rows'] == off['rows'] and baseline['result']['checkpoint']['state'] == off['result']['checkpoint']['state'], 'default-off identity')
    spec, binding, cp = setup(d, wi, .25, 'always', 'finest_identity')
    fine = execute(d, spec, binding, cp, folder / 'always_fine_identity.json', 100, 'always')
    api.require(fine['rows'] == reference(d['windows'][wi])['rows'][:100], 'always-fine exact reference identity')
    spec, binding, cp = setup(d, wi, .25, 'state', 'restart')
    full = execute(d, spec, binding, cp, folder / 'restart_full.json', 100, 'state')
    first = execute(d, spec, binding, cp, folder / 'restart_first.json', 37, 'state')
    last = execute(d, spec, binding, first['result']['checkpoint'], folder / 'restart_last.json', 63, 'state')
    api.require(full['rows'] == first['rows'] + last['rows'] and full['result']['checkpoint']['state'] == last['result']['checkpoint']['state'], 'exact state restart')
    api.require(full['controller_steps'] == first['controller_steps'] + last['controller_steps'] and full['discarded_trials'] == first['discarded_trials'] + last['discarded_trials'], 'controller restart accounting')
    spec, binding, cp = pending_setup(d, wi)
    pending = execute(d, spec, binding, cp, folder / 'pending_fine_resume.json', 1, 'state')
    api.require(pending['rows'] == fine['rows'][:1] and not pending['discarded_trials'], 'pending fine trial is not reduced again')
    saved = model.original.INTEGRATE
    try:
        with control.scope('state', spec['config']['target_mean_interstitial_velocity_m_s']): raise RuntimeError('scope restoration test')
    except RuntimeError: pass
    api.require(model.original.INTEGRATE is saved, 'exception restores controller scope')


def pending_setup(d, wi):
    spec, binding, cp = setup(d, wi, .25, 'state', 'synthetic_pending_test')
    fine = read(RUN / d['windows'][wi]['id'] / 'always_fine_identity.json')
    cp['state']['pending_trial'] = {'time_s': cp['state']['t'], 'dt_s': fine['rows'][0]['dt_s'], 'attempt': 1}
    cp['state_sha256'] = api.digest(cp['state'])
    return spec, binding, cp


def joined(d, wi, factor):
    spec, binding, cp = setup(d, wi, factor); folder = RUN / d['windows'][wi]['id'] / f'factor_{factor}'
    paths = sorted(folder.glob('segment_[0-9][0-9].json')); rows = []; logs = []; discarded = []; cost = 0.
    api.require(0 < len(paths) <= d['budget']['max_calls_per_case'], 'segment budget')
    for n, p in enumerate(paths, 1):
        api.require(p.name == f'segment_{n:02d}.json', 'ordered segments'); r = read(p); check(r, cp, spec, binding)
        api.require(n == len(paths) or r['result']['status'] in ['paused_checkpoint', 'incomplete_budget'], 'no terminal continuation')
        api.require(r['mode'] == 'state', 'controller mode')
        rows += r['rows']; logs += r['controller_steps']; discarded += r['discarded_trials']; cost += r['result']['runtime_seconds']; cp = r['result']['checkpoint']
    api.require(r['result']['status'] == 'present_at_horizon', 'full window')
    return {'result': r['result'], 'rows': rows, 'spec': spec, 'cost_s': cost, 'factor': factor, 'phase': 1., 'controller_steps': logs, 'discarded_trials': discarded}


def metric_design(d, wi):
    w = d['windows'][wi]
    return {**d, 'window': w, 'seed_source': w['seed_source']}


def metrics(d, wi, rec, ref, imp, refimp):
    md = metric_design(d, wi); report = phasejob.case_metrics(md, rec, ref, imp, refimp)
    report.pop('first_step_fraction'); w = d['windows'][wi]; seed = api.read(w['seed_source'])
    args = [seed['rows'][-1]['supported_bearing_ids'], seed['result']['time_s'], w['grain_id'], w['after_present'], d['local_event_persistence_s']]
    event = old.event(rec['rows'], *args); revent = old.event(ref['rows'], *args)
    event_error = abs(event['midpoint_s']-revent['midpoint_s']) if event and revent else None
    event_limit = 4*max(max(r['dt_s'] for r in ref['rows']), max(c['fine_floor_dt_s'] for c in rec['controller_steps']))
    solves = len(rec['rows']) + len(rec['discarded_trials']); ratio = solves / len(ref['rows'])
    report['checks']['event'] = event_error is not None and event_error <= event_limit
    report['checks']['cost'] = rec['factor'] != 1. or ratio <= .75
    report.update(passed=all(report['checks'].values()), event=event, reference_event=revent, event_error_s=event_error, event_limit_s=event_limit,
                  accepted_steps=len(rec['rows']), discarded_solves=len(rec['discarded_trials']), contact_solves=solves, solve_ratio_to_finest=ratio,
                  fine_steps=sum(c['accepted_dt_s'] == c['fine_floor_dt_s'] for c in rec['controller_steps']), fine_factor=rec['factor']/16)
    return report


def run():
    d = api.read(DESIGN); verify(d); RUN.mkdir(parents=True, exist_ok=False); OUT.mkdir(parents=True, exist_ok=False)
    api.write(RUN / 'launch.json', {'pid': os.getpid(), 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'design_sha256': api.sha(DESIGN), 'python': sys.version})
    api.write(OUT / 'selector_selftest.json', control.selftest(), raw=True)
    old.parent.configure(); spec = d['base_spec']; field, data, meta = api.fields.load(spec['seed'], spec['flow_factor'], spec['cpd'])
    geometry = diag.core.geometry_tools.GrainGeometry(data['sand_centres_m'], data['sand_radii_m'], meta['cell_length_m'])
    reports = []
    for wi, w in enumerate(d['windows']):
        preflight(d, wi); ref = reference(w); md = metric_design(d, wi)
        reference_imp = phasejob.impulse(md, ref, field, geometry)
        seed = api.read(w['seed_source'])['result']['checkpoint']['state']; cfg = d['base_spec']['config']; a, b, _ = cfg['prolate_semiaxes_m']
        mass, _ = diag.backend.generalized_mass_matrix(np.array(seed['p']), a, b, cfg['particle_density_kg_m3'], cfg['fluid_density_kg_m3'], cfg['added_mass_fraction'])
        refimp = {'mass_at_entry': mass.tolist(), 'levels': [reference_imp]}
        api.write(OUT / (w['id']+'_reference_impulses.json'), refimp, raw=True)
        for factor in FACTORS:
            folder = RUN / w['id'] / f'factor_{factor}'; folder.mkdir(exist_ok=False); spec, binding, cp = setup(d, wi, factor)
            for n in range(1, d['budget']['max_calls_per_case']+1):
                r = execute(d, spec, binding, cp, folder / f'segment_{n:02d}.json', 2500, 'state')
                if r['result']['status'] == 'present_at_horizon': break
                cp = r['result']['checkpoint']
            api.require(r['result']['status'] == 'present_at_horizon', 'case resource budget')
            rec = joined(d, wi, factor); imp = phasejob.impulse(md, rec, field, geometry); report = metrics(d, wi, rec, ref, imp, refimp)
            report['window'] = w['id']; name = f"{w['id']}_factor_{factor}"
            api.write(OUT / (name+'_impulses.json'), imp, raw=True); api.write(OUT / (name+'_summary.json'), report, raw=True)
            print('CASE', w['id'], factor, report['checks'], 'solve ratio=', report['solve_ratio_to_finest'], flush=True)
            api.require(report['passed'], 'local controller verification gate failed')
            reports.append(report)
    verify(d)
    result = {'stage': 'Stage163', 'passed': True, 'cases': reports, 'design_sha256': api.sha(DESIGN),
              'artifacts': {str(p): api.sha(p) for folder in [RUN, OUT] for p in folder.rglob('*') if p.is_file()},
              'claim': d['limitations'], 'full_window_accuracy': False, 'production_promotion': False}
    api.write(OUT / 'results.json', result, raw=True); api.write(OUT / 'completion.json', {'results_sha256': api.sha(OUT / 'results.json'), 'passed': True})
    print('LOCAL CONTROLLER PASS', flush=True)


if __name__ == '__main__':
    owned = False
    try:
        if sys.argv[1:] == ['prepare']: prepare()
        elif sys.argv[1:] == ['run']:
            api.require(not RUN.exists() and not OUT.exists(), 'immutable destination exists'); owned = True; run()
        else: raise ValueError('Use prepare or run')
    except Exception as exc:
        if owned and RUN.exists() and not (RUN / 'failure.json').exists():
            api.write(RUN / 'failure.json', {'error': repr(exc), 'traceback': traceback.format_exc()})
        raise
