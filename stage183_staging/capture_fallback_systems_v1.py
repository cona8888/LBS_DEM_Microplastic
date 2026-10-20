"""Opt-in diagnostic observer: preserves the exact fallback solver return.

Enter INSIDE the qualified contact scope. No solver replacement, catch/retry,
force selection or physical state is introduced. Each input and result is
copied for evidence; the original returned tuple is returned unchanged.
"""
from contextlib import contextmanager
import copy,time
import numpy as np
records=[]


@contextmanager
def scope(runtime,enabled=False):
    if type(enabled) is not bool:raise ValueError('explicit Boolean diagnostic mode required')
    if not enabled:yield;return
    original=runtime.mixed.solve
    def observed(v,M,J,g,dt,mu,tol,maxiter):
        start=time.perf_counter()
        row={'vfree':np.asarray(v).tolist(),'mobility':np.asarray(M).tolist(),'jacobian':np.asarray(J).tolist(),
             'gaps_m':np.asarray(g).tolist(),'dt_s':float(dt),'friction':float(mu),'tolerance':float(tol),'maxiter':int(maxiter)}
        try:
            result=original(v,M,J,g,dt,mu,tol,maxiter)
            row.update(accepted=True,velocity=np.asarray(result[0]).tolist(),health=copy.deepcopy(result[1]))
            return result
        except Exception as error:
            row.update(accepted=False,error=repr(error));raise
        finally:
            row['wall_s']=time.perf_counter()-start;records.append(row)
    runtime.mixed.solve=observed
    try:yield
    finally:runtime.mixed.solve=original
