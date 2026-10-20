"""Stage53 default with gated, deterministic small-contact recovery.

The portfolio is active only after the trajectory explicitly enters a
time-step recovery episode. Its nonlinear candidates solve the same scaled
complementarity equations as Stage50 and pass through the original Stage50
force, cone, residual, closure and dissipation gates. No optimizer flag alone
can accept a reaction. The final fallback is unchanged Stage53.
"""
import sys
import warnings
from pathlib import Path

import numpy as np
from scipy.optimize import root

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage41_staging"),str(ROOT/"stage42_staging"),
              str(ROOT/"stage50_staging"),str(ROOT/"stage53_staging"),
              str(ROOT/"stage63_staging")]
import inertial_contact_cold_optimized_v1 as s41
import inertial_contact_robust_v1 as s42
import inertial_contact_seeded_lm_v1 as s50
import inertial_contact_multistart_lm_v1 as s53
import inertial_contact_projected_sor_v1 as s63

base=s42.base
generalized_mass_matrix=s42.generalized_mass_matrix
stokes_generalized_resistance=s42.stokes_generalized_resistance
contact_model=s42.contact_model
finite_re=s42.finite_re
contact_solve=s42.contact_solve
_recovery=False
_stats={"default_stage53_calls":0,"krylov_attempts":0,"krylov_accepts":0,
        "diagbroyden_attempts":0,"diagbroyden_accepts":0,
        "projected_sor_attempts":0,"projected_sor_accepts":0,
        "stage53_recovery_fallbacks":0,"recovery_failures":0}


def set_recovery_mode(value):
    global _recovery
    _recovery=bool(value)


def recovery_mode():
    return _recovery


def stats():
    return dict(_stats)


def _root_candidate(method,vfree,mobility,jacobian,gaps,dt,friction,tol,maxiter):
    vfree=contact_model.finite(vfree)
    mobility=contact_model.finite(mobility)
    A=jacobian@mobility@jacobian.T
    z=jacobian@vfree
    scale=max(np.linalg.norm(vfree),1e-15)
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max()
                    for k in range(len(gaps))])
    scales=np.repeat(steps,3)
    for k in range(len(gaps)):
        scales[3*k]=A[3*k,3*k]
    if not np.isfinite(scales).all() or np.any(scales<=0):
        raise RuntimeError("nonpositive direct contact scale")

    def equations(u):
        force=u/scales
        velocity=z+A@force
        residual=np.empty_like(u)
        for k in range(len(gaps)):
            i=3*k
            vn=velocity[i]+gaps[k]/dt
            residual[i]=np.hypot(u[i],vn)-u[i]-vn
            residual[i+1:i+3]=u[i+1:i+3]-steps[k]*s50._project(
                force[i+1:i+3],velocity[i+1:i+3],steps[k],friction*force[i])
        return residual/scale

    iteration_cap=1000 if method=="krylov" else 2000
    with warnings.catch_warnings():
        warnings.simplefilter("ignore",RuntimeWarning)
        solved=root(equations,np.zeros(len(z)),method=method,
                    options={"maxiter":iteration_cap,"fatol":1e-12})
    force=solved.x/scales
    if not np.isfinite(force).all():
        raise RuntimeError("nonfinite direct contact reaction")
    # The unchanged Stage50 physical gates, not solved.success, decide.
    return s50._finish(vfree,mobility,jacobian,force,z,A,gaps,dt,friction,
                       steps,int(getattr(solved,"nfev",0)),
                       f"recovery_{method}",
                       {"root_nfev":int(getattr(solved,"nfev",0)),
                        "root_success_flag":bool(solved.success)})


def _solve(vfree,mobility,jacobian,gaps,dt,friction,tol,maxiter):
    if not _recovery:
        _stats["default_stage53_calls"]+=1
        return s53._solve(vfree,mobility,jacobian,gaps,dt,friction,tol,maxiter)
    if 0<len(gaps)<=3:
        for method in ("krylov","diagbroyden"):
            _stats[f"{method}_attempts"]+=1
            try:
                answer=_root_candidate(method,vfree,mobility,jacobian,gaps,dt,
                                       friction,tol,maxiter)
            except (ValueError,RuntimeError,FloatingPointError,
                    np.linalg.LinAlgError,OverflowError):
                continue
            _stats[f"{method}_accepts"]+=1
            return answer
        _stats["projected_sor_attempts"]+=1
        try:
            answer=s63._solve(vfree,mobility,jacobian,gaps,dt,friction,tol,maxiter)
        except (ValueError,RuntimeError,FloatingPointError,np.linalg.LinAlgError):
            pass
        else:
            _stats["projected_sor_accepts"]+=1
            return answer
    try:
        answer=s53._solve(vfree,mobility,jacobian,gaps,dt,friction,tol,maxiter)
    except (ValueError,RuntimeError,FloatingPointError,np.linalg.LinAlgError):
        _stats["recovery_failures"]+=1
        raise
    _stats["stage53_recovery_fallbacks"]+=1
    return answer


def inertial_contact_step(*args,**kwargs):
    original=s41._solve_prepared
    s41._solve_prepared=_solve
    try:
        return s42.inertial_contact_step(*args,**kwargs)
    finally:
        s41._solve_prepared=original
