"""Original full-path gates on explicitly stitched authenticated observations.

Authenticate inherited per-segment physics receipts and raw/trace hashes;
new continuation segments were decoded and physically audited synchronously.
This successor evaluation never fabricates an original Stage219 terminal pass.
"""
from pathlib import Path
import os, sys, traceback
import numpy as np
import recover_fibre_v1 as r
api,job=r.api,r.job


def run():
    plan=r.verify_plan();d=api.read(job.DESIGN);job.verify(d)
    api.require(job.utc()<job.policy.utc(plan['final_audit_deadline_utc']),'Final evaluation before original audit cutoff')
    destination=r.OUT/'combined_evaluation_01'
    api.require(not destination.exists(),'Exclusive successor evaluation')
    recovery=r.sealed(r.RUN/'production_01/results.json')
    api.require(recovery['complete_observation'] and recovery['reason']=='observation_complete','Complete recovery before comparison')
    destination.mkdir(parents=True)
    job.commit(destination/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),new_trajectory_steps=0,recovery_design_sha256=api.sha(r.PLAN)))
    observations={};traces={};details=[];saved=0
    artifacts={str(r.PLAN):api.sha(r.PLAN),str(job.DESIGN):api.sha(job.DESIGN)}
    try:
        reconstruction=r.sealed(r.RECON/'results.json')
        for case in d['cases']:
            name=case['id'];folder=job.RUN/name;markers=sorted(folder.glob('segment_*.ready.json'))
            previous=None;before_sha=api.digest(None);count=0;stop=0.;chain=[];last=None
            for index,marker in enumerate(markers,1):
                paths=job.paths(job.RUN,name,index)
                api.require(marker==paths['ready'],'Contiguous inherited inventory')
                receipt=api.read(paths['receipt']);ready=api.read(marker);summary=receipt['summary']
                # Authenticate the full old receipt/raw/trace chain, preserving
                # the original auditor identity and every acceptance threshold.
                job.policy.verify_receipt(paths,name,index,api.sha(job.DESIGN),d['audit_source_sha256'],before_sha,previous)
                api.require(summary['start_s']==stop and summary['steps']==ready['steps'],'Exact inherited clock/step accounting')
                stop=summary['stop_s'];count+=summary['steps'];previous=api.sha(paths['receipt']);last=summary
                chain.append(paths['trace'])
                for p in paths.values():artifacts[str(p)]=api.sha(p)
                if index<len(markers):
                    # The next ready digest is bound to an independently
                    # audited full state by the inherited audit, not invented.
                    before_sha=api.read(job.paths(job.RUN,name,index+1)['ready'])['input_checkpoint_sha256']
                if index%250==0:print('INHERITED_RECEIPTS_AUTHENTICATED',name,index,count,flush=True)
                if index%250==0:api.require(job.utc()<job.policy.utc(plan['final_audit_deadline_utc']),'Original final audit cutoff')
            api.require(len(list(folder.glob('segment_*.json.xz')))==len(markers)==len(list(folder.glob('segment_*.audit.json'))),'No orphan inherited segments')
            if name==r.NAME:
                api.require(count==reconstruction['total_saved_steps'] and stop==reconstruction['time_s'],'Complete reconstructed prefix matches inherited inventory')
                previous_checkpoint=api.digest(api.read(r.RECON/'checkpoint_01060.json'));previous_result=None
                for entry in recovery['entries']:
                    newfolder=r.RUN/'production_01'/f"segment_{entry['segment']:05d}"
                    row=r.sealed(newfolder/'results.json');api.verify_mapping(row['artifacts'])
                    api.require(row['passed'] and row['recovery_design_sha256']==api.sha(r.PLAN)
                        and row['physical_design_sha256']==api.sha(job.DESIGN)
                        and row['numerical_policy_contract_sha256']==api.sha(job.WORK),'Exact passing continuation identities')
                    api.require(row['input_checkpoint_sha256']==previous_checkpoint and row['previous_recovery_receipt_sha256']==previous_result,'Exact continuation checkpoint/receipt ancestry')
                    api.require(row['summary']['start_s']==stop and row['new_saved_steps']==entry['new_saved_steps'],'Continuous successor time/steps')
                    count+=row['new_saved_steps'];stop=row['summary']['stop_s'];last=row['summary']
                    previous_checkpoint=row['output_checkpoint_sha256'];previous_result=api.sha(newfolder/'results.json')
                    chain.append(newfolder/'trace.npy');artifacts.update(row['artifacts'])
                    artifacts[str(newfolder/'results.json')]=previous_result
                terminal=api.read(r.RUN/'production_01/checkpoint.json')
                api.require(api.digest(terminal)==previous_checkpoint==recovery['final_checkpoint_sha256'],'Complete stitched terminal checkpoint')
                state=terminal['state'];label=recovery['final_status'];rejected=state['rejected'];first=state['first_contact_dwell_time']
            else:
                produced=api.read(folder/'result.json')
                api.require(api.read(folder/'completion.json')['result_sha256']==api.sha(folder/'result.json')
                    and produced['design_sha256']==api.sha(job.DESIGN),'Original producer completion seal')
                final=produced['final_result'];state=final['checkpoint']['state'];label=final['status'];rejected=final['rejected'];first=final['first_contact_dwell_time_s']
                api.require(state['steps']==count and state['t']==stop,'Producer endpoint accounting')
                api.require(api.digest(state)==final['checkpoint']['state_sha256']==last['output_checkpoint_state_sha256'],'Producer and independent terminal state identity')
                artifacts[str(folder/'result.json')]=api.sha(folder/'result.json')
            evidence=dict(status=label,steps=count,start_s=0.,stop_s=stop,rejected=rejected,failure_markers=[],
                pending_trial=state['pending_trial'],first_dwell_s=first,export_verified=label=='full_window_exit',
                raw_hashes_verified=True,clock_steps_verified=True,physics_verified=True,fresh_start=True)
            observations[name]=job.policy.observation(evidence,case['spec']['horizon_s']);traces[name]=chain;saved+=count
            details.append(dict(case=name,steps=count,stop_s=stop,inherited_segments=len(markers),new_segments=len(chain)-len(markers)))
        comparisons={}
        for shape in ('rigid_prolate_ar4','equal_volume_sphere'):
            selected=next(c for c in d['cases'] if c['shape']==shape and c['sample_id']==0 and c['factor']==.0625)
            fine=next(c for c in d['cases'] if c['shape']==shape and c['sample_id']==0 and c['factor']==.03125)
            def blocks(name):
                for p in traces[name]:yield np.load(p,mmap_mode='r',allow_pickle=False)
            def initial(c):
                state=c['spec']['initial_state'];return [0.,*state['position_m'],*state['orientation'],*state['velocity_generalized']]
            cfg=selected['spec']['config'];a=observations[selected['id']];b=observations[fine['id']]
            metrics=job.path_metrics.metrics(blocks(selected['id']),blocks(fine['id']),initial(selected),initial(fine),a['stop_s'],b['stop_s'],cfg['prolate_semiaxes_m'][1],cfg['target_mean_interstitial_velocity_m_s'])
            comparisons[shape]=job.policy.pair_gates(a,b,metrics,d['numerical_gates'])
        failures=[str(p) for p in job.RUN.rglob('*.failure.json')]+[str(p) for p in job.RUN.rglob('*.exception.json')]
        failures += [str(p) for p in (r.RUN/'production_01').rglob('failure.json')]
        api.require(job.utc()<job.policy.utc(plan['final_audit_deadline_utc']),'Final assembly within original audit deadline')
        summary=job.policy.campaign_summary(d['cases'],observations,comparisons,failures,[],0)
        summary.update(successor_evaluation=True,original_stage219_remains_interrupted=True,original_terminal_record_created=False,
            new_trajectory_steps=0,physical_trajectory_steps=saved,qualification_steps=1024,details=details,
            recovery_design_sha256=api.sha(r.PLAN),physical_design_sha256=api.sha(job.DESIGN),artifacts=artifacts,
            audit_scope='All inherited raw/trace/receipt hashes and original independent physics receipts authenticated; all new segments independently decoded and physically audited. Original physical audits reused, not rerun.',
            claim='Original finite-horizon six-observation scientific gates evaluated using explicit continuation lineage. Two placements, one packing and flow; no population shape/flow trend or empirical validation.')
        job.commit(destination/'results.json',summary);job.commit(destination/'completion.json',dict(passed=summary['passed'],results_sha256=api.sha(destination/'results.json')))
        print('SUCCESSOR_FULL_PATH_GATES',summary['passed'],saved,flush=True)
    except Exception as error:
        job.commit(destination/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0));raise


if __name__=='__main__':run()
