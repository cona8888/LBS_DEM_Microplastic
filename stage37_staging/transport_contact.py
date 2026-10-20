"""Auditable overdamped rigid-body primitives. SI or any consistent units.

These primitives do not by themselves qualify near-wall hydrodynamics.
Generalized velocity is (U, ell*omega), load is (F, torque/ell).
"""
from functools import lru_cache
import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.spatial import cKDTree


def finite(x):
    x = np.asarray(x, dtype=float)
    if not np.isfinite(x).all():
        raise FloatingPointError('nonfinite state')
    return x


def unit(x):
    x = finite(x)
    n = np.linalg.norm(x)
    if n == 0:
        raise ValueError('zero direction')
    return x/n


class CellField:
    """Cell-centred xyz velocity; periodic continuation explicitly declared.

    Interpolation uses only all-fluid stencils. Mixed solid/fluid stencils
    raise an applicability error instead of smoothing through a solid.
    """
    def __init__(self, velocity_xyz, spacing, fluid=None):
        self.u = finite(velocity_xyz)
        if self.u.ndim != 4 or self.u.shape[0] != 3 or spacing <= 0:
            raise ValueError('invalid field')
        self.dx = float(spacing)
        self.shape = np.array(self.u.shape[1:])
        self.fluid = np.ones(tuple(self.shape), bool) if fluid is None else np.asarray(fluid,bool)
        if self.fluid.shape != tuple(self.shape): raise ValueError('phase shape mismatch')

    def sample(self, x):
        q = finite(x)/self.dx - .5
        i = np.floor(q).astype(int); w = q-i
        v = np.zeros(3); g = np.zeros((3,3))
        for bits in np.ndindex(2,2,2):
            b = np.array(bits); idx = tuple((i+b)%self.shape)
            if not self.fluid[idx]: raise ValueError('unresolved mixed fluid/solid interpolation stencil')
            fac = np.where(b,w,1-w); value=self.u[(slice(None),)+idx]
            v += np.prod(fac)*value
            for j in range(3):
                g[:,j] += value*(1 if b[j] else -1)*np.prod(np.delete(fac,j))/self.dx
        return finite(v),finite(g)


def support(n,p,a,b):
    if a <= 0 or b <= 0: raise ValueError('positive axes required')
    c=np.dot(unit(n),unit(p))
    return float(np.sqrt(b*b+(a*a-b*b)*c*c))


def ellipsoid_grain_contact(x,p,a,b,c,r):
    """Exact closest point from external spherical grain centre to prolate.

    Returns gap, normal pointing from grain toward polymer, polymer lever arm.
    Sphere centre inside ellipsoid is an inadmissible deep-overlap state.
    """
    x,c=finite(x),finite(c);p=unit(p)
    if min(a,b,r)<=0: raise ValueError('positive radii required')
    d=(c-x)/a; ratio=b/a; parallel=np.dot(d,p)*p; transverse=d-parallel
    val=np.dot(parallel,parallel)+np.dot(transverse,transverse)/(ratio*ratio)
    if val<=1: raise ValueError('grain centre inside ellipsoid')
    if abs(a-b)<1e-13*a:
        lever=a*unit(d)
    else:
        d2p=np.dot(parallel,parallel);d2t=np.dot(transverse,transverse)
        fun=lambda t:d2p/(1+t)**2+ratio**2*d2t/(ratio**2+t)**2-1
        hi=max(1.,np.linalg.norm(d))
        while fun(hi)>0: hi*=2
        t=brentq(fun,0.,hi,xtol=1e-14)
        lever=a*(parallel/(1+t)+ratio**2*transverse/(ratio**2+t))
    sep=x+lever-c;dist=np.linalg.norm(sep)
    return float(dist-r),unit(sep),lever


class GrainGeometry:
    """Periodic nearest images; works with unwrapped transport coordinates."""
    def __init__(self,centres,radii,length):
        self.c=finite(centres);self.r=finite(radii);self.L=float(length)
        if self.c.shape!=(len(self.r),3) or self.L<=0 or np.any(self.r<=0): raise ValueError('invalid grains')
        self.tree=cKDTree(np.mod(self.c,self.L),boxsize=self.L)
    def contacts(self,x,p,a,b,skin=0.):
        x=finite(x); ids=self.tree.query_ball_point(np.mod(x,self.L),self.r.max()+a+skin)
        out=[]
        for k in sorted(ids):
            d=self.c[k]-x;d-=self.L*np.round(d/self.L);c=x+d
            gap,n,lever=ellipsoid_grain_contact(x,p,a,b,c,self.r[k])
            if gap<=skin: out.append((k,gap,n,lever))
        return out


def jeffery(p,g,ar):
    p=unit(p);g=finite(g);E=(g+g.T)/2;W=(g-g.T)/2
    return W@p+(ar*ar-1)/(ar*ar+1)*(E@p-(p@E@p)*p)


def midpoint_orientation(p,gradient,ar,dt):
    p=unit(p);mid=unit(p+.5*dt*jeffery(p,gradient,ar))
    return unit(p+dt*jeffery(mid,gradient,ar))


@lru_cache(maxsize=16)
def resistance_axes(a,b,mu):
    """Perrin ellipsoid integrals; quadrature uses dimensionless major axis."""
    if min(a,b,mu)<=0: raise ValueError('positive dimensions required')
    s=np.array([1.,b/a,b/a]); delta=lambda t:np.sqrt(np.prod(s*s+t))
    chi=quad(lambda t:1/delta(t),0,np.inf,epsabs=1e-11)[0]
    alpha=np.array([quad(lambda t:1/((s[i]**2+t)*delta(t)),0,np.inf,epsabs=1e-11)[0] for i in range(3)])
    rt=16*np.pi*mu*a/(chi+s*s*alpha)
    rr=np.array([(16*np.pi*mu*a**3/3)*(s[j]**2+s[k]**2)/(s[j]**2*alpha[j]+s[k]**2*alpha[k]) for j,k in [(1,2),(0,2),(0,1)]])
    return rt,rr


def mobility(p,a,b,mu):
    p=unit(p);rt,rr=resistance_axes(a,b,mu);pp=np.outer(p,p);I=np.eye(3)
    M=np.zeros((6,6));M[:3,:3]=pp/rt[0]+(I-pp)/rt[1]
    M[3:,3:]=a*a*(pp/rr[0]+(I-pp)/rr[1])
    return M


def free_motion(p,g,u,a,b,mu,rho_p,rho_f,gravity):
    p=unit(p);u=finite(u);g=finite(g)
    vorticity=np.array([g[2,1]-g[1,2],g[0,2]-g[2,0],g[1,0]-g[0,1]])/2
    E=(g+g.T)/2;lam=(a*a-b*b)/(a*a+b*b)
    omega=vorticity+lam*np.cross(p,E@p)
    M=mobility(p,a,b,mu);load=np.r_[(rho_p-rho_f)*4*np.pi*a*b*b/3*finite(gravity),np.zeros(3)]
    return np.r_[u,a*omega]+M@load,M


def contact_frame(n):
    n=unit(n);axis=np.eye(3)[np.argmin(abs(n))];t=unit(np.cross(n,axis))
    return np.vstack([n,t,np.cross(n,t)])


def contact_solve(vfree,M,contacts,ell,dt,friction,tol=1e-9,maxiter=2000):
    """Coulomb projected block iteration with explicit residual acceptance.

    Normal Signorini condition is at the implicit linearized next gap.
    Tangential reaction is maximum-dissipation disk projection. Contacts are
    coupled through J M J.T; no associated friction-cone dilatancy law.
    """
    vfree=finite(vfree);M=finite(M)
    if dt<=0 or ell<=0 or friction<0: raise ValueError('invalid contact parameter')
    if not contacts:return vfree,{'iterations':0,'residual':0.,'force_residual':0.,'dissipation':0.,'reactions':[]}
    J=[];gaps=[]
    for _,gap,n,lever in contacts:
        frame=contact_frame(n);J.extend(np.c_[frame,np.cross(lever,frame)/ell]);gaps.append(gap)
    J=np.array(J);gaps=np.array(gaps);A=J@M@J.T;z=J@vfree
    force=np.zeros(len(z));scale=max(np.linalg.norm(vfree),1e-15)
    for iteration in range(maxiter):
        for k in range(len(contacts)):
            i=3*k;vn=z[i]+A[i]@force+gaps[k]/dt
            force[i]=max(0.,force[i]-vn/A[i,i])
            vt=z[i+1:i+3]+A[i+1:i+3]@force
            # Scalar Lipschitz step gives a correct Euclidean disk fixed point.
            step=np.linalg.eigvalsh(A[i+1:i+3,i+1:i+3]).max()
            t=force[i+1:i+3]-vt/step;limit=friction*force[i];tn=np.linalg.norm(t)
            force[i+1:i+3]=t*min(1.,limit/max(tn,1e-300))
        vel=z+A@force;res=0.
        for k in range(len(contacts)):
            i=3*k;normal=vel[i]+gaps[k]/dt
            res=max(res,abs(min(A[i,i]*force[i],normal)))
            step=np.linalg.eigvalsh(A[i+1:i+3,i+1:i+3]).max()
            t=force[i+1:i+3]-vel[i+1:i+3]/step;lim=friction*force[i];tn=np.linalg.norm(t)
            proj=t*min(1.,lim/max(tn,1e-300));res=max(res,np.linalg.norm(force[i+1:i+3]-proj)*step)
        if res/scale<=tol:break
    else: raise RuntimeError('contact nonconvergence')
    v=vfree+M@J.T@force
    f_res=np.linalg.norm(np.linalg.solve(M,v-vfree)-J.T@force)/max(np.linalg.norm(J.T@force),1e-30)
    tang_work=sum(float(force[3*k+1:3*k+3]@vel[3*k+1:3*k+3]) for k in range(len(contacts)))
    if tang_work>1e-8*max(np.linalg.norm(force)*scale,1e-30): raise RuntimeError('friction generates energy')
    return finite(v),{'iterations':iteration+1,'residual':res/scale,'force_residual':float(f_res),'dissipation':-tang_work,'reactions':force.tolist()}


def advance_pose(x,p,v,ell,dt):
    v=finite(v);x=finite(x)+dt*v[:3];omega=v[3:]/ell;theta=np.linalg.norm(omega)*dt
    p=unit(p)
    if theta>0:
        n=unit(omega);p=p*np.cos(theta)+np.cross(n,p)*np.sin(theta)+n*(n@p)*(1-np.cos(theta))
    return x,unit(p)


def full_exit_function(x,p,a,b,outlet):
    return float(finite(x)[0]-support([1,0,0],p,a,b)-outlet)


def linear_pose_exit_time(x,p,v,a,b,outlet,dt):
    """Root within a constant-velocity/rotation step, never mean-flow extrapolation."""
    fn=lambda t:full_exit_function(*advance_pose(x,p,v,a,t),a,b,outlet)
    if fn(0)>=0:return 0.
    if fn(dt)<0:return None
    return brentq(fn,0,dt,xtol=max(1e-14,dt*1e-12))
