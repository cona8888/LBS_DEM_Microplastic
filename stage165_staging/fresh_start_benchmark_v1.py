"""Gated six-case fresh-start check and deadline cost measurement.

Prepare refuses until the full Stage164 workflow and audit have passed. This
script is not a long-trajectory dispatcher. It measures a 2-ms startup at three
levels for both equal-volume shapes, and verifies resource/storage adapters.
"""
from pathlib import Path
import copy
import datetime
import inspect
import os
import sys
import time
import traceback
import numpy as np
import transport_budget_io_v1 as storage

q = storage.qualification
api, old, model, engine, fix = q.api, q.old, q.model, q.engine, q.fix
ROOT = q.ROOT
BASE = 'fresh_start_deadline_benchmark_20260922'
DESIGN = ROOT / 'stage165_designs' / BASE / 'design_01.json'
RUN = ROOT / 'stage165_runs' / BASE / 'run_01'
OUT = ROOT / 'stage165_evaluations' / BASE / 'evaluation_01'
AUDIT = OUT.parent / 'independent_audit_01'
STORAGE_UNITS = ROOT / 'stage165_evaluations/budget_storage_units_20260922/verification_01'
START = None


def resolve_start_lineage():
    """Resolve the physical pose, not stale labels inherited in config metadata."""
    protocol_path = ROOT / 'stage109_designs/shape_flow_protocol_20260914/protocol.json'
    protocol = api.read(protocol_path)
    api.require(api.read(protocol_path.with_name('completion.json'))['protocol_sha256'] == api.sha(protocol_path), 'population protocol seal')
    starts_path = ROOT / 'stage95_designs/common_admissible_population_01/starts_s2.json'
    api.require(protocol['input_hashes'][str(starts_path)] == api.sha(starts_path), 'population starts binding')
    start = api.read(starts_path)[0]
    parent = api.read(q.DESIGN)
    state = {'position_m': start['position_m'], 'orientation': start['orientation'],
             'velocity_generalized': start['initial_velocity_generalized']}
    api.require(start['id'] == 0 and state == parent['base_spec']['initial_state'], 'actual initial-state identity')
    legacy_path = ROOT / 'stage37_runs/stage4_farfield_bound_20260912/pilot_01/starts_s2.json'
    legacy = next(x for x in api.read(legacy_path) if x['id'] == 47)
    api.require(legacy['position_m'] != state['position_m'], 'legacy label must not be substituted for actual state')
    return {'packing_seed': 2, 'sample_id': 0, 'state': state, 'state_sha256': api.digest(state),
        'role': 'Known IID development sentinel, not an independent held-out or probability-weighted population estimate.',
        'population': protocol['population']['source_conditioning'],
        'stale_legacy_config_start_id': 47,
        'stale_label_correction_changes_physical_state': False,
        'inputs': {str(p): api.sha(p) for p in [protocol_path, protocol_path.with_name('completion.json'), starts_path, legacy_path]}}


def ready():
    d = api.read(q.DESIGN); q.verify(d)
    r = api.read(q.OUT / 'results.json'); a = api.read(q.AUDIT / 'results.json')
    api.require(api.read(q.OUT / 'completion.json')['results_sha256'] == api.sha(q.OUT / 'results.json'), 'qualification seal')
    api.require(api.read(q.AUDIT / 'completion.json')['results_sha256'] == api.sha(q.AUDIT / 'results.json'), 'qualification audit seal')
    api.require(r['passed'] and a['audit_integrity_passed'] and a['scientific_gates_passed'] and r['selected_factor'] == a['selected_factor'], 'full-window qualification required')
    api.require(not (q.RUN / 'failure.json').exists(), 'qualification runtime failure')
    units = api.read(STORAGE_UNITS / 'results.json')
    api.require(units['passed'] and api.read(STORAGE_UNITS / 'completion.json')['results_sha256'] == api.sha(STORAGE_UNITS / 'results.json'), 'storage/budget unit seal')
    api.verify_mapping(units['sources']); api.verify_mapping(units['inputs']); api.verify_mapping(units['artifacts'])
    return d, r


def prepare():
    parent, result = ready(); selected = result['selected_factor']
    lineage = resolve_start_lineage()
    factors = [selected*2, selected, selected/2]
    old_design = ROOT / 'stage135_designs/matched_transport_extension_20260918/design_01.json'
    sphere = next(c['spec'] for c in api.read(old_design)['cases'] if c['spec']['shape'] == 'equal_volume_sphere')
    specs = []
    for shape in ['equal_volume_sphere', 'rigid_prolate_ar4']:
        for factor in factors:
            spec = copy.deepcopy(parent['base_spec'])
            spec['case_id'] = f's165_{shape}_factor_{factor}'
            spec['shape'] = shape
            if shape == 'equal_volume_sphere':
                spec['config']['prolate_semiaxes_m'] = sphere['config']['prolate_semiaxes_m']
            spec['horizon_s'] = .002
            spec['horizon_pv'] = .002 * spec['field_metadata']['pv_per_second']
            spec['refinement'] = parent['base_spec']['refinement'] * factor
            spec['config']['horizon_pore_volumes'] = spec['horizon_pv']
            spec['config']['packings'] = [{'seed': 2, 'sample_id': 0}]
            spec['config']['selection_rule'] = lineage['role']
            spec['config']['purpose'] = 'Fresh 2-ms sphere/fibre startup verification and runtime measurement from the hash-bound IID development sentinel.'
            spec['config']['claim_boundary'] = 'Numerical development benchmark only; no long-trajectory, held-out, population-release or empirical-validation claim.'
            for key in api.DT_CONTROLS: spec['config']['numerics'][key] *= factor
            specs.append({'id': spec['case_id'], 'shape': shape, 'factor': factor, 'spec': spec})
    inputs = {str(p): api.sha(p) for p in [q.DESIGN, q.OUT / 'results.json', q.OUT / 'completion.json',
               q.AUDIT / 'results.json', q.AUDIT / 'completion.json', old_design,
               STORAGE_UNITS / 'results.json', STORAGE_UNITS / 'completion.json']}
    inputs.update(lineage['inputs'])
    d = {'stage': 'Stage165', 'cases': specs, 'factors': factors, 'selected_factor': selected,
        'question': 'Do both matched shapes start from their unmodified physical initial state with accurate resolved rigid inertia, and what is their measured cost?',
        'physical_changes': [], 'new_initial_history': 'Fresh t=0, zero velocity, prescribed initial pose; never a quasistatic prefix.',
        'source': 'Exact Stage95 seed-2 IID sample-0 physical initial state reused by Stage135 and Stage164; inherited Stage86 near-outlet metadata is stale and is not the selection rule.',
        'initial_state_lineage': lineage,
        'accuracy_limits': parent['limits'],
        'gates': ['All six fresh startup cases reach 2 ms with no rejected trials and unchanged independent health/clock/balance gates.',
                  'Both coarser levels meet the Stage164 absolute endpoint, whole-pose and exact mean-L1 velocity caps against finest. Uniform instantaneous-velocity trace is reported, not gated.',
                  'Measure and report active-contact coverage during startup; do not assume it is a contact-free trajectory.',
                  'Budget adapter leaves bytecode unchanged and default versus enlarged-limit 100-step paths identical; 100 versus 37+63 restart exact.',
                  'A synthetic high-step-counter checkpoint tests old-cap stopping, enlarged-cap advancement and identical physical state to the unshifted-counter case.',
                  'Lossless deterministic compression round-trips every saved value; writes are exclusive and both compressed and raw bytes hash-bound.'],
        'resource_adapter': 'Only max_steps default changes from 500000 to the declared 10000000 for the adapter tests and this bounded startup. Physics, all time controls, and data precision are unchanged.',
        'budget': {'step_cap': 2500, 'maximum_calls_per_case': 8, 'maximum_steps_per_case': 20000,
                   'maximum_new_accepted_steps': 121000, 'declared_total_step_ceiling': 10000000,
                   'workflow_wall_seconds': 900., 'workers': 1, 'threads': 1},
        'deadline': parent['deadline'], 'claim': 'Short fresh-start solution verification and measured cost only; not a completed long trajectory or population release dataset.',
        'projection_rule': 'Report observed startup and full-contact-window rates. Projections are scenarios, not guaranteed completion times. Allow 30% wall-time margin and four final audit hours. Do not select physical cases by release outcomes.',
        'stop': 'Any gate or budget failure stops. No automatic long run, parameter change, tolerance relaxation or refitting.',
        'inputs': inputs, 'sources': {str(Path(m.__file__).resolve()): api.sha(m.__file__) for m in list(sys.modules.values())
             if getattr(m, '__file__', None) and Path(m.__file__).suffix == '.py' and ROOT in Path(m.__file__).resolve().parents}}
    d['binding'] = api.digest(d); DESIGN.parent.mkdir(parents=True, exist_ok=True); api.write(DESIGN, d)
    print('FROZEN', api.sha(DESIGN), flush=True)


def verify(d):
    api.require(d['binding'] == api.digest({k: v for k, v in d.items() if k != 'binding'}), 'design digest')
    api.verify_mapping(d['inputs']); api.verify_mapping(d['sources']); ready()


def check(r, before, spec, binding):
    result = r['result']; rows = r['rows']; effective = model.binding_for(binding, True)
    start = 0. if before is None else before['state']['t']
    steps = 0 if before is None else before['state']['steps']
    api.require(r['input_checkpoint_sha256'] == api.digest(before), 'input checkpoint binding')
    api.require(r['spec'] == spec and r['effective_binding'] == effective, 'case binding')
    api.require(result['checkpoint']['contract'] == engine.prior.contracts.expected_contract(spec, effective), 'full dynamics contract')
    api.require(result['checkpoint']['state_sha256'] == api.digest(result['checkpoint']['state']), 'checkpoint hash')
    api.require(engine.prior.reference.independent_health(result, spec)['passed'], 'independent numerical health')
    api.require(old.parent.prior.w.prior.audit.clock_chain(start, rows, result['time_s'])['passed'], 'exact clock')
    api.require(len(rows) == result['steps']-steps and 0 < len(rows) <= r['step_cap'] <= 2500, 'accepted-step accounting')
    api.require(result['rejected'] == (0 if before is None else before['state']['rejected']), 'no rejected trial')
    api.require(not result.get('stage119_repair_calls'), 'no unqualified solver repair')
    api.require(len(r['backend_calls']) == 1 and r['backend_calls'][0]['enabled'], 'rigid live backend')
    api.require(result['status'] in ['paused_checkpoint', 'incomplete_budget', 'present_at_horizon'], 'unexpected termination')
    api.require((result['status'] == 'present_at_horizon') == (result['time_s'] == spec['horizon_s']), 'exact completion')
    api.require(start < result['time_s'] <= spec['horizon_s'], 'progress/horizon')


def execute(d, spec, binding, cp, path, steps, enlarged=True, allow_zero=False):
    if START is not None: api.require(time.monotonic()-START <= d['budget']['workflow_wall_seconds'], '15-minute benchmark budget')
    before = copy.deepcopy(cp); ncalls = len(model.calls); ncerts = len(fix.telemetry)
    scope = storage.step_budget_scope(d['budget']['declared_total_step_ceiling']) if enlarged else old.parent.prior.candidate.scope(True)
    with old.hot.scope(), scope, fix.scope():
        result, rows = engine.runtime.execute(spec, binding, checkpoint=cp,
            pause=(0 if cp is None else cp['state']['steps'])+steps)
    rec = {'result': result, 'rows': rows, 'spec': spec, 'input_checkpoint_sha256': api.digest(before),
           'effective_binding': model.binding_for(binding, True), 'design_sha256': api.sha(DESIGN),
           'backend_calls': copy.deepcopy(model.calls[ncalls:]), 'certificates': copy.deepcopy(fix.telemetry[ncerts:]),
           'step_cap': steps, 'enlarged_resource_budget': enlarged}
    seal = storage.write_record(path, rec)
    api.require(api.digest(storage.read_record(path, api.sha(DESIGN))) == api.digest(rec), 'lossless record round-trip')
    if not allow_zero: check(rec, before, spec, binding)
    print(path.relative_to(RUN), result['status'], len(rows), 't=', result['time_s'], 'compression=', round(seal['uncompressed_bytes']/seal['compressed_bytes'], 2), flush=True)
    return rec


def preflight(d):
    folder = RUN / 'adapter_checks'; folder.mkdir(exist_ok=False)
    c = next(x for x in d['cases'] if x['shape'] == 'rigid_prolate_ar4' and x['factor'] == d['selected_factor'])
    spec = c['spec']; binding = api.digest([d['binding'], 'adapter_checks'])
    plain = execute(d, spec, binding, None, folder / 'plain.json.gz', 100, False)
    full = execute(d, spec, binding, None, folder / 'full.json.gz', 100)
    first = execute(d, spec, binding, None, folder / 'first.json.gz', 37)
    last = execute(d, spec, binding, first['result']['checkpoint'], folder / 'last.json.gz', 63)
    api.require(plain['rows'] == full['rows'] == first['rows']+last['rows'], 'unchanged default and exact split path')
    api.require(plain['result']['checkpoint']['state'] == full['result']['checkpoint']['state'] == last['result']['checkpoint']['state'], 'unchanged complete state')
    cp = copy.deepcopy(full['result']['checkpoint']); synthetic = copy.deepcopy(cp)
    synthetic['state']['steps'] = 500000; synthetic['state_sha256'] = api.digest(synthetic['state'])
    api.write(folder / 'synthetic_counter_input.json', {'checkpoint': synthetic, 'purpose': 'Budget control-flow test only, not trajectory data.'}, raw=True)
    stopped = execute(d, spec, binding, synthetic, folder / 'old_cap_stop.json.gz', 3, False, True)
    api.require(stopped['result']['status'] == 'incomplete_budget' and not stopped['rows'] and stopped['result']['checkpoint']['state'] == synthetic['state'], 'old global cap semantics')
    high = execute(d, spec, binding, synthetic, folder / 'new_cap_advance.json.gz', 3)
    low = execute(d, spec, binding, cp, folder / 'ordinary_advance.json.gz', 3)
    api.require(high['rows'] == low['rows'], 'step budget cannot change physics')
    hs, ls = copy.deepcopy(high['result']['checkpoint']['state']), copy.deepcopy(low['result']['checkpoint']['state'])
    hs.pop('steps'); ls.pop('steps'); api.require(hs == ls, 'counter-only distinction')
    # Negative inputs and exclusive writes are tested without advancing physics.
    for invalid in [0, -1, 1.5, True, 50000001]:
        try: storage.with_step_budget(storage.modal.CANDIDATE, invalid)
        except ValueError: pass
        else: raise RuntimeError('invalid budget accepted')
    try: storage.write_record(folder / 'full.json.gz', full)
    except FileExistsError: pass
    else: raise RuntimeError('overwrite unexpectedly accepted')
    api.write(folder / 'completion.json', {'passed': True, 'default_identity': True, 'exact_restart': True,
        'synthetic_global_ceiling_test': True, 'invalid_budgets_rejected': 5, 'overwrite_rejected': True})


def joined(d, c):
    binding = api.digest([d['binding'], c['id']]); cp = None; rows = []; cost = 0.; raw = compressed = 0
    paths = sorted((RUN / c['id']).glob('segment_??.json.gz'))
    api.require(0 < len(paths) <= d['budget']['maximum_calls_per_case'], 'case call budget')
    for n, p in enumerate(paths, 1):
        api.require(p.name == f'segment_{n:02d}.json.gz', 'segment order')
        r = storage.read_record(p, api.sha(DESIGN)); check(r, cp, c['spec'], binding)
        api.require(n == len(paths) or r['result']['status'] in ['paused_checkpoint', 'incomplete_budget'], 'no post-completion dispatch')
        rows += r['rows']; cp = r['result']['checkpoint']; cost += r['result']['runtime_seconds']
        seal = api.read(p.with_suffix('.seal.json')); raw += seal['uncompressed_bytes']; compressed += seal['compressed_bytes']
    api.require(r['result']['status'] == 'present_at_horizon', 'complete fresh-start case')
    return {'result': r['result'], 'rows': rows, 'spec': c['spec'], 'cost_s': cost, 'raw_bytes': raw, 'compressed_bytes': compressed}


def audit_preflight(d):
    folder = RUN / 'adapter_checks'
    read = lambda name: storage.read_record(folder / (name + '.json.gz'), api.sha(DESIGN))
    plain, full, first, last = [read(n) for n in ['plain', 'full', 'first', 'last']]
    spec = full['spec']; binding = api.digest([d['binding'], 'adapter_checks'])
    for r in [plain, full, first]: check(r, None, spec, binding)
    check(last, first['result']['checkpoint'], spec, binding)
    api.require(plain['rows'] == full['rows'] == first['rows']+last['rows'], 'independent adapter path identity')
    api.require(plain['result']['checkpoint']['state'] == full['result']['checkpoint']['state'] == last['result']['checkpoint']['state'], 'independent adapter state identity')
    synthetic = api.read(folder / 'synthetic_counter_input.json')['checkpoint']
    expected = copy.deepcopy(full['result']['checkpoint']); expected['state']['steps'] = 500000
    expected['state_sha256'] = api.digest(expected['state'])
    api.require(synthetic == expected, 'synthetic counter changed only resource metadata')
    stopped, high, low = [read(n) for n in ['old_cap_stop', 'new_cap_advance', 'ordinary_advance']]
    api.require(not stopped['rows'] and stopped['result']['status'] == 'incomplete_budget' and stopped['result']['checkpoint']['state'] == synthetic['state'], 'independent cap stop')
    check(high, synthetic, spec, binding); check(low, full['result']['checkpoint'], spec, binding)
    api.require(high['rows'] == low['rows'], 'independent physical path unaffected')
    hs, ls = copy.deepcopy(high['result']['checkpoint']['state']), copy.deepcopy(low['result']['checkpoint']['state'])
    hs.pop('steps'); ls.pop('steps'); api.require(hs == ls, 'independent counter-only state distinction')


def evaluate(d):
    reports = []
    for shape in ['equal_volume_sphere', 'rigid_prolate_ar4']:
        cases = [c for c in d['cases'] if c['shape'] == shape]; recs = [joined(d, c) for c in cases]
        spec = cases[0]['spec']; state = spec['initial_state']; U = spec['config']['target_mean_interstitial_velocity_m_s']
        seed = {'state': {'t': 0., 'x': state['position_m'], 'p': state['orientation'], 'q': state['velocity_generalized']}}
        metrics = []
        for rec in recs[:-1]:
            endpoint = old.parent.prior.w.compare(rec['result'], recs[-1]['result'], recs[-1]['spec'])
            trace = old.parent.prior.common_trace(recs[-1]['rows'], rec, seed)
            l1 = q.diag.piecewise_l1(rec['rows'], recs[-1]['rows'], 0., .002, U)['mean_norm_over_scale']
            independent = q.independent_l1(rec['rows'], recs[-1]['rows'], 0., .002, U)
            api.require(abs(l1-independent) <= 1e-12, 'independent L1')
            passed = all(endpoint[k] <= v for k, v in d['accuracy_limits'].items()) and all(trace[k] <= d['accuracy_limits'][k] for k in ['position_over_b', 'axis_vector_norm']) and l1 <= .005
            metrics.append({'passed': passed, 'endpoint': endpoint, 'trace': trace, 'L1_over_U': l1})
        contact_free = all(not row['active_contact_ids'] for r in recs for row in r['rows'])
        reports.append({'shape': shape, 'passed': all(x['passed'] for x in metrics),
            'no_contact': contact_free, 'to_finest': metrics,
            'cost': [{'factor': c['factor'], 'steps': len(r['rows']), 'runtime_s': r['cost_s'],
                      'seconds_per_simulated_second': r['cost_s']/.002, 'raw_bytes': r['raw_bytes'],
                      'compressed_bytes': r['compressed_bytes'],
                      'active_contact_time_fraction': sum(row['dt_s'] for row in r['rows'] if row['active_contact_ids'])/.002}
                     for c, r in zip(cases, recs)]})
    return {'stage': 'Stage165', 'passed': all(r['passed'] for r in reports), 'shapes': reports,
            'design_sha256': api.sha(DESIGN), 'claim': d['claim'], 'long_trajectory_executed': False}


def run():
    global START
    START = time.monotonic(); d = api.read(DESIGN); verify(d)
    RUN.mkdir(parents=True, exist_ok=False); OUT.mkdir(parents=True, exist_ok=False)
    api.write(RUN / 'launch.json', {'pid': os.getpid(), 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'design_sha256': api.sha(DESIGN), 'python': sys.version, 'threads': {k: os.environ.get(k) for k in old.parent.THREADS}})
    old.parent.configure(); preflight(d)
    total = 306
    for c in d['cases']:
        folder = RUN / c['id']; folder.mkdir(exist_ok=False); cp = None; steps = 0; binding = api.digest([d['binding'], c['id']])
        for n in range(1, d['budget']['maximum_calls_per_case']+1):
            r = execute(d, c['spec'], binding, cp, folder / f'segment_{n:02d}.json.gz', d['budget']['step_cap'])
            steps += len(r['rows']); total += len(r['rows'])
            api.require(steps <= d['budget']['maximum_steps_per_case'] and total <= d['budget']['maximum_new_accepted_steps'], 'step budgets')
            if r['result']['status'] == 'present_at_horizon': break
            cp = r['result']['checkpoint']
        api.require(r['result']['status'] == 'present_at_horizon', 'case budget exhausted')
    result = evaluate(d); verify(d)
    result['artifacts'] = {str(p): api.sha(p) for p in RUN.rglob('*') if p.is_file()}
    api.write(OUT / 'results.json', result, raw=True)
    api.write(OUT / 'completion.json', {'passed': result['passed'], 'results_sha256': api.sha(OUT / 'results.json')})
    api.verify_mapping(result['artifacts']); audit_preflight(d); recomputed = evaluate(d)
    api.require(all(result[k] == v for k, v in recomputed.items()), 'independent full record reload')
    AUDIT.mkdir(parents=True, exist_ok=False)
    api.write(AUDIT / 'results.json', {'audit_integrity_passed': True, 'scientific_gates_passed': result['passed'],
        'evaluation_sha256': api.sha(OUT / 'results.json'), 'claim': d['claim']}, raw=True)
    api.write(AUDIT / 'completion.json', {'audit_integrity_passed': True, 'results_sha256': api.sha(AUDIT / 'results.json')})
    print('STAGE165', result['passed'], flush=True)


if __name__ == '__main__':
    owned = False
    try:
        if sys.argv[1:] == ['prepare']: prepare()
        elif sys.argv[1:] == ['run']:
            api.require(not RUN.exists() and not OUT.exists() and not AUDIT.exists(), 'immutable destination exists')
            owned = True; run()
        else: raise ValueError('Use prepare or run')
    except Exception as e:
        if owned and RUN.exists() and not (RUN / 'failure.json').exists():
            api.write(RUN / 'failure.json', {'error': repr(e), 'traceback': traceback.format_exc()})
        raise
