"""One bounded full-stack preflight: 18,200 accepted steps, no production.

Existing archived paths are oracles, never initial conditions for production.
Failure-drain fixtures only re-encode saved evidence and advance zero steps.
"""
from pathlib import Path
from datetime import timedelta
import copy
import os
import subprocess
import sys
import time
import traceback
import numpy as np
import integrated_paired_campaign_v1 as job

api, parent = job.api, job.parent
ROOT, RUN, OUT = job.ROOT, job.PREFLIGHT, job.OUT / 'preflight_01'
SELF = Path(__file__).resolve()


def seed(d, case):
    old = job.qualified.previous
    saved = next(c for c in api.read(old.DESIGN)['cases'] if c['id'] == case['id'])
    source_sha = api.sha(old.prior.DESIGN)
    record = old.independent.independent_read(Path(saved['source']), source_sha)
    oracle = old.independent.independent_read(Path(saved['oracle']), source_sha)
    api.require(saved['spec'] == case['spec'], 'archived oracle spec is exactly frozen case')
    cp = parent.model.checkpoint(case['spec'], job.binding(d, case), record['result']['checkpoint'], True)
    return cp, oracle


def deadline():
    r = api.read(RUN / 'launch.json')
    api.require(job.utc() < job.policy.utc(r['preflight_stop_utc']) - timedelta(seconds=120), 'bounded preflight wall reserve')
    return r['preflight_stop_utc']


def geometry():
    _, data, meta = api.fields.load(2, 1., 6)
    return job.prior.candidate.original.GrainGeometry(data['sand_centres_m'], data['sand_radii_m'], meta['cell_length_m'])


def call(d, case, cp, name, cap, geo, prefix=None):
    path = RUN / 'probes' / (name + '.json.xz'); path.parent.mkdir(exist_ok=True)
    record, state, _, transaction = job.execute_segment(d, case, copy.deepcopy(cp), path, cap, prefix, deadline())
    api.require(len(record['rows']) == cap and record['result']['status'] == 'paused_checkpoint', 'exact bounded step count')
    decoded, decoded_state = job.codec.read_record(path, api.sha(job.DESIGN), prefix)
    api.require(job.codec.base.raw_bytes(decoded) == job.codec.base.raw_bytes(record), 'raw canonical byte identity')
    summary = job.kernel.evaluate(decoded, case['spec'], job.binding(d, case), cp, geo, api.sha(job.DESIGN), d['minimum_gap_semantics'])
    receipt = {'case': case['id'], 'steps': cap, 'path': str(path), 'sha256': api.sha(path), 'summary': summary,
               'transaction_seconds': transaction, 'design_sha256': api.sha(job.DESIGN)}
    job.commit(path.with_suffix('.preflight_audit.json'), receipt)
    return decoded, decoded_state, receipt


def probe(tag):
    d = api.read(job.DESIGN); job.verify(d); parent.b.old.parent.configure()
    case = d['cases'][0]; cp, _ = seed(d, case)
    with job.prior.snapshot.scope(api, case['spec']['field_metadata']):
        call(d, case, cp, tag, 1000, geometry())


def spawn(args, tag):
    stdout = (RUN / (tag + '.stdout.log')).open('xb'); stderr = (RUN / (tag + '.stderr.log')).open('xb')
    command = [sys.executable, '-B', '-u', str(SELF), *args]
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', OMP_NUM_THREADS='1')
    try:
        child = subprocess.Popen(command, cwd=str(ROOT), env=env, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
    finally:
        stdout.close(); stderr.close()
    return child, command


def protocol_fixtures(d):
    """Exercise the actual auditor loop after stop, including a rejected chain."""
    findings = []
    original_root_for = job.root_for
    for label, corrupt in [('cutoff_drain', False), ('failure_drain', True)]:
        root = RUN / 'protocol_fixtures' / label; root.mkdir(parents=True, exist_ok=False)
        job.commit(root / 'launch.json', {'design_sha256': api.sha(job.DESIGN), 'stop_utc': '2000-01-01T00:00:00Z',
                                        'fixture_only': True, 'new_trajectory_steps': 0})
        job.latch(root, label)
        # Two independent cases each have two recorded segments. A corrupt
        # first chain must not prevent independent drain of the other chain.
        for case_index, case in enumerate(d['cases'][:2]):
            prefix = None; source_prefix = None
            for index in (1, 2):
                src = job.paths(job.root_for('preflight'), case['id'], index)
                record, source_prefix = job.codec.read_record(src['raw'], api.sha(job.DESIGN), source_prefix)
                record = copy.deepcopy(record)
                if corrupt and case_index == 0 and index == 1:
                    record['result']['checkpoint']['state_sha256'] = '0' * 64
                p = job.paths(root, case['id'], index); p['raw'].parent.mkdir(exist_ok=True)
                _, prefix = job.codec.write_record(p['raw'], record, prefix)
                marker = {'case': case['id'], 'segment': index, 'design_sha256': api.sha(job.DESIGN),
                          'raw_path': str(p['raw']), 'raw_sha256': api.sha(p['raw']),
                          'seal_sha256': api.sha(p['raw'].with_suffix('.seal.json')),
                          'input_checkpoint_sha256': record['input_checkpoint_sha256'], 'steps': len(record['rows'])}
                job.commit(p['ready'], marker)
        job.commit(root / 'producers_complete.json', {'fixture_only': True, 'all_producers_retired': True})
        try:
            job.root_for = lambda mode: root
            job.auditor('preflight')
        finally:
            job.root_for = original_root_for
        r = api.read(root / 'auditor_complete.json')
        api.require(len(r['items']) == 4 and r['passed'] is (not corrupt), 'all sealed records drained after stop')
        if corrupt:
            api.require(sum(x['passed'] for x in r['items']) == 2 and len(r['failures']) == 1, 'failed chain retained and independent case audited')
        else:
            api.require(all(x['passed'] for x in r['items']), 'cutoff cannot discard sealed evidence')
        findings.append({'fixture': label, 'sealed_records': 4, 'passed_audits': sum(x['passed'] for x in r['items']),
                         'expected_failure_preserved': corrupt, 'new_trajectory_steps': 0})
    # Exact exclusive-commit tests use only new synthetic files.
    occupied = RUN / 'protocol_fixtures' / 'exclusive.json'; job.commit(occupied, {'fixture': True})
    try: job.commit(occupied, {'wrong': True})
    except FileExistsError: pass
    else: raise AssertionError('immutable marker overwritten')
    api.require(api.read(occupied) == {'fixture': True}, 'original marker preserved')
    absent = RUN / 'protocol_fixtures' / 'pending_guard.json'
    job.commit(absent.with_name(absent.name + f'.pending.{os.getpid()}'), {'fixture': True})
    try: job.commit(absent, {'wrong': True})
    except FileExistsError: pass
    else: raise AssertionError('orphan pending ignored')
    return findings


def run():
    d = api.read(job.DESIGN); job.verify(d)
    api.require(job.utc() < job.policy.utc(d['agent_work_end_utc']) - timedelta(seconds=3700), 'preflight work-window reserve')
    RUN.mkdir(parents=True, exist_ok=False); OUT.mkdir(parents=True, exist_ok=False)
    stop = job.utc() + timedelta(seconds=d['preflight']['wall_seconds'])
    job.commit(RUN / 'launch.json', {'pid': os.getpid(), 'argv': sys.argv, 'utc': job.utc().isoformat(),
               'preflight_stop_utc': stop.isoformat(), 'design_sha256': api.sha(job.DESIGN), 'maximum_steps': 18200})
    started = time.perf_counter(); new_steps = 0; cases = []; rates = []; children = []
    try:
        parent.b.old.parent.configure()
        with job.prior.snapshot.scope(api, d['cases'][0]['spec']['field_metadata']):
            geo = geometry()
            for case in d['cases']:
                fresh, _, audit = call(d, case, None, case['id'] + '_fresh', 200, geo)
                new_steps += 200
                cp, oracle = seed(d, case)
                rec, _, audit = call(d, case, cp, case['id'] + '_contact', 1000, geo)
                new_steps += 1000
                api.require(rec['rows'] == oracle['rows'] and rec['result']['checkpoint']['state'] == oracle['result']['checkpoint']['state'], 'exact archived contact/full-state identity')
                rates.append(rec['compute_call_wall_s'] / oracle['compute_call_wall_s'])
                cases.append({'case': case['id'], 'fresh_steps': 200, 'contact_steps': 1000, 'exact_archived_identity': True,
                              'compute_ratio_to_archived_same_steps': rates[-1], 'independent_audit': audit['summary']})
                print('PREFLIGHT_CASE', case['id'], 'steps', new_steps, flush=True)
            case = d['cases'][0]; cp, _ = seed(d, case)
            serial, _, serial_audit = call(d, case, cp, 'serial', 1000, geo); new_steps += 1000
            first, prefix, _ = call(d, case, cp, 'split_first', 371, geo); new_steps += 371
            last, _, _ = call(d, case, first['result']['checkpoint'], 'split_last', 629, geo, prefix); new_steps += 629
            api.require(serial['rows'] == first['rows'] + last['rows'] and serial['result']['checkpoint']['state'] == last['result']['checkpoint']['state'], 'exact production-stack checkpoint split')
        dispatches = []
        for i in range(3):
            p, command = spawn(['probe', f'parallel_{i}'], f'parallel_{i}'); children.append(p)
            dispatches.append({'pid': p.pid, 'argv': command})
        job.commit(RUN / 'parallel_launches.json', {'children': dispatches, 'design_sha256': api.sha(job.DESIGN)})
        while any(p.poll() is None for p in children):
            time.sleep(.2)
        api.require(all(p.returncode == 0 for p in children), 'parallel probe processes')
        ratios = []
        for i in range(3):
            path = RUN / 'probes' / f'parallel_{i}.json.xz'
            rec, _ = job.codec.read_record(path, api.sha(job.DESIGN)); new_steps += len(rec['rows'])
            api.require((RUN / f'parallel_{i}.stderr.log').stat().st_size == 0, 'parallel stderr empty')
            api.require(rec['rows'] == serial['rows'] and rec['result']['checkpoint']['state'] == serial['result']['checkpoint']['state'], 'separate-process exact numerical identity')
            ratios.append(rec['compute_call_wall_s'] / serial['compute_call_wall_s'])
        api.require(max(ratios) <= 1.3, 'parallel slowdown within frozen 30 percent margin')
        deadline()
        job.supervise('preflight')
        live = job.evaluate('preflight'); new_steps += live['total_accepted_steps']
        api.require(live['preflight_passed'] and live['total_accepted_steps'] == 6000, 'same-runner live pipeline qualification')
        fixtures = protocol_fixtures(d)
        api.require(new_steps == 18200 <= d['preflight']['maximum_new_steps'], 'exact new-step ledger')
        api.require(sum(c['step_ceiling'] for c in d['cases']) + new_steps <= d['budget']['max_new_steps_total'], 'original inclusive campaign/preflight step reserve')
        job.verify(d)
        # Existing conservative late-history scenario plus measured current-stack
        # serial overhead; no reduction for unusually fast short pilot windows.
        overhead = max(1., max(rates))
        refreshed_hours = d['resource_scenario']['hours_with_margin'] * overhead
        available = (job.policy.utc(d['simulation_cutoff_utc']) - job.utc()).total_seconds() / 3600
        result = {'passed': True, 'new_steps': new_steps, 'cases': cases, 'exact_restart': True,
                  'parallel_identity': True, 'parallel_slowdown_ratios': ratios, 'independent_audit_passed': True,
                  'live_pipeline_steps': 6000, 'protocol_fixtures': fixtures, 'cutoff_and_failure_drain': True,
                  'serial_overhead_factor': overhead, 'refreshed_hours_with_margin': refreshed_hours,
                  'available_simulation_hours': available, 'resource_scenario_fits': refreshed_hours <= available,
                  'design_sha256': api.sha(job.DESIGN), 'sources': d['sources'],
                  'artifacts': {str(p): api.sha(p) for p in RUN.rglob('*') if p.is_file()},
                  'wall_seconds': time.perf_counter() - started, 'production_launched': False,
                  'claim': 'Full-stack bounded numerical/process qualification only; no full-path observation or population release.'}
        job.commit(OUT / 'results.json', result)
        job.commit(OUT / 'completion.json', {'passed': True, 'results_sha256': api.sha(OUT / 'results.json')})
        print('INTEGRATED_PREFLIGHT_PASS', new_steps, ratios, 'hours', refreshed_hours, flush=True)
    except Exception as error:
        for p in children:
            while p.poll() is None: time.sleep(.2)
        job.commit(OUT / 'failure.json', {'error': repr(error), 'traceback': traceback.format_exc(),
            'counted_new_steps': new_steps, 'all_raw_evidence_preserved': True, 'design_sha256': api.sha(job.DESIGN)})
        raise


if __name__ == '__main__':
    if sys.argv[1:] == ['run']: run()
    elif len(sys.argv) == 3 and sys.argv[1] == 'probe': probe(sys.argv[2])
    else: raise ValueError('run | probe TAG')
