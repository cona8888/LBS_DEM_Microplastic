"""CPU D3Q19 [q,x,y,z] moving sphere; uniform-flow verification only."""
import time
import numpy as np
from body_link_extractor_v1 import C,OPP
from moving_wall_reference_v1 import equilibrium,W64


def coordinates(n):return np.indices((n,n,n)).reshape(3,-1).T.astype(float)+.5


def fluid_mask(x,centre,radius):
    centre=np.asarray(centre,dtype=float)
    if centre.shape!=(3,) or not np.isfinite(centre).all() or not np.isfinite(radius) or radius<=0:raise ValueError('invalid sphere')
    return np.sum((x-centre)**2,axis=1)>radius**2


def intersection(x,c,centre,radius):
    r=x-centre;dot=r@c;cc=float(c@c);disc=dot*dot-cc*(np.sum(r*r,axis=1)-radius**2)
    if cc==0 or np.any(disc<0):raise ValueError('ray misses sphere')
    q=(dot-np.sqrt(disc))/cc
    if not np.isfinite(q).all() or np.any(q<=0) or np.any(q>1+1e-12):raise ValueError('intersection outside link')
    return q


def reflect(outgoing,incoming_post,far_outgoing,k,q,U):
    if k not in range(1,19) or np.any(q<=0) or np.any(q>1+1e-12):raise ValueError('invalid bounce link')
    correction=6*W64[k]*float(C[k]@U)
    near=2*q*outgoing+(1-2*q)*far_outgoing+correction
    far=(outgoing+correction)/(2*q)+(2*q-1)*incoming_post/(2*q)
    return np.where(q<=.5,near,far)


def step(f,x,centre,radius,U,capture=False):
    n=f.shape[1]
    if f.shape!=(19,n,n,n) or n not in (12,16,24):raise ValueError('bounded cubic grid required')
    U=np.asarray(U,dtype=float)
    if U.shape!=(3,) or not np.isfinite(U).all() or np.linalg.norm(U)>.01:raise ValueError('invalid speed')
    if np.any(centre-radius<=1) or np.any(centre+radius>=n-1):raise ValueError('sphere too close to periodic seam')
    a=fluid_mask(x,centre,radius);shape=(n,n,n);am=a.reshape(shape);flat=f.reshape(19,-1)
    if not np.isfinite(f).all() or np.any(flat[:,a]<=0) or np.any(flat[:,~a]!=0):raise ValueError('invalid populations')
    rho=flat[:,a].sum(axis=0);u=(C.T@flat[:,a])/rho
    post=np.zeros_like(flat);post[:,a]=flat[:,a]-(flat[:,a]-equilibrium(rho,u))/.8
    if np.any(post[:,a]<=0):raise ValueError('collision positivity failed')
    cp=(C.T@(post-flat)).sum(axis=1);cm=float(post.sum()-flat.sum());post=post.reshape(f.shape)
    nxt=np.zeros_like(f);boundary_mass=0.;J=np.zeros(3);T=np.zeros(3);link_count=0;captured=[]
    for k,c in enumerate(C):
        pulled=np.roll(post[k],tuple(c),axis=(0,1,2));nxt[k,am]=pulled[am]
        if k==0:continue
        selected=am&np.roll(~am,tuple(c),axis=(0,1,2));ids=np.flatnonzero(selected)
        if not len(ids):continue
        q=intersection(x[ids],c,centre,radius)
        far=np.roll(post[OPP[k]],tuple(-c),axis=(0,1,2)).ravel()[ids]
        far_fluid=np.roll(am,tuple(-c),axis=(0,1,2)).ravel()[ids]
        if np.any((q<=.5)&~far_fluid):raise ValueError('missing interpolation donor')
        outgoing=post[OPP[k]].ravel()[ids];incoming=reflect(outgoing,post[k].ravel()[ids],far,k,q,U)
        nxt[k].ravel()[ids]=incoming
        packet=-(outgoing+incoming)[:,None]*c
        boundary_mass+=float(np.sum(incoming-outgoing));J+=packet.sum(axis=0)
        T+=np.cross(x[ids]-q[:,None]*c-centre,packet).sum(axis=0);link_count+=len(ids)
        if capture:captured.append(np.column_stack((np.full(len(ids),k),ids,q,outgoing,incoming)))
    intermediate=nxt.reshape(19,-1).copy();b=fluid_mask(x,centre+U,radius);ret=(a&b).reshape(shape)
    added=np.flatnonzero(b&~a);removed=np.flatnonzero(a&~b);nf=nxt.reshape(19,-1);stencils=[]
    for j in added:
        point=np.array(np.unravel_index(j,shape));values=[]
        for c in C[1:]:
            p1=tuple((point+c)%n);p2=tuple((point+2*c)%n)
            if ret[p1] and ret[p2]:
                j1=np.ravel_multi_index(p1,shape);j2=np.ravel_multi_index(p2,shape)
                values.append(2*intermediate[:,j1]-intermediate[:,j2]);stencils.append((int(j),int(j1),int(j2)))
        if not values:raise ValueError('no two-point retained refill ray')
        nf[:,j]=np.mean(values,axis=0)
    removed_p=(C.T@intermediate[:,removed]).T;added_p=(C.T@nf[:,added]).T
    Js=removed_p.sum(axis=0)-added_p.sum(axis=0)
    Ts=np.cross(x[removed]-centre,removed_p).sum(axis=0)-np.cross(x[added]-centre,added_p).sum(axis=0)
    sm=float(nf[:,added].sum()-intermediate[:,removed].sum());nf[:,~b]=0
    if not np.isfinite(nxt).all() or np.any(nf[:,b]<=0):raise ValueError('boundary/refill positivity failed')
    p0=(C.T@flat).sum(axis=1);p1=(C.T@nf).sum(axis=1);m0=float(flat.sum());m1=float(nf.sum())
    rho=nf[:,b].sum(axis=0);u=(C.T@nf[:,b])/rho
    row={'centre_before':centre.tolist(),'centre_after':(centre+U).tolist(),'fluid_nodes_before':int(a.sum()),'fluid_nodes_after':int(b.sum()),
         'mass_before':m0,'mass_after':m1,'momentum_before':p0.tolist(),'momentum_after':p1.tolist(),
         'collision_mass':cm,'collision_momentum':cp.tolist(),'boundary_mass':boundary_mass,'status_mass':sm,
         'boundary_impulse':J.tolist(),'status_impulse':Js.tolist(),'traction_candidate':(J+Js).tolist(),
         'boundary_torque':T.tolist(),'status_torque':Ts.tolist(),
         'mass_ledger_residual':m1-m0-cm-boundary_mass-sm,'momentum_ledger_residual':(p1-p0-cp+J+Js).tolist(),
         'added_cells':len(added),'removed_cells':len(removed),'links':link_count,
         'rho_max_error':float(np.max(np.abs(rho-1))),'u_max_error':float(np.max(np.abs(u-U[:,None])))}
    extra={'intermediate':intermediate.reshape(f.shape),'added_indices':added,'removed_indices':removed,
           'refill_stencils':np.asarray(stencils,dtype=int).reshape(-1,3),'links':np.concatenate(captured) if captured else np.empty((0,5))} if capture else None
    return nxt,row,extra


def run(n,direction=1,phase=0.,deadline=None):
    if n not in (12,16,24) or direction not in (-1,0,1) or phase not in (0.,.5):raise ValueError('outside benchmark plan')
    x=coordinates(n);centre0=np.array([n/2+.13+phase,n/2+.17,n/2+.19]);R=n/5;U=np.array([direction*.08/n,0,0])
    a=fluid_mask(x,centre0,R);f=np.zeros((19,len(x)));f[:,a]=equilibrium(np.ones(a.sum()),np.tile(U[:,None],(1,a.sum())))
    f=f.reshape((19,n,n,n));initial=f.copy();history=[];transition={};M0=float(f.sum());N0=int(a.sum())
    for t in range(n*n):
        if deadline is not None and time.monotonic()>deadline:raise TimeoutError('bounded CPU flow cap')
        centre=centre0+t*U
        changes=not np.array_equal(fluid_mask(x,centre,R),fluid_mask(x,centre+U,R))
        capture=changes and not transition
        previous=f.copy() if capture else None
        f,row,extra=step(f,x,centre,R,U,capture)
        row.update(step=t+1,mass_relative_drift=abs(row['mass_after']-M0)/M0,
                   binary_volume_residual_relative=abs(row['mass_after']-M0-(row['fluid_nodes_after']-N0))/M0)
        history.append(row)
        if capture:transition={'old':previous,'new':f.copy(),'centre':centre,'velocity':U,'radius':np.array(R),'step':np.array(t+1),**extra}
    metrics={'max_mass_relative_drift':max(r['mass_relative_drift'] for r in history),
             'max_binary_volume_residual_relative':max(r['binary_volume_residual_relative'] for r in history),
             'max_density_error':max(r['rho_max_error'] for r in history),'max_velocity_error':max(r['u_max_error'] for r in history),
             'max_mass_ledger_relative':max(abs(r['mass_ledger_residual'])/M0 for r in history),
             'max_momentum_ledger_relative':max(np.max(np.abs(r['momentum_ledger_residual']))/M0 for r in history),
             'max_boundary_impulse':max(np.max(np.abs(r['boundary_impulse'])) for r in history),
             'max_traction_candidate':max(np.max(np.abs(r['traction_candidate'])) for r in history),
             'max_node_count_change':max(abs(r['fluid_nodes_after']-N0) for r in history),
             'cover_uncover_steps':sum(r['added_cells']+r['removed_cells']>0 for r in history)}
    gates={'uniform_density':metrics['max_density_error']<=1e-10,'uniform_velocity':metrics['max_velocity_error']<=1e-10,
           'mass_ledger':metrics['max_mass_ledger_relative']<=1e-12,'momentum_ledger':metrics['max_momentum_ledger_relative']<=1e-12,
           'global_mass':metrics['max_mass_relative_drift']<=1e-6,'zero_force_candidate':metrics['max_traction_candidate']<=1e-9}
    result={'n':n,'direction':direction,'phase_lu':phase,'radius_lu':R,'velocity_lu':U.tolist(),'steps':n*n,
            'initial_mass':M0,'initial_fluid_nodes':N0,'analytical_fluid_volume_lu':n**3-4*np.pi*R**3/3,
            **metrics,'gates':gates,'passed':all(gates.values())}
    states={'initial':initial,'final':f,'centre_initial':centre0,'centre_final':centre0+n*n*U}
    return result,history,states,transition
