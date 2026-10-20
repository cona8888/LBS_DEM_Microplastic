"""Independent zero-step closure check using full producer-history bootstrap."""
from pathlib import Path
import copy, hashlib, os, traceback
import numpy as np
import cone_feasibility_campaign_v1 as s

api, job = s.api, s.job
OUT = job.OUT / 'old_accounting_independent_01'


def counters(p):
    api.require(p['old_failed_run_fully_accounted'] is True and p['old_run_remains_failed'] is True
                and p['new_trajectory_steps'] == 0, 'accounting only, failed run never promoted')
    api.require((p['total_raw_records'], p['independently_verified_records'], p['producer_declared_saved_steps'],
                 p['independently_verified_steps'], p['preserved_failed_saved_steps']) == (3100, 3099, 30631450, 30628462, 2988),
                'exact original ledger')
    api.require(p['original_failed_trace_existed'] is False and p['failed_trace_is_labelled_derived'] is True,
                'derived trace never labelled original')


def run():
    api.require(all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS')), 'BLAS/OpenMP1')
    api.require(not OUT.exists(), 'exclusive independent audit')
    OUT.mkdir(parents=True, exist_ok=False)
    job.commit(OUT / 'launch.json', dict(utc=job.utc().isoformat(), pid=os.getpid(), source_sha256=api.sha(__file__), new_trajectory_steps=0))
    try:
        proof = s.require_old_terminal_closure(); counters(proof)
        qualification_path = job.OUT / 'old_accounting_repair_01/results.json'
        qualification = s.sealed(qualification_path); api.verify_mapping(qualification['inputs'])
        api.require(qualification['passed'] and qualification['numerical_gate_passed'] is False
                    and qualification['old_campaign_remains_failed'] and len(qualification['corrupt_controls_rejected']) == 9,
                    'qualified extraction keeps numerical failure')
        rejected = []
        for key in ('total_raw_records', 'independently_verified_records', 'producer_declared_saved_steps',
                    'independently_verified_steps', 'preserved_failed_saved_steps', 'new_trajectory_steps'):
            bad = copy.deepcopy(proof); bad[key] += 1
            try: counters(bad)
            except RuntimeError: rejected.append(key)
            else: raise RuntimeError('corrupt ledger accepted: ' + key)
        for key in ('old_run_remains_failed', 'old_failed_run_fully_accounted', 'original_failed_trace_existed', 'failed_trace_is_labelled_derived'):
            bad = copy.deepcopy(proof); bad[key] = not bad[key]
            try: counters(bad)
            except RuntimeError: rejected.append(key)
            else: raise RuntimeError('corrupt disclosure accepted: ' + key)
        full = s.sealed(s.OLD_OUT / 'evaluation_01/results.json')
        observed_records = observed_steps = 0
        for detail in full['details']:
            folder = s.OLD_RUN / detail['case']
            raw_files = list(folder.glob('segment_*.json.xz')); markers = list(folder.glob('segment_*.ready.json'))
            saved = sum(api.read(p)['steps'] for p in markers)
            api.require(len(raw_files) == len(markers) == detail['records'] and saved == detail['producer_declared_saved_steps'],
                        'independent filesystem/marker inventory ' + detail['case'])
            observed_records += len(raw_files); observed_steps += saved
        api.require(observed_records == 3100 and observed_steps == 30631450 and full['passed'] is False, 'full failed inventory retained')
        folder = s.OLD_RUN / 's2_i124_fibre_f0p0625'
        producer = api.read(folder / 'result.json')['final_result']
        checks = []
        # No incremental HistoryState or candidate extractor: bootstrap independently
        # from the original sealed producer's complete history and each wire envelope.
        for number in (227, 228):
            raw = folder / ('segment_%05d.json.xz' % number)
            envelope = job.codec.base.read_record(raw, api.sha(s.OLD_DESIGN))
            history = producer['history'][:envelope['history']['length']]
            packed = job.codec.packed_history(history)
            api.require(hashlib.sha256(packed).hexdigest() == envelope['history']['sha256'], 'independent full producer-history prefix')
            record = copy.deepcopy(envelope['payload'])
            record['result']['history'] = history; record['result']['checkpoint']['state']['history'] = history
            canonical = job.codec.base.raw_bytes(record)
            api.require(len(canonical) == envelope['original_uncompressed_bytes']
                        and hashlib.sha256(canonical).hexdigest() == envelope['original_uncompressed_sha256'],
                        'independent complete canonical original record')
            trace_path = folder / 'segment_00227.npy' if number == 227 else Path(proof['derived_failed_trace_path'])
            arr = np.load(trace_path, allow_pickle=False)
            api.require(arr.shape == (len(record['rows']), 13) and np.isfinite(arr).all(), 'independent trace shape/health')
            for row, saved_row in zip(record['rows'], arr):
                api.require(saved_row[0] == row['time_s'] and saved_row[1:4].tolist() == row['position_m']
                            and saved_row[4:7].tolist() == row['orientation'] and saved_row[7:].tolist() == row['velocity_generalized'],
                            'all independently bootstrapped trace columns')
            receipt = api.read(folder / ('segment_%05d.audit.json' % number))
            if number == 227:
                api.require(receipt['status'] == 'independently_verified' and receipt['trace_sha256'] == api.sha(trace_path), 'original independent control trace')
            else:
                api.require(receipt['status'] == 'audit_failed' and 'trace_sha256' not in receipt
                            and not (folder / 'segment_00228.npy').exists(), 'original failure before trace creation')
                api.require(record['result'] == producer and producer['rejected'] == 1 and len(arr) == 2988,
                            'entire failed producer/raw result retained')
            checks.append(dict(segment=number, rows=len(arr), canonical_original_sha256=envelope['original_uncompressed_sha256'],
                               producer_history_sha256=envelope['history']['sha256'], trace_sha256=api.sha(trace_path),
                               trace_is_original=number == 227, numerical_verdict=receipt['status']))
        job.verify(api.read(job.DESIGN))
        result = dict(passed=True, independent_accounting_verified=True, new_trajectory_steps=0,
                      old_campaign_remains_failed=True, numerical_gate_passed=False,
                      total_raw_records=observed_records, total_saved_steps=observed_steps, checks=checks,
                      corrupt_accounting_and_disclosure_controls_rejected=rejected,
                      original_failed_trace_absence_is_expected=True,
                      closure_sha256=api.sha(s.OLD_TERMINAL_PROOF),
                      inputs={str(p): api.sha(p) for p in (Path(__file__), job.DESIGN, s.OLD_TERMINAL_PROOF,
                              s.OLD_TERMINAL_PROOF.parent / 'completion.json', qualification_path,
                              s.OLD_OUT / 'evaluation_01/results.json', folder / 'result.json',
                              folder / 'segment_00227.json.xz', folder / 'segment_00228.json.xz',
                              folder / 'segment_00227.npy', Path(proof['derived_failed_trace_path']))})
        job.commit(OUT / 'results.json', result)
        job.commit(OUT / 'completion.json', dict(passed=True, results_sha256=api.sha(OUT / 'results.json')))
        print('INDEPENDENT_OLD_ACCOUNTING_PASS', api.sha(OUT / 'results.json'), flush=True)
    except Exception as error:
        job.commit(OUT / 'failure.json', dict(error=repr(error), traceback=traceback.format_exc(), new_trajectory_steps=0)); raise


if __name__ == '__main__': run()
