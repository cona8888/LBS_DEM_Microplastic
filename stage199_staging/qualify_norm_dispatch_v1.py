"""Zero-step private norm dispatch and complete held-contact equivalence."""
from pathlib import Path
from types import FunctionType
import inspect,sys,traceback
import numpy as np
import exact_norm_dispatch_v1 as candidate
ROOT=candidate.ROOT
sys.path.insert(0,str(ROOT/'stage198_staging'))
import qualify_direct_trf_v1 as tests
import qualify_trf_helpers_v1 as previous
api,job=tests.api,tests.job
WORK=previous.WORK;DESIGN=WORK.with_name('norm_dispatch_01.json');OUT=previous.OUT.with_name('norm_dispatch_01')
ns={**tests.__dict__,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'__file__':__file__}
for name in ('trials','verify','run'):
    f=getattr(tests,name);ns[name]=FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)

def prepare():
    p=api.read(previous.DESIGN);previous.ns['verify'](p);p={**p,'sources':dict(p['sources']),'inputs':dict(p['inputs'])};p.pop('binding')
    fast=candidate.batch.original
    for x in (Path(__file__),Path(candidate.__file__),Path(fast.__file__),Path(fast.old.__file__),Path(fast.gate.__file__),Path(candidate.repair.prior.__file__)):
        p['sources'][str(x.resolve())]=api.sha(x)
    for x in (previous.DESIGN,previous.OUT/'results.json',previous.OUT.parent/'trf_helper_edges_01.json'):
        p['inputs'][str(x)]=api.sha(x)
    p.update(stage='Stage199 private dense norm dispatch',norm_seed=19904,norm_arrays=1000,
        mode_meanings={'baseline':'constant arithmetic and original SciPy wrapper','direct':'Stage199 TRF helpers','compiled_direct':'same plus private original-code-object dense norm dispatch'},
        helper_criteria='All default vector norm bits exact; fallback and exception semantics match NumPy; full optimizer, outer velocity/health and independent physical gates identical.')
    p['binding']=api.digest(p);job.commit(DESIGN,p);ns['verify'](p);print('NORM_DISPATCH_PROTOCOL',api.sha(DESIGN),flush=True)

def helpers():
    p=api.read(DESIGN);ns['verify'](p);api.require(job.utc()<job.policy.utc(api.read(WORK)['work_end_utc']),'work cutoff')
    rng=np.random.default_rng(p['norm_seed']);count=0
    def out(fn):
        try:
            v=np.asarray(fn());return ('ok',v.shape,v.dtype.str,v.tobytes())
        except Exception as e:return ('exception',type(e).__name__)
    with np.errstate(over='ignore',under='ignore',invalid='ignore'):
        for i in range(p['norm_arrays']):
            x=rng.normal(size=i%50)*(1.,1e-200,1e200)[i%3]
            for v in (x,x[::-1],x.astype(np.float32),x.astype(complex),x.tolist()):
                for kw in ({},{'ord':np.inf},{'ord':1},{'keepdims':True}):
                    api.require(out(lambda:candidate.norm(v,**kw))==out(lambda:candidate.original_norm(v,**kw)),'bit-exact private norm/fallback/exception');count+=1
    # Guard restoration on a deliberate exception, and no global NumPy mutation.
    f=candidate.batch.original;targets=[(f,'scalar_solve'),(f,'solve'),(f.old,'constrained_stick'),(f.gate,'_finish'),(f.gate,'_residual'),(candidate.repair.prior,'solve'),(candidate.repair.prior.analytic,'system')]
    saved=[getattr(m,n) for m,n in targets]
    try:
        with candidate.scope('compiled_direct'):
            api.require(np.linalg.norm is candidate.original_norm,'no global NumPy mutation')
            raise LookupError('test restore')
    except LookupError:pass
    api.require(all(getattr(m,n) is old for (m,n),old in zip(targets,saved)),'all private bindings restored')
    candidate.batch.equation_arrays(np.zeros((1,9)),0,.3);candidate.batch.bracket_indices(np.zeros(1))
    candidate.prior.column_norms(np.eye(9));candidate.prior.max_abs(np.zeros(9));candidate.prior.all_finite(np.zeros(9))
    job.commit(OUT.parent/'norm_helper_edges_01.json',{'passed':True,'new_trajectory_steps':0,'norm_checks':count,'restoration_passed':True,'protocol_sha256':api.sha(DESIGN)})
    print('NORM_HELPERS_EXACT',count,flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:
        try:helpers();ns['run']()
        except Exception as e:
            path=OUT.parent/'norm_dispatch_failure_01.json'
            if not path.exists():job.commit(path,{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0})
            raise
    else:raise ValueError('prepare | run')
