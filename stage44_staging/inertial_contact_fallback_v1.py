"""Cold-PGS fallback for difficult multi-contact Coulomb states.

The accepted Stage42 solve is attempted first.  On its exact
``contact nonconvergence`` failure only, the force iteration restarts from zero
with deterministic under-relaxation.  The contact law, ordering, residual and
tolerance are unchanged; convex blending keeps every iterate inside each
Coulomb cone.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage41_staging"), str(ROOT / "stage42_staging")]
import inertial_contact_cold_optimized_v1 as stage41
import inertial_contact_robust_v1 as stage42

base = stage42.base
generalized_mass_matrix = stage42.generalized_mass_matrix
stokes_generalized_resistance = stage42.stokes_generalized_resistance
contact_model = stage42.contact_model
finite_re = stage42.finite_re
contact_solve = stage42.contact_solve

_standard = stage41._solve_prepared
_stats = {"standard_solves": 0, "fallback_solves": 0,
          "fallback_failures": 0, "damping_used": {}}


def stats():
    return {**_stats, "damping_used": dict(_stats["damping_used"])}


def _damped(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter, omega):
    vfree = contact_model.finite(vfree)
    mobility = contact_model.finite(mobility)
    if not len(gaps):
        return vfree, {"iterations": 0, "residual": 0., "force_residual": 0.,
                       "dissipation": 0., "reactions": [],
                       "solver": "underrelaxed_cold_pgs", "damping": omega}
    A = jacobian @ mobility @ jacobian.T
    z = jacobian @ vfree
    force = np.zeros(len(z))
    scale = max(np.linalg.norm(vfree), 1e-15)
    steps = [np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max()
             for k in range(len(gaps))]
    for iteration in range(maxiter):
        for k in range(len(gaps)):
            i = 3*k
            old = force[i:i+3].copy()
            vn = z[i] + A[i] @ force + gaps[k] / dt
            normal = max(0., force[i] - vn / A[i, i])
            trial_force = force.copy()
            trial_force[i] = normal
            vt = z[i+1:i+3] + A[i+1:i+3] @ trial_force
            tangential = old[1:] - vt / steps[k]
            limit = friction * normal
            norm = np.linalg.norm(tangential)
            tangential *= min(1., limit / max(norm, 1e-300))
            target = np.r_[normal, tangential]
            force[i:i+3] = old + omega * (target - old)
        vel = z + A @ force
        residual = 0.
        for k in range(len(gaps)):
            i = 3*k
            normal_velocity = vel[i] + gaps[k] / dt
            residual = max(residual, abs(min(A[i, i] * force[i], normal_velocity)))
            trial = force[i+1:i+3] - vel[i+1:i+3] / steps[k]
            limit = friction * force[i]
            norm = np.linalg.norm(trial)
            projection = trial * min(1., limit / max(norm, 1e-300))
            residual = max(residual, np.linalg.norm(force[i+1:i+3] - projection) * steps[k])
        if residual / scale <= tol:
            break
    else:
        raise RuntimeError("underrelaxed contact nonconvergence")
    velocity = vfree + mobility @ jacobian.T @ force
    force_residual = (np.linalg.norm(np.linalg.solve(mobility, velocity-vfree) - jacobian.T @ force)
                      / max(np.linalg.norm(jacobian.T @ force), 1e-30))
    tangential_work = sum(float(force[3*k+1:3*k+3] @ vel[3*k+1:3*k+3])
                          for k in range(len(gaps)))
    if tangential_work > 1e-8 * max(np.linalg.norm(force) * scale, 1e-30):
        raise RuntimeError("friction generates energy")
    return contact_model.finite(velocity), {
        "iterations": iteration + 1, "residual": residual / scale,
        "force_residual": float(force_residual), "dissipation": -tangential_work,
        "reactions": force.tolist(), "solver": "underrelaxed_cold_pgs",
        "damping": omega}


def _solve_with_fallback(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
    try:
        answer = _standard(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter)
        _stats["standard_solves"] += 1
        answer[1]["solver"] = "standard_cold_pgs"
        answer[1]["damping"] = 1.0
        return answer
    except RuntimeError as exc:
        if str(exc) != "contact nonconvergence":
            raise
    for omega in (0.5, 0.25):
        try:
            answer = _damped(vfree, mobility, jacobian, gaps, dt, friction, tol,
                             max(50000, 2 * maxiter), omega)
            _stats["fallback_solves"] += 1
            key = str(omega)
            _stats["damping_used"][key] = _stats["damping_used"].get(key, 0) + 1
            return answer
        except RuntimeError as exc:
            if str(exc) != "underrelaxed contact nonconvergence":
                raise
    _stats["fallback_failures"] += 1
    raise RuntimeError("contact nonconvergence after deterministic damping fallback")


def inertial_contact_step(*args, **kwargs):
    original = stage41._solve_prepared
    stage41._solve_prepared = _solve_with_fallback
    try:
        return stage42.inertial_contact_step(*args, **kwargs)
    finally:
        stage41._solve_prepared = original
