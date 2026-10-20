"""Zero-trajectory inspection of immutable Stage200 segment197 trial evidence."""
from pathlib import Path
import hashlib
import json
import lzma
import os
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage200_staging'))
import revised_deadline_campaign_v1 as frozen

job, api = frozen.job, frozen.api
WORK = ROOT / 'stage201_designs/eight_hour_contact_repair_20260928/contract_01.json'
OUT = ROOT / 'stage201_evaluations/contact_repair_20260928/failed_evidence_01'
NAME = 's2_i124_fibre_f0p0625'


def run():
    work = api.read(WORK)
    api.require(job.utc() < job.policy.utc(work['work_end_utc']), 'work window')
    d = api.read(job.DESIGN)
    job.verify(d)
    dh = api.sha(job.DESIGN)
    api.require(dh == work['stage200_design_sha256'], 'frozen source design')
    p = job.paths(job.RUN, NAME, 197)
    marker, receipt = api.read(p['ready']), api.read(p['receipt'])
    api.require(receipt['status'] == 'audit_failed' and receipt['case'] == NAME and receipt['segment'] == 197, 'exact failed receipt')
    api.require(receipt['ready_sha256'] == api.sha(p['ready']) and marker['raw_sha256'] == api.sha(p['raw']), 'failed raw bound through receipt')
    sealpath = p['raw'].with_suffix('.seal.json')
    seal = api.read(sealpath)
    raw = p['raw'].read_bytes()
    uncompressed = lzma.decompress(raw)
    api.require(len(raw) == seal['compressed_bytes'] and hashlib.sha256(raw).hexdigest() == seal['compressed_sha256'], 'compressed seal')
    api.require(len(uncompressed) == seal['uncompressed_bytes'] and hashlib.sha256(uncompressed).hexdigest() == seal['uncompressed_sha256'], 'uncompressed seal')
    wrapper = json.loads(uncompressed)
    envelope = frozen.pre.storage.read_envelope(p['raw'], dh)
    canonical = frozen.pre.storage.base.raw_bytes(envelope)
    api.require(hashlib.sha256(canonical).hexdigest() == wrapper['original_envelope_sha256'] and len(canonical) == wrapper['original_envelope_bytes'], 'exact original envelope')
    payload = envelope['payload']
    log = payload['contact_trial_trace']
    failed_outer = [t for t in log['detailed_trials'] if not t['accepted']]
    systems = []
    for ti, trial in enumerate(failed_outer):
        for si, system in enumerate(trial['inner_systems']):
            if not system['accepted']:
                systems.append({'failed_outer_index': ti, 'inner_index': si, 'system_sha256': api.digest(system), 'system': system})
    producer_path = job.RUN / NAME / 'result.json'
    producer = api.read(producer_path)
    done = api.read(producer_path.parent / 'completion.json')
    api.require(done['result_sha256'] == api.sha(producer_path), 'sealed producer result')
    result = producer['final_result']
    api.require(result['rejected'] == len(result['rejected_trials']) == len(failed_outer) == 22, 'all rejected outer trials preserved')
    OUT.mkdir(parents=True, exist_ok=False)
    inputs = {str(x): api.sha(x) for x in (WORK, job.DESIGN, Path(__file__), p['raw'], sealpath, p['ready'], p['receipt'], producer_path, producer_path.parent / 'completion.json')}
    job.commit(OUT / 'launch.json', {'pid': os.getpid(), 'argv': sys.argv, 'utc': job.utc().isoformat(), 'new_trajectory_steps': 0, 'inputs': inputs})
    try:
        job.commit(OUT / 'failed_systems.json', {'case': NAME, 'failed_outer_trials': failed_outer, 'failed_inner_systems': systems, 'rejected_trials': result['rejected_trials'], 'source_design_sha256': dh, 'source_raw_sha256': api.sha(p['raw'])})
        summary = {'evidence_extraction_complete': True, 'new_trajectory_steps': 0, 'original_stage200_acceptance_unchanged': False,
                   'original_campaign_remains_failed': True, 'case': NAME, 'segment': 197,
                   'failed_outer_trials': len(failed_outer), 'failed_inner_systems': len(systems),
                   'all_inner_counts': log['trial_inner_counts'],
                   'payload_keys': list(payload), 'envelope_keys': list(envelope),
                   'sample_system_keys': list(systems[0]['system']) if systems else [],
                   'first_rejected_time_s': result['rejected_trials'][0]['time_s'], 'last_rejected_time_s': result['rejected_trials'][-1]['time_s'],
                   'producer_saved_steps': result['steps'], 'failed_segment_saved_steps': marker['steps'],
                   'pending_trial': result['checkpoint']['state'].get('pending_trial'),
                   'compressed_uncompressed_original_envelope_hashes_verified': True,
                   'full_history_reconstruction_in_this_check': False,
                   'inputs': inputs, 'failed_systems_sha256': api.sha(OUT / 'failed_systems.json'),
                   'claim': 'Authenticated held trial systems only. No new trajectory, recovered production, or numerical pass.'}
        # The numerical verdict remains failure; extraction success is separate.
        summary.pop('original_stage200_acceptance_unchanged')
        summary['original_stage200_gate_verdict'] = 'failed'
        job.commit(OUT / 'results.json', summary)
        job.commit(OUT / 'completion.json', {'results_sha256': api.sha(OUT / 'results.json'), 'new_trajectory_steps': 0})
        print(json.dumps({k: v for k, v in summary.items() if k not in ('inputs', 'all_inner_counts')}, indent=2), flush=True)
    except Exception as error:
        job.commit(OUT / 'failure.json', {'error': repr(error), 'traceback': traceback.format_exc(), 'new_trajectory_steps': 0})
        raise


if __name__ == '__main__':
    run()
