"""One bounded diagnostic, not a restart of failed Stage193 production.

Qualified integration bytecode, original spec/binding/checkpoint and original
numerical gates are retained. Only the new exact-lossless writer is substituted
in an isolated function namespace; failed evidence is saved before evaluation.
"""
from pathlib import Path
from datetime import timedelta
import collections
import copy
import hashlib
import os
import shutil
import sys
import traceback
import types
import psutil
import lossless_trial_references_v2 as repair
import qualify_failure_codec_v1 as qualification

ROOT, job, api = repair.ROOT, qualification.job, qualification.api
WORK = qualification.WORK
SEED_OUT = ROOT / 'stage194_evaluations/evidence_repair_20260924/seed_extraction_01'
DESIGN = ROOT / 'stage194_designs/evidence_repair_20260924/diagnostic_replay_01.json'
RUN = ROOT / 'stage194_runs/evidence_repair_20260924/diagnostic_replay_01'
OUT = ROOT / 'stage194_evaluations/evidence_repair_20260924/diagnostic_replay_01'


def check_prerequisites():
    work = api.read(WORK)
    api.require(job.utc() < job.policy.utc(work['work_end_utc']) - timedelta(seconds=900), 'diagnostic launch cutoff')
    d = api.read(job.DESIGN); job.verify(d)
    for folder in (SEED_OUT, qualification.OUT):
        r = api.read(folder / 'results.json')
        api.require(r['passed'] and api.read(folder / 'completion.json')['results_sha256'] == api.sha(folder / 'results.json'), 'qualified prerequisite seal')
        api.verify_mapping(r['inputs'])
        if 'artifacts' in r: api.verify_mapping(r['artifacts'])
    s = api.read(SEED_OUT / 'results.json')
    api.require(api.sha(Path(s['seed_path'])) == s['seed_sha256'], 'reconstructed seed binding')
    return work, d, api.read(Path(s['seed_path']))


def prepare():
    w, d, seed = check_prerequisites()
    case = next(c for c in d['cases'] if c['id'] == seed['case'])
    api.require(seed['checkpoint']['state']['steps'] == 1730000 and seed['source_design_sha256'] == api.sha(job.DESIGN), 'original diagnostic checkpoint')
    paths = [WORK, job.DESIGN, Path(__file__), Path(repair.__file__), Path(qualification.__file__),
             SEED_OUT / 'diagnostic_seed_01.json', SEED_OUT / 'results.json', SEED_OUT / 'completion.json',
             qualification.OUT / 'results.json', qualification.OUT / 'completion.json']
    p = {'stage': 'Stage194 diagnostic replay of masked writer failure', 'case': case,
         'maximum_new_accepted_steps': 10000, 'source_segment': 173,
         'work_end_utc': w['work_end_utc'], 'maximum_runtime_seconds': 1200,
         'original_integration_code_sha256': qualification.campaign.code_sha(job.execute_segment),
         'only_execute_namespace_substitution': ['codec'], 'physical_and_numerical_changes': [],
         'inputs': {str(p): api.sha(p) for p in paths}, 'numerical_gates': d['numerical_gates'],
         'stage193_block174_actual_outcome_and_steps_remain_unknown': True,
         'claim': 'New diagnostic evidence only, not full observation, historical recovery, release estimate or validation.'}
    job.commit(DESIGN, p)
    print('DIAGNOSTIC_PREPARED', api.sha(DESIGN), flush=True)


def run():
    w, d, seed = check_prerequisites(); p = api.read(DESIGN); api.verify_mapping(p['inputs'])
    api.require(qualification.campaign.code_sha(job.execute_segment) == p['original_integration_code_sha256'], 'frozen integration code')
    api.require(p['maximum_new_accepted_steps'] == 10000 and w['maximum_new_accepted_trajectory_steps'] == 50000, 'bounded step authority')
    api.require(shutil.disk_usage(ROOT).free > w['minimum_free_disk_bytes'] + 2 * repair.base.MAX_RAW, 'disk reserve')
    for proc in psutil.process_iter(['pid', 'cmdline']):
        if proc.info['pid'] != os.getpid() and any(str(Path(__file__).resolve()).lower() == str(arg).lower() for arg in (proc.info['cmdline'] or [])):
            raise RuntimeError('another bound diagnostic process exists')
    RUN.mkdir(parents=True, exist_ok=False); OUT.mkdir(parents=True, exist_ok=False)
    # Reservation is charged even if process termination makes its actual count unknown.
    stop = min(job.utc() + timedelta(seconds=p['maximum_runtime_seconds']), job.policy.utc(w['work_end_utc']) - timedelta(seconds=900)).isoformat()
    job.commit(RUN / 'launch.json', {'pid': os.getpid(), 'argv': sys.argv, 'utc': job.utc().isoformat(),
                                   'stop_utc': stop, 'reserved_new_accepted_steps': 10000, 'protocol_sha256': api.sha(DESIGN),
                                   'original_design_sha256': api.sha(job.DESIGN), 'blas_threads': 1})
    accepted = None; record = None
    try:
        namespace = dict(job.execute_segment.__globals__); namespace['codec'] = repair.codec
        execute = types.FunctionType(job.execute_segment.__code__, namespace, 'execute_segment', job.execute_segment.__defaults__, job.execute_segment.__closure__)
        api.require(execute.__code__ is job.execute_segment.__code__, 'exact integration bytecode')
        api.require([k for k in namespace if namespace[k] is not job.execute_segment.__globals__[k]] == ['codec'], 'storage-only namespace difference')
        case = p['case']; before = copy.deepcopy(seed['checkpoint'])
        api.require(case == next(c for c in d['cases'] if c['id'] == seed['case']), 'original frozen case')
        job.parent.b.old.parent.configure()
        with job.prior.snapshot.scope(api, case['spec']['field_metadata']):
            api.fields.load(2, 1., 6)
            record, prefix, seal, elapsed = execute(d, case, before, RUN / 'diagnostic.json.xz', 10000, None, stop)
        accepted = len(record['rows'])
        result = record['result']; after = result['checkpoint']
        api.require(after['state']['steps'] - before['state']['steps'] == accepted <= 10000, 'exact new accepted-step accounting')
        decoded, _ = repair.codec.read_record(RUN / 'diagnostic.json.xz', api.sha(job.DESIGN))
        independent = qualification.independent_file(RUN / 'diagnostic.json.xz', api.sha(job.DESIGN))
        api.require(repair.base.raw_bytes(record) == repair.base.raw_bytes(decoded) == repair.base.raw_bytes(independent), 'both readers restore complete original diagnostic bytes')
        log = decoded['contact_trial_trace']; failed = [t for t in log['detailed_trials'] if not t['accepted']]
        detail = {'failed_outer_trials': failed, 'rejected_trials': after['state'].get('rejected_trials', []),
                  'record_sha256': api.sha(RUN / 'diagnostic.json.xz'), 'new_accepted_steps': accepted,
                  'status': result['status'], 'result': {k: v for k, v in result.items() if k not in ('history', 'checkpoint')}}
        job.commit(OUT / 'failure_details.json', detail)
        sources = {str(f): api.sha(f) for f in RUN.rglob('*') if f.is_file()}
        api.verify_mapping(p['inputs']); job.verify(d)
        report = {'diagnostic_evidence_passed': True, 'numerical_campaign_gate_passed': False,
                  'numerical_verdict': 'not adjudicated here; any rejection preserves original campaign failure',
                  'new_accepted_steps': accepted, 'reserved_step_ceiling': 10000, 'outer_trial_count': len(log['trial_inner_counts']),
                  'failed_outer_trials': len(failed), 'error_counts': dict(collections.Counter(t.get('error') for t in failed)),
                  'result_status': result['status'], 'rejected_total': result['rejected'], 'transaction_seconds': elapsed,
                  'input_checkpoint_sha256': api.digest(before), 'output_checkpoint_sha256': api.digest(after),
                  'end_time_s': after['state']['t'], 'raw_artifacts': sources,
                  'failure_details_sha256': api.sha(OUT / 'failure_details.json'), 'protocol_sha256': api.sha(DESIGN),
                  'underlying_record_saved_without_writer_failure': True,
                  'stage193_original_promoted': False, 'old_unsaved_block174_actual_steps_still_unknown': True}
        job.commit(OUT / 'results.json', report)
        job.commit(OUT / 'completion.json', {'diagnostic_evidence_passed': True, 'results_sha256': api.sha(OUT / 'results.json')})
        print('DIAGNOSTIC_SAVED', accepted, result['status'], 'rejected', result['rejected'], 'failed_trials', len(failed), flush=True)
    except Exception as e:
        # Never disguise an unavailable accepted state or overwrite failed evidence.
        job.commit(OUT / 'failure.json', {'error': repr(e), 'traceback': traceback.format_exc(),
                                        'new_accepted_steps_known': accepted, 'reserved_step_ceiling': 10000,
                                        'record_returned': record is not None, 'protocol_sha256': api.sha(DESIGN)})
        raise


if __name__ == '__main__':
    if sys.argv[1:] == ['prepare']: prepare()
    elif sys.argv[1:] == ['run']: run()
    else: raise ValueError('prepare | run')
