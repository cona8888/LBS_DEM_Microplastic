"""Authenticate terminal overnight evidence; never launch or advance a case.

Historical independent physical audits are rehashed/reused, not rerun. A
finished workflow is kept distinct from a completed/qualified observation.
"""
from pathlib import Path
import hashlib, json, shutil, sys, time, traceback
import psutil

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage222_staging'))
import overnight_campaign_v1 as n
OUT=n.OUT/'final_disposition_01'


def retired(path):
    launch=n.api.read(path)
    try:
        p=psutil.Process(launch['pid'])
        same=abs(p.create_time()-launch['created'])<.001 and p.cmdline()==launch['argv']
        n.api.require(not same,'Owned process has retired before closure')
        return dict(pid=launch['pid'],exact_launch_identity_absent=True,pid_reused=True)
    except psutil.NoSuchProcess:
        return dict(pid=launch['pid'],exact_launch_identity_absent=True,pid_reused=False)


def run():
    d=n.api.read(n.PLAN)
    n.api.require(n.job.utc()<n.job.policy.utc(d['authorized_end_utc']),'Final disposition within authorized window')
    n.api.verify_mapping(d['sources'])
    terminal=n.sealed(n.RUN/'results.json')
    n.api.require(terminal['finished'] and terminal['design_sha256']==n.api.sha(n.PLAN),'Exact terminal design')
    supervisor=n.RUN.parent/'supervisor_01'
    exit_row=n.api.read(supervisor/'exit.json')
    n.api.require(exit_row['exit_code']==0 and not exit_row['forced_deadline_stop'],'Normal bounded worker retirement')
    n.api.require(exit_row['design_sha256']==n.api.sha(n.PLAN),'Supervisor exit design identity')
    n.api.require(n.job.policy.utc(exit_row['utc'])<n.job.policy.utc(d['authorized_end_utc']) and n.job.policy.utc(terminal['utc'])<n.job.policy.utc(d['authorized_end_utc']),'Terminal records before absolute deadline')
    identities=dict(supervisor=retired(n.RUN.parent/'launcher_01/launch.json'),worker=retired(supervisor/'worker_launch.json'))
    n.api.require(not list(n.RUN.rglob('failure.json')) and not (supervisor/'deadline_stop.json').exists(),'No failure or forced-stop promotion')
    n.api.require(not (supervisor/'stderr.log').read_text().strip(),'Empty worker error log')
    artifacts={str(p):n.api.sha(p) for p in (n.PLAN,n.RUN/'results.json',n.RUN/'completion.json',
        supervisor/'exit.json',supervisor/'worker_launch.json',supervisor/'launch.json',supervisor/'stdout.log',supervisor/'stderr.log',
        n.RUN.parent/'launcher_01/launch.json',Path(__file__).resolve())}
    ledger=[];physical=0;diagnostics=0;producer=0.;audit=0.;profiled=[];receipt_map={}
    reported={c['case']:c for c in terminal['cases']}
    for case in d['cases']:
        name=case['id'];folder=n.RUN/name
        if name not in reported:
            n.api.require(not folder.exists(),'Explicit unstarted case has no saved work')
            ledger.append(dict(case=name,disposition='not_started',physical_steps=0,diagnostic_steps=0,
                               complete_observation=False,full_path_qualified=False))
            continue
        row=n.sealed(folder/'results.json')
        n.api.require(row==reported[name],'Exact case/global terminal agreement')
        qual=n.sealed(folder/'qualification_01/results.json')
        n.api.require(qual['passed'] and qual['exact_serial_split'] and qual['diagnostic_saved_steps']==512,'Initial exact restart qualification')
        n.api.verify_mapping(qual['artifacts']);diagnostics+=512
        artifacts[str(folder/'qualification_01/results.json')]=n.api.sha(folder/'qualification_01/results.json')
        artifacts[str(folder/'qualification_01/completion.json')]=n.api.sha(folder/'qualification_01/completion.json')
        files=sorted(folder.glob('segment_*/completion.json'))
        n.api.require(len(files)==len(row['entries']) and len(files)<=d['maximum_calls_per_case'],'Complete terminal segment inventory')
        pending=[p for p in folder.glob('segment_*') if not (p/'completion.json').exists()]
        n.api.require(not pending,'No unsealed segment reservation remains')
        previous=None;checkpoint=n.api.digest(None);clock=0.;steps=0;history=[];prefix=None;restored_cp=None
        started=time.perf_counter()
        for i,(p,entry) in enumerate(zip(files,row['entries']),1):
            n.api.require(n.job.utc()<n.job.policy.utc(d['authorized_end_utc']),'Bounded final authentication')
            n.api.require(p.parent.name==f'segment_{i:05d}','Contiguous production inventory')
            result_path=p.with_name('results.json');r=n.sealed(result_path)
            n.api.require(r['passed'] and r['summary']['passed'] and r['design_sha256']==n.api.sha(n.PLAN),'Original independent physical receipt')
            n.api.require(r['previous_receipt_sha256']==previous and r['input_checkpoint_sha256']==checkpoint,'Full receipt/checkpoint chain')
            n.api.require(r['summary']['start_s']==clock and r['summary']['steps']==r['new_saved_steps'],'Exact physical time/step chain')
            n.api.verify_mapping(r['artifacts'])
            a=n.api.read(p.parent/'accounting.json')
            n.api.require(a['saved_steps']==r['new_saved_steps'] and a['rejected']==0 and a['raw_sha256']==n.api.sha(p.parent/'call.json.xz'),'Independent saved ledger')
            n.api.require(entry==dict(segment=i,new_saved_steps=r['new_saved_steps'],results_sha256=n.api.sha(result_path),stop_s=r['summary']['stop_s']),'Exact terminal entry')
            raw=p.parent/'call.json.xz'
            # Fresh bounded reader verifies compressed/uncompressed hashes,
            # sizes and CRC64 before parsing. Restore only checkpoint history;
            # original independent physical audits remain authenticated/reused.
            wrapper=n.source.stack.storage.fresh_reader(raw,n.api.sha(n.PLAN))
            env=wrapper['packed_envelope'];meta=env['history'];rec=env['payload']
            n.api.require(env['evidence_encoding']==n.job.codec.ENCODING and env['design_sha256']==n.api.sha(n.PLAN),'Bound lossless history encoding')
            n.api.require(meta['prefix']==prefix and rec['input_checkpoint_sha256']==checkpoint,'Raw prefix and checkpoint ancestry')
            history=history+meta['appended_rows'];hb=n.job.codec.packed_history(history)
            n.api.require(len(history)==meta['length'] and hashlib.sha256(hb).hexdigest()==meta['sha256'],'Restored complete history seal')
            restored_cp=rec['result']['checkpoint'];restored_cp['state']['history']=history
            n.api.require(n.api.digest(restored_cp)==r['output_checkpoint_sha256'],'Independently restored full raw checkpoint')
            n.api.require(n.api.digest(restored_cp['state'])==restored_cp['state_sha256']==r['summary']['output_checkpoint_state_sha256'],'Complete physical state digest')
            seal=n.api.read(raw.with_suffix('.seal.json'))
            prefix=n.job.codec.make_state(raw,env,hb,seal).reference()
            steps+=r['new_saved_steps'];clock=r['summary']['stop_s'];previous=n.api.sha(result_path);checkpoint=r['output_checkpoint_sha256']
            producer+=r['transaction_seconds'];audit+=r['summary']['audit_seconds'];receipt_map[str(result_path)]=previous
            if r['transaction_profiled']:profiled.append(dict(case=name,segment=i,producer_seconds=r['transaction_seconds'],audit_seconds=r['summary']['audit_seconds']))
            if i%50==0:print('AUTHENTICATED',i,'seconds',round(time.perf_counter()-started,1),flush=True)
        cp=n.api.read(folder/'checkpoint.json')
        n.api.require(n.api.digest(cp)==row['final_checkpoint_sha256']==checkpoint,'Saved full terminal checkpoint digest')
        n.api.require(cp['state']['steps']==row['physical_steps']==steps and cp['state']['t']==clock,'Terminal checkpoint time and step ledger')
        n.api.require(restored_cp==cp and n.api.read(folder/'prefix.json')==prefix,'Published terminal checkpoint and prefix equal complete reconstructed ancestry')
        comparison=n.OUT/name/'comparison_01/results.json'
        if not row['complete_observation']:
            n.api.require(not comparison.exists() and row['reason']=='simulation_cutoff','Incomplete path has no fabricated comparison')
        for p in (folder/'results.json',folder/'completion.json',folder/'checkpoint.json',folder/'prefix.json'):
            artifacts[str(p)]=n.api.sha(p)
        ledger.append(dict(case=name,disposition='complete' if row['complete_observation'] else 'incomplete_at_cutoff',
                           complete_observation=row['complete_observation'],reason=row['reason'],physical_steps=steps,diagnostic_steps=512,
                           audited_segments=len(files),stop_s=clock,target_horizon_s=case['spec']['horizon_s'],
                           final_checkpoint_sha256=checkpoint,full_path_qualified=comparison.exists() and n.sealed(comparison)['passed']))
        physical+=steps
    n.api.require(physical==terminal['physical_steps'] and diagnostics==terminal['diagnostic_saved_steps'],'Exact campaign physical/diagnostic balance')
    n.api.require(physical+diagnostics==terminal['saved_steps_including_diagnostics']<=d['maximum_saved_steps_including_diagnostics'],'Shared saved-step ceiling')
    n.api.require(terminal['reason']=='simulation_cutoff' and not terminal['whole_overnight_success'],'Expected bounded incomplete disposition')
    result=dict(passed=True,final_accounting_authenticated=True,utc=n.job.utc().isoformat(),
        design_sha256=n.api.sha(n.PLAN),new_trajectory_steps=0,terminal_reason=terminal['reason'],
        whole_overnight_success=False,owned_processes_retired=identities,cases=ledger,
        physical_steps=physical,diagnostic_steps=diagnostics,total_saved_steps=physical+diagnostics,
        production_producer_seconds=producer,recorded_physics_audit_seconds=audit,profiled_segments=profiled,
        cost_scope='Producer/audit sums include the explicitly listed instrumented transaction; no full-case speedup or campaign CPU-hour claim. Other pipeline/qualification costs are excluded.',
        inherited_physical_audits_rehashed_and_reused=True,physical_audits_rerun=False,
        all_raw_seals_and_full_checkpoint_history_ancestry_reconstructed=True,terminal_prefix_authenticated=True,
        all_sealed_production_receipts=receipt_map,artifacts=artifacts,free_disk_bytes=shutil.disk_usage(ROOT).free,
        claim='Reference verification remains passed. First coarser case is incomplete; the other three were not started. No coarser full-path accuracy, shape/flow inference, export fraction or optimization speedup established.')
    n.job.commit(OUT/'results.json',result)
    n.job.commit(OUT/'completion.json',dict(passed=True,results_sha256=n.api.sha(OUT/'results.json')))
    print('FINAL_AUTHENTICATED',physical,diagnostics,[(r['case'],r['disposition']) for r in ledger])


if __name__=='__main__':
    try:run()
    except Exception as error:
        n.job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0,utc=n.job.utc().isoformat()))
        raise
