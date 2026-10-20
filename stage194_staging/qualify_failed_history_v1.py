"""Zero-step synthetic failure-only history chains; never trajectory evidence."""
import copy
import sys
from pathlib import Path
import qualify_failure_codec_v1 as q

job, api, codec = q.job, q.api, q.repair.codec
OUT = q.ROOT / 'stage194_evaluations/evidence_repair_20260924/failed_history_01'


def run():
    api.require(job.utc() < job.policy.utc(api.read(q.WORK)['work_end_utc']), 'work clock')
    passed = api.read(q.OUT / 'results.json')
    api.require(passed['passed'] and api.read(q.OUT / 'completion.json')['results_sha256'] == api.sha(q.OUT / 'results.json'), 'qualified codec')
    api.verify_mapping(passed['inputs'])
    OUT.mkdir(parents=True, exist_ok=False)
    history = [[0., 1., 2., 3.]]
    tests = []; rejects = []; prefix = None
    for index, name in enumerate(['outer_failure_missing_outputs', 'inner_exception_missing_outputs', 'outer_failure_no_inner']):
        fixture = next(e for n, e in q.fixtures() if n == name)
        record = copy.deepcopy(fixture['payload']); record['design_sha256'] = fixture['design_sha256']
        record['fixture_only'] = True; record['new_trajectory_steps'] = 0
        record['rows'] = []; record['result'] = {'status': 'numerical_failure', 'history': copy.deepcopy(history),
            'checkpoint': {'state': {'history': copy.deepcopy(history), 'steps': 0}}}
        path = OUT / f'synthetic_failure_{index:02d}.json.xz'
        before = q.repair.base.raw_bytes(record)
        seal, new_prefix = codec.write_record(path, record, prefix)
        restored, _ = codec.read_record(path, record['design_sha256'], prefix)
        independent = q.independent_file(path, record['design_sha256'], history if prefix else None, prefix.reference() if prefix else None)
        api.require(q.repair.base.raw_bytes(restored) == before == q.repair.base.raw_bytes(independent), 'full failed record exact bytes')
        api.require(q.repair.base.raw_bytes(record) == before and restored['result']['status'] == 'numerical_failure', 'failure and input preserved')
        if prefix:
            try: codec.read_record(path, record['design_sha256'], None)
            except ValueError: rejects.append('missing_failed_history_parent_' + str(index))
            else: raise AssertionError('missing parent accepted')
        prefix = new_prefix; tests.append(name)
    result = {'passed': True, 'new_trajectory_steps': 0, 'synthetic_failures_only': True,
              'full_history_failure_round_trips': tests, 'parent_rejections': rejects,
              'unchanged_history_zero_accepted_steps_supported': True,
              'sources': {str(Path(__file__)): api.sha(Path(__file__)), str(Path(q.repair.__file__)): api.sha(q.repair.__file__)},
              'prerequisite_sha256': api.sha(q.OUT / 'results.json'),
              'artifacts': {str(p): api.sha(p) for p in OUT.glob('synthetic_failure*') if p.is_file()}}
    job.commit(OUT / 'results.json', result); job.commit(OUT / 'completion.json', {'passed': True, 'results_sha256': api.sha(OUT / 'results.json')})
    print('FAILED_HISTORY_PASS', len(tests), len(rejects), flush=True)


if __name__ == '__main__': run()
