"""Zero-step exact bracket edge and complete held optimizer qualification."""
from pathlib import Path
from types import FunctionType
import sys,traceback
import numpy as np
import exact_solver_brackets_v1 as candidate
ROOT=candidate.ROOT
sys.path.insert(0,str(ROOT/'stage198_staging'))
import qualify_direct_trf_v1 as tests
import qualify_solver_dispatch_v1 as previous
api,job=tests.api,tests.job
WORK=previous.WORK
DESIGN=WORK.with_name('solver_brackets_01.json')
OUT=previous.OUT.with_name('solver_brackets_01')
ns={**tests.__dict__,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'__file__':__file__}
for name in ('trials','verify','run'):
    f=getattr(tests,name);ns[name]=FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)

def prepare():
    p=api.read(previous.DESIGN);previous.ns['verify'](p);p={**p,'sources':dict(p['sources']),'inputs':dict(p['inputs'])};p.pop('binding')
    for x in (Path(__file__),Path(candidate.__file__),Path(candidate.batch.__file__)):
        p['sources'][str(x.resolve())]=api.sha(x)
    for x in (previous.DESIGN,previous.OUT/'results.json'):
        p['inputs'][str(x)]=api.sha(x)
    p.update(stage='Stage199 exact scalar-bracket bookkeeping',bracket_seed=19901,bracket_random_arrays=1000,
        mode_meanings={'baseline':'constant arithmetic and original SciPy wrapper','direct':'Stage199 exact array/LAPACK dispatch','compiled_direct':'same plus strict native scalar-bracket index selection'},
        helper_criteria='Identical ordered bracket indices, including zero, underflow, overflow and nonfinite tests. Grid, determinant, Brent, root order, stopping controls, physical gates and TRF unchanged.')
    p['binding']=api.digest(p);job.commit(DESIGN,p);ns['verify'](p);print('BRACKETS_PROTOCOL',api.sha(DESIGN),flush=True)

def helpers():
    p=api.read(DESIGN);ns['verify'](p);api.require(job.utc()<job.policy.utc(api.read(WORK)['work_end_utc']),'work cutoff')
    rng=np.random.default_rng(p['bracket_seed']);count=0
    special=np.array([0.,-0.,1e-300,-1e-300,1e300,-1e300,np.inf,-np.inf,np.nan,1.,-1.])
    arrays=[np.array([x,y]) for x in special for y in special]
    arrays += [rng.normal(size=n)*scale for i in range(p['bracket_random_arrays']) for n,scale in [(i%258,(1.,1e-300,1e300)[i%3])]]
    with np.errstate(over='ignore',under='ignore',invalid='ignore'):
        for samples in arrays:
            expected=[]
            for i in range(len(samples)-1):
                if not np.isfinite(samples[i:i+2]).all() or samples[i]*samples[i+1]>=0:continue
                expected.append(i)
            actual=candidate.batch.bracket_indices(samples)
            api.require(actual.tolist()==expected,'exact original ordered bracket selection');count+=1
    candidate.batch.equation_arrays(np.zeros((1,9)),0,.3)
    job.commit(OUT.parent/'bracket_helper_edges_01.json',{'passed':True,'new_trajectory_steps':0,'bracket_arrays':count,'protocol_sha256':api.sha(DESIGN)})
    print('BRACKET_EDGES_EXACT',count,flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:
        try:helpers();ns['run']()
        except Exception as e:
            path=OUT.parent/'bracket_helper_failure_01.json'
            if not path.exists():job.commit(path,{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0})
            raise
    else:raise ValueError('prepare | run')
