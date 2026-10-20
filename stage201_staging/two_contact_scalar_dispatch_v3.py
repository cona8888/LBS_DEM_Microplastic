"""Experimental numerical ordering after the unchanged primary solve fails.

The runtime invokes mixed.solve only after an allowed primary failure. The
independent audit requires that captured failure and the original reduced
three-contact exclusion. Original mixed search remains a backup. No primary
success, equation, gap, timestep or acceptance tolerance is modified.
"""
from contextlib import contextmanager
from types import FunctionType
import time
import numpy as np
import two_contact_scalar_repair_v2 as prior

algebra=prior.algebra;ERRORS=prior.ERRORS
NAME='stage201_primary_failure_two_contact_scalar_v3'
solve=FunctionType(prior.solve.__code__,{**prior.solve.__globals__,'NAME':NAME},'solve',prior.solve.__defaults__,prior.solve.__closure__)
telemetry=[]


@contextmanager
def scope(runtime,enabled=False,stop_epoch=None):
    if type(enabled) is not bool:raise ValueError('explicit Boolean opt-in required')
    if not enabled:yield;return
    if stop_epoch is None or not np.isfinite(stop_epoch):raise ValueError('finite work cutoff required')
    original=runtime.mixed.solve
    def dispatch(v,M,J,g,dt,mu,tol,maxiter):
        if len(g)!=2:return original(v,M,J,g,dt,mu,tol,maxiter)
        started=time.perf_counter();row={'dt_s':float(dt),'accepted':False,'original_mixed_attempted':False}
        try:
            q,h=solve(v,M,J,g,dt,mu,tol,maxiter,stop_epoch)
            h.update(scalar_dispatch_policy='after_original_primary_failure',original_mixed_attempted=False)
            row.update(accepted=True,health=h);return q,h
        except (RuntimeError,ValueError,np.linalg.LinAlgError,FloatingPointError) as error:
            row.update(candidate_error=str(error),original_mixed_attempted=True)
            return original(v,M,J,g,dt,mu,tol,maxiter)
        finally:row['seconds']=time.perf_counter()-started;telemetry.append(row)
    runtime.mixed.solve=dispatch
    try:yield
    finally:runtime.mixed.solve=original
