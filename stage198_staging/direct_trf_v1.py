"""Private narrow entry to unchanged SciPy TRF, no numerical algorithm edit.

Only the existing dense nine-variable analytic, unbounded, linear-loss contact
call is supported. The original trf_no_bounds code, SVD, trust-region updates,
scaling, tolerances and evaluation limit are retained. Scope is process-local
and restores every binding. Exact held-result and trajectory tests are required.
"""
from pathlib import Path
from contextlib import contextmanager
import importlib, sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage194_staging'),str(ROOT/'stage196_staging')]
import early_semismooth_dispatch_v1 as repair
import constant_analytic_pair_v1 as constant
import compiled_analytic_pair_v3 as compiled
lsq=importlib.import_module('scipy.optimize._lsq.least_squares')
trf=importlib.import_module('scipy.optimize._lsq.trf')
ORIGINAL=repair.prior.least_squares

def least_squares(fun,x0,*,jac,method,xtol,ftol,gtol,max_nfev,x_scale):
    if not (method=='trf' and xtol==ftol==gtol==1e-14 and max_nfev==2000 and x_scale=='jac' and callable(fun) and callable(jac)):
        raise ValueError('outside frozen dense contact optimizer contract')
    if np.iscomplexobj(x0):raise ValueError('real initial state required')
    x=np.atleast_1d(x0).astype(float)
    if x.shape!=(9,) or not np.isfinite(x).all():raise ValueError('finite nine-variable state required')
    # Same transformations as VectorFunction for this already dense float64
    # callback domain. Preserve its initial fun-then-jac evaluation order.
    def f(y):return np.atleast_1d(fun(y))
    def j(y):return np.atleast_2d(jac(y))
    f0=f(x);J0=j(x)
    if f0.shape!=(9,) or J0.shape!=(9,9) or f0.dtype!=np.float64 or J0.dtype!=np.float64 or not np.isfinite(f0).all():
        raise ValueError('outside dense float64 analytic callback contract')
    result=trf.trf_no_bounds(f,j,x,f0,J0,ftol,xtol,gtol,max_nfev,x_scale,None,'exact',{},0,callback=None)
    result.message=lsq.TERMINATION_MESSAGES[result.status];result.success=result.status>0
    return result

@contextmanager
def scope(mode):
    if mode not in ('baseline','direct','compiled_direct'):raise ValueError('explicit qualified mode required')
    original=repair.prior.least_squares
    arithmetic=compiled if mode=='compiled_direct' else constant
    if mode!='baseline':repair.prior.least_squares=least_squares
    try:
        with arithmetic.scope(True):yield
    finally:repair.prior.least_squares=original
