"""QR-accelerated fixed-grain/ellipsoid MFS candidate.

Same geometry, collocation, sources and 1e-12 rank threshold as
open_grains_ellipsoid_v1; solves only the seven required right-hand sides.
Candidate until compared with the frozen SVD implementation.
"""
import numpy as np
from scipy.linalg import lstsq
import sharp_stokes_mfs_v3 as m
import sharp_sphere_reference_v1 as q

def solve(centre,Q,n=192,check=True,grains=((0.,-1.5,0.),(0.,1.5,0.)),axes=(.2,.1,.1)):
    AXES=np.asarray(axes,float);centre=np.asarray(centre,float);Q=np.asarray(Q,float);grains=np.asarray(grains,float)
    if AXES.shape!=(3,) or np.any(AXES<=0) or not np.isfinite(AXES).all():raise ValueError('invalid axes')
    if centre.shape!=(3,) or Q.shape!=(3,3) or grains.ndim!=2 or grains.shape[1]!=3:raise ValueError('invalid geometry')
    for i in range(len(grains)):
        for j in range(i):
            if np.linalg.norm(grains[i]-grains[j])<=2:raise ValueError('overlapping grains')
    if np.min(np.linalg.norm(grains-centre,axis=1))<=1+max(AXES)+.05:raise ValueError('outside verified clearance domain')
    k=len(grains);nf=k*n;nb=3*nf;total=(k+1)*n
    dirs=m.directions(n);bd=m.directions(3*n)
    source_axes=np.sqrt(AXES**2-(1-.55**2)*float(np.min(AXES))**2)
    sources=np.vstack([np.vstack([g+.6*dirs for g in grains]),centre+(dirs*source_axes)@Q.T])
    points=np.vstack([np.vstack([g+bd for g in grains]),centre+(bd*AXES)@Q.T])
    A=m.kernel(points,sources,1).transpose(0,2,1,3).reshape(9*total,3*total)
    targets=np.zeros((3*total,3,7));targets[:,:,0]=[-1,0,0]
    for d in range(3):
        targets[nb:,:,d+1]=np.eye(3)[d]
        targets[nb:,:,d+4]=np.cross(np.eye(3)[d],points[nb:]-centre)
    coeff,_,rank,_=lstsq(A,targets.reshape(9*total,7),cond=1e-12,lapack_driver='gelsy')
    lam=coeff.reshape(total,3,7)
    wrench=np.vstack([lam[nf:].sum(axis=0),np.stack([np.cross(sources[nf:]-centre,lam[nf:,:,d]).sum(axis=0) for d in range(7)],axis=1)])
    z=np.linalg.solve(wrench[:,1:],-wrench[:,0]);strength=lam[:,:,0]+np.einsum('ncd,d->nc',lam[:,:,1:],z)
    state={'sources':sources,'mu':1.};sol={'lambda':strength,'far_velocity':np.array([1.,0,0])}
    residual=np.r_[strength[nf:].sum(axis=0),np.cross(sources[nf:]-centre,strength[nf:]).sum(axis=0)]
    health={'force_free_residual':float(np.linalg.norm(residual)),'rank':int(rank)}
    if check:
        unit,_,_=q.surface_quadrature(1,24,48);errors=[]
        for p,free in [(g+unit,False) for g in grains]+[(centre+(unit*AXES)@Q.T,True)]:
            errs=[]
            for chunk in np.array_split(p,8):
                expected=z[:3]+np.cross(z[3:],chunk-centre) if free else 0
                errs.append(np.linalg.norm(m.velocity(state,sol,chunk)-expected,axis=1).max())
            errors.append(float(max(errs)))
        health['grain_boundary_error']=max(errors[:-1]);health['fibre_boundary_error']=errors[-1]
    return z,health
