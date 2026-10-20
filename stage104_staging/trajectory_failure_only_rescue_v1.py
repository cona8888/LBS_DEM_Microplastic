"""Near-zero-gap three-contact rescue; original-system physical gates only."""
import sys
from pathlib import Path
import numpy as np
from scipy.linalg import null_space
from scipy.optimize import least_squares
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage89_staging'))
import verify_short_seed_local_v1 as h
s=h.candidate.stage50
portfolio=h.candidate.portfolio

def mixed(v,M,J,g,dt,mu,tol,maxiter):
    seedargs=(v,M,J,np.zeros_like(g),dt,mu,tol,maxiter)
    _,seed=h.candidate._original_solve(*seedargs)
    fs=max(np.linalg.norm(seed['reactions']),1e-30);vs=max(np.max(np.abs(g/dt)),1e-15)
    B=np.linalg.inv(M);load=B@v;P=np.linalg.pinv(J.T);Z=null_space(J.T)
    target=np.zeros(9);target[::3]=-g/dt
    q0=np.linalg.lstsq(J,target,rcond=1e-12)[0]/vs
    y0=np.r_[q0,Z.T@(np.array(seed['reactions'])-P@(-load))/fs]
    def reactions(y):return P@(B@(y[:6]*vs)-load)+Z@(y[6:]*fs)
    def equations(y):
        f=reactions(y);w=J@y[:6];out=[]
        for k in range(3):
            i=3*k;out.append(w[i]+g[k]/dt/vs)
            tang=w[i+1:i+3]
            out.extend(f[i+1:i+3]/fs+mu*f[i]/fs*tang/max(np.linalg.norm(tang),1e-30))
        return np.array(out)
    opt=least_squares(equations,y0,xtol=1e-13,ftol=1e-13,gtol=1e-13,max_nfev=300)
    f=reactions(opt.x);A=J@M@J.T;z=J@v
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(3)])
    return s._finish(v,M,J,f,z,A,g,dt,mu,steps,opt.nfev+seed['iterations'],'nullspace_all_slide',{})

def integrate(*args,**kwargs):
    old=portfolio._solve;counts=dict(attempts=0,accepted=0,fallbacks=0)
    def solve(v,M,J,g,dt,mu,tol,maxiter):
        try:
            return old(v,M,J,g,dt,mu,tol,maxiter)
        except RuntimeError as original_error:
            if str(original_error) != 'direct contact residual nonconvergence' or len(g)!=3 or np.max(np.abs(g))>1e-15:
                raise
            counts['attempts']+=1
            try:
                answer=mixed(v,M,J,g,dt,mu,tol,maxiter)
            except (RuntimeError,ValueError,FloatingPointError,np.linalg.LinAlgError):
                counts['fallbacks']+=1
                raise original_error
            counts['accepted']+=1
            return answer
    portfolio._solve=solve
    try:r=h.candidate.integrate(*args,**kwargs)
    finally:portfolio._solve=old
    r['nullspace_rescue']=counts
    return r
