"""Compile the full original two-contact PGS seed without fast math.

The 25,000-sweep budget, update order, convergence test, seeded LM fallback,
and Stage50 physical acceptance gates are retained. Single-threaded CPU JIT;
larger/smaller contact sets and recovery use the original implementation.
"""
import math
import sys
from pathlib import Path

import numpy as np
from numba import njit
from scipy.optimize import root

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage50_staging"), str(ROOT / "stage70_staging"),
                str(ROOT / "stage81_staging")]
import inertial_contact_seeded_lm_v1 as gate
import inertial_contact_runtime_portfolio_v1 as portfolio
import trajectory_combined_scalar_v1 as parent

_original = gate._solve
_stats = {"native_calls": 0, "native_pgs_converged": 0, "native_seeded_lm": 0}


@njit(cache=True, fastmath=False)
def pgs_seed(A, z, gaps, dt, friction, steps, scale, tol, maxiter):
    force = np.zeros(len(z))
    for iteration in range(maxiter):
        for k in range(len(gaps)):
            i = 3*k
            vn = z[i] + A[i] @ force + gaps[k]/dt
            force[i] = max(0., force[i]-vn/A[i, i])
            vt = z[i+1:i+3] + A[i+1:i+3] @ force
            x = force[i+1]-vt[0]/steps[k]
            y = force[i+2]-vt[1]/steps[k]
            factor = min(1., friction*force[i]/max(math.hypot(x, y), 1e-300))
            force[i+1] = x*factor
            force[i+2] = y*factor
        velocity = z + A @ force
        residual = 0.
        for k in range(len(gaps)):
            i = 3*k
            residual = max(residual, abs(min(A[i,i]*force[i], velocity[i]+gaps[k]/dt)))
            x = force[i+1]-velocity[i+1]/steps[k]
            y = force[i+2]-velocity[i+2]/steps[k]
            factor = min(1., friction*force[i]/max(math.hypot(x,y), 1e-300))
            residual = max(residual, math.hypot(force[i+1]-x*factor,
                                               force[i+2]-y*factor)*steps[k])
        if residual/scale <= tol:
            return force, iteration+1, True
    return force, maxiter, False


def solve(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
    if len(gaps) != 2 or portfolio.recovery_mode():
        return _original(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter)
    _stats["native_calls"] += 1
    vfree = gate.contact_model.finite(vfree)
    mobility = gate.contact_model.finite(mobility)
    A = jacobian @ mobility @ jacobian.T
    z = jacobian @ vfree
    scale = max(np.linalg.norm(vfree), 1e-15)
    steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max()
                      for k in range(len(gaps))])
    force, iterations, converged = pgs_seed(A, z, np.asarray(gaps), dt,
                                           friction, steps, scale, tol, maxiter)
    if converged:
        answer = gate._finish(vfree, mobility, jacobian, force, z, A, gaps, dt,
                              friction, steps, iterations, "native_standard_cold_pgs", {})
        _stats["native_pgs_converged"] += 1
        return answer
    scales = np.repeat(steps, 3)
    for k in range(len(gaps)):
        scales[3*k] = A[3*k,3*k]
    if np.any(scales <= 0) or not np.isfinite(scales).all():
        raise RuntimeError("nonpositive direct contact scale")

    def equations(u):
        f = u/scales
        velocity = z+A@f
        result = np.empty_like(u)
        for k in range(len(gaps)):
            i = 3*k
            vn = velocity[i]+gaps[k]/dt
            result[i] = np.hypot(u[i],vn)-u[i]-vn
            result[i+1:i+3] = u[i+1:i+3]-steps[k]*gate._project(
                f[i+1:i+3],velocity[i+1:i+3],steps[k],friction*f[i])
        return result/scale

    solved = root(equations, force*scales, method="lm", options={
        "ftol": 1e-14, "xtol": 1e-14, "gtol": 1e-14, "maxiter": 50000})
    answer = gate._finish(vfree,mobility,jacobian,solved.x/scales,z,A,gaps,dt,
                          friction,steps,maxiter+int(solved.nfev),
                          "native_cold_pgs_seeded_scaled_lm", {
                              "pgs_seed_iterations": maxiter,
                              "lm_nfev": int(solved.nfev),
                              "lm_success_flag": bool(solved.success)})
    _stats["native_seeded_lm"] += 1
    return answer


def integrate(*args, **kwargs):
    original = gate._solve
    before = dict(_stats)
    gate._solve = solve
    try:
        result = parent.integrate(*args, **kwargs)
    finally:
        gate._solve = original
    result["native_pgs_stats"] = {k: _stats[k]-before[k] for k in before}
    return result


lubrication_matrix = parent.lubrication_matrix
enrich = parent.enrich
