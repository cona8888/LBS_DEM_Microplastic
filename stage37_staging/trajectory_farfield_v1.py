"""Far-field trajectory bound with an explicit near-grain applicability stop.

This module never treats entry into the unqualified clearance region as retention.
It provides a release lower bound and an unresolved-censored upper bound only.
"""
import time
import numpy as np
from scipy.optimize import minimize_scalar
import transport_contact as model

def clearance_ratio_at(geometry,x,p,a,b,search_extra=0.0):
    ids=geometry.tree.query_ball_point(np.mod(x,geometry.L),geometry.r.max()+a+search_extra)
    best=np.inf
    for k in ids:
        d=geometry.c[k]-x; d-=geometry.L*np.round(d/geometry.L); c=x+d
        gap,_,_=model.ellipsoid_grain_contact(x,p,a,b,c,geometry.r[k])
        best=min(best,gap/geometry.r[k])
    return float(best)

def swept_clearance_ratio(geometry,x,p,v,a,b,dt,search_extra=0.0):
    travel=np.linalg.norm(v[:3])*dt
    ids=geometry.tree.query_ball_point(np.mod(x,geometry.L),geometry.r.max()+a+travel+search_extra)
    best=np.inf
    for k in ids:
        d=geometry.c[k]-x; d-=geometry.L*np.round(d/geometry.L); c=x+d
        if abs(a-b)<1e-13*a:
            disp=v[:3]*dt; den=float(disp@disp)
            q=float(np.clip(d@disp/den,0,1)) if den else 0.0
            gap=np.linalg.norm(x+q*disp-c)-a-geometry.r[k]
        else:
            def f(q):
                xx,pp=model.advance_pose(x,p,v,a,q*dt)
                return model.ellipsoid_grain_contact(xx,pp,a,b,c,geometry.r[k])[0]
            gap=min(f(0.0),f(1.0))
            for lo,hi in zip(np.linspace(0,1,5)[:-1],np.linspace(0,1,5)[1:]):
                opt=minimize_scalar(f,bounds=(lo,hi),method='bounded',options={'xatol':1e-8})
                if not opt.success: raise RuntimeError('clearance minimization failed')
                gap=min(gap,float(opt.fun))
        best=min(best,gap/geometry.r[k])
    return float(best)

def integrate(field,geometry,x,p,a,b,mu,outlet,horizon,clearance_cutoff=0.2,
              displacement_fraction=0.1,angle_limit=0.02,max_dt=np.inf,
              max_steps=300000,wall_budget=120.0):
    """Integrate a density-matched passive body until passage or censoring."""
    x=model.finite(x).copy(); p=model.unit(p); t=0.0; n=0; rejected=0
    started=time.perf_counter(); minimum=np.inf; history=[]
    def finish(status,reason=None,bracket=None):
        return {'status':status,'reason':reason,'time_s':t,'event_time_bracket_s':bracket,
                'position_m':x.tolist(),'orientation':p.tolist(),'steps':n,'rejected':rejected,
                'minimum_clearance_ratio':None if not np.isfinite(minimum) else minimum,
                'runtime_seconds':time.perf_counter()-started,'history':history}
    try:
        while t<horizon:
            if n>=max_steps or time.perf_counter()-started>wall_budget:
                return finish('incomplete_budget')
            search_extra=clearance_cutoff*geometry.r.max()
            current=clearance_ratio_at(geometry,x,p,a,b,search_extra)
            minimum=min(minimum,current)
            if current<=clearance_cutoff:
                return finish('unresolved_near_wall','outside qualified far-field mobility domain',[t,t])
            u,g=field.sample(x)
            v,_=model.free_motion(p,g,u,a,b,mu,1.0,1.0,[0,0,0])
            speed=np.linalg.norm(v[:3]); omega=np.linalg.norm(v[3:])/a
            dt=min(max_dt,horizon-t,displacement_fraction*b/max(speed,1e-30),angle_limit/max(omega,1e-30))
            if not np.isfinite(dt) or dt<=0: raise RuntimeError('invalid adaptive timestep')
            crossed=False
            for _ in range(30):
                swept=swept_clearance_ratio(geometry,x,p,v,a,b,dt,search_extra)
                if swept>clearance_cutoff: break
                if speed*dt<=1e-4*b and omega*dt<=1e-5:
                    crossed=True; break
                dt*=0.5; rejected+=1
            if crossed:
                minimum=min(minimum,swept)
                return finish('unresolved_near_wall','crossed qualified clearance boundary',[t,t+dt])
            minimum=min(minimum,swept)
            event=model.linear_pose_exit_time(x,p,v,a,b,outlet,dt)
            if event is not None:
                x,p=model.advance_pose(x,p,v,a,event); t+=event; n+=1
                return finish('full_window_exit')
            x,p=model.advance_pose(x,p,v,a,dt); t+=dt; n+=1
            if n%250==0: history.append([t,*x,*p,minimum])
        return finish('present_at_horizon')
    except (ValueError,FloatingPointError,RuntimeError,np.linalg.LinAlgError) as exc:
        kind='unresolved_field' if 'mixed fluid/solid' in str(exc) else 'numerical_failure'
        return finish(kind,str(exc))
