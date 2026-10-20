"""Adaptive inertial translation / overdamped rotation through fixed sand."""
import sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'stage37_staging'),str(ROOT/'stage38_staging'),str(ROOT/'stage39_staging')]
import transport_contact as mechanics
import trajectory as geometry_tools
import lubrication_contact_v1 as lubrication
import inertial_contact_v2 as inertial

def enrich(geometry,contacts):
 return [(*c,float(geometry.r[c[0]])) if len(c)==4 else c for c in contacts]

def lubrication_matrix(near,p,a,b,ell,mu,cutoff_ratio,roughness_ratio):
 L=np.zeros((6,6));rows=[]
 for grain,gap,n,lever,radius in near:
  curv=lubrication.prolate_principal_curvatures(lever,p,a,b);pref=lubrication.squeeze_prefactor(mu,radius,curv);cut=cutoff_ratio*radius;rough=roughness_ratio*radius
  coeff=lubrication.matched_excess_resistance(gap,cut,rough,pref);J=lubrication.normal_jacobian(n,lever,ell);L+=coeff*np.outer(J,J);rows.append({'grain_id':int(grain),'gap':float(gap),'grain_radius':radius,'coefficient':coeff})
 return L,rows

def integrate(field,geometry,x,p,velocity,a,b,mu,rhop,rhof,gravity,friction,outlet,horizon,
 added_mass_fraction=0.,cutoff_ratio=.2,roughness_ratio=.01,displacement_fraction=.1,angle_limit=.02,relaxation_fraction=.5,max_dt=1.,max_steps=500000,wall_budget=120.):
 x=mechanics.finite(x).copy();p=mechanics.unit(p);q=mechanics.finite(velocity).copy();t=0.;steps=rejected=contact_steps=0;started=time.perf_counter();mingap=np.inf;mingapratio=np.inf;maxmom=maxcres=maxfres=maxre=0.;maxnear=maxactive=0;history=[];tol=1e-5*b;deq=2*(a*b*b)**(1/3);phi=inertial.finite_re.prolate_sphericity(a,b);maxr=float(np.max(geometry.r))
 def finish(status,reason=None):return {'status':status,'reason':reason,'time_s':t,'position_m':x.tolist(),'orientation':p.tolist(),'velocity_generalized':q.tolist(),'steps':steps,'rejected':rejected,'minimum_gap_m':None if not np.isfinite(mingap) else mingap,'minimum_gap_over_grain_radius':None if not np.isfinite(mingapratio) else mingapratio,'max_momentum_residual':maxmom,'max_contact_residual':maxcres,'max_force_residual':maxfres,'max_reynolds':maxre,'max_lubrication_contacts':maxnear,'max_active_contacts':maxactive,'contact_steps':contact_steps,'runtime_seconds':time.perf_counter()-started,'history':history}
 try:
  while t<horizon:
   if steps>=max_steps or time.perf_counter()-started>wall_budget:return finish('incomplete_budget')
   initial=geometry.contacts(x,p,a,b,0.); 
   if initial and min(c[1] for c in initial)<-tol:raise RuntimeError('inadmissible penetration')
   u,g=field.sample(x);background,_=mechanics.free_motion(p,g,u,a,b,mu,1.,1.,[0,0,0]);R=inertial.stokes_generalized_resistance(p,a,b,mu);H,massmeta=inertial.generalized_mass_matrix(p,a,b,rhop,rhof,added_mass_fraction);H[3:,3:]=0.
   body=np.r_[(rhop-rhof)*4*np.pi*a*b*b/3*mechanics.finite(gravity),np.zeros(3)]
   near=enrich(geometry,geometry.contacts(x,p,a,b,cutoff_ratio*maxr));L,lrows=lubrication_matrix(near,p,a,b,a,mu,cutoff_ratio,roughness_ratio)
   translation_scale=max(np.linalg.norm(q[:3]),np.linalg.norm(background[:3]),np.linalg.norm(body[:3])/max(np.linalg.eigvalsh(R[:3,:3]).min(),1e-30),1e-30);rotation_scale=max(np.linalg.norm(q[3:]),np.linalg.norm(background[3:]),1e-30)/a
   tau=np.linalg.eigvalsh(H[:3,:3]).min()/np.linalg.eigvalsh(R[:3,:3]).max();dt=min(max_dt,horizon-t,displacement_fraction*b/translation_scale,angle_limit/rotation_scale,relaxation_fraction*tau)
   for _attempt in range(30):
    reach=(translation_scale+a*rotation_scale)*dt+tol;active=geometry.contacts(x,p,a,b,reach)
    qq,health=inertial.inertial_contact_step(q,background,body,R,L,H,[c[:4] for c in active],a,dt,friction,rhof,mu,deq,phi)
    if np.linalg.norm(qq[:3])*dt>1.1*displacement_fraction*b or np.linalg.norm(qq[3:])*dt/a>1.1*angle_limit:dt*=.5;rejected+=1;continue
    gap=geometry_tools.swept_gap(geometry,x,p,qq,a,b,dt)
    if gap < -tol:dt*=.5;rejected+=1;continue
    xx,pp=mechanics.advance_pose(x,p,qq,a,dt);break
   else:raise RuntimeError('adaptive step failed to maintain clearance')
   for c in enrich(geometry,geometry.contacts(x,p,a,b,cutoff_ratio*maxr)):mingapratio=min(mingapratio,c[1]/c[4])
   mingap=min(mingap,gap);maxmom=max(maxmom,health['momentum_residual']);maxcres=max(maxcres,health['contact']['residual']);maxfres=max(maxfres,health['contact']['force_residual']);maxre=max(maxre,health['reynolds']);maxnear=max(maxnear,len(lrows));maxactive=max(maxactive,len(active));contact_steps+=int(any(v>0 for v in health['contact']['reactions'][::3]));steps+=1
   event=mechanics.linear_pose_exit_time(x,p,qq,a,b,outlet,dt)
   if event is not None:x,p=mechanics.advance_pose(x,p,qq,a,event);q=qq;t+=event;return finish('full_window_exit')
   x,p,q=xx,pp,qq;t+=dt
   if steps%250==0:history.append([t,*x,*p,*q,mingap,mingapratio])
  return finish('present_at_horizon')
 except (ValueError,FloatingPointError,RuntimeError,np.linalg.LinAlgError) as exc:return finish('unresolved_field' if 'mixed fluid/solid' in str(exc) else 'numerical_failure',str(exc))

