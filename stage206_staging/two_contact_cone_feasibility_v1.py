"""Failure-only candidate feasibility retraction; all original gates retained.

Only after the qualified v4 solve fails, repeat its deterministic search with
a bounded tangential trial-force projection. The unchanged finalizer must
accept the new force; an optimizer result or projection is never acceptance.
Successful v4 returns remain untouched, including object/value identity.
"""
from contextlib import contextmanager
from types import FunctionType
import time
import numpy as np
import two_contact_seeded_polish_v4 as prior

NAME='stage206_failure_only_two_contact_cone_feasibility_v1'
ERRORS=prior.ERRORS
MAX_RELATIVE_RETRACTION=1e-10
telemetry=prior.telemetry
input_hash=prior.input_hash

def solve(v,M,J,g,dt,mu,tol,maxiter,stop_epoch):
    try:return prior.solve(v,M,J,g,dt,mu,tol,maxiter,stop_epoch)
    except RuntimeError as error:
        if str(error) not in ERRORS:raise
        first_error=str(error)
    v,M,J,g=[np.asarray(x,float) for x in (v,M,J,g)]
    if v.shape!=(6,) or M.shape!=(6,6) or J.shape!=(6,6) or g.shape!=(2,) or tol!=1e-10:
        raise ValueError('original two-contact six-DOF domain and tolerance required')
    if not all(np.isfinite(x).all() for x in (v,M,J,g)) or not np.isfinite([dt,mu,tol,stop_epoch]).all() or dt<=0 or mu<=0:
        raise ValueError('finite original inputs required')
    if time.time()>=stop_epoch:raise RuntimeError('diagnostic work cutoff reached')
    gate=prior.algebra.job.fast.gate;finish=gate._finish
    def retract(*args):
        try:return finish(*args)
        except RuntimeError as error:
            if str(error)!='direct contact cone violation':raise
        vv,MM,JJ,force,z,A,gg,dtt,friction,steps,it,method,extra=args
        original=np.asarray(force,float);projected=original.copy()
        if original.shape!=(6,) or not np.isfinite(original).all() or np.any(original[::3]<0):
            raise RuntimeError('direct contact cone violation')
        for k in range(2):
            i=3*k;radius=friction*original[i];length=np.linalg.norm(original[i+1:i+3])
            if length>radius:projected[i+1:i+3]*=radius/length
        delta=float(np.linalg.norm(projected-original)/max(np.linalg.norm(original),1e-30))
        if not 0<delta<=MAX_RELATIVE_RETRACTION:raise RuntimeError('direct contact cone violation')
        evidence={**extra,'cone_feasibility_projection':True,'unmodified_v4_failure':first_error,
                  'cone_trial_method':method,'cone_trial_reactions':original.tolist(),
                  'cone_relative_force_retraction':delta,'cone_retraction_limit':MAX_RELATIVE_RETRACTION,
                  'cone_system_sha256':input_hash(vv,MM,JJ,gg,dtt,friction),
                  'original_gaps_preserved':True,'stateless_same_system':True}
        return finish(vv,MM,JJ,projected,z,A,gg,dtt,friction,steps,it,method,evidence)
    gate._finish=retract
    try:
        q,h=prior.solve(v,M,J,g,dt,mu,tol,maxiter,stop_epoch)
    finally:gate._finish=finish
    if h.get('cone_feasibility_projection') is not True:
        raise RuntimeError('unproven cone-feasibility route')
    h=dict(h);h['pre_retraction_solver']=h['solver'];h['solver']=NAME
    return q,h

# The exact existing primary-failure dispatch is retained. Only solve binding
# changes in this new version; the frozen v4 module remains unmodified.
generator=prior.bound
bound=FunctionType(generator.__code__,{**generator.__globals__,'solve':solve},generator.__name__,generator.__defaults__,generator.__closure__)
scope=contextmanager(bound)
