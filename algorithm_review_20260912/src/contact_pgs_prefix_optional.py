"""UNPROMOTED candidate: exact cold PGS prefix, analytic recovery, Stage53.

This optional path preserves converged <=200-sweep Stage53 PGS calls exactly.
For harder one-to-three-contact systems it solves the unchanged equations via
the separately verified analytic solver before the original 25,000-sweep ceiling.
Hard-contact root selection still needs matrix and timestep qualification.
No historical or accepted module is rebound or modified.
"""
import numpy as np
import contact_dimensionless_lm_v1 as analytic

PREFIX_ITERATIONS = 200
_stats = {"calls": 0, "prefix_passes": 0, "prefix_iterations": 0,
          "analytic_passes": 0, "analytic_rejections": 0,
          "authoritative_fallbacks": 0}


def stats():
    return dict(_stats)


def solve_prepared(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
    """Explicit optional prepared-solver API; original physical gates remain."""
    _stats["calls"] += 1
    if not 0 < len(gaps) <= 3:
        _stats["authoritative_fallbacks"] += 1
        return analytic.stage53._solve(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter)
    # This is the exact Stage50/53 PGS arithmetic and ordering. The prefix
    # changes when another solver is attempted, not any accepted PGS iterate.
    vfree = analytic.stage50.contact_model.finite(vfree)
    mobility = analytic.stage50.contact_model.finite(mobility)
    A = jacobian @ mobility @ jacobian.T
    z = jacobian @ vfree
    force = np.zeros(len(z))
    scale = max(np.linalg.norm(vfree), 1e-15)
    steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max()
                      for k in range(len(gaps))])
    ceiling = min(PREFIX_ITERATIONS, int(maxiter))
    for iteration in range(ceiling):
        for k in range(len(gaps)):
            i = 3*k
            vn = z[i] + A[i] @ force + gaps[k]/dt
            force[i] = max(0., force[i]-vn/A[i, i])
            vt = z[i+1:i+3] + A[i+1:i+3] @ force
            force[i+1:i+3] = analytic.stage50._project(
                force[i+1:i+3], vt, steps[k], friction*force[i])
        if analytic.stage50._residual(force, z, A, gaps, dt, friction, steps)/scale <= tol:
            answer = analytic.stage50._finish(
                vfree, mobility, jacobian, force, z, A, gaps, dt, friction, steps,
                iteration+1, "standard_cold_pgs", {})
            _stats["prefix_passes"] += 1
            _stats["prefix_iterations"] += iteration+1
            return answer
    _stats["prefix_iterations"] += ceiling
    try:
        velocity, health = analytic.solve_analytic_prepared(
            vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter)
    except (RuntimeError, FloatingPointError):
        _stats["analytic_rejections"] += 1
    else:
        health["iterations"] += ceiling
        health["initial_pgs_prefix_iterations"] = ceiling
        health["solver"] = "optional_pgs_prefix_then_" + health["solver"]
        _stats["analytic_passes"] += 1
        return velocity, health
    _stats["authoritative_fallbacks"] += 1
    velocity, health = analytic.stage53._solve(
        vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter)
    health["iterations"] += ceiling
    health["initial_pgs_prefix_iterations"] = ceiling
    return velocity, health


_solve_prepared = solve_prepared
