"""Body-fitted radial Stokes solver for the isolated-sphere axisymmetric mode.

Numerically solve (D_s^2-2/s^2)^2 H=0, s=r/a, psi=U*a^2*H*sin(theta)^2.
The wall is exactly s=1. No diffuse kernel, radius fit, or target drag in solve.
Exact far-field solution supplies only velocity data at a finite outer shell.
Not a general 3-D, periodic, non-spherical or moving-particle solver.
"""
import math,time
import numpy as np
from scipy.sparse import lil_matrix
from scipy.sparse.linalg import spsolve

def weights(offsets,order):
    x=np.asarray(offsets,dtype=float)
    rhs=np.zeros(len(x));rhs[order]=math.factorial(order)
    return np.linalg.solve(np.array([x**k for k in range(len(x))]),rhs)

def solve(intervals=192,outer_ratio=8.,radius=1.,viscosity=.1,speed=1e-4):
    if type(intervals) is not int or not 24<=intervals<=1024:raise ValueError('intervals outside bounded diagnostic range')
    if not all(np.isfinite(x) for x in [outer_ratio,radius,viscosity,speed]) or not 2<=outer_ratio<=16 or radius<=0 or viscosity<=0:
        raise ValueError('invalid physical parameters')
    started=time.perf_counter();n=intervals;s=np.linspace(1,outer_ratio,n+1);h=s[1]-s[0]
    A=lil_matrix((n+1,n+1));b=np.zeros(n+1)
    d1=weights(np.arange(-2,3),1);d2=weights(np.arange(-2,3),2);d4=weights(np.arange(-2,3),4)
    # Interior rows scaled by h^4 for the sparse linear solve.
    for i in range(2,n-1):
        coeff=d4-4*h*h/s[i]**2*d2+8*h**3/s[i]**3*d1
        coeff[2]-=8*h**4/s[i]**4
        A[i,i-2:i+3]=coeff
    A[0,0]=1
    A[1,:5]=weights(np.arange(5),1) # h*dH/ds=0 at the physical surface
    R=outer_ratio
    A[n,n]=1;b[n]=.5*(R*R-1.5*R+.5/R)
    A[n-1,n-4:n+1]=weights(np.arange(-4,1),1)
    b[n-1]=h*(R-.75-.25/R**2)
    A=A.tocsr();H=spsolve(A,b)
    if not np.isfinite(H).all():raise ValueError('nonfinite radial solve')
    algebraic=float(np.max(np.abs(A@H-b))/max(np.max(np.abs(b)),1.))
    # Different, seven-point wall stencil used for traction and slip assessment.
    derivatives=[float(weights(np.arange(7),k)@H[:7]/h**k) for k in [1,2,3]]
    Hp,Hpp,Hppp=derivatives
    pressure_coefficient=viscosity*speed/radius*(Hppp-2*Hp+4*H[0])
    radial_viscous=4*viscosity*speed/radius*(Hp-2*H[0])
    tangential_viscous=viscosity*speed/radius*(-Hpp+2*Hp-2*H[0])
    pressure_force=-4*np.pi*radius**2/3*pressure_coefficient
    viscous_force=4*np.pi*radius**2/3*(radial_viscous-2*tangential_viscous)
    dH=np.array([weights(np.arange(-2,3),1)@H[i-2:i+3]/h for i in range(2,n-1)])
    return {'s':s,'H':H,'interior_dH':dH,'wall_derivatives':derivatives,
            'force':float(pressure_force+viscous_force),'pressure_force':float(pressure_force),
            'viscous_force':float(viscous_force),'algebraic_residual':algebraic,
            'independent_wall_slip_over_abs_U':float(max(abs(2*H[0]),abs(Hp))),
            'seconds':time.perf_counter()-started,'intervals':intervals,'outer_ratio':outer_ratio,
            'radius':radius,'viscosity':viscosity,'speed':speed}
