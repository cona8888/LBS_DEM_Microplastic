"""Zero-step alias/cycle/default semantics and complete independent codec QA."""
from pathlib import Path
from types import FunctionType
import copy,math,sys,time,traceback
import lossless_tree_copy_v1 as candidate
import qualify_transaction_json_v1 as prior
api,job,q,WORK=prior.api,prior.job,prior.q,prior.WORK
DESIGN=WORK.with_name('tree_copy_01.json');RUN=prior.RUN.with_name('tree_copy_01');OUT=prior.OUT.with_name('tree_copy_01')
ns={**prior.tests.__dict__,'candidate':candidate,'WORK':WORK,'DESIGN':DESIGN,'RUN':RUN,'OUT':OUT,'__file__':__file__}
f=prior.tests.run;run_fixtures=FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)

def graph(x,seen=None):
    if seen is None:seen={}
    if type(x) in candidate.ATOMIC:
        if type(x) is float:return ('float',x.hex())
        return (type(x).__name__,x)
    if id(x) in seen:return ('ref',seen[id(x)])
    seen[id(x)]=len(seen)
    if isinstance(x,(list,tuple)):return(type(x).__name__,[graph(y,seen) for y in x])
    if isinstance(x,dict):return(type(x).__name__,[(graph(k,seen),graph(v,seen)) for k,v in x.items()])
    return(type(x).__name__,repr(x))

def main():
    api.require(job.utc()<job.policy.utc(api.read(WORK)['work_end_utc']),'work cutoff')
    sealed=prior.OUT/'results.json';api.require(api.read(sealed)['passed'] and api.read(sealed.parent/'completion.json')['results_sha256']==api.sha(sealed),'qualified prior codec')
    mapping={str(x):api.sha(x) for x in (Path(__file__),Path(candidate.__file__),Path(candidate.memo_storage.__file__),Path(prior.tests.__file__),WORK,sealed,sealed.parent/'completion.json')}
    job.commit(DESIGN.with_name('tree_copy_harness_01.json'),{'stage':'Stage199 exact private reconstruction copy qualification','inputs':mapping,'new_trajectory_steps':0,'maximum_random_graphs':1000,'benchmark_rounds':3,'reader_speedup_gate':1.1,'bound':'Original envelope/history/raw hashes and every independent decoder check retained; only private container copying changes.'})
    import random
    rng=random.Random(19910)
    atoms=[None,False,True,0,-1,2**100,0.,-0.,float('nan'),float('inf'),'unicode\u03bb','line\nquote"']
    def make(depth):
        if depth==0 or rng.random()<.4:return rng.choice(atoms)
        if rng.random()<.5:return [make(depth-1) for _ in range(rng.randrange(8))]
        return {str(k):make(depth-1) for k in range(rng.randrange(8))}
    values=[make(5) for _ in range(1000)]
    shared=[1.,-0.];values.append([shared,shared,{'a':shared}])
    cycle=[];cycle.append(cycle);values.append(cycle)
    loop={};loop['self']=loop;values.append(loop)
    cycle2=[];pair=(cycle2,shared);cycle2.append(pair);values.append(pair)
    values.extend([bytearray(b'abc'),{'x':(shared,shared),'s':set([1,2]),'b':b'abc'}])
    for value in values:
        before=graph(value);a=copy.deepcopy(value);b=candidate.tree_copy(value)
        api.require(graph(a)==graph(b)==before and graph(value)==before,'copy value/alias/cycle semantics and no input mutation')
        if type(value) in (dict,list):api.require(b is not value,'independent copied container')
    job.commit(OUT.parent/'tree_copy_edges_01.json',{'passed':True,'checks':len(values),'new_trajectory_steps':0,'inputs':mapping})
    run_fixtures()
    raw=Path('D:/MATDEM_MICROPLASTIC/stage199_runs/eight_hour_optimization_20260926/current_prefix_01/serial.json.xz')
    design=api.read(raw.with_suffix('.seal.json'))['design_sha256']
    expected=q.independent_file(raw,design);original=prior.candidate
    info=__import__('qualify_performance_stack_v1').wrapper.affinity.bind(14);rows=[]
    for i in range(3):
        for label,module in (('original',original),('tree',candidate)) if i%2==0 else (('tree',candidate),('original',original)):
            tick=time.perf_counter();decoded,_=module.codec.read_record(raw,design);elapsed=time.perf_counter()-tick
            api.require(candidate.base.raw_bytes(decoded)==candidate.base.raw_bytes(expected),'full canonical independent read identity')
            rows.append({'round':i,'mode':label,'read_seconds':elapsed});print('TREE_READ',label,elapsed,flush=True)
    means={label:sum(x['read_seconds'] for x in rows if x['mode']==label)/3 for label in ('original','tree')}
    speed=means['original']/means['tree'];candidate.verify_bindings();api.verify_mapping(mapping)
    r={'passed':True,'new_trajectory_steps':0,'reader_speedup':speed,'material_reader_gain_passed':speed>=1.1,'reader_speedup_gate':1.1,'measurements':rows,'means':means,'independent_reference_sha256':api.sha(raw),'fixture_results_sha256':api.sha(OUT/'results.json'),'affinity':info,'inputs':mapping,'production_authorized':False}
    job.commit(OUT/'benchmark.json',r);job.commit(OUT/'benchmark_completion.json',{'benchmark_sha256':api.sha(OUT/'benchmark.json')});print('TREE_COPY_QUALIFIED',speed,r['material_reader_gain_passed'],flush=True)

if __name__=='__main__':
    try:main()
    except Exception as e:
        path=OUT.parent/'tree_copy_failure_01.json'
        if not path.exists():job.commit(path,{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0})
        raise
