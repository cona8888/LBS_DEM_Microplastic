"""Scalar arithmetic for the existing two-tangent Coulomb projection and SOR.

This changes implementation cost, not the contact equations or thresholds.
Stage50 _finish remains the sole acceptance gate. The functions are scoped to
the Stage74 wrapper and do not modify immutable earlier source files.
"""
import math
import numpy as np

import inertial_contact_seeded_lm_v1 as s50
import inertial_contact_projected_sor_v1 as s63


def project(ft, vt, step, limit):
    x = float(ft[0] - vt[0] / step)
    y = float(ft[1] - vt[1] / step)
    factor = min(1., limit / max(math.hypot(x, y), 1e-300))
    return np.array((x * factor, y * factor))


def residual(force, z, A, gaps, dt, friction, steps):
    velocity = z + A @ force
    value = 0.
    for k in range(len(gaps)):
        i = 3 * k
        value = max(value, abs(min(A[i, i] * force[i], velocity[i] + gaps[k] / dt)))
        x = float(force[i+1] - velocity[i+1] / steps[k])
        y = float(force[i+2] - velocity[i+2] / steps[k])
        factor = min(1., friction * force[i] / max(math.hypot(x, y), 1e-300))
        value = max(value, math.hypot(float(force[i+1] - x * factor),
                                      float(force[i+2] - y * factor)) * steps[k])
    return value


def sor_solve(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
    vfree = s63.contact_model.finite(vfree)
    mobility = s63.contact_model.finite(mobility)
    if not len(gaps):
        s63._stats["solves"] += 1
        return vfree, {"iterations": 0, "residual": 0., "force_residual": 0.,
                       "dissipation": 0., "reactions": [], "solver": "projected_sor"}
    A = jacobian @ mobility @ jacobian.T
    z = jacobian @ vfree
    force = np.zeros(len(z))
    scale = max(np.linalg.norm(vfree), 1e-15)
    steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max()
                      for k in range(len(gaps))])
    omega = s63.RELAXATION
    for iteration in range(maxiter):
        for k in range(len(gaps)):
            i = 3 * k
            old = force[i]
            vn = z[i] + A[i] @ force + gaps[k] / dt
            candidate = max(0., old - vn / A[i, i])
            force[i] = max(0., old + omega * (candidate - old))
            old_x = float(force[i+1])
            old_y = float(force[i+2])
            vt_x = float(z[i+1] + A[i+1] @ force)
            vt_y = float(z[i+2] + A[i+2] @ force)
            x = old_x - vt_x / steps[k]
            y = old_y - vt_y / steps[k]
            limit = friction * force[i]
            factor = min(1., limit / max(math.hypot(x, y), 1e-300))
            trial_x = old_x + omega * (x * factor - old_x)
            trial_y = old_y + omega * (y * factor - old_y)
            factor = min(1., limit / max(math.hypot(trial_x, trial_y), 1e-300))
            force[i+1] = trial_x * factor
            force[i+2] = trial_y * factor
        if residual(force, z, A, gaps, dt, friction, steps) / scale <= tol:
            answer = s50._finish(vfree, mobility, jacobian, force, z, A, gaps, dt,
                                 friction, steps, iteration+1, "projected_sor",
                                 {"relaxation": omega})
            s63._stats["solves"] += 1
            s63._stats["iterations"] += iteration+1
            return answer
    s63._stats["failures"] += 1
    raise RuntimeError("direct contact residual nonconvergence")
