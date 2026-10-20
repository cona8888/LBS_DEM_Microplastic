"""Frozen 50-ms, conditional moving-fibre check; no production promotion.

Only the observation horizon and prospectively bounded segmentation change.
The Stage153 modal controller and Stage151 rigid Euler dynamics are unchanged.
Use prepare -> preflight -> run -> audit. Every output directory is exclusive.
"""
from pathlib import Path
import copy
import datetime
import os
import sys
import traceback
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage153_staging'))
import verify_modal_dt_v1 as prior

api, engine, model, hot = prior.api, prior.engine, prior.model, prior.hot
BASE = 'longer_rotation_window_20260922'
DESIGN = ROOT / 'stage154_designs' / BASE / 'design_01.json'
PREFLIGHT = ROOT / 'stage154_evaluations' / BASE / 'preflight_01'
RUN = ROOT / 'stage154_runs' / BASE / 'run_01'
OUT = ROOT / 'stage154_evaluations' / BASE / 'evaluation_01'
AUDIT = OUT.parent / 'independent_audit_01'
THREADS = ['OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS']
CASES = [
    {'id': 'modal_1', 'factor': 1., 'rigid': True, 'max_calls': 4},
    {'id': 'modal_half', 'factor': .5, 'rigid': True, 'max_calls': 6},
    {'id': 'modal_quarter', 'factor': .25, 'rigid': True, 'max_calls': 12},
    {'id': 'quasistatic_1', 'factor': 1., 'rigid': False, 'max_calls': 2},
    {'id': 'quasistatic_half', 'factor': .5, 'rigid': False, 'max_calls': 2},
]


def sealed(folder):
    r = api.read(folder / 'results.json')
    c = api.read(folder / 'completion.json')
    api.require(r['passed'] and c['passed'] and c['results_sha256'] == api.sha(folder / 'results.json'), 'passed result seal')
    return r


def verify(d):
    api.require(d['binding'] == api.digest({k: v for k, v in d.items() if k != 'binding'}), 'design binding')
    api.verify_mapping(d['sources'])
    api.verify_mapping(d['inputs'])
    prior.verify(api.read(prior.DESIGN))
    api.require(d['modal_source_digest'] == api.digest(prior.candidate.GENERATED_SOURCE), 'modal controller source')
    api.require(d['cases'] == CASES and d['window_s'] == .05, 'frozen case order and horizon')
    api.require(d['accuracy'] == api.read(prior.DESIGN)['acceptance'], 'unchanged inherited tolerances')


def prepare():
    previous = sealed(prior.OUT)
    api.verify_mapping(previous['artifacts'])
    old_audit = prior.OUT.parent / 'independent_audit_01'
    sealed(old_audit)
    prior.verify(api.read(prior.DESIGN))
    old = api.read(prior.w.DESIGN)
    source = api.read(old['case']['source'])['result']['checkpoint']
    paths = [prior.DESIGN, prior.OUT / 'results.json', prior.OUT / 'completion.json',
             old_audit / 'results.json', old_audit / 'completion.json', Path(old['case']['source'])]
    inputs = {str(p): api.sha(p) for p in paths}
    sources = {str(Path(m.__file__).resolve()): api.sha(m.__file__) for m in list(sys.modules.values())
               if getattr(m, '__file__', None) and Path(m.__file__).suffix == '.py'
               and ROOT in Path(m.__file__).resolve().parents}
    d = {
        'stage': 'Stage154', 'window_s': .05, 'cases': CASES,
        'question': 'Does the locally qualified modal timestep remain accurate over a 25-times-longer moving, multi-contact fibre window?',
        'evidence_class': 'Conditional solution verification and model-assumption diagnostic, not empirical validation.',
        'source': old['case']['source'], 'source_time_s': source['state']['t'],
        'horizon_s': source['state']['t'] + .05, 'base_spec': old['case']['spec'],
        'physical_changes_from_Stage153': [], 'controller_changes_from_Stage153': [],
        'accuracy': api.read(prior.DESIGN)['acceptance'],
        'primary_gates': [
            'Every segment independently passes state/contract hashes, exact accepted clock, health and no unqualified fallback.',
            'All modal levels reach the same frozen horizon with no new rejected trials.',
            'Endpoint fine-pair errors obey the inherited limits and refinement-reduction rule.',
            'Both coarser modal whole traces satisfy the inherited limits against the modal finest trace.',
            'Modal outlet/dwell verdicts agree; numerical validity of the quasistatic diagnostic is reported separately.',
        ],
        'contact_coverage': 'Report time-weighted active/bearing contact coverage, contact-set changes and observed IDs. The source has three active contacts. Do not assume contact creation or release occurs.',
        'quasistatic_comparator': 'Two timestep levels at the same saved state and clock. Report its own discretization discrepancy and the difference from rigid-inertia finest; do not tune parameters or require the models to agree.',
        'budget': {'cooperative_seconds_per_call': 45., 'step_cap_per_call': 2500,
                   'maximum_calls': sum(c['max_calls'] for c in CASES), 'workers': 1, 'threads': 1,
                   'estimated_total_integration_minutes': [8, 12],
                   'note': 'Prospective per-case limits above. Healthy paused_checkpoint or incomplete_budget may continue only within them; no unbudgeted retries. Wall cap is cooperative, not a hard kill.'},
        'preflight': '100 modal accepted steps versus 37+63 exact restart, 20 quasistatic steps, wrong-model checkpoint rejection, canonical modes and completion-guard negatives. These are not the 50-ms result.',
        'claim': 'One inherited moving-fibre state over 0.05 s. No fresh full-path history, contact-onset qualification, population export, permanent retention, experimental validation or production promotion.',
        'stop': 'Any provenance, runtime-health, completion, or primary scientific failure stops advancement. Preserve every segment. No automatic repair, wider budgets or relaxed tolerances.',
        'next_job_model': {'routine_run_and_audit': 'GPT-5.6 Luna, low reasoning',
                           'bounded_runner_repair': 'GPT-5.6 Terra, medium reasoning',
                           'failed_scientific_gate_or_physics_change': 'GPT-6 Astra, high reasoning'},
        'sources': sources, 'inputs': inputs, 'modal_source_digest': api.digest(prior.candidate.GENERATED_SOURCE),
    }
    d['binding'] = api.digest(d)
    DESIGN.parent.mkdir(parents=True, exist_ok=True)
    api.write(DESIGN, d)
    print('FROZEN', api.sha(DESIGN), flush=True)


def setup(d, case, purpose='campaign'):
    spec = copy.deepcopy(d['base_spec'])
    spec['horizon_s'] = d['horizon_s']
    spec['horizon_pv'] = d['horizon_s'] * spec['field_metadata']['pv_per_second']
    for key in api.DT_CONTROLS:
        spec['config']['numerics'][key] *= case['factor']
    binding = api.digest([d['binding'], purpose, case['id']])
    source = api.read(d['source'])['result']['checkpoint']
    cp = model.checkpoint(spec, binding, source, case['rigid'])
    return spec, binding, cp


def segment_guard(result, before, horizon):
    status = result['status']
    api.require(status in ['paused_checkpoint', 'incomplete_budget', 'present_at_horizon'], 'unexpected termination')
    api.require(result['steps'] > before['state']['steps'] and result['time_s'] > before['state']['t'], 'no accepted progress')
    api.require(result['time_s'] <= horizon, 'horizon overshoot')
    api.require((status == 'present_at_horizon') == (result['time_s'] == horizon), 'completion status/clock mismatch')
    api.require(result['rejected'] == before['state']['rejected'], 'new rejected trial')


def execute_segment(d, case, spec, binding, cp, path, steps):
    before = copy.deepcopy(cp)
    call_start = len(model.calls)
    scope = prior.candidate.scope(True) if case['rigid'] else model.scope(False)
    with hot.scope(), scope:
        result, rows = engine.runtime.execute(spec, binding, checkpoint=cp, pause=cp['state']['steps'] + steps)
    rec = {'result': result, 'rows': rows, 'spec': spec, 'case_id': case['id'],
           'input_checkpoint_sha256': api.digest(before), 'design_sha256': api.sha(DESIGN),
           'effective_binding': model.binding_for(binding, case['rigid']),
           'runtime_backend_calls': copy.deepcopy(model.calls[call_start:]), 'requested_step_cap': steps}
    rec['checks'] = prior.s.check_record(rec, before, spec, rec['effective_binding'])
    api.write(path, rec, raw=True)
    api.write(path.with_suffix('.seal.json'), {'record_sha256': api.sha(path), 'design_sha256': api.sha(DESIGN)})
    # Evidence is durable before any gate can stop the workflow.
    api.require(rec['checks']['passed'], 'independent segment health/clock/contract')
    expected_calls = 1 if case['rigid'] else 0
    api.require(len(rec['runtime_backend_calls']) == expected_calls, 'explicit selected runtime backend')
    api.require(not case['rigid'] or rec['runtime_backend_calls'][0]['enabled'], 'rigid backend enabled')
    api.require(len(rows) <= steps, 'accepted step cap')
    segment_guard(result, before, d['horizon_s'])
    print(case['id'], path.name, result['status'], len(rows), 't=', result['time_s'], flush=True)
    return rec


def configure():
    api.require(all(os.environ.get(k) == '1' for k in THREADS), 'single-thread environment required')
    prior.w.prior.parent.old.prior.prior.configure()
    hot.warmup()


def preflight():
    d = api.read(DESIGN)
    verify(d)
    PREFLIGHT.mkdir(parents=True, exist_ok=False)
    configure()
    toy = prior.toys()
    api.require(toy['passed'], 'canonical paired modes')
    case = d['cases'][0]
    spec, binding, cp = setup(d, case, 'preflight')
    full = execute_segment(d, case, spec, binding, cp, PREFLIGHT / 'full.json', 100)
    first = execute_segment(d, case, spec, binding, cp, PREFLIGHT / 'split_first.json', 37)
    last = execute_segment(d, case, spec, binding, first['result']['checkpoint'], PREFLIGHT / 'split_second.json', 63)
    exact = full['rows'] == first['rows'] + last['rows'] and full['result']['checkpoint']['state'] == last['result']['checkpoint']['state']
    api.require(exact, 'segmentation exact restart')
    wrong = model.checkpoint(spec, binding, api.read(d['source'])['result']['checkpoint'], False)
    rejected = False
    try:
        with hot.scope(), prior.candidate.scope(True):
            engine.runtime.execute(spec, binding, checkpoint=wrong, pause=wrong['state']['steps'] + 1)
    except ValueError as exc:
        rejected = 'checkpoint binding or integrity mismatch' in str(exc)
    api.require(rejected, 'wrong mode accepted')
    qcase = d['cases'][3]
    qspec, qbinding, qcp = setup(d, qcase, 'preflight')
    execute_segment(d, qcase, qspec, qbinding, qcp, PREFLIGHT / 'quasistatic.json', 20)
    negatives = []
    for changes in [{'status': 'present_at_horizon'}, {'status': 'solver_failed'},
                    {'time_s': d['horizon_s'] + 1.}, {'steps': cp['state']['steps']},
                    {'rejected': cp['state']['rejected'] + 1}]:
        bad = dict(full['result'], **changes)
        try:
            segment_guard(bad, cp, d['horizon_s'])
        except (ValueError, RuntimeError, AssertionError):
            negatives.append(True)
        else:
            negatives.append(False)
    api.require(all(negatives), 'completion guards failed to reject invalid records')
    verify(d)
    result = {'stage': 'Stage154 preflight', 'passed': True, 'design_sha256': api.sha(DESIGN),
              'canonical': toy, 'exact_100_vs_37_plus_63': exact, 'wrong_mode_rejected': rejected,
              'completion_guard_negatives': negatives, 'campaign_executed': False,
              'artifacts': {str(p): api.sha(p) for p in PREFLIGHT.iterdir() if p.is_file()}}
    api.write(PREFLIGHT / 'results.json', result, raw=True)
    api.write(PREFLIGHT / 'completion.json', {'passed': True, 'results_sha256': api.sha(PREFLIGHT / 'results.json')})
    print('PREFLIGHT_PASS; FROZEN_50MS_CAMPAIGN_NOT_RUN', flush=True)


def load_case(d, case):
    spec, binding, initial = setup(d, case)
    before = initial
    rows, segments = [], []
    paths = sorted((RUN / case['id']).glob('segment_[0-9][0-9].json'))
    api.require(0 < len(paths) <= case['max_calls'], 'case segment count')
    for i, path in enumerate(paths, 1):
        api.require(path.name == f'segment_{i:02d}.json', 'continuous segment order')
        seal = api.read(path.with_suffix('.seal.json'))
        api.require(seal['record_sha256'] == api.sha(path) and seal['design_sha256'] == api.sha(DESIGN), 'segment seal')
        rec = api.read(path)
        api.require(rec['spec'] == spec and rec['design_sha256'] == api.sha(DESIGN) and rec['case_id'] == case['id'], 'case identity')
        api.require(rec['effective_binding'] == model.binding_for(binding, case['rigid']), 'model binding')
        check = prior.s.check_record(rec, before, spec, rec['effective_binding'])
        api.require(check['passed'], 'independent reloaded segment check')
        segment_guard(rec['result'], before, d['horizon_s'])
        api.require(len(rec['rows']) <= rec['requested_step_cap'] == d['budget']['step_cap_per_call'], 'frozen segment step cap')
        api.require(len(rec['runtime_backend_calls']) == int(case['rigid']) and all(x['enabled'] for x in rec['runtime_backend_calls']), 'runtime mode')
        api.require(i == len(paths) or rec['result']['status'] in ['paused_checkpoint', 'incomplete_budget'], 'no dispatch after completion')
        rows.extend(rec['rows'])
        segments.append(rec)
        before = rec['result']['checkpoint']
    api.require(segments[-1]['result']['status'] == 'present_at_horizon', 'case has not completed')
    api.require(prior.w.prior.audit.clock_chain(initial['state']['t'], rows, d['horizon_s'])['passed'], 'joined exact clock')
    return {'spec': spec, 'result': segments[-1]['result'], 'rows': rows,
            'runtime_s': sum(s['result']['runtime_seconds'] for s in segments), 'segments': len(segments)}


def contact_coverage(rec):
    rows = rec['rows']
    duration = sum(r['dt_s'] for r in rows)
    active = [tuple(sorted(r['active_contact_ids'])) for r in rows]
    bearing = [tuple(sorted(r['supported_bearing_ids'])) for r in rows]
    return {'duration_s': duration,
            'fraction_with_any_active_contact': sum(r['dt_s'] for r, ids in zip(rows, active) if ids) / duration,
            'fraction_with_multiple_bearing_contacts': sum(r['dt_s'] for r, ids in zip(rows, bearing) if len(ids) >= 2) / duration,
            'active_set_changes': sum(a != b for a, b in zip(active, active[1:])),
            'bearing_set_changes': sum(a != b for a, b in zip(bearing, bearing[1:])),
            'observed_active_ids': sorted(set(i for ids in active for i in ids))}


def summarize(d, records):
    modal = [records[c['id']] for c in d['cases'] if c['rigid']]
    source = api.read(d['source'])['result']['checkpoint']
    # Explicit common endpoints prevent np.interp from silently extrapolating.
    api.require(all(r['result']['time_s'] == d['horizon_s'] for r in records.values()), 'common observation clock')
    errors = [prior.w.compare(a['result'], b['result'], b['spec']) for a, b in zip(modal, modal[1:])]
    limits = d['accuracy']['limits']
    trend = all(errors[1][k] <= lim and (errors[1][k] <= d['accuracy']['error_reduction_ratio_max'] * errors[0][k]
                or max(errors[0][k], errors[1][k]) < d['accuracy']['noise_floor']) for k, lim in limits.items())
    trace = [prior.common_trace(modal[-1]['rows'], r, source) for r in modal[:-1]]
    trace_pass = all(all(e[k] <= lim for k, lim in limits.items()) for e in trace)
    verdict = all(all(r['result'][k] == modal[-1]['result'][k] for k in ['status', 'persistent_contact_observed', 'dwell_is_absorbing']) for r in modal)
    qcoarse, qfine = records['quasistatic_1'], records['quasistatic_half']
    qerror = prior.common_trace(qfine['rows'], qcoarse, source)
    qresolved = all(qerror[k] <= lim for k, lim in limits.items())
    return {'passed': bool(trend and trace_pass and verdict), 'endpoint_pair_errors': errors,
            'endpoint_refinement_passed': bool(trend), 'whole_trace_errors_to_modal_finest': trace,
            'whole_trace_passed': bool(trace_pass), 'modal_verdicts_agree': verdict,
            'quasistatic_two_level_trace_error': qerror, 'quasistatic_diagnostic_under_inherited_limits': qresolved,
            'quasistatic_fine_vs_rigid_finest_trace_difference': prior.common_trace(modal[-1]['rows'], qfine, source),
            'model_difference_interpretation': 'Descriptive only; two quasistatic levels are not a three-level asymptotic study. Never use agreement to establish empirical validity.',
            'contacts': {name: contact_coverage(r) for name, r in records.items()},
            'cost': {name: {'steps': len(r['rows']), 'runtime_s': r['runtime_s'], 'segments': r['segments']} for name, r in records.items()},
            'verdicts': {name: {k: r['result'][k] for k in ['status', 'persistent_contact_observed', 'dwell_is_absorbing']} for name, r in records.items()}}


def run():
    d = api.read(DESIGN)
    verify(d)
    ready = sealed(PREFLIGHT)
    api.verify_mapping(ready['artifacts'])
    api.require(ready['design_sha256'] == api.sha(DESIGN), 'preflight design')
    RUN.mkdir(parents=True, exist_ok=False)
    api.write(RUN / 'launch.json', {'pid': os.getpid(), 'argv': sys.argv, 'python': sys.version,
        'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'design_sha256': api.sha(DESIGN),
        'threads': {k: os.environ.get(k) for k in THREADS}})
    configure()
    for case in d['cases']:
        folder = RUN / case['id']
        folder.mkdir(exist_ok=False)
        spec, binding, cp = setup(d, case)
        for i in range(1, case['max_calls'] + 1):
            rec = execute_segment(d, case, spec, binding, cp, folder / f'segment_{i:02d}.json', d['budget']['step_cap_per_call'])
            if rec['result']['status'] == 'present_at_horizon':
                break
            cp = rec['result']['checkpoint']
        api.require(rec['result']['status'] == 'present_at_horizon', 'prospective per-case budget exhausted; stop')
    verify(d)
    records = {c['id']: load_case(d, c) for c in d['cases']}
    result = summarize(d, records)
    result.update(stage='Stage154', design_sha256=api.sha(DESIGN), claim=d['claim'], production_promotion=False,
                  artifacts={str(p): api.sha(p) for p in RUN.rglob('*') if p.is_file()})
    OUT.mkdir(parents=True, exist_ok=False)
    api.write(OUT / 'results.json', result, raw=True)
    api.write(OUT / 'completion.json', {'passed': result['passed'], 'results_sha256': api.sha(OUT / 'results.json')})
    print('STAGE154_PASS', result['passed'], flush=True)
    return 0 if result['passed'] else 4


def audit():
    d = api.read(DESIGN)
    verify(d)
    result = sealed(OUT)
    api.verify_mapping(result['artifacts'])
    api.require(not list(RUN.rglob('failure.json')), 'no failure markers')
    configure()
    records = {c['id']: load_case(d, c) for c in d['cases']}
    recomputed = summarize(d, records)
    api.require(all(result[k] == v for k, v in recomputed.items()) and recomputed['passed'], 'independent raw-record recomputation')
    AUDIT.mkdir(parents=True, exist_ok=False)
    report = {'passed': True, 'design_sha256': api.sha(DESIGN), 'evaluation_sha256': api.sha(OUT / 'results.json'),
              'raw_segments_reloaded_and_rechecked': True, 'checks': recomputed, 'claim': d['claim'],
              'production_promotion': False, 'next_job': 'Astra high: interpret longer-window evidence and freeze the next scientifically justified test; no automatic production or physics change.'}
    api.write(AUDIT / 'results.json', report, raw=True)
    api.write(AUDIT / 'completion.json', {'passed': True, 'results_sha256': api.sha(AUDIT / 'results.json')})
    print('INDEPENDENT_RAW_RECORD_AUDIT_PASS', flush=True)


if __name__ == '__main__':
    command = sys.argv[1] if len(sys.argv) == 2 else ''
    owned = None
    try:
        if command == 'prepare':
            prepare()
        elif command == 'preflight':
            api.require(not PREFLIGHT.exists(), 'preflight already exists; do not overwrite')
            owned = PREFLIGHT
            preflight()
        elif command == 'run':
            api.require(not RUN.exists() and not OUT.exists(), 'run already exists; do not restart')
            owned = RUN
            raise SystemExit(run())
        elif command == 'audit':
            audit()
        else:
            raise ValueError('Use prepare, preflight, run or audit')
    except Exception as exc:
        if owned is not None and owned.exists() and not (owned / 'failure.json').exists():
            api.write(owned / 'failure.json', {'error': repr(exc), 'traceback': traceback.format_exc()})
        raise
