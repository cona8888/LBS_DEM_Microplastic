"""Explicit frozen-domain guard around the bit-exact native trust candidate."""
from contextlib import contextmanager
from types import SimpleNamespace
import numpy as np
import native_trust_candidate_v2 as previous
prior=previous.prior
ROOT,repair,compiled,batch=prior.ROOT,prior.repair,prior.compiled,prior.batch
constant,lsq=prior.constant,prior.lsq
original_trust=previous.original_trust
trust9=previous.trust9

def trust(n,m,uf,s,V,Delta,initial_alpha=None,rtol=.01,max_iter=10):
    if rtol!=.01 or max_iter!=10 or not np.isfinite(Delta) or Delta<=0:
        return original_trust(n,m,uf,s,V,Delta,initial_alpha=initial_alpha,rtol=rtol,max_iter=max_iter)
    return previous.trust(n,m,uf,s,V,Delta,initial_alpha=initial_alpha,rtol=rtol,max_iter=max_iter)

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
