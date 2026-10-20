"""Independent low-Re pair resistance for a fixed sphere and rigid ellipsoid.

The returned matrix maps generalized body velocity (U, a*omega) to the
generalized load exerted by the body on the fluid (F, T/a), with mu=1.
It is a verification/reference builder, not a trajectory-time solver.
"""
import sys
from pathlib import Path
import numpy as np
from scipy.linalg import svd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage36_staging'))
import sharp_stokes_mfs_v3 as mfs
import sharp_sphere_reference_v1 as sphere

def frame_from_axis(p):
    p=np.asarray(p,float); p/=np.linalg.norm(p)
    e=np.eye(3)[np.argmin(abs(p))]; q=np.cross(p,e); q/=np.linalg.norm(q)
    return np.column_stack((p,q,np.cross(p,q)))

def geometry(axes,gap,angle,n,source_fraction=.55):
    axes=np.asarray(axes,float); R=1.0; normal=np.array([0.,1.,0.])
    p=np.cos(angle)*normal+np.sin(angle)*np.array([1.,0.,0.]); Q=frame_from_axis(p)
    support=np.sqrt(np.sum((axes*(Q.T@normal))**2)); centre=normal*(R+support+gap)
    dirs=mfs.directions(n); boundary=mfs.directions(3*n)
    confocal=np.sqrt(axes**2-(1-source_fraction**2)*min(axes)**2)
    sources=np.vstack((.6*dirs,centre+(dirs*confocal)@Q.T))
    points=np.vstack((boundary,centre+(boundary*axes)@Q.T))
    return centre,Q,sources,points

def solve(axes,gap,angle,n=384,rtol=1e-12):
    axes=np.asarray(axes,float); a=float(axes[0]); centre,Q,sources,points=geometry(axes,gap,angle,n)
    A=mfs.kernel(points,sources,1.).transpose(0,2,1,3).reshape(18*n,6*n)
    left,s,right=svd(A,full_matrices=False); keep=s>s[0]*rtol
    rhs=np.zeros((6*n,3,6))
    for j in range(3):
        rhs[3*n:,:,j]=np.eye(3)[j]
        rhs[3*n:,:,j+3]=np.cross(np.eye(3)[j],points[3*n:]-centre)
    lam=(right[keep].T@((left[:,keep].T@rhs.reshape(18*n,6))/s[keep,None])).reshape(2*n,3,6)
    lever=sources[n:]-centre
    wrench=np.vstack((lam[n:].sum(axis=0),np.stack([np.cross(lever,lam[n:,:,j]).sum(axis=0) for j in range(6)],axis=1)))
    D=np.diag([1,1,1,1/a,1/a,1/a]); resistance=D@wrench@D
    # Boundary residual on independent surface points, all six motions.
    state={'sources':sources,'mu':1.}; evaluation,_w,_=sphere.surface_quadrature(1.,24,48)
    evals=(evaluation,centre+(evaluation*axes)@Q.T); maxerr=0.0
    for surf,is_body in ((evals[0],False),(evals[1],True)):
        for chunks in np.array_split(surf,8):
            pred=np.stack([mfs.velocity(state,{'lambda':lam[:,:,j],'far_velocity':np.zeros(3)},chunks) for j in range(6)],axis=2)
            target=np.zeros_like(pred)
            if is_body:
                for j in range(3): target[:,:,j]=np.eye(3)[j]
                for j in range(3): target[:,:,j+3]=np.cross(np.eye(3)[j],chunks-centre)
            maxerr=max(maxerr,float(np.linalg.norm(pred-target,axis=1).max()))
    # Net source strength is not a closed-system force residual: momentum is
    # transmitted to the unbounded far field. Reciprocity is the appropriate
    # operator-level consistency check here.
    sym=float(np.linalg.norm(resistance-resistance.T)/np.linalg.norm(resistance))
    eig=np.linalg.eigvalsh((resistance+resistance.T)/2)
    return resistance,{'boundary_error_max':maxerr,
        'reciprocity_residual':sym,'minimum_symmetric_eigenvalue':float(eig.min()),
        'condition':float(s[0]/s[-1]),'retained_singular_values':int(keep.sum()),
        'centre':centre.tolist(),'orientation_matrix':Q.tolist()}
