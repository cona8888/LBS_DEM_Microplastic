"""Unqualified strict native translation of the existing9-variable trust solve.

Original More/SciPy decisions, tolerances and iteration count are retained.
No fast math or parallel loops. Must pass bit-exact helper/outer tests before
any trajectory; a numerical mismatch rejects this candidate.
"""
from contextlib import contextmanager
from types import SimpleNamespace
import numpy as np
import exact_dense_dispatch_v1 as prior
ROOT,repair,compiled,batch=prior.ROOT,prior.repair,prior.compiled,prior.batch
constant,lsq=prior.constant,prior.lsq
original_trust=prior.trust

@compiled.numba.njit(cache=True,fastmath=False,parallel=False,error_model='numpy')
def sum9(x):
    return ((x[0]+x[1])+(x[2]+x[3]))+((x[4]+x[5])+(x[6]+x[7]))+x[8]

@compiled.numba.njit(cache=True,fastmath=False,parallel=False,error_model='numpy')
def norm9(x):return np.sqrt(x.dot(x))

@compiled.numba.njit(cache=True,fastmath=False,parallel=False,error_model='numpy')
def phi(alpha,suf,s2,suf2,Delta):
    denom=s2+alpha;p_norm=norm9(suf/denom)
    return p_norm-Delta,-sum9(suf2/denom**3)/p_norm

@compiled.numba.njit(cache=True,fastmath=False,parallel=False,error_model='numpy')
def trust9(uf,s,V,Delta,initial_alpha,rtol,max_iter):
    suf=s*uf;s2=s**2;suf2=suf**2
    threshold=np.finfo(np.float64).eps*9*s[0];full_rank=s[-1]>threshold
    if full_rank:
        p=-V.dot(uf/s)
        if norm9(p)<=Delta:return p,0.,0
    alpha_upper=norm9(suf)/Delta
    if full_rank:
        f,fp=phi(0.,suf,s2,suf2,Delta);alpha_lower=-f/fp
    else:alpha_lower=0.
    if initial_alpha is None or not full_rank and initial_alpha==0.:
        alpha=max(.001*alpha_upper,(alpha_lower*alpha_upper)**.5)
    else:alpha=initial_alpha
    it=0
    for it in range(max_iter):
        if alpha<alpha_lower or alpha>alpha_upper:alpha=max(.001*alpha_upper,(alpha_lower*alpha_upper)**.5)
        f,fp=phi(alpha,suf,s2,suf2,Delta)
        if f<0:alpha_upper=alpha
        ratio=f/fp;alpha_lower=max(alpha_lower,alpha-ratio);alpha-=(f+Delta)*ratio/Delta
        if np.abs(f)<rtol*Delta:break
    p=-V.dot(suf/(s2+alpha));p*=Delta/norm9(p)
    return p,alpha,it+1

def trust(n,m,uf,s,V,Delta,initial_alpha=None,rtol=.01,max_iter=10):
    if n==m==9 and all(type(x) is np.ndarray and x.dtype==np.float64 for x in (uf,s,V)) and uf.shape==s.shape==(9,) and V.shape==(9,9):
        return trust9(uf,s,V,Delta,initial_alpha,rtol,max_iter)
    return original_trust(n,m,uf,s,V,Delta,initial_alpha=initial_alpha,rtol=rtol,max_iter=max_iter)

trf_no_bounds=prior.clone(prior.trf_no_bounds,{'solve_lsq_trust_region':trust})
least_squares=prior.clone(prior.least_squares,{'trf':SimpleNamespace(trf_no_bounds=trf_no_bounds)})

@contextmanager
def scope(mode):
    if mode in ('baseline','direct'):
        with prior.scope('baseline' if mode=='baseline' else 'compiled_direct'):yield
    elif mode=='compiled_direct':
        with prior.scope('compiled_direct'):
            old=repair.prior.least_squares;repair.prior.least_squares=least_squares
            try:yield
            finally:repair.prior.least_squares=old
    else:raise ValueError('explicit benchmark mode required')
