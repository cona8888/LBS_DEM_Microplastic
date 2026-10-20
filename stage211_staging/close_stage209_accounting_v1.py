"""Zero-step failed-inclusive Stage209 accounting. Never accepts rejected steps."""
from pathlib import Path
import copy, hashlib, json, os, shutil, sys, traceback
import numpy as np
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage209_staging'))
import cone_feasibility_campaign_v1 as frozen
api, job = frozen.api, frozen.job
CONTRACT = ROOT / 'stage211_designs/terminal_accounting_20261001/contract_01.json'
OUT = ROOT / 'stage211_evaluations/terminal_accounting_20261001/closure_01'
RECON = ROOT / 'stage210_evaluations/three_contact_failure_20261001/reconstructed_window_01'
AUTH = ROOT / 'stage210_evaluations/three_contact_failure_20261001/failed_evidence_01'
FAILED = 's2_i124_sphere_f0p0625'


def must(condition, label):
    if not condition:
        raise RuntimeError(label)


def sealed(path):
    value = api.read(path)
    marker = api.read(Path(path).parent / 'completion.json')
    must(marker['results_sha256'] == api.sha(path), 'result seal ' + str(path))
    return value


def precheck():
    c = api.read(CONTRACT)
    must(c['new_trajectory_steps'] == 0 and not c['numerical_policy_change_authorized'], 'accounting only')
    must(all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS')), 'threads1')
    must(shutil.disk_usage(ROOT).free >= c['minimum_free_disk_bytes'], 'C reserve')
    must(job.utc() < job.policy.utc(c['audit_cutoff_utc']), 'audit before cutoff')
    api.verify_mapping(c['sources']); api.verify_mapping(c['inputs'])
    job.verify(api.read(job.DESIGN))
    must(not frozen.active_owned(False), 'no competing owned worker/audit')
    terminal = api.read(job.RUN / 'completion.json')
    must(terminal['all_owned_processes_retired'] and terminal['unrun_cases'] == [], 'six original cases dispatched/retired')
    return c


def extract(record):
    rows = record['rows']
    return np.column_stack(([r['time_s'] for r in rows], [r['position_m'] for r in rows],
                            [r['orientation'] for r in rows], [r['velocity_generalized'] for r in rows])).astype(np.float64)


def validate_trace(trace, record):
    expected = np.asarray([[r['time_s'], *r['position_m'], *r['orientation'], *r['velocity_generalized']]
                           for r in record['rows']], dtype=np.float64)
    must(trace.dtype == np.float64 and trace.shape == (len(record['rows']), 13) and np.isfinite(trace).all(), 'trace shape/health')
    must(trace.tobytes() == expected.tobytes(), 'bitwise trace rows')
    result = record['result']
    endpoint = np.asarray([result['time_s'], *result['position_m'], *result['orientation'], *result['velocity_generalized']])
    must(trace[-1].tobytes() == endpoint.tobytes() and np.all(np.diff(trace[:, 0]) > 0), 'exact endpoint/clock')


def ledger(c, full):
    must(full['passed'] is False and full['integrity_passed'] is False, 'original terminal failure retained')
    must(full['design_sha256'] == api.sha(job.DESIGN), 'evaluation design')
    rows = []
    expected = {x['case']: x for x in c['cases']}
    must({x['case'] for x in full['details']} == set(expected), 'exact six cases')
    for x in full['details']:
        e = expected[x['case']]
        must({k: x[k] for k in ('records', 'producer_declared_saved_steps', 'verified_accepted_steps', 'errors')}
             == {k: e[k] for k in ('records', 'producer_declared_saved_steps', 'verified_accepted_steps', 'errors')}, 'case ledger ' + x['case'])
        folder = job.RUN / x['case']
        producer = api.read(folder / 'result.json'); done = api.read(folder / 'completion.json')
        must(done['result_sha256'] == api.sha(folder / 'result.json') and producer['design_sha256'] == api.sha(job.DESIGN), 'producer seal')
        raw = sorted(folder.glob('segment_*.json.xz')); markers = sorted(folder.glob('segment_*.ready.json'))
        receipts = sorted(folder.glob('segment_*.audit.json'))
        must(len(raw) == len(markers) == len(receipts) == x['records'] == len(producer['entries']), 'inclusive inventory')
        saved = 0
        for i, (archive, ready, receipt) in enumerate(zip(raw, markers, receipts), 1):
            must(archive.name == 'segment_%05d.json.xz' % i and ready.name == 'segment_%05d.ready.json' % i
                 and receipt.name == 'segment_%05d.audit.json' % i, 'contiguous identity')
            marker = api.read(ready); verdict = api.read(receipt); seal = api.read(archive.with_suffix('.seal.json'))
            must(marker == producer['entries'][i - 1] and marker['case'] == x['case'] and marker['segment'] == i
                 and marker['design_sha256'] == api.sha(job.DESIGN), 'producer marker identity')
            must(verdict['ready_sha256'] == api.sha(ready) and marker['seal_sha256'] == api.sha(archive.with_suffix('.seal.json'))
                 and marker['raw_sha256'] == seal['compressed_sha256'] == api.sha(archive), 'raw/seal/receipt identity')
            must(verdict['status'] == ('audit_failed' if x['case'] == FAILED and i == 33 else 'independently_verified'), 'original verdict')
            must(type(marker['steps']) is int and 0 < marker['steps'] <= 10000, 'bounded saved steps')
            saved += marker['steps']
        must(saved == x['producer_declared_saved_steps'], 'saved step sum')
        rows.append(dict(case=x['case'], records=len(raw), saved_steps=saved, verified_steps=x['verified_accepted_steps']))
    must(sum(x['records'] for x in rows) == 3319 and sum(x['saved_steps'] for x in rows) == 32284748
         and sum(x['verified_steps'] for x in rows) == 32284084, 'full balance')
    return rows


def run():
    c = precheck()
    must(not OUT.exists(), 'exclusive closure output')
    OUT.mkdir(parents=True, exist_ok=False)
    p = psutil.Process()
    job.commit(OUT / 'launch.json', dict(pid=p.pid, created=p.create_time(), argv=p.cmdline(), utc=job.utc().isoformat(),
               contract_sha256=api.sha(CONTRACT), source_sha256=api.sha(__file__), new_trajectory_steps=0))
    try:
        full = sealed(job.OUT / 'evaluation_01/results.json')
        exit_record = api.read(job.OUT / 'terminal_evaluator_01/exit.json')
        witness = api.read(job.OUT / 'terminal_evaluator_01/completion.json')
        must(witness['exit_sha256'] == api.sha(job.OUT / 'terminal_evaluator_01/exit.json') and witness['passed']
             and exit_record['exit_code'] == 0 and exit_record['results_sha256'] == api.sha(job.OUT / 'evaluation_01/results.json')
             and not exit_record['audit_passed'] and exit_record['new_trajectory_steps'] == 0, 'witnessed failure, zero-step audit')
        rows = ledger(c, full)
        for i, (path, digest) in enumerate(full['artifacts'].items(), 1):
            must(api.sha(path) == digest, 'frozen full-audit artifact ' + path)
            if i % 1000 == 0:
                print('FROZEN_ARTIFACT_RECHECK', i, len(full['artifacts']), flush=True)
        auth, recon = sealed(AUTH / 'results.json'), sealed(RECON / 'results.json')
        api.verify_mapping(auth['inputs']); api.verify_mapping(recon['inputs']); api.verify_mapping(recon['artifacts'])
        folder = job.RUN / FAILED
        state = job.codec.HistoryState(**api.read(RECON / 'prefix_00031.json'),
                history_bytes=job.codec.packed_history(api.read(RECON / 'history_00031.json')))
        control, prefix = job.codec.read_record(folder / 'segment_00032.json.xz', api.sha(job.DESIGN), state)
        failed, _ = job.codec.read_record(folder / 'segment_00033.json.xz', api.sha(job.DESIGN), prefix)
        must(control['input_checkpoint_sha256'] == api.digest(api.read(RECON / 'checkpoint_00031.json'))
             and failed['input_checkpoint_sha256'] == api.digest(control['result']['checkpoint']), 'checkpoint ancestry')
        must(failed['result'] == api.read(folder / 'result.json')['final_result'] and failed['result']['status'] == 'numerical_failure'
             and failed['result']['rejected'] == 30 and failed['result']['rejected_trials'] == auth['rejected_trials'], 'all rejected evidence')
        must(failed['result']['steps'] - control['result']['steps'] == len(failed['rows']) == 664, 'failed exact step difference')
        must(failed['result']['checkpoint']['state_sha256'] == api.digest(failed['result']['checkpoint']['state']), 'failed checkpoint state seal')
        receipt = api.read(folder / 'segment_00033.audit.json')
        must(receipt['error'] == "RuntimeError('supported nonfailed status, zero rejected trials')" and 'trace_sha256' not in receipt
             and not (folder / 'segment_00033.npy').exists(), 'original rejection/trace absence')
        must(full['unsealed_artifacts'] == [str(folder / 'segment_00033.ready.json')], 'sole excluded failure marker')
        arr = np.load(folder / 'segment_00032.npy', allow_pickle=False)
        must(extract(control).tobytes() == arr.tobytes(), 'independent original passing32 extraction control')
        validate_trace(arr, control)
        negative = []
        for label, col in [('clock', 0), ('position', 1), ('orientation', 4), ('velocity', 7), ('angular_velocity', 12)]:
            bad = arr.copy(); bad[0, col] = np.nextafter(bad[0, col], np.inf)
            try:
                validate_trace(bad, control)
            except RuntimeError:
                negative.append(label)
            else:
                raise RuntimeError('corrupt trace accepted ' + label)
        for label, bad in [('nan', np.full_like(arr, np.nan)), ('row_count', arr[:-1]), ('column_count', arr[:, :-1])]:
            try:
                validate_trace(bad, control)
            except RuntimeError:
                negative.append(label)
            else:
                raise RuntimeError('corrupt dimensions/health accepted ' + label)
        wrong = copy.deepcopy(control); wrong['result']['time_s'] = np.nextafter(wrong['result']['time_s'], np.inf)
        try:
            validate_trace(arr, wrong)
        except RuntimeError:
            negative.append('producer_endpoint')
        else:
            raise RuntimeError('wrong endpoint accepted')
        trace = extract(failed); validate_trace(trace, failed)
        derived = OUT / 'derived_rejected_00033.npy'
        with derived.open('xb') as stream:
            np.save(stream, trace, allow_pickle=False); stream.flush(); os.fsync(stream.fileno())
        validate_trace(np.load(derived, allow_pickle=False), failed)
        files = [CONTRACT, Path(__file__), job.DESIGN, job.OUT / 'evaluation_01/results.json', job.OUT / 'evaluation_01/completion.json',
                 job.OUT / 'terminal_evaluator_01/exit.json', job.OUT / 'terminal_evaluator_01/completion.json', job.RUN / 'completion.json',
                 AUTH / 'results.json', RECON / 'results.json', folder / 'result.json', folder / 'completion.json', derived]
        files += [folder / ('segment_%05d%s' % (n, suffix)) for n in (32, 33)
                  for suffix in ('.json.xz', '.json.seal.json', '.ready.json', '.audit.json')]
        files += [folder / 'segment_00032.npy', RECON / 'prefix_00031.json', RECON / 'history_00031.json', RECON / 'checkpoint_00031.json']
        r = dict(accounting_check_passed=True, independent_accounting_verification_pending=True, full_failed_run_accounting_closed=False,
                 campaign_passed=False, numerical_gate_passed=False, new_trajectory_steps=0, total_raw_records=3319,
                 independently_verified_records=3318, producer_declared_saved_steps=32284748, independently_verified_steps=32284084,
                 preserved_failed_saved_steps=664, cases=rows, unrun_cases=[], original_failed_trace_existed=False,
                 failed_trace_is_labelled_derived=True, derived_failed_trace_path=str(derived), original_frozen_error_preserved=full['details'][-1]['errors'],
                 original_passing_control_rows=len(arr), corrupt_trace_controls_rejected=negative,
                 failed_raw_history_checkpoint_and_trace_authenticated=True, frozen_artifacts_reauthenticated=len(full['artifacts']),
                 inputs={str(p): api.sha(p) for p in files},
                 claim='Accounting only. Rejected33 remains numerically failed. No original trace invented, raw altered, gate changed or new trajectory.')
        job.verify(api.read(job.DESIGN)); must(shutil.disk_usage(ROOT).free >= c['minimum_free_disk_bytes'], 'closing reserve')
        job.commit(OUT / 'results.json', r)
        job.commit(OUT / 'completion.json', dict(accounting_check_passed=True, results_sha256=api.sha(OUT / 'results.json'), campaign_passed=False))
        print('FAILED_ACCOUNTING_CANDIDATE', api.sha(OUT / 'results.json'), flush=True)
    except Exception as error:
        job.commit(OUT / 'failure.json', dict(error=repr(error), traceback=traceback.format_exc(), utc=job.utc().isoformat(), new_trajectory_steps=0))
        raise


if __name__ == '__main__':
    run()
