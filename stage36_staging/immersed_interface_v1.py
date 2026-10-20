"""Fixed-grid four-point transfer and persistent sphere quadrature; no flow solver."""
import numpy as np
from itertools import product

def phi(r):
    a=np.abs(np.asarray(r,dtype=float))
    if not np.isfinite(a).all():raise ValueError('nonfinite kernel argument')
    out=np.zeros_like(a);near=a<=1;far=(a>1)&(a<2)
    out[near]=(3-2*a[near]+np.sqrt(1+4*a[near]-4*a[near]**2))/8
    out[far]=(5-2*a[far]-np.sqrt(-7+12*a[far]-4*a[far]**2))/8
    return out

def stencil(points,n,h):
    X=np.asarray(points,float)
    if X.ndim!=2 or X.shape[1]!=3 or not len(X) or not np.isfinite(X).all() or n<4 or not np.isfinite(h) or h<=0:raise ValueError('invalid grid or markers')
    base=np.floor(X/h-.5).astype(int)-1;offset=np.array(list(product(range(4),repeat=3)))
    ijk=base[:,None,:]+offset[None,:,:]
    if np.any(ijk<0) or np.any(ijk>=n):raise ValueError('kernel support outside box')
    pos=(ijk+.5)*h;w=np.prod(phi((pos-X[:,None,:])/h),axis=2)
    ids=np.ravel_multi_index(ijk.reshape(-1,3).T,(n,n,n)).reshape(len(X),64)
    return ids,w,pos

def interpolate(grid,ids,w):
    u=np.asarray(grid,float)
    if not np.isfinite(u).all():raise ValueError('invalid grid field')
    return np.einsum('lk,lkc->lc',w,u[ids])

def spread(force,ids,w,n,h):
    F=np.asarray(force,float)
    if F.shape!=(len(ids),3) or not np.isfinite(F).all() or not np.isfinite(h) or h<=0:raise ValueError('invalid integrated marker force')
    f=np.zeros((n**3,3));np.add.at(f,ids.ravel(),(w[:,:,None]*F[:,None,:]/h**3).reshape(-1,3))
    return f

def sphere_quadrature(radius,nr=4,nmu=8,ntheta=16):
    if not np.isfinite(radius) or radius<=0 or nr<2 or nmu<3 or ntheta<4:raise ValueError('invalid quadrature')
    r,wr=np.polynomial.legendre.leggauss(nr);r=(r+1)*radius/2;wr=wr*radius/2
    mu,wm=np.polynomial.legendre.leggauss(nmu);theta=2*np.pi*np.arange(ntheta)/ntheta
    rr,mm,tt=np.meshgrid(r,mu,theta,indexing='ij');ww=wr[:,None,None]*wm[None,:,None]*np.ones((1,1,ntheta))*2*np.pi/ntheta*rr**2
    x=np.stack((rr*np.sqrt(1-mm**2)*np.cos(tt),rr*np.sqrt(1-mm**2)*np.sin(tt),rr*mm),axis=-1)
    return x.reshape(-1,3),ww.ravel()

def interior_momentum(grid,ids,w,volume_weights,rho=1.):
    V=np.asarray(volume_weights,float)
    if V.shape!=(len(ids),) or not np.isfinite(V).all() or np.any(V<=0) or not np.isfinite(rho) or rho<=0:raise ValueError('invalid volume/density')
    return rho*np.sum(V[:,None]*interpolate(grid,ids,w),axis=0)

def hydrodynamic_force(force_on_fluid,p_before,p_after,dt):
    a=np.asarray([force_on_fluid,p_before,p_after],float)
    if a.shape!=(3,3) or not np.isfinite(a).all() or not np.isfinite(dt) or dt<=0:raise ValueError('invalid force balance')
    return -a[0]+(a[2]-a[1])/dt
