"""Bounded healthy-prefix and six-case regression; never a production run.

Explicit 16,841-step reservation: 9,641 healthy steps, and six original
200-step fresh plus 1,000-step contact controls. Original physics/gates remain
frozen. No numeric string substitution or inheritance of parallel readiness.
"""
from pathlib import Path
from datetime import timedelta
import copy
import os
import shutil
import sys
import time
import traceback
import types
import psutil
import qualify_failure_codec_v1 as q
import early_semismooth_dispatch_v1 as repair
import audit_early_semismooth_v1 as auditor

job, api = q.job, q.api
BASE = q.ROOT / 'stage194_evaluations/evidence_repair_20260924'
DESIGN = q.ROOT / 'stage194_designs/evidence_repair_20260924/broader_early_dispatch_01.json'
RUN = q.ROOT / 'stage194_runs/evidence_repair_20260924/broader_early_dispatch_01'
OUT = BASE / 'broader_early_dispatch_01'
SEED = BASE / 'seed_extraction_01/diagnostic_seed_01.json'
PREFIX_RAW = RUN.parent / 'trajectory_qualification_01/call_01.json.xz'
PREFIX_DESIGN = DESIGN.with_name('trajectory_qualification_01.json')
FRESH_DESIGN = q.campaign.old.DESIGN
FRESH_ROOT = q.ROOT / 'stage192_runs/qualified_provenance_campaign_20260924/preflight_01/probes'
PRIOR = {'diagnostic_replay_01': 9645, 'trajectory_qualification_01': 9696,
         'dispatch_restart_01': 55, 'semismooth_restart_01': 256,
         'early_semismooth_restart_01': 2048, 'conditional_fine_01': 2048}
PRIOR_TOTAL = 23748
RESERVATION = 16841


def sealed(root):
    result = api.read(root / 'results.json')
    api.require(api.read(root / 'completion.json')['results_sha256'] == api.sha(root / 'results.json'), 'completion seal ' + str(root))
    return result


def prerequisites():
    w = api.read(q.WORK)
    api.require(job.utc() < job.policy.utc(w['work_end_utc']) - timedelta(seconds=900), 'no launch in final fifteen minutes')
    for key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
        api.require(os.environ.get(key) == '1', 'one numerical thread: ' + key)
    d = api.read(job.DESIGN); job.verify(d)
    ledger = sealed(BASE / 'conditional_fine_independent_audit_01')
    api.require(ledger['passed'] and ledger['window_total_new_steps'] == PRIOR_TOTAL, 'independent prior ledger')
    api.require(sum(PRIOR.values()) == PRIOR_TOTAL, 'explicit prior sum')
    for name, count in PRIOR.items():
        api.require(api.read(BASE / name / 'results.json')['new_accepted_steps'] == count, 'all prior counts preserved')
    api.require(PRIOR_TOTAL + RESERVATION <= w['maximum_new_accepted_trajectory_steps'], 'window reserve')
    return w, d


def controls(d):
    previous = job.qualified.previous
    source_design = api.sha(previous.prior.DESIGN)
    old_cases = {c['id']: c for c in api.read(previous.DESIGN)['cases']}
    plan = [{'tag': 'healthy_prefix', 'kind': 'healthy', 'cap': 9641,
             'case': next(c for c in d['cases'] if c['id'] == api.read(SEED)['case']),
             'oracle': str(PREFIX_RAW), 'oracle_design_sha256': api.sha(PREFIX_DESIGN),
             'source': str(SEED)}]
    for case in d['cases']:
        saved = old_cases[case['id']]
        api.require(saved['spec'] == case['spec'], 'original six-case spec unchanged')
        plan += [
            {'tag': case['id'] + '_fresh', 'kind': 'fresh', 'cap': 200, 'case': case,
             'oracle': str(FRESH_ROOT / (case['id'] + '_fresh.json.xz')), 'oracle_design_sha256': api.sha(FRESH_DESIGN)},
            {'tag': case['id'] + '_contact', 'kind': 'contact', 'cap': 1000, 'case': case,
             'source': saved['source'], 'oracle': saved['oracle'], 'oracle_design_sha256': source_design}]
    return plan


def materialize(item, d):
    """Read hash-bound controls only; no trajectory execution."""
    case = item['case']
    if item['kind'] == 'healthy':
        before = copy.deepcopy(api.read(SEED)['checkpoint'])
        oracle = q.independent_file(Path(item['oracle']), item['oracle_design_sha256'])
    elif item['kind'] == 'fresh':
        before = None
        oracle = q.old_codec.codec.read_record(Path(item['oracle']), item['oracle_design_sha256'])[0]
    else:
        old = job.qualified.previous
        record = old.independent.independent_read(Path(item['source']), item['oracle_design_sha256'])
        oracle = old.independent.independent_read(Path(item['oracle']), item['oracle_design_sha256'])
        before = job.parent.model.checkpoint(case['spec'], job.binding(d, case), record['result']['checkpoint'], True)
        api.require(before['state'] == record['result']['checkpoint']['state'], 'only diagnostic contract rebound')
    api.require(len(oracle['rows']) == item['cap'] and oracle['spec'] == case['spec'], 'exact oracle interval/spec')
    return before, oracle


def prepare():
    w, d = prerequisites(); plan = controls(d)
    api.require(sum(x['cap'] for x in plan) == RESERVATION and len(plan) == 13, 'declared thirteen calls')
    paths = [q.WORK, job.DESIGN, SEED, PREFIX_DESIGN, FRESH_DESIGN,
             job.qualified.previous.DESIGN, job.qualified.previous.prior.DESIGN,
             BASE / 'conditional_fine_independent_audit_01/results.json',
             BASE / 'conditional_fine_independent_audit_01/completion.json']
    paths += list(Path(__file__).parent.glob('*.py'))
    for name in PRIOR:
        paths += [BASE / name / 'results.json', BASE / name / 'completion.json']
    for item in plan:
        for key in ('source', 'oracle'):
            if key in item:
                path = Path(item[key]); paths.append(path)
                if path.suffix == '.xz': paths.append(path.with_suffix('.seal.json'))
        before, oracle = materialize(item, d)
        item['input_checkpoint_sha256'] = api.digest(before)
        item['oracle_rows_sha256'] = api.digest(oracle['rows'])
        item['oracle_checkpoint_state_sha256'] = api.digest(oracle['result']['checkpoint']['state'])
    p = {'stage': 'Stage194 broader early-dispatch regression', 'prior_new_steps': PRIOR_TOTAL,
         'maximum_new_steps': RESERVATION, 'maximum_window_steps_after_reservation': PRIOR_TOTAL + RESERVATION,
         'calls': plan, 'sources': d['sources'], 'inputs': {str(x): api.sha(x) for x in paths},
         'integration_code_sha256': q.campaign.code_sha(job.execute_segment),
         'frozen_numerical_gates': d['numerical_gates'], 'physical_and_timestep_changes': [],
         'required_exact_rows_and_checkpoint_state': True, 'production_authorized': False,
         'parallel_full_stack_qualification_inherited': False,
         'claim': 'Healthy-path regression and local original six-case controls only; no fresh full-path, release, or empirical validation claim.'}
    job.commit(DESIGN, p); print('BROADER_PROTOCOL', api.sha(DESIGN), flush=True)


def run():
    w, d = prerequisites(); p = api.read(DESIGN)
    api.verify_mapping(p['inputs']); api.verify_mapping(p['sources'])
    api.require(not RUN.exists() and not OUT.exists(), 'new immutable output only')
    for path in RUN.parent.rglob('launch.json'):
        if api.read(path).get('reserved_new_accepted_steps', 0):
            api.require(path.parent.name in PRIOR, 'no unresolved/new reservation')
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if proc.info['pid'] == os.getpid() or 'python' not in (proc.info['name'] or '').lower(): continue
        cmd = ' '.join(proc.info['cmdline'] or []).lower()
        api.require('matdem_microplastic' not in cmd and 'stage194_staging' not in cmd, 'one simulation worker')
    api.require(shutil.disk_usage(q.ROOT).free > w['minimum_free_disk_bytes'] + 2*q.repair.base.MAX_RAW, 'disk reserve')
    RUN.mkdir(parents=True, exist_ok=False); OUT.mkdir(parents=True, exist_ok=False)
    stop = min(job.utc() + timedelta(minutes=20), job.policy.utc(w['work_end_utc']) - timedelta(seconds=900)).isoformat()
    job.commit(RUN / 'launch.json', {'pid': os.getpid(), 'argv': sys.argv, 'utc': job.utc().isoformat(), 'stop_utc': stop,
        'reserved_new_accepted_steps': RESERVATION, 'prior_window_steps': PRIOR_TOTAL, 'protocol_sha256': api.sha(DESIGN), 'blas_threads': 1})
    ns = {**job.execute_segment.__globals__, 'DESIGN': DESIGN, 'codec': q.repair.codec}
    execute = types.FunctionType(job.execute_segment.__code__, ns, 'execute_segment', job.execute_segment.__defaults__, job.execute_segment.__closure__)
    api.require(q.campaign.code_sha(execute) == p['integration_code_sha256'], 'unchanged integration bytecode')
    api.require(sorted(k for k in ns if ns[k] is not job.execute_segment.__globals__[k]) == ['DESIGN', 'codec'], 'only declared integration bindings')
    total = 0; reports = []; failure = None; unresolved = None
    try:
        job.parent.b.old.parent.configure()
        for item in p['calls']:
            api.require(job.utc() < job.policy.utc(stop), 'bounded call clock')
            api.require(shutil.disk_usage(q.ROOT).free > w['minimum_free_disk_bytes'] + 2*q.repair.base.MAX_RAW, 'disk reserve')
            case = item['case']; before, oracle = materialize(item, d)
            api.require(api.digest(before) == item['input_checkpoint_sha256'], 'prepared predecessor unchanged')
            raw = RUN / (item['tag'] + '.json.xz')
            job.commit(RUN / (item['tag'] + '.launch.json'), {'cap': item['cap'], 'input_checkpoint_sha256': api.digest(before),
                'utc': job.utc().isoformat(), 'known_new_steps': total, 'case': case['id']})
            unresolved = {'tag': item['tag'], 'maximum_unaccounted_steps': item['cap']}
            with job.prior.snapshot.scope(api, case['spec']['field_metadata']):
                _, data, meta = api.fields.load(2, 1., 6)
                geo = job.prior.candidate.original.GrainGeometry(data['sand_centres_m'], data['sand_radii_m'], meta['cell_length_m'])
                with repair.scope(job.parent.engine.runtime, True, job.policy.utc(stop).timestamp()):
                    record, _, _, elapsed = execute(d, case, before, raw, item['cap'], None, stop)
                n = len(record['rows']); total += n
                job.commit(RUN / (item['tag'] + '.accounting.json'), {'accepted_steps': n, 'cumulative_new_steps': total,
                    'raw_sha256': api.sha(raw), 'rejected_total': record['result']['rejected'], 'status': record['result']['status']})
                unresolved = None
                api.require(n <= item['cap'] <= w['maximum_accepted_steps_per_diagnostic_call'] and total <= RESERVATION, 'bounded exact step ledger')
                audit_start = time.perf_counter(); independent = q.independent_file(raw, api.sha(DESIGN))
                api.require(q.repair.base.raw_bytes(independent) == q.repair.base.raw_bytes(record), 'independent raw identity')
                check = auditor.kernel(independent, case['spec'], job.binding(d, case), before, geo, api.sha(DESIGN), d['minimum_gap_semantics'])
                exact_rows = record['rows'] == oracle['rows']
                exact_state = record['result']['checkpoint']['state'] == oracle['result']['checkpoint']['state']
                entry = {'tag': item['tag'], 'kind': item['kind'], 'case': case['id'], 'steps': n,
                    'compute_seconds': record['compute_call_wall_s'], 'transaction_seconds': elapsed,
                    'independent_decode_and_audit_seconds': time.perf_counter()-audit_start, 'raw_bytes': raw.stat().st_size,
                    'raw_sha256': api.sha(raw), 'audit': check, 'exact_oracle_rows': exact_rows,
                    'exact_oracle_checkpoint_state': exact_state, 'early_attempt_count': len(record['early_attempts']),
                    'fallback_system_count': len(record['fallback_systems'])}
                reports.append(entry); job.commit(OUT / (item['tag'] + '.audit.json'), entry)
                print('BROADER_AUDIT', item['tag'], n, exact_rows, exact_state, elapsed, flush=True)
                api.require(n == item['cap'] and exact_rows and exact_state, 'complete exact healthy/control regression')
    except Exception as error:
        failure = {'error': repr(error), 'traceback': traceback.format_exc(), 'known_new_steps': total, 'unresolved_reservation': unresolved}
        job.commit(OUT / 'failure.json', failure)
    api.verify_mapping(p['inputs']); api.verify_mapping(p['sources']); job.verify(d)
    r = {'passed': failure is None and len(reports) == 13, 'new_accepted_steps': total, 'window_total_new_steps': PRIOR_TOTAL+total,
         'remaining_step_allowance_if_fully_accounted': 50000-PRIOR_TOTAL-total if unresolved is None else None,
         'unresolved_reservation': unresolved, 'calls': reports, 'failure': failure, 'protocol_sha256': api.sha(DESIGN),
         'complete_observation': False, 'production_authorized': False, 'parallel_full_stack_qualification_inherited': False,
         'artifacts': {str(x): api.sha(x) for x in RUN.rglob('*') if x.is_file()}, 'claim': p['claim']}
    job.commit(OUT / 'results.json', r); job.commit(OUT / 'completion.json', {'passed': r['passed'], 'results_sha256': api.sha(OUT / 'results.json')})
    print('BROADER_RESULT', r['passed'], total, flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['prepare']: prepare()
    elif sys.argv[1:] == ['run']: run()
    else: raise ValueError('prepare | run')
