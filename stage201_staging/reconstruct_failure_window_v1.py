"""Zero-step exact raw/history reconstruction; no mutation of failed campaign."""
from pathlib import Path
import copy, hashlib, os, time, traceback
import inspect_failed_contact_v1 as source

job,api,frozen,ROOT=source.job,source.api,source.frozen,source.ROOT
OUT=ROOT/'stage201_evaluations/contact_repair_20260928/reconstructed_window_01'


def run():
    w=api.read(source.WORK);api.require(job.utc()<job.policy.utc(w['work_end_utc']),'work window')
    d=api.read(job.DESIGN);job.verify(d);dh=api.sha(job.DESIGN)
    resultfile=job.RUN/source.NAME/'result.json';donefile=resultfile.parent/'completion.json'
    api.require(api.sha(resultfile)==api.read(donefile)['result_sha256'],'sealed producer result')
    result=api.read(resultfile)['final_result'];history=result['history'];codec=frozen.pre.storage.codec
    inputs={str(p):api.sha(p) for p in (source.WORK,job.DESIGN,Path(__file__),resultfile,donefile)}
    OUT.mkdir(parents=True,exist_ok=False);job.commit(OUT/'launch.json',{'utc':job.utc().isoformat(),'pid':os.getpid(),'new_trajectory_steps':0,'inputs':inputs})
    checks=[];records={};states={}
    try:
        for number in range(194,198):
            api.require(job.utc()<job.policy.utc(w['work_end_utc']),'work cutoff')
            p=job.paths(job.RUN,source.NAME,number);sp=p['raw'].with_suffix('.seal.json')
            marker,receipt,seal=api.read(p['ready']),api.read(p['receipt']),api.read(sp)
            api.require(receipt['ready_sha256']==api.sha(p['ready']) and marker['raw_sha256']==api.sha(p['raw'])==seal['compressed_sha256'],'ready/receipt/raw seal')
            api.require(receipt['status']==('audit_failed' if number==197 else 'audit_passed'),'original receipt verdict retained')
            env=frozen.pre.storage.read_envelope(p['raw'],dh)
            hist=history[:env['history']['length']];hb=codec.packed_history(hist)
            api.require(hashlib.sha256(hb).hexdigest()==env['history']['sha256'],'full history prefix from sealed producer')
            if number==194:
                # A byte-exact independently sealed bootstrap, not a claim of
                # independently re-auditing all earlier physical steps.
                rec=copy.deepcopy(env['payload']);rec['result']['history']=hist;rec['result']['checkpoint']['state']['history']=hist
                raw=frozen.pre.storage.base.raw_bytes(rec)
                api.require(len(raw)==env['original_uncompressed_bytes'] and hashlib.sha256(raw).hexdigest()==env['original_uncompressed_sha256'],'original complete record194 canonical seal')
                state=codec.make_state(p['raw'],env,hb,seal)
            else:
                rec,state=codec.read_record(p['raw'],dh,states[number-1])
                api.require(state.history_bytes==hb,'independent codec/full-producer history identity')
                api.require(rec['input_checkpoint_sha256']==api.digest(records[number-1]['result']['checkpoint']),'checkpoint ancestry')
            records[number]=rec;states[number]=state
            cp=rec['result']['checkpoint'];api.require(cp['state']['history']==rec['result']['history'],'two history copies')
            checks.append({'segment':number,'status':receipt['status'],'raw_sha256':api.sha(p['raw']),'original_sha256':env['original_uncompressed_sha256'],'history_sha256':env['history']['sha256'],'history_rows':len(hist),'checkpoint_sha256':api.digest(cp),'steps':marker['steps']})
            for file in (p['raw'],sp,p['ready'],p['receipt']):inputs[str(file)]=api.sha(file)
            print('RECONSTRUCTED',number,len(hist),marker['steps'],flush=True)
        api.require(api.digest(records[197]['result'])==api.digest(result),'entire failed result matches sealed producer')
        for number in (195,196):
            job.commit(OUT/('checkpoint_%05d.json'%number),records[number]['result']['checkpoint'])
        job.commit(OUT/'prefix_00196.json',states[196].reference())
        job.commit(OUT/'history_00196.json',records[196]['result']['history'])
        api.verify_mapping(inputs);job.verify(d)
        r={'passed':True,'new_trajectory_steps':0,'inputs':inputs,'checks':checks,'artifacts':{str(p):api.sha(p) for p in OUT.glob('*.json')},'claim':'Exact local raw/history/checkpoint reconstruction, not promotion of failed segment197 or full prior-chain numerical audit.'}
        job.commit(OUT/'results.json',r);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')})
        print('WINDOW_RECONSTRUCTION_PASS',flush=True)
    except Exception as error:
        job.commit(OUT/'failure.json',{'error':repr(error),'traceback':traceback.format_exc(),'checks':checks,'new_trajectory_steps':0});raise


if __name__=='__main__':run()
