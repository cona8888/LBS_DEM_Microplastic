"""Fixed grains with a freely suspended ellipsoid in uniform Stokes flow.
Rigid force/torque-free body. Finite-clearance only; no contact model.
"""
import numpy as np
from scipy.linalg import svd
import sharp_stokes_mfs_v3 as m
import sharp_sphere_reference_v1 as q
def solve(centre,Q,n=192,check=True,grains=((0.,-1.5,0.),(0.,1.5,0.)),axes=(.2,.1,.1)):
    AXES=np.asarray(axes,float)
    if AXES.shape!=(3,) or not np.isfinite(AXES).all() or np.any(AXES<=0):raise ValueError('invalid axes')
    centre=np.asarray(centre,float);Q=np.asarray(Q,float)
    grains=np.asarray(grains,float)
    if grains.ndim!=2 or grains.shape[1]!=3 or len(grains)<1 or not np.isfinite(grains).all():raise ValueError('invalid grains')
    for i in range(len(grains)):
        for j in range(i):
            if np.linalg.norm(grains[i]-grains[j])<=2:raise ValueError('overlapping grains')
    k=len(grains);nf=k*n;nb=3*nf;total=(k+1)*n
    if np.min(np.linalg.norm(grains-centre,axis=1))<=1+max(AXES)+.05:raise ValueError('outside verified clearance domain')
    dirs=m.directions(n);bd=m.directions(3*n)
    sources=np.vstack([np.vstack([g+.6*dirs for g in grains]),centre+(dirs*np.sqrt(AXES**2-(1-.55**2)*float(np.min(AXES))**2))@Q.T])
    points=np.vstack([np.vstack([g+bd for g in grains]),centre+(bd*AXES)@Q.T]);N=3*total
    A=m.kernel(points,sources,1).transpose(0,2,1,3).reshape(9*total,3*total)
    u,s,v=svd(A,full_matrices=False);keep=s>s[0]*1e-12
    targets=np.zeros((N,3,7));targets[:,:,0]=[-1,0,0]
    for d in range(3):
        targets[nb:,:,d+1]=np.eye(3)[d]
        targets[nb:,:,d+4]=np.cross(np.eye(3)[d],points[nb:]-centre)
    lam=(v[keep].T@((u[:,keep].T@targets.reshape(9*total,7))/s[keep,None])).reshape(total,3,7)
    wrench=np.vstack([lam[nf:].sum(axis=0),np.stack([np.cross(sources[nf:]-centre,lam[nf:,:,d]).sum(axis=0) for d in range(7)],axis=1)])
    z=np.linalg.solve(wrench[:,1:],-wrench[:,0]);strength=lam[:,:,0]+np.einsum('ncd,d->nc',lam[:,:,1:],z)
    state={'sources':sources,'mu':1.};sol={'lambda':strength,'far_velocity':np.array([1.,0,0])}
    residual=np.r_[strength[nf:].sum(axis=0),np.cross(sources[nf:]-centre,strength[nf:]).sum(axis=0)]
    health={'force_free_residual':float(np.linalg.norm(residual)),'condition':float(s[0]/s[-1])}
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
