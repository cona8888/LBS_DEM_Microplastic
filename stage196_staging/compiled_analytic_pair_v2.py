"""Strict compiled scalar arithmetic; original NumPy reductions kept outside.

No fast math, reassociation, threaded loops, changed optimizer or inter-pose
reuse. Candidate requires exact independent verification before trajectories.
"""
from pathlib import Path
from contextlib import contextmanager
import os, sys
ROOT=Path(__file__).resolve().parents[1]
DEPENDENCIES=ROOT/'bottleneck_resolution_20260912/deps'
sys.path.insert(0,str(DEPENDENCIES))
os.environ['NUMBA_NUM_THREADS']='1'
os.environ['NUMBA_DISABLE_INTEL_SVML']='1'
os.environ['NUMBA_CACHE_DIR']=str(ROOT/'stage196_dependencies/jit_cache_01')
import numba, llvmlite
import numpy as np
import constant_analytic_pair_v1 as previous
repair=previous.repair
assert numba.__version__=='0.62.1' and llvmlite.__version__=='0.45.1'


@numba.njit(cache=True,fastmath=False,parallel=False)
def assemble(y,vc,gap,norms,speeds,H,eye,steps,scales,mu,dr):
    count=len(gap);size=len(y)
    result=np.empty(size);jac=np.empty_like(H);projection=np.zeros((count,2,2));sliding=np.zeros(count,np.bool_)
    for k in range(count):
        i=3*k;n=y[i];vn=vc[i]+gap[k];norm=norms[k]
        if norm:
            result[i]=norm-n-vn
            for j in range(size):jac[i,j]=(n/norm-1)*eye[i,j]+(vn/norm-1)*H[i,j]
        else:
            result[i]=0.
            for j in range(size):jac[i,j]=-eye[i,j]-H[i,j]
        r=mu*y[i]*steps[k]/scales[i];speed=speeds[k]
        if r<=0:
            for t in range(2):
                result[i+1+t]=y[i+1+t]
                for j in range(size):jac[i+1+t,j]=eye[i+1+t,j]
        elif speed<=r:
            for t in range(2):
                result[i+1+t]=vc[i+1+t]
                for j in range(size):jac[i+1+t,j]=H[i+1+t,j]
        else:
            sliding[k]=True
            direction=np.empty(2)
            for t in range(2):direction[t]=(y[i+1+t]-vc[i+1+t])/speed
            for t in range(2):
                result[i+1+t]=y[i+1+t]-r*direction[t]
                for j in range(size):jac[i+1+t,j]=eye[i+1+t,j]-direction[t]*dr[k,j]
                for u in range(2):projection[k,t,u]=(r/speed)*((1. if t==u else 0.)-direction[t]*direction[u])
    return result,jac,projection,sliding


def optimized_system(v,M,J,g,dt,mu):
    A=J@M@J.T;z=J@v;vs=max(np.linalg.norm(v),1e-15)
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(len(g))])
    scales=np.repeat(steps,3);scales[::3]=A.diagonal()[::3]
    H=A/scales[None,:];zv=z/vs;gap=g/dt/vs;eye=np.eye(len(z))
    constants=[(3*k,eye[3*k+1:3*k+3]-H[3*k+1:3*k+3]) for k in range(len(g))]
    dr=np.array([mu*steps[k]/scales[3*k]*eye[3*k] for k in range(len(g))])
    key=None;value=None
    def both(y):
        nonlocal key,value
        a=np.asarray(y);new_key=(a.shape,a.dtype.str,a.tobytes())
        if new_key==key:return tuple(x.copy() for x in value)
        vc=zv+H@y
        norms=np.hypot(y[::3],vc[::3]+gap)
        speeds=np.array([np.linalg.norm(y[i+1:i+3]-vc[i+1:i+3]) for i,_ in constants])
        result,jac,projection,sliding=assemble(y,vc,gap,norms,speeds,H,eye,steps,scales,mu,dr)
        for k,(i,dx) in enumerate(constants):
            if sliding[k]:jac[i+1:i+3]-=projection[k]@dx
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
