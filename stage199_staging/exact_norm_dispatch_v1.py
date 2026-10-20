"""Private exact dense-vector norm dispatch in the known contact call graph.

No global NumPy mutation. Cloned functions retain their complete code objects,
all gates and all arguments. Inputs outside the narrow domain use NumPy.
"""
from contextlib import contextmanager
from types import FunctionType,SimpleNamespace
import numpy as np
import exact_trf_helpers_v1 as prior
ROOT,repair,compiled,batch=prior.ROOT,prior.repair,prior.compiled,prior.batch
constant,lsq=prior.constant,prior.lsq
trf_no_bounds,least_squares=prior.trf_no_bounds,prior.least_squares
original_norm=np.linalg.norm

def norm(x,ord=None,axis=None,keepdims=False):
    if ord is None and axis is None and keepdims is False and type(x) is np.ndarray and x.dtype==np.float64 and x.ndim==1:
        a=x.ravel(order='K');return np.sqrt(a.dot(a))
    return original_norm(x,ord=ord,axis=axis,keepdims=keepdims)

np_private=SimpleNamespace(**vars(np));np_private.linalg=SimpleNamespace(**vars(np.linalg));np_private.linalg.norm=norm
def clone(fn):
    if fn.__globals__.get('np') is not np:raise RuntimeError('unexpected original NumPy binding')
    return FunctionType(fn.__code__,{**fn.__globals__,'np':np_private},fn.__name__,fn.__defaults__,fn.__closure__)

@contextmanager
def scope(mode):
    if mode in ('baseline','direct'):
        with prior.scope('baseline' if mode=='baseline' else 'compiled_direct'):yield
    elif mode=='compiled_direct':
        with prior.scope('compiled_direct'):
            fast=batch.original
            targets=[(fast,'scalar_solve'),(fast,'solve'),(fast.old,'constrained_stick'),(fast.gate,'_finish'),(fast.gate,'_residual'),(repair.prior,'solve')]
            saved=[]
            try:
                for module,name in targets:
                    fn=getattr(module,name);saved.append((module,name,fn));setattr(module,name,clone(fn))
                system=repair.prior.analytic.system;saved.append((repair.prior.analytic,'system',system));repair.prior.analytic.system=clone(system)
                yield
            finally:
                for module,name,fn in reversed(saved):setattr(module,name,fn)
    else:raise ValueError('explicit benchmark mode required')
