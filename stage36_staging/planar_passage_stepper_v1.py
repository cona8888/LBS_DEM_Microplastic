"""Bounded x-parameterized planar passage integrator.

Requires positive axial velocity. The provider returns (Ux,Uy,omega_z).
All provider queries stay inside x_bounds; outlet crossing uses ellipsoid
support, with bisection on a cubic Hermite state inside the accepted step.
Near-contact or nonpositive-Ux paths are unresolved rather than retained.
"""
import numpy as np

def support(theta,axes):
    a,b,_=axes
    return float(np.sqrt((a*np.cos(theta))**2+(b*np.sin(theta))**2))

def volume_fraction(x,theta,axes,outlet):
    s=float(np.clip((outlet-x)/support(theta,axes),-1,1))
    return .5-.75*s+.25*s**3

def integrate(provider,axes,y0,theta0,dx,x_bounds=(-4.2,4.2),outlet=4.,horizon=100.):
    axes=np.asarray(axes,float)
    if axes.shape!=(3,) or np.any(axes<=0) or not np.isfinite(axes).all():raise ValueError('invalid axes')
    if dx<=0 or not np.isfinite(dx) or x_bounds[0]>=x_bounds[1]:raise ValueError('invalid domain')
    x=float(x_bounds[0]);s=np.array([0.,y0,theta0],float)
    if not np.isfinite(s).all():raise ValueError('invalid pose')
    history=[];calls=0
    def rhs(q,z):
        nonlocal calls
        if not x_bounds[0]-1e-13<=q<=x_bounds[1]+1e-13:raise ValueError('provider extrapolation')
        v=np.asarray(provider(q,float(z[1]),float(z[2])),float);calls+=1
        if v.shape!=(3,) or not np.isfinite(v).all() or v[0]<=0:raise ValueError('nonpositive/invalid axial motion')
        return np.array([1.,v[1],v[2]])/v[0]
    def event(q,z):return q-support(z[2],axes)-outlet
    def record(q,z):return {'x':float(q),'t':float(z[0]),'y':float(z[1]),'theta':float(z[2]),'released_volume_fraction':float(volume_fraction(q,z[2],axes,outlet))}
    history.append(record(x,s))
    while x<x_bounds[1]-1e-13:
        h=min(dx,x_bounds[1]-x)
        k1=rhs(x,s);k2=rhs(x+h/2,s+h*k1/2);k3=rhs(x+h/2,s+h*k2/2);k4=rhs(x+h,s+h*k3)
        new=s+h*(k1+2*k2+2*k3+k4)/6;end=rhs(x+h,new)
        def dense(f):
            return (2*f**3-3*f**2+1)*s+(f**3-2*f**2+f)*h*k1+(-2*f**3+3*f**2)*new+(f**3-f**2)*h*end
        candidates=[]
        for name,fun in [('released',lambda f:event(x+f*h,dense(f))),('horizon',lambda f:dense(f)[0]-horizon)]:
            if fun(0)<0 and fun(1)>=-1e-12:
                lo,hi=0.,1.
                for _ in range(48):
                    mid=(lo+hi)/2
                    if fun(mid)<0:lo=mid
                    else:hi=mid
                candidates.append((hi,name))
        if candidates:
            f,status=min(candidates);s=dense(f);x+=f*h;history.append(record(x,s))
            return {'status':status,'history':history,'provider_calls':calls}
        x+=h;s=new;history.append(record(x,s))
    return {'status':'domain_end_unresolved','history':history,'provider_calls':calls}
