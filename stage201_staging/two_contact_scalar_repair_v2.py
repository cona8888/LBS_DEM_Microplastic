"""Same v1 numerics, explicit original mixed-solver failure in returned evidence."""
from contextlib import contextmanager
from types import FunctionType
import time
import numpy as np
import two_contact_scalar_repair_v1 as prior

algebra=prior.algebra;ERRORS=prior.ERRORS
NAME='stage201_failure_only_two_contact_scalar_v2'
solve=FunctionType(prior.solve.__code__,{**prior.solve.__globals__,'NAME':NAME},'solve',prior.solve.__defaults__,prior.solve.__closure__)
telemetry=[]


@contextmanager
def scope(runtime,enabled=False,stop_epoch=None):
    if type(enabled) is not bool:raise ValueError('explicit Boolean opt-in required')
    if not enabled:yield;return
    if stop_epoch is None or not np.isfinite(stop_epoch):raise ValueError('finite diagnostic cutoff required')
    original=runtime.mixed.solve
    def repaired(v,M,J,g,dt,mu,tol,maxiter):
        try:return original(v,M,J,g,dt,mu,tol,maxiter)
        except RuntimeError as error:
            if len(g)!=2 or str(error) not in ERRORS:raise
            started=time.perf_counter();row={'original_error':str(error),'dt_s':float(dt),'accepted':False}
            try:
                q,h=solve(v,M,J,g,dt,mu,tol,maxiter,stop_epoch)
                h.update(original_mixed_error=str(error),original_mixed_solver='stage119_scaled_active_modes')
                row.update(accepted=True,health=h);return q,h
            except (RuntimeError,ValueError,np.linalg.LinAlgError,FloatingPointError) as failure:
                row['candidate_error']=str(failure);raise error
            finally:
                row['seconds']=time.perf_counter()-started;telemetry.append(row)
    runtime.mixed.solve=repaired
    try:yield
    finally:runtime.mixed.solve=original
