"""Guarded all-stick candidate; original Coulomb gates and fallback retained.

Only full-column-rank contact Jacobians are eligible: the all-stick velocity
is then uniquely constrained. Inscribed polygon constraints are a sufficient
force-feasibility search, not a replacement friction law. No reaction warm
start, timestep change, rounded geometry, static hold or changed tolerance.
"""
from contextlib import contextmanager
from pathlib import Path
import sys
import time
import numpy as np
from scipy.optimize import linprog

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage136_staging'))
import compiled_scalar_v1 as hot
import inertial_contact_runtime_portfolio_v1 as portfolio

work={'attempts':0,'accepted':0,'rejected':0,'ineligible':0,'wall_s':0.}


def candidate(vfree,mobility,jacobian,gaps,dt,friction,tol,maxiter):
    v,M,J,g=map(np.asarray,(vfree,mobility,jacobian,gaps))
    n=len(g);scale=max(np.linalg.norm(v),1e-15)
    if not (1<=n<=3 and friction>0 and dt>0 and J.shape==(3*n,6)
            and np.isfinite(v).all() and np.isfinite(M).all() and np.isfinite(J).all()
            and np.isfinite(g).all() and np.max(np.abs(g/dt))<=1e-8*scale):
        raise ValueError('not near a sticking-contact state')
    u,s,vh=np.linalg.svd(J,full_matrices=False)
    if len(s)!=6 or s[-1]<=1e-10*s[0]:
        raise ValueError('sticking velocity not fully constrained')
    target=np.zeros(3*n);target[::3]=-g/dt
    q=vh.T@((u.T@target)/s)
    if np.max(np.abs(J@q-target))>tol*scale:
        raise ValueError('inconsistent sticking constraints')
    B=np.linalg.inv(M);load=B@(q-v);fs=max(np.linalg.norm(load),1e-30)
    # Polygon lies strictly within the circular Coulomb cone. A rejected
    # polygon search only selects the original solver, never a physical state.
    count=16;angles=2*np.pi*np.arange(count)/count
    A_ub=np.zeros((n*count,3*n))
    for k in range(n):
        A_ub[k*count:(k+1)*count,3*k]=-friction*np.cos(np.pi/count)
        A_ub[k*count:(k+1)*count,3*k+1]=np.cos(angles)
        A_ub[k*count:(k+1)*count,3*k+2]=np.sin(angles)
    objective=np.zeros(3*n);objective[::3]=1.
    bounds=[(0,None) if i%3==0 else (None,None) for i in range(3*n)]
    solved=linprog(objective,A_ub=A_ub,b_ub=np.zeros(n*count),
        A_eq=J.T,b_eq=load/fs,bounds=bounds,method='highs',
        options={'dual_feasibility_tolerance':1e-9,'primal_feasibility_tolerance':1e-9})
    if not solved.success or not np.isfinite(solved.x).all():
        raise RuntimeError('no certified sticking candidate')
    f=solved.x*fs
    # Correct equality roundoff only; the unchanged final gates decide
    # whether the corrected force remains inside the true Coulomb cone.
    f+=np.linalg.lstsq(J.T,load-J.T@f,rcond=1e-12)[0]
    A=J@M@J.T;z=J@v
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(n)])
    return hot.s50._finish(v,M,J,f,z,A,g,dt,friction,steps,int(solved.nit),
        'stage138_certified_sticking_candidate',{'search':'inscribed_16_sided_cone_sufficient_only',
        'all_stick_constraint_error':float(np.max(np.abs(J@q-target))/scale)})


@contextmanager
def scope():
    old=portfolio._solve
    def solve(*args,**kwargs):
        started=time.perf_counter();work['attempts']+=1
        try:
            answer=candidate(*args,**kwargs)
        except ValueError:
            work['ineligible']+=1
        except (RuntimeError,FloatingPointError,np.linalg.LinAlgError):
            work['rejected']+=1
        else:
            work['accepted']+=1
            return answer
        finally:work['wall_s']+=time.perf_counter()-started
        return old(*args,**kwargs)
    portfolio._solve=solve
    try:yield
    finally:portfolio._solve=old
