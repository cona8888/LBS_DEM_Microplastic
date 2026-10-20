"""Stage42 cold PGS with a seeded direct LM fallback for <=3 contacts.

The PGS loop is identical to Stage41/42 and retains its terminal cone-feasible
iterate if the residual ceiling is not met.  A scaled Levenberg--Marquardt solve
then targets the same complementarity/projection equations.  Its solution is
accepted only if normal forces, Coulomb cones, original residual, force closure
and dissipation all pass.  Larger contact sets fail closed.
"""
import sys
from pathlib import Path
import numpy as np
from scipy.optimize import root
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage41_staging"),str(ROOT/"stage42_staging")]
import inertial_contact_cold_optimized_v1 as s41
import inertial_contact_robust_v1 as s42
base=s42.base; generalized_mass_matrix=s42.generalized_mass_matrix; stokes_generalized_resistance=s42.stokes_generalized_resistance
contact_model=s42.contact_model; finite_re=s42.finite_re; contact_solve=s42.contact_solve
_stats={"standard_solves":0,"lm_solves":0,"lm_failures":0,"lm_nfev":0,"pgs_seed_iterations":0}
def stats(): return dict(_stats)
def _project(ft,vt,step,limit):
    trial=ft-vt/step; return trial*min(1.,limit/max(np.linalg.norm(trial),1e-300))
def _residual(force,z,A,gaps,dt,friction,steps):
    velocity=z+A@force; value=0.
    for k in range(len(gaps)):
        i=3*k; value=max(value,abs(min(A[i,i]*force[i],velocity[i]+gaps[k]/dt)))
        value=max(value,np.linalg.norm(force[i+1:i+3]-_project(force[i+1:i+3],velocity[i+1:i+3],steps[k],friction*force[i]))*steps[k])
    return value
def _finish(vfree,mobility,jacobian,force,z,A,gaps,dt,friction,steps,iterations,solver,extra):
    velocity_contact=z+A@force; scale=max(np.linalg.norm(vfree),1e-15); residual=_residual(force,z,A,gaps,dt,friction,steps)
    if np.any(force[::3]<0): raise RuntimeError("direct contact negative normal force")
    for k in range(len(gaps)):
        i=3*k
        if np.linalg.norm(force[i+1:i+3])>friction*force[i]+1e-12*max(np.linalg.norm(force),1e-30):
            raise RuntimeError("direct contact cone violation")
    if residual/scale>1e-10: raise RuntimeError("direct contact residual nonconvergence")
    velocity=vfree+mobility@jacobian.T@force
    closure=np.linalg.norm(np.linalg.solve(mobility,velocity-vfree)-jacobian.T@force)/max(np.linalg.norm(jacobian.T@force),1e-30)
    work=sum(float(force[3*k+1:3*k+3]@velocity_contact[3*k+1:3*k+3]) for k in range(len(gaps)))
    if closure>1e-8: raise RuntimeError("direct contact force closure failed")
    if work>1e-8*max(np.linalg.norm(force)*scale,1e-30): raise RuntimeError("friction generates energy")
    health={"iterations":iterations,"residual":float(residual/scale),"force_residual":float(closure),
        "dissipation":-work,"reactions":force.tolist(),"solver":solver}; health.update(extra)
    return contact_model.finite(velocity),health
def _solve(vfree,mobility,jacobian,gaps,dt,friction,tol,maxiter):
    vfree=contact_model.finite(vfree); mobility=contact_model.finite(mobility)
    if not len(gaps):
        _stats["standard_solves"]+=1
        return vfree,{"iterations":0,"residual":0.,"force_residual":0.,"dissipation":0.,"reactions":[],"solver":"standard_cold_pgs"}
    A=jacobian@mobility@jacobian.T; z=jacobian@vfree; force=np.zeros(len(z)); scale=max(np.linalg.norm(vfree),1e-15)
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(len(gaps))])
    for iteration in range(maxiter):
        for k in range(len(gaps)):
            i=3*k; vn=z[i]+A[i]@force+gaps[k]/dt; force[i]=max(0.,force[i]-vn/A[i,i]); vt=z[i+1:i+3]+A[i+1:i+3]@force
            force[i+1:i+3]=_project(force[i+1:i+3],vt,steps[k],friction*force[i])
        if _residual(force,z,A,gaps,dt,friction,steps)/scale<=tol:
            _stats["standard_solves"]+=1
            return _finish(vfree,mobility,jacobian,force,z,A,gaps,dt,friction,steps,iteration+1,"standard_cold_pgs",{})
    if len(gaps)>3:
        _stats["lm_failures"]+=1; raise RuntimeError("contact nonconvergence; seeded LM contact limit exceeded")
    scales=np.repeat(steps,3)
    for k in range(len(gaps)): scales[3*k]=A[3*k,3*k]
    if np.any(scales<=0) or not np.isfinite(scales).all():
        _stats["lm_failures"]+=1; raise RuntimeError("nonpositive direct contact scale")
    def equations(u):
        f=u/scales; velocity=z+A@f; result=np.empty_like(u)
        for k in range(len(gaps)):
            i=3*k; vn=velocity[i]+gaps[k]/dt; result[i]=np.hypot(u[i],vn)-u[i]-vn
            result[i+1:i+3]=u[i+1:i+3]-steps[k]*_project(f[i+1:i+3],velocity[i+1:i+3],steps[k],friction*f[i])
        return result/scale
    solved=root(equations,force*scales,method="lm",options={"ftol":1e-14,"xtol":1e-14,"gtol":1e-14,"maxiter":50000})
    trial=solved.x/scales
    try:
        answer=_finish(vfree,mobility,jacobian,trial,z,A,gaps,dt,friction,steps,maxiter+int(solved.nfev),
            "cold_pgs_seeded_scaled_lm",{"pgs_seed_iterations":maxiter,"lm_nfev":int(solved.nfev),
            "lm_success_flag":bool(solved.success),"lm_message":str(solved.message)})
    except RuntimeError:
        _stats["lm_failures"]+=1; raise
    _stats["lm_solves"]+=1; _stats["lm_nfev"]+=int(solved.nfev); _stats["pgs_seed_iterations"]+=maxiter
    return answer
def inertial_contact_step(*args,**kwargs):
    original=s41._solve_prepared; s41._solve_prepared=_solve
    try: return s42.inertial_contact_step(*args,**kwargs)
    finally: s41._solve_prepared=original
