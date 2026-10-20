"""Original-law sliding fallback with analytic variable-projection derivative.

V1's finite differences missed two contact-permutation tests. V1 stays failed.
This version differentiates the eliminated linear normal-force solution, with
no altered force law, gap, time step or physical acceptance criterion.
"""
from contextlib import contextmanager
import time
import numpy as np
from scipy.optimize import least_squares
import sliding_projection_repair_v1 as prior
gate=prior.gate;ERRORS=prior.ERRORS
NAME='stage194_failure_only_sliding_projection_v2'
telemetry=[]


def solve(vfree,mobility,jacobian,gaps,dt,friction,tol,maxiter,stop_epoch=None):
    v,M,J,g=[np.asarray(x,float) for x in (vfree,mobility,jacobian,gaps)]
    if v.shape!=(6,) or M.shape!=(6,6) or J.shape!=(9,6) or g.shape!=(3,):raise ValueError('three-contact six-DOF domain only')
    if not all(np.isfinite(x).all() for x in (v,M,J,g)) or not np.isfinite([dt,friction,tol]).all() or dt<=0 or friction<=0 or tol!=1e-10:raise ValueError('invalid original-law input')
    if not np.allclose(M,M.T,rtol=0,atol=1e-12*np.linalg.norm(M)):raise ValueError('symmetric mobility required')
    np.linalg.cholesky(M)
    B=np.linalg.inv(M);load=B@v;fs=max(np.linalg.norm(load),1e-30);vs=max(np.linalg.norm(v),1e-15)
    if np.max(np.abs(g/dt))>1e-5*vs:raise ValueError('outside nearly closed fallback domain')
    qs=max(np.max(np.abs(g/dt)),vs*1e-15);mu=friction
    A=J@M@J.T;z=J@v;steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(3)])
    C=J[::3];d=-g/dt/qs;u,sv,vh=np.linalg.svd(C,full_matrices=True)
    if sv[-1]<=sv[0]*1e-12:raise RuntimeError('rank deficient normal constraints')
    q0=vh[:3].T@((u.T@d)/sv);N=vh[3:].T;JN=J@N;rhsD=B@N*qs/fs
    def both(y):
        vel=q0+N@y;vc=J@vel;E=np.zeros((9,3));dE=np.zeros((3,9,3))
        for k in range(3):
            i=3*k;vt=vc[i+1:i+3];speed=np.linalg.norm(vt);E[i,k]=1.
            if speed<=1e-30:direction=vt/1e-30;derivative=JN[i+1:i+3]/1e-30
            else:
                direction=vt/speed;derivative=(np.eye(2)-np.outer(direction,direction))@JN[i+1:i+3]/speed
            E[i+1:i+3,k]=-mu*direction
            for j in range(3):dE[j,i+1:i+3,k]=-mu*derivative[:,j]
        H=J.T@E;rhs=B@(vel*qs-v)/fs
        normal=np.linalg.lstsq(H,rhs,rcond=1e-12)[0];res=H@normal-rhs;deriv=np.empty((6,3))
        gram=H.T@H
        for j in range(3):
            dH=J.T@dE[j]
            dn=np.linalg.solve(gram,-dH.T@res+H.T@(rhsD[:,j]-dH@normal))
            deriv[:,j]=dH@normal+H@dn-rhsD[:,j]
        return res,deriv,E@normal*fs
    rng=np.random.default_rng(194)
    seeds=[np.zeros(3),np.ones(3),-np.ones(3)]+[x for e in np.eye(3) for x in (e,-e)]+[rng.normal(size=3)*scale for scale in (.1,1.,10.,100.) for _ in range(12)]
    evaluations=0;start=time.perf_counter()
    for i,seed in enumerate(seeds):
        if stop_epoch is not None and time.time()>=stop_epoch:raise RuntimeError('diagnostic work cutoff reached')
        try:
            opt=least_squares(lambda y:both(y)[0],seed,jac=lambda y:both(y)[1],xtol=1e-14,ftol=1e-14,gtol=1e-14,max_nfev=1000,x_scale='jac')
            evaluations+=int(opt.nfev);f=both(opt.x)[2]
        except np.linalg.LinAlgError:continue
        try:
            answer=gate._finish(v,M,J,f,z,A,g,dt,mu,steps,evaluations,NAME,
               {'projection_seed_index':i,'projection_nfev':evaluations,'original_gaps_preserved':True,'contact_modes':[2,2,2],'analytic_projection_jacobian':True})
        except RuntimeError:continue
        telemetry.append({'seed_index':i,'nfev':evaluations,'seconds':time.perf_counter()-start})
        return answer
    raise RuntimeError('direct contact residual nonconvergence')


@contextmanager
def scope(runtime,enabled=False,stop_epoch=None):
    if type(enabled) is not bool:raise ValueError('explicit Boolean opt-in required')
    if not enabled:yield;return
    original=runtime.mixed.solve
    def repaired(v,M,J,g,dt,mu,tol,maxiter):
        try:return original(v,M,J,g,dt,mu,tol,maxiter)
        except RuntimeError as original_error:
            if str(original_error) not in ERRORS or len(g)!=3:raise
            try:return solve(v,M,J,g,dt,mu,tol,maxiter,stop_epoch)
            except (RuntimeError,ValueError,np.linalg.LinAlgError,FloatingPointError):raise original_error
    runtime.mixed.solve=repaired
    try:yield
    finally:runtime.mixed.solve=original
