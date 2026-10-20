"""Fail-closed zero-step exactness screen of native trust-region translation."""
from pathlib import Path
from types import FunctionType
import sys,traceback
import numpy as np
import native_trust_candidate_v1 as candidate
ROOT=candidate.ROOT
sys.path.insert(0,str(ROOT/'stage198_staging'))
import qualify_direct_trf_v1 as tests
import qualify_dense_dispatch_v1 as previous
api,job=tests.api,tests.job
WORK=previous.WORK;DESIGN=WORK.with_name('native_trust_01.json');OUT=previous.OUT.with_name('native_trust_01')
ns={**tests.__dict__,'candidate':candidate,'DESIGN':DESIGN,'OUT':OUT,'__file__':__file__}
for name in ('trials','verify','run'):
    f=getattr(tests,name);ns[name]=FunctionType(f.__code__,ns,f.__name__,f.__defaults__,f.__closure__)

def prepare():
    p=api.read(previous.DESIGN);previous.ns['verify'](p);p={**p,'sources':dict(p['sources']),'inputs':dict(p['inputs'])};p.pop('binding')
    for x in (Path(__file__),Path(candidate.__file__)):
        p['sources'][str(x.resolve())]=api.sha(x)
    for x in (previous.DESIGN,previous.OUT/'results.json',previous.OUT.parent/'dense_helper_edges_01.json'):
        p['inputs'][str(x)]=api.sha(x)
    p.update(stage='Stage199 strict native trust helper screening',trust_seed=19906,trust_matrices=600,recovery_steps_before=67652,
        mode_meanings={'baseline':'constant arithmetic and original SciPy wrapper','direct':'Stage199 dense dispatch','compiled_direct':'same with strict native existing trust-region algorithm'},
        helper_criteria='Bit-exact helper output and every full optimizer/outer result. Reject even small arithmetic mismatch; no gates or tolerances change.')
    p['binding']=api.digest(p);job.commit(DESIGN,p);ns['verify'](p);print('NATIVE_TRUST_PROTOCOL',api.sha(DESIGN),flush=True)

def helpers():
    p=api.read(DESIGN);ns['verify'](p);api.require(job.utc()<job.policy.utc(api.read(WORK)['work_end_utc']),'work cutoff')
    rng=np.random.default_rng(p['trust_seed']);count=0
    for i in range(p['trust_matrices']):
        J=rng.normal(size=(9,9))
        if i%4==0:J[:,2]=J[:,1]
        U,s,VT=np.linalg.svd(J,full_matrices=False);V=VT.T;uf=rng.normal(size=9)
        for radius in (1e-5,.1,10.):
            for alpha in (None,0.,.03):
                args=(9,9,uf,s,V,radius)
                a=candidate.original_trust(*args,initial_alpha=alpha);b=candidate.trust(*args,initial_alpha=alpha)
                exact=all(np.asarray(x).tobytes()==np.asarray(y).tobytes() for x,y in zip(a,b))
                if not exact:
                    job.commit(OUT.parent/'native_trust_mismatch_01.json',{'new_trajectory_steps':0,'matrix_index':i,'radius':radius,'initial_alpha':alpha,'uf':uf.tolist(),'s':s.tolist(),'V':V.tolist(),'expected':[np.asarray(x).tolist() for x in a],'actual':[np.asarray(x).tolist() for x in b],'prior_exact_checks':count,'protocol_sha256':api.sha(DESIGN)})
                api.require(exact,'strict original trust-region bits');count+=1
    candidate.batch.equation_arrays(np.zeros((1,9)),0,.3);candidate.batch.bracket_indices(np.zeros(1))
    candidate.prior.prior.column_norms(np.eye(9));candidate.prior.prior.max_abs(np.zeros(9));candidate.prior.prior.all_finite(np.zeros(9));candidate.prior.prior.all_finite(np.eye(9))
    job.commit(OUT.parent/'native_trust_edges_01.json',{'passed':True,'new_trajectory_steps':0,'trust_comparisons':count,'protocol_sha256':api.sha(DESIGN)})
    print('NATIVE_TRUST_EXACT',count,flush=True)

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:
        try:helpers();ns['run']()
        except Exception as e:
            path=OUT.parent/'native_trust_failure_01.json'
            if not path.exists():job.commit(path,{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0})
            raise
    else:raise ValueError('prepare | run')
