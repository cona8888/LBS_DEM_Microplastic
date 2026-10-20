"""Opt-in certificate for force recovery across a rounded velocity addition.

The normal route is the unchanged Stage50 1e-8 force gate. Only on its failure,
solve the six-dimensional system with exact rational arithmetic on the binary64
inputs. Require the UNSUMMED correction to close against J.T*f at the same
tolerance and require the returned velocity to be the correctly rounded sum.
This does not alter forces, velocities, contact laws or any physical tolerance.
It certifies arithmetic, not the physical correctness of the supplied matrices.
"""
from contextlib import contextmanager
from fractions import Fraction as F
from pathlib import Path
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage157_staging'))
import verify_nonsmooth_windows_v1 as prior
hot=prior.old.hot
telemetry=[]


def rational_solve(matrix, rhs):
    """Exact Gauss-Jordan elimination; multiple RHS, no numerical inverse."""
    n=len(matrix); width=len(rhs[0])
    a=[list(row)+list(b) for row,b in zip(matrix,rhs)]
    for k in range(n):
        pivot=max(range(k,n),key=lambda i:abs(a[i][k]))
        if not a[pivot][k]:raise RuntimeError('singular exact closure matrix')
        a[k],a[pivot]=a[pivot],a[k]
        divisor=a[k][k];a[k]=[x/divisor for x in a[k]]
        for i in range(n):
            if i==k:continue
            factor=a[i][k]
            a[i]=[x-factor*y for x,y in zip(a[i],a[k])]
    return [row[n:n+width] for row in a]


def certificate(vfree,mobility,jacobian,force,increment,velocity,exact=False):
    arrays=[np.asarray(x,dtype=float) for x in (vfree,mobility,jacobian,force,increment,velocity)]
    v,M,J,f,d,q=arrays
    if (v.shape!=(6,) or M.shape!=(6,6) or J.ndim!=2 or J.shape[1]!=6
        or f.shape!=(J.shape[0],) or d.shape!=(6,) or q.shape!=(6,)
        or any(not np.isfinite(x).all() for x in arrays)):
        raise RuntimeError('nonfinite or invalid closure inputs')
    reaction=J.T@f
    old=float(np.linalg.norm(np.linalg.solve(M,q-v)-reaction)/max(np.linalg.norm(reaction),1e-30))
    if not np.isfinite(old):raise RuntimeError('nonfinite force closure')
    if old<=1e-8 and not exact:
        return {'force_residual':old,'rounded_velocity_force_residual':old,'roundoff_certificate_used':False}
    start=time.perf_counter()
    # This bounded fallback must not hide an unresolved ill-conditioned system.
    condition=float(np.linalg.cond(M))
    if (not np.isfinite(condition) or condition>1e8 or
        not np.allclose(M,M.T,rtol=0,atol=1e-12*np.linalg.norm(M))):
        raise RuntimeError('uncertifiable closure matrix')
    np.linalg.cholesky(M)
    mf=[[F(float(x)) for x in row] for row in M]
    vf,df,qf=([F(float(x)) for x in arr] for arr in (v,d,q))
    jf=[[F(float(x)) for x in row] for row in J]
    ff=[F(float(x)) for x in f]
    target=[sum((jf[j][i]*ff[j] for j in range(len(ff))),F(0)) for i in range(6)]
    # Fraction->float rounds independently of the NumPy velocity-add operation.
    if any(float(x+y)!=z for x,y,z in zip(vf,df,q)):
        raise RuntimeError('velocity is not the correctly rounded correction sum')
    solved=rational_solve(mf,[[df[i],qf[i]-vf[i]] for i in range(6)])
    error=[r[0]-t for r,t in zip(solved,target)]
    reaction2=sum(x*x for x in target)
    denominator2=max(reaction2,F(1e-30)**2) # unchanged legacy floor
    error2=sum(x*x for x in error)
    if error2>F(1e-8)**2*denominator2:
        raise RuntimeError('unsummed contact force closure failed')
    addition_load=[r[1]-r[0] for r in solved]
    total_error=[r[1]-t for r,t in zip(solved,target)]
    if any(a+e!=t for a,e,t in zip(addition_load,error,total_error)):
        raise RuntimeError('exact closure decomposition failed')
    stable=float(np.sqrt(float(error2/denominator2)))
    report={'force_residual':stable,'rounded_velocity_force_residual':old,
            'roundoff_certificate_used':True,'exact_rational_inputs':True,
            'correctly_rounded_velocity_sum':True,'mobility_condition_number':condition,
            'unsummed_force_error_N':float(np.sqrt(float(error2))),
            'velocity_addition_roundoff_load_N':float(np.sqrt(float(sum(x*x for x in addition_load)))),
            'exact_recovered_force_error_N':float(np.sqrt(float(sum(x*x for x in total_error)))),
            'reaction_load_norm_N':float(np.sqrt(float(reaction2))),
            'certificate_seconds':time.perf_counter()-start}
    return report


def finish(vfree,mobility,jacobian,force,z,A,gaps,dt,friction,steps,iterations,solver,extra):
    """Stage50 finalization, with only the closure certificate replaced."""
    if any(not np.isfinite(np.asarray(x)).all() for x in (vfree,mobility,jacobian,force,z,A,gaps,dt,friction,steps)):
        raise RuntimeError('nonfinite contact finalization inputs')
    velocity_contact=z+A@force;scale=max(np.linalg.norm(vfree),1e-15)
    residual=hot.s50._residual(force,z,A,gaps,dt,friction,steps)
    if np.any(force[::3]<0):raise RuntimeError('direct contact negative normal force')
    for k in range(len(gaps)):
        i=3*k
        if np.linalg.norm(force[i+1:i+3])>friction*force[i]+1e-12*max(np.linalg.norm(force),1e-30):
            raise RuntimeError('direct contact cone violation')
    if residual/scale>1e-10:raise RuntimeError('direct contact residual nonconvergence')
    increment=mobility@jacobian.T@force # preserve original left association
    velocity=vfree+increment
    report=certificate(vfree,mobility,jacobian,force,increment,velocity)
    work=sum(float(force[3*k+1:3*k+3]@velocity_contact[3*k+1:3*k+3]) for k in range(len(gaps)))
    if work>1e-8*max(np.linalg.norm(force)*scale,1e-30):raise RuntimeError('friction generates energy')
    health={'iterations':iterations,'residual':float(residual/scale),'force_residual':report['force_residual'],
            'dissipation':-work,'reactions':force.tolist(),'solver':solver}
    health.update(extra)
    health.update(report)
    if report['roundoff_certificate_used']:telemetry.append(dict(report))
    return hot.s50.contact_model.finite(velocity),health


@contextmanager
def scope():
    saved=hot.s50._finish;saved_compiled=hot.PRIMARY.__globals__['_finish']
    hot.s50._finish=finish;hot.PRIMARY.__globals__['_finish']=finish
    try:yield
    finally:
        hot.s50._finish=saved;hot.PRIMARY.__globals__['_finish']=saved_compiled
