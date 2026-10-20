"""Same SciPy TRF/LAPACK algorithms with fixed-size dispatch preparation."""
from pathlib import Path
from types import SimpleNamespace
from contextlib import contextmanager
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage198_staging'),str(ROOT/'stage194_staging')]
import direct_trf_v2 as prior
import exact_batch_arrays_v1 as batch
import numpy as np
from scipy.linalg.lapack import get_lapack_funcs,_compute_lwork
repair,compiled,constant,lsq=prior.repair,prior.compiled,prior.constant,prior.lsq
lapack,workquery=get_lapack_funcs(('gesdd','gesdd_lwork'),(np.zeros((9,9)),),ilp64='preferred')
worksize=_compute_lwork(workquery,9,9,compute_uv=True,full_matrices=False)
original_svd=prior.prior.trf.svd

def svd(a,full_matrices=True):
    if not (type(a) is np.ndarray and a.dtype==np.float64 and a.shape==(9,9) and full_matrices is False):
        return original_svd(a,full_matrices=full_matrices)
    if not np.isfinite(a).all():raise ValueError('array must not contain infs or NaNs')
    u,s,v,info=lapack(a,compute_uv=True,lwork=worksize,full_matrices=False,overwrite_a=False)
    if info>0:raise np.linalg.LinAlgError('SVD did not converge')
    if info<0:
        if info==-4:raise ValueError('A has a NaN entry')
        raise ValueError(f'illegal value in {-info}th argument of internal gesdd')
    return u,s,v

trf_no_bounds=prior.clone(prior.trf_no_bounds,{'svd':svd})
trf=SimpleNamespace(trf_no_bounds=trf_no_bounds)
least_squares=prior.clone(prior.least_squares,{'trf':trf})

@contextmanager
def scope(mode):
    if mode=='baseline':
        with prior.scope('baseline'):yield
    elif mode=='direct':
        with prior.scope('compiled_direct'):yield
    elif mode=='compiled_direct':
        saved=repair.prior.least_squares;repair.prior.least_squares=least_squares
        try:
            with compiled.scope(True),batch.scope():yield
        finally:repair.prior.least_squares=saved
    else:raise ValueError('explicit benchmark mode required')
