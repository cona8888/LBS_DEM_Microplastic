"""Zero-step exact helper/outer regression; no new trajectory budget."""
from pathlib import Path
from types import FunctionType
import sys,traceback
import numpy as np
import exact_trf_helpers_v1 as candidate
ROOT=candidate.ROOT
sys.path.insert(0,str(ROOT/'stage198_staging'))
import qualify_direct_trf_v1 as tests
import qualify_solver_brackets_v1 as previous
api,job=tests.api,tests.job
WORK=previous.WORK;DESIGN=WORK.with_name('trf_helpers_01.json');OUT=previous.OUT.with_name('trf_helpers_01')
ns={**tests.__dict__,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'__file__':__file__}
for name in ('trials','verify','run'):
    f=getattr(tests,name);ns[name]=FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)

def prepare():
    p=api.read(previous.DESIGN);previous.ns['verify'](p);p={**p,'sources':dict(p['sources']),'inputs':dict(p['inputs'])};p.pop('binding')
    for x in (Path(__file__),Path(candidate.__file__)):
        p['sources'][str(x.resolve())]=api.sha(x)
    for x in (previous.DESIGN,previous.OUT/'results.json',previous.OUT.parent/'bracket_helper_edges_01.json'):
        p['inputs'][str(x)]=api.sha(x)
    p.update(stage='Stage199 fixed-size TRF helper specialization',helper_seed=19902,helper_matrices=1000,recovery_steps_before=56666,
        mode_meanings={'baseline':'constant arithmetic and original SciPy wrapper','direct':'Stage199 brackets exact implementation','compiled_direct':'same plus fixed-size norm/scale/finite helpers and invariant-square hoisting'},
        helper_criteria='Bit-identical norms, column scales and trust-region answers; all optimizer/outer outputs and physical checks identical. No termination, tolerances, SVD, iteration controls, trust decisions or matrix products changed.')
    p['binding']=api.digest(p);job.commit(DESIGN,p);ns['verify'](p);print('TRF_HELPERS_PROTOCOL',api.sha(DESIGN),flush=True)

def helpers():
    p=api.read(DESIGN);ns['verify'](p);api.require(job.utc()<job.policy.utc(api.read(WORK)['work_end_utc']),'work cutoff')
    rng=np.random.default_rng(p['helper_seed']);count=0;trust_count=0
    for i in range(p['helper_matrices']):
        scale=(1.,1e-150,1e150)[i%3];m=rng.normal(size=(9,9))*scale
        if i%7==0:m[:,2]=0.
        for J in (m,np.asfortranarray(m),np.tile(m,(2,2))[::2,::2]):
            for old in (None,np.abs(rng.normal(size=9))*scale):
                expected=candidate.original_scale(J,old);actual=candidate.compute_jac_scale(J,old)
                api.require(all(a.tobytes()==b.tobytes() for a,b in zip(expected,actual)),'exact column scaling');count+=1
        x=m[0];api.require(np.asarray(candidate.norm(x,np.inf)).tobytes()==np.asarray(candidate.original_norm(x,np.inf)).tobytes(),'exact infinity norm')
        api.require(candidate.all_finite(m)==np.all(np.isfinite(m)),'same finite decision')
        if i<200:
            U,s,VT=np.linalg.svd(rng.normal(size=(9,9)),full_matrices=False);uf=rng.normal(size=9);V=VT.T
            for radius in (1e-5,.1,10.):
                before=(uf.copy(),s.copy(),V.copy());args=(9,9,uf,s,V,radius)
                a=candidate.trust_original(*args);b=candidate.trust(*args)
                api.require(all(np.asarray(x).tobytes()==np.asarray(y).tobytes() for x,y in zip(a,b)),'exact trust-region solution')
                api.require(all(x.tobytes()==y.tobytes() for x,y in zip(before,(uf,s,V))),'trust inputs not mutated');trust_count+=1
    for z in (0.,-0.,np.inf,-np.inf,np.nan):
        x=np.array([z]*9);api.require(candidate.all_finite(x)==np.all(np.isfinite(x)),'finite edges retained')
        a,b=candidate.norm(x,np.inf),candidate.original_norm(x,np.inf)
        api.require((np.isnan(a) and np.isnan(b)) or np.asarray(a).tobytes()==np.asarray(b).tobytes(),'norm edges retained')
    candidate.batch.equation_arrays(np.zeros((1,9)),0,.3);candidate.batch.bracket_indices(np.zeros(1))
    job.commit(OUT.parent/'trf_helper_edges_01.json',{'passed':True,'new_trajectory_steps':0,'scale_tests':count,'trust_tests':trust_count,'norm_tests':p['helper_matrices']+5,'protocol_sha256':api.sha(DESIGN)})
    print('TRF_HELPERS_EXACT',count,trust_count,flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:
        try:helpers();ns['run']()
        except Exception as e:
            path=OUT.parent/'trf_helpers_failure_01.json'
            if not path.exists():job.commit(path,{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0})
            raise
    else:raise ValueError('prepare | run')
