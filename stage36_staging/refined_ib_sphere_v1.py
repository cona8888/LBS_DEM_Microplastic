"""Stage36M adapter: variable relaxation and fixed independent probe cloud."""
import time
import numpy as np
from scipy.sparse import csr_matrix
import immersed_interface_v1 as ib
from moving_wall_reference_v1 import equilibrium
from body_link_extractor_v1 import C

def surface(R,count,phase=0.):
    j=np.arange(count);z=1-2*(j+.5)/count;theta=j*np.pi*(3-np.sqrt(5))+phase
    return R*np.column_stack((np.sqrt(1-z*z)*np.cos(theta),np.sqrt(1-z*z)*np.sin(theta),z))

def matrix(X,n):
    ids,w,_=ib.stencil(X,n,1.);J=csr_matrix((w.ravel(),(np.repeat(np.arange(len(X)),64),ids.ravel())),shape=(len(X),n**3))
    return J

def trilinear(field,X,n):
    a=X-.5;base=np.floor(a).astype(int);s=a-base;out=np.zeros((len(X),field.shape[1]))
    if np.any(base<0) or np.any(base+1>=n):raise ValueError('interior quadrature at outer seam')
    for i in (0,1):
        for j in (0,1):
            for k in (0,1):
                b=np.array([i,j,k]);w=np.prod(np.where(b,s,1-s),axis=1);idx=np.ravel_multi_index((base+b).T,(n,n,n));out+=field[idx]*w[:,None]
    return out

def interior(f,centre,R,fine=False):
    n=f.shape[1];flat=f.reshape(19,-1);body,v=ib.sphere_quadrature(R,8,16,32) if fine else ib.sphere_quadrature(R)
    fields=np.column_stack((flat.sum(axis=0),(C.T@flat).T));tot=v@trilinear(fields,body+centre,n)
    return float(tot[0]),tot[1:]

def project(f,J,U,enabled=True):
    flat=f.reshape(19,-1);rho=flat.sum(axis=0);u=(C.T@flat).T/rho[:,None];rhs=np.tile(U,(J.shape[0],1))-J@u
    A=(J.multiply(1/rho)@J.T).toarray();cond=float(np.linalg.cond(A))
    if not np.isfinite(cond) or cond>1e10:raise ValueError('ill-conditioned interface')
    lam=np.linalg.solve(A,rhs) if enabled else np.zeros_like(rhs);g=J.T@lam;up=u+g/rho[:,None]
    new=flat+equilibrium(rho,up.T)-equilibrium(rho,u.T)
    slip=float(np.max(np.abs(J@up-U)))
    return new.reshape(f.shape),lam,g,slip,cond

def step(f,centre,R,U,count,enabled=True,capture=False,tau=.8):
    if tau not in (.8,.65,.575):raise ValueError("outside frozen relaxation plan")
    n=f.shape[1]
    if f.shape!=(19,n,n,n) or n not in (12,16,24) or not np.isfinite(f).all() or np.any(f<=0):raise ValueError('invalid flow state')
    U=np.asarray(U,float)
    if U.shape!=(3,) or not np.isfinite(U).all() or np.linalg.norm(U)>.01:raise ValueError('invalid prescribed speed')
    flat=f.reshape(19,-1);rho=flat.sum(axis=0);u=C.T@flat/rho;post=(flat-(flat-equilibrium(rho,u))/tau).reshape(f.shape)
    streamed=np.stack([np.roll(post[k],tuple(C[k]),axis=(0,1,2)) for k in range(19)])
    if np.any(streamed<=0):raise ValueError('collision positivity')
    X=surface(R,count)+centre+U;J=matrix(X,n);new,lam,g,slip,cond=project(streamed,J,U,enabled)
    if not np.isfinite(new).all() or np.any(new<=0):raise ValueError('impulse positivity')
    nf=new.reshape(19,-1);rn=nf.sum(axis=0);un=(C.T@nf).T/rn[:,None]
    probes=matrix(surface(R,256,.37)+centre+U,n);probe=float(np.max(np.abs(probes@un-U)))
    m0=float(f.sum());m1=float(new.sum());p0=(C.T@flat).sum(axis=1);p1=(C.T@nf).sum(axis=1)
    mi0,pi0=interior(f,centre,R);mi1,pi1=interior(new,centre+U,R);impulse=lam.sum(axis=0);F=-impulse+pi1-pi0
    row={'centre_before':centre.tolist(),'centre_after':(centre+U).tolist(),'mass_before':m0,'mass_after':m1,'interior_mass_before':mi0,'interior_mass_after':mi1,
         'exterior_mass_before':m0-mi0,'exterior_mass_after':m1-mi1,'momentum_before':p0.tolist(),'momentum_after':p1.tolist(),
         'interior_momentum_before':pi0.tolist(),'interior_momentum_after':pi1.tolist(),'force_on_fluid':impulse.tolist(),'force_candidate':F.tolist(),
         'momentum_ledger_residual':(p1-p0-impulse).tolist(),'marker_slip':slip,'probe_slip':probe,'condition_number':cond,
         'density_error':float(np.max(np.abs(rn-1))),'velocity_error_from_comotion':float(np.max(np.abs(un-U))),'minimum_population':float(new.min())}
    extra={'old':f,'streamed':streamed,'new':new,'centre':centre,'velocity':U,'markers':X,'marker_impulses':lam,'grid_impulse':g} if capture else None
    return new,row,extra
