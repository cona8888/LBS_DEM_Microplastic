"""Read-only re-audit of saved qualification; zero trajectory steps.

Creates one new report, never an existing run/audit receipt. Numerical
qualification and campaign launch readiness are deliberately separate gates.
"""
from pathlib import Path
import copy
import hashlib
import json
import os
import shutil
import traceback
import numpy as np
import qualify_provenance_campaign_v1 as pre

job, api = pre.job, pre.api
ROOT, RUN = job.ROOT, job.PREFLIGHT
OUT = job.OUT / 'independent_readiness_01'
SELF = Path(__file__).resolve()


def sealed_result(folder):
    r = api.read(folder / 'results.json')
    seal = api.read(folder / 'completion.json')
    api.require(seal['passed'] and seal['results_sha256'] == api.sha(folder / 'results.json'), 'completion result seal')
    api.verify_mapping(r.get('artifacts', {}))
    api.verify_mapping(r.get('sources', {}))
    return r


def run():
    api.require(job.utc() < job.policy.utc(api.read(job.WORK)['agent_work_end_utc']), 'work window')
    OUT.mkdir(parents=True, exist_ok=False)
    job.commit(OUT / 'launch.json', {'pid': os.getpid(), 'utc': job.utc().isoformat(), 'new_steps': 0, 'source_sha256': api.sha(SELF)})
    try:
        d = api.read(job.DESIGN); job.verify(d)
        r = job.verify_preflight(d); sealed_result(job.OUT / 'preflight_01')
        dsha = api.sha(job.DESIGN)
        zero_folder = ROOT / 'stage189_evaluations/trial_provenance_20260924/zero_step_03'
        local_folder = ROOT / 'stage190_evaluations/explicit_trial_paired_campaign_20260924/known_transition_01'
        codec_folder = ROOT / 'stage191_evaluations/lossless_trial_references_20260924/qualification_01'
        zero, local, storage = map(sealed_result, (zero_folder, local_folder, codec_folder))
        api.require(zero['passed'] and local['passed'] and storage['passed'], 'prerequisite results')
        api.require(local['new_steps'] == 20000 and storage['new_trajectory_steps'] == 0, 'local and storage step ledger')
        api.require(len(zero['corruption_rejections']) == 18 and len(storage['rejections']) == 13, 'rejection qualifications')
        all_paths = {p.resolve() for p in RUN.rglob('*.json.xz')}
        api.require(len(all_paths) == 38, 'complete raw inventory: 18 probes, 12 live, 8 fixtures')
        decoded, states, independent_history = {}, {}, {}
        reports = []

        def decode(path):
            path = path.resolve()
            if path in decoded: return decoded[path]
            api.require(path in all_paths, 'prefix restricted to inventoried immutable evidence')
            # This separate decoder independently verifies compressed, uncompressed,
            # reference, envelope and full logical-record seals.
            env = pre.wrapper.storage_qualification.independent_envelope(path, dsha)
            meta = env['history']; prefix = None; hist = []
            if meta['prefix'] is not None:
                parent_path = Path(meta['prefix']['path']).resolve()
                decode(parent_path); prefix = states[parent_path]
                api.require(prefix.reference() == meta['prefix'], 'independent exact prefix reference')
                hist = independent_history[parent_path]
            hist = hist + meta['appended_rows']
            packed = json.dumps(hist, separators=(',', ':'), allow_nan=True).encode()
            api.require(len(hist) == meta['length'] and hashlib.sha256(packed).hexdigest() == meta['sha256'], 'independent restored history SHA')
            logical = copy.deepcopy(env['payload'])
            logical['result']['history'] = hist
            logical['result']['checkpoint']['state']['history'] = hist
            canonical = (json.dumps(logical, sort_keys=True, indent=2, allow_nan=True) + '\n').encode()
            api.require(len(canonical) == env['original_uncompressed_bytes'] and hashlib.sha256(canonical).hexdigest() == env['original_uncompressed_sha256'], 'independent full logical bytes')
            record, state = job.codec.read_record(path, dsha, prefix)
            api.require(job.codec.base.raw_bytes(record) == canonical, 'independent/production decoder exact agreement')
            decoded[path], states[path], independent_history[path] = record, state, hist
            reports.append({'path': str(path), 'steps': len(record['rows']), 'raw_sha256': api.sha(path), 'logical_sha256': state.original_sha256, 'prefix_verified': True})
            return record

        for path in sorted(all_paths): decode(path)
        print('RAW_SEALS_AND_INDEPENDENT_DECODING', len(decoded), flush=True)
        cases = {c['id']: c for c in d['cases']}; summaries = []

        def check_record(path, case, before):
            rec = decode(path)
            summary = job.kernel.evaluate(rec, case['spec'], job.binding(d, case), before, geo, dsha, d['minimum_gap_semantics'])
            api.require(summary['passed'] and not summary['complete_observation'], 'bounded numerical qualification only')
            return summary

        job.parent.b.old.parent.configure()
        with job.prior.snapshot.scope(api, d['cases'][0]['spec']['field_metadata']):
            geo = pre.geometry()
            for path in sorted((RUN / 'probes').glob('*.json.xz')):
                saved = api.read(path.with_suffix('.preflight_audit.json')); case = cases[saved['case']]
                if path.name.endswith('_fresh.json.xz'): before = None
                elif path.name == 'split_last.json.xz': before = decode(RUN / 'probes/split_first.json.xz')['result']['checkpoint']
                else: before, _ = pre.seed(d, case)
                summary = check_record(path, case, before)
                a = {k:v for k,v in summary.items() if k != 'audit_seconds'}
                b = {k:v for k,v in saved['summary'].items() if k != 'audit_seconds'}
                api.require(a == b and saved['sha256'] == api.sha(path), 'recomputed full numerical summary')
                summaries.append({'path':str(path), 'summary':summary})
            live = job.root_for('preflight')
            for case in d['cases']:
                before = prefix = receipt_sha = None
                for index in (1, 2):
                    p = job.paths(live, case['id'], index)
                    job.policy.verify_receipt(p, case['id'], index, dsha, d['audit_source_sha256'], api.digest(before), receipt_sha)
                    rec = decode(p['raw']); saved = api.read(p['receipt'])
                    summary = check_record(p['raw'], case, before)
                    api.require(saved['original_raw_sha256'] == states[p['raw'].resolve()].original_sha256, 'receipt exact logical SHA')
                    api.require({k:v for k,v in summary.items() if k!='audit_seconds'} == {k:v for k,v in saved['summary'].items() if k!='audit_seconds'}, 'live independent full summary')
                    arr = np.load(p['trace'], allow_pickle=False)
                    expected = np.array([[x['time_s'], *x['position_m'], *x['orientation'], *x['velocity_generalized']] for x in rec['rows']])
                    api.require(np.array_equal(arr, expected), 'live full trace equals sealed raw')
                    before, receipt_sha = rec['result']['checkpoint'], api.sha(p['receipt'])
                    summaries.append({'path':str(p['raw']), 'summary':summary})
                completion = api.read(live / case['id'] / 'completion.json')
                terminal = api.read(live / case['id'] / 'result.json')
                api.require(completion['result_sha256']==api.sha(live / case['id'] / 'result.json') and terminal['final_result']==rec['result'] and len(terminal['entries'])==2, 'exact terminal/raw inventory')
        serial = decode(RUN / 'probes/serial.json.xz')
        first = decode(RUN / 'probes/split_first.json.xz'); last = decode(RUN / 'probes/split_last.json.xz')
        api.require(serial['rows']==first['rows']+last['rows'] and serial['result']['checkpoint']['state']==last['result']['checkpoint']['state'], 'independent exact restart')
        for i in range(3):
            rec = decode(RUN / 'probes' / f'parallel_{i}.json.xz')
            api.require(rec['rows']==serial['rows'] and rec['result']['checkpoint']['state']==serial['result']['checkpoint']['state'], 'independent parallel identity')
        terminal = api.read(live / 'completion.json')
        api.require(terminal['all_owned_processes_retired'] and terminal['auditor_exit_code']==0 and terminal['producer_exit_codes']=={c:0 for c in cases} and not terminal['stop_reasons'] and not terminal['unrun_cases'], 'clean terminal lifecycle')
        api.require(not list(live.rglob('*.failure.json')) and all(p.stat().st_size==0 for p in RUN.rglob('*.stderr.log')), 'real run failure markers and stderr')
        api.require(not any('.pending.' in p.name for p in live.rglob('*')), 'no real pending files')
        live_result = sealed_result(job.OUT / 'live_preflight_01')
        api.require(live_result['preflight_passed'] and live_result['total_accepted_steps']==6000, 'live terminal evaluation')
        fixtures = []
        for label, passes in [('cutoff_drain',4),('failure_drain',2)]:
            f = api.read(RUN / 'protocol_fixtures' / label / 'auditor_complete.json')
            api.require(len(f['items'])==4 and sum(x['passed'] for x in f['items'])==passes and f['passed']==(passes==4), 'expected fixture drain and failure preserved')
            fixtures.append({'name':label,'saved_record_copies':4,'passed_audits':passes,'new_steps':0})
        actual_new = sum(x['summary']['steps'] for x in summaries)
        api.require(actual_new==r['new_steps']==18200 and actual_new+local['new_steps']==38200<=60000, 'independent work ledger')
        api.require(sum(c['step_ceiling'] for c in d['cases'])+actual_new<=d['budget']['max_new_steps_total'], 'original campaign ceiling')
        api.require(not job.RUN.exists(), 'no production launched')
        required = max(d['resource_scenario']['hours_with_margin'], d['provenance_transaction_hours_with_margin'], r['refreshed_hours_with_margin'])
        now = job.utc(); available=(job.policy.utc(d['simulation_cutoff_utc'])-now).total_seconds()/3600
        free=shutil.disk_usage(ROOT).free; required_storage=d['provenance_bytes_with_margin']+d['budget']['minimum_free_disk_bytes']
        job.verify(d); job.verify_preflight(d)
        result={'numerical_qualification_passed':True,'readiness_audit_passed':True,'campaign_launch_ready':required<=available and free>=required_storage,
                'production_launched':False,'new_trajectory_steps':0,'work_qualification_steps':actual_new+local['new_steps'],
                'stage192_steps':actual_new,'raw_records_independently_decoded':len(decoded),'raw_records':reports,'numerical_reaudits':summaries,
                'protocol_fixtures':fixtures,'terminal':terminal,'required_simulation_hours':required,'available_simulation_hours':available,
                'required_storage_with_reserve_bytes':required_storage,'free_disk_bytes':free,'deadline_gate_passed':required<=available,'storage_gate_passed':free>=required_storage,
                'utc':now.isoformat(),'design_sha256':dsha,'preflight_result_sha256':api.sha(job.OUT/'preflight_01/results.json'),
                'source_sha256':api.sha(SELF),'frozen_sources_verified':len(d['sources']),'preflight_artifacts_verified':len(r['artifacts']),
                'historical_stage187_still_failed':True,'claim':'Bounded software/numerical qualification only. No full-path observation, release estimate or empirical validation. Fresh campaign blocked by unchanged deadline gate.'}
        job.commit(OUT/'results.json',result)
        job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
        print('INDEPENDENT_READINESS',json.dumps({k:v for k,v in result.items() if k not in ('raw_records','numerical_reaudits','terminal')}),flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'new_steps':0})
        raise


if __name__ == '__main__': run()
