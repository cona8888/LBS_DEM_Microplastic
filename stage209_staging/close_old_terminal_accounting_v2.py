"""Zero-step old failed-ledger closure; never invent an original failed trace.

The original auditor rejects segment228 before writing its .npy. V1 incorrectly
expected that file. V2 preserves V1 and all its other checks, qualifies extraction
against original passing227, and labels the C-side228 trace as derived evidence.
No production source, numerical gate, old output or trajectory is modified.
"""
from pathlib import Path
import copy, os, sys, traceback
import numpy as np
import psutil
import close_old_terminal_accounting_v1 as original

s, api, job = original.s, original.api, original.job
WORK = s.ROOT / 'stage209_evaluations' / s.BASE / 'old_accounting_repair_01'
V1 = Path(original.__file__).resolve()


def extract(record):
    rows = record['rows']
    return np.column_stack((np.asarray([r['time_s'] for r in rows]),
                            np.asarray([r['position_m'] for r in rows]),
                            np.asarray([r['orientation'] for r in rows]),
                            np.asarray([r['velocity_generalized'] for r in rows]))).astype(np.float64)


def validate_trace(trace, record):
    expected = np.asarray([[r['time_s'], *r['position_m'], *r['orientation'],
                            *r['velocity_generalized']] for r in record['rows']], dtype=np.float64)
    api.require(trace.shape == (len(record['rows']), 13) and np.isfinite(trace).all(),
                'exact finite trace dimensions')
    api.require(np.array_equal(trace, expected), 'trace exactly authenticated decoded rows')
    r = record['result']
    endpoint = np.asarray([r['time_s'], *r['position_m'], *r['orientation'], *r['velocity_generalized']])
    api.require(np.array_equal(trace[-1], endpoint), 'trace exactly sealed producer endpoint')
    api.require(np.all(np.diff(trace[:, 0]) > 0), 'strictly increasing saved clocks')


def prefix(number):
    codec = job.codec
    return codec.HistoryState(**api.read(s.stack.RECON / ('prefix_%05d.json' % number)),
                              history_bytes=codec.packed_history(api.read(s.stack.RECON / ('history_%05d.json' % number))))


def run():
    api.require(all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS')),
                'BLAS/OpenMP1')
    d = api.read(s.OLD_DESIGN); api.verify_mapping(d['sources']); api.verify_mapping(d['inputs'])
    fresh = api.read(job.DESIGN); job.verify(fresh)
    api.require(fresh['sources'][str(V1)] == api.sha(V1), 'original frozen V1 closure unchanged')
    api.require(not s.OLD_TERMINAL_PROOF.exists() and not WORK.exists(), 'exclusive new accounting outputs')
    WORK.mkdir(parents=True, exist_ok=False)
    current = psutil.Process()
    job.commit(WORK / 'launch.json', dict(pid=current.pid, created=current.create_time(), argv=current.cmdline(),
                utc=job.utc().isoformat(), source_sha256=api.sha(__file__), design_sha256=api.sha(job.DESIGN),
                new_trajectory_steps=0))
    try:
        witness = s.OLD_OUT / 'terminal_evaluator_01'
        exit_record, seal = api.read(witness / 'exit.json'), api.read(witness / 'completion.json')
        api.require(seal['exit_sha256'] == api.sha(witness / 'exit.json') and seal['passed'] and exit_record['exit_code'] == 0,
                    'original frozen full evaluator witnessed normal closure')
        full = s.sealed(s.OLD_OUT / 'evaluation_01/results.json')
        api.require(exit_record['results_sha256'] == api.sha(s.OLD_OUT / 'evaluation_01/results.json') and not full['passed'],
                    'original failed result never promoted')
        inventory = s.sealed(s.OLD_OUT / 'terminal_failure_01/results.json')
        terminal = api.read(s.OLD_RUN / 'completion.json')
        api.require(terminal['all_owned_processes_retired'] and terminal['stop_reasons'] and len(terminal['unrun_cases']) == 1,
                    'old failed lifecycle retained')
        declared = sum(c['declared_saved_steps'] for c in inventory['cases']); verified = 0
        details = {x['case']: x for x in full['details']}
        failed_name, unrun = 's2_i124_fibre_f0p0625', 's2_i124_sphere_f0p0625'
        for x in inventory['cases']:
            z = details[x['case']]; expected = x['declared_saved_steps'] - (2988 if x['case'] == failed_name else 0)
            errors = ["KeyError('audit_source_sha256')"] if x['case'] == failed_name else (["RuntimeError('producer completion present')"] if x['case'] == unrun else [])
            api.require(z['records'] == x['sealed_segments'] and z['producer_declared_saved_steps'] == x['declared_saved_steps']
                        and z['verified_accepted_steps'] == expected and z['errors'] == errors,
                        'exact disclosed old terminal case ledger/errors ' + x['case'])
            verified += expected
        api.require(declared == 30631450 and verified == 30628462 and full['producer_declared_saved_steps'] == declared
                    and full['total_accepted_steps'] == verified, 'inclusive saved/verified/failed balance')
        folder = s.OLD_RUN / failed_name
        raw, ready = folder / 'segment_00228.json.xz', folder / 'segment_00228.ready.json'
        receipt = api.read(folder / 'segment_00228.audit.json')
        api.require(receipt['status'] == 'audit_failed' and receipt['error'] == "RuntimeError('supported nonfailed status, zero rejected trials')"
                    and receipt['ready_sha256'] == api.sha(ready), 'original numerical failure receipt')
        api.require(full['unsealed_artifacts'] == [str(ready)], 'only excluded failed ready marker')
        auth = s.sealed(s.ROOT / 'stage206_evaluations/contact_failure_20260930/failed_evidence_01/results.json')
        api.verify_mapping(auth['inputs'])
        recon = s.sealed(s.stack.RECON / 'results.json'); api.verify_mapping(recon['inputs']); api.verify_mapping(recon['artifacts'])
        record, state = job.codec.read_record(raw, api.sha(s.OLD_DESIGN), prefix(227))
        before = api.read(s.stack.RECON / 'checkpoint_00227.json'); result, marker = record['result'], api.read(ready)
        api.require(record['input_checkpoint_sha256'] == api.digest(before)
                    and result['steps'] - before['state']['steps'] == len(record['rows']) == marker['steps'] == 2988,
                    'failed bundle exact clock/step ancestry')
        producer = api.read(folder / 'result.json')
        api.require(producer['final_result'] == result and result['rejected'] == 1
                    and result['rejected_trials'] == auth['rejected_trials'], 'all producer/rejected evidence retained')
        # V1's missing trace is expected: kernel.evaluate raises before np.save.
        absent = folder / 'segment_00228.npy'
        api.require(not absent.exists() and 'trace_path' not in receipt and 'trace_sha256' not in receipt,
                    'no original failed trace exists or is invented')
        job.commit(WORK / 'preserved_v1_failure.json', dict(recorded_utc=job.utc().isoformat(),
                    source_sha256=api.sha(V1), observed_exit_code=1, new_trajectory_steps=0,
                    observed_error="FileNotFoundError: original failed segment_00228.npy absent",
                    missing_original_path=str(absent), original_failure_receipt_sha256=api.sha(folder / 'segment_00228.audit.json'),
                    explanation='Original physical auditor rejects before trace creation. V1 expected a nonexistent derivative; no old file was removed or recreated by this repair.'))
        # Independent passing archive/receipt provides a non-tautological extractor control.
        control_raw, control_path = folder / 'segment_00227.json.xz', folder / 'segment_00227.npy'
        control_record, _ = job.codec.read_record(control_raw, api.sha(s.OLD_DESIGN), prefix(226))
        control_receipt = api.read(folder / 'segment_00227.audit.json')
        api.require(control_receipt['status'] == 'independently_verified'
                    and control_receipt['trace_sha256'] == api.sha(control_path) == full['artifacts'][str(control_path)],
                    'original passing control trace/receipt/full-audit hash')
        control = np.load(control_path, allow_pickle=False)
        api.require(np.array_equal(extract(control_record), control), 'independent column extraction exactly original control')
        validate_trace(control, control_record)
        rejected_controls = []
        for label, column in [('clock', 0), ('position', 1), ('orientation', 4), ('velocity', 7), ('angular_velocity', 12)]:
            bad = control.copy(); bad[0, column] = np.nextafter(bad[0, column], np.inf)
            try: validate_trace(bad, control_record)
            except RuntimeError: rejected_controls.append(label)
            else: raise RuntimeError('corrupt trace accepted: ' + label)
        for label, bad in [('nan', np.full_like(control, np.nan)), ('missing_row', control[:-1]), ('missing_column', control[:, :-1])]:
            try: validate_trace(bad, control_record)
            except RuntimeError: rejected_controls.append(label)
            else: raise RuntimeError('corrupt trace accepted: ' + label)
        bad_record = copy.deepcopy(control_record); bad_record['result']['time_s'] = np.nextafter(bad_record['result']['time_s'], np.inf)
        try: validate_trace(control, bad_record)
        except RuntimeError: rejected_controls.append('producer_endpoint')
        else: raise RuntimeError('corrupt producer endpoint accepted')
        trace = extract(record); validate_trace(trace, record)
        derived = WORK / 'derived_failed_00228.npy'
        with derived.open('xb') as stream:
            np.save(stream, trace, allow_pickle=False); stream.flush(); os.fsync(stream.fileno())
        validate_trace(np.load(derived, allow_pickle=False), record)
        api.verify_mapping(full['artifacts'])
        for process in psutil.process_iter(['name']):
            if process.pid == os.getpid() or 'python' not in (process.info['name'] or '').lower(): continue
            try: api.require(not any(str(x) in process.cmdline() for x in
                            (s.ROOT / 'stage205_staging/receipt_repaired_campaign_v2.py', s.ROOT / 'stage205_staging/run_terminal_evaluator_v1.py')),
                             'old evaluator/witness identity retired')
            except psutil.NoSuchProcess: continue
        qualification = dict(passed=True, new_trajectory_steps=0, passing_control_rows=len(control),
                    passing_control_exact=True, corrupt_controls_rejected=rejected_controls, failed_rows=len(trace),
                    original_failed_trace_absent=True, failed_trace_is_derived_not_original=True,
                    numerical_gate_passed=False, old_campaign_remains_failed=True,
                    inputs={str(p): api.sha(p) for p in (Path(__file__), V1, control_raw, control_path,
                            folder / 'segment_00227.audit.json', raw, ready, derived, WORK / 'preserved_v1_failure.json')})
        job.commit(WORK / 'results.json', qualification)
        job.commit(WORK / 'completion.json', dict(passed=True, results_sha256=api.sha(WORK / 'results.json')))
        files = [Path(__file__), V1, job.DESIGN, s.OLD_DESIGN, s.OLD_OUT / 'evaluation_01/results.json',
                 s.OLD_OUT / 'evaluation_01/completion.json', witness / 'exit.json', witness / 'completion.json',
                 s.OLD_OUT / 'terminal_failure_01/results.json', raw, raw.with_suffix('.seal.json'), ready,
                 folder / 'segment_00228.audit.json', folder / 'result.json', folder / 'completion.json',
                 s.ROOT / 'stage206_evaluations/contact_failure_20260930/failed_evidence_01/results.json',
                 s.stack.RECON / 'results.json', s.stack.RECON / 'checkpoint_00227.json',
                 s.stack.RECON / 'prefix_00227.json', s.stack.RECON / 'history_00227.json',
                 WORK / 'results.json', WORK / 'completion.json', WORK / 'preserved_v1_failure.json', derived]
        proof = dict(old_failed_run_fully_accounted=True, old_run_remains_failed=True, new_trajectory_steps=0,
                     total_raw_records=3100, independently_verified_records=3099, producer_declared_saved_steps=declared,
                     independently_verified_steps=verified, preserved_failed_saved_steps=2988,
                     failed_raw_history_trace_authenticated=True, original_failed_trace_existed=False,
                     failed_trace_is_labelled_derived=True, derived_failed_trace_path=str(derived),
                     unrun_cases=[unrun], terminal_frozen_audit_preserved_errors={failed_name: details[failed_name]['errors'],
                                                                               unrun: details[unrun]['errors']},
                     explanation='All3099 passing bundles retain the frozen full audit. Failed228 compressed/uncompressed/canonical raw, full history, checkpoint ancestry and endpoint are authenticated separately. Its original auditor rejected before creating any trace; a labelled C-side derivative is independently qualified against original passing227. Rejection and2,988 failed saved steps are preserved, not numerically accepted.',
                     inputs={str(p): api.sha(p) for p in files})
        api.verify_mapping(proof['inputs']); job.verify(fresh)
        job.commit(s.OLD_TERMINAL_PROOF, proof)
        job.commit(s.OLD_TERMINAL_PROOF.parent / 'completion.json', dict(passed=True, results_sha256=api.sha(s.OLD_TERMINAL_PROOF)))
        s.require_old_terminal_closure()
        print('OLD_FAILED_LEDGER_CLOSED_V2', verified, declared, api.sha(s.OLD_TERMINAL_PROOF), flush=True)
    except Exception as error:
        job.commit(WORK / 'failure.json', dict(error=repr(error), traceback=traceback.format_exc(), new_trajectory_steps=0,
                    utc=job.utc().isoformat())); raise


if __name__ == '__main__': run()
