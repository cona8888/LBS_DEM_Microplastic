"""Isolated stationary sphere in uniform creeping flow; NOT periodic flow.

Closed-form exterior velocity/pressure and independent numerical traction.
Newtonian stress sigma=-p I+mu(grad u+grad u.T), normal out of the solid.
"""
import numpy as np

def fields(points,radius,viscosity,far_velocity,solid_interior=False):
    x=np.asarray(points,dtype=float);U=np.asarray(far_velocity,dtype=float)
    if x.ndim!=2 or x.shape[1]!=3 or U.shape!=(3,) or not np.isfinite(x).all() or not np.isfinite(U).all():
        raise ValueError('invalid points or far-field velocity')
    if not np.isfinite(radius) or radius<=0 or not np.isfinite(viscosity) or viscosity<=0:
        raise ValueError('positive radius and viscosity required')
    r=np.linalg.norm(x,axis=1)
    if not solid_interior and np.any(r==0):raise ValueError('singular analytic continuation at centre')
    rr=np.maximum(r,radius) if solid_interior else r
    e=x/rr[:,None];b=radius/rr
    u=(1-.75*b-.25*b**3)[:,None]*U+(-.75*b+.75*b**3)[:,None]*np.sum(e*U,axis=1)[:,None]*e
    p=-1.5*viscosity*radius*(x@U)/rr**3
    if solid_interior:
        u[r<radius]=0.;p[r<radius]=np.nan # pressure inside solid is not defined here
    return u,p

def surface_quadrature(radius,nmu=24,ntheta=48):
    z,w=np.polynomial.legendre.leggauss(nmu);theta=2*np.pi*np.arange(ntheta)/ntheta
    zz,tt=np.meshgrid(z,theta,indexing='ij')
    normals=np.column_stack((np.sqrt(1-zz.ravel()**2)*np.cos(tt.ravel()),
                             np.sqrt(1-zz.ravel()**2)*np.sin(tt.ravel()),zz.ravel()))
    weights=np.repeat(w,ntheta)*(2*np.pi/ntheta)*radius**2
    return normals*radius,normals,weights

def numerical_traction(points,normals,radius,viscosity,U,h):
    if not np.isfinite(h) or not 0<h<radius/4:raise ValueError('invalid derivative step')
    grad=np.empty((len(points),3,3))
    for j in range(3):
        d=np.eye(3)[j]*h
        # Smooth analytic continuation is used ONLY to differentiate at the surface.
        grad[:,:,j]=(fields(points+d,radius,viscosity,U)[0]-fields(points-d,radius,viscosity,U)[0])/(2*h)
    p=fields(points,radius,viscosity,U)[1]
    pressure=-p[:,None]*normals
    viscous=viscosity*np.einsum('nij,nj->ni',grad+grad.swapaxes(1,2),normals)
    return pressure,viscous
