"""Adaptive contact trajectories with measured whole-body exit.

Periodic material and velocity continue across the measurement plane. The
observable is first full passage from an observation window, not column effluent.
Physical matrix runs must separately pass hydrodynamic applicability.
"""
import time
import numpy as np
from scipy.optimize import minimize_scalar
import transport_contact as m


def swept_gap(geometry,x,p,v,a,b,dt):
    """Broad-phase displacement envelope plus exact sphere segment distance.

    Rotating ellipsoids use bounded scalar minimization on four subintervals;
    angular step is limited by the integrator and results need refinement tests.
    """
    if not isinstance(geometry,m.GrainGeometry):
        # Test geometries provide their independent sweep.
        return geometry.swept_gap(x,p,v,a,b,dt)
    travel=np.linalg.norm(v[:3])*dt
    ids=geometry.tree.query_ball_point(np.mod(x,geometry.L),geometry.r.max()+a+travel)
    minimum=np.inf
    for k in ids:
        d=geometry.c[k]-x;d-=geometry.L*np.round(d/geometry.L);c=x+d
        if abs(a-b)<1e-13*a:
            disp=v[:3]*dt;den=disp@disp
            t=np.clip(d@disp/den,0,1) if den>0 else 0
            gap=np.linalg.norm(x+t*disp-c)-a-geometry.r[k]
        else:
            def fun(t):
                xx,pp=m.advance_pose(x,p,v,a,t)
                return m.ellipsoid_grain_contact(xx,pp,a,b,c,geometry.r[k])[0]
            gap=min(fun(0),fun(dt))
            for lo,hi in zip(np.linspace(0,dt,5)[:-1],np.linspace(0,dt,5)[1:]):
                opt=minimize_scalar(fun,bounds=(lo,hi),method='bounded',options={'xatol':max(dt*1e-8,1e-14)})
                if not opt.success:raise RuntimeError('swept-gap minimization failed')
                gap=min(gap,opt.fun)
        minimum=min(minimum,gap)
    return float(minimum)


def integrate(field,geometry,x,p,a,b,mu,rhop,rhof,gravity,friction,outlet,horizon,
              displacement_fraction=.1,angle_limit=.02,max_dt=1.,max_steps=200000,wall_budget=120.):
    x=m.finite(x).copy();p=m.unit(p);t=0.;start=time.perf_counter();n=0;rejected=0
    min_gap=np.inf;max_res=0.;max_force=0.;max_contacts=0;contact_steps=0;history=[];tol=1e-5*b
    def result(status,reason=None):
        return {'status':status,'reason':reason,'time':t,'position':x.tolist(),'orientation':p.tolist(),
                'steps':n,'rejected':rejected,'minimum_gap':None if not np.isfinite(min_gap) else min_gap,
                'max_contact_residual':max_res,'max_force_residual':max_force,'max_contacts':max_contacts,
                'contact_steps':contact_steps,'runtime_seconds':time.perf_counter()-start,'history':history}
    try:
        while t<horizon:
            if n>=max_steps or time.perf_counter()-start>wall_budget:return result('incomplete_budget')
            initial=geometry.contacts(x,p,a,b,0.)
            if initial and min(c[1] for c in initial)<-tol:raise RuntimeError('inadmissible penetration')
            u,g=field.sample(x);vf,M=m.free_motion(p,g,u,a,b,mu,rhop,rhof,gravity)
            speed=np.linalg.norm(vf[:3]);rot=np.linalg.norm(vf[3:])/a
            dt=min(max_dt,horizon-t,displacement_fraction*b/max(speed,1e-30),angle_limit/max(rot,1e-30))
            for attempt in range(30):
                # Broad active set includes contacts reachable within this step.
                reach=(speed+a*rot)*dt+tol
                contacts=geometry.contacts(x,p,a,b,reach)
                vv,health=m.contact_solve(vf,M,contacts,a,dt,friction,tol=1e-8)
                if np.linalg.norm(vv[:3])*dt>1.1*displacement_fraction*b or np.linalg.norm(vv[3:])*dt/a>1.1*angle_limit:
                    dt*=.5;rejected+=1;continue
                gap=swept_gap(geometry,x,p,vv,a,b,dt)
                if gap < -tol:dt*=.5;rejected+=1;continue
                xx,pp=m.advance_pose(x,p,vv,a,dt)
                break
            else:raise RuntimeError('adaptive step failed to maintain clearance')
            min_gap=min(min_gap,gap);max_res=max(max_res,health['residual']);max_force=max(max_force,health['force_residual'])
            max_contacts=max(max_contacts,len(contacts));contact_steps+=int(any(v>0 for v in health['reactions'][::3]));n+=1
            event=m.linear_pose_exit_time(x,p,vv,a,b,outlet,dt)
            if event is not None:
                x,p=m.advance_pose(x,p,vv,a,event);t+=event
                return result('full_window_exit')
            x,p=xx,pp;t+=dt
            if n%100==0:history.append([t,*x,*p])
        return result('present_at_horizon')
    except (ValueError,FloatingPointError,RuntimeError,np.linalg.LinAlgError) as exc:
        return result('unresolved_model' if 'mixed fluid/solid' in str(exc) else 'numerical_failure',str(exc))
