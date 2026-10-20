"""Stage50 solver plus a deterministic zero-seeded LM recovery.

The accepted cold-PGS/PGS-seeded-LM path runs first.  Only if its direct
residual gate fails for <=3 contacts is the identical scaled system solved from
zero.  The Stage50 original residual, cone, closure and dissipation checks make
the final acceptance decision.
"""
import sys
from pathlib import Path
import numpy as np
from scipy.optimize import root
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage41_staging"),str(ROOT/"stage42_staging"),str(ROOT/"stage50_staging")]
import inertial_contact_cold_optimized_v1 as s41
import inertial_contact_robust_v1 as s42
import inertial_contact_seeded_lm_v1 as s50
base=s42.base; generalized_mass_matrix=s42.generalized_mass_matrix; stokes_generalized_resistance=s42.stokes_generalized_resistance
contact_model=s42.contact_model; finite_re=s42.finite_re; contact_solve=s42.contact_solve
_stats={"primary_solves":0,"zero_lm_solves":0,"zero_lm_failures":0,"zero_lm_nfev":0}
def stats(): return dict(_stats)
def _solve(vfree,mobility,jacobian,gaps,dt,friction,tol,maxiter):
    try:
        answer=s50._solve(vfree,mobility,jacobian,gaps,dt,friction,tol,maxiter); _stats["primary_solves"]+=1; return answer
    except RuntimeError as exc:
        if str(exc)!="direct contact residual nonconvergence": raise
    if len(gaps)>3:
        _stats["zero_lm_failures"]+=1; raise RuntimeError("zero-seeded LM contact limit exceeded")
    vfree=contact_model.finite(vfree); mobility=contact_model.finite(mobility); A=jacobian@mobility@jacobian.T; z=jacobian@vfree
    scale=max(np.linalg.norm(vfree),1e-15); steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(len(gaps))])
    scales=np.repeat(steps,3)
    for k in range(len(gaps)): scales[3*k]=A[3*k,3*k]
    if np.any(scales<=0) or not np.isfinite(scales).all():
        _stats["zero_lm_failures"]+=1; raise RuntimeError("nonpositive zero-LM contact scale")
    def equations(u):
        force=u/scales; velocity=z+A@force; result=np.empty_like(u)
        for k in range(len(gaps)):
            i=3*k; vn=velocity[i]+gaps[k]/dt; result[i]=np.hypot(u[i],vn)-u[i]-vn
            result[i+1:i+3]=u[i+1:i+3]-steps[k]*s50._project(force[i+1:i+3],velocity[i+1:i+3],steps[k],friction*force[i])
        return result/scale
    solved=root(equations,np.zeros(len(z)),method="lm",options={"ftol":1e-14,"xtol":1e-14,"gtol":1e-14,"maxiter":50000})
    force=solved.x/scales
    try:
        answer=s50._finish(vfree,mobility,jacobian,force,z,A,gaps,dt,friction,steps,maxiter+int(solved.nfev),
            "cold_pgs_then_zero_seeded_scaled_lm",{"pgs_seed_iterations":maxiter,"zero_lm_nfev":int(solved.nfev),
            "zero_lm_success_flag":bool(solved.success),"zero_lm_message":str(solved.message)})
    except RuntimeError:
        _stats["zero_lm_failures"]+=1; raise
    _stats["zero_lm_solves"]+=1; _stats["zero_lm_nfev"]+=int(solved.nfev); return answer
def inertial_contact_step(*args,**kwargs):
    original=s41._solve_prepared; s41._solve_prepared=_solve
    try: return s42.inertial_contact_step(*args,**kwargs)
    finally: s41._solve_prepared=original
