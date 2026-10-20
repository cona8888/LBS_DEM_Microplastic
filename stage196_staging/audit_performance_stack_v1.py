"""Separate Stage196 zero-step audit; 35 archives, 27 numerical records, six owned P cores."""
from pathlib import Path
import hashlib
import json
import lzma
import os
import shutil
import traceback
import numpy as np
import psutil
import qualify_performance_stack_v1 as pre
job, api, q = pre.job, pre.api, pre.q
OUT = job.OUT/'independent_readiness_01'


def run():
    d = api.read(job.DESIGN); job.verify(d)
    api.require(job.utc() < job.policy.utc(d['agent_work_end_utc']), 'audit work clock')
    affinity = pre.wrapper.affinity.bind(d['auditor_logical_cpu'])
    OUT.mkdir(parents=True, exist_ok=False)
    job.commit(OUT/'launch.json', {'pid':os.getpid(), 'utc':job.utc().isoformat(), 'new_trajectory_steps':0, 'source_sha256':api.sha(__file__), 'owned_affinity':affinity})
    try:
        r = job.verify_preflight(d)
        api.require(r['new_steps'] == 17000 and r['prior_stage196_steps'] == 8326, 'separate completed ledgers')
        dsha = api.sha(job.DESIGN)
        all_paths = {p.resolve() for p in job.PREFLIGHT.rglob('*.json.xz')}
        api.require(len(all_paths) == 35, '15 probes, 12 live records, eight zero-step fixtures')
        decoded, states, history, reports = {}, {}, {}, []

        def decode(path):
            path = path.resolve()
            if path in decoded: return decoded[path]
            api.require(path in all_paths, 'prefix restricted to complete immutable inventory')
            seal = api.read(path.with_suffix('.seal.json')); packed = path.read_bytes()
            api.require(hashlib.sha256(packed).hexdigest() == seal['compressed_sha256'], 'compressed seal')
            raw = lzma.decompress(packed)
            api.require(len(raw) == seal['uncompressed_bytes'] and hashlib.sha256(raw).hexdigest() == seal['uncompressed_sha256'], 'uncompressed seal')
            env = q.independent_unpack(json.loads(raw)); meta = env['history']
            prefix = None; hist = None; reference = None
            if meta['prefix'] is not None:
                parent_path = Path(meta['prefix']['path']).resolve(); decode(parent_path)
                prefix = states[parent_path]; reference = prefix.reference(); hist = history[parent_path]
                api.require(meta['prefix'] == reference, 'exact independent history ancestry')
            independent = q.independent_file(path, dsha, hist, reference)
            record, state = job.codec.read_record(path, dsha, prefix)
            api.require(q.repair.base.raw_bytes(independent) == q.repair.base.raw_bytes(record), 'independent/full production decoder identity')
            decoded[path], states[path], history[path] = record, state, independent['result']['history']
            reports.append({'path':str(path), 'steps':len(record['rows']), 'raw_sha256':api.sha(path), 'logical_sha256':state.original_sha256})
            return record

        for path in sorted(all_paths): decode(path)
        print('STAGE196_INDEPENDENT_RAW', len(reports), flush=True)
        cases = {c['id']:c for c in d['cases']}; audits = []; actual = 0
        job.parent.b.old.parent.configure()
        with job.prior.snapshot.scope(api, d['cases'][0]['spec']['field_metadata']):
            geo = pre.prior.geometry()
            for path in sorted((job.PREFLIGHT/'probes').glob('*.json.xz')):
                receipt = api.read(path.with_suffix('.preflight_audit.json')); case = cases[receipt['case']]
                if path.name.endswith('_fresh.json.xz'): before = None
                elif path.name == 'split_last.json.xz': before = decode(job.PREFLIGHT/'probes/split_first.json.xz')['result']['checkpoint']
                elif path.name in ('serial.json.xz','split_first.json.xz') or path.name.startswith('parallel_'):
                    stress_case, before = pre.stress_seed(d); api.require(stress_case == case, 'repaired regime stress case')
                else: before, oracle = pre.seed(d, case)
                rec = decode(path)
                check = job.kernel.evaluate(rec, case['spec'], job.binding(d, case), before, geo, dsha, d['minimum_gap_semantics'])
                api.require(check['passed'] and not check['complete_observation'], 'local qualification only')
                api.require({k:v for k,v in check.items() if k!='audit_seconds'} == {k:v for k,v in receipt['summary'].items() if k!='audit_seconds'}, 'complete independently reproduced numerical summary')
                launch = api.read(path.with_suffix('.launch.json')); account = api.read(path.with_suffix('.accounting.json'))
                api.require(launch['reserved_new_accepted_steps'] == len(rec['rows']) == account['accepted_steps'] and launch['input_checkpoint_sha256'] == api.digest(before), 'probe reservation and actual ledger')
                api.require(account['raw_sha256'] == receipt['raw_sha256'] == api.sha(path) and rec['result']['rejected'] == 0, 'zero rejected trials and exact raw binding')
                if path.name.endswith('_contact.json.xz'):
                    api.require(rec['rows'] == oracle['rows'] and rec['result']['checkpoint']['state'] == oracle['result']['checkpoint']['state'], 'original contact oracle unchanged')
                actual += len(rec['rows']); audits.append({'path':str(path),'summary':check})
            live = job.root_for('preflight')
            for case in d['cases']:
                before = receipt_sha = None
                for index in (1,2):
                    paths = job.paths(live, case['id'], index)
                    job.policy.verify_receipt(paths, case['id'], index, dsha, d['audit_source_sha256'], api.digest(before), receipt_sha)
                    rec = decode(paths['raw']); receipt = api.read(paths['receipt'])
                    check = job.kernel.evaluate(rec, case['spec'], job.binding(d, case), before, geo, dsha, d['minimum_gap_semantics'])
                    api.require({k:v for k,v in check.items() if k!='audit_seconds'} == {k:v for k,v in receipt['summary'].items() if k!='audit_seconds'}, 'independent live numerical summary')
                    api.require(receipt['original_raw_sha256'] == states[paths['raw'].resolve()].original_sha256, 'receipt logical seal')
                    expected = np.asarray([[x['time_s'],*x['position_m'],*x['orientation'],*x['velocity_generalized']] for x in rec['rows']])
                    api.require(np.array_equal(expected,np.load(paths['trace'],allow_pickle=False)), 'exact complete raw/trace identity')
                    actual += len(rec['rows']); before = rec['result']['checkpoint']; receipt_sha = api.sha(paths['receipt'])
                    audits.append({'path':str(paths['raw']), 'summary':check})
                terminal = api.read(live/case['id']/'result.json'); seal = api.read(live/case['id']/'completion.json')
                api.require(seal['result_sha256'] == api.sha(live/case['id']/'result.json') and terminal['final_result'] == rec['result'] and len(terminal['entries']) == 2, 'sealed producer inventory')
        serial = decode(job.PREFLIGHT/'probes/serial.json.xz'); first = decode(job.PREFLIGHT/'probes/split_first.json.xz'); last = decode(job.PREFLIGHT/'probes/split_last.json.xz')
        api.require(serial['rows'] == first['rows']+last['rows'] and serial['result']['checkpoint']['state'] == last['result']['checkpoint']['state'], 'exact repaired-regime restart')
        oracle = q.independent_file(Path(d['stress_oracle_raw']), api.sha(d['stress_oracle_design']))
        api.require(serial['rows'] == oracle['rows'][:1000], 'repaired-regime prior local numerical oracle')
        ratios = []
        for index in range(6):
            rec = decode(job.PREFLIGHT/'probes'/f'parallel_{index}.json.xz')
            api.require(rec['rows'] == first['rows'] and rec['result']['checkpoint']['state'] == first['result']['checkpoint']['state'], 'exact concurrent independent-process result')
            ratios.append(rec['compute_call_wall_s']/first['compute_call_wall_s'])
        api.require(ratios == r['parallel_slowdown_ratios'] and max(ratios) <= 1.3, 'unchanged concurrent slowdown gate')
        terminal = api.read(live/'completion.json')
        api.require(terminal['all_owned_processes_retired'] and terminal['auditor_exit_code']==0 and terminal['producer_exit_codes']=={c:0 for c in cases} and not terminal['stop_reasons'] and not terminal['unrun_cases'], 'clean complete lifecycle')
        api.require(not list(live.rglob('*.failure.json')) and not any('.pending.' in p.name for p in live.rglob('*')), 'no genuine failures or pending writes')
        api.require(all(p.stat().st_size == 0 for p in job.PREFLIGHT.rglob('*.stderr.log')), 'all child stderr empty')
        owned = [api.read(job.PREFLIGHT/'launch.json')['pid']]
        owned += [x['pid'] for x in api.read(job.PREFLIGHT/'parallel_launches.json')['children']]
        owned += [api.read(live/'auditor_launch.json')['pid']]
        owned += [api.read(path)['pid'] for path in live.glob('dispatch_*.json')]
        api.require(not any(psutil.pid_exists(pid) for pid in owned), 'every owned process retired')
        fixtures = []
        for label, expected in [('cutoff_drain',4), ('failure_drain',2)]:
            f = api.read(job.PREFLIGHT/'protocol_fixtures'/label/'auditor_complete.json')
            api.require(len(f['items']) == 4 and sum(x['passed'] for x in f['items']) == expected and f['passed'] == (expected == 4), 'all fixture records drained, injected failure preserved')
            fixtures.append({'name':label,'saved_copies':4,'passed_audits':expected,'new_trajectory_steps':0})
        api.require(actual == r['new_steps'] == 17000 and actual+8326 == 25326, 'all new accepted steps and prior work disclosed')
        api.require(sum(c['step_ceiling'] for c in d['cases'])+actual <= d['budget']['max_new_steps_total'], 'original prospective campaign plus preflight ceiling')
        api.require(not job.RUN.exists(), 'no production run')
        required = None  # Fresh absolute performance/storage forecast is a separate gate.
        available = (job.policy.utc(d['simulation_cutoff_utc'])-job.utc()).total_seconds()/3600
        free = shutil.disk_usage(job.ROOT).free; required_bytes = d['provenance_bytes_with_margin']+d['budget']['minimum_free_disk_bytes']
        wrapper = pre.wrapper
        wrapper.affinity.verify_layout(d['worker_logical_cpus']+[d['auditor_logical_cpu']])
        for index in range(6):
            info=api.read(job.PREFLIGHT/f'parallel_{index}.affinity.json')
            api.require(info['current_affinity']==[d['worker_logical_cpus'][index]],'declared parallel owned affinity')
        for index,case in enumerate(d['cases']):
            info=api.read(live/(case['id']+'.affinity.json'))
            api.require(info['current_affinity']==[d['worker_logical_cpus'][index]],'declared live owned affinity')
        api.require(api.read(live/'auditor.affinity.json')['current_affinity']==[d['auditor_logical_cpu']],'declared auditor owned affinity')
        job.verify(d); job.verify_preflight(d)
        result = {'numerical_qualification_passed':True, 'process_qualification_passed':True, 'production_authorized':False,
            'campaign_launch_ready':False, 'deadline_gate_passed':False, 'storage_gate_passed':None,
            'new_trajectory_steps':0, 'stage196_preflight_steps_verified':actual, 'prior_stage196_steps':8326, 'window_new_accepted_steps':25326,
            'raw_records_independently_decoded':len(reports),'raw_records':reports,'numerical_reaudits':audits,'protocol_fixtures':fixtures,
            'all_owned_processes_retired':True, 'required_simulation_hours':required, 'available_simulation_hours':available,
            'old_scenario_storage_bytes_not_refreshed':required_bytes, 'free_disk_bytes':free, 'parallel_slowdown_ratios':ratios,
            'design_sha256':dsha, 'preflight_result_sha256':api.sha(pre.OUT/'results.json'), 'source_sha256':api.sha(__file__),
            'claim':'Bounded full-stack verification only, not complete observation, release estimate or empirical validation. Production deadline/authority unresolved.'}
        job.commit(OUT/'results.json',result); job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
        print('STAGE196_INDEPENDENT_PASS',actual,'required_hours',required,'available_hours',available,flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'new_trajectory_steps':0}); raise


if __name__ == '__main__': run()
