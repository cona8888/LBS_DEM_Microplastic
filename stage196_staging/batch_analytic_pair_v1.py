"""Batch elementwise contact Jacobian work; unchanged same-system optimizer.

Candidate only. Must pass bitwise function and complete held-solve tests before
any trajectory use. No force transfer between systems, poses or timesteps.
"""
from contextlib import contextmanager
import numpy as np
import constant_analytic_pair_v1 as previous
repair=previous.repair


def optimized_system(v,M,J,g,dt,mu):
    A=J@M@J.T;z=J@v;vs=max(np.linalg.norm(v),1e-15)
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(len(g))])
    scales=np.repeat(steps,3);scales[::3]=A.diagonal()[::3]
    H=A/scales[None,:];zv=z/vs;gap=g/dt/vs;eye=np.eye(len(z))
    count=len(g);normal=np.arange(count)*3
    e3=eye.reshape(count,3,-1);h3=H.reshape(count,3,-1)
    dx=e3[:,1:]-h3[:,1:]
    dr=np.array([mu*steps[k]/scales[3*k]*eye[3*k] for k in range(count)])
    identity2=np.eye(2);key=None;value=None
    def both(y):
        nonlocal key,value
        a=np.asarray(y);new_key=(a.shape,a.dtype.str,a.tobytes())
        if new_key==key:return tuple(x.copy() for x in value)
        vc=zv+H@y;result=np.empty(len(y));jac=np.empty_like(H)
        result3=result.reshape(count,3);jac3=jac.reshape(count,3,-1)
        n=y[normal];vn=vc[normal]+gap;norm=np.hypot(n,vn)
        nz=norm!=0
        result3[:,0]=norm-n-vn
        jac3[:,0]=-e3[:,0]-h3[:,0]
        if np.any(nz):
            jac3[nz,0]=(n[nz]/norm[nz]-1)[:,None]*e3[nz,0]+(vn[nz]/norm[nz]-1)[:,None]*h3[nz,0]
        result3[~nz,0]=0.
        yt=y.reshape(count,3)[:,1:];vt=vc.reshape(count,3)[:,1:];x=yt-vt
        r=mu*y[normal]*steps/scales[normal]
        # Keep the original per-row norm implementation and arithmetic order.
        speed=np.array([np.linalg.norm(row) for row in x])
        result3[:,1:]=yt;jac3[:,1:]=e3[:,1:]
        inside=(r>0)&(speed<=r);sliding=(r>0)&(speed>r)
        result3[inside,1:]=vt[inside];jac3[inside,1:]=h3[inside,1:]
        if np.any(sliding):
            direction=x[sliding]/speed[sliding,None]
            result3[sliding,1:]=yt[sliding]-r[sliding,None]*direction
            jac3[sliding,1:]=e3[sliding,1:]-direction[:,:,None]*dr[sliding,None,:]-(r[sliding]/speed[sliding])[:,None,None]*(identity2-direction[:,:,None]*direction[:,None,:])@dx[sliding]
        key=new_key;value=(result.copy(),jac.copy())
        return result,jac
    return both,A,z,steps,scales,vs


@contextmanager
def scope(enabled=False):
    if type(enabled) is not bool:raise ValueError('explicit Boolean opt-in')
    if not enabled:yield;return
    analytic=repair.prior.analytic;original=analytic.system;analytic.system=optimized_system
    try:yield
    finally:analytic.system=original
