"""Reduced one-way transport for rigid axisymmetric bodies in a frozen LBM field.

Coordinates are lattice-cell units.  The body is an axisymmetric ellipsoid
with semi-axes (a,b,b) and unit major-axis vector p.  Grain interception uses
the ellipsoid support function and is deliberately conservative: an indicated
interception is unresolved, never asserted to be permanent retention.
"""
from __future__ import annotations
import numpy as np
from scipy.spatial import cKDTree

def periodic_gradient(velocity):
    """Return du_i/dx_j with centered periodic differences."""
    u=np.asarray(velocity,float)
    if u.ndim!=4 or u.shape[0]!=3: raise ValueError('velocity must be (3,nx,ny,nz)')
    g=np.empty((3,3,*u.shape[1:]),float)
    for j in range(3): g[:,j]=(np.roll(u,-1,axis=j+1)-np.roll(u,1,axis=j+1))/2
    return g

def trilinear(field,point):
    """Periodic trilinear interpolation of (...,nx,ny,nz) at one point."""
    f=np.asarray(field);p=np.asarray(point,float);shape=np.array(f.shape[-3:],int)
    if p.shape!=(3,) or not np.isfinite(p).all(): raise ValueError('invalid point')
    q=np.mod(p,shape);i=np.floor(q).astype(int);w=q-i;out=np.zeros(f.shape[:-3],float)
    for dx in (0,1):
      for dy in (0,1):
       for dz in (0,1):
        wt=(w[0] if dx else 1-w[0])*(w[1] if dy else 1-w[1])*(w[2] if dz else 1-w[2])
        out+=wt*f[..., (i[0]+dx)%shape[0],(i[1]+dy)%shape[1],(i[2]+dz)%shape[2]]
    return out

def ellipsoid_support(direction,p,a,b):
    n=np.asarray(direction,float);p=np.asarray(p,float);nn=np.linalg.norm(n)
    if nn==0:return float(a)
    c=float(np.dot(n/nn,p/np.linalg.norm(p)))
    return float(np.sqrt(b*b+(a*a-b*b)*c*c))

def jeffery_rhs(p,grad,aspect_ratio):
    p=np.asarray(p,float);p=p/np.linalg.norm(p);g=np.asarray(grad,float)
    E=(g+g.T)/2;W=(g-g.T)/2;lam=(aspect_ratio**2-1)/(aspect_ratio**2+1)
    return W@p+lam*(E@p-float(p@E@p)*p)

class PeriodicGrains:
    def __init__(self,centres,radii,box_length):
        c=np.asarray(centres,float);r=np.asarray(radii,float);L=float(box_length)
        if c.ndim!=2 or c.shape[1]!=3 or r.shape!=(len(c),) or L<=0:raise ValueError('invalid grains')
        shifts=np.array(np.meshgrid([-L,0,L],[-L,0,L],[-L,0,L],indexing='ij')).reshape(3,-1).T
        self.centres=np.vstack([c+s for s in shifts]);self.radii=np.tile(r,len(shifts));self.tree=cKDTree(self.centres);self.max_radius=float(r.max());self.L=L
    def margin(self,point,p,a,b):
        q=np.asarray(point,float);ids=self.tree.query_ball_point(q,self.max_radius+a)
        if not ids:return np.inf
        d=self.centres[ids]-q;dist=np.linalg.norm(d,axis=1);sup=np.array([ellipsoid_support(v,p,a,b) for v in d])
        return float(np.min(dist-self.radii[ids]-sup))

def advance_orientation(p,grad,aspect_ratio,dt):
    q=np.asarray(p,float)+dt*jeffery_rhs(p,grad,aspect_ratio)
    n=np.linalg.norm(q)
    if not np.isfinite(n) or n==0:raise FloatingPointError('invalid orientation')
    return q/n

