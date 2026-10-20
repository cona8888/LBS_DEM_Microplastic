"""Axisymmetric exact Stokes streamfunction in a concentric spherical shell.

psi=f(r) sin(theta)^2; f=A*r^4+B*r^2+C*r+D/r solves
(d2/dr2-2/r2)^2 f=0. Moving inner sphere: f(a)=U*a^2/2,
f'(a)=U*a; stationary outer sphere: f(b)=f'(b)=0.
Hydrodynamic force along translation is -8*pi*mu*C.
"""
import numpy as np
def solve(a,b,mu,U):
    if not np.isfinite([a,b,mu,U]).all() or not 0<a<b or mu<=0:raise ValueError('invalid shell')
    def row(r):return [r**4,r**2,r,1/r]
    def derivative(r):return [4*r**3,2*r,1,-1/r**2]
    coeff=np.linalg.solve(np.array([row(a),derivative(a),row(b),derivative(b)]),[U*a*a/2,U*a,0,0])
    return coeff,-8*np.pi*mu*coeff[2]

def velocity(points,coeff):
    p=np.asarray(points);r=np.linalg.norm(p,axis=1);er=p/r[:,None]
    A,B,C,D=coeff
    f=A*r**4+B*r**2+C*r+D/r
    fp=4*A*r**3+2*B*r+C-D/r**2
    # Polar axis is x; reconstruct from radial and tangential components.
    return (fp/r)[:,None]*np.array([1.,0,0])+(2*f/r**2-fp/r)[:,None]*er[:,0,None]*er
