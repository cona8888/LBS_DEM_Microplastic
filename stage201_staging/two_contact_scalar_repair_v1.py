"""Explicit failure-only, stateless two-contact numerical candidate.

No contact law, gap, timestep, tolerance or original successful route changes.
The scalar construction is still experimental until independent qualification.
"""
from contextlib import contextmanager
import time
import numpy as np
import probe_two_contact_scalar_v1 as algebra

NAME = 'stage201_failure_only_two_contact_scalar_v1'
ERRORS = frozenset(('direct contact residual nonconvergence', 'direct contact negative normal force', 'direct contact cone violation'))
telemetry = []


def solve(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter, stop_epoch):
    v,M,J,g=[np.asarray(x,float) for x in (vfree,mobility,jacobian,gaps)]
    if v.shape!=(6,) or M.shape!=(6,6) or J.shape!=(6,6) or g.shape!=(2,):raise ValueError('two-contact six-DOF domain only')
    if not all(np.isfinite(x).all() for x in (v,M,J,g)) or not np.isfinite([dt,friction,tol]).all() or dt<=0 or friction<=0 or tol!=1e-10:raise ValueError('invalid original-law input')
    if not np.allclose(M,M.T,rtol=0,atol=1e-12*np.linalg.norm(M)):raise ValueError('symmetric mobility required')
    np.linalg.cholesky(M)
    if not np.isfinite(stop_epoch) or time.time()>=stop_epoch:raise RuntimeError('diagnostic work cutoff reached')
    s={'vfree':v,'mobility':M,'jacobian':J,'gaps_m':g,'dt_s':dt,'friction':friction}
    reports=algebra.solve_modes(s,stop_epoch)
    for mode in reports:
        for candidate in mode['candidates']:
            if candidate['accepted']:
                health=dict(candidate['health']);health['solver']=NAME
                health.update(scalar_mode_seed=candidate['seed'],scalar_coordinate=candidate['scalar'],stateless_same_system=True,original_gaps_preserved=True)
                return np.asarray(candidate['velocity']),health
    raise RuntimeError('direct contact residual nonconvergence')


@contextmanager
def scope(runtime, enabled=False, stop_epoch=None):
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
                row.update(accepted=True,health=h);return q,h
            except (RuntimeError,ValueError,np.linalg.LinAlgError,FloatingPointError) as failure:
                row['candidate_error']=str(failure);raise error
            finally:
                row['seconds']=time.perf_counter()-started;telemetry.append(row)
    runtime.mixed.solve=repaired
    try:yield
    finally:runtime.mixed.solve=original
