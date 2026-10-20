"""Hoist y-independent analytic Jacobian arrays; memoize one identical y.

The original matrix products and y-dependent arithmetic order are retained.
No inter-contact-system, inter-pose or reaction reuse. No optimizer setting or
acceptance criterion changes. Requires exact held-system and trajectory tests.
"""
from contextlib import contextmanager
import numpy as np
import early_semismooth_dispatch_v1 as repair


def optimized_system(v, M, J, g, dt, mu):
    A=J@M@J.T;z=J@v;vs=max(np.linalg.norm(v),1e-15)
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(len(g))])
    scales=np.repeat(steps,3);scales[::3]=A.diagonal()[::3]
    H=A/scales[None,:];zv=z/vs;gap=g/dt/vs;eye=np.eye(len(z))
    identity2=np.eye(2)
    constants=[(3*k,eye[3*k+1:3*k+3]-H[3*k+1:3*k+3],mu*steps[k]/scales[3*k]*eye[3*k]) for k in range(len(g))]
    key=None;value=None
    def both(y):
        nonlocal key,value
        a=np.asarray(y);new_key=(a.shape,a.dtype.str,a.tobytes())
        if new_key==key:
            return tuple(x.copy() for x in value)
        vc=zv+H@y;result=np.empty(len(y));jac=np.empty_like(H)
        for k,(i,dx,dr) in enumerate(constants):
            n=y[i];vn=vc[i]+gap[k];norm=np.hypot(n,vn)
            if norm:
                result[i]=norm-n-vn;jac[i]=(n/norm-1)*eye[i]+(vn/norm-1)*H[i]
            else:result[i]=0.;jac[i]=-eye[i]-H[i]
            x=y[i+1:i+3]-vc[i+1:i+3];r=mu*y[i]*steps[k]/scales[i];speed=np.linalg.norm(x)
            if r<=0:
                result[i+1:i+3]=y[i+1:i+3];jac[i+1:i+3]=eye[i+1:i+3]
            elif speed<=r:
                result[i+1:i+3]=vc[i+1:i+3];jac[i+1:i+3]=H[i+1:i+3]
            else:
                direction=x/speed
                result[i+1:i+3]=y[i+1:i+3]-r*direction
                jac[i+1:i+3]=eye[i+1:i+3]-np.outer(direction,dr)-r/speed*(identity2-np.outer(direction,direction))@dx
        key=new_key;value=(result.copy(),jac.copy())
        return result,jac
    return both,A,z,steps,scales,vs


@contextmanager
def scope(enabled=False):
    if type(enabled) is not bool:raise ValueError('explicit Boolean opt-in')
    if not enabled:yield;return
    analytic=repair.prior.analytic;original=analytic.system
    analytic.system=optimized_system
    try:yield
    finally:analytic.system=original
