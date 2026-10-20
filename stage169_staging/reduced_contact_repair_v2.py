"""Failure-only original-law contact feasibility, including redundant forces.

For two/three sticking contacts, solve kinematics, then select reactions in
the force-balance nullspace subject to the actual Coulomb cones. The earlier
unconstrained least-squares reaction need not lie in those cones. For one
sticking contact use the bounded scalar-root method. Original final gates
remain authoritative; no gap alteration, compliance, damping or force history.
"""
from contextlib import contextmanager
import itertools,time
import numpy as np
from scipy.optimize import minimize
import reduced_contact_repair_v1 as scalar
gate=scalar.gate
NAME='stage169_cone_feasible_reduced_modes_v2'
telemetry=[]


def constrained_stick(v,M,J,g,dt,mu):
    B=np.linalg.inv(M);vs=max(np.linalg.norm(v),1e-15);fs=max(np.linalg.norm(B@v),1e-30)
    A=J@M@J.T;z=J@v
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(3)])
    modes=[[1,1,1]]+[[2 if k==sliding else 1 for k in range(3)] for sliding in range(3)]
    for mode in modes:
        rows=[];target=[]
        for k,m in enumerate(mode):
            rows.append(J[3*k]);target.append(-g[k]/dt/vs)
            if m==1:rows.extend(J[3*k+1:3*k+3]);target.extend([0.,0.])
        C=np.asarray(rows);target=np.asarray(target);u,s,vh=np.linalg.svd(C,full_matrices=True)
        if sum(s>s[0]*1e-12)!=6:continue
        q0=vh[:6].T@((u[:,:6].T@target)/s[:6])
        if np.linalg.norm(C@q0-target)>1e-11*max(np.linalg.norm(target),1e-15):continue
        w=J@q0;cols=[];valid=True
        for k,m in enumerate(mode):
            if m==1:
                for j in range(3):
                    col=np.zeros(9);col[3*k+j]=1.;cols.append(col)
            else:
                vt=w[3*k+1:3*k+3];speed=np.linalg.norm(vt)
                if speed==0:valid=False;break
                col=np.zeros(9);col[3*k]=1.;col[3*k+1:3*k+3]=-mu*vt/speed;cols.append(col)
        if not valid:continue
        E=np.column_stack(cols);H=J.T@E;rhs=B@(q0*vs-v)/fs
        u,s,vh=np.linalg.svd(H,full_matrices=True)
        rank=int(sum(s>s[0]*1e-12))
        if rank!=6:continue
        coefficients=vh[:rank].T@((u[:,:rank].T@rhs)/s[:rank]);Z=vh[rank:].T
        f0=E@coefficients;F=E@Z
        # This is a convex feasibility problem in 1 or 3 redundant force DOFs.
        def inequalities(y):
            f=f0+F@y;values=[]
            for k,m in enumerate(mode):
                i=3*k;values.append(f[i])
                if m==1:values.append(mu*f[i]-np.linalg.norm(f[i+1:i+3]))
            return np.asarray(values)
        def derivative(y):
            f=f0+F@y;rows=[]
            for k,m in enumerate(mode):
                i=3*k;rows.append(F[i])
                if m==1:
                    tang=f[i+1:i+3];direction=tang/max(np.linalg.norm(tang),1e-300)
                    rows.append(mu*F[i]-direction@F[i+1:i+3])
            return np.asarray(rows)
        seeds=[np.zeros(Z.shape[1])]
        for seed in seeds:
            # Feasibility only: minimizing reaction norm drives the iterate onto
            # a cone boundary and can stop just outside it. No unique reaction
            # distribution is claimed for a rigid redundant contact assembly.
            opt=minimize(lambda y:0.,seed,jac=lambda y:np.zeros_like(y),method='SLSQP',
                constraints=[{'type':'ineq','fun':inequalities,'jac':derivative}],
                options={'maxiter':100,'ftol':1e-14})
            force=(f0+F@opt.x)*fs
            try:
                return gate._finish(v,M,J,force,z,A,g,dt,mu,steps,int(opt.nit),NAME,
                    {'contact_modes':mode,'force_nullity':int(Z.shape[1]),'cone_optimizer_success':bool(opt.success),
                     'scalar_evaluations':0,'original_gaps_preserved':True})
            except (RuntimeError,ValueError,FloatingPointError,np.linalg.LinAlgError):continue
    raise RuntimeError('direct contact residual nonconvergence')


def solve(vfree,mobility,jacobian,gaps,dt,friction,tol,maxiter):
    v,M,J,g=[np.asarray(x,float) for x in (vfree,mobility,jacobian,gaps)]
    if g.shape!=(3,) or v.shape!=(6,) or M.shape!=(6,6) or J.shape!=(9,6):raise RuntimeError('stage169 supports exactly three six-DOF contacts')
    if not all(np.isfinite(x).all() for x in (v,M,J,g)) or not np.isfinite([dt,friction]).all() or dt<=0 or friction<=0:raise RuntimeError('stage169 invalid input')
    if not np.allclose(M,M.T,rtol=0,atol=1e-12*np.linalg.norm(M)):raise RuntimeError('stage169 symmetric mobility required')
    np.linalg.cholesky(M)
    try:return constrained_stick(v,M,J,g,dt,friction)
    except RuntimeError:
        q,h=scalar.solve(v,M,J,g,dt,friction,tol,maxiter)
        h['solver']=NAME;h['reduced_mode']='one_stick_two_slide'
        return q,h


@contextmanager
def scope(runtime,enabled=False):
    if type(enabled) is not bool:raise ValueError('explicit Boolean mode required')
    if not enabled:
        yield
        return
    original=runtime.mixed.solve
    def attempt(*args,**kwargs):
        started=time.perf_counter();row={}
        try:q,h=solve(*args,**kwargs)
        except (RuntimeError,ValueError,FloatingPointError,np.linalg.LinAlgError) as error:
            row.update(reduced_accepted=False,reduced_error=str(error));return original(*args,**kwargs)
        else:
            row.update(reduced_accepted=True,solver=h['solver'],residual=h['residual'],force_residual=h['force_residual'],
                scalar_evaluations=h['scalar_evaluations'],dt_s=float(args[4]));return q,h
        finally:row['wall_s']=time.perf_counter()-started;telemetry.append(row)
    runtime.mixed.solve=attempt
    try:yield
    finally:runtime.mixed.solve=original
