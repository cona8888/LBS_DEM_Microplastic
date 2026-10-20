"""Stage36I: explicit incoming time level; other Stage36H operators unchanged."""
import time
import numpy as np
from body_link_extractor_v1 import C,OPP
from moving_wall_reference_v1 import equilibrium,W64

PLUS=np.flatnonzero(C[:,1]>0);MINUS=np.flatnonzero(C[:,1]<0);KEEP=np.flatnonzero(C[:,1]==0)


def boundary(f,post,j,inward,q,uw,incoming_level="old"):
    if incoming_level not in ("old","post"):raise ValueError("unknown incoming time level")
    if not np.isfinite(q) or not 0<=q<=1:raise ValueError('wall distance outside link')
    uw=np.asarray(uw,dtype=float)
    if uw.shape!=(3,) or not np.isfinite(uw).all() or np.linalg.norm(uw)>.03:raise ValueError('invalid wall velocity')
    if inward not in (-1,1):raise ValueError('invalid inward sign')
    k=PLUS if inward==1 else MINUS;o=OPP[k];out=post[o,j]
    correction=6*W64[k]*(C[k]@uw)
    if q<=.5:incoming=2*q*out+(1-2*q)*post[o,j+inward]+correction
    else:incoming=(out+correction)/(2*q)+(2*q-1)*(f if incoming_level=="old" else post)[k,j]/(2*q)
    if np.any(incoming<=0) or not np.isfinite(incoming).all():raise ValueError('boundary populations invalid')
    # Flux actually removed/inserted by this numerical boundary, not an assumed
    # pressure/viscous force decomposition.
    impulse=(out[:,None]*C[o]-incoming[:,None]*C[k]).sum(axis=0)
    return k,incoming,float(np.sum(incoming-out)),impulse


def mask(y,lower,n):return (y>lower)&(y<lower+n)


def advance(f,y,lower,n,V,U,incoming_level="old"):
    a=mask(y,lower,n);idx=np.flatnonzero(a)
    if len(idx)!=n or f.shape!=(19,len(y)) or np.any(f[:,~a]!=0) or not np.isfinite(f).all() or np.any(f[:,a]<=0):raise ValueError('invalid initial state')
    rho=f[:,a].sum(axis=0);u=(C.T@f[:,a])/rho
    post=np.zeros_like(f);post[:,a]=f[:,a]-(f[:,a]-equilibrium(rho,u))/.8
    if np.any(post[:,a]<=0):raise ValueError('collision positivity failure')
    collision_mass=float(post.sum()-f.sum());collision_p=(C.T@(post-f)).sum(axis=1)
    nxt=np.zeros_like(f);lo,hi=idx[0],idx[-1]
    nxt[np.ix_(KEEP,idx)]=post[np.ix_(KEEP,idx)]
    nxt[np.ix_(PLUS,idx[1:])]=post[np.ix_(PLUS,idx[:-1])]
    nxt[np.ix_(MINUS,idx[:-1])]=post[np.ix_(MINUS,idx[1:])]
    boundary_mass=np.zeros(2);boundary_j=np.zeros((2,3))
    for side,j,d,q,uw in [(0,lo,1,y[lo]-lower,[0,V,0]),(1,hi,-1,lower+n-y[hi],[U,V,0])]:
        k,inc,boundary_mass[side],boundary_j[side]=boundary(f,post,j,d,q,uw,incoming_level);nxt[k,j]=inc
    b=mask(y,lower+V,n);ret=a&b;add=np.flatnonzero(b&~a);remove=np.flatnonzero(a&~b)
    if b.sum()!=n or len(add)!=len(remove) or len(add)>1:raise ValueError('unsupported volume/mask change')
    status_mass=np.zeros(2);status_j=np.zeros((2,3));stencils=[]
    intermediate=nxt.copy()
    for j in add:
        d=1 if j<lo else -1;side=0 if d==1 else 1
        if not (ret[j+d] and ret[j+2*d]):raise ValueError('refill missing two retained donors')
        nxt[:,j]=2*intermediate[:,j+d]-intermediate[:,j+2*d]
        status_mass[side]+=nxt[:,j].sum();status_j[side]-=C.T@nxt[:,j]
        stencils.append((int(j),int(j+d),int(j+2*d)))
    for j in remove:
        side=0 if j==lo else 1
        status_mass[side]-=intermediate[:,j].sum();status_j[side]+=C.T@intermediate[:,j]
    nxt[:,~b]=0
    if np.any(nxt[:,b]<=0) or not np.isfinite(nxt).all():raise ValueError('refill positivity failure')
    dm=float(nxt.sum()-f.sum());dp=(C.T@nxt).sum(axis=1)-(C.T@f).sum(axis=1)
    row={'mass_before':float(f.sum()),'mass_after':float(nxt.sum()),'collision_mass':collision_mass,
         'collision_momentum':collision_p.tolist(),'boundary_mass':boundary_mass.tolist(),
         'status_mass':status_mass.tolist(),'boundary_impulse':boundary_j.tolist(),'status_impulse':status_j.tolist(),
         'momentum_before':(C.T@f).sum(axis=1).tolist(),'momentum_after':(C.T@nxt).sum(axis=1).tolist(),
         'mass_ledger_residual':dm-collision_mass-boundary_mass.sum()-status_mass.sum(),
         'momentum_ledger_residual':(dp-collision_p+boundary_j.sum(axis=0)+status_j.sum(axis=0)).tolist(),
         'refill_stencils':stencils,'covered_indices':remove.tolist(),'fluid_nodes':int(b.sum())}
    return nxt,row


def run(n,V,U,deadline=None,incoming_level="old",phase=0.):
    if incoming_level not in ("old","post") or not np.isfinite(phase) or phase not in (0.,.25,.5,.75):raise ValueError("outside variant/phase domain")
    if type(n) is not int or n not in (8,16,32) or not np.isfinite(V+U) or max(abs(V),abs(U))>.01:raise ValueError('outside benchmark domain')
    y=np.arange(4*n)+.5;L0=n+np.sqrt(2)/10+phase;a=mask(y,L0,n)
    f=np.zeros((19,len(y)));vel=np.zeros((3,n));vel[0]=U*(y[a]-L0)/n;vel[1]=V
    f[:,a]=equilibrium(np.ones(n),vel);initial=f.copy();steps=10*n*n;history=[]
    maxmass=maxrho=0.;event_states=[]
    for t in range(steps):
        if t%128==0 and deadline is not None and time.monotonic()>deadline:raise TimeoutError('bounded benchmark cap')
        L=L0+V*t
        f,row=advance(f,y,L,n,V,U,incoming_level);row.update(step=t+1,lower=L0+V*(t+1))
        b=mask(y,row['lower'],n);rho=f[:,b].sum(axis=0)
        maxmass=max(maxmass,abs(float(f.sum())/n-1));maxrho=max(maxrho,float(np.max(np.abs(rho-1))))
        row['mass_relative_drift']=abs(float(f.sum())/n-1);row['density_max_error']=float(np.max(np.abs(rho-1)))
        current_u=(C.T@f[:,b])/rho
        row['ux_normalized_error']=float(np.max(np.abs(current_u[0]-U*(y[b]-row['lower'])/n))/max(abs(U),.001))
        history.append(row)
        if row['refill_stencils']:event_states.append(f.copy())
    b=mask(y,L0+V*steps,n);rho=f[:,b].sum(axis=0);u=(C.T@f[:,b])/rho;s=(y[b]-L0-V*steps)/n
    window=int(round(5/abs(V))) if V else 500
    if window>steps:raise ValueError('insufficient traction averaging cycles')
    late=history[-window:];jb=np.mean([r['boundary_impulse'] for r in late],axis=0);js=np.mean([r['status_impulse'] for r in late],axis=0);j=jb+js
    shear=.1*U/n;shear_error=float(np.max(np.abs(j[:,0]-[shear,-shear])))
    result={'incoming_level':incoming_level,'phase_offset_lu':phase,'late_window_max_ux_error':max(r['ux_normalized_error'] for r in late),'n':n,'V_lu':V,'U_lu':U,'steps':steps,'refill_events':len(event_states),'traction_window_steps':window,
            'max_mass_relative_drift':maxmass,'max_density_error':maxrho,
            'final_ux_normalized_error':float(np.max(np.abs(u[0]-U*s))/max(abs(U),.001)),
            'final_uy_max_error_lu':float(np.max(np.abs(u[1]-V))),
            'max_mass_ledger_residual':max(abs(r['mass_ledger_residual']) for r in history),
            'max_momentum_ledger_residual':max(max(abs(v) for v in r['momentum_ledger_residual']) for r in history),
            'mean_boundary_impulse':jb.tolist(),'mean_status_impulse':js.tolist(),'mean_traction_candidate':j.tolist(),
            'expected_wall_x_traction':[shear,-shear],'wall_shear_absolute_error':shear_error,
            'wall_shear_relative_error':shear_error/abs(shear) if shear else None,
            'normal_traction_absolute_error':float(np.max(np.abs(j[:,1]-[-1/3,1/3]))),
            'y_over_H':s.tolist(),'ux_final':u[0].tolist(),'uy_final':u[1].tolist(),'rho_final':rho.tolist()}
    gates={'mass_ledger':result['max_mass_ledger_residual']<=1e-11,'momentum_ledger':result['max_momentum_ledger_residual']<=1e-11,
           'global_mass':maxmass<=1e-6,'density':maxrho<=.01,'ux_profile':result['final_ux_normalized_error']<=.02,
           'uy_profile':result['final_uy_max_error_lu']<=1e-5,'wall_shear':shear_error<=.05*abs(shear) if shear else shear_error<=1e-10,
           'normal_traction':result['normal_traction_absolute_error']<=.01,'constant_volume':all(r['fluid_nodes']==n for r in history)}
    if U==0:gates['uniform_exact']=bool(maxrho<=1e-10 and np.max(np.abs(u-np.array([[0],[V],[0]])))<=1e-10)
    result['gates']=gates;result['passed']=all(gates.values())
    return result,history,{'initial':initial,'final':f,'event_states':np.asarray(event_states),'y':y}
