"""Unchanged TRF bytecode with exact dense-vector norm dispatch specialization."""
from types import FunctionType, SimpleNamespace
from contextlib import contextmanager
import numpy as np
import direct_trf_v1 as prior
ROOT=prior.ROOT;repair=prior.repair;compiled=prior.compiled;constant=prior.constant;lsq=prior.lsq

def norm(x,ord=None):
    if type(x) is np.ndarray and x.dtype==np.float64 and x.ndim==1:
        if ord is None:
            a=x.ravel(order='K');return np.sqrt(a.dot(a))
        if ord==np.inf:return abs(x).max(axis=(0,),keepdims=False,initial=0)
    return np.linalg.norm(x,ord=ord)

def clone(fn,changes):
    return FunctionType(fn.__code__,{**fn.__globals__,**changes},fn.__name__,fn.__defaults__,fn.__closure__)

trust=clone(prior.trf.solve_lsq_trust_region,{'norm':norm})
trf_no_bounds=clone(prior.trf.trf_no_bounds,{'norm':norm,'solve_lsq_trust_region':trust})
trf=SimpleNamespace(trf_no_bounds=trf_no_bounds)
least_squares=clone(prior.least_squares,{'trf':trf})

@contextmanager
def scope(mode):
    if mode not in ('baseline','direct','compiled_direct'):raise ValueError('explicit mode required')
    original=repair.prior.least_squares;arithmetic=compiled if mode=='compiled_direct' else constant
    if mode!='baseline':repair.prior.least_squares=least_squares
    try:
        with arithmetic.scope(True):yield
    finally:repair.prior.least_squares=original
