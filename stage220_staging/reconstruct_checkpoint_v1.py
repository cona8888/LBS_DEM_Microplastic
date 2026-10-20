"""Authenticate the interrupted Stage219 chain without changing its evidence."""
from pathlib import Path
import os, sys, time, traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage219_staging'))
import normal_gap_campaign_v1 as source
api, job = source.api, source.job
NAME = 's2_i124_fibre_f0p0625'
OUT = ROOT / 'stage220_evaluations/checkpoint_recovery_20261006/reconstruction_01'


def run():
    d = api.read(job.DESIGN); job.verify(d)
    api.require(not source.active_owned(), 'No active competing simulation')
    api.require(not (job.RUN / 'completion.json').exists(), 'Interrupted original remains incomplete')
    api.require(not OUT.exists(), 'New reconstruction output')
    dh = api.sha(job.DESIGN); case = next(c for c in d['cases'] if c['id'] == NAME)
    markers = sorted((job.RUN / NAME).glob('segment_*.ready.json'))
    api.require(len(markers) == 1060, 'Frozen interrupted chain length')
    OUT.mkdir(parents=True)
    job.commit(OUT / 'launch.json', dict(pid=os.getpid(), utc=job.utc().isoformat(), new_trajectory_steps=0,
        source_sha256=api.sha(__file__), original_design_sha256=dh))
    before = prefix = receipt_sha = None
    checks = []; inputs = {str(job.DESIGN): dh, str(Path(__file__)): api.sha(__file__)}
    total = 0; started = time.perf_counter()
    try:
        for index, marker in enumerate(markers, 1):
            p = job.paths(job.RUN, NAME, index)
            api.require(marker == p['ready'], 'Contiguous segment inventory')
            m = api.read(marker)
            job.policy.verify_receipt(p, NAME, index, dh, d['audit_source_sha256'], api.digest(before), receipt_sha)
            record, next_prefix = job.codec.read_record(p['raw'], dh, prefix)
            receipt = api.read(p['receipt']); summary = receipt['summary']
            api.require(record['input_checkpoint_sha256'] == api.digest(before), 'Complete input checkpoint ancestry')
            cp = record['result']['checkpoint']
            api.require(api.digest(cp['state']) == cp['state_sha256'] == summary['output_checkpoint_state_sha256'], 'Full checkpoint state digest')
            api.require(record['numerical_policy_contract_sha256'] == api.sha(job.WORK), 'Unchanged explicit numerical policy')
            api.require(next_prefix.original_sha256 == receipt['original_raw_sha256'], 'Original logical record identity')
            api.require(summary['passed'] and record['result']['rejected'] == 0, 'Inherited independent passing record')
            api.require(summary['steps'] == m['steps'] == len(record['rows']), 'Exact saved-step count')
            api.require(summary['start_s'] == (0. if before is None else before['state']['t'])
                and summary['stop_s'] == cp['state']['t'], 'Physical time continuity')
            total += m['steps']
            api.require(cp['state']['steps'] == total, 'Cumulative step continuity')
            receipt_sha = api.sha(p['receipt'])
            checks.append(dict(segment=index, receipt_sha256=receipt_sha, checkpoint_sha256=api.digest(cp),
                raw_sha256=next_prefix.compressed_sha256, history_sha256=next_prefix.history_sha256,
                history_length=next_prefix.history_length, steps=m['steps'], stop_s=summary['stop_s']))
            for path in (p['raw'], p['ready'], p['receipt'], p['trace'], p['raw'].with_suffix('.seal.json')):
                inputs[str(path)] = api.sha(path)
            if index >= 1059:
                job.commit(OUT / f'checkpoint_{index:05d}.json', cp)
                job.commit(OUT / f'prefix_{index:05d}.json', next_prefix.reference())
                job.commit(OUT / f'history_{index:05d}.json', record['result']['history'])
            before, prefix = cp, next_prefix
            if index % 25 == 0:
                print('RECONSTRUCTED', index, total, cp['state']['t'], round(time.perf_counter()-started,1), flush=True)
        api.require(total == 5531978 and not record['result']['complete_observation'], 'Original incomplete endpoint')
        source.bindings(); job.verify(d)
        result = dict(passed=True, new_trajectory_steps=0, original_campaign_passed=False,
            case=NAME, original_design_sha256=dh, original_binding=job.binding(d,case),
            original_numerical_policy_contract_sha256=api.sha(job.WORK), complete_chain_segments=len(checks),
            total_saved_steps=total, time_s=before['state']['t'], horizon_s=case['spec']['horizon_s'],
            complete_checkpoint_and_history_reconstructed=True, inherited_physics_receipts_authenticated=True,
            independent_physics_replayed=False, seconds=time.perf_counter()-started, checks=checks, inputs=inputs,
            artifacts={str(p):api.sha(p) for p in OUT.glob('*.json')},
            claim='Exact full-chain raw/history/checkpoint authentication; original campaign remains interrupted. No new transport or shape/flow inference.')
        job.commit(OUT/'results.json',result)
        job.commit(OUT/'completion.json',dict(passed=True,results_sha256=api.sha(OUT/'results.json')))
        print('CHECKPOINT_RECONSTRUCTION_COMPLETE',total,before['state']['t'],flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0,completed_segments=len(checks)))
        raise


if __name__ == '__main__': run()
