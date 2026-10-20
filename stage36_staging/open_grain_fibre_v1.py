"""Two-body MFS: fixed unit grain, freely suspended prolate in uniform Stokes flow.
Rigid force/torque-free body. Finite-clearance only; no contact model.
"""
import numpy as np
from scipy.linalg import svd
import sharp_stokes_mfs_v3 as m
import sharp_sphere_reference_v1 as q
AXES=np.array([.2,.1,.1])
def solve(centre,Q,n=192,check=True):
    centre=np.asarray(centre,float);Q=np.asarray(Q,float)
    if np.linalg.norm(centre)<=1+max(AXES)+.05:raise ValueError('outside verified clearance domain')
    dirs=m.directions(n);bd=m.directions(3*n)
    sources=np.vstack([.6*dirs,centre+(dirs*np.sqrt(AXES**2-(1-.55**2)*.1**2))@Q.T])
    points=np.vstack([bd,centre+(bd*AXES)@Q.T]);N=6*n
    A=m.kernel(points,sources,1).transpose(0,2,1,3).reshape(18*n,6*n)
    u,s,v=svd(A,full_matrices=False);keep=s>s[0]*1e-12
    targets=np.zeros((N,3,7));targets[:,:,0]=[-1,0,0]
    for d in range(3):
        targets[3*n:,:,d+1]=np.eye(3)[d]
        targets[3*n:,:,d+4]=np.cross(np.eye(3)[d],points[3*n:]-centre)
    lam=(v[keep].T@((u[:,keep].T@targets.reshape(18*n,7))/s[keep,None])).reshape(2*n,3,7)
    wrench=np.vstack([lam[n:].sum(axis=0),np.stack([np.cross(sources[n:]-centre,lam[n:,:,d]).sum(axis=0) for d in range(7)],axis=1)])
    z=np.linalg.solve(wrench[:,1:],-wrench[:,0]);strength=lam[:,:,0]+np.einsum('ncd,d->nc',lam[:,:,1:],z)
    state={'sources':sources,'mu':1.};sol={'lambda':strength,'far_velocity':np.array([1.,0,0])}
    residual=np.r_[strength[n:].sum(axis=0),np.cross(sources[n:]-centre,strength[n:]).sum(axis=0)]
    health={'force_free_residual':float(np.linalg.norm(residual)),'condition':float(s[0]/s[-1])}
    if check:
        unit,_,_=q.surface_quadrature(1,24,48);errors=[]
        for p,free in [(unit,False),(centre+(unit*AXES)@Q.T,True)]:
            errs=[]
            for chunk in np.array_split(p,8):
                expected=z[:3]+np.cross(z[3:],chunk-centre) if free else 0
                errs.append(np.linalg.norm(m.velocity(state,sol,chunk)-expected,axis=1).max())
            errors.append(float(max(errs)))
        health['grain_boundary_error']=errors[0];health['fibre_boundary_error']=errors[1]
    return z,health
