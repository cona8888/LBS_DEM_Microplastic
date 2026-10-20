"""Read-only early full-path screen of the completed original sample-0 pairs."""
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage219_staging'))
import normal_gap_campaign_v1 as source
api,job=source.api,source.job
OUT=ROOT/'stage220_evaluations/checkpoint_recovery_20261006/existing_pair_screen_01'


def run():
    d=api.read(job.DESIGN);dh=api.sha(job.DESIGN)
    api.require(d['binding']==api.digest({k:v for k,v in d.items() if k!='binding'}),'Exact original design')
    api.require(not OUT.exists(),'New early screen')
    results={};traces={};observations={};inputs={str(job.DESIGN):dh,str(Path(__file__)):api.sha(__file__)}
    for case in [c for c in d['cases'] if c['sample_id']==0]:
        name=case['id'];folder=job.RUN/name;produced=api.read(folder/'result.json');seal=api.read(folder/'completion.json')
        api.require(seal['result_sha256']==api.sha(folder/'result.json') and produced['design_sha256']==dh,'Sealed complete producer')
        final=produced['final_result'];markers=sorted(folder.glob('segment_*.ready.json'));chain=[];previous=None;stop=0.;steps=0
        for index,marker in enumerate(markers,1):
            paths=job.paths(job.RUN,name,index);m=api.read(marker);receipt=api.read(paths['receipt']);s=receipt['summary']
            api.require(marker==paths['ready'] and m['segment']==receipt['segment']==index and receipt['case']==name,'Contiguous inherited identity')
            api.require(receipt['design_sha256']==m['design_sha256']==dh and receipt['audit_source_sha256']==d['audit_source_sha256'],'Bound original physical auditor')
            api.require(receipt['status']=='independently_verified' and s['passed'] and receipt['previous_receipt_sha256']==previous,'Passing independent receipt ancestry')
            api.require(receipt['ready_sha256']==api.sha(marker) and receipt['trace_path']==str(paths['trace']) and receipt['trace_sha256']==api.sha(paths['trace']),'Exact independently audited trace hash')
            api.require(s['start_s']==stop and s['steps']==m['steps'],'Full time/step coverage')
            stop=s['stop_s'];steps+=s['steps'];previous=api.sha(paths['receipt']);chain.append(paths['trace'])
            inputs[str(marker)]=api.sha(marker);inputs[str(paths['receipt'])]=previous;inputs[str(paths['trace'])]=receipt['trace_sha256']
        api.require(final['checkpoint']['state']['steps']==steps and final['checkpoint']['state']['t']==stop,'Producer complete accounting')
        api.require(api.digest(final['checkpoint']['state'])==final['checkpoint']['state_sha256']==s['output_checkpoint_state_sha256'],'Independent full terminal state identity')
        evidence=dict(status=final['status'],steps=steps,start_s=0.,stop_s=stop,rejected=final['rejected'],failure_markers=[],
            pending_trial=final['checkpoint']['state']['pending_trial'],first_dwell_s=final['first_contact_dwell_time_s'],
            export_verified=final['status']=='full_window_exit',raw_hashes_verified=True,clock_steps_verified=True,physics_verified=True,fresh_start=True)
        # raw_hashes_verified here denotes authenticated original audit verdicts;
        # this early screen freshly hashes traces, not all compressed archives.
        observations[name]=job.policy.observation(evidence,case['spec']['horizon_s']);traces[name]=chain
        api.require(observations[name]['complete_observation'],'Complete original observation')
        inputs[str(folder/'result.json')]=api.sha(folder/'result.json')
        print('EARLY_TRACE_AUTHENTICATED',name,steps,flush=True)
    for shape in ('rigid_prolate_ar4','equal_volume_sphere'):
        a=next(c for c in d['cases'] if c['sample_id']==0 and c['shape']==shape and c['factor']==.0625)
        b=next(c for c in d['cases'] if c['sample_id']==0 and c['shape']==shape and c['factor']==.03125)
        def blocks(name):
            for path in traces[name]:yield np.load(path,mmap_mode='r',allow_pickle=False)
        def initial(c):
            s=c['spec']['initial_state'];return [0.,*s['position_m'],*s['orientation'],*s['velocity_generalized']]
        cfg=a['spec']['config'];oa=observations[a['id']];ob=observations[b['id']]
        metrics=job.path_metrics.metrics(blocks(a['id']),blocks(b['id']),initial(a),initial(b),oa['stop_s'],ob['stop_s'],cfg['prolate_semiaxes_m'][1],cfg['target_mean_interstitial_velocity_m_s'])
        results[shape]=job.policy.pair_gates(oa,ob,metrics,d['numerical_gates'])
    r=dict(passed=all(x['passed'] for x in results.values()),new_trajectory_steps=0,comparisons=results,
        original_campaign_passed=False,observations=observations,inputs=inputs,
        audit_scope='Original independent physics receipts and complete producer seals authenticated; all trace hashes freshly checked. Compressed archives not rehashed in this preliminary screen.',
        claim='Full-horizon sample-0 numerical screen only. Interrupted sample-124 fibre still needs recovery; combined successor evaluation remains required.')
    job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',dict(passed=r['passed'],results_sha256=api.sha(OUT/'results.json')))
    print('EARLY_FULL_PATH_GATES',r['passed'],results,flush=True)


if __name__=='__main__':run()
