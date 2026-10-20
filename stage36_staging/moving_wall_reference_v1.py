"""CPU-only planar moving-wall reference and explicit mask-transition audit."""
import math
import time
import numpy as np
from body_link_extractor_v1 import C, OPP

W64=np.array([1/3]+[1/18]*6+[1/36]*12,dtype=float)


def moving_reflection(outgoing,q,wall_velocity,rho_wall=1.):
    f=np.asarray(outgoing,dtype=float); q=np.asarray(q)
    u=np.asarray(wall_velocity,dtype=float)
    if q.dtype.kind not in 'iu' or q.shape!=f.shape or np.any(q<1) or np.any(q>18): raise ValueError('invalid link directions')
    if u.shape!=(3,) or not np.isfinite(u).all() or np.linalg.norm(u)>.05: raise ValueError('invalid wall velocity')
    if not np.isfinite(rho_wall) or rho_wall<=0 or not np.isfinite(f).all() or np.any(f<=0): raise ValueError('invalid populations/density')
    incoming=f+6*W64[q]*rho_wall*(C[q]@u)
    if np.any(incoming<=0) or not np.isfinite(incoming).all(): raise ValueError('invalid reflected population')
    return incoming,-(f+incoming)[...,None]*C[q]


def equilibrium(rho,u):
    cu=C@u
    return W64[:,None]*rho*(1+3*cu+4.5*cu**2-1.5*np.sum(u*u,axis=0))


def analytic(s,theta):
    n=np.arange(1,101,dtype=float)[:,None]
    return s+(2/math.pi)*np.sum((-1.)**n*np.sin(n*math.pi*s)/n*np.exp(-n*n*math.pi**2*theta),axis=0)


def couette(n,top,bottom=0.,initial=0.,deadline=None):
    if type(n) is not int or not 4<=n<=32: raise ValueError('invalid grid size')
    if not all(np.isfinite(v) and abs(v)<=.02 for v in [top,bottom,initial]): raise ValueError('invalid velocity')
    f=equilibrium(np.ones(n),np.tile([[initial],[0.],[0.]],(1,n)))
    plus,minus=np.flatnonzero(C[:,1]>0),np.flatnonzero(C[:,1]<0)
    keep=np.flatnonzero(C[:,1]==0)
    tau=.8;nu=(tau-.5)/3;steps=round(2*n*n/nu)
    max_mass=max_momentum=0.;history=[];profiles={}; wall=None
    for step in range(1,steps+1):
        if step%256==0 and deadline is not None and time.monotonic()>deadline: raise TimeoutError('bounded CPU benchmark time cap')
        rho=f.sum(axis=0);u=(C.T@f)/rho
        before=(C.T@f).sum(axis=1)
        post=f-(f-equilibrium(rho,u))/tau
        nxt=np.empty_like(f)
        nxt[keep]=post[keep]
        nxt[plus,1:]=post[plus,:-1];nxt[minus,:-1]=post[minus,1:]
        bot_in,bot_imp=moving_reflection(post[OPP[plus],0],plus,[bottom,0,0])
        top_in,top_imp=moving_reflection(post[OPP[minus],-1],minus,[top,0,0])
        nxt[plus,0]=bot_in;nxt[minus,-1]=top_in
        wall=np.array([bot_imp.sum(axis=0),top_imp.sum(axis=0)])
        after=(C.T@nxt).sum(axis=1)
        residual=after-before+wall.sum(axis=0)
        max_momentum=max(max_momentum,float(np.max(np.abs(residual))))
        max_mass=max(max_mass,abs(float(nxt.sum())/n-1))
        if not np.isfinite(nxt).all() or np.any(nxt<=0): raise ValueError('numerical health failed')
        f=nxt
        if step in (round(.1*n*n/nu),steps):
            velocity=(C.T@f)/f.sum(axis=0);theta=nu*step/n**2
            profiles[str(round(theta,8))]=velocity[0].tolist()
            history.append({'step':step,'theta':theta,'wall_impulse_lu':wall.tolist(),'mass_relative_drift':abs(float(f.sum())/n-1)})
    final=(C.T@f)/f.sum(axis=0)
    s=(np.arange(n)+.5)/n;scale=max(abs(top-bottom),abs(top),1e-3)
    exact=bottom+(top-bottom)*s
    shear=nu*(top-bottom)/n
    expected_walls=np.array([shear,-shear])
    result={'n':n,'top_lu':top,'bottom_lu':bottom,'initial_lu':initial,'steps':steps,
            'max_mass_relative_drift':max_mass,'max_step_momentum_residual_lu':max_momentum,
            'final_profile_normalized_max_error':float(np.max(np.abs(final[0]-exact))/scale),
            'wall_shear_relative_error':float(np.max(np.abs(wall[:,0]-expected_walls))/max(abs(shear),1e-8)),
            'profiles':profiles,'history':history,'y_over_H':s.tolist()}
    if initial==0 and bottom==0 and top!=0:
        result['transient_normalized_rms_error']=float(np.sqrt(np.mean((np.array(profiles['0.1'])/top-analytic(s,.1))**2)))
    return result


def mask_change_audit(old,new,old_fluid,new_fluid,positions,origin):
    old,new=np.asarray(old,dtype=float),np.asarray(new,dtype=float)
    a,b=np.asarray(old_fluid),np.asarray(new_fluid)
    if old.ndim!=2 or old.shape[0]!=19 or new.shape!=old.shape or old.shape[1]>262144: raise ValueError('invalid population arrays')
    if a.dtype!=bool or b.dtype!=bool or a.shape!=(old.shape[1],) or b.shape!=a.shape: raise ValueError('invalid masks')
    x=np.asarray(positions,dtype=float);origin=np.asarray(origin,dtype=float)
    if x.shape!=(len(a),3) or origin.shape!=(3,) or not np.isfinite(x).all() or not np.isfinite(origin).all(): raise ValueError('invalid unwrapped coordinates')
    for f,fluid in [(old,a),(new,b)]:
        if not np.isfinite(f).all() or np.any(f[:,fluid]<=0) or np.any(f[:,~fluid]!=0): raise ValueError('invalid fluid/solid populations')
    if not np.array_equal(old[:,a&b],new[:,a&b]): raise ValueError('retained-fluid modification is outside this audit')
    removed=a&~b;added=~a&b
    pr=(C.T@old[:,removed]).T;pa=(C.T@new[:,added]).T
    impulse=pr.sum(axis=0)-pa.sum(axis=0)
    angular=np.cross(x[removed]-origin,pr).sum(axis=0)-np.cross(x[added]-origin,pa).sum(axis=0)
    dm=float(new[:,added].sum()-old[:,removed].sum());m0=float(old.sum())
    return {'removed_cells':int(removed.sum()),'added_cells':int(added.sum()),'uncompensated_mass_change_lu':dm,
            'mass_conserved':bool(abs(dm)<=1e-12*max(m0,1)), 'required_body_impulse_lu':impulse.tolist(),
            'required_body_angular_impulse_lu':angular.tolist(),
            'momentum_bookkeeping_residual':((C.T@new).sum(axis=1)-(C.T@old).sum(axis=1)+impulse).tolist()}


def require_conservative(audit):
    if not audit['mass_conserved']: raise ValueError('uncompensated fluid mass change: no refill scheme qualified')
