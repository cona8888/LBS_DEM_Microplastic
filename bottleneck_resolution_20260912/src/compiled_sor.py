"""Compiled cold projected contact sweeps, with unchanged Stage50 gates.

Only the float64 sweep loop is compiled. Matrix assembly and eigenvalue scales
use the original NumPy operations; final acceptance always uses Stage50._finish.
No fast-math, parallel reductions, force warm start, tolerance relaxation, or
changes to the Coulomb projection are enabled. Scalar dot-product accumulation
may round differently from NumPy/BLAS; numerical equivalence must be measured.
"""
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "bottleneck_resolution_20260912/deps"),
               str(ROOT / "stage50_staging"), str(ROOT / "stage63_staging")]
import numpy as np
from numba import njit
import inertial_contact_seeded_lm_v1 as s50

RELAXATION = 1.7
_stats = {"calls": 0, "successes": 0, "failures": 0, "iterations": 0,
          "loop_seconds": 0.0, "finish_seconds": 0.0}


def stats():
    return dict(_stats)


@njit(cache=True, fastmath=False, parallel=False)
def _row_dot(A, row, force):
    value = 0.0
    for j in range(len(force)):
        value += A[row, j] * force[j]
    return value


@njit(cache=True, fastmath=False, parallel=False)
def _norm2(x, y):
    return np.sqrt(x*x + y*y)


@njit(cache=True, fastmath=False, parallel=False)
def cold_loop(A, z, gaps, dt, mu, steps, scale, tol, maxiter, omega=1.7):
    """Return (cold force, sweeps performed, residual convergence flag).

    omega=1.0 selects original PGS assignment structure. Other omega values use
    the Stage63 projected-SOR update including its second tangent projection.
    This internal convergence flag NEVER replaces original Python final gates.
    """
    force = np.zeros(len(z), dtype=np.float64)
    for iteration in range(maxiter):
        for k in range(len(gaps)):
            i = 3*k
            old = force[i]
            vn = z[i] + _row_dot(A, i, force) + gaps[k]/dt
            candidate = max(0.0, old-vn/A[i, i])
            if omega == 1.0:
                force[i] = candidate
            else:
                force[i] = max(0.0, old+omega*(candidate-old))
            old_x = force[i+1]
            old_y = force[i+2]
            vx = z[i+1] + _row_dot(A, i+1, force)
            vy = z[i+2] + _row_dot(A, i+2, force)
            tx = old_x-vx/steps[k]
            ty = old_y-vy/steps[k]
            limit = mu*force[i]
            factor = min(1.0, limit/max(_norm2(tx, ty), 1e-300))
            candidate_x = tx*factor
            candidate_y = ty*factor
            if omega == 1.0:
                force[i+1] = candidate_x
                force[i+2] = candidate_y
            else:
                tx = old_x+omega*(candidate_x-old_x)
                ty = old_y+omega*(candidate_y-old_y)
                factor = min(1.0, limit/max(_norm2(tx, ty), 1e-300))
                force[i+1] = tx*factor
                force[i+2] = ty*factor
        value = 0.0
        for k in range(len(gaps)):
            i = 3*k
            vn = z[i]+_row_dot(A, i, force)+gaps[k]/dt
            value = max(value, abs(min(A[i, i]*force[i], vn)))
            vx = z[i+1]+_row_dot(A, i+1, force)
            vy = z[i+2]+_row_dot(A, i+2, force)
            tx = force[i+1]-vx/steps[k]
            ty = force[i+2]-vy/steps[k]
            factor = min(1.0, mu*force[i]/max(_norm2(tx, ty), 1e-300))
            residual_x = force[i+1]-tx*factor
            residual_y = force[i+2]-ty*factor
            value = max(value, _norm2(residual_x, residual_y)*steps[k])
        if value/scale <= tol:
            return force, iteration+1, True
    return force, maxiter, False


def _failure(message, iterations, diagnostics):
    error = RuntimeError(message)
    error.iterations = int(iterations)
    error.contact_diagnostics = dict(diagnostics)
    return error


def solve_prepared(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
    """Stage63 projected SOR interface; unchanged physical acceptance gates."""
    _stats["calls"] += 1
    vfree = s50.contact_model.finite(vfree)
    mobility = s50.contact_model.finite(mobility)
    if not len(gaps):
        _stats["successes"] += 1
        return vfree, {"iterations": 0, "residual": 0., "force_residual": 0.,
                       "dissipation": 0., "reactions": [], "solver": "compiled_projected_sor"}
    A = jacobian @ mobility @ jacobian.T
    z = jacobian @ vfree
    scale = max(np.linalg.norm(vfree), 1e-15)
    steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max()
                      for k in range(len(gaps))])
    if (not all(np.isfinite(x).all() for x in (A, z, gaps, steps)) or
            np.any(np.diag(A)[::3] <= 0) or np.any(steps <= 0) or
            not np.isfinite([dt, friction, tol]).all() or dt <= 0 or friction < 0 or
            tol <= 0 or maxiter < 0):
        _stats["failures"] += 1
        raise _failure("invalid compiled contact inputs", 0, {"phase": "preparation"})
    begin = time.perf_counter()
    force, sweeps, converged = cold_loop(
        np.ascontiguousarray(A, dtype=np.float64), np.ascontiguousarray(z, dtype=np.float64),
        np.ascontiguousarray(gaps, dtype=np.float64), float(dt), float(friction),
        np.ascontiguousarray(steps, dtype=np.float64), float(scale), float(tol),
        int(maxiter), RELAXATION)
    elapsed = time.perf_counter()-begin
    _stats["loop_seconds"] += elapsed
    _stats["iterations"] += sweeps
    diagnostics = {"solver": "compiled_projected_sor", "iterations": int(sweeps),
                   "loop_seconds": elapsed, "compiled_converged": bool(converged)}
    if not converged or not np.isfinite(force).all():
        _stats["failures"] += 1
        raise _failure("direct contact residual nonconvergence", sweeps, diagnostics)
    begin = time.perf_counter()
    try:
        answer = s50._finish(vfree, mobility, jacobian, force, z, A, gaps, dt,
                            friction, steps, int(sweeps), "compiled_projected_sor",
                            {"relaxation": RELAXATION})
        if not all(np.isfinite(answer[1][key]) for key in
                   ("residual", "force_residual", "dissipation")):
            raise RuntimeError("nonfinite compiled contact health")
    except RuntimeError as exc:
        _stats["failures"] += 1
        diagnostics["phase"] = "original_finish_gate"
        raise _failure(str(exc), sweeps, diagnostics) from exc
    finally:
        _stats["finish_seconds"] += time.perf_counter()-begin
    _stats["successes"] += 1
    return answer


_solve_prepared = solve_prepared
_solve = solve_prepared


def warmup():
    """Compile/load float64 specialization separately from warmed timings."""
    begin = time.perf_counter()
    cold_loop(np.eye(3), np.array([-1., .2, -.1]), np.zeros(1), .01, .3,
              np.ones(1), 1., 1e-10, 25000, 1.7)
    return time.perf_counter()-begin
