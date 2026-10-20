"""Close the failed Stage205 ledger without promoting rejected evidence."""
from pathlib import Path
import os,sys,psutil
import numpy as np
import cone_feasibility_campaign_v1 as s
api,job=s.api,s.job

def run():
    d=api.read(s.OLD_DESIGN);api.verify_mapping(d['sources']);api.verify_mapping(d['inputs'])
    witness=s.OLD_OUT/'terminal_evaluator_01';exit=api.read(witness/'exit.json');seal=api.read(witness/'completion.json')
    api.require(seal['exit_sha256']==api.sha(witness/'exit.json') and seal['passed'] and exit['exit_code']==0,'original frozen full evaluator witnessed normal closure')
    full=s.sealed(s.OLD_OUT/'evaluation_01/results.json');api.require(exit['results_sha256']==api.sha(s.OLD_OUT/'evaluation_01/results.json') and not full['passed'],'original failed result never promoted')
    inventory=s.sealed(s.OLD_OUT/'terminal_failure_01/results.json')
    terminal=api.read(s.OLD_RUN/'completion.json');api.require(terminal['all_owned_processes_retired'] and terminal['stop_reasons'] and len(terminal['unrun_cases'])==1,'old failed lifecycle retained')
    declared=sum(c['declared_saved_steps'] for c in inventory['cases']);verified=0;details={x['case']:x for x in full['details']}
    failed_name='s2_i124_fibre_f0p0625';unrun='s2_i124_sphere_f0p0625'
    for x in inventory['cases']:
        z=details[x['case']];expected=x['declared_saved_steps']-(2988 if x['case']==failed_name else 0)
        errors=["KeyError('audit_source_sha256')"] if x['case']==failed_name else (["RuntimeError('producer completion present')"] if x['case']==unrun else [])
        api.require(z['records']==x['sealed_segments'] and z['producer_declared_saved_steps']==x['declared_saved_steps'] and z['verified_accepted_steps']==expected and z['errors']==errors,'exact disclosed old terminal case ledger/errors '+x['case'])
        verified+=expected
    api.require(declared==30631450 and verified==30628462 and full['producer_declared_saved_steps']==declared and full['total_accepted_steps']==verified,'inclusive saved/verified/failed balance')
    folder=s.OLD_RUN/failed_name;raw=folder/'segment_00228.json.xz';ready=folder/'segment_00228.ready.json';receipt=api.read(folder/'segment_00228.audit.json')
    api.require(receipt['status']=='audit_failed' and receipt['error']=="RuntimeError('supported nonfailed status, zero rejected trials')" and receipt['ready_sha256']==api.sha(ready),'original numerical failure receipt')
    api.require(full['unsealed_artifacts']==[str(ready)],'only excluded failed ready marker, no missing successful evidence')
    auth=s.sealed(s.ROOT/'stage206_evaluations/contact_failure_20260930/failed_evidence_01/results.json');api.verify_mapping(auth['inputs'])
    recon=s.sealed(s.stack.RECON/'results.json');api.verify_mapping(recon['inputs']);api.verify_mapping(recon['artifacts'])
    codec=job.codec;prefix=codec.HistoryState(**api.read(s.stack.RECON/'prefix_00227.json'),history_bytes=codec.packed_history(api.read(s.stack.RECON/'history_00227.json')))
    rec,state=codec.read_record(raw,api.sha(s.OLD_DESIGN),prefix)
    before=api.read(s.stack.RECON/'checkpoint_00227.json');result=rec['result'];mark=api.read(ready)
    api.require(rec['input_checkpoint_sha256']==api.digest(before) and result['steps']-before['state']['steps']==len(rec['rows'])==mark['steps']==2988,'failed bundle exact clock/step ancestry')
    trace=np.load(folder/'segment_00228.npy',allow_pickle=False)
    expected=np.asarray([[r['time_s'],*r['position_m'],*r['orientation'],*r['velocity_generalized']] for r in rec['rows']])
    api.require(np.array_equal(trace,expected) and np.isfinite(trace).all(),'failed raw/trace exact identity')
    producer=api.read(folder/'result.json');api.require(producer['final_result']==result and result['rejected']==1 and result['rejected_trials']==auth['rejected_trials'],'all producer/rejected trial evidence retained')
    api.verify_mapping(full['artifacts'])
    for p in psutil.process_iter(['name']):
        if p.pid==os.getpid() or 'python' not in (p.info['name'] or '').lower():continue
        try:api.require(not any(str(x) in p.cmdline() for x in (s.ROOT/'stage205_staging/receipt_repaired_campaign_v2.py',s.ROOT/'stage205_staging/run_terminal_evaluator_v1.py')),'old evaluator/witness identity retired')
        except psutil.NoSuchProcess:continue
    files=[Path(__file__),s.OLD_DESIGN,s.OLD_OUT/'evaluation_01/results.json',s.OLD_OUT/'evaluation_01/completion.json',witness/'exit.json',witness/'completion.json',s.OLD_OUT/'terminal_failure_01/results.json',raw,ready,folder/'segment_00228.audit.json',folder/'segment_00228.npy',s.ROOT/'stage206_evaluations/contact_failure_20260930/failed_evidence_01/results.json',s.stack.RECON/'results.json']
    proof=dict(old_failed_run_fully_accounted=True,old_run_remains_failed=True,new_trajectory_steps=0,total_raw_records=3100,independently_verified_records=3099,producer_declared_saved_steps=declared,independently_verified_steps=verified,preserved_failed_saved_steps=2988,failed_raw_history_trace_authenticated=True,unrun_cases=[unrun],terminal_frozen_audit_preserved_errors={failed_name:details[failed_name]['errors'],unrun:details[unrun]['errors']},explanation='Original audit_failed receipt deliberately lacks the passed-receipt fields; the frozen terminal assembler raises the disclosed KeyError before its passing-physics assertion. All3099 successful raw/history bundles are verified by that evaluator; rejected228 is separately fully authenticated/decoded and remains numerically failed. No hidden repair or promotion.',inputs={str(p):api.sha(p) for p in files})
    job.commit(s.OLD_TERMINAL_PROOF,proof);job.commit(s.OLD_TERMINAL_PROOF.parent/'completion.json',dict(passed=True,results_sha256=api.sha(s.OLD_TERMINAL_PROOF)));print('OLD_FAILED_LEDGER_CLOSED',verified,declared,api.sha(s.OLD_TERMINAL_PROOF),flush=True)
if __name__=='__main__':run()
