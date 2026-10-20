"""Stateless analytic complementarity refinement of same-system rejected seeds.

Primary/reduced successful paths retain priority when this scope is installed
outside Stage169. Every seed is generated on these exact input matrices; no
inter-pose reaction history, changed gaps, contact law, or gate is used.
"""
from contextlib import contextmanager
import time
import numpy as np
from scipy.optimize import least_squares
import projection_fallback_dispatch_v1 as fallback
import importlib.util
from pathlib import Path
# The older algorithm-review directory has a module with the same basename.
# Bind this exact local equation source, not the mutable sys.path search order.
_spec=importlib.util.spec_from_file_location('stage194_exact_analytic_equations',Path(__file__).with_name('probe_analytic_contact_v1.py'))
analytic=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(analytic)
q=analytic.q;fast=q.job.fast;gate=fast.gate
NAME='stage194_analytic_same_system_rejected_seed_v1'
ERRORS=fallback.ERRORS

def solve(vfree,mobility,jacobian,gaps,dt,friction,tol,maxiter,stop_epoch=None):
    v,M,J,g=[np.asarray(x,float) for x in (vfree,mobility,jacobian,gaps)]
    if v.shape!=(6,) or M.shape!=(6,6) or J.shape!=(9,6) or g.shape!=(3,):raise ValueError('three-contact six-DOF domain only')
    if not all(np.isfinite(x).all() for x in (v,M,J,g)) or not np.isfinite([dt,friction,tol]).all() or dt<=0 or friction<=0 or tol!=1e-10:raise ValueError('invalid original-law input')
    if not np.allclose(M,M.T,rtol=0,atol=1e-12*np.linalg.norm(M)):raise ValueError('symmetric mobility required')
    np.linalg.cholesky(M);vs=max(np.linalg.norm(v),1e-15)
    if np.max(np.abs(g/dt))>1e-5*vs:raise ValueError('outside nearly closed domain')
    if stop_epoch is None or not np.isfinite(stop_epoch):raise ValueError('explicit finite deadline required')
    order=sorted(range(3),key=lambda k:(float(g[k]),*J[3*k:3*k+3].ravel().tolist()));idx=[3*k+j for k in order for j in range(3)];JJ=J[idx];gg=g[order]
    both,A,z,steps,scales,vs=analytic.system(v,M,JJ,gg,dt,friction);seeds=[];finish=gate._finish
    def observe(vv,MM,jj,f,zz,AA,gap,dtt,mu,ss,it,name,extra):
        try:return finish(vv,MM,jj,f,zz,AA,gap,dtt,mu,ss,it,name,extra)
        except RuntimeError as error:
            seeds.append({'force':np.asarray(f).copy(),'error':str(error),'solver':name,'residual':float(gate._residual(f,zz,AA,gap,dtt,mu,ss)/vs)});raise
    gate._finish=observe
    try:
        # Successful candidate here is only a seed, not a bypass of this method's gates.
        answer=fast.solve(v,M,JJ,gg,dt,friction,tol,maxiter)
        seeds.append({'force':np.asarray(answer[1]['reactions']),'error':None,'solver':answer[1]['solver'],'residual':answer[1]['residual']})
    except (RuntimeError,ValueError,np.linalg.LinAlgError,FloatingPointError):pass
    finally:gate._finish=finish
    ordered=sorted(enumerate(seeds),key=lambda p:(p[1]['residual'],p[0]))[:8]
    for seed_index,(source_index,seed) in enumerate(ordered):
        if time.time()>=stop_epoch:raise RuntimeError('diagnostic work cutoff reached')
        opt=least_squares(lambda y:both(y)[0],seed['force']*scales/vs,jac=lambda y:both(y)[1],method='trf',xtol=1e-14,ftol=1e-14,gtol=1e-14,max_nfev=2000,x_scale='jac')
        f=np.empty(9);f[idx]=opt.x*vs/scales;seed_original=np.empty(9);seed_original[idx]=seed['force']
        original_A=J@M@J.T;original_z=J@v
        original_steps=np.array([np.linalg.eigvalsh(original_A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(3)])
        extra={'original_gaps_preserved':True,'analytic_complementarity_jacobian':True,'canonical_order':order,
           'same_system_seed':True,'seed_candidate_count':len(seeds),'seed_index':seed_index,'source_candidate_index':source_index,
           'seed_reactions':seed_original.tolist(),'seed_solver':seed['solver'],'seed_gate_error':seed['error'],'semismooth_nfev':int(opt.nfev)}
        try:return finish(v,M,J,f,original_z,original_A,g,dt,friction,original_steps,int(opt.nfev),NAME,extra)
        except RuntimeError:continue
    raise RuntimeError('direct contact residual nonconvergence')

@contextmanager
def scope(runtime,enabled=False,stop_epoch=None):
    if type(enabled) is not bool:raise ValueError('explicit Boolean opt-in required')
    if not enabled:yield;return
    with fallback.scope(runtime,True,stop_epoch):
        original=runtime.mixed.solve
        def preferred(v,M,J,g,dt,mu,tol,maxiter):
            if len(g)==3:
                try:return solve(v,M,J,g,dt,mu,tol,maxiter,stop_epoch)
                except (RuntimeError,ValueError,np.linalg.LinAlgError,FloatingPointError):pass
            return original(v,M,J,g,dt,mu,tol,maxiter)
        runtime.mixed.solve=preferred
        try:yield
        finally:runtime.mixed.solve=original
