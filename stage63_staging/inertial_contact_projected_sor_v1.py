"""Cold projected SOR for small Coulomb contact sets, with strict Stage50 gates."""
import sys
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage41_staging"),str(ROOT/"stage42_staging"),str(ROOT/"stage50_staging")]
import inertial_contact_cold_optimized_v1 as s41
import inertial_contact_robust_v1 as s42
import inertial_contact_seeded_lm_v1 as s50

base=s42.base; generalized_mass_matrix=s42.generalized_mass_matrix; stokes_generalized_resistance=s42.stokes_generalized_resistance
contact_model=s42.contact_model; finite_re=s42.finite_re; contact_solve=s42.contact_solve
RELAXATION=1.7
_stats={"solves":0,"failures":0,"iterations":0}
def stats(): return dict(_stats)


def _solve(vfree,mobility,jacobian,gaps,dt,friction,tol,maxiter):
    vfree=contact_model.finite(vfree); mobility=contact_model.finite(mobility)
    if not len(gaps):
        _stats["solves"]+=1
        return vfree,{"iterations":0,"residual":0.,"force_residual":0.,"dissipation":0.,"reactions":[],"solver":"projected_sor"}
    A=jacobian@mobility@jacobian.T; z=jacobian@vfree; force=np.zeros(len(z)); scale=max(np.linalg.norm(vfree),1e-15)
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(len(gaps))])
    for iteration in range(maxiter):
        for k in range(len(gaps)):
            i=3*k
            old=force[i]; vn=z[i]+A[i]@force+gaps[k]/dt
            candidate=max(0.,old-vn/A[i,i]); force[i]=max(0.,old+RELAXATION*(candidate-old))
            old_t=force[i+1:i+3].copy(); vt=z[i+1:i+3]+A[i+1:i+3]@force
            candidate_t=s50._project(old_t,vt,steps[k],friction*force[i]); trial=old_t+RELAXATION*(candidate_t-old_t)
            limit=friction*force[i]; force[i+1:i+3]=trial*min(1.,limit/max(np.linalg.norm(trial),1e-300))
        if s50._residual(force,z,A,gaps,dt,friction,steps)/scale<=tol:
            answer=s50._finish(vfree,mobility,jacobian,force,z,A,gaps,dt,friction,steps,iteration+1,"projected_sor",{"relaxation":RELAXATION})
            _stats["solves"]+=1; _stats["iterations"]+=iteration+1
            return answer
    _stats["failures"]+=1
    raise RuntimeError("direct contact residual nonconvergence")


def inertial_contact_step(*args,**kwargs):
    original=s41._solve_prepared; s41._solve_prepared=_solve
    try: return s42.inertial_contact_step(*args,**kwargs)
    finally: s41._solve_prepared=original
