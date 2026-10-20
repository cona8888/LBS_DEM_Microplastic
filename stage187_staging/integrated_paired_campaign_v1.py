"""Fresh six-case campaign with sealed prefix storage and a separate auditor.

All physics comes from previously qualified immutable modules. No resume or
overwrite command exists. Preparation and preflight never confer a pass on the
full observation. Simulation and autonomous-agent deadlines are distinct.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import copy
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / f'stage{s}_staging') for s in (183, 181, 180, 179, 185)]
import qualify_fallback_evidence_v1 as qualified
import audit_optimized_record_v2 as kernel
import capture_fallback_systems_v1 as capture
import streaming_path_metrics_v2 as path_metrics
import campaign_lifecycle_policy_v1 as policy

api, parent, fast = qualified.api, qualified.parent, qualified.fast
prior, codec, deadline = qualified.prior, qualified.codec, qualified.previous.candidate
SELF = Path(__file__).resolve()
BASE = 'integrated_paired_campaign_20260924'
DESIGN = ROOT / 'stage187_designs' / BASE / 'design_01.json'
RUN = ROOT / 'stage187_runs' / BASE / 'run_01'
PREFLIGHT = ROOT / 'stage187_runs' / BASE / 'preflight_01'
OUT = ROOT / 'stage187_evaluations' / BASE
WORK = ROOT / 'stage187_designs/eight_hour_work_20260924/contract_01.json'
HANDOFF = ROOT / 'stage186_designs/next_campaign_handoff_20260924/preparation_01.json'
PREFLIGHT_SCRIPT = SELF.with_name('qualify_integrated_campaign_v1.py')


def utc():
    return datetime.now(timezone.utc)


def commit(path, data):
    """Exclusive atomic Windows publication: occupied or pending files fail."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f'.pending.{os.getpid()}')
    if path.exists() or temp.exists():
        raise FileExistsError(str(path))
    with temp.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2, sort_keys=True, allow_nan=True, default=api.frozen.h.json_value)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    api.require(os.name == 'nt', 'qualified exclusive Windows rename')
    os.rename(temp, path)


def latch(root, reason, detail=None):
    try:
        commit(root / 'stop_requested.json', {'reason': reason, 'detail': detail, 'utc': utc().isoformat()})
    except FileExistsError:
        pass


def failure(root, role, error):
    detail = {'role': role, 'error': repr(error), 'traceback': traceback.format_exc(), 'utc': utc().isoformat()}
    path = root / (role + '.failure.json')
    if not path.exists():
        commit(path, detail)
    latch(root, 'failure', detail)


def source_map():
    sources = parent.source_map()
    for path in (SELF, PREFLIGHT_SCRIPT):
        sources[str(path)] = api.sha(path)
    return sources


def prepare():
    work = api.read(WORK)
    api.require(utc() < policy.utc(work['agent_work_end_utc']), 'agent work window')
    old = api.read(parent.DESIGN)
    api.require(api.sha(parent.DESIGN) == '79834baa71a68a7e9a20901763a8779481d1a620dc0f48a13bca3fe884b1de84', 'original design')
    h = api.read(HANDOFF)
    api.require(h['cases'] == old['cases'] and h['numerical_gates'] == old['numerical_gates'] == policy.GATES, 'frozen scientific contract')
    summary = ROOT / 'stage186_evaluations/next_campaign_handoff_20260924/handoff_01/results.json'
    r = api.read(summary)
    api.require(r['passed'] and r['manifest_sha256'] == api.sha(HANDOFF), 'qualified preparation')
    api.require(api.read(summary.parent / 'completion.json')['results_sha256'] == api.sha(summary), 'handoff seal')
    qualified.verify(api.read(qualified.DESIGN))
    sources = source_map()
    inputs = {str(p): api.sha(p) for p in (WORK, HANDOFF, parent.DESIGN, summary, summary.parent / 'completion.json', qualified.DESIGN, qualified.OUT / 'results.json', qualified.OUT / 'completion.json')}
    d = {'stage': 'Stage187 integrated fresh six-case campaign', 'cases': copy.deepcopy(old['cases']),
         'numerical_gates': copy.deepcopy(old['numerical_gates']), 'budget': copy.deepcopy(old['budget']),
         'sources': sources, 'inputs': inputs, 'physical_changes': [], 'fresh_start_required': True,
         'simulation_cutoff_utc': work['simulation_cutoff_utc'], 'final_audit_deadline_utc': work['final_audit_deadline_utc'],
         'agent_work_end_utc': work['agent_work_end_utc'], 'resource_scenario': h['resource_scenario'],
         'minimum_gap_semantics': api.read(qualified.DESIGN)['minimum_gap_semantics'],
         'audit_source_sha256': api.sha(kernel.__file__), 'maximum_unverified_segments_per_case': 2,
         'maximum_unverified_segments_total': 6, 'poll_seconds': .2, 'stop_reserve_seconds': 120,
         'preflight': {'maximum_new_steps': 40000, 'wall_seconds': 3600, 'steps_per_live_segment': 500,
                       'segments_per_live_case': 2, 'contact_probe_steps': 1000},
         'claim': h['claim'], 'historical_failures_unchanged': True,
         'guard': 'Run requires a passing independent integrated preflight bound to this exact design and all source hashes.'}
    d['binding'] = api.digest(d)
    DESIGN.parent.mkdir(parents=True, exist_ok=True); api.write(DESIGN, d)
    print('FROZEN', api.sha(DESIGN), flush=True)


def verify(d):
    api.require(d['binding'] == api.digest({k: v for k, v in d.items() if k != 'binding'}), 'design binding')
    api.verify_mapping(d['sources']); api.verify_mapping(d['inputs'])
    old = api.read(parent.DESIGN)
    api.require(d['cases'] == old['cases'] and d['numerical_gates'] == old['numerical_gates'] == policy.GATES and d['budget'] == old['budget'], 'unchanged cases, gates and resource ceilings')
    api.require(all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS')), 'BLAS1')


def binding(d, case):
    return api.digest([d['binding'], case['id']])


def paths(root, case, index):
    folder = root / case
    stem = f'segment_{index:05d}'
    return {'raw': folder / (stem + '.json.xz'), 'ready': folder / (stem + '.ready.json'),
            'receipt': folder / (stem + '.audit.json'), 'trace': folder / (stem + '.npy')}


def clear_telemetry():
    for records in (capture.records, fast.attempts, fast.telemetry, fast.old.telemetry,
                    parent.fix.telemetry, parent.model.calls, prior.candidate.records):
        records.clear()


def execute_segment(d, case, before, raw_path, cap, prefix, stop_utc):
    """The only integration call. Always persist returned raw evidence first."""
    clear_telemetry(); fast.capture_systems = True
    start = time.perf_counter(); spec = case['spec']; bound = binding(d, case)
    try:
        with prior.p.hot.scope(), parent.storage.step_budget_scope(case['step_ceiling']), parent.fix.scope(), \
             deadline.scope(parent.engine.runtime, stop_utc, True), capture.scope(parent.engine.runtime, True), prior.candidate.scope():
            result, rows = parent.engine.runtime.execute(spec, bound, checkpoint=before,
                pause=(0 if before is None else before['state']['steps']) + cap)
    except Exception as error:
        # Preserve all accessible input and diagnostics, mark unavailable accepted
        # state explicitly; never reconstruct it from a failed speculative solve.
        commit(raw_path.with_suffix('.exception.json'), {'case': case['id'], 'design_sha256': api.sha(DESIGN),
            'input_checkpoint': before, 'error': repr(error), 'traceback': traceback.format_exc(),
            'fallback_systems': copy.deepcopy(capture.records), 'early_attempts': copy.deepcopy(fast.attempts),
            'sweep_certificates': copy.deepcopy(prior.candidate.records),
            'accepted_prefix_unavailable_from_runtime': True, 'complete_observation': False})
        raise
    record = {'spec': spec, 'result': result, 'rows': rows, 'input_checkpoint_sha256': api.digest(before),
              'effective_binding': parent.model.binding_for(bound, True), 'design_sha256': api.sha(DESIGN),
              'step_cap': cap, 'declared_total_step_ceiling': case['step_ceiling'], 'compute_call_wall_s': time.perf_counter() - start,
              'early_attempts': copy.deepcopy(fast.attempts), 'repairs': copy.deepcopy(fast.old.telemetry),
              'backend_calls': copy.deepcopy(parent.model.calls), 'certificates': copy.deepcopy(parent.fix.telemetry),
              'sweep_certificates': copy.deepcopy(prior.candidate.records), 'fallback_systems': copy.deepcopy(capture.records),
              'minimum_gap_semantics': d['minimum_gap_semantics']}
    seal, next_prefix = codec.write_record(raw_path, record, prefix)
    clear_telemetry()
    return record, next_prefix, seal, time.perf_counter() - start


def root_for(mode):
    api.require(mode in ('campaign', 'preflight'), 'explicit execution mode')
    return RUN if mode == 'campaign' else PREFLIGHT / 'live'


def root_settings(d, root):
    launch = api.read(root / 'launch.json')
    api.require(launch['design_sha256'] == api.sha(DESIGN), 'owned run design')
    return launch


def stopping(d, root, launch):
    if (root / 'stop_requested.json').exists():
        return 'cooperative_stop'
    if utc() >= policy.utc(launch['stop_utc']) - timedelta(seconds=d['stop_reserve_seconds']):
        latch(root, 'cutoff_reserve'); return 'cutoff_reserve'
    if shutil.disk_usage(ROOT).free <= d['budget']['minimum_free_disk_bytes'] + 4 * codec.base.MAX_COMPRESSED:
        latch(root, 'disk_reserve'); return 'disk_reserve'
    return None


def acknowledged(d, pending):
    left = []
    for entry in pending:
        p = entry['paths']
        if not p['receipt'].exists():
            left.append(entry); continue
        receipt = api.read(p['receipt'])
        if receipt['status'] != 'independently_verified':
            raise RuntimeError('independent segment audit rejected ' + str(p['raw']))
        policy.verify_receipt(p, entry['case'], entry['index'], api.sha(DESIGN), d['audit_source_sha256'],
                              entry['before_sha'], entry['previous_receipt_sha'])
    return left


def worker(mode, name):
    d = api.read(DESIGN); verify(d); root = root_for(mode); launch = root_settings(d, root)
    case = next(c for c in d['cases'] if c['id'] == name)
    folder = root / name; folder.mkdir(exist_ok=False)
    commit(folder / 'launch.json', {'pid': os.getpid(), 'argv': sys.argv, 'utc': utc().isoformat(), 'design_sha256': api.sha(DESIGN)})
    parent.b.old.parent.configure(); cp = None; prefix = None; entries = []; pending = []; reason = None
    previous_receipt_path = None; result = None
    try:
        with prior.snapshot.scope(api, case['spec']['field_metadata']):
            api.fields.load(2, 1., 6)
            cap = d['budget']['step_cap_per_call'] if mode == 'campaign' else d['preflight']['steps_per_live_segment']
            call_limit = d['budget']['max_calls_per_case'] if mode == 'campaign' else d['preflight']['segments_per_live_case']
            for index in range(1, call_limit + 1):
                # For a per-case chain, publication of the predecessor audit is
                # needed before accepting the next receipt ancestry. Two sealed
                # records may be outstanding but never an unbounded queue.
                pending = acknowledged(d, pending)
                while len(pending) >= d['maximum_unverified_segments_per_case'] and not stopping(d, root, launch):
                    time.sleep(d['poll_seconds']); pending = acknowledged(d, pending)
                reason = stopping(d, root, launch)
                if reason: break
                n = 0 if cp is None else cp['state']['steps']
                if n >= case['step_ceiling']:
                    reason = 'step_ceiling'; break
                p = paths(root, name, index); before = copy.deepcopy(cp)
                rec, prefix, seal, elapsed = execute_segment(d, case, before, p['raw'], min(cap, case['step_ceiling'] - n), prefix, launch['stop_utc'])
                result = rec['result']; cp = result['checkpoint']
                marker = {'case': name, 'segment': index, 'design_sha256': api.sha(DESIGN),
                          'raw_path': str(p['raw']), 'raw_sha256': api.sha(p['raw']),
                          'seal_sha256': api.sha(p['raw'].with_suffix('.seal.json')),
                          'input_checkpoint_sha256': api.digest(before), 'steps': len(rec['rows']),
                          'transaction_seconds': elapsed}
                commit(p['ready'], marker); entries.append(marker)
                # Parent SHA becomes available before this successor is acked;
                # resolve it lazily from the immutable predecessor receipt.
                pending.append({'paths': p, 'case': name, 'index': index, 'before_sha': api.digest(before),
                                'previous_receipt_sha': None, 'previous_receipt_path': previous_receipt_path})
                previous_receipt_path = p['receipt']
                print('SEALED', name, index, 'steps', cp['state']['steps'], 't', cp['state']['t'], flush=True)
                if len(rec['rows']) == 0:
                    reason = 'zero_accepted_steps'; latch(root, reason, name); break
                if result['rejected'] != 0 or not parent.engine.prior.reference.independent_health(result, case['spec'])['passed']:
                    reason = 'numerical_failure'; latch(root, reason, name); break
                if result['status'] in policy.COMPLETE:
                    reason = 'observation_complete'; break
            else:
                reason = 'preflight_segment_limit' if mode == 'preflight' else 'call_limit'
            # Do not release a producer slot with healthy unacknowledged records:
            # three slots times two outstanding records is the global lag bound.
            while pending and not stopping(d, root, launch):
                pending = acknowledged(d, pending)
                if pending: time.sleep(d['poll_seconds'])
        verify(d)
        complete = bool(result and result['status'] in policy.COMPLETE and result['rejected'] == 0)
        record = {'case': name, 'reason': reason, 'entries': entries, 'final_result': result,
                  'complete_observation_producer_only': complete, 'design_sha256': api.sha(DESIGN)}
        commit(folder / 'result.json', record)
        commit(folder / 'completion.json', {'result_sha256': api.sha(folder / 'result.json'), 'design_sha256': api.sha(DESIGN)})
    except Exception as error:
        failure(root, name, error); raise


def receipt_parent(entry):
    parent_path = entry.get('previous_receipt_path')
    return None if parent_path is None else api.sha(parent_path)


# Keep lazy ancestry resolution explicit rather than weakening its check.
_acknowledged = acknowledged
def acknowledged(d, pending):
    resolved = []
    for entry in pending:
        item = dict(entry)
        if item['paths']['receipt'].exists():
            item['previous_receipt_sha'] = receipt_parent(item)
        resolved.append(item)
    return _acknowledged(d, resolved)


def audit_one(d, root, case, index, before, prefix, previous_sha, geometry):
    p = paths(root, case['id'], index); marker = api.read(p['ready'])
    api.require(marker['case'] == case['id'] and marker['segment'] == index and marker['design_sha256'] == api.sha(DESIGN), 'ready identity')
    api.require(marker['raw_path'] == str(p['raw']) and marker['raw_sha256'] == api.sha(p['raw']) and
                marker['seal_sha256'] == api.sha(p['raw'].with_suffix('.seal.json')), 'ready raw/seal binding')
    api.require(marker['input_checkpoint_sha256'] == api.digest(before), 'ready input ancestry')
    rec, next_prefix = codec.read_record(p['raw'], api.sha(DESIGN), prefix)
    summary = kernel.evaluate(rec, case['spec'], binding(d, case), before, geometry, api.sha(DESIGN), d['minimum_gap_semantics'])
    trace = np.array([[r['time_s'], *r['position_m'], *r['orientation'], *r['velocity_generalized']] for r in rec['rows']], dtype=np.float64)
    with p['trace'].open('xb') as stream:
        np.save(stream, trace, allow_pickle=False); stream.flush(); os.fsync(stream.fileno())
    receipt = {'case': case['id'], 'segment': index, 'ready_sha256': api.sha(p['ready']), 'raw_sha256': api.sha(p['raw']),
               'original_raw_sha256': next_prefix.original_sha256, 'trace_path': str(p['trace']), 'trace_sha256': api.sha(p['trace']),
               'previous_receipt_sha256': previous_sha, 'input_checkpoint_sha256': api.digest(before), 'summary': summary,
               'design_sha256': api.sha(DESIGN), 'audit_source_sha256': d['audit_source_sha256'], 'status': 'independently_verified'}
    commit(p['receipt'], receipt)
    return rec['result']['checkpoint'], next_prefix, api.sha(p['receipt']), summary


def auditor(mode):
    d = api.read(DESIGN); verify(d); root = root_for(mode); root_settings(d, root)
    parent.b.old.parent.configure(); _, data, meta = api.fields.load(2, 1., 6)
    geometry = prior.candidate.original.GrainGeometry(data['sand_centres_m'], data['sand_radii_m'], meta['cell_length_m'])
    order = [c['id'] for c in d['cases']]; expected = {n: 1 for n in order}
    states = {n: (None, None, None) for n in order}; poisoned = {}; items = []; cursor = 0
    try:
        while True:
            available = {n: {int(p.name.split('_')[1].split('.')[0]) for p in (root / n).glob('segment_*.ready.json')} for n in order}
            item, cursor = policy.next_audit(order, expected, available, cursor)
            if item is None:
                if (root / 'producers_complete.json').exists(): break
                # Producer stopping does not stop the independent evidence drain.
                time.sleep(d['poll_seconds']); continue
            name, index = item; case = next(c for c in d['cases'] if c['id'] == name); p = paths(root, name, index)
            try:
                api.require(name not in poisoned, 'unverified predecessor: ' + poisoned.get(name, ''))
                cp, prefix, prior_sha, summary = audit_one(d, root, case, index, *states[name], geometry)
                states[name] = (cp, prefix, prior_sha)
                items.append({'case': name, 'segment': index, 'receipt_sha256': prior_sha, 'passed': True, 'steps': summary['steps']})
                print('VERIFIED', name, index, summary['stop_s'], flush=True)
            except Exception as error:
                poisoned[name] = repr(error)
                detail = {'case': name, 'segment': index, 'status': 'audit_failed', 'error': repr(error),
                          'design_sha256': api.sha(DESIGN), 'ready_sha256': api.sha(p['ready']), 'traceback': traceback.format_exc()}
                if not p['receipt'].exists(): commit(p['receipt'], detail)
                items.append({**detail, 'passed': False}); latch(root, 'audit_failure', detail)
            expected[name] += 1
        # Detect holes, unannounced archives, stray pending writes and failures.
        for name in order:
            numbers = sorted(int(p.name.split('_')[1].split('.')[0]) for p in (root / name).glob('segment_*.ready.json'))
            api.require(numbers == list(range(1, expected[name])), 'missing/unprocessed ready predecessor')
        verify(d)
        commit(root / 'auditor_complete.json', {'passed': not poisoned, 'items': items, 'failures': poisoned, 'design_sha256': api.sha(DESIGN)})
    except Exception as error:
        failure(root, 'auditor', error); raise


def start_child(root, role, command):
    stdout = (root / (role + '.stdout.log')).open('xb'); stderr = (root / (role + '.stderr.log')).open('xb')
    args = [sys.executable, '-B', '-u', str(SELF), *command]
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', OMP_NUM_THREADS='1')
    try:
        process = subprocess.Popen(args, cwd=str(ROOT), env=env, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
    finally:
        stdout.close(); stderr.close()
    return process, args


def verify_preflight(d):
    folder = OUT / 'preflight_01'; r = api.read(folder / 'results.json')
    api.require(r['passed'] and r['design_sha256'] == api.sha(DESIGN) and r['new_steps'] <= d['preflight']['maximum_new_steps'], 'integrated preflight')
    api.require(api.read(folder / 'completion.json')['results_sha256'] == api.sha(folder / 'results.json'), 'preflight seal')
    api.verify_mapping(r['artifacts']); api.verify_mapping(r['sources'])
    api.require(max(r['parallel_slowdown_ratios']) <= 1.3 and r['independent_audit_passed'], 'original slowdown and audit gates')
    api.require(sum(c['step_ceiling'] for c in d['cases']) + r['new_steps'] <= d['budget']['max_new_steps_total'], 'inclusive campaign/preflight budget')
    api.require(r['exact_restart'] and r['parallel_identity'] and r['cutoff_and_failure_drain'], 'complete integration prerequisites')
    return r


def supervise(mode):
    d = api.read(DESIGN); verify(d); root = root_for(mode)
    api.require(utc() < policy.utc(d['agent_work_end_utc']), 'no new autonomous launch after work window')
    if mode == 'campaign':
        preflight = verify_preflight(d)
        required_hours = max(d['resource_scenario']['hours_with_margin'], preflight['refreshed_hours_with_margin'])
        api.require((policy.utc(d['simulation_cutoff_utc']) - utc()).total_seconds() / 3600 >= required_hours, 'conservative runtime gate')
        api.require(shutil.disk_usage(ROOT).free - d['budget']['minimum_free_disk_bytes'] >= d['resource_scenario']['bytes_with_margin'], 'conservative storage gate')
        stop_utc = d['simulation_cutoff_utc']
    else:
        stop_utc = min(utc() + timedelta(seconds=1200), policy.utc(d['agent_work_end_utc'])).isoformat()
    root.mkdir(parents=True, exist_ok=False)
    commit(root / 'launch.json', {'supervisor_pid': os.getpid(), 'argv': sys.argv, 'utc': utc().isoformat(),
                                'design_sha256': api.sha(DESIGN), 'mode': mode, 'stop_utc': stop_utc})
    life = policy.initial([c['id'] for c in d['cases']]); active = {}; dispatches = []; exits = {}; audit = None
    try:
        audit, argv = start_child(root, 'auditor', ['auditor', mode])
        commit(root / 'auditor_launch.json', {'pid': audit.pid, 'argv': argv, 'design_sha256': api.sha(DESIGN)})
        while life.queued or active:
            reason = stopping(d, root, root_settings(d, root))
            if reason: life = policy.stop(life, reason)
            if audit.poll() is not None:
                life = policy.stop(life, 'auditor_exited_before_producers'); latch(root, 'auditor_exited_before_producers')
            while True:
                life, name = policy.dispatch(life, d['budget']['workers'], audit.poll() is None)
                if name is None: break
                process, argv = start_child(root, name, ['worker', mode, name]); active[name] = process
                item = {'case': name, 'pid': process.pid, 'argv': argv, 'utc': utc().isoformat(), 'design_sha256': api.sha(DESIGN)}
                dispatches.append(item); commit(root / f'dispatch_{len(dispatches):02d}.json', item)
                print('DISPATCH', name, process.pid, flush=True)
            for name, process in list(active.items()):
                code = process.poll()
                if code is None: continue
                del active[name]; exits[name] = code
                sealed = (root / name / 'completion.json').exists() and (root / (name + '.stderr.log')).stat().st_size == 0
                life = policy.retire(life, name, code, sealed)
                if life.stop_reasons: latch(root, 'worker_retirement_failure', list(life.stop_reasons))
            if not active and life.stop_reasons: break
            time.sleep(d['poll_seconds'])
        commit(root / 'producers_complete.json', {'dispatches': dispatches, 'exit_codes': exits, 'unrun_cases': list(life.queued),
                'stop_reasons': list(life.stop_reasons), 'design_sha256': api.sha(DESIGN)})
        while audit.poll() is None: time.sleep(d['poll_seconds'])
        commit(root / 'completion.json', {'design_sha256': api.sha(DESIGN), 'auditor_exit_code': audit.returncode,
                'producer_exit_codes': exits, 'unrun_cases': list(life.queued), 'stop_reasons': list(life.stop_reasons),
                'utc': utc().isoformat(), 'all_owned_processes_retired': True})
        print('SUPERVISOR_TERMINAL', mode, exits, 'auditor', audit.returncode, flush=True)
    except Exception as error:
        failure(root, 'supervisor', error)
        while any(p.poll() is None for p in active.values()): time.sleep(d['poll_seconds'])
        if not (root / 'producers_complete.json').exists():
            commit(root / 'producers_complete.json', {'exception': repr(error), 'design_sha256': api.sha(DESIGN),
                   'exit_codes': {n: p.returncode for n, p in active.items()}, 'unrun_cases': list(life.queued)})
        if audit is not None:
            while audit.poll() is None: time.sleep(d['poll_seconds'])
        raise


def evaluate(mode):
    """Independent terminal assembler; raw physics is authenticated by receipts."""
    d = api.read(DESIGN); verify(d); root = root_for(mode)
    terminal = api.read(root / 'completion.json')
    api.require(terminal['design_sha256'] == api.sha(DESIGN) and terminal['all_owned_processes_retired'], 'retired supervisor bound to design')
    failure_files = [str(p) for p in root.rglob('*.failure.json')]
    stderr = [str(p) for p in root.glob('*.stderr.log') if p.stat().st_size]
    unsealed = [str(p) for p in root.rglob('*') if p.is_file() and ('.pending.' in p.name or p.name.endswith('.exception.json'))]
    observations = {}; traces = {}; artifacts = {}; total = 0; integrity = True; details = []
    saved_total = 0
    for case in d['cases']:
        name = case['id']; cp = None; prefix = None; previous_sha = None; chain = []; accepted = 0; reason = []
        record = None
        folder = root / name
        raw_paths = sorted(folder.glob('segment_*.json.xz'))
        # Count producer-declared saved steps separately from verified steps;
        # rejected audit evidence never disappears from the terminal ledger.
        declared_saved = 0
        for ready in folder.glob('segment_*.ready.json'):
            marker = api.read(ready)
            api.require(type(marker.get('steps')) is int and marker['steps'] >= 0, 'saved step inventory')
            declared_saved += marker['steps']
        saved_total += declared_saved
        try:
            for index, raw in enumerate(raw_paths, 1):
                p = paths(root, name, index)
                api.require(raw == p['raw'], 'contiguous exact raw filenames')
                policy.verify_receipt(p, name, index, api.sha(DESIGN), d['audit_source_sha256'], api.digest(cp), previous_sha)
                record, prefix = codec.read_record(raw, api.sha(DESIGN), prefix)
                receipt = api.read(p['receipt']); r = record['result']
                api.require(receipt['original_raw_sha256'] == prefix.original_sha256 and receipt['summary']['output_checkpoint_state_sha256'] == r['checkpoint']['state_sha256'], 'decoded raw and receipt endpoint')
                api.require(record['input_checkpoint_sha256'] == api.digest(cp) and record['spec'] == case['spec'], 'case raw ancestry')
                arr = np.load(p['trace'], mmap_mode='r', allow_pickle=False)
                api.require(arr.shape == (len(record['rows']), 13) and np.isfinite(arr).all(), 'trace dimensions and finiteness')
                api.require(np.array_equal(arr, np.array([[x['time_s'], *x['position_m'], *x['orientation'], *x['velocity_generalized']] for x in record['rows']])), 'trace exactly decoded raw')
                api.require(index == len(raw_paths) or r['status'] not in policy.COMPLETE, 'no records after terminal observation')
                cp = r['checkpoint']; accepted += len(arr); previous_sha = api.sha(p['receipt']); chain.append(str(p['trace']))
                for f in (*p.values(), raw.with_suffix('.seal.json')): artifacts[str(f)] = api.sha(f)
            api.require((folder / 'completion.json').exists(), 'producer completion present')
            done = api.read(folder / 'completion.json'); producer = api.read(folder / 'result.json')
            api.require(done['result_sha256'] == api.sha(folder / 'result.json') and producer['design_sha256'] == api.sha(DESIGN), 'sealed producer terminal result')
            api.require(len(producer['entries']) == len(raw_paths) and producer['final_result'] == (record['result'] if record else None), 'complete producer/raw inventory')
            api.require(accepted == declared_saved <= case['step_ceiling'], 'case exact saved/verified accounting and ceiling')
        except Exception as error:
            integrity = False; reason.append(repr(error))
        total += accepted
        last = {} if record is None else record['result']
        evidence = {'status': last.get('status', 'unrun'), 'steps': accepted, 'start_s': 0., 'stop_s': last.get('time_s'),
                    'rejected': last.get('rejected'), 'failure_markers': reason,
                    'pending_trial': last.get('checkpoint', {}).get('state', {}).get('pending_trial'),
                    'first_dwell_s': last.get('first_contact_dwell_time_s'), 'export_verified': last.get('status') == 'full_window_exit',
                    'raw_hashes_verified': not reason and record is not None, 'clock_steps_verified': not reason and record is not None,
                    'physics_verified': not reason and record is not None, 'fresh_start': True}
        observations[name] = policy.observation(evidence, case['spec']['horizon_s'])
        traces[name] = chain; details.append({'case': name, 'verified_accepted_steps': accepted,
            'producer_declared_saved_steps': declared_saved, 'records': len(raw_paths), 'errors': reason})
    ready_set = {str(p) for p in root.rglob('segment_*.ready.json')}
    accounted_ready = {p for p in artifacts if p.endswith('.ready.json')}
    unsealed.extend(sorted(ready_set - accounted_ready))
    comparisons = {}
    def blocks(name):
        for path in traces[name]: yield np.load(path, mmap_mode='r', allow_pickle=False)
    for shape in ('rigid_prolate_ar4', 'equal_volume_sphere'):
        first = next(c for c in d['cases'] if c['shape'] == shape and c['sample_id'] == 0 and c['factor'] == .0625)
        second = next(c for c in d['cases'] if c['shape'] == shape and c['sample_id'] == 0 and c['factor'] == .03125)
        a, b = observations[first['id']], observations[second['id']]; metrics = None
        if a['complete_observation'] and b['complete_observation']:
            def initial(c):
                state = c['spec']['initial_state']; return [0., *state['position_m'], *state['orientation'], *state['velocity_generalized']]
            cfg = first['spec']['config']
            metrics = path_metrics.metrics(blocks(first['id']), blocks(second['id']), initial(first), initial(second), a['stop_s'], b['stop_s'], cfg['prolate_semiaxes_m'][1], cfg['target_mean_interstitial_velocity_m_s'])
        comparisons[shape] = policy.pair_gates(a, b, metrics, d['numerical_gates'])
    process_errors = []
    if terminal['auditor_exit_code'] != 0: process_errors.append('auditor_nonzero_exit')
    process_errors.extend('producer_nonzero_exit:' + name for name, code in terminal['producer_exit_codes'].items() if code != 0)
    if not (root / 'auditor_complete.json').exists() or not api.read(root / 'auditor_complete.json').get('passed'):
        process_errors.append('independent_auditor_incomplete_or_failed')
    preflight_steps = 0 if mode == 'preflight' else verify_preflight(d)['new_steps']
    if saved_total + preflight_steps > d['budget']['max_new_steps_total']:
        process_errors.append('inclusive_step_ceiling_exceeded')
    summary = policy.campaign_summary(d['cases'], observations, comparisons, failure_files + stderr + process_errors, unsealed, 0)
    summary.update(mode=mode, integrity_passed=integrity, total_accepted_steps=total, details=details,
                   producer_declared_saved_steps=saved_total, preflight_steps=preflight_steps,
                   artifacts=artifacts, design_sha256=api.sha(DESIGN), new_physics=False)
    if mode == 'preflight':
        expected = len(d['cases']) * d['preflight']['segments_per_live_case'] * d['preflight']['steps_per_live_segment']
        summary['preflight_passed'] = integrity and not failure_files and not stderr and not unsealed and total == expected and terminal['auditor_exit_code'] == 0 and all(v == 0 for v in terminal['producer_exit_codes'].values())
    folder = OUT / ('live_preflight_01' if mode == 'preflight' else 'evaluation_01')
    folder.mkdir(parents=True, exist_ok=False)
    commit(folder / 'results.json', summary)
    commit(folder / 'completion.json', {'results_sha256': api.sha(folder / 'results.json'), 'passed': summary.get('preflight_passed', summary['passed'])})
    print('EVALUATED', mode, summary.get('preflight_passed', summary['passed']), total, flush=True)
    return summary


if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['prepare']: prepare()
    elif len(args) == 2 and args[0] == 'supervise': supervise(args[1])
    elif len(args) == 3 and args[0] == 'worker': worker(args[1], args[2])
    elif len(args) == 2 and args[0] == 'auditor': auditor(args[1])
    elif len(args) == 2 and args[0] == 'evaluate': evaluate(args[1])
    else: raise ValueError('prepare | supervise MODE | worker MODE CASE | auditor MODE | evaluate MODE')
