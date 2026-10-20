"""Full sealed checkpoint/history chain, with inherited physical receipts.

Restore and hash every full checkpoint. Prior physics is authenticated through
original passing receipts; only the last two full logical records are decoded
again by the independent codec. No physical solver is executed.
"""
from pathlib import Path
import copy, hashlib, json, os, sys, time, traceback
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage219_staging'),str(ROOT/'stage194_staging')]
import normal_gap_campaign_v1 as source
import qualify_failure_codec_v1 as independent
api,job=source.api,source.job
NAME='s2_i124_fibre_f0p0625'
OUT=ROOT/'stage220_evaluations/checkpoint_recovery_20261006/reconstruction_02'


def run():
    d=api.read(job.DESIGN);job.verify(d);source.bindings()
    api.require(not source.active_owned() and not OUT.exists(),'Exclusive reconstruction, no simulation')
    dh=api.sha(job.DESIGN);case=next(c for c in d['cases'] if c['id']==NAME)
    markers=sorted((job.RUN/NAME).glob('segment_*.ready.json'))
    api.require(len(markers)==1060,'Exact interrupted chain inventory')
    OUT.mkdir(parents=True)
    job.commit(OUT/'launch.json',dict(pid=os.getpid(),utc=job.utc().isoformat(),new_trajectory_steps=0,source_sha256=api.sha(__file__)))
    before=prefix=receipt_sha=None;history=[];checks=[];inputs={str(job.DESIGN):dh,str(Path(__file__)):api.sha(__file__)}
    total=0;started=time.perf_counter();tail={}
    try:
        expected_contract=job.parent.engine.prior.contracts.expected_contract(case['spec'],job.parent.model.binding_for(job.binding(d,case),True))
        for index,marker in enumerate(markers,1):
            p=job.paths(job.RUN,NAME,index)
            api.require(marker==p['ready'],'Contiguous marker inventory')
            # Frozen fresh bounded reader checks compressed/uncompressed SHA256,
            # CRC64, sizes, format and exact design before parsing a private tree.
            wrapper=source.stack.storage.fresh_reader(p['raw'],dh)
            api.require(wrapper['evidence_encoding']==d['codec_schema'],'Exact lossless schema')
            env=wrapper['packed_envelope'];meta=env['history'];rec=env['payload']
            job.policy.verify_receipt(p,NAME,index,dh,d['audit_source_sha256'],api.digest(before),receipt_sha)
            m=api.read(p['ready']);receipt=api.read(p['receipt']);summary=receipt['summary'];seal=api.read(p['raw'].with_suffix('.seal.json'))
            api.require(meta['prefix']==prefix,'Exact historical prefix ancestry')
            history=history+meta['appended_rows'];hb=job.codec.packed_history(history)
            api.require(len(history)==meta['length'] and hashlib.sha256(hb).hexdigest()==meta['sha256'],'Complete restored history digest')
            cp=rec['result']['checkpoint'];cp['state']['history']=history
            api.require(cp['contract']==expected_contract and api.digest(cp['state'])==cp['state_sha256']==summary['output_checkpoint_state_sha256'],'Exact complete state/contract digest')
            api.require(rec['input_checkpoint_sha256']==api.digest(before),'Complete checkpoint ancestry')
            api.require(rec['spec']==case['spec'] and rec['effective_binding']==job.parent.model.binding_for(job.binding(d,case),True),'Exact physical case and binding')
            api.require(rec['numerical_policy_contract_sha256']==api.sha(job.WORK),'Frozen numerical policy')
            api.require(env['original_uncompressed_sha256']==receipt['original_raw_sha256'],'Inherited full logical identity')
            api.require(summary['passed'] and rec['result']['rejected']==0 and summary['steps']==m['steps']==len(rec['rows']),'Inherited health and exact saved-step count')
            api.require(summary['start_s']==(0. if before is None else before['state']['t']) and summary['stop_s']==cp['state']['t'],'Continuous physical times')
            total+=m['steps'];api.require(cp['state']['steps']==total,'Continuous cumulative steps')
            next_prefix=job.codec.make_state(p['raw'],env,hb,seal)
            receipt_sha=api.sha(p['receipt'])
            checks.append(dict(segment=index,receipt_sha256=receipt_sha,checkpoint_sha256=api.digest(cp),
                history_sha256=next_prefix.history_sha256,history_length=next_prefix.history_length,raw_sha256=next_prefix.compressed_sha256,
                original_raw_sha256=receipt['original_raw_sha256'],steps=m['steps'],stop_s=summary['stop_s']))
            for path in (p['raw'],p['ready'],p['receipt'],p['trace'],p['raw'].with_suffix('.seal.json')):inputs[str(path)]=api.sha(path)
            if index>=1058:tail[index]=dict(checkpoint=cp,prefix=next_prefix.reference(),history=history)
            if index>=1059:
                job.commit(OUT/f'checkpoint_{index:05d}.json',cp)
                job.commit(OUT/f'prefix_{index:05d}.json',next_prefix.reference())
                job.commit(OUT/f'history_{index:05d}.json',history)
            before,prefix=cp,next_prefix.reference()
            if index%25==0:print('AUTHENTICATED_CHECKPOINT',index,total,cp['state']['t'],round(time.perf_counter()-started,1),flush=True)
        for index in (1059,1060):
            rec=independent.independent_file(job.paths(job.RUN,NAME,index)['raw'],dh,tail[index-1]['history'],tail[index-1]['prefix'])
            api.require(api.digest(rec['result']['checkpoint'])==api.digest(tail[index]['checkpoint']),'Independent full logical decoder/complete checkpoint identity')
        api.require(total==5531978 and before['state']['t']==3.439634877424857,'Original incomplete endpoint')
        result=dict(passed=True,new_trajectory_steps=0,original_campaign_passed=False,case=NAME,original_design_sha256=dh,
            original_binding=job.binding(d,case),original_numerical_policy_contract_sha256=api.sha(job.WORK),
            complete_chain_segments=len(checks),total_saved_steps=total,time_s=before['state']['t'],horizon_s=case['spec']['horizon_s'],
            complete_checkpoint_and_history_reconstructed=True,inherited_physics_receipts_authenticated=True,
            full_raw_compressed_and_uncompressed_seals_checked=True,all_checkpoint_state_digests_checked=True,
            independent_full_logical_tail_records=2,independent_physics_replayed=False,seconds=time.perf_counter()-started,
            checks=checks,inputs=inputs,artifacts={str(p):api.sha(p) for p in OUT.glob('*.json')},
            prior_attempt='reconstruction_01 is preserved as an interrupted zero-step reconstruction attempt',
            claim='Exact full-chain raw/history/checkpoint authentication with inherited physics receipts; independent full logical last-two reconstruction. Original campaign remains interrupted.')
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',dict(passed=True,results_sha256=api.sha(OUT/'results.json')))
        print('FULL_CHECKPOINT_RECONSTRUCTED',total,before['state']['t'],flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',dict(error=repr(error),traceback=traceback.format_exc(),new_trajectory_steps=0,completed_segments=len(checks)));raise


if __name__=='__main__':run()
