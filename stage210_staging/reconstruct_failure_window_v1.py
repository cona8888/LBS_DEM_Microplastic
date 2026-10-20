"""Independent full-producer-history bootstrap of local Stage209 evidence."""
from pathlib import Path
import copy, hashlib, os, traceback
import authenticate_failed_system_v1 as source
job, api, ROOT, frozen = source.job, source.api, source.ROOT, source.frozen
OUT = ROOT / 'stage210_evaluations/three_contact_failure_20261001/reconstructed_window_01'


def run():
    d = api.read(job.DESIGN); job.verify(d); dh = api.sha(job.DESIGN); w = api.read(source.WORK)
    name, stop = w['case'], w['failed_segment']; start = stop - 3
    resultfile = job.RUN / name / 'result.json'; donefile = resultfile.parent / 'completion.json'
    api.require(api.sha(resultfile) == api.read(donefile)['result_sha256'], 'original failed producer seal')
    result = api.read(resultfile)['final_result']; history = result['history']; codec = frozen.stack.storage.codec
    inputs = {str(p): api.sha(p) for p in (source.WORK, job.DESIGN, Path(__file__), resultfile, donefile)}
    OUT.mkdir(parents=True, exist_ok=False)
    job.commit(OUT / 'launch.json', dict(pid=os.getpid(), utc=job.utc().isoformat(), new_trajectory_steps=0, inputs=inputs))
    records, states, checks = {}, {}, []
    try:
        for number in range(start, stop + 1):
            p = job.paths(job.RUN, name, number); sealpath = p['raw'].with_suffix('.seal.json')
            marker, receipt, seal = api.read(p['ready']), api.read(p['receipt']), api.read(sealpath)
            api.require(receipt['ready_sha256'] == api.sha(p['ready']) and marker['raw_sha256'] == api.sha(p['raw']) == seal['compressed_sha256'], 'original raw ready receipt seal')
            api.require(receipt['status'] == ('audit_failed' if number == stop else 'independently_verified'), 'original accepted/failed verdicts preserved')
            env = frozen.stack.storage.read_envelope(p['raw'], dh); hist = history[:env['history']['length']]; hb = codec.packed_history(hist)
            api.require(hashlib.sha256(hb).hexdigest() == env['history']['sha256'], 'sealed producer history prefix')
            if number == start:
                rec = copy.deepcopy(env['payload']); rec['result']['history'] = hist; rec['result']['checkpoint']['state']['history'] = hist
                canonical = frozen.stack.storage.base.raw_bytes(rec)
                api.require(len(canonical) == env['original_uncompressed_bytes'] and hashlib.sha256(canonical).hexdigest() == env['original_uncompressed_sha256'], 'original complete local bootstrap seal')
                state = codec.make_state(p['raw'], env, hb, seal)
            else:
                rec, state = codec.read_record(p['raw'], dh, states[number - 1])
                api.require(state.history_bytes == hb, 'independent codec/full-producer prefix identity')
                api.require(rec['input_checkpoint_sha256'] == api.digest(records[number - 1]['result']['checkpoint']), 'full checkpoint ancestry')
            records[number] = rec; states[number] = state; cp = rec['result']['checkpoint']
            api.require(cp['state']['history'] == rec['result']['history'], 'checkpoint and result history identity')
            checks.append(dict(segment=number, status=receipt['status'], raw_sha256=api.sha(p['raw']), original_sha256=env['original_uncompressed_sha256'], history_sha256=env['history']['sha256'], history_rows=len(hist), checkpoint_sha256=api.digest(cp), steps=marker['steps']))
            for file in (p['raw'], sealpath, p['ready'], p['receipt']): inputs[str(file)] = api.sha(file)
            print('LOCAL_RECONSTRUCTION', number, len(hist), marker['steps'], flush=True)
        api.require(api.digest(records[stop]['result']) == api.digest(result), 'entire failed result matches producer')
        for number in (stop - 2, stop - 1):
            job.commit(OUT / ('checkpoint_%05d.json' % number), records[number]['result']['checkpoint'])
            job.commit(OUT / ('prefix_%05d.json' % number), states[number].reference())
            job.commit(OUT / ('history_%05d.json' % number), records[number]['result']['history'])
        api.verify_mapping(inputs); job.verify(d)
        r = dict(passed=True, new_trajectory_steps=0, inputs=inputs, checks=checks, artifacts={str(p): api.sha(p) for p in OUT.glob('*.json')},
                 claim='Exact local raw/history/full-checkpoint reconstruction, not a full prior-chain physical audit or promotion of failed segment33. No trajectory or old production restart.')
        job.commit(OUT / 'results.json', r); job.commit(OUT / 'completion.json', dict(passed=True, results_sha256=api.sha(OUT / 'results.json')))
    except Exception as error:
        job.commit(OUT / 'failure.json', dict(error=repr(error), traceback=traceback.format_exc(), new_trajectory_steps=0, checks=checks)); raise


if __name__ == '__main__': run()
