"""Zero-step independent broader regression audit.

V1 was frozen but not run. Review caught its comparison of an effective solver
binding to the base case binding. This version uses the original binding_for
function; no acceptance gate or numerical audit is changed.
"""
from pathlib import Path
import os
import shutil
import time
import psutil
import qualify_broader_early_dispatch_v1 as test
q = test.q; job, api = q.job, q.api
OUT = test.BASE / 'broader_early_dispatch_independent_02'


def run():
    w = api.read(q.WORK); api.require(job.utc() < job.policy.utc(w['work_end_utc']), 'audit work clock')
    d = api.read(job.DESIGN); job.verify(d)
    p = api.read(test.DESIGN); api.verify_mapping(p['inputs']); api.verify_mapping(p['sources'])
    result = test.sealed(test.OUT); api.verify_mapping(result['artifacts'])
    api.require(result['passed'] and result['unresolved_reservation'] is None, 'successful fully-accounted regression')
    launch = api.read(test.RUN / 'launch.json')
    api.require(not psutil.pid_exists(launch['pid']), 'regression worker retired')
    api.require(launch['protocol_sha256'] == result['protocol_sha256'] == api.sha(test.DESIGN), 'exact protocol binding')
    api.require(launch['reserved_new_accepted_steps'] == test.RESERVATION, 'declared reservation')
    OUT.mkdir(parents=True, exist_ok=False)
    inputs = {str(x): api.sha(x) for x in (Path(__file__), test.DESIGN, test.OUT/'results.json', test.OUT/'completion.json', q.WORK)}
    job.commit(OUT/'launch.json', {'pid': os.getpid(), 'utc': job.utc().isoformat(), 'inputs': inputs, 'new_trajectory_steps': 0})
    total = 0; checks = []; job.parent.b.old.parent.configure()
    for item in p['calls']:
        start = time.perf_counter(); case = item['case']; before, oracle = test.materialize(item, d)
        raw = test.RUN / (item['tag'] + '.json.xz')
        record = q.independent_file(raw, api.sha(test.DESIGN))
        account = api.read(test.RUN / (item['tag'] + '.accounting.json'))
        call = api.read(test.RUN / (item['tag'] + '.launch.json'))
        api.require(call['input_checkpoint_sha256'] == record['input_checkpoint_sha256'] == item['input_checkpoint_sha256'] == api.digest(before), 'complete input binding')
        n = len(record['rows']); total += n
        api.require(n == account['accepted_steps'] == call['cap'] == item['cap'] and n <= 10000, 'exact capped step accounting')
        api.require(account['cumulative_new_steps'] == total and account['raw_sha256'] == api.sha(raw), 'cumulative ledger/raw seal')
        api.require(record['spec'] == case['spec'], 'original case physics')
        api.require(record['effective_binding'] == job.parent.model.binding_for(job.binding(d, case), True), 'original effective solver binding')
        api.require(record['rows'] == oracle['rows'] and api.digest(record['rows']) == item['oracle_rows_sha256'], 'exact independently decoded oracle rows')
        api.require(record['result']['checkpoint']['state'] == oracle['result']['checkpoint']['state'], 'exact complete checkpoint state')
        api.require(api.digest(record['result']['checkpoint']['state']) == item['oracle_checkpoint_state_sha256'], 'frozen oracle state digest')
        with job.prior.snapshot.scope(api, case['spec']['field_metadata']):
            _, data, meta = api.fields.load(2, 1., 6)
            geo = job.prior.candidate.original.GrainGeometry(data['sand_centres_m'], data['sand_radii_m'], meta['cell_length_m'])
            check = test.auditor.kernel(record, case['spec'], job.binding(d, case), before, geo, api.sha(test.DESIGN), d['minimum_gap_semantics'])
        checks.append({'tag': item['tag'], 'steps': n, 'audit': check, 'wall_seconds': time.perf_counter()-start})
        print('BROADER_INDEPENDENT', item['tag'], n, flush=True)
    api.require(total == result['new_accepted_steps'] == test.RESERVATION == sum(x['cap'] for x in p['calls']), 'every step independently accounted')
    prior = test.sealed(test.BASE/'conditional_fine_independent_audit_01')
    api.require(prior['window_total_new_steps']+total == result['window_total_new_steps'] == 40589, 'complete current-window ledger')
    api.verify_mapping(inputs); api.verify_mapping(p['inputs']); api.verify_mapping(p['sources']); api.verify_mapping(result['artifacts']); job.verify(d)
    closure = {'passed': True, 'new_trajectory_steps': 0, 'steps_verified': total, 'window_total_new_steps': 40589,
        'remaining_step_allowance': 9411, 'worker_retired': True, 'calls': checks, 'inputs': inputs,
        'free_disk_bytes': shutil.disk_usage(q.ROOT).free, 'all_thirteen_exact_rows_and_checkpoint_states': True,
        'fresh_full_path_pair_gate_passed': False, 'production_authorized': False, 'parallel_preflight_requalified': False,
        'v1_preserved_unexecuted_review_defect': 'Base/effective binding assertion corrected to original binding_for(base, True).',
        'claim': p['claim']}
    job.commit(OUT/'results.json', closure); job.commit(OUT/'completion.json', {'results_sha256': api.sha(OUT/'results.json')})
    print('BROADER_INDEPENDENT_PASS', total, 40589, flush=True)


if __name__ == '__main__': run()
