"""Translation-only RK2 integrator with mandatory state-dependent mobility.

No contact, rotation, inertia or release interpretation is implemented.
The provider must supply mobility for the requested position, not a stale cache.
"""
import numpy as np

def integrate(x0,force,mobility,clearance,*,duration,steps):
    x=np.array(x0,dtype=float,copy=True);F=np.asarray(force,float)
    if x.shape!=(3,) or F.shape!=(3,) or not np.isfinite(x).all() or not np.isfinite(F).all():raise ValueError('invalid state/load')
    if type(steps) is not int or steps<1 or not np.isfinite(duration) or duration<=0:raise ValueError('invalid time settings')
    dt=duration/steps;path=[x.copy()]
    def check(p):
        gap=float(clearance(p.copy()))
        if not np.isfinite(gap) or gap<=0:raise ValueError('clearance violated; step rejected')
    def velocity(p):
        check(p)
        M=np.asarray(mobility(p.copy()),float)
        if M.shape!=(3,3) or not np.isfinite(M).all():raise ValueError('invalid mobility')
        if not np.allclose(M,M.T,rtol=1e-10,atol=1e-14) or np.linalg.eigvalsh(M).min()<=0:raise ValueError('mobility must be symmetric positive definite')
        return M@F
    for _ in range(steps):
        midpoint=x+.5*dt*velocity(x)
        candidate=x+dt*velocity(midpoint)
        check(candidate)
        x=candidate;path.append(x.copy())
    return np.asarray(path)
