"""Fail-closed zero-step intermediate-array checks before any full replay."""
from pathlib import Path
import sys,traceback
import numpy as np
import native_batch_candidate_v1 as candidate
import qualify_dense_dispatch_v1 as prior
api,job,WORK=prior.api,prior.job,prior.WORK
DESIGN=WORK.with_name('native_batch_helpers_01.json');OUT=prior.OUT.with_name('native_batch_helpers_01')

def verify(p):
    api.require(p['binding']==api.digest({k:v for k,v in p.items() if k!='binding'}),'immutable helper protocol')
    api.verify_mapping(p['sources']);api.verify_mapping(p['inputs'])
    api.require(job.utc()<job.policy.utc(api.read(WORK)['work_end_utc']),'work cutoff')

def prepare():
    p=api.read(prior.DESIGN);prior.ns['verify'](p)
    d={'stage':'Stage199 native scalar-batch preparation screening','new_trajectory_steps':0,'seed':19909,'matrices':300,
       'criterion':'Exact E,H,rhs,determinant bits for every intermediate. Reject any mismatch, no tolerance change. Original scan/root/budget/physical gates retained.',
       'sources':{**p['sources'],**{str(x):api.sha(x) for x in (Path(__file__),Path(candidate.__file__))}},'inputs':{**p['inputs'],str(WORK):api.sha(WORK)},'production_authorized':False}
    d['binding']=api.digest(d);job.commit(DESIGN,d);verify(d);print('NATIVE_BATCH_HELPER_PROTOCOL',api.sha(DESIGN),flush=True)

def reference(beta,q0,direction,J,stick,mu,vs,v,B,fs):
    q=q0[None,:]+beta[:,None]*direction;w=q@J.T
    E,valid=candidate.equation_arrays(w,stick,mu)
    H=J.T@E;rhs=((vs*q-v)@B.T)/fs
    determinant=candidate.prior.determinant(np.concatenate((H,rhs[:,:,None]),axis=2));determinant[~valid]=np.nan
    return determinant,E,H,rhs

def run():
    p=api.read(DESIGN);verify(p);OUT.mkdir(parents=True,exist_ok=False);rng=np.random.default_rng(p['seed']);count=0
    try:
        for i in range(p['matrices']):
            n=(1,17,257)[i%3];beta=rng.normal(size=n);q0=rng.normal(size=6);direction=rng.normal(size=6);J=rng.normal(size=(9,6));v=rng.normal(size=6);M=rng.normal(size=(6,6));B=M@M.T+np.eye(6);vs=.01;fs=.03
            for stick in range(3):
                args=(beta,q0,direction,J,stick,.3,vs,v,B,fs);a=reference(*args);b=candidate.batch_body(*args)
                exact=[x.tobytes()==y.tobytes() for x,y in zip(a,b)]
                if not all(exact):
                    job.commit(OUT/'mismatch.json',{'new_trajectory_steps':0,'matrix':i,'stick':stick,'exact':dict(zip(('det','E','H','rhs'),exact)),'maximum_differences':[float(np.nanmax(np.abs(x-y))) for x,y in zip(a,b)],'args':[x.tolist() if isinstance(x,np.ndarray) else x for x in args],'protocol_sha256':api.sha(DESIGN)})
                api.require(all(exact),'original intermediate arrays and determinant exactly preserved');count+=1
        verify(p);job.commit(OUT/'results.json',{'passed':True,'new_trajectory_steps':0,'exact_intermediate_tests':count,'protocol_sha256':api.sha(DESIGN),'production_authorized':False});job.commit(OUT/'completion.json',{'results_sha256':api.sha(OUT/'results.json')});print('BATCH_HELPERS_EXACT',count,flush=True)
    except Exception as e:
        job.commit(OUT/'failure.json',{'error':repr(e),'traceback':traceback.format_exc(),'new_trajectory_steps':0,'completed_checks':count});raise

if __name__=='__main__':
    if sys.argv[1:]==['prepare']:prepare()
    elif sys.argv[1:]==['run']:run()
    else:raise ValueError('prepare | run')
