"""Project CPU collide/stream/endpoint-impulse reference; not a validated IBM solver."""
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

def step(f,centre,R,U,count,enabled=True,capture=False):
    n=f.shape[1]
    if f.shape!=(19,n,n,n) or n not in (12,16,24) or not np.isfinite(f).all() or np.any(f<=0):raise ValueError('invalid flow state')
    U=np.asarray(U,float)
    if U.shape!=(3,) or not np.isfinite(U).all() or np.linalg.norm(U)>.01:raise ValueError('invalid prescribed speed')
    flat=f.reshape(19,-1);rho=flat.sum(axis=0);u=C.T@flat/rho;post=(flat-(flat-equilibrium(rho,u))/.8).reshape(f.shape)
    streamed=np.stack([np.roll(post[k],tuple(C[k]),axis=(0,1,2)) for k in range(19)])
    if np.any(streamed<=0):raise ValueError('collision positivity')
    X=surface(R,count)+centre+U;J=matrix(X,n);new,lam,g,slip,cond=project(streamed,J,U,enabled)
    if not np.isfinite(new).all() or np.any(new<=0):raise ValueError('impulse positivity')
    nf=new.reshape(19,-1);rn=nf.sum(axis=0);un=(C.T@nf).T/rn[:,None]
    probes=matrix(surface(R,2*count,.37)+centre+U,n);probe=float(np.max(np.abs(probes@un-U)))
    m0=float(f.sum());m1=float(new.sum());p0=(C.T@flat).sum(axis=1);p1=(C.T@nf).sum(axis=1)
    mi0,pi0=interior(f,centre,R);mi1,pi1=interior(new,centre+U,R);impulse=lam.sum(axis=0);F=-impulse+pi1-pi0
    row={'centre_before':centre.tolist(),'centre_after':(centre+U).tolist(),'mass_before':m0,'mass_after':m1,'interior_mass_before':mi0,'interior_mass_after':mi1,
         'exterior_mass_before':m0-mi0,'exterior_mass_after':m1-mi1,'momentum_before':p0.tolist(),'momentum_after':p1.tolist(),
         'interior_momentum_before':pi0.tolist(),'interior_momentum_after':pi1.tolist(),'force_on_fluid':impulse.tolist(),'force_candidate':F.tolist(),
         'momentum_ledger_residual':(p1-p0-impulse).tolist(),'marker_slip':slip,'probe_slip':probe,'condition_number':cond,
         'density_error':float(np.max(np.abs(rn-1))),'velocity_error_from_comotion':float(np.max(np.abs(un-U))),'minimum_population':float(new.min())}
    extra={'old':f,'streamed':streamed,'new':new,'centre':centre,'velocity':U,'markers':X,'marker_impulses':lam,'grid_impulse':g} if capture else None
    return new,row,extra

def run(n,direction=1,phase=0.,perturb=False,enabled=True,deadline=None):
    if n not in (12,16,24) or direction not in (-1,0,1) or phase not in (0.,.5):raise ValueError('outside frozen plan')
    count={12:32,16:56,24:128}[n];R=n/5;centre0=np.array([n/2+.13+phase,n/2+.17,n/2+.19]);U=np.array([direction*.08/n,0,0])
    g=(np.indices((n,n,n)).reshape(3,-1).T+.5);u=np.tile(U,(n**3,1));amp=.02/n
    if perturb:u[:,0]+=amp*np.sin(2*np.pi*g[:,1]/n)
    f=equilibrium(np.ones(n**3),u.T).reshape(19,n,n,n);initial=f.copy();M0=float(f.sum());mi0,_=interior(f,centre0,R);ME0=M0-mi0;history=[]
    for t in range(n*n):
        if deadline and time.monotonic()>deadline:raise TimeoutError('bounded CPU cap')
        f,row,extra=step(f,centre0+t*U,R,U,count,enabled,t==0)
        row.update(step=t+1,total_mass_relative_drift=abs(row['mass_after']-M0)/M0,exterior_mass_relative_drift=abs(row['exterior_mass_after']-ME0)/ME0)
        history.append(row)
        if t==0:transition=extra
    fine,_=interior(f,centre0+n*n*U,R,True);fine_error=abs(fine-history[-1]['interior_mass_after'])/ME0
    metrics={'max_total_mass_drift':max(r['total_mass_relative_drift'] for r in history),'max_exterior_mass_drift':max(r['exterior_mass_relative_drift'] for r in history),
             'max_momentum_ledger_relative':max(np.max(np.abs(r['momentum_ledger_residual']))/M0 for r in history),'max_marker_slip':max(r['marker_slip'] for r in history),
             'max_probe_slip_over_amplitude':max(r['probe_slip'] for r in history)/amp,'max_density_error':max(r['density_error'] for r in history),
             'max_velocity_error':max(r['velocity_error_from_comotion'] for r in history),'max_force_candidate':max(np.max(np.abs(r['force_candidate'])) for r in history),
             'max_condition_number':max(r['condition_number'] for r in history),'final_exterior_quadrature_discrepancy':fine_error,'minimum_population':min(r['minimum_population'] for r in history)}
    gates={'total_mass':metrics['max_total_mass_drift']<=1e-10,'exterior_mass_estimate':metrics['max_exterior_mass_drift']<=1e-6,'momentum_ledger':metrics['max_momentum_ledger_relative']<=1e-12,
           'marker_no_slip':metrics['max_marker_slip']<=1e-10,'density_health':metrics['max_density_error']<=.01,'quadrature_crosscheck':fine_error<=1e-6}
    if perturb:gates['probe_no_slip']=metrics['max_probe_slip_over_amplitude']<=.05
    else:gates.update(uniform_density=metrics['max_density_error']<=1e-10,uniform_velocity=metrics['max_velocity_error']<=1e-10,zero_force=metrics['max_force_candidate']<=1e-9)
    r={'n':n,'direction':direction,'phase':phase,'perturb':perturb,'interface_enabled':enabled,'marker_count':count,'radius_lu':R,'steps':n*n,'initial_total_mass':M0,'initial_exterior_mass':ME0,**metrics,'gates':gates,'passed':all(gates.values())}
    return r,history,{'initial':initial,'final':f,'centre_initial':centre0,'centre_final':centre0+n*n*U},transition
