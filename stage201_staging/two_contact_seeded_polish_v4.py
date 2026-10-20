"""Failure-only same-system coordinate refinement, retaining scalar successes."""
from contextlib import contextmanager
from types import FunctionType
import numpy as np
import two_contact_scalar_dispatch_v3 as prior
import probe_two_contact_elimination_v1 as eliminated

algebra=prior.algebra;job,api=algebra.job,algebra.api
NAME='stage201_primary_failure_two_contact_seeded_elimination_v4'
ERRORS=prior.ERRORS;telemetry=prior.telemetry


def input_hash(v,M,J,g,dt,mu):
    return api.digest({'vfree':np.asarray(v).tolist(),'mobility':np.asarray(M).tolist(),'jacobian':np.asarray(J).tolist(),'gaps_m':np.asarray(g).tolist(),'dt_s':float(dt),'friction':float(mu)})


def solve(v,M,J,g,dt,mu,tol,maxiter,stop_epoch):
    try:return prior.solve(v,M,J,g,dt,mu,tol,maxiter,stop_epoch)
    except RuntimeError as error:
        if str(error) not in ERRORS:raise
        original_error=str(error)
    system={'vfree':np.asarray(v),'mobility':np.asarray(M),'jacobian':np.asarray(J),'gaps_m':np.asarray(g),'dt_s':dt,'friction':mu}
    modes=algebra.solve_modes(system,stop_epoch)
    flat=[c for mode in modes for c in mode['candidates']]
    api.require(not any(c['accepted'] for c in flat),'deterministic failed scalar repetition')
    near=[np.asarray(c['force']) for c in sorted(flat,key=lambda c:c['residual'])[:3]]
    reports=eliminated.candidates(system,near,stop_epoch)
    for mode_index,mode in enumerate(reports):
        for c in mode.get('candidates',[]):
            if c['accepted']:
                h=dict(c['health']);h.update(solver=NAME,original_gaps_preserved=True,stateless_same_system=True,
                   scalar_first_error=original_error,seeded_system_sha256=input_hash(v,M,J,g,dt,mu),seed_reactions=[f.tolist() for f in near],
                   elimination_mode_index=mode_index,elimination_seed_index=c['seed'],elimination_nfev=c['nfev'],force_nullspace_width=mode['force_nullspace_width'],velocity_width=mode['velocity_width'])
                return np.asarray(c['velocity']),h
    raise RuntimeError(original_error)


# Identical primary-failure-only dispatch mechanics; only its numerical solve
# binding is replaced. No primary path or success returned by v3 is modified.
generator=prior.scope.__wrapped__
bound=FunctionType(generator.__code__,{**generator.__globals__,'solve':solve},generator.__name__,generator.__defaults__,generator.__closure__)
scope=contextmanager(bound)
