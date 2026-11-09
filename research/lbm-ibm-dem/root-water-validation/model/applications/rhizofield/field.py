"""Equilibrium diffuse-interface patch on a moving finite-volume mesh.

The Cartesian solid masks are fixed in reference coordinates. Physical x-faces
translate rigidly around each disk and stretch only in fluid strips. There is
no cell birth/death and no change of disk area or wall length. A 1-D normal
motion constraint is deliberate. SI conversion is applied only at the ports.
"""
from pathlib import Path
from dataclasses import dataclass
import numpy as np
from scipy import sparse
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
DX, GAMMA, WIDTH, KAPPA, SIGMA = 50e-6, .072, 2.5, 2.5**2/2, 2*2.5/3
P0 = GAMMA/(SIGMA*DX)
REFERENCE_GAP = 12.

def seed():
    a = np.genfromtxt(HERE/'seed/pore_traction_map.csv', delimiter=',', names=True)
    shape = 1+int(a['y'].max()), 1+int(a['x'].max())
    solid = a['solid'].astype(int).reshape(shape)
    return solid, a['phi'].reshape(shape)[solid == 0]

@dataclass
class State:
    phi: np.ndarray
    mu: float                    # equilibrium Lagrange multiplier, lattice pressure units
    residual: float              # max absolute deviation of chemical potential
    energy: float
    water: float                 # integral (phi+1)/2, lattice area units
    force: float                 # signed force on grain, N/m
    psi: float                   # p_water - p_gas in Pa, extrapolated bulk branches
    wet_length: float            # wetted root perimeter, m

class Mesh:
    def __init__(self, labels, gap=12., *, grain_deg=60., root_deg=50., interface_width=WIDTH):
        if not np.isfinite(gap) or not 9 <= gap <= 16:
            raise ValueError('Patch implemented only for gaps 9..16 reference spacings.')
        self.labels=np.asarray(labels); self.fluid=self.labels==0
        if self.labels.shape not in tuple((67*k,94*k) for k in (1,2,3,4,8)): raise ValueError('Unexpected reference mesh.')
        if not np.isfinite(interface_width) or interface_width<=0: raise ValueError('Interface width must be finite and positive.')
        self.interface_width=float(interface_width)
        self.kappa=self.interface_width**2/2
        self.sigma=2*self.interface_width/3
        self.pressure_scale=GAMMA/(self.sigma*DX)
        self.scale=self.labels.shape[0]//67; self.hy=hy=1./self.scale
        edge=np.arange(self.labels.shape[1]+1)*hy-.5
        move=np.interp(edge,[-.5,49.5,59.5,75.5,91.5,93.5],[0,0,1,1,0,0])
        self.edge=edge+(gap-REFERENCE_GAP)*move
        width=np.diff(self.edge); wd=np.diff(move)
        center=(self.edge[1:]+self.edge[:-1])*.5
        self.cx=center
        col=np.nonzero(self.fluid)[1]; self.V=hy*width[col]; self.Vd=hy*wd[col]
        ids=np.full(self.labels.shape,-1,int); ids[self.fluid]=np.arange(len(col))
        self.wall=np.zeros(len(col)); self.root=np.zeros(len(col)); self.walld=np.zeros(len(col))
        left=[]; right=[]; weights=[]; derivatives=[]
        if not all(np.isfinite(z) and 0 < z < 180 for z in (grain_deg,root_deg)):
            raise ValueError("Wetting angles must lie strictly inside (0,180) degrees")
        angles=np.cos(np.deg2rad([90,grain_deg,root_deg]))
        for axis in [0,1]:
            a,b=((np.s_[:-1,:],np.s_[1:,:]) if axis==0 else (np.s_[:,:-1],np.s_[:,1:]))
            ia,ib=ids[a],ids[b]; both=(ia>=0)&(ib>=0)
            if axis==0:
                k=width/hy; kd=wd/hy; area=width; ad=wd
            else:
                d=(width[1:]+width[:-1])/2; dd=(wd[1:]+wd[:-1])/2
                k=hy/d; kd=-hy*dd/d**2; area=hy*np.ones_like(k); ad=np.zeros_like(k)
            j=np.where(both)[1]; left.append(ia[both]); right.append(ib[both]); weights.append(k[j]); derivatives.append(kd[j])
            for fi,si,sl in [(ia,ib,self.labels[b]),(ib,ia,self.labels[a])]:
                take=(fi>=0)&(si<0); j=np.where(take)[1]; f=fi[take]; lab=sl[take]
                np.add.at(self.wall,f,area[j]*angles[lab]); np.add.at(self.walld,f,ad[j]*angles[lab]); np.add.at(self.root,f,area[j]*(lab==2))
        self.i=np.concatenate(left); self.j=np.concatenate(right); self.kd=np.concatenate(derivatives)
        k=np.concatenate(weights); i,j=self.i,self.j; n=len(col)
        self.K=sparse.coo_matrix((np.r_[k,k,-k,-k],(np.r_[i,j,i,j],np.r_[i,j,j,i])),shape=(n,n)).tocsr()

    def energy_grad(self,x):
        kx=self.K@x; f=.25*(x*x-1)**2; h=-self.sigma*(3*x-x**3)/4
        E=self.V@f + .5*self.kappa*(x@kx) + self.wall@h
        grad=self.V*x*(x*x-1) + self.kappa*kx -.75*self.sigma*self.wall*(1-x*x)
        return E,grad

    def water(self,x): return .5*(self.V@(1+x))

    def solve(self, guess, water, tol=4e-6):
        V=self.V; guess=np.asarray(guess,float)
        if guess.shape!=V.shape or not np.isfinite(guess).all() or not np.isfinite(water) or not 0<=water<=sum(V):
            raise ValueError('Invalid phase field or water inventory.')
        vv=V@V
        def project(z): return z-V*((V@z)/vv)
        anchor=guess+V*(2*(water-self.water(guess))/vv)
        def obj(z):
            y=anchor+project(z); e,g=self.energy_grad(y)
            return e,project(g)
        res=minimize(obj,np.zeros_like(anchor),jac=True,method='L-BFGS-B',options={'ftol':1.e-15,'gtol':3e-8,'maxiter':1200,'maxcor':8})
        x=anchor+project(res.x); E,g=self.energy_grad(x); mu=(g@V)/vv
        r=np.max(np.abs(g/V-mu))
        if r>tol or not np.isfinite(r) or abs(self.water(x)-water)>1e-8:
            raise RuntimeError(f'Equilibrium or mass check failed: residual={r}, solver={res.message}')
        f=.25*(x*x-1)**2; h=-self.sigma*(3*x-x**3)/4
        slope=self.Vd@f+.5*self.kappa*(self.kd@((x[self.i]-x[self.j])**2))+self.walld@h-mu*(self.Vd@(1+x))
        roots=np.roots([1.,0.,-1.,-mu]); real=np.sort(roots.real[np.abs(roots.imag)<1e-10]);
        if len(real)!=3: raise RuntimeError('Bulk extensions do not admit two stable phases')
        gas,liq=real[[0,-1]]
        p=lambda z: mu*z-(z*z-1)**2/4
        # Compact smooth wet-wall indicator with exact dry/wet bulk limits.
        z=np.clip((x+.8)/1.6,0,1); wet=self.root@(z*z*(3-2*z))
        return State(x,float(mu),float(r),float(E),float(self.water(x)),float(-slope*self.pressure_scale*DX),float((p(liq)-p(gas))*self.pressure_scale),float(wet*DX))

    def map(self, x):
        out=np.full(self.labels.shape,np.nan); out[self.fluid]=x; return out

    def contour(self,s,pad=3,body=1):
        """Independent Korteweg stress integral across a four-sided fluid contour."""
        if body not in (1,2) or pad not in (2,3,4,5): raise ValueError('Invalid contour')
        pad=self.scale*pad+self.scale-1
        phi=self.map(s.phi); _,g=self.energy_grad(s.phi); mu=self.map(g/self.V)
        gy,gx=np.gradient(phi,self.hy,self.cx); width=np.diff(self.edge)
        ys,xs=np.where(self.labels==body); x0,x1=xs.min()-pad,xs.max()+pad; y0,y1=ys.min()-pad,ys.max()+pad
        if np.any((self.labels[y0:y1+1,x0:x1+1]!=0)&(self.labels[y0:y1+1,x0:x1+1]!=body)):
            raise ValueError('Contour encloses another body')
        def xface(k):
            a,b=phi[y0:y1+1,k],phi[y0:y1+1,k+1]; t=width[k]/(width[k]+width[k+1]); avg=lambda f:(1-t)*f[y0:y1+1,k]+t*f[y0:y1+1,k+1]
            n=(b-a)/(self.cx[k+1]-self.cx[k]); v=avg(phi); tang=avg(gy)
            return self.hy*np.sum(-v*avg(mu)+(v*v-1)**2/4+.5*self.kappa*(tang*tang-n*n))
        def yface(k):
            sl=slice(x0,x1+1); n=(phi[k+1,sl]-phi[k,sl])/self.hy; tang=(gx[k+1,sl]+gx[k,sl])/2
            return np.sum(-self.kappa*n*tang*width[sl])
        force=(xface(x1)-xface(x0)+yface(y1)-yface(y0-1))*self.pressure_scale*DX
        if not np.isfinite(force): raise RuntimeError('Stress stencil intersects a solid')
        return float(force)
