"""Zero-step canonical equality and unbiased saved-record benchmark."""
from pathlib import Path
from datetime import datetime,timezone
import random,sys,time,math,traceback
import token_storage_v1 as candidate
ROOT=candidate.ROOT
sys.path.insert(0,str(ROOT/'stage198_staging'))
import fast_storage_v1 as old
import profile_runtime_storage_v1 as profile
api,job,q=profile.api,profile.job,profile.q
WORK=profile.WORK;DESIGN=WORK.with_name('canonical_tokens_01.json');OUT=profile.OUT.parent/'canonical_tokens_01'

def main():
    work=api.read(WORK);api.require(datetime.now(timezone.utc)<datetime.fromisoformat(work['work_end_utc']),'work cutoff')
    profile.held.pre.wrapper.affinity.bind(14)
    files=[Path(__file__),Path(candidate.__file__),Path(candidate.canonical.__file__),WORK,profile.OUT/'results.json',profile.OUT/'completion.json',profile.RAW,profile.RAW.with_suffix('.seal.json'),profile.RAWDESIGN]
    protocol={'new_trajectory_steps':0,'inputs':{str(x):api.sha(x) for x in files},'random_seed':199,'random_objects':1000,'full_record_rounds':3,'criteria':'Original canonical byte equality including signed zero, float extremes, strings/escapes, integer and default handling; preserved rejection of cycles/unsupported keys.'}
    job.commit(DESIGN,protocol);OUT.mkdir(parents=True,exist_ok=False)
    try:
        import numpy as np
        special=[0.,-0.,float('nan'),float('inf'),-float('inf'),1e-308,5e-324,1e308,1e-7,1.,1,True,None,'[{}]:,\\"\n\t é \ud800',2**80,-2**80]
        tests=[special,{'z':special,'a':[special,special]},[],{},[[],{}],tuple(special),np.array([0.,-0.,1e300]),np.float64(3.),{1:3,2:4},{True:'a',False:'b'},{None:5}]
        rng=random.Random(protocol['random_seed'])
        for _ in range(protocol['random_objects']):
            values=[rng.uniform(-1e25,1e25),rng.randint(-2**70,2**70),rng.choice(special)]
            tests.append({'f':values,'matrix':[[rng.random() for _ in range(9)] for _ in range(6)],'a':[values,{},False,[[values]]]})
        for obj in tests:api.require(candidate.raw_bytes(obj)==candidate.base.raw_bytes(obj),'exact canonical object')
        cycle=[];cycle.append(cycle);bad=[cycle,{'a':1,1:2},{(1,2):0},object()];rejections=[]
        for obj in bad:
            results=[]
            for fn in (candidate.base.raw_bytes,candidate.raw_bytes):
                try:fn(obj);results.append(None)
                except Exception as e:results.append(type(e).__name__)
            api.require(results[0] is not None and results[0]==results[1],'same invalid-input rejection class');rejections.append(results[0])
        record=q.independent_file(profile.RAW,api.sha(profile.RAWDESIGN));expected=candidate.base.raw_bytes(record)
        timings={'stage198':[],'tokens':[]}
        for i in range(protocol['full_record_rounds']):
            for label,fn in ([('stage198',old.raw_bytes),('tokens',candidate.raw_bytes)] if i%2==0 else [('tokens',candidate.raw_bytes),('stage198',old.raw_bytes)]):
                start=time.perf_counter();encoded=fn(record);elapsed=time.perf_counter()-start;api.require(encoded==expected,'full archived original canonical bytes');timings[label].append(elapsed)
        api.verify_mapping(protocol['inputs']);candidate.verify_bindings()
        result={'passed':True,'new_trajectory_steps':0,'edge_objects':len(tests),'invalid_input_rejections':rejections,'timings_seconds':timings,'mean_speedup':sum(timings['stage198'])/sum(timings['tokens']),'raw_bytes':len(expected),'protocol_sha256':api.sha(DESIGN),'production_authorized':False}
        job.commit(OUT/'results.json',result);job.commit(OUT/'completion.json',{'passed':True,'results_sha256':api.sha(OUT/'results.json')});print('CANONICAL_TOKENS_PASS',result,flush=True)
    except Exception as e:
        job.commit(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0});raise

if __name__=='__main__':main()
