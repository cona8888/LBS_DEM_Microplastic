"""Independent producer-history bootstrap and ledger audit; no candidate extractor."""
from pathlib import Path
import copy, hashlib, json, os, shutil, sys, traceback
import numpy as np
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage209_staging'))
import cone_feasibility_campaign_v1 as frozen
api, job = frozen.api, frozen.job
BASE = ROOT / 'stage211_evaluations/terminal_accounting_20261001'
CONTRACT = ROOT / 'stage211_designs/terminal_accounting_20261001/contract_01.json'
OUT = BASE / 'independent_01'


def check(ok, message):
    if not ok:
        raise RuntimeError(message)


def counters(p):
    check((p['total_raw_records'], p['independently_verified_records'], p['producer_declared_saved_steps'],
           p['independently_verified_steps'], p['preserved_failed_saved_steps'], p['new_trajectory_steps'])
          == (3319, 3318, 32284748, 32284084, 664, 0), 'exact inclusive counts')
    check(p['campaign_passed'] is False and p['numerical_gate_passed'] is False and p['original_failed_trace_existed'] is False
          and p['failed_trace_is_labelled_derived'] is True and p['full_failed_run_accounting_closed'] is False,
          'candidate is accounting only, pending independent closure')


def bootstrap(path, producer, design):
    # Direct complete producer history, not HistoryState, candidate decoder or extractor.
    env = frozen.stack.storage.read_envelope(path, design)
    history = producer['history'][:env['history']['length']]
    packed = json.dumps(history, separators=(',', ':'), allow_nan=True,
                        default=api.frozen.h.json_value).encode('utf-8')
    check(hashlib.sha256(packed).hexdigest() == env['history']['sha256'], 'full producer-history seal')
    record = copy.deepcopy(env['payload'])
    record['result']['history'] = history
    record['result']['checkpoint']['state']['history'] = history
    canonical = (json.dumps(record, sort_keys=True, indent=2, allow_nan=True,
                            default=api.frozen.h.json_value) + '\n').encode('utf-8')
    check(len(canonical) == env['original_uncompressed_bytes']
          and hashlib.sha256(canonical).hexdigest() == env['original_uncompressed_sha256'], 'original complete canonical record')
    cp = record['result']['checkpoint']
    check(cp['state_sha256'] == api.digest(cp['state']), 'complete checkpoint state seal')
    return record, env


def run():
    c = api.read(CONTRACT)
    check(all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS')), 'threads1')
    check(job.utc() < job.policy.utc(c['audit_cutoff_utc']) and shutil.disk_usage(ROOT).free >= c['minimum_free_disk_bytes'], 'cutoff/reserve')
    api.verify_mapping(c['sources']); api.verify_mapping(c['inputs']); job.verify(api.read(job.DESIGN))
    check(not frozen.active_owned(False) and not OUT.exists(), 'exclusive independent audit, no owned work')
    proofpath = BASE / 'closure_01/results.json'; proof = api.read(proofpath)
    check(api.read(proofpath.parent / 'completion.json')['results_sha256'] == api.sha(proofpath), 'closure candidate seal')
    counters(proof); api.verify_mapping(proof['inputs'])
    OUT.mkdir(parents=True, exist_ok=False)
    p = psutil.Process()
    job.commit(OUT / 'launch.json', dict(pid=p.pid, created=p.create_time(), argv=p.cmdline(), utc=job.utc().isoformat(),
               source_sha256=api.sha(__file__), contract_sha256=api.sha(CONTRACT), new_trajectory_steps=0))
    try:
        negative = []
        for key in ('total_raw_records', 'independently_verified_records', 'producer_declared_saved_steps',
                    'independently_verified_steps', 'preserved_failed_saved_steps', 'new_trajectory_steps'):
            bad = copy.deepcopy(proof); bad[key] += 1
            try:
                counters(bad)
            except RuntimeError:
                negative.append(key)
            else:
                raise RuntimeError('ledger corruption accepted ' + key)
        for key in ('campaign_passed', 'numerical_gate_passed', 'original_failed_trace_existed',
                    'failed_trace_is_labelled_derived', 'full_failed_run_accounting_closed'):
            bad = copy.deepcopy(proof); bad[key] = not bad[key]
            try:
                counters(bad)
            except RuntimeError:
                negative.append(key)
            else:
                raise RuntimeError('disclosure corruption accepted ' + key)
        fullpath = job.OUT / 'evaluation_01/results.json'; full = api.read(fullpath)
        check(api.read(fullpath.parent / 'completion.json')['results_sha256'] == api.sha(fullpath) and full['passed'] is False, 'original failed evaluation')
        totals = [0, 0, 0]; cases = []
        for item in full['details']:
            folder = job.RUN / item['case']; markers = sorted(folder.glob('segment_*.ready.json'))
            raw = sorted(folder.glob('segment_*.json.xz')); receipts = sorted(folder.glob('segment_*.audit.json'))
            check(len(markers) == len(raw) == len(receipts) == item['records'], 'independent exact inventory')
            saved = sum(api.read(x)['steps'] for x in markers)
            check(saved == item['producer_declared_saved_steps'], 'independent saved sum')
            passing = sum(api.read(x)['steps'] for x, y in zip(markers, receipts) if api.read(y)['status'] == 'independently_verified')
            check(passing == item['verified_accepted_steps'], 'independent verdict step sum')
            totals = [totals[0] + len(raw), totals[1] + saved, totals[2] + passing]
            cases.append(dict(case=item['case'], records=len(raw), saved_steps=saved, independently_verified_steps=passing))
        check(totals == [3319, 32284748, 32284084] and totals[1] - totals[2] == 664, 'independent full accounting balance')
        # Rehash the original full evaluator's passing artifacts independently of closure implementation.
        for i, (path, sha) in enumerate(full['artifacts'].items(), 1):
            digest = hashlib.sha256()
            with Path(path).open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
            check(digest.hexdigest() == sha, 'independent frozen artifact seal')
            if i % 1000 == 0:
                print('INDEPENDENT_SEALS', i, len(full['artifacts']), flush=True)
        folder = job.RUN / 's2_i124_sphere_f0p0625'; producerpath = folder / 'result.json'
        check(api.read(folder / 'completion.json')['result_sha256'] == api.sha(producerpath), 'producer seal')
        producer = api.read(producerpath)['final_result']; records = {}; checks = []
        for n in (31, 32, 33):
            path = folder / ('segment_%05d.json.xz' % n)
            record, env = bootstrap(path, producer, api.sha(job.DESIGN)); records[n] = record
            if n > 31:
                check(record['input_checkpoint_sha256'] == api.digest(records[n - 1]['result']['checkpoint']), 'independent checkpoint ancestry')
            if n >= 32:
                tracepath = folder / 'segment_00032.npy' if n == 32 else Path(proof['derived_failed_trace_path'])
                arr = np.load(tracepath, allow_pickle=False)
                check(arr.dtype == np.float64 and arr.shape == (len(record['rows']), 13) and np.isfinite(arr).all(), 'independent trace shape/health')
                for row, savedrow in zip(record['rows'], arr):
                    independent = np.asarray([row['time_s'], *row['position_m'], *row['orientation'], *row['velocity_generalized']], dtype=np.float64)
                    check(savedrow.tobytes() == independent.tobytes(), 'independent bitwise trace columns')
                final = record['result']
                endpoint = np.asarray([final['time_s'], *final['position_m'], *final['orientation'], *final['velocity_generalized']], dtype=np.float64)
                check(arr[-1].tobytes() == endpoint.tobytes() and np.all(np.diff(arr[:, 0]) > 0), 'independent trace endpoint/clock')
                receipt = api.read(folder / ('segment_%05d.audit.json' % n))
                check(receipt['status'] == ('independently_verified' if n == 32 else 'audit_failed'), 'original verdict retained')
                if n == 32:
                    check(receipt['trace_sha256'] == api.sha(tracepath) == full['artifacts'][str(tracepath)], 'independent original passing control')
                else:
                    check(record['result'] == producer and producer['rejected'] == 30 and len(arr) == 664, 'entire rejected producer result')
                    check('trace_sha256' not in receipt and not (folder / 'segment_00033.npy').exists(), 'derived not original')
                    check(producer['steps'] - records[32]['result']['steps'] == 664, 'independent failed step ancestry')
                checks.append(dict(segment=n, rows=len(arr), original_canonical_sha256=env['original_uncompressed_sha256'],
                                   complete_history_sha256=env['history']['sha256'], trace_sha256=api.sha(tracepath), trace_is_original=n == 32))
        frozen.verify(api.read(job.DESIGN))
        check(shutil.disk_usage(ROOT).free >= c['minimum_free_disk_bytes'], 'closing reserve')
        r = dict(independent_accounting_verified=True, full_failed_run_accounting_closed=True, campaign_passed=False,
                 numerical_gate_passed=False, new_trajectory_steps=0, total_raw_records=3319, independently_verified_records=3318,
                 producer_declared_saved_steps=32284748, independently_verified_steps=32284084, preserved_failed_saved_steps=664,
                 corrupt_accounting_and_disclosure_controls_rejected=negative, cases=cases, checks=checks,
                 original_failed_trace_existed=False, failed_trace_is_labelled_derived=True,
                 closure_candidate_sha256=api.sha(proofpath), original_evaluation_sha256=api.sha(fullpath),
                 inputs={str(p): api.sha(p) for p in (Path(__file__), CONTRACT, proofpath, proofpath.parent / 'completion.json', fullpath,
                         fullpath.parent / 'completion.json', producerpath, folder / 'completion.json', folder / 'segment_00031.json.xz',
                         folder / 'segment_00032.json.xz', folder / 'segment_00033.json.xz', folder / 'segment_00032.npy', Path(proof['derived_failed_trace_path']))},
                 claim='Full failed-inclusive accounting is closed using the immutable passing evaluator plus independently authenticated rejected raw/history/checkpoint/derived trace. Campaign remains failed/incomplete;664 saved steps stay rejected.')
        api.verify_mapping(r['inputs'])
        job.commit(OUT / 'results.json', r)
        job.commit(OUT / 'completion.json', dict(independent_accounting_verified=True, results_sha256=api.sha(OUT / 'results.json'), campaign_passed=False))
        print('INDEPENDENT_FAILED_ACCOUNTING_CLOSED', api.sha(OUT / 'results.json'), flush=True)
    except Exception as error:
        job.commit(OUT / 'failure.json', dict(error=repr(error), traceback=traceback.format_exc(), utc=job.utc().isoformat(), new_trajectory_steps=0))
        raise


if __name__ == '__main__':
    run()
