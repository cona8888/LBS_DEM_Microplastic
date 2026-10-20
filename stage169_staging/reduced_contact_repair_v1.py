"""Opt-in, failure-only one-stick/two-slide three-contact fallback.

Keep the original gaps, Coulomb law, mobility and final acceptance gates.
Normal closure plus one sticking contact leave one rigid velocity coordinate.
Eliminate sliding tangential forces analytically, bracket the remaining scalar
force-balance determinant, then judge the reconstructed force with the original
gate. Not a universal solver or a uniqueness certificate. No cross-pose cache.
"""
from contextlib import contextmanager
from pathlib import Path
import sys,time
import numpy as np
from scipy.optimize import brentq
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage50_staging'))
import inertial_contact_seeded_lm_v1 as gate

NAME='stage169_reduced_one_stick_two_slide'
GRID=np.sort(np.r_[0.,np.logspace(-11,2,79),-np.logspace(-11,2,79)])
telemetry=[]


def solve(vfree,mobility,jacobian,gaps,dt,friction,tol,maxiter):
    v,M,J,g=[np.asarray(x,float) for x in (vfree,mobility,jacobian,gaps)]
    if g.shape!=(3,) or v.shape!=(6,) or M.shape!=(6,6) or J.shape!=(9,6):
        raise RuntimeError('stage169 supports exactly three six-DOF contacts')
    if not all(np.isfinite(x).all() for x in (v,M,J,g)) or not np.isfinite([dt,friction]).all() or dt<=0 or friction<=0:
        raise RuntimeError('stage169 invalid physical input')
    if not np.allclose(M,M.T,rtol=0,atol=1e-12*np.linalg.norm(M)):
        raise RuntimeError('stage169 requires symmetric positive mobility')
    np.linalg.cholesky(M)
    B=np.linalg.inv(M);vs=max(np.linalg.norm(v),1e-15);fs=max(np.linalg.norm(B@v),1e-30)
    A=J@M@J.T;z=J@v
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(3)])
    calls=0;rejected=0
    for stick in range(3):
        ci=[];target=[]
        for k in range(3):
            ci.append(J[3*k]);target.append(-g[k]/dt/vs)
            if k==stick:ci.extend(J[3*k+1:3*k+3]);target.extend([0.,0.])
        C=np.asarray(ci);target=np.asarray(target)
        u,s,vh=np.linalg.svd(C,full_matrices=True)
        if sum(s>s[0]*1e-12)!=5:continue
        q0=vh[:5].T@((u[:,:5].T@target)/s[:5]);direction=vh[5]
        if np.linalg.norm(C@q0-target)>1e-11*max(np.linalg.norm(target),1e-15):continue

        def evaluate(beta):
            nonlocal calls
            calls+=1
            if calls>2500:raise RuntimeError('stage169 bounded scalar budget')
            q=q0+direction*beta;w=J@q;cols=[]
            for k in range(3):
                if k==stick:
                    for j in range(3):
                        col=np.zeros(9);col[3*k+j]=1.;cols.append(col)
                else:
                    vt=w[3*k+1:3*k+3];speed=np.linalg.norm(vt)
                    if speed==0:raise RuntimeError('stage169 undefined slide direction')
                    col=np.zeros(9);col[3*k]=1.;col[3*k+1:3*k+3]=-friction*vt/speed;cols.append(col)
            E=np.column_stack(cols);H=J.T@E;rhs=B@(vs*q-v)/fs
            return float(np.linalg.det(np.column_stack([H,rhs]))),E,H,rhs

        samples=[]
        for beta in GRID:
            try:samples.append(evaluate(beta)[0])
            except RuntimeError as error:
                if str(error)!='stage169 undefined slide direction':raise
                samples.append(float('nan'))
        brackets=[(GRID[i],GRID[i+1]) for i in range(len(GRID)-1)
                  if np.isfinite(samples[i:i+2]).all() and samples[i]*samples[i+1]<0]
        # An exact zero sample must also be judged, not silently discarded.
        roots=[GRID[i] for i,value in enumerate(samples) if value==0.]
        for left,right in brackets:
            try:roots.append(brentq(lambda b:evaluate(b)[0],left,right,xtol=1e-20,rtol=1e-14,maxiter=200))
            except (ValueError,RuntimeError):continue
        for beta in roots:
            try:
                det,E,H,rhs=evaluate(beta)
                reduced=np.linalg.lstsq(H,rhs,rcond=1e-12)[0];force=E@reduced*fs
                q,h=gate._finish(v,M,J,force,z,A,g,dt,friction,steps,calls,NAME,
                    {'sticking_contact_index':stick,'scalar_coordinate':float(beta),'scalar_evaluations':calls,
                     'rejected_reduced_candidates':rejected,'original_gaps_preserved':True})
            except (RuntimeError,ValueError,FloatingPointError,np.linalg.LinAlgError):
                rejected+=1;continue
            return q,h
    raise RuntimeError('direct contact residual nonconvergence')


@contextmanager
def scope(runtime,enabled=False):
    """Patch only the existing failure fallback, never a successful primary call."""
    if type(enabled) is not bool:raise ValueError('explicit Boolean mode required')
    if not enabled:
        yield
        return
    original=runtime.mixed.solve
    def attempt(*args,**kwargs):
        started=time.perf_counter();row={}
        try:
            q,h=solve(*args,**kwargs)
        except (RuntimeError,ValueError,FloatingPointError,np.linalg.LinAlgError) as error:
            row.update(reduced_accepted=False,reduced_error=str(error))
            return original(*args,**kwargs)
        else:
            row.update(reduced_accepted=True,solver=h['solver'],residual=h['residual'],force_residual=h['force_residual'],
                scalar_evaluations=h['scalar_evaluations'],dt_s=float(args[4]))
            return q,h
        finally:
            row['wall_s']=time.perf_counter()-started;telemetry.append(row)
    runtime.mixed.solve=attempt
    try:yield
    finally:runtime.mixed.solve=original
