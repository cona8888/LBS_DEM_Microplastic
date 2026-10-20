"""Opt-in stateless near-rest dispatch and batched original-law scalar scan.

No contact state, reaction or mode is reused across poses. The scan retains
Stage169's grid, brackets, SVD ranks, Brent settings and original final gates.
An earlier candidate is used only for three nearly closed contacts whose
certified outgoing generalized speed is at most 1e-4 of the free speed.
Otherwise the qualified primary plus failure-only repair remains in force.
"""
from contextlib import contextmanager
from pathlib import Path
import sys, time, datetime
import numpy as np
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'stage169_staging'))
import reduced_contact_repair_v2 as old
gate = old.gate
NAME = 'stage172_batched_reduced_near_rest_v1'
END_UTC = datetime.datetime.fromisoformat('2026-09-24T02:46:55+00:00').timestamp()
telemetry = []
attempts = []
capture_systems = False


def scalar_solve(v, M, J, g, dt, mu, tol, maxiter):
    B = np.linalg.inv(M)
    vs = max(np.linalg.norm(v), 1e-15)
    fs = max(np.linalg.norm(B@v), 1e-30)
    A, z = J@M@J.T, J@v
    steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(3)])
    calls, rejected = 0, 0
    for stick in range(3):
        ci, target = [], []
        for k in range(3):
            ci.append(J[3*k]); target.append(-g[k]/dt/vs)
            if k == stick:
                ci.extend(J[3*k+1:3*k+3]); target.extend([0., 0.])
        C, target = np.asarray(ci), np.asarray(target)
        u, s, vh = np.linalg.svd(C, full_matrices=True)
        if sum(s > s[0]*1e-12) != 5:
            continue
        q0 = vh[:5].T@((u[:,:5].T@target)/s[:5])
        direction = vh[5]
        if np.linalg.norm(C@q0-target) > 1e-11*max(np.linalg.norm(target),1e-15):
            continue

        def batch(beta):
            nonlocal calls
            beta = np.atleast_1d(beta)
            calls += len(beta)
            if calls > 2500:
                raise RuntimeError('stage172 bounded scalar budget')
            q = q0[None,:]+beta[:,None]*direction
            w = q@J.T
            E = np.zeros((len(beta), 9, 5))
            col = 0
            valid = np.ones(len(beta), dtype=bool)
            for k in range(3):
                if k == stick:
                    for j in range(3):
                        E[:,3*k+j,col] = 1.; col += 1
                else:
                    vt = w[:,3*k+1:3*k+3]
                    speed = np.linalg.norm(vt, axis=1)
                    valid &= speed > 0
                    E[:,3*k,col] = 1.
                    E[:,3*k+1:3*k+3,col] = -mu*vt/np.where(speed>0,speed,1.)[:,None]
                    col += 1
            H = J.T@E
            rhs = ((vs*q-v)@B.T)/fs
            determinant = np.linalg.det(np.concatenate((H,rhs[:,:,None]),axis=2))
            determinant[~valid] = np.nan
            return determinant, E, H, rhs

        samples = batch(old.scalar.GRID)[0]
        roots = [old.scalar.GRID[i] for i,x in enumerate(samples) if x == 0.]
        for i in range(len(samples)-1):
            if not np.isfinite(samples[i:i+2]).all() or samples[i]*samples[i+1] >= 0:
                continue
            try:
                roots.append(brentq(lambda b:batch(b)[0][0],old.scalar.GRID[i],old.scalar.GRID[i+1],
                                    xtol=1e-20,rtol=1e-14,maxiter=200))
            except (ValueError, RuntimeError):
                continue
        for beta in roots:
            try:
                det, E, H, rhs = batch(beta)
                force = E[0]@np.linalg.lstsq(H[0],rhs[0],rcond=1e-12)[0]*fs
                return gate._finish(v,M,J,force,z,A,g,dt,mu,steps,calls,NAME,
                    {'sticking_contact_index':stick,'scalar_coordinate':float(beta),'scalar_evaluations':calls,
                     'rejected_reduced_candidates':rejected,'original_gaps_preserved':True,'batched_scan':True})
            except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError):
                rejected += 1
    raise RuntimeError('direct contact residual nonconvergence')


def solve(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
    v, M, J, g = [np.asarray(x,float) for x in (vfree,mobility,jacobian,gaps)]
    if g.shape!=(3,) or v.shape!=(6,) or M.shape!=(6,6) or J.shape!=(9,6):
        raise RuntimeError('stage172 supports exactly three six-DOF contacts')
    if (not all(np.isfinite(x).all() for x in (v,M,J,g))
        or not np.isfinite([dt,friction]).all() or dt<=0 or friction<=0):
        raise RuntimeError('stage172 invalid physical input')
    if not np.allclose(M,M.T,rtol=0,atol=1e-12*np.linalg.norm(M)):
        raise RuntimeError('stage172 requires symmetric positive mobility')
    np.linalg.cholesky(M)
    try:
        q,h = old.constrained_stick(v,M,J,g,dt,friction)
    except RuntimeError:
        q,h = scalar_solve(v,M,J,g,dt,friction,tol,maxiter)
    h['solver'] = NAME
    return q,h


@contextmanager
def scope(runtime, enabled=False):
    if type(enabled) is not bool:
        raise ValueError('explicit Boolean mode required')
    if not enabled:
        yield; return
    portfolio = runtime.probe.RECOVERY.portfolio
    original = portfolio._solve

    def early(v,M,J,g,dt,mu,tol,maxiter):
        if time.time() >= END_UTC:
            raise RuntimeError('four-hour work cutoff reached')
        scale = max(np.linalg.norm(v),1e-15)
        eligible = len(g)==3 and mu>0 and dt>0 and np.max(np.abs(g))/dt <= 1e-5*scale
        if eligible:
            start = time.perf_counter()
            row = {'dt_s':float(dt),'gaps_m':list(g)}
            try:
                q,h = solve(v,M,J,g,dt,mu,tol,maxiter)
                row['near_rest_ratio'] = float(np.linalg.norm(q)/scale)
                use = row['near_rest_ratio'] <= 1e-4
                row.update(accepted=use,health=h,wall_s=time.perf_counter()-start)
                if capture_systems:
                    row.update(vfree=np.asarray(v).tolist(),mobility=np.asarray(M).tolist(),jacobian=np.asarray(J).tolist(),
                               friction=float(mu),velocity=q.tolist())
                attempts.append(row)
                if use:
                    telemetry.append(row)
                    return q,h
            except (RuntimeError,ValueError,FloatingPointError,np.linalg.LinAlgError) as error:
                row.update(accepted=False,error=str(error),wall_s=time.perf_counter()-start)
                attempts.append(row)
        return original(v,M,J,g,dt,mu,tol,maxiter)

    with old.scope(runtime,True):
        portfolio._solve = early
        try:
            yield
        finally:
            portfolio._solve = original
