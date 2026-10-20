"""Six immutable fresh trajectories, three isolated CPU workers, no new physics.

Commands: prepare; preflight; run; worker CASE; probe TAG.
No command resumes an occupied case. A supervisor failure requests cooperative
stopping between segments; no process is killed and no failed case is replaced.
"""
from pathlib import Path
import copy
import datetime as dt
import os
import shutil
import subprocess
import sys
import time
import traceback
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage166_staging'))
import selected_step_adjudication_v1 as selection
b = selection.b
api, model, engine, storage, fix = b.api, b.model, b.engine, b.storage, b.fix
BASE = 'paired_full_path_deadline_20260922'
DESIGN = ROOT / 'stage167_designs' / BASE / 'design_01.json'
RUN = ROOT / 'stage167_runs' / BASE / 'run_01'
PREFLIGHT = ROOT / 'stage167_evaluations' / BASE / 'preflight_01'
OUT = ROOT / 'stage167_evaluations' / BASE / 'evaluation_01'
SELF = Path(__file__).resolve()
TERMINAL = {'present_at_horizon', 'full_window_exit'}


def utc():
    return dt.datetime.now(dt.timezone.utc)


def source_map():
    return {str(Path(m.__file__).resolve()): api.sha(m.__file__) for m in list(sys.modules.values())
            if getattr(m, '__file__', None) and Path(m.__file__).suffix == '.py' and ROOT in Path(m.__file__).resolve().parents}


def prepare():
    sd, sr = selection.verify()
    bd = api.read(b.DESIGN); br = api.read(b.OUT / 'results.json')
    population_path = ROOT / 'stage95_designs/common_admissible_population_01/starts_s2.json'
    protocol_path = ROOT / 'stage109_designs/shape_flow_protocol_20260914/protocol.json'
    protocol = api.read(protocol_path); starts = api.read(population_path)
    api.require(protocol['input_hashes'][str(population_path)] == api.sha(population_path), 'population hash')
    order = np.random.Generator(np.random.PCG64(109003)).permutation(np.arange(1, 256))
    api.require(sorted(map(int, order[:10])) == protocol['population']['pilot_ids']['2'], 'reproduce original pilot selection')
    pilot_id = int(order[0])
    api.require(pilot_id not in protocol['population']['heldout_ids']['2'], 'do not consume held-out data')
    # Longest reference starts first. No ordering depends on observed transport.
    matrix = [(0, 'rigid_prolate_ar4', .03125), (0, 'rigid_prolate_ar4', .0625),
              (0, 'equal_volume_sphere', .03125), (0, 'equal_volume_sphere', .0625),
              (pilot_id, 'rigid_prolate_ar4', .0625), (pilot_id, 'equal_volume_sphere', .0625)]
    cases = []
    for sample, shape, factor in matrix:
        spec = copy.deepcopy(next(c['spec'] for c in bd['cases'] if c['shape'] == shape and c['factor'] == factor))
        name = f's2_i{sample}_{"fibre" if shape == "rigid_prolate_ar4" else "sphere"}_f{str(factor).replace(".","p")}'
        start = starts[sample]
        spec.update(case_id=name, horizon_pv=.1, horizon_s=.1 / spec['field_metadata']['pv_per_second'])
        spec['initial_state'] = {'position_m': start['position_m'], 'orientation': start['orientation'],
                                 'velocity_generalized': start['initial_velocity_generalized']}
        spec['config'].update(horizon_pore_volumes=.1, status='frozen_fresh_paired_development',
            packings=[{'seed': 2, 'sample_id': sample}], selection_rule='Known sample-0 development sentinel plus first original Stage109 seed-2 randomized pilot ID; selected before new transport outcomes.',
            purpose='Matched fresh sphere/fibre finite-horizon transport and full-path numerical comparison.',
            claim_boundary='Two labelled placements at one packing/flow; not a population release estimate, flow trend, empirical validation or completed 180-case campaign.')
        for key in ['parent_stage55_design_sha256', 'stage85_preflight_results_sha256']:
            spec['config'].pop(key, None)
        cases.append({'id': name, 'sample_id': sample, 'role': 'known_development' if sample == 0 else 'prospective_pilot',
                      'shape': shape, 'factor': factor, 'spec': spec, 'step_ceiling': 20_000_000 if factor == .03125 else 10_000_000})
    cutoff = dt.datetime.fromisoformat(sd['deadline']['utc']) - dt.timedelta(hours=4)
    q_result = api.read(b.q.OUT / 'results.json')
    rates = {factor: max(cost['seconds_per_simulated_second'] for window in q_result['windows'] for cost in window['cost'] if cost['factor'] == factor)
             for factor in [.0625, .03125]}
    critical_hours = cases[0]['spec']['horizon_s'] * rates[.03125] * 1.3 / 3600
    api.require((cutoff-utc()).total_seconds()/3600 >= critical_hours, 'conservative fibre critical path exceeds audit cutoff')
    probe_path = b.q.RUN / 'engagement/factor_0.0625/segment_10.json'
    probe = api.read(probe_path)
    api.require(probe['result']['contact_steps'] > 0, 'parallel resource probe must exercise contact')
    inputs = [selection.DESIGN, selection.OUT / 'results.json', selection.OUT / 'completion.json', b.DESIGN,
              b.OUT / 'results.json', b.AUDIT / 'results.json', b.q.DESIGN, b.q.OUT / 'results.json',
              population_path, protocol_path, ROOT / 'stage109_staging/freeze_stage_a_v1.py', probe_path]
    design = {'stage': 'Stage167', 'cases': cases, 'selected_factor': .0625, 'reference_factor': .03125,
        'pilot_id': pilot_id, 'deadline': sd['deadline'], 'simulation_cutoff_utc': cutoff.isoformat(),
        'budget': {'workers': 3, 'threads': 1, 'step_cap_per_call': 10000, 'max_calls_per_case': 10000,
                   'max_new_steps_total': 80_020_000, 'minimum_free_disk_bytes': 20*1024**3,
                   'runtime_margin': 1.3, 'contact_probe_steps': 1000},
        'cost': {'fibre_contact_rates_s_per_simulated_s': rates, 'critical_path_hours_with_margin': critical_hours,
                 'available_hours_at_freeze': (cutoff-utc()).total_seconds()/3600,
                 'limitations': 'Measured short-window extrapolations; contact occupancy and other system activity may change costs. Queued pilot cases remain unresolved if the deadline is reached.'},
        'contact_probe_path': str(probe_path),
        'numerical_gates': {'whole_position_over_b_max': .02, 'whole_axis_vector_norm_max': .01,
            'endpoint_q_over_U_max': .005, 'mean_L1_q_over_U_max': .005, 'exit_time_difference_s_max': .0025,
            'same_terminal_label': True, 'same_dwell_flag': True, 'first_dwell_time_difference_s_max': .0025},
        'gate_basis': 'Retain prior Stage135 full-path pose/event budgets; use the unchanged Stage164/165 0.005-U endpoint and mean-L1 velocity limits. No uniform impact-velocity norm gate. Conditional three-level evidence remains separate from this two-level full-path comparison.',
        'observation': 'Fresh t=0 to exact 0.1 PV (4.682 s), or first whole-body downstream export. Nonabsorbing contact dwell; unchanged fixed sand/CPD6 steady field, rigid AR4/equal-volume sphere, one-way forcing.',
        'claim': 'Finite-horizon paired development observations; one independent pilot placement. No population release fraction, absolute permeability validation, new flow level, coupled physics or asymptotic-order claim.',
        'stop': 'Any source, health, numerical or worker failure prevents further dispatch. Preserve every prefix and unresolved denominator. Cooperative deadline/disk stop only; never terminate/restart/overwrite a process or run.',
        'inputs': {str(p): api.sha(p) for p in inputs}, 'sources': source_map()}
    design['binding'] = api.digest(design)
    DESIGN.parent.mkdir(parents=True, exist_ok=True); api.write(DESIGN, design)
    print('FROZEN', api.sha(DESIGN), 'pilot', pilot_id, 'critical_hours', critical_hours, flush=True)


def verify(d):
    api.require(d['binding'] == api.digest({k: v for k, v in d.items() if k != 'binding'}), 'design digest')
    api.verify_mapping(d['inputs']); api.verify_mapping(d['sources']); selection.verify()
    api.require(all(os.environ.get(k) == '1' for k in b.old.parent.THREADS), 'one BLAS/OpenMP thread')


def case_binding(d, c):
    return api.digest([d['binding'], c['id']])


def check(rec, before, spec, binding, cap):
    r, rows = rec['result'], rec['rows']
    t0 = 0. if before is None else before['state']['t']
    n0 = 0 if before is None else before['state']['steps']
    effective = model.binding_for(binding, True)
    api.require(rec['input_checkpoint_sha256'] == api.digest(before) and rec['effective_binding'] == effective, 'checkpoint input/binding')
    api.require(rec['spec'] == spec and r['checkpoint']['contract'] == engine.prior.contracts.expected_contract(spec, effective), 'resolved spec/contract')
    state = r['checkpoint']['state']
    api.require(r['checkpoint']['state_sha256'] == api.digest(state), 'checkpoint state hash')
    api.require(state['t'] == r['time_s'] and state['steps'] == r['steps'] and state['x'] == r['position_m'] and state['q'] == r['velocity_generalized'], 'state/result identity')
    api.require(engine.prior.reference.independent_health(r, spec)['passed'], 'independent physical/numerical health')
    api.require(b.old.parent.prior.w.prior.audit.clock_chain(t0, rows, r['time_s'])['passed'], 'exact accepted clock')
    api.require(0 < len(rows) == r['steps']-n0 <= cap, 'step accounting')
    api.require(r['rejected'] == (0 if before is None else before['state']['rejected']), 'no newly rejected trial')
    api.require(not r.get('stage119_repair_calls'), 'no unqualified solver repair')
    api.require(len(rec['backend_calls']) == 1 and rec['backend_calls'][0]['enabled'], 'one bound rigid backend')
    api.require(r['status'] in TERMINAL | {'paused_checkpoint', 'incomplete_budget'}, 'unexpected status')
    api.require(r['status'] != 'present_at_horizon' or r['time_s'] == spec['horizon_s'], 'exact horizon status')
    api.require(r['time_s'] != spec['horizon_s'] or r['status'] in TERMINAL, 'horizon requires terminal observation')
    api.require(t0 < r['time_s'] <= spec['horizon_s'], 'forward clock within horizon')
    api.require(rows[-1]['position_m'] == r['position_m'] and np.allclose(rows[-1]['orientation'], r['orientation'], rtol=0, atol=1e-12), 'last row/result pose')
    values = np.asarray([[row['time_s'], row['dt_s'], *row['position_m'], *row['orientation'], *row['velocity_generalized']] for row in rows])
    api.require(np.isfinite(values).all(), 'finite whole trace')


def execute(d, spec, binding, cp, path, cap, ceiling):
    before = copy.deepcopy(cp); nc, nf = len(model.calls), len(fix.telemetry)
    started = time.perf_counter()
    with b.old.hot.scope(), storage.step_budget_scope(ceiling), fix.scope():
        result, rows = engine.runtime.execute(spec, binding, checkpoint=cp,
            pause=(0 if cp is None else cp['state']['steps']) + cap)
    rec = {'result': result, 'rows': rows, 'spec': spec, 'input_checkpoint_sha256': api.digest(before),
           'effective_binding': model.binding_for(binding, True), 'design_sha256': api.sha(DESIGN),
           'backend_calls': copy.deepcopy(model.calls[nc:]), 'certificates': copy.deepcopy(fix.telemetry[nf:]),
           'step_cap': cap, 'declared_total_step_ceiling': ceiling, 'compute_call_wall_s': time.perf_counter()-started}
    storage.write_record(path, rec)
    api.require(api.digest(storage.read_record(path, api.sha(DESIGN))) == api.digest(rec), 'lossless persisted record')
    check(rec, before, spec, binding, cap)
    return rec


def probe_spec(d):
    saved = api.read(d['contact_probe_path'])
    spec = saved['spec']; binding = api.digest([d['binding'], 'contact_parallel_identity'])
    cp = model.checkpoint(spec, binding, saved['result']['checkpoint'], True)
    return spec, binding, cp


def probe(tag):
    d = api.read(DESIGN); verify(d); b.old.parent.configure()
    spec, binding, cp = probe_spec(d)
    path = PREFLIGHT / (tag + '.json.gz')
    r = execute(d, spec, binding, cp, path, d['budget']['contact_probe_steps'], 20_000_000)
    print(tag, r['result']['runtime_seconds'], flush=True)


def start_child(command, folder, tag):
    stdout = (folder / (tag + '.stdout.txt')).open('xb')
    stderr = (folder / (tag + '.stderr.txt')).open('xb')
    try:
        p = subprocess.Popen([sys.executable, '-B', '-u', str(SELF), *command], cwd=ROOT,
                             stdout=stdout, stderr=stderr, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    finally:
        stdout.close(); stderr.close()
    return p


def preflight():
    d = api.read(DESIGN); verify(d); PREFLIGHT.mkdir(parents=True, exist_ok=False)
    b.old.parent.configure(); spec, binding, cp = probe_spec(d)
    base = execute(d, spec, binding, cp, PREFLIGHT / 'serial.json.gz', 1000, 20_000_000)
    first = execute(d, spec, binding, cp, PREFLIGHT / 'split_first.json.gz', 571, 20_000_000)
    last = execute(d, spec, binding, first['result']['checkpoint'], PREFLIGHT / 'split_last.json.gz', 429, 20_000_000)
    api.require(base['rows'] == first['rows'] + last['rows'] and base['result']['checkpoint']['state'] == last['result']['checkpoint']['state'], 'exact contact restart with production resource wrapper')
    children = [start_child(['probe', f'parallel_{i}'], PREFLIGHT, f'parallel_{i}') for i in range(3)]
    api.write(PREFLIGHT / 'launches.json', {'pids': [p.pid for p in children], 'design_sha256': api.sha(DESIGN)})
    while any(p.poll() is None for p in children): time.sleep(.2)
    api.require(all(p.returncode == 0 for p in children), 'parallel probe child failed')
    ratios = []
    for i in range(3):
        api.require((PREFLIGHT / f'parallel_{i}.stderr.txt').stat().st_size == 0, 'nonempty probe stderr')
        r = storage.read_record(PREFLIGHT / f'parallel_{i}.json.gz', api.sha(DESIGN))
        check(r, cp, spec, binding, 1000)
        api.require(r['rows'] == base['rows'] and r['result']['checkpoint']['state'] == base['result']['checkpoint']['state'], 'separate-process numerical identity')
        ratios.append(r['result']['runtime_seconds']/base['result']['runtime_seconds'])
    api.require(max(ratios) <= d['budget']['runtime_margin'], 'measured parallel slowdown exceeds reserved margin')
    # Frozen prospective pilot is checked, never reselected if inadmissible.
    for c in [c for c in d['cases'] if c['role'] == 'prospective_pilot']:
        execute(d, c['spec'], case_binding(d, c), None, PREFLIGHT / (c['id'] + '.json.gz'), 100, c['step_ceiling'])
    verify(d)
    result = {'passed': True, 'exact_contact_restart': True, 'parallel_identity': True,
              'parallel_runtime_ratios': ratios, 'accepted_steps': 5200,
              'design_sha256': api.sha(DESIGN), 'artifacts': {str(p): api.sha(p) for p in PREFLIGHT.rglob('*') if p.is_file()}}
    api.write(PREFLIGHT / 'results.json', result, raw=True)
    api.write(PREFLIGHT / 'completion.json', {'passed': True, 'results_sha256': api.sha(PREFLIGHT / 'results.json')})
    print('PREFLIGHT PASS', ratios, flush=True)


def verify_preflight():
    r = api.read(PREFLIGHT / 'results.json')
    api.require(r['passed'] and r['design_sha256'] == api.sha(DESIGN), 'preflight passed for this design')
    api.require(api.read(PREFLIGHT / 'completion.json')['results_sha256'] == api.sha(PREFLIGHT / 'results.json'), 'preflight seal')
    api.verify_mapping(r['artifacts'])


def worker(name):
    d = api.read(DESIGN); verify(d); verify_preflight()
    c = next(c for c in d['cases'] if c['id'] == name)
    folder = RUN / name; folder.mkdir(exist_ok=False)
    api.write(folder / 'launch.json', {'pid': os.getpid(), 'utc': utc().isoformat(), 'argv': sys.argv,
                                     'design_sha256': api.sha(DESIGN), 'case_id': name})
    b.old.parent.configure(); cp = None; entries = []; cost = 0.; status = 'not_started'; reason = None
    cutoff = dt.datetime.fromisoformat(d['simulation_cutoff_utc'])
    for n in range(1, d['budget']['max_calls_per_case']+1):
        if (RUN / 'STOP_REQUEST.json').exists(): reason = 'supervisor_cooperative_stop'; break
        if utc() >= cutoff: reason = 'audit_reserve_cutoff'; break
        if shutil.disk_usage(ROOT).free < d['budget']['minimum_free_disk_bytes']: reason = 'disk_reserve'; break
        if cp is not None and cp['state']['steps'] >= c['step_ceiling']: reason = 'step_budget'; break
        path = folder / f'segment_{n:05d}.json.gz'
        r = execute(d, c['spec'], case_binding(d, c), cp, path, d['budget']['step_cap_per_call'], c['step_ceiling'])
        cp = r['result']['checkpoint']; status = r['result']['status']; cost += r['result']['runtime_seconds']
        entries.append({'path': str(path), 'sha256': api.sha(path), 'seal_sha256': api.sha(path.with_suffix('.seal.json')),
                        'steps': len(r['rows']), 'time_s': r['result']['time_s']})
        print(name, n, status, 'steps', cp['state']['steps'], 't', cp['state']['t'], flush=True)
        if status in TERMINAL: break
    else: reason = 'call_budget'
    verify(d)
    result = {'case_id': name, 'status': status if status in TERMINAL else 'budget_incomplete', 'reason': reason,
              'complete_observation': status in TERMINAL, 'entries': entries, 'integration_runtime_s': cost,
              'final_result': r['result'] if entries else None, 'design_sha256': api.sha(DESIGN)}
    api.write(folder / 'case_result.json', result, raw=True)
    api.write(folder / 'completion.json', {'complete_observation': result['complete_observation'], 'result_sha256': api.sha(folder / 'case_result.json')})


def run():
    d = api.read(DESIGN); verify(d); verify_preflight()
    api.require(shutil.disk_usage(ROOT).free >= d['budget']['minimum_free_disk_bytes'], 'initial disk reserve')
    critical = d['cost']['critical_path_hours_with_margin']
    api.require((dt.datetime.fromisoformat(d['simulation_cutoff_utc'])-utc()).total_seconds()/3600 >= critical, 'launch misses conservative critical path budget')
    RUN.mkdir(parents=True, exist_ok=False)
    api.write(RUN / 'launch.json', {'pid': os.getpid(), 'utc': utc().isoformat(), 'design_sha256': api.sha(DESIGN),
        'argv': sys.argv, 'python': sys.version, 'threads': {k: os.environ.get(k) for k in b.old.parent.THREADS}})
    queue = list(d['cases']); active = {}; completed = []; failed = []; dispatch = []
    while queue or active:
        while queue and len(active) < d['budget']['workers'] and not failed and utc() < dt.datetime.fromisoformat(d['simulation_cutoff_utc']):
            c = queue.pop(0); p = start_child(['worker', c['id']], RUN, c['id'])
            active[c['id']] = p; dispatch.append({'case_id': c['id'], 'pid': p.pid, 'utc': utc().isoformat()})
            api.write(RUN / f'dispatch_{len(dispatch):02d}.json', dispatch[-1])
            print('DISPATCH', c['id'], 'PID', p.pid, flush=True)
        for name, p in list(active.items()):
            code = p.poll()
            if code is None: continue
            del active[name]
            healthy_exit = code == 0 and (RUN / name / 'completion.json').exists() and (RUN / (name + '.stderr.txt')).stat().st_size == 0
            if healthy_exit:
                completed.append(name); print('FINISHED', name, flush=True)
            else:
                failed.append({'case_id': name, 'exit_code': code})
                if not (RUN / 'STOP_REQUEST.json').exists():
                    api.write(RUN / 'STOP_REQUEST.json', {'reason': 'worker_failure', 'case_id': name, 'utc': utc().isoformat()})
        if not active and (failed or utc() >= dt.datetime.fromisoformat(d['simulation_cutoff_utc'])): break
        time.sleep(1.)
    result = {'design_sha256': api.sha(DESIGN), 'dispatch': dispatch, 'completed_processes': completed,
              'failures': failed, 'unrun_cases': [c['id'] for c in queue],
              'all_observations_complete': not failed and not queue and all(api.read(RUN / name / 'case_result.json')['complete_observation'] for name in completed)}
    api.write(RUN / 'completion.json', result)
    print('CAMPAIGN TERMINAL', result['all_observations_complete'], flush=True)


if __name__ == '__main__':
    owned = None
    try:
        args = sys.argv[1:]
        if args == ['prepare']: prepare()
        elif args == ['preflight']:
            api.require(not PREFLIGHT.exists(), 'occupied preflight'); owned = PREFLIGHT; preflight()
        elif args == ['run']:
            api.require(not RUN.exists(), 'occupied run'); owned = RUN; run()
        elif len(args) == 2 and args[0] == 'probe': probe(args[1])
        elif len(args) == 2 and args[0] == 'worker':
            api.require(not (RUN / args[1]).exists(), 'occupied case'); owned = RUN / args[1]; worker(args[1])
        else: raise ValueError('prepare | preflight | run | worker CASE | probe TAG')
    except Exception as error:
        if owned is not None and owned.exists() and not (owned / 'failure.json').exists():
            api.write(owned / 'failure.json', {'error': repr(error), 'traceback': traceback.format_exc(), 'utc': utc().isoformat()})
        raise
