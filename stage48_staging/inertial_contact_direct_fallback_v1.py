"""Direct small-contact fallback for the accepted Stage42 cold Coulomb solver.

Stage42 PGS is always attempted first.  If and only if it reports contact
nonconvergence for at most three contacts, a scaled bounded least-squares solve
targets the same normal complementarity and tangential projection fixed point.
The result is accepted only by the original residual, force-closure, cone and
dissipation checks.  No fallback is defined for larger contact sets.
"""
import sys
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage41_staging"),str(ROOT/"stage42_staging")]
import inertial_contact_cold_optimized_v1 as stage41
import inertial_contact_robust_v1 as stage42

base=stage42.base
generalized_mass_matrix=stage42.generalized_mass_matrix
stokes_generalized_resistance=stage42.stokes_generalized_resistance
contact_model=stage42.contact_model
finite_re=stage42.finite_re
contact_solve=stage42.contact_solve
_standard=stage41._solve_prepared
_stats={"standard_solves":0,"direct_solves":0,"direct_failures":0,"direct_nfev":0}

def stats(): return dict(_stats)

def _projection(force_t, velocity_t, step, limit):
    trial=force_t-velocity_t/step; norm=np.linalg.norm(trial)
    return trial*min(1.,limit/max(norm,1e-300))

def _direct(vfree,mobility,jacobian,gaps,dt,friction,tol,max_nfev=10000):
    vfree=contact_model.finite(vfree); mobility=contact_model.finite(mobility)
    count=len(gaps)
    if count<1 or count>3: raise RuntimeError("direct fallback supports one to three contacts")
    A=jacobian@mobility@jacobian.T; z=jacobian@vfree; scale=max(np.linalg.norm(vfree),1e-15)
    tangent_steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(count)])
    variable_scales=np.empty(3*count)
    for k in range(count):
        variable_scales[3*k]=A[3*k,3*k]; variable_scales[3*k+1:3*k+3]=tangent_steps[k]
    if np.any(variable_scales<=0) or not np.isfinite(variable_scales).all():
        raise RuntimeError("nonpositive direct contact scale")
    def unpack(u): return u/variable_scales
    def equations(u):
        force=unpack(u); velocity=z+A@force; residual=np.empty_like(u)
        for k in range(count):
            i=3*k; normal_velocity=velocity[i]+gaps[k]/dt
            # Fischer--Burmeister equation for u_n >= 0, v_n >= 0, u_n*v_n = 0.
            residual[i]=np.hypot(u[i],normal_velocity)-u[i]-normal_velocity
            projection=_projection(force[i+1:i+3],velocity[i+1:i+3],tangent_steps[k],friction*force[i])
            residual[i+1:i+3]=u[i+1:i+3]-tangent_steps[k]*projection
        return residual/scale
    lower=np.full(3*count,-np.inf); upper=np.full(3*count,np.inf); lower[::3]=0.
    guesses=[np.zeros(3*count)]
    # A frictionless nonnegative least-squares-like seed improves near-singular cases.
    normal_guess=np.zeros(3*count)
    for k in range(count): normal_guess[3*k]=max(0.,-(z[3*k]+gaps[k]/dt))
    guesses.append(normal_guess)
    best=None
    for guess in guesses:
        solved=least_squares(equations,guess,bounds=(lower,upper),xtol=1e-14,ftol=1e-14,gtol=1e-14,
                             max_nfev=max_nfev,x_scale="jac")
        norm=float(np.linalg.norm(equations(solved.x),ord=np.inf))
        if best is None or norm<best[0]: best=(norm,solved)
        if norm<=tol: break
    normalized,best_result=best; force=unpack(best_result.x); velocity=z+A@force
    # Reproduce the accepted Stage41 residual exactly.
    residual=0.
    for k in range(count):
        i=3*k; normal=velocity[i]+gaps[k]/dt
        residual=max(residual,abs(min(A[i,i]*force[i],normal)))
        projection=_projection(force[i+1:i+3],velocity[i+1:i+3],tangent_steps[k],friction*force[i])
        residual=max(residual,np.linalg.norm(force[i+1:i+3]-projection)*tangent_steps[k])
        if force[i]<-1e-14 or np.linalg.norm(force[i+1:i+3])>friction*force[i]+1e-12*max(abs(force[i]),1.):
            raise RuntimeError("direct contact cone violation")
    if residual/scale>tol:
        raise RuntimeError("direct contact residual nonconvergence")
    result=vfree+mobility@jacobian.T@force
    force_residual=np.linalg.norm(np.linalg.solve(mobility,result-vfree)-jacobian.T@force)/max(np.linalg.norm(jacobian.T@force),1e-30)
    tangential_work=sum(float(force[3*k+1:3*k+3]@velocity[3*k+1:3*k+3]) for k in range(count))
    if force_residual>1e-8: raise RuntimeError("direct contact force closure failed")
    if tangential_work>1e-8*max(np.linalg.norm(force)*scale,1e-30): raise RuntimeError("friction generates energy")
    return contact_model.finite(result),{"iterations":int(best_result.nfev),"residual":float(residual/scale),
        "force_residual":float(force_residual),"dissipation":-tangential_work,"reactions":force.tolist(),
        "solver":"direct_scaled_fb_projection","direct_normalized_residual":normalized,
        "direct_success_flag":bool(best_result.success),"direct_message":best_result.message}

def _solve_with_fallback(vfree,mobility,jacobian,gaps,dt,friction,tol,maxiter):
    try:
        answer=_standard(vfree,mobility,jacobian,gaps,dt,friction,tol,maxiter)
        _stats["standard_solves"]+=1; answer[1]["solver"]="standard_cold_pgs"; return answer
    except RuntimeError as exc:
        if str(exc)!="contact nonconvergence": raise
    if len(gaps)>3:
        _stats["direct_failures"]+=1; raise RuntimeError("contact nonconvergence; direct fallback contact limit exceeded")
    try:
        answer=_direct(vfree,mobility,jacobian,gaps,dt,friction,tol)
    except RuntimeError:
        _stats["direct_failures"]+=1; raise
    _stats["direct_solves"]+=1; _stats["direct_nfev"]+=answer[1]["iterations"]; return answer

def inertial_contact_step(*args,**kwargs):
    original=stage41._solve_prepared; stage41._solve_prepared=_solve_with_fallback
    try: return stage42.inertial_contact_step(*args,**kwargs)
    finally: stage41._solve_prepared=original
