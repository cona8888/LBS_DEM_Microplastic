"""Read-only, zero-step authentication of the Stage205 rejected contact trial."""
from pathlib import Path
import hashlib,json,lzma,os,shutil,sys,traceback
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage205_staging'))
import receipt_repaired_campaign_v2 as frozen
job,api=frozen.job,frozen.api
WORK=ROOT/'stage206_designs/contact_failure_20260930/contract_01.json'
OUT=ROOT/'stage206_evaluations/contact_failure_20260930/failed_evidence_01'

def run():
    w=api.read(WORK);d=api.read(job.DESIGN);job.verify(d)
    dh=api.sha(job.DESIGN)
    api.require(dh==w['source_design_sha256'] and w['maximum_new_trajectory_steps']==0,'exact zero-step contract')
    api.require(shutil.disk_usage(job.RUN).free>=w['minimum_free_disk_bytes'],'disk reserve')
    api.require(api.read(job.RUN/'completion.json')['all_owned_processes_retired'],'failed production retired')
    name=w['case'];number=w['failed_segment'];p=job.paths(job.RUN,name,number)
    marker,receipt=api.read(p['ready']),api.read(p['receipt'])
    api.require(receipt['status']=='audit_failed' and receipt['case']==name and receipt['segment']==number,'original failure verdict')
    api.require(receipt['ready_sha256']==api.sha(p['ready']) and marker['raw_sha256']==api.sha(p['raw']),'receipt-ready-raw binding')
    sealpath=p['raw'].with_suffix('.seal.json');seal=api.read(sealpath)
    raw=p['raw'].read_bytes();decoded=lzma.decompress(raw)
    api.require(len(raw)==seal['compressed_bytes'] and hashlib.sha256(raw).hexdigest()==seal['compressed_sha256'],'compressed seal')
    api.require(len(decoded)==seal['uncompressed_bytes'] and hashlib.sha256(decoded).hexdigest()==seal['uncompressed_sha256'],'uncompressed seal')
    wrapper=json.loads(decoded);envelope=frozen.pre.storage.read_envelope(p['raw'],dh)
    canonical=frozen.pre.storage.base.raw_bytes(envelope)
    api.require(hashlib.sha256(canonical).hexdigest()==wrapper['original_envelope_sha256'] and len(canonical)==wrapper['original_envelope_bytes'],'exact original envelope')
    payload=envelope['payload'];trace=payload['contact_trial_trace']
    outer=[t for t in trace['detailed_trials'] if not t['accepted']]
    systems=[{'failed_outer_index':ti,'inner_index':si,'system_sha256':api.digest(s),'system':s}
             for ti,t in enumerate(outer) for si,s in enumerate(t['inner_systems']) if not s['accepted']]
    producerpath=job.RUN/name/'result.json';donepath=producerpath.parent/'completion.json'
    api.require(api.read(donepath)['result_sha256']==api.sha(producerpath),'producer seal')
    producer=api.read(producerpath);r=producer['final_result']
    api.require(producer['reason']=='numerical_failure' and not producer['complete_observation_producer_only'],'original failed campaign remains failed')
    api.require(r['rejected']==len(r['rejected_trials'])==len(outer)==1,'one rejected outer trial accounted')
    api.require(0<len(systems)<=w['maximum_held_systems'],'bounded captured systems')
    inputs={str(f):api.sha(f) for f in (WORK,job.DESIGN,Path(__file__),p['raw'],sealpath,p['ready'],p['receipt'],producerpath,donepath)}
    OUT.mkdir(parents=True,exist_ok=False)
    job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),argv=sys.argv,new_trajectory_steps=0,inputs=inputs))
    try:
        job.commit(OUT/'failed_systems.json',dict(case=name,segment=number,source_design_sha256=dh,
            source_raw_sha256=api.sha(p['raw']),failed_outer_trials=outer,failed_inner_systems=systems,rejected_trials=r['rejected_trials']))
        api.verify_mapping(inputs);job.verify(d)
        result=dict(evidence_authentication_passed=True,numerical_gate_passed=False,new_trajectory_steps=0,
            original_campaign_remains_failed=True,case=name,segment=number,failed_outer_trials=len(outer),failed_inner_systems=len(systems),
            rejected_trials=r['rejected_trials'],producer_saved_steps=r['steps'],failed_segment_saved_steps=marker['steps'],
            pending_trial=r['checkpoint']['state'].get('pending_trial'),failed_systems_sha256=api.sha(OUT/'failed_systems.json'),
            compressed_uncompressed_original_envelope_hashes_verified=True,full_history_reconstruction_in_this_check=False,inputs=inputs,
            claim='Authenticated held equations only. No trajectory, recovered production or numerical pass.')
        job.commit(OUT/'results.json',result)
        job.commit(OUT/'completion.json',dict(results_sha256=api.sha(OUT/'results.json'),new_trajectory_steps=0))
        print(json.dumps({k:v for k,v in result.items() if k not in ('inputs','pending_trial')},indent=2),flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0));raise

if __name__=='__main__':run()
