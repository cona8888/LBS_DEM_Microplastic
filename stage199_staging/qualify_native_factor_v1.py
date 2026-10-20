"""Exact structured equality and original full archive/failure/chain tests."""
from pathlib import Path
from types import FunctionType
import copy,random,sys,time,traceback
import numpy as np
import native_factor_storage_v1 as candidate
ROOT=candidate.ROOT
sys.path.insert(0,str(ROOT/'stage196_staging'))
import qualify_compact_storage_v1 as tests
import native_storage_v2 as previous
WORK=ROOT/'stage199_designs/eight_hour_optimization_20260926/contract_01.json'
DESIGN=WORK.with_name('native_factor_01.json')
RUN=Path('D:/MATDEM_MICROPLASTIC/stage199_runs/eight_hour_optimization_20260926/native_factor_01')
OUT=ROOT/'stage199_evaluations/eight_hour_optimization_20260926/native_factor_01'
api,job=tests.api,tests.job
ns={**tests.__dict__,'candidate':candidate,'WORK':WORK,'DESIGN':DESIGN,'RUN':RUN,'OUT':OUT,'__file__':__file__}
run=FunctionType(tests.run.__code__,ns,tests.run.__name__,tests.run.__defaults__,tests.run.__closure__)

def main():
    api.require(job.utc()<job.policy.utc(api.read(WORK)['work_end_utc']),'work cutoff')
    prerequisite=OUT.parent/'native_storage_02/results.json';r=api.read(prerequisite)
    api.require(r['passed'] and api.read(prerequisite.parent/'completion.json')['results_sha256']==api.sha(prerequisite),'prior sealed codec qualification')
    files=[Path(__file__),Path(candidate.__file__),Path(candidate.canonical.__file__),Path(candidate.prior.__file__),Path(tests.__file__),Path(previous.__file__),WORK,prerequisite,prerequisite.parent/'completion.json']
    mapping={str(x):api.sha(x) for x in files}
    job.commit(DESIGN.with_name('native_factor_harness_01.json'),{'stage':'Stage199 exact built-in-tree factoring qualification','inputs':mapping,'new_trajectory_steps':0,'test_code':'Original full failure/chain/rejection test unchanged, new isolated candidate bound explicitly.'})
    special=[0.,-0.,np.nan,np.inf,-np.inf,1.,1,True,None,'é\\\n"',np.float64(2),np.int64(2),np.array([1.,2.])]
    values=special+[[],{},[{},[]],tuple(special),{'z':special,'a':[]},{'a':1,'b':2},{'b':2,'a':1},[[0.,1]],[[0,1]],{1:'x'},{'1':'x'}]
    def outcome(fn):
        try:return ('ok',fn())
        except Exception as e:return ('exception',type(e).__name__)
    count=0
    for a in values:
        for b in values:
            actual=outcome(lambda:candidate.equivalent(a,b));expected=outcome(lambda:candidate.base.raw_bytes(a)==candidate.base.raw_bytes(b))
            api.require(actual==expected,'exact structured equality edge/exception');count+=1
    cyclic=[];cyclic.append(cyclic)
    for a,b in ((cyclic,[]),([],cyclic),(cyclic,cyclic),(object(),None),({'a':1,2:3},{})):
        api.require(outcome(lambda:candidate.equivalent(a,b))==outcome(lambda:candidate.base.raw_bytes(a)==candidate.base.raw_bytes(b)),'original unsupported/circular semantics');count+=1
    rng=random.Random(19903);pairs=[]
    for i in range(1000):
        a={'z':[rng.random(),rng.choice(special[:10])],'nested':[{'a':rng.randint(-999,999),'b':[0.,-0.]}]};b=copy.deepcopy(a)
        if i%2:b['nested'][0]['a']+=1
        pairs.append((a,b))
        api.require(candidate.equivalent(a,b)==(candidate.base.raw_bytes(a)==candidate.base.raw_bytes(b)),'randomized structured identity');count+=1
    # Frozen identical inputs, timer result is descriptive; no automatic adoption.
    times={}
    for name,fn in [('previous',previous.prior.equivalent),('candidate',candidate.equivalent)]:
        tick=time.perf_counter()
        for _ in range(10):
            for a,b in pairs:fn(a,b)
        times[name]=time.perf_counter()-tick
    job.commit(DESIGN.with_name('native_factor_edges_01.json'),{'passed':True,'pairs':count,'timings':times,'speedup':times['previous']/times['candidate'],'new_trajectory_steps':0,'inputs':mapping})
    print('NATIVE_FACTOR_EDGES',count,times,flush=True);run()

if __name__=='__main__':
    try:main()
    except Exception as e:
        path=OUT.parent/'native_factor_failure_01.json'
        if not path.exists():job.commit(path,{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0})
        raise
