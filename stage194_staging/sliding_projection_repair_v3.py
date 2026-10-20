"""Canonical contact ordering for the original-law failure-only projection.

Sort by the unchanged gap followed by its complete Jacobian block. This only
chooses a deterministic numerical basis; every force is mapped back and judged
against the ORIGINAL ordered system. V1/v2 failed permutation tests remain.
"""
from contextlib import contextmanager
import numpy as np
import sliding_projection_repair_v2 as prior
gate=prior.gate;ERRORS=prior.ERRORS
NAME='stage194_failure_only_sliding_projection_v3'
telemetry=prior.telemetry


def solve(vfree,mobility,jacobian,gaps,dt,friction,tol,maxiter,stop_epoch=None):
    v,M,J,g=[np.asarray(x,float) for x in (vfree,mobility,jacobian,gaps)]
    if J.shape!=(9,6) or g.shape!=(3,):raise ValueError('three-contact six-DOF domain only')
    order=sorted(range(3),key=lambda k:(float(g[k]),*J[3*k:3*k+3].ravel().tolist()))
    indices=[3*k+j for k in order for j in range(3)]
    _,h=prior.solve(v,M,J[indices],g[order],dt,friction,tol,maxiter,stop_epoch)
    f=np.empty(9);f[indices]=np.asarray(h['reactions'])
    A=J@M@J.T;z=J@v
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(3)])
    extras={k:h[k] for k in ('projection_seed_index','projection_nfev','original_gaps_preserved','contact_modes','analytic_projection_jacobian')}
    extras['canonical_order']=order
    return gate._finish(v,M,J,f,z,A,g,dt,friction,steps,h['iterations'],NAME,extras)


@contextmanager
def scope(runtime,enabled=False,stop_epoch=None):
    if type(enabled) is not bool:raise ValueError('explicit Boolean opt-in required')
    if not enabled:yield;return
    original=runtime.mixed.solve
    def repaired(v,M,J,g,dt,mu,tol,maxiter):
        try:return original(v,M,J,g,dt,mu,tol,maxiter)
        except RuntimeError as original_error:
            if str(original_error) not in ERRORS or len(g)!=3:raise
            try:return solve(v,M,J,g,dt,mu,tol,maxiter,stop_epoch)
            except (RuntimeError,ValueError,np.linalg.LinAlgError,FloatingPointError):raise original_error
    runtime.mixed.solve=repaired
    try:yield
    finally:runtime.mixed.solve=original
