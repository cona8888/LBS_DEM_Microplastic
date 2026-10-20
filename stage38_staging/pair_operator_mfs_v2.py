"""Asymmetrically resolved sphere--ellipsoid Stokes pair operator."""
import sys
from pathlib import Path
import numpy as np
from scipy.linalg import svd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage36_staging'))
import sharp_stokes_mfs_v3 as mfs
import sharp_sphere_reference_v1 as sphere

def frame(p):
    p=np.asarray(p,float); p/=np.linalg.norm(p); e=np.eye(3)[np.argmin(abs(p))]
    q=np.cross(p,e);q/=np.linalg.norm(q);return np.column_stack((p,q,np.cross(p,q)))

def ellipsoid_quadrature(centre,Q,axes,nmu=40,ntheta=80):
    unit,norm0,w=sphere.surface_quadrature(1.,nmu,ntheta); inv=unit/np.asarray(axes)
    scale=np.prod(axes)*np.linalg.norm(inv,axis=1); normals=(inv/np.linalg.norm(inv,axis=1)[:,None])@Q.T
    return centre+(unit*np.asarray(axes))@Q.T,normals,w*scale

def solve(axes,gap,angle,n_body=768,n_grain=384,rtol=1e-12):
    axes=np.asarray(axes,float);a=float(axes[0]);normal=np.array([0.,1.,0.]);p=np.cos(angle)*normal+np.sin(angle)*np.array([1.,0.,0.]);Q=frame(p)
    support=np.sqrt(np.sum((axes*(Q.T@normal))**2));centre=normal*(1+support+gap)
    dg=mfs.directions(n_grain);db=mfs.directions(n_body);cg=mfs.directions(3*n_grain);cb=mfs.directions(3*n_body)
    confocal=np.sqrt(axes**2-(1-.55**2)*min(axes)**2)
    sources=np.vstack((.6*dg,centre+(db*confocal)@Q.T));points=np.vstack((cg,centre+(cb*axes)@Q.T))
    A=mfs.kernel(points,sources,1.).transpose(0,2,1,3).reshape(9*(n_grain+n_body),3*(n_grain+n_body))
    left,s,right=svd(A,full_matrices=False);keep=s>s[0]*rtol
    rhs=np.zeros((3*(n_grain+n_body),3,6))
    for j in range(3):
        rhs[3*n_grain:,:,j]=np.eye(3)[j]
        rhs[3*n_grain:,:,j+3]=np.cross(np.eye(3)[j],points[3*n_grain:]-centre)
    lam=(right[keep].T@((left[:,keep].T@rhs.reshape(9*(n_grain+n_body),6))/s[keep,None])).reshape(n_grain+n_body,3,6)
    lever=sources[n_grain:]-centre
    wrench=np.vstack((lam[n_grain:].sum(axis=0),np.stack([np.cross(lever,lam[n_grain:,:,j]).sum(axis=0) for j in range(6)],axis=1)))
    D=np.diag([1,1,1,1/a,1/a,1/a]);resistance=D@wrench@D
    # Independent no-slip evaluation.
    eg,_ng,_wg=sphere.surface_quadrature(1.,24,48);eb,_nb,_wb=ellipsoid_quadrature(centre,Q,axes,24,48);maxerr=0.
    state={'sources':sources,'mu':1.}
    for boundary,is_body in ((eg,False),(eb,True)):
        for chunk in np.array_split(boundary,8):
            pred=np.stack([mfs.velocity(state,{'lambda':lam[:,:,j],'far_velocity':np.zeros(3)},chunk) for j in range(6)],axis=2);target=np.zeros_like(pred)
            if is_body:
                for j in range(3):target[:,:,j]=np.eye(3)[j]
                for j in range(3):target[:,:,j+3]=np.cross(np.eye(3)[j],chunk-centre)
            maxerr=max(maxerr,float(np.linalg.norm(pred-target,axis=1).max()))
    # Independent surface-stress integration on the body.
    qp,qn,qw=ellipsoid_quadrature(centre,Q,axes);balance=[]
    for j in range(6):
        traction=[]
        for pts,nrm in zip(np.array_split(qp,16),np.array_split(qn,16)):
            traction.append(mfs.traction(state,{'lambda':lam[:,:,j]},pts,nrm))
        traction=np.vstack(traction);force=(qw[:,None]*traction).sum(axis=0);torque=(qw[:,None]*np.cross(qp-centre,traction)).sum(axis=0)
        # Surface traction is fluid-on-body, opposite body source strength.
        reference=np.r_[wrench[:3,j],wrench[3:,j]];balance.append(float(np.linalg.norm(np.r_[force,torque]+reference)/max(np.linalg.norm(reference),1e-30)))
    sym=float(np.linalg.norm(resistance-resistance.T)/np.linalg.norm(resistance));eig=np.linalg.eigvalsh((resistance+resistance.T)/2)
    return resistance,{'boundary_error_max':maxerr,'surface_source_balance_max':max(balance),'reciprocity_residual':sym,
        'minimum_symmetric_eigenvalue':float(eig.min()),'condition':float(s[0]/s[-1]),'retained_singular_values':int(keep.sum()),
        'centre':centre.tolist(),'orientation_matrix':Q.tolist()}
