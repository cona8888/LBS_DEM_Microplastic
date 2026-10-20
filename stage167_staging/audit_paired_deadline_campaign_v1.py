"""Read-only numerical audit; never integrates, resumes or modifies raw runs.

Commands: units; prefix; evaluate. Outputs are exclusive, and failures preserved.
Pose uses the previously frozen piecewise-linear nodal convention. Velocity L1
uses accepted interval velocities, without impact alignment or smoothing.
"""
from pathlib import Path
import copy
import datetime
import math
import sys
import traceback
import numpy as np
import paired_deadline_campaign_v1 as c

api = c.api
UNITS = c.OUT.parent / 'audit_units_01'
PREFIX = c.OUT.parent / 'prefix_audit_01'


def arrays(rows, state):
    initial = [0., *state['position_m'], *state['orientation'], *state['velocity_generalized']]
    return np.array([initial] + [[r['time_s'], *r['position_m'], *r['orientation'], *r['velocity_generalized']] for r in rows], float)


def metrics(a, b, minor_radius, speed, chunk=100000):
    """O(chunk) working arrays, plus two contiguous time vectors.

    Column layout: time, position(3), axis(3), generalized velocity(6).
    The comparison stops at the earlier actual endpoint; never extrapolates an
    exited trajectory. Endpoint-q therefore means common-clock endpoint-q.
    """
    api.require(len(a) > 1 and len(b) > 1 and a.shape[1] == b.shape[1] == 13, 'trace shape')
    ta, tb = np.array(a[:, 0]), np.array(b[:, 0])
    api.require(ta[0] == tb[0] == 0. and np.all(np.diff(ta) > 0) and np.all(np.diff(tb) > 0), 'strict trace clocks')
    api.require(minor_radius > 0 and speed > 0 and chunk > 0, 'metric scales')
    stop = min(ta[-1], tb[-1]); left = 0.; partials = []; px = pa = sup = 0.

    def interp(values, times, grid):
        j = np.clip(np.searchsorted(times, grid, side='left'), 1, len(times)-1)
        fraction = (grid-times[j-1])/(times[j]-times[j-1])
        return values[j-1, 1:7] + fraction[:, None]*(values[j, 1:7]-values[j-1, 1:7])

    for i in range(1, len(a), chunk):
        right = min(ta[min(i+chunk-1, len(a)-1)], stop)
        if right <= left: break
        aa = ta[np.searchsorted(ta, left, side='right'):np.searchsorted(ta, right, side='left')]
        bb = tb[np.searchsorted(tb, left, side='right'):np.searchsorted(tb, right, side='left')]
        grid = np.unique(np.r_[left, aa, bb, right])
        difference = interp(a, ta, grid)-interp(b, tb, grid)
        px = max(px, float(np.max(np.linalg.norm(difference[:, :3], axis=1)))/minor_radius)
        pa = max(pa, float(np.max(np.linalg.norm(difference[:, 3:6], axis=1))))
        # Right endpoints select the q belonging to the preceding interval.
        qa = a[np.searchsorted(ta, grid[1:], side='left'), 7:13]
        qb = b[np.searchsorted(tb, grid[1:], side='left'), 7:13]
        errors = np.linalg.norm(qa-qb, axis=1)/speed
        partials.append(float(np.dot(errors, np.diff(grid))))
        sup = max(sup, float(errors.max())); left = right
        if right == stop: break
    api.require(left == stop, 'complete common-clock coverage')
    qa = a[np.searchsorted(ta, stop), 7:13]; qb = b[np.searchsorted(tb, stop), 7:13]
    integral = math.fsum(partials)
    return {'common_stop_s': float(stop), 'whole_position_over_b_max': px, 'whole_axis_vector_norm_max': pa,
            'endpoint_q_over_U_max': float(np.linalg.norm(qa-qb))/speed,
            'mean_L1_q_over_U_max': integral/stop, 'integrated_q_error_over_U_s': integral,
            'interval_velocity_sup_over_U_diagnostic_only': sup,
            'endpoint_convention': 'At the earlier actual end time; no extension beyond outlet export.'}


def make_monitor(spec):
    cfg = spec['config']; trap = cfg['trap']
    return api.frozen.core.trap_event_v2.TrapMonitor(cfg['target_mean_interstitial_velocity_m_s'],
        cfg['prolate_semiaxes_m'][1], trap['dwell_time_s'], speed_ratio=trap['speed_ratio'],
        drift_over_minor_radius=trap['drift_over_minor_radius'])


def check_rows(record, monitor, accumulated):
    r = record['result']; state = r['checkpoint']['state']
    for row in record['rows']:
        reproduced = monitor.update(row['dt_s'], row['position_m'], row['velocity_generalized'],
                                    row['active_contact_ids'], row['supported_bearing_ids'])
        api.require(reproduced == row['dwell'], 'independent whole-row dwell replay')
        if reproduced['persistent_contact_observed'] and accumulated['first_dwell_s'] is None:
            accumulated['first_dwell_s'] = row['time_s']
        accumulated['supported_steps'] += bool(row['supported_bearing_ids'])
        accumulated['active_steps'] += bool(row['active_contact_ids'])
        accumulated['active_duration_s'] += row['dt_s'] if row['active_contact_ids'] else 0.
        accumulated['supported_duration_s'] += row['dt_s'] if row['supported_bearing_ids'] else 0.
    api.require(api.digest(monitor.__dict__) == api.digest(state['monitor']), 'full monitor-state identity')
    api.require(record['rows'][-1]['dwell'] == state['last_trap_state'] == r['trap_state'], 'final dwell state identity')
    api.require(accumulated['first_dwell_s'] == r['first_contact_dwell_time_s'] == state['first_contact_dwell_time'], 'first dwell time')
    api.require((accumulated['first_dwell_s'] is not None) == r['persistent_contact_observed'] == state['persistent_contact_observed'], 'dwell verdict')
    api.require(accumulated['supported_steps'] <= r['contact_steps'] <= accumulated['active_steps'] <= r['steps'], 'contact accounting bounds')
    for cert in record['certificates']:
        api.require(cert['roundoff_certificate_used'] and cert['exact_rational_inputs'] and cert['correctly_rounded_velocity_sum'], 'closure certificate flags')
        api.require(0 <= cert['force_residual'] <= 1e-8 and 0 < cert['mobility_condition_number'] <= 1e8, 'closure certificate limits')
        api.require(all(math.isfinite(v) for v in cert.values() if type(v) in (int, float)), 'finite certificate')
    accumulated['closure_certificates'] += len(record['certificates'])


def case_audit(d, case, paths, folder, terminal):
    spec = case['spec']; binding = c.case_binding(d, case); cp = None
    # Sidecar/entry counts allocate the disk-backed table; the raw loop checks them.
    if terminal:
        cr = api.read(c.RUN / case['id'] / 'case_result.json')
        count = sum(entry['steps'] for entry in cr['entries'])
    else:
        count = sum(len(c.storage.read_record(p, api.sha(c.DESIGN))['rows']) for p in paths)
    api.require(0 < count <= case['step_ceiling'], 'nonempty bounded audited prefix')
    path = folder / (case['id'] + '.npy'); api.require(not path.exists(), 'occupied trace table')
    trace = np.lib.format.open_memmap(path, mode='w+', dtype=np.float64, shape=(count+1, 13))
    trace[0] = [0., *spec['initial_state']['position_m'], *spec['initial_state']['orientation'], *spec['initial_state']['velocity_generalized']]
    monitor = make_monitor(spec)
    totals = {'first_dwell_s': None, 'supported_steps': 0, 'active_steps': 0, 'active_duration_s': 0., 'supported_duration_s': 0., 'closure_certificates': 0}
    hashes = {}; position = 1; runtime = 0.
    for index, raw in enumerate(paths, 1):
        api.require(raw.name == f'segment_{index:05d}.json.gz', 'ordered contiguous segments')
        rec = c.storage.read_record(raw, api.sha(c.DESIGN)); r = rec['result']
        c.check(rec, cp, spec, binding, d['budget']['step_cap_per_call'])
        api.require(rec['declared_total_step_ceiling'] == case['step_ceiling'] and r['steps'] <= case['step_ceiling'], 'case step budget')
        if terminal:
            entry = cr['entries'][index-1]
            api.require(entry == {'path': str(raw), 'sha256': api.sha(raw), 'seal_sha256': api.sha(raw.with_suffix('.seal.json')), 'steps': len(rec['rows']), 'time_s': r['time_s']}, 'case entry binding')
        check_rows(rec, monitor, totals)
        nextcp = r['checkpoint']
        if cp is not None:
            previous = cp['state']; now = nextcp['state']
            api.require(now['history'][:len(previous['history'])] == previous['history'], 'immutable history prefix')
            for key in ['max_momentum', 'max_contact_residual', 'max_force_residual', 'max_reynolds', 'contact_steps', 'total_contact_iterations']:
                api.require(now[key] >= previous[key], 'cumulative diagnostic monotonicity '+key)
            api.require(now['minimum_gap'] <= previous['minimum_gap'], 'cumulative clearance')
        api.require(not nextcp['state'].get('pending_trial') and not nextcp['state'].get('rejected_trials'), 'no unresolved/rejected trial')
        data = np.asarray([[row['time_s'], *row['position_m'], *row['orientation'], *row['velocity_generalized']] for row in rec['rows']], float)
        trace[position:position+len(data)] = data; position += len(data)
        cp = nextcp; runtime += r['runtime_seconds']
        hashes[str(raw)] = api.sha(raw); hashes[str(raw.with_suffix('.seal.json'))] = api.sha(raw.with_suffix('.seal.json'))
        api.require(index == len(paths) or r['status'] not in c.TERMINAL, 'no post-terminal segment')
    api.require(position == len(trace) and cp['state']['steps'] == count, 'complete fresh trace accounting')
    trace.flush(); del trace
    if terminal:
        api.require(cr['final_result'] == r and cr['integration_runtime_s'] == runtime, 'terminal result and runtime identity')
        api.require(cr['complete_observation'] == (r['status'] in c.TERMINAL), 'observation completeness')
    return {'case_id': case['id'], 'sample_id': case['sample_id'], 'shape': case['shape'], 'factor': case['factor'],
        'status': r['status'], 'complete_observation': r['status'] in c.TERMINAL, 'steps': count,
        'observed_s': r['time_s'], 'observed_pv': r['time_s']*spec['field_metadata']['pv_per_second'],
        'integration_runtime_s': runtime, 'health': c.engine.prior.reference.independent_health(r, spec),
        'dwell': totals, 'raw_artifacts': hashes, 'trace_path': str(path), 'trace_sha256': api.sha(path),
        'export_observed': r['status'] == 'full_window_exit', 'final_position_m': r['position_m'],
        'final_orientation': r['orientation'], 'final_velocity_generalized': r['velocity_generalized']}


def pair_gates(d, first, second, spec):
    if not (first['complete_observation'] and second['complete_observation']):
        return {'passed': False, 'reason': 'incomplete observation; no extrapolation'}
    a = np.load(first['trace_path'], mmap_mode='r'); b = np.load(second['trace_path'], mmap_mode='r')
    m = metrics(a, b, spec['config']['prolate_semiaxes_m'][1], spec['config']['target_mean_interstitial_velocity_m_s'])
    gates = d['numerical_gates']
    checks = {key: m[key] <= gates[key] for key in ['whole_position_over_b_max', 'whole_axis_vector_norm_max', 'endpoint_q_over_U_max', 'mean_L1_q_over_U_max']}
    checks['same_terminal_label'] = first['status'] == second['status']
    checks['exit_time_difference'] = abs(first['observed_s']-second['observed_s']) <= gates['exit_time_difference_s_max']
    da, db = first['dwell']['first_dwell_s'], second['dwell']['first_dwell_s']
    checks['same_dwell_flag'] = (da is None) == (db is None)
    checks['first_dwell_time_difference'] = (da is None and db is None) or (da is not None and db is not None and abs(da-db) <= gates['first_dwell_time_difference_s_max'])
    return {'passed': all(checks.values()), 'checks': checks, 'metrics': m,
            'selected_case': first['case_id'], 'reference_case': second['case_id'],
            'terminal_time_difference_s': abs(first['observed_s']-second['observed_s'])}


def units(folder):
    d = api.read(c.DESIGN); c.verify(d)
    spec = d['cases'][0]['spec']; initial = spec['initial_state']; rng = np.random.default_rng(16701)
    tests = []
    for n, m, chunk in [(17, 31, 1), (120, 33, 7), (8, 220, 3), (3, 3, 100)]:
        def rows(size):
            ts = np.r_[np.sort(rng.uniform(.00001, .9999, size-1)), 1.]
            return [{'time_s': float(t), 'position_m': rng.normal(size=3).tolist(), 'orientation': rng.normal(size=3).tolist(), 'velocity_generalized': rng.normal(size=6).tolist()} for t in ts]
        ra, rb = rows(n), rows(m); a, b = arrays(ra, initial), arrays(rb, initial)
        speed = spec['config']['target_mean_interstitial_velocity_m_s']; minor = spec['config']['prolate_semiaxes_m'][1]
        got = metrics(a, b, minor, speed, chunk)
        old = c.b.old.parent.prior.common_trace(rb, {'rows': ra, 'spec': spec}, {'state': {'t': 0., 'x': initial['position_m'], 'p': initial['orientation'], 'q': initial['velocity_generalized']}})
        exact = c.b.q.diag.piecewise_l1(ra, rb, 0., 1., speed)['mean_norm_over_scale']
        api.require(np.isclose(got['whole_position_over_b_max'], old['position_over_b'], rtol=1e-14), 'chunked pose oracle')
        api.require(np.isclose(got['whole_axis_vector_norm_max'], old['axis_vector_norm'], rtol=1e-14), 'chunked axis oracle')
        api.require(np.isclose(got['mean_L1_q_over_U_max'], exact, rtol=1e-14), 'chunked interval L1 oracle')
        api.require(metrics(a, a, minor, speed, chunk)['mean_L1_q_over_U_max'] == 0., 'identity')
        tests.append({'n': n, 'm': m, 'chunk': chunk, 'oracle_passed': True})
    a = np.zeros((3, 13)); b = np.zeros((3, 13)); a[:, 0] = [0., .25, .75]; b[:, 0] = [0., .5, 1.]
    a[1:, 7] = 2.; b[1:, 7] = 1.
    unequal = metrics(a, b, 1., 1., 1)
    api.require(unequal['common_stop_s'] == .75 and unequal['mean_L1_q_over_U_max'] == 1. and unequal['endpoint_q_over_U_max'] == 1., 'unequal endpoint exact integral')
    bad = a.copy(); bad[1, 0] = 0.
    try: metrics(bad, b, 1., 1.)
    except RuntimeError: pass
    else: raise RuntimeError('duplicate clock accepted')
    return {'passed': True, 'random_oracles': tests, 'unequal_endpoint_test': unequal,
            'duplicate_clock_rejected': True, 'new_integration': False}


def evaluate(folder):
    d = api.read(c.DESIGN); c.verify(d); c.verify_preflight()
    u = api.read(UNITS / 'results.json')
    api.require(u['passed'] and u['evaluator_sha256'] == api.sha(__file__), 'auditor unit qualification')
    api.require(api.read(UNITS / 'completion.json')['results_sha256'] == api.sha(UNITS / 'results.json'), 'unit seal')
    root = api.read(c.RUN / 'completion.json')
    api.require(root['design_sha256'] == api.sha(c.DESIGN), 'terminal supervisor binding')
    failures = [str(p) for p in c.RUN.rglob('failure.json')]
    stderr = [str(p) for p in c.RUN.glob('*.stderr.txt') if p.stat().st_size]
    ids = [case['id'] for case in d['cases']]
    api.require([x['case_id'] for x in root['dispatch']] == ids[:len(root['dispatch'])], 'frozen dispatch order')
    records = []; artifacts = {str(c.RUN / 'completion.json'): api.sha(c.RUN / 'completion.json')}
    for case in d['cases']:
        directory = c.RUN / case['id']; result_path = directory / 'case_result.json'
        if not result_path.exists():
            records.append({'case_id': case['id'], 'sample_id': case['sample_id'], 'shape': case['shape'], 'factor': case['factor'], 'complete_observation': False, 'status': 'failed_or_unrun'})
            continue
        cr = api.read(result_path); seal = api.read(directory / 'completion.json')
        api.require(seal['result_sha256'] == api.sha(result_path) and cr['design_sha256'] == api.sha(c.DESIGN), 'case result binding')
        paths = [Path(e['path']) for e in cr['entries']]
        api.require(paths == sorted(directory.glob('segment_*.json.gz')), 'all case segments accounted')
        launch = api.read(directory / 'launch.json'); dispatch = next(x for x in root['dispatch'] if x['case_id'] == case['id'])
        api.require(launch['case_id'] == case['id'] and launch['design_sha256'] == api.sha(c.DESIGN) and launch['pid'] == dispatch['pid'], 'worker binding')
        if paths: records.append(case_audit(d, case, paths, folder, True))
        else: records.append({'case_id': case['id'], 'sample_id': case['sample_id'], 'shape': case['shape'], 'factor': case['factor'], 'complete_observation': False, 'status': cr['status']})
        artifacts.update({str(p): api.sha(p) for p in [result_path, directory/'completion.json', directory/'launch.json']})
        print('AUDITED', case['id'], flush=True)
    pairs = []
    for shape in ['equal_volume_sphere', 'rigid_prolate_ar4']:
        a, b = [next(r for r in records if r['sample_id'] == 0 and r['shape'] == shape and r['factor'] == f) for f in [.0625, .03125]]
        spec = next(x['spec'] for x in d['cases'] if x['id'] == a['case_id'])
        pairs.append({'shape': shape, **pair_gates(d, a, b, spec)})
    complete = all(r['complete_observation'] for r in records)
    api.require(root['all_observations_complete'] == (not root['failures'] and not root['unrun_cases'] and complete), 'supervisor completeness reproduced')
    passed = complete and not failures and not stderr and all(p['passed'] for p in pairs)
    c.verify(d); c.verify_preflight()
    return {'passed': passed, 'all_observations_complete': complete, 'records': records, 'full_path_comparisons': pairs,
            'failure_markers': failures, 'nonempty_stderr': stderr, 'artifacts': artifacts,
            'total_accepted_steps': sum(r.get('steps', 0) for r in records), 'claim': d['claim'],
            'population_release_estimated': False, 'empirical_validation': False,
            'health_scope': 'All segment cumulative health bounds and recorded closure certificates rechecked; no fresh force solve or mechanical rerun performed.'}


def prefix(folder):
    d = api.read(c.DESIGN); c.verify(d); c.verify_preflight()
    reports = []
    for case in d['cases'][:3]:
        paths = [p for p in sorted((c.RUN / case['id']).glob('segment_*.json.gz')) if p.with_suffix('.seal.json').exists()][:2]
        api.require(len(paths) == 2, 'two fully sealed segments required for prefix test')
        reports.append(case_audit(d, case, paths, folder, False))
    return {'passed': True, 'scope': 'First two immutable segments of each initial worker only; not full-path qualification.', 'records': reports, 'new_integration': False}


if __name__ == '__main__':
    owned = None
    try:
        mode = sys.argv[1]
        folder = {'units': UNITS, 'prefix': PREFIX, 'evaluate': c.OUT}[mode]
        # A live run is not a terminal result; do not create a spurious failed audit.
        if mode == 'evaluate': api.require((c.RUN/'completion.json').exists(), 'supervisor still running')
        folder.mkdir(parents=True, exist_ok=False); owned = folder
        result = {'units': units, 'prefix': prefix, 'evaluate': evaluate}[mode](folder)
        result.update(evaluator_sha256=api.sha(__file__), design_sha256=api.sha(c.DESIGN), utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        api.write(folder/'results.json', result, raw=True)
        api.write(folder/'completion.json', {'passed': result['passed'], 'results_sha256': api.sha(folder/'results.json')})
        print(mode.upper(), result['passed'], flush=True)
    except Exception as error:
        if owned is not None: api.write(owned/'failure.json', {'error': repr(error), 'traceback': traceback.format_exc()})
        raise
