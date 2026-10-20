"""Zero-step primitive trace of the newly observed native mismatch."""
from pathlib import Path
from types import FunctionType
import numpy as np
import native_trust_candidate_v2 as c
import diagnose_native_prefix_v1 as d

def trace(uf,s,V,Delta,alpha):
    suf=s*uf;s2=s**2;suf2=suf**2
    upper=c.norm9(suf)/Delta
    f,fp=c.phi(0.,suf,s2,suf2,Delta);lower=-f/fp
    rows=np.full((11,8),np.nan)
    rows[0,:4]=np.array([upper,lower,(lower*upper)**.5,alpha])
    for i in range(10):
        if alpha<lower or alpha>upper:alpha=max(.001*upper,(lower*upper)**.5)
        f,fp=c.phi(alpha,suf,s2,suf2,Delta)
        rows[i+1,:4]=np.array([alpha,f,fp,lower])
        if f<0:upper=alpha
        ratio=f/fp;lower=max(lower,alpha-ratio);alpha-=(f+Delta)*ratio/Delta
        rows[i+1,4:]=np.array([ratio,lower,alpha,upper])
        if np.abs(f)<.01*Delta:break
    return rows

def phi(alpha,suf,s2,suf2,Delta):
    denom=s2+alpha;n=np.sqrt((suf/denom).dot(suf/denom))
    return n-Delta,-np.sum(suf2/denom**3)/n

if __name__=='__main__':
    d.api.require(d.job.utc()<d.job.policy.utc(d.api.read(d.probe.WORK)['work_end_utc']),'work cutoff')
    path=d.OUT/'results.json';r=d.api.read(path);m=r['trust_mismatches'][0]
    args=m['args'];uf,s,V=map(np.asarray,args[2:5]);Delta=args[5];alpha=m['kwargs']['initial_alpha']
    from types import SimpleNamespace
    py=FunctionType(trace.__code__,{**globals(),'c':SimpleNamespace(norm9=lambda x:np.sqrt(x.dot(x)),phi=phi)})
    native=c.compiled.numba.njit(trace,cache=True,fastmath=False,parallel=False,error_model='numpy')
    a=py(uf,s,V,Delta,alpha);b=native(uf,s,V,Delta,alpha)
    diffs=[{'iteration_row':int(i),'field':int(j),'expected':float(a[i,j]),'actual':float(b[i,j])} for i,j in zip(*np.where((a!=b)&~(np.isnan(a)&np.isnan(b))))]
    result={'new_trajectory_steps':0,'differences':diffs,'input_sha256':d.api.sha(path),'source_sha256':d.api.sha(__file__)}
    d.job.commit(d.OUT/'primitive_iterations.json',result);print('ITERATION_DIFFERENCES',diffs[:10],flush=True)
