"""Two prospectively selected conditional contact-transition windows.

Unchanged Stage153 rigid Euler/modal-timestep algorithm. Seed preparation uses
the unchanged quasistatic model; no claim of a fresh full inertial trajectory.
"""
from pathlib import Path
import copy
import datetime
import os
import sys
import traceback
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage154_staging'))
import longer_rotation_window_v1 as parent

api, engine, model, hot = parent.api, parent.engine, parent.model, parent.hot
BASE = 'contact_transitions_20260922'
DESIGN = ROOT / 'stage155_designs' / BASE / 'design_01.json'
RUN = ROOT / 'stage155_runs' / BASE / 'run_01'
OUT = ROOT / 'stage155_evaluations' / BASE / 'evaluation_01'
AUDIT = OUT.parent / 'independent_audit_01'
ARCHIVE = ROOT / 'stage135_runs/matched_transport_extension_20260918/pilot_01'
OLD_DESIGN = ROOT / 'stage135_designs/matched_transport_extension_20260918/design_01.json'
OLD_EVAL = ROOT / 'stage135_evaluations/matched_transport_extension_20260918/independent_evaluation_01'
FACTORS = [1., .5, .25]
LIMIT_CALLS = {'1.0': 3, '0.5': 4, '0.25': 7}
WINDOWS = [
    {'id': 'engagement', 'seed_time_s': .555, 'horizon_s': .580, 'grain_id': 3,
     'after_present': True, 'guidance_segment': 1},
    {'id': 'release', 'seed_time_s': 1.742, 'horizon_s': 1.772, 'grain_id': 2,
     'after_present': False, 'guidance_segment': 6},
]


def event(rows, initial_ids, initial_time, grain, after, persistence):
    """First sustained indicator change; return the enclosing sample bracket."""
    previous = grain in initial_ids
    bracket = None
    last_time = initial_time
    for row in rows:
        now = grain in row['supported_bearing_ids']
        if now == after and previous != after:
            bracket = [last_time, row['time_s']]
        if now != after:
            bracket = None
        if bracket is not None and row['time_s'] - bracket[1] >= persistence:
            return {'bracket_s': bracket, 'midpoint_s': sum(bracket) / 2,
                    'confirmed_through_s': row['time_s'], 'minimum_persistence_s': persistence}
        previous = now
        last_time = row['time_s']
    return None


def selftest():
    def rows(flags):
        return [{'time_s': i * .001, 'supported_bearing_ids': [3] if f else []}
                for i, f in enumerate(flags, 1)]
    assert event(rows([False, True, True, True]), [], 0., 3, True, .001)['bracket_s'] == [.001, .002]
    assert event(rows([True, False, False, False]), [3], 0., 3, False, .001)['bracket_s'] == [.001, .002]
    assert event(rows([False, True, False, True]), [], 0., 3, True, .001) is None
    assert event(rows([True, True, True]), [3], 0., 3, True, .001) is None
    assert event(rows([False, True, False, True, True, True]), [], 0., 3, True, .001)['bracket_s'] == [.003, .004]
    print('EVENT_EXTRACTOR_SELFTEST_PASS', flush=True)


def verify(d):
    api.require(d['binding'] == api.digest({k: v for k, v in d.items() if k != 'binding'}), 'design binding')
    api.verify_mapping(d['sources'])
    api.verify_mapping(d['inputs'])
    parent.verify(api.read(parent.DESIGN))
    api.require(d['windows'] == WINDOWS and d['factors'] == FACTORS, 'prospective selection')
    api.require(d['accuracy'] == api.read(parent.DESIGN)['accuracy'], 'inherited accuracy limits')


def archived_inputs():
    old = api.read(OLD_DESIGN)
    api.require(old['binding'] == api.digest({k: v for k, v in old.items() if k != 'binding'}), 'old design binding')
    api.verify_mapping(old['inputs'])
    seal = api.read(OLD_EVAL / 'completion.json')
    api.require(seal['results_sha256'] == api.sha(OLD_EVAL / 'results.json'), 'old audit seal')
    api.require(seal['run_completion_sha256'] == api.sha(ARCHIVE / 'completion.json'), 'old run seal')
    old_result = api.read(OLD_EVAL / 'results.json')
    api.require(old_result['all_health_passed'] and old_result['no_failure_or_stderr'], 'healthy archived partial trajectories')
    case = next(c for c in old['cases'] if 'fibre' in c['id'])
    api.require(case['spec']['config'] == api.read(parent.DESIGN)['base_spec']['config'], 'same physical/numerical base')
    source5 = ARCHIVE / case['id'] / 'segment_05/record.json'
    source0 = Path(case['source_record']['path'])
    paths = [OLD_DESIGN, OLD_EVAL / 'completion.json', OLD_EVAL / 'results.json', ARCHIVE / 'completion.json', source0,
             source0.parent / 'completion.json', source5, source5.parent / 'completion.json']
    ledger = next(e for e in api.read(ARCHIVE / 'completion.json')['ledger'] if e['case_id'] == case['id'])
    for n in [1, 5, 6]:
        p = ARCHIVE / case['id'] / f'segment_{n:02d}/record.json'
        r = api.read(p)
        expected = next(x['sha256'] for x in ledger['records'] if Path(x['path']) == p)
        api.require(api.sha(p) == expected == api.read(p.parent / 'completion.json')['record_sha256'], 'archive record binding')
        intervals = p.parent / 'accepted_intervals.json'
        api.require(api.sha(intervals) == r['accepted_intervals_sha256'], 'archive interval binding')
        paths += [p, p.parent / 'completion.json', intervals]
    return case, [str(source0), str(source5)], paths


def prepare():
    selftest()
    parent.verify(api.read(parent.DESIGN))
    previous = parent.sealed(parent.OUT)
    api.verify_mapping(previous['artifacts'])
    parent.sealed(parent.AUDIT)
    case, sources, paths = archived_inputs()
    guidance = []
    for window in WINDOWS:
        p = ARCHIVE / case['id'] / f"segment_{window['guidance_segment']:02d}/accepted_intervals.json"
        rows = api.read(p)
        e = event(rows, rows[0]['supported_bearing_ids'], rows[0]['time_s'], window['grain_id'], window['after_present'], .001)
        api.require(e is not None and window['seed_time_s'] < e['midpoint_s'] < window['horizon_s'], 'archived event inside prospectively selected window')
        guidance.append(e)
    paths += [parent.DESIGN, parent.OUT / 'results.json', parent.OUT / 'completion.json', parent.AUDIT / 'results.json', parent.AUDIT / 'completion.json']
    modules = {str(Path(m.__file__).resolve()): api.sha(m.__file__) for m in list(sys.modules.values())
               if getattr(m, '__file__', None) and Path(m.__file__).suffix == '.py' and ROOT in Path(m.__file__).resolve().parents}
    d = {'stage': 'Stage155', 'windows': WINDOWS, 'factors': FACTORS, 'base_spec': case['spec'],
         'seed_sources': sources, 'archived_guidance_only': guidance,
         'question': 'Does the unchanged rigid/modal algorithm resolve a supported-contact engagement and release at three timesteps?',
         'physical_or_algorithm_changes': [],
         'seed_preparation': 'Each original checkpoint is advanced with unchanged quasistatic dynamics to the fixed seed clock; the full resulting checkpoint is rebound for all rigid comparisons. Conditional initialized windows, not a fresh inertial history.',
         'observable': 'First sustained change of grain membership in supported_bearing_ids, persisting at least 1 ms. This is the existing end-point-supported reaction indicator, not an exact continuous contact time or soil export event. The observer suppresses all bearing IDs when any bearing contact lacks endpoint geometric support; active_contact_ids are search candidates.',
         'event_acceptance': {'persistence_s': .001, 'maximum_midpoint_shift_in_coarse_steps': 4.,
                              'require_every_level': True, 'require_initial_state_opposite_to_event': True},
         'accuracy': api.read(parent.DESIGN)['accuracy'],
         'primary_gates': 'All six cases complete at matched window endpoints with independent health, exact clocks, no new rejections or fallback. Both coarser whole traces and finest endpoint pair obey inherited limits, with inherited endpoint refinement trend. Each prescribed sustained event occurs at all levels; event midpoint spread is at most four maximum coarse accepted timesteps.',
         'restart': 'Before campaign execution, each prepared seed passes 100 steps versus 37+63 with identical full accepted rows and checkpoint state. Failed preflight stops all longer dispatch.',
         'budget': {'cooperative_seconds_per_call': 45., 'step_cap': 2500, 'max_seed_calls': 1,
                    'max_calls_per_factor_per_window': LIMIT_CALLS, 'maximum_campaign_and_seed_calls': 30,
                    'preflight_calls': 6, 'workers': 1, 'threads': 1,
                    'estimated_campaign_minutes': [6, 12], 'rule': 'No unbudgeted retries or horizon extensions. Healthy budget checkpoints may continue only within frozen case limits.'},
         'stop': 'A failed provenance, runtime-health, coverage, time-resolution or accuracy gate stops advancement. Preserve failures and do not change thresholds retrospectively.',
         'claim': 'Two conditional contact-indicator transition windows only. No population release fraction, permanent retention, experimental validation, full-path qualification or production promotion.',
         'sources': modules, 'inputs': {str(p): api.sha(p) for p in paths}}
    d['binding'] = api.digest(d)
    DESIGN.parent.mkdir(parents=True, exist_ok=True)
    api.write(DESIGN, d)
    print('FROZEN', api.sha(DESIGN), flush=True)


def setup(d, wi, factor, *, seed=False, preflight=False):
    w = d['windows'][wi]
    spec = copy.deepcopy(d['base_spec'])
    spec['horizon_s'] = w['seed_time_s'] if seed else w['horizon_s']
    spec['horizon_pv'] = spec['horizon_s'] * spec['field_metadata']['pv_per_second']
    for key in api.DT_CONTROLS:
        spec['config']['numerics'][key] *= factor
    source = api.read(d['seed_sources'][wi] if seed else RUN / w['id'] / 'seed.json')['result']['checkpoint']
    api.require(source['state']['pending_trial'] is None, 'no pending adaptive trial in selected source')
    binding = api.digest([d['binding'], w['id'], factor, 'seed' if seed else ('preflight' if preflight else 'campaign')])
    cp = model.checkpoint(spec, binding, source, not seed)
    return spec, binding, cp


def execute(d, spec, binding, cp, path, rigid, steps):
    before = copy.deepcopy(cp)
    calls = len(model.calls)
    scope = parent.prior.candidate.scope(True) if rigid else model.scope(False)
    with hot.scope(), scope:
        result, rows = engine.runtime.execute(spec, binding, checkpoint=cp, pause=cp['state']['steps'] + steps)
    r = {'result': result, 'rows': rows, 'spec': spec, 'rigid': rigid, 'step_cap': steps,
         'input_checkpoint_sha256': api.digest(before), 'design_sha256': api.sha(DESIGN),
         'effective_binding': model.binding_for(binding, rigid), 'backend_calls': copy.deepcopy(model.calls[calls:])}
    r['checks'] = parent.prior.s.check_record(r, before, spec, r['effective_binding'])
    api.write(path, r, raw=True)
    api.write(path.with_suffix('.seal.json'), {'record_sha256': api.sha(path), 'design_sha256': api.sha(DESIGN)})
    verify_segment(d, r, before, spec, binding, rigid)
    print(path.relative_to(RUN), result['status'], len(rows), 't=', result['time_s'], flush=True)
    return r


def verify_segment(d, r, before, spec, binding, rigid):
    api.require(r['spec'] == spec and r['rigid'] == rigid and r['design_sha256'] == api.sha(DESIGN), 'segment identity')
    effective = model.binding_for(binding, rigid)
    api.require(r['effective_binding'] == effective, 'model binding')
    api.require(parent.prior.s.check_record(r, before, spec, effective)['passed'], 'health/clock/contract')
    api.require(len(r['backend_calls']) == int(rigid) and all(x['enabled'] for x in r['backend_calls']), 'selected runtime backend')
    api.require(len(r['rows']) <= r['step_cap'], 'step cap')
    parent.segment_guard(r['result'], before, spec['horizon_s'])


def read_record(path):
    api.require(api.read(path.with_suffix('.seal.json')) == {'record_sha256': api.sha(path), 'design_sha256': api.sha(DESIGN)}, 'record seal')
    return api.read(path)


def seed_preflight(d, wi):
    folder = RUN / d['windows'][wi]['id']
    folder.mkdir(exist_ok=False)
    spec, binding, cp = setup(d, wi, 1., seed=True)
    r = execute(d, spec, binding, cp, folder / 'seed.json', False, d['budget']['step_cap'])
    api.require(r['result']['status'] == 'present_at_horizon', 'seed budget exhausted')
    w = d['windows'][wi]
    api.require((w['grain_id'] in r['rows'][-1]['supported_bearing_ids']) != w['after_present'], 'seed already in target event state')
    spec, binding, cp = setup(d, wi, 1., preflight=True)
    full = execute(d, spec, binding, cp, folder / 'preflight_full.json', True, 100)
    first = execute(d, spec, binding, cp, folder / 'preflight_first.json', True, 37)
    last = execute(d, spec, binding, first['result']['checkpoint'], folder / 'preflight_last.json', True, 63)
    api.require(len(full['rows']) == 100 and len(first['rows']) == 37 and len(last['rows']) == 63, 'complete bounded preflight')
    api.require(full['rows'] == first['rows'] + last['rows'] and full['result']['checkpoint']['state'] == last['result']['checkpoint']['state'], 'exact seed restart')


def join_case(d, wi, factor):
    folder = RUN / d['windows'][wi]['id'] / f'factor_{factor}'
    spec, binding, initial = setup(d, wi, factor)
    before = initial
    rows, records = [], []
    paths = sorted(folder.glob('segment_[0-9][0-9].json'))
    api.require(0 < len(paths) <= LIMIT_CALLS[str(factor)], 'segment budget')
    for i, p in enumerate(paths, 1):
        api.require(p.name == f'segment_{i:02d}.json', 'contiguous case ledger')
        r = read_record(p)
        verify_segment(d, r, before, spec, binding, True)
        api.require(r['step_cap'] == d['budget']['step_cap'], 'frozen step cap')
        api.require(i == len(paths) or r['result']['status'] in ['paused_checkpoint', 'incomplete_budget'], 'no post-completion dispatch')
        rows.extend(r['rows'])
        records.append(r)
        before = r['result']['checkpoint']
    api.require(records[-1]['result']['status'] == 'present_at_horizon', 'common endpoint not reached')
    api.require(parent.prior.w.prior.audit.clock_chain(initial['state']['t'], rows, spec['horizon_s'])['passed'], 'joined exact clock')
    return {'result': records[-1]['result'], 'rows': rows, 'spec': spec,
            'cost_s': sum(r['result']['runtime_seconds'] for r in records), 'segments': len(records)}


def observed_event(d, wi, rec):
    w = d['windows'][wi]
    seed = read_record(RUN / w['id'] / 'seed.json')
    return event(rec['rows'], seed['rows'][-1]['supported_bearing_ids'], w['seed_time_s'],
                 w['grain_id'], w['after_present'], d['event_acceptance']['persistence_s'])


def evaluate_window(d, wi):
    w = d['windows'][wi]
    recs = [join_case(d, wi, f) for f in FACTORS]
    seed = read_record(RUN / w['id'] / 'seed.json')
    source = seed['result']['checkpoint']
    errors = [parent.prior.w.compare(a['result'], b['result'], b['spec']) for a, b in zip(recs, recs[1:])]
    acc = d['accuracy']
    trend = all(errors[1][k] <= lim and (errors[1][k] <= acc['error_reduction_ratio_max'] * errors[0][k]
                 or max(errors[0][k], errors[1][k]) < acc['noise_floor']) for k, lim in acc['limits'].items())
    trace = [parent.prior.common_trace(recs[-1]['rows'], r, source) for r in recs[:-1]]
    trace_ok = all(all(e[k] <= lim for k, lim in acc['limits'].items()) for e in trace)
    events = [observed_event(d, wi, r) for r in recs]
    spread = max(e['midpoint_s'] for e in events) - min(e['midpoint_s'] for e in events) if all(events) else None
    timing_limit = d['event_acceptance']['maximum_midpoint_shift_in_coarse_steps'] * max(r['dt_s'] for r in recs[0]['rows'])
    timing_ok = spread is not None and spread <= timing_limit
    return {'id': w['id'], 'passed': bool(trend and trace_ok and timing_ok), 'endpoint_errors': errors,
            'endpoint_refinement_passed': bool(trend), 'whole_trace_errors_to_finest': trace,
            'whole_trace_passed': bool(trace_ok), 'events': events, 'event_spread_s': spread,
            'event_spread_limit_s': timing_limit, 'event_coverage_and_timing_passed': timing_ok,
            'contact_coverage': [parent.contact_coverage(r) for r in recs],
            'cost': [{'factor': f, 'steps': len(r['rows']), 'runtime_s': r['cost_s'], 'segments': r['segments']} for f, r in zip(FACTORS, recs)]}


def run():
    d = api.read(DESIGN)
    verify(d)
    RUN.mkdir(parents=True, exist_ok=False)
    api.write(RUN / 'launch.json', {'pid': os.getpid(), 'argv': sys.argv, 'python': sys.version,
        'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'design_sha256': api.sha(DESIGN),
        'threads': {k: os.environ.get(k) for k in parent.THREADS}})
    parent.configure()
    for wi in range(2):
        seed_preflight(d, wi)
    for factor in FACTORS:
        for wi, w in enumerate(d['windows']):
            folder = RUN / w['id'] / f'factor_{factor}'
            folder.mkdir(exist_ok=False)
            spec, binding, cp = setup(d, wi, factor)
            for i in range(1, LIMIT_CALLS[str(factor)] + 1):
                r = execute(d, spec, binding, cp, folder / f'segment_{i:02d}.json', True, d['budget']['step_cap'])
                if r['result']['status'] == 'present_at_horizon':
                    break
                cp = r['result']['checkpoint']
            api.require(r['result']['status'] == 'present_at_horizon', 'prospective case budget exhausted')
            api.require(observed_event(d, wi, join_case(d, wi, factor)) is not None, 'specified event missing; no further dispatch')
    verify(d)
    rows = [evaluate_window(d, wi) for wi in range(2)]
    result = {'stage': 'Stage155', 'passed': all(r['passed'] for r in rows), 'windows': rows,
              'design_sha256': api.sha(DESIGN), 'claim': d['claim'], 'production_promotion': False,
              'artifacts': {str(p): api.sha(p) for p in RUN.rglob('*') if p.is_file()}}
    OUT.mkdir(parents=True, exist_ok=False)
    api.write(OUT / 'results.json', result, raw=True)
    api.write(OUT / 'completion.json', {'passed': result['passed'], 'results_sha256': api.sha(OUT / 'results.json')})
    print('STAGE155_PASS', result['passed'], flush=True)
    return 0 if result['passed'] else 4


def audit():
    d = api.read(DESIGN)
    verify(d)
    result = api.read(OUT / 'results.json')
    seal = api.read(OUT / 'completion.json')
    api.require(seal['results_sha256'] == api.sha(OUT / 'results.json') and seal['passed'] == result['passed'], 'result seal')
    api.verify_mapping(result['artifacts'])
    api.require(not list(RUN.rglob('failure.json')), 'no runtime failures')
    parent.configure()
    for wi, w in enumerate(d['windows']):
        folder = RUN / w['id']
        spec, binding, cp = setup(d, wi, 1., seed=True)
        seed = read_record(folder / 'seed.json')
        verify_segment(d, seed, cp, spec, binding, False)
        api.require(seed['result']['status'] == 'present_at_horizon', 'seed completion')
        spec, binding, cp = setup(d, wi, 1., preflight=True)
        full, first, last = [read_record(folder / f'preflight_{n}.json') for n in ['full', 'first', 'last']]
        for r, c in [(full, cp), (first, cp), (last, first['result']['checkpoint'])]:
            verify_segment(d, r, c, spec, binding, True)
        api.require(full['rows'] == first['rows'] + last['rows'] and full['result']['checkpoint']['state'] == last['result']['checkpoint']['state'], 'exact restart recheck')
    recalculated = [evaluate_window(d, wi) for wi in range(2)]
    api.require(recalculated == result['windows'] and result['passed'] == all(r['passed'] for r in recalculated), 'raw-record recomputation')
    AUDIT.mkdir(parents=True, exist_ok=False)
    report = {'audit_integrity_passed': True, 'scientific_gates_passed': result['passed'], 'windows': recalculated,
              'design_sha256': api.sha(DESIGN), 'evaluation_sha256': api.sha(OUT / 'results.json'),
              'claim': d['claim'], 'production_promotion': False}
    api.write(AUDIT / 'results.json', report, raw=True)
    api.write(AUDIT / 'completion.json', {'results_sha256': api.sha(AUDIT / 'results.json'), 'audit_integrity_passed': True, 'scientific_gates_passed': result['passed']})
    print('RAW_RECORD_AUDIT_PASS; SCIENTIFIC_GATES', result['passed'], flush=True)


if __name__ == '__main__':
    command = sys.argv[1] if len(sys.argv) == 2 else ''
    owned = False
    try:
        if command == 'selftest':
            selftest()
        elif command == 'prepare':
            prepare()
        elif command == 'run':
            api.require(not RUN.exists() and not OUT.exists(), 'immutable run exists; no restart')
            owned = True
            raise SystemExit(run())
        elif command == 'audit':
            audit()
        else:
            raise ValueError('Use selftest, prepare, run or audit')
    except Exception as exc:
        if owned and RUN.exists() and not (RUN / 'failure.json').exists():
            api.write(RUN / 'failure.json', {'error': repr(exc), 'traceback': traceback.format_exc()})
        raise
