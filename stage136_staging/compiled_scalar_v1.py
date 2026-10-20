"""Compile only Stage74/Stage50 cold sweeps; preserve the live final gates.

Reuse the qualified NumPy-BLAS ABI adapter, but retain Stage74 scalar SOR
row-dots and hypot projections. No fastmath, new physics, warm starts or caps.
The primary solver is the original Stage50 AST with exactly its PGS loop
replaced. Its seeded LM and Stage53 fallback paths remain the original code.
Binary identity of hypot is not assumed: replay qualification is mandatory.
"""
from contextlib import contextmanager
from pathlib import Path
import ast
import inspect
import math
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'bottleneck_resolution_20260912/deps'),
               str(ROOT/'bottleneck_resolution_20260912/src'), str(ROOT/'stage74_staging')]
import numpy as np
from numba import njit
import compiled_blas_loop as abi
import scalar_contact_kernels_v1 as scalar

s50, s63 = scalar.s50, scalar.s63
DDOT, DGEMV = abi._ddot, abi._dgemv
work = {'pgs_calls':0, 'sor_calls':0, 'sweeps':0, 'loop_s':0.0}


@njit(cache=False, fastmath=False, parallel=False)
def sweep(A,z,gaps,dt,mu,steps,force,omega,sor,tangent,velocity):
    n=len(z)
    for k in range(len(gaps)):
        i=3*k
        old=force[i]
        vn=z[i]+DDOT(n,A[i].ctypes,1,force.ctypes,1)+gaps[k]/dt
        candidate=max(0.,old-vn/A[i,i])
        force[i]=max(0.,old+omega*(candidate-old)) if sor else candidate
        old_x,old_y=force[i+1],force[i+2]
        if sor:
            vx=z[i+1]+DDOT(n,A[i+1].ctypes,1,force.ctypes,1)
            vy=z[i+2]+DDOT(n,A[i+2].ctypes,1,force.ctypes,1)
        else:
            DGEMV(102,112,n,2,1.,A[i+1:].ctypes,n,force.ctypes,1,0.,tangent.ctypes,1)
            vx,vy=z[i+1]+tangent[0],z[i+2]+tangent[1]
        x,y=old_x-vx/steps[k],old_y-vy/steps[k]
        limit=mu*force[i]
        factor=min(1.,limit/max(math.hypot(x,y),1e-300))
        if sor:
            tx=old_x+omega*(x*factor-old_x)
            ty=old_y+omega*(y*factor-old_y)
            factor=min(1.,limit/max(math.hypot(tx,ty),1e-300))
            force[i+1],force[i+2]=tx*factor,ty*factor
        else:
            force[i+1],force[i+2]=x*factor,y*factor
    DGEMV(102,112,n,n,1.,A.ctypes,n,force.ctypes,1,0.,velocity.ctypes,1)
    for i in range(n):
        velocity[i]=z[i]+velocity[i]
    value=0.
    for k in range(len(gaps)):
        i=3*k
        value=max(value,abs(min(A[i,i]*force[i],velocity[i]+gaps[k]/dt)))
        x,y=force[i+1]-velocity[i+1]/steps[k],force[i+2]-velocity[i+2]/steps[k]
        factor=min(1.,mu*force[i]/max(math.hypot(x,y),1e-300))
        value=max(value,math.hypot(force[i+1]-x*factor,force[i+2]-y*factor)*steps[k])
    return value


@njit(cache=False, fastmath=False, parallel=False)
def loop(A,z,gaps,dt,mu,steps,scale,tol,maxiter,omega,sor):
    force=np.zeros(len(z))
    tangent=np.empty(2)
    velocity=np.empty(len(z))
    for iteration in range(maxiter):
        value=sweep(A,z,gaps,dt,mu,steps,force,omega,sor,tangent,velocity)
        if value/scale<=tol:
            return force,iteration+1,True
    return force,maxiter,False


def phase(A,z,gaps,dt,mu,steps,scale,tol,maxiter,omega=1.,sor=False):
    arrays=[np.asarray(v,dtype=np.float64) for v in (A,z,gaps,steps)]
    A,z,gaps,steps=arrays
    n=len(z) if z.ndim==1 else -1
    if (n<=0 or gaps.ndim!=1 or steps.shape!=gaps.shape or n!=3*len(gaps)
        or A.shape!=(n,n) or any(not v.flags.c_contiguous for v in arrays)
        or any(not np.isfinite(v).all() for v in arrays)
        or not np.isfinite([dt,mu,scale,tol,maxiter,omega]).all()
        or min(dt,scale,tol,omega)<=0 or mu<0 or maxiter<1 or int(maxiter)!=maxiter
        or np.any(np.diag(A)[::3]<=0) or np.any(steps<=0)):
        raise ValueError('invalid compiled scalar inputs')
    start=time.perf_counter()
    answer=loop(A,z,gaps,float(dt),float(mu),steps,float(scale),float(tol),int(maxiter),float(omega),bool(sor))
    work['loop_s']+=time.perf_counter()-start
    work['sweeps']+=int(answer[1])
    work['sor_calls' if sor else 'pgs_calls']+=1
    return answer


def sor_solve(vfree,mobility,jacobian,gaps,dt,friction,tol,maxiter):
    vfree=s63.contact_model.finite(vfree)
    mobility=s63.contact_model.finite(mobility)
    if not len(gaps):
        s63._stats['solves']+=1
        return vfree,{'iterations':0,'residual':0.,'force_residual':0.,'dissipation':0.,'reactions':[],'solver':'projected_sor'}
    A=jacobian@mobility@jacobian.T
    z=jacobian@vfree
    scale=max(np.linalg.norm(vfree),1e-15)
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(len(gaps))])
    force,used,converged=phase(A,z,gaps,dt,friction,steps,scale,tol,maxiter,s63.RELAXATION,True)
    if converged:
        answer=s50._finish(vfree,mobility,jacobian,force,z,A,gaps,dt,friction,steps,used,'projected_sor',{'relaxation':s63.RELAXATION})
        s63._stats['solves']+=1
        s63._stats['iterations']+=used
        return answer
    s63._stats['failures']+=1
    raise RuntimeError('direct contact residual nonconvergence')


def make_primary():
    original=inspect.getsource(s50._solve)
    tree=ast.parse(original)
    body=tree.body[0].body
    matches=[i for i,node in enumerate(body) if isinstance(node,ast.For) and isinstance(node.target,ast.Name) and node.target.id=='iteration']
    if len(matches)!=1:
        raise RuntimeError('Stage50 PGS source structure changed')
    replacement=ast.parse('''
force, used, converged = compiled_phase(A,z,gaps,dt,friction,steps,scale,tol,maxiter)
if converged:
    _stats['standard_solves'] += 1
    return _finish(vfree,mobility,jacobian,force,z,A,gaps,dt,friction,steps,used,'standard_cold_pgs',{})
''').body
    i=matches[0]
    body[i:i+1]=replacement
    ast.fix_missing_locations(tree)
    namespace=dict(s50.__dict__)
    namespace.update(compiled_phase=phase,_project=scalar.project,_residual=scalar.residual)
    exec(compile(tree,'<Stage136:Stage50_PGS_only>','exec'),namespace)
    return namespace['_solve'],ast.unparse(tree)


PRIMARY,PRIMARY_SOURCE=make_primary()


@contextmanager
def scope():
    old=(s50._solve,scalar.sor_solve)
    s50._solve,scalar.sor_solve=PRIMARY,sor_solve
    try:
        yield
    finally:
        s50._solve,scalar.sor_solve=old


def warmup():
    start=time.perf_counter()
    for sor in [False,True]:
        phase(np.eye(3),np.array([-1.,.2,-.1]),np.zeros(1),.01,.3,np.ones(1),1.,1e-10,25000,1.7 if sor else 1.,sor)
    return time.perf_counter()-start
