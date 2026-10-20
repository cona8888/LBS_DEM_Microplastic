"""Stateless all-sliding candidate before the expensive general fallback.

Installed OUTSIDE the unchanged Stage169 scope: every original primary and
reduced success retains priority. Only after both fail can this three-contact,
nearly-closed, certified near-rest candidate return. Every candidate uses the
unchanged original-law final gate. No state or force is cached between poses.
The ordering relative to the general fallback changes; this is not a promise
of bitwise identity for every possible general-fallback success.
"""
from contextlib import contextmanager
import time
import numpy as np
import sliding_projection_repair_v3 as projection
NAME=projection.NAME
ERRORS=projection.ERRORS
solve=projection.solve

@contextmanager
def scope(runtime,enabled=False,stop_epoch=None):
    if type(enabled) is not bool:raise ValueError('explicit Boolean opt-in required')
    if not enabled:yield;return
    if stop_epoch is None or not np.isfinite(stop_epoch):raise ValueError('explicit finite work deadline required')
    with projection.scope(runtime,True,stop_epoch):
        original=runtime.mixed.solve
        def preferred(v,M,J,g,dt,mu,tol,maxiter):
            if time.time()>=stop_epoch:raise RuntimeError('diagnostic work cutoff reached')
            scale=max(np.linalg.norm(v),1e-15)
            eligible=len(g)==3 and mu>0 and dt>0 and tol==1e-10 and np.max(np.abs(g))/dt<=1e-5*scale
            if eligible:
                try:
                    answer=projection.solve(v,M,J,g,dt,mu,tol,maxiter,stop_epoch)
                    if np.linalg.norm(answer[0])/scale<=1e-4:return answer
                except (RuntimeError,ValueError,np.linalg.LinAlgError,FloatingPointError):pass
            return original(v,M,J,g,dt,mu,tol,maxiter)
        runtime.mixed.solve=preferred
        try:yield
        finally:runtime.mixed.solve=original
