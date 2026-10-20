"""Oversampled 3-D exterior Stokes method of fundamental solutions (MFS) candidate.

Singular Stokeslets lie strictly inside an ellipsoid; no singularity or
regularized force is placed in fluid. Collocation stays on physical surface.
Unbounded steady Newtonian Stokes flow ONLY; no contact or periodic boundaries.
Three boundary points per source; SVD cutoff 1e-12 fixed, not drag-fitted.
Dense O(N^3) factorization limits use to small verification problems.
"""
import numpy as np
from scipy.linalg import svd

def directions(count):
    if type(count) is not int or not 24<=count<=4096:raise ValueError('invalid point count')
    j=np.arange(count);z=1-2*(j+.5)/count;theta=j*np.pi*(3-np.sqrt(5))
    return np.column_stack((np.sqrt(1-z*z)*np.cos(theta),np.sqrt(1-z*z)*np.sin(theta),z))

def kernel(points,sources,mu):
    d=np.asarray(points)[:,None,:]-np.asarray(sources)[None,:,:]
    r=np.linalg.norm(d,axis=2)
    if np.any(r<=0) or not np.isfinite(r).all():raise ValueError('singular source evaluation')
    return (np.eye(3)[None,None,:,:]/r[:,:,None,None]+d[:,:,:,None]*d[:,:,None,:]/r[:,:,None,None]**3)/(8*np.pi*mu)

def prepare(axes=(1.,1.,1.),count=96,source_fraction=.6,mu=.1,centre=(0.,0.,0.)):
    axes=np.asarray(axes,float);centre=np.asarray(centre,float)
    if axes.shape!=(3,) or centre.shape!=(3,) or not np.isfinite(axes).all() or not np.isfinite(centre).all() or np.any(axes<=0):raise ValueError('invalid ellipsoid')
    if not np.isfinite(mu) or mu<=0 or not np.isfinite(source_fraction) or not 0<source_fraction<1:raise ValueError('invalid viscosity/source fraction')
    if count>1024:raise ValueError('source count exceeds bounded dense-solver range')
    points=centre+directions(3*count)*axes
    # Confocal source ellipsoid: stays inside and encloses the focal set.
    delta2=(1-source_fraction**2)*float(np.min(axes))**2
    source_axes=np.sqrt(axes**2-delta2)
    sources=centre+directions(count)*source_axes
    A=kernel(points,sources,mu).transpose(0,2,1,3).reshape(9*count,3*count)
    left,singular,right=svd(A,full_matrices=False)
    condition=float(singular[0]/singular[-1])
    keep=singular>singular[0]*1e-12
    if not np.isfinite(condition) or not np.any(keep):raise ValueError('invalid source matrix spectrum')
    inverse=(right[keep].T/singular[keep])@left[:,keep].T
    return {'points':points,'sources':sources,'axes':axes,'centre':centre,'mu':mu,'matrix':A,
            'inverse':inverse,'rank':int(keep.sum()),'source_axes':source_axes,'boundary_count':3*count,'condition':condition,'source_fraction':source_fraction,'count':count}

def solve(state,far_velocity=(0.,0.,0.),body_velocity=(0.,0.,0.),omega=(0.,0.,0.)):
    U,V,W=[np.asarray(x,float) for x in [far_velocity,body_velocity,omega]]
    if any(x.shape!=(3,) or not np.isfinite(x).all() for x in [U,V,W]):raise ValueError('invalid velocity')
    target=V+np.cross(W,state['points']-state['centre'])-U
    lam=(state['inverse']@target.ravel()).reshape(-1,3)
    residual=float(np.max(np.abs((state['matrix']@lam.ravel()).reshape(-1,3)-target)))
    return {'lambda':lam,'far_velocity':U,'body_velocity':V,'omega':W,
            'force':-lam.sum(axis=0),'torque':-np.cross(state['sources']-state['centre'],lam).sum(axis=0),
            'collocation_residual':residual}

def velocity(state,solution,points):
    return solution['far_velocity']+np.einsum('mnij,nj->mi',kernel(points,state['sources'],state['mu']),solution['lambda'])

def traction(state,solution,points,normals):
    d=np.asarray(points)[:,None,:]-state['sources'][None,:,:];r=np.linalg.norm(d,axis=2)
    if np.any(r==0):raise ValueError('singular stress evaluation')
    dot=np.einsum('mnj,nj->mn',d,solution['lambda'])
    dn=np.einsum('mnj,mj->mn',d,np.asarray(normals))
    return -3/(4*np.pi)*np.sum((dot*dn/r**5)[:,:,None]*d,axis=1)
