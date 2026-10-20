"""Preserve and authenticate failed local extension without new physics."""
from pathlib import Path
import os,hashlib,lzma,traceback
import numpy as np
import bounded_contact_diagnostic_v1 as prior
job,api,ROOT=prior.job,prior.api,prior.ROOT
OUT=prior.EVALBASE/'extension_failure_audit_01'


def run():
    w=api.read(prior.source.WORK);api.require(job.utc()<job.policy.utc(w['work_end_utc']),'work window');d=api.read(job.DESIGN);job.verify(d)
    used,pending=prior.ledger();api.require(used==30765 and not pending,'resolved saved-step ledger');prior.require_no_diagnostic()
    chain=['dispatch_full_01','extension_call01_01'];prefix=prior.prefix196();records={};inputs={str(Path(__file__)):api.sha(__file__)};checks=[]
    for name in chain:
        folder=prior.RUNBASE/name;result=prior.sealed_result(folder/'results.json');api.verify_mapping(result['artifacts'])
        design=prior.DESIGNBASE/(name+'.json');p=api.read(design);api.verify_mapping(p['inputs']);api.verify_mapping(p['new_sources'])
        raw=folder/'call.json.xz';seal=api.read(folder/'call.json.seal.json');packed=raw.read_bytes();unpacked=lzma.decompress(packed)
        api.require(hashlib.sha256(packed).hexdigest()==seal['compressed_sha256'] and len(packed)==seal['compressed_bytes'],'independent compressed seal')
        api.require(hashlib.sha256(unpacked).hexdigest()==seal['uncompressed_sha256'] and len(unpacked)==seal['uncompressed_bytes'],'independent uncompressed seal')
        rec,prefix=prior.frozen.pre.storage.codec.read_record(raw,api.sha(job.DESIGN),prefix);records[name]=rec
        api.require(rec['result']['checkpoint']==api.read(folder/'checkpoint.json'),'saved checkpoint identity')
        if name=='extension_call01_01':api.require(rec['input_checkpoint_sha256']==api.digest(records['dispatch_full_01']['result']['checkpoint']),'exact failed-extension input')
        checks.append({'name':name,'compressed_and_uncompressed_seals_verified':True,'original_raw_sha256':prefix.original_sha256,'history_sha256':prefix.history_sha256,'checkpoint_sha256':api.digest(rec['result']['checkpoint'])})
        for f in (design,raw,folder/'call.json.seal.json',folder/'results.json',folder/'completion.json',folder/'accounting.json'):inputs[str(f)]=api.sha(f)
    rec=records['extension_call01_01'];failed=[t for t in rec['contact_trial_trace']['detailed_trials'] if not t['accepted']];systems=[]
    for ti,t in enumerate(failed):
        for ii,s in enumerate(t['inner_systems']):
            if not s['accepted']:systems.append({'outer_index':ti,'inner_index':ii,'system_sha256':api.digest(s),'system':s})
    api.require(len(failed)==len(rec['result']['rejected_trials'])==rec['result']['rejected']==5,'complete rejected trial coverage')
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',{'pid':os.getpid(),'utc':job.utc().isoformat(),'new_trajectory_steps':0,'inputs':inputs})
    job.commit(OUT/'failed_systems.json',{'failed_outer_trials':failed,'failed_inner_systems':systems,'rejected_trials':rec['result']['rejected_trials'],'checks':checks})
    summary=[{'index':i,'contacts':len(s['system']['gaps_m']),'error':s['system'].get('error'),'dt_s':s['system']['dt_s'],'gaps_m':s['system']['gaps_m'],'vfree_norm':float(np.linalg.norm(s['system']['vfree'])),'jacobian_singular_values':np.linalg.svd(s['system']['jacobian'],compute_uv=False).tolist()} for i,s in enumerate(systems)]
    api.verify_mapping(inputs);job.verify(d)
    r={'evidence_audit_passed':True,'numerical_gate_passed':False,'new_trajectory_steps':0,'saved_window_steps':30765,'previous_independently_passing_steps':30277,'new_failed_bundle_saved_steps':488,'unresolved_step_reservations':[],'checks':checks,'failed_systems':summary,'rejected_trials':rec['result']['rejected_trials'],'pending_trial':rec['result']['checkpoint']['state']['pending_trial'],'failed_systems_sha256':api.sha(OUT/'failed_systems.json'),'inputs':inputs,'claim':'Failed local extension remains failed. Exact saved evidence/accounting is not numerical acceptance.'}
    job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'evidence_audit_passed':True,'numerical_gate_passed':False,'results_sha256':api.sha(OUT/'results.json')});print('FAILED_EXTENSION_AUDIT',r['saved_window_steps'],summary,flush=True)


if __name__=='__main__':run()
