"""Isolated local mask-transition candidates; not a moving-body flow solver."""
import numpy as np
from body_link_extractor_v1 import C

FACE=np.array([[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]],dtype=int)


def validate(f,a,b):
    f=np.asarray(f,dtype=float);a=np.asarray(a);b=np.asarray(b)
    if a.ndim!=3 or a.dtype!=bool or b.dtype!=bool or b.shape!=a.shape:
        raise ValueError('expected equally shaped 3D boolean fluid masks')
    if a.size>32768 or min(a.shape)<3 or f.shape!=(19,)+a.shape:
        raise ValueError('bounded D3Q19 grid required')
    if not np.isfinite(f).all() or np.any(f[:,a]<=0) or np.any(f[:,~a]!=0):
        raise ValueError('positive fluid and exactly zero solid populations required')
    return f,a,b


def neighbours(index,mask,distance=1):
    p=np.array(np.unravel_index(index,mask.shape))
    result=[]
    for d in FACE:
        q=p+distance*d
        if np.all(q>=0) and np.all(q<mask.shape) and mask[tuple(q)]:
            result.append(int(np.ravel_multi_index(tuple(q),mask.shape)))
    return result


def ae6(f,a,b):
    f,a,b=validate(f,a,b);ret=a&b
    out=f.copy();out[:,~b]=0;flat=f.reshape(19,-1);nf=out.reshape(19,-1)
    rays=[]
    for j in np.flatnonzero(b&~a):
        p=np.array(np.unravel_index(j,a.shape));values=[]
        for d in FACE:
            q=p+d;r=p+2*d
            if np.all(r>=0) and np.all(r<a.shape) and ret[tuple(q)] and ret[tuple(r)]:
                qf=int(np.ravel_multi_index(tuple(q),a.shape));rf=int(np.ravel_multi_index(tuple(r),a.shape))
                values.append(2*flat[:,qf]-flat[:,rf]);rays.append((j,qf,rf))
        if not values: raise ValueError('AE6: no retained-fluid two-point ray')
        nf[:,j]=np.mean(values,axis=0)
    if np.any(out[:,b]<=0) or not np.isfinite(out).all():raise ValueError('AE6: inadmissible extrapolation')
    return out,np.asarray(rays,dtype=np.int64).reshape(-1,3)


def pool6(f,a,b):
    f,a,b=validate(f,a,b);ret=a&b;added=b&~a;removed=a&~b
    flat=f.reshape(19,-1);mid=np.zeros_like(flat);mid[:,ret.ravel()]=flat[:,ret.ravel()]
    edges=[];amounts=[]
    for i in np.flatnonzero(removed):
        targets=neighbours(i,ret)
        if not targets:raise ValueError('POOL6: covered cell lacks retained neighbour')
        share=flat[:,i]/len(targets)
        for j in targets:
            mid[:,j]+=share;edges.append((i,j));amounts.append(share.copy())
    donors={}
    for j in np.flatnonzero(added):
        hosts=neighbours(j,ret)
        if not hosts:raise ValueError('POOL6: exposed cell lacks retained neighbour')
        for i in hosts:donors.setdefault(i,[]).append(j)
    out=mid.copy()
    for i,targets in donors.items():
        share=mid[:,i]/(len(targets)+1)
        out[:,i]=share
        for j in targets:
            out[:,j]+=share;edges.append((i,j));amounts.append(share.copy())
    out=out.reshape(f.shape)
    if np.any(out[:,b]<=0) or np.any(out[:,~b]!=0):raise ValueError('POOL6: invalid output')
    return out,np.asarray(edges,dtype=np.int64).reshape(-1,2),np.asarray(amounts).reshape(-1,19)


def moments(f):
    flat=f.reshape(19,-1);rho=flat.sum(axis=0);p=C.T@flat
    return rho,p


def coordinates(shape):
    return np.indices(shape).reshape(3,-1).T.astype(float)+.5


def angular(f,origin=(0,0,0)):
    _,p=moments(f)
    return np.cross(coordinates(f.shape[1:])-origin,p.T).sum(axis=0)


def ledger_check(old,new,edges,amounts):
    # Independent scalar reconstruction, not the pooling execution path.
    reconstructed=old.reshape(19,-1).copy();x=coordinates(old.shape[1:]);dl=np.zeros(3)
    for (i,j),packet in zip(edges,amounts):
        for q in range(19):
            reconstructed[q,i]-=packet[q];reconstructed[q,j]+=packet[q]
        momentum=np.array([sum(float(packet[q])*int(C[q,k]) for q in range(19)) for k in range(3)])
        dl+=np.cross(x[j]-x[i],momentum)
    return {'reconstruction_max_error':float(np.max(np.abs(reconstructed-new.reshape(19,-1)))),
            'max_edge_length_lu':float(max((np.linalg.norm(x[j]-x[i]) for i,j in edges),default=0)),
            'orbital_angular_change_lu':(angular(new)-angular(old)).tolist(),
            'ledger_angular_residual_lu':(angular(new)-angular(old)-dl).tolist()}
