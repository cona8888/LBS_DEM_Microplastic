"""Read-only reconstruction of Stage193 selected-fibre segment173; no physics."""
from pathlib import Path
import copy
import os
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage193_staging'))
import deadline_extended_campaign_v2 as old

job, api = old.job, old.api
WORK = ROOT / 'stage194_designs/eight_hour_repair_20260924/contract_01.json'
OUT = ROOT / 'stage194_evaluations/evidence_repair_20260924/seed_extraction_01'
NAME = 's2_i0_fibre_f0p0625'


def run():
    w = api.read(WORK)
    api.require(job.utc() < job.policy.utc(w['work_end_utc']), 'work window')
    d = api.read(job.DESIGN); job.verify(d)
    api.require(api.sha(job.DESIGN) == w['stage193_design_sha256'], 'frozen design')
    terminal = job.OUT / 'evaluation_01/results.json'
    closure = job.OUT / 'terminal_closure_01/results.json'
    api.require(api.sha(terminal) == w['stage193_terminal_result_sha256'], 'terminal result')
    api.require(api.sha(closure) == w['stage193_terminal_closure_sha256'], 'terminal closure')
    OUT.mkdir(parents=True, exist_ok=False)
    inputs = {str(p): api.sha(p) for p in (WORK, job.DESIGN, terminal, closure, Path(__file__))}
    job.commit(OUT / 'launch.json', {'pid': os.getpid(), 'argv': sys.argv, 'utc': job.utc().isoformat(), 'new_steps': 0, 'inputs': inputs})
    prefix = before = previous_receipt = None
    try:
        for index in range(1, 174):
            api.require(job.utc() < job.policy.utc(w['work_end_utc']), 'work cutoff')
            p = job.paths(job.RUN, NAME, index)
            rec, prefix = job.codec.read_record(p['raw'], api.sha(job.DESIGN), prefix)
            marker, receipt = api.read(p['ready']), api.read(p['receipt'])
            api.require(marker['input_checkpoint_sha256'] == rec['input_checkpoint_sha256'] == api.digest(before), 'complete input-checkpoint ancestry')
            job.policy.verify_receipt(p, NAME, index, api.sha(job.DESIGN), d['audit_source_sha256'], api.digest(before), previous_receipt)
            api.require(receipt['status'] == 'independently_verified', 'accepted archive receipt')
            api.require(len(rec['rows']) == 10000 and rec['result']['rejected'] == 0, 'saved accepted block')
            before = rec['result']['checkpoint']
            api.require(before['state']['steps'] == index * 10000, 'full step ledger')
            previous_receipt = api.sha(p['receipt'])
            for path in (*p.values(), p['raw'].with_suffix('.seal.json')):
                inputs[str(path)] = api.sha(path)
            if index % 10 == 0 or index == 173:
                print('VERIFIED_SEED_ANCESTOR', index, before['state']['steps'], flush=True)
        seed = OUT / 'diagnostic_seed_01.json'
        job.commit(seed, {'case': NAME, 'checkpoint': copy.deepcopy(before), 'source_segment': 173,
                          'source_design_sha256': api.sha(job.DESIGN), 'source_binding': job.binding(d, next(c for c in d['cases'] if c['id'] == NAME)),
                          'source_raw': str(p['raw']), 'source_raw_sha256': api.sha(p['raw']),
                          'use': 'New bounded diagnostic only; not a restart or promotion of Stage193.'})
        api.verify_mapping(inputs)
        result = {'passed': True, 'new_trajectory_steps': 0, 'saved_verified_steps': 1730000, 'ancestors': 173,
                  'checkpoint_sha256': api.digest(before), 'checkpoint_state_sha256': before['state_sha256'],
                  'time_s': before['state']['t'], 'seed_path': str(seed), 'seed_sha256': api.sha(seed),
                  'inputs': inputs, 'stage193_block174_outcome_and_steps_still_unknown': True}
        job.commit(OUT / 'results.json', result)
        job.commit(OUT / 'completion.json', {'passed': True, 'results_sha256': api.sha(OUT / 'results.json')})
        print('SEED_COMPLETE', result['time_s'], result['seed_sha256'], flush=True)
    except Exception as error:
        job.commit(OUT / 'failure.json', {'error': repr(error), 'traceback': traceback.format_exc(), 'new_trajectory_steps': 0})
        raise


if __name__ == '__main__':
    run()
