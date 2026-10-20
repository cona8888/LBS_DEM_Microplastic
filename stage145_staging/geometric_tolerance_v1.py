"""Stage145: dt-consistent velocity-level tolerance, as an additive contract.

Stage50/Stage41 accept a contact solution when ``residual/|vfree| <= 1e-10``.
That ceiling does not depend on ``dt``, while the velocity-level Signorini term
``g/dt`` does.  A gap is only known to a geometric uncertainty ``delta_geom``
(the rounding error of the closest-point evaluation), so the smallest velocity
the geometry can resolve over one step is ``delta_geom/dt``: a residual below
that is unresolvable by construction, and a ceiling below it is unattainable
for small enough ``dt``.  The contract here is

    ceiling = max(contact_relative * |vfree|,  delta_geom / dt)
    delta_geom = kappa * eps * length_scale

with ``kappa`` DECLARED, not fitted.  The Stage142 Decimal diagnostic measured
the actual gap rounding error at ``4.17e-19 m = 0.40 * eps * L``; kappa = 16 is
a ~40x margin and 8/16/64 are carried as a sensitivity.

RAW GAPS ARE NEVER MODIFIED.  The equations are solved with the gaps as
computed; only the acceptance threshold changes, and both the old and the new
metric are reported so nothing in the existing evidence chain becomes
unfalsifiable.

``solve_prepared`` is Stage41 ``_solve_prepared`` with exactly three edits:
  1. the convergence test uses ``ceiling`` instead of ``tol * scale``;
  2. the energy gate carries the same allowance (otherwise it silently
     re-imposes the old contract at small dt -- see the tripod test);
  3. an optional ``force0`` warm start (Stage145 uses it only to study the
     Stage40 rejection; it is None everywhere else).
With ``delta_geom = 0.0`` and ``force0 = None`` the two must agree bitwise, and
``run_stage145_v1`` proves that on every frozen and random system before any
other result is reported.  That inertness proof is the precondition for
landing this patch in the production chain.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage38_staging"), str(ROOT / "stage39_staging"),
                str(ROOT / "stage41_staging")]
import inertial_contact_cold_optimized_v1 as stage41

contact_model = stage41.contact_model
EPS = float(np.finfo(float).eps)
DECLARED_MULTIPLIERS = (8.0, 16.0, 64.0)
DEFAULT_MULTIPLIER = 16.0


def length_budget(length_scale, multiplier=DEFAULT_MULTIPLIER):
    """delta_geom = kappa * eps * length_scale, with the declared multipliers only."""
    if not np.isfinite(length_scale) or length_scale <= 0:
        raise ValueError("positive finite length scale required")
    if multiplier not in DECLARED_MULTIPLIERS:
        raise ValueError("undeclared geometric multiplier")
    return float(multiplier) * EPS * float(length_scale)


def geometric_length_scale(cell_length, position=None, body_extent=0.0):
    """Magnitude of the operands entering a gap evaluation.

    The gap is ``|x + lever - c| - r``; its absolute rounding error scales with
    the largest coordinate magnitude that is subtracted, not with the cell
    length alone.  GrainGeometry works in unwrapped transport coordinates, so a
    particle that has crossed several cells carries a proportionally larger
    error than kappa*eps*L.  Wrapping x into the primary cell with an integer
    cell offset would keep this at L forever.
    """
    scale = float(cell_length)
    if position is not None:
        scale = max(scale, float(np.max(np.abs(position))))
    return max(scale, float(body_extent))


def velocity_ceiling(vfree, dt, delta_geom, contact_relative=1e-10):
    scale = max(float(np.linalg.norm(vfree)), 1e-15)
    return max(contact_relative * scale, float(delta_geom) / float(dt))


def solve_prepared(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter,
                   delta_geom=0.0, force0=None):
    """Stage41 ``_solve_prepared`` with the dt-consistent ceiling.

    delta_geom = 0.0 and force0 = None reproduce Stage41 bitwise (proven, not asserted).
    """
    vfree = contact_model.finite(vfree)
    mobility = contact_model.finite(mobility)
    if not len(gaps):
        return vfree, {"iterations": 0, "residual": 0., "force_residual": 0.,
                       "dissipation": 0., "reactions": []}
    A = jacobian @ mobility @ jacobian.T
    z = jacobian @ vfree
    force = np.zeros(len(z)) if force0 is None else np.array(force0, float)
    scale = max(np.linalg.norm(vfree), 1e-15)
    ceiling = max(tol * scale, delta_geom / dt)                     # EDIT 1
    steps = [np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max()
             for k in range(len(gaps))]
    for iteration in range(maxiter):
        for k in range(len(gaps)):
            i = 3*k
            vn = z[i] + A[i] @ force + gaps[k] / dt
            force[i] = max(0., force[i] - vn / A[i, i])
            vt = z[i+1:i+3] + A[i+1:i+3] @ force
            step = steps[k]
            t = force[i+1:i+3] - vt / step
            limit = friction * force[i]
            tn = np.linalg.norm(t)
            force[i+1:i+3] = t * min(1., limit / max(tn, 1e-300))
        vel = z + A @ force
        residual = 0.
        for k in range(len(gaps)):
            i = 3*k
            normal = vel[i] + gaps[k] / dt
            residual = max(residual, abs(min(A[i, i] * force[i], normal)))
            step = steps[k]
            t = force[i+1:i+3] - vel[i+1:i+3] / step
            limit = friction * force[i]
            tn = np.linalg.norm(t)
            projection = t * min(1., limit / max(tn, 1e-300))
            residual = max(residual, np.linalg.norm(force[i+1:i+3] - projection) * step)
        if residual <= ceiling:                                      # EDIT 1
            break
    else:
        raise RuntimeError("contact nonconvergence")
    velocity = vfree + mobility @ jacobian.T @ force
    force_residual = np.linalg.norm(np.linalg.solve(mobility, velocity-vfree) - jacobian.T @ force) / max(np.linalg.norm(jacobian.T @ force), 1e-30)
    tangential_work = sum(float(force[3*k+1:3*k+3] @ vel[3*k+1:3*k+3]) for k in range(len(gaps)))
    # EDIT 2: a tangential velocity below the ceiling is unresolvable, so the
    # reaction may do spurious work of at most |f_t| * ceiling through it.
    tangential_norm = sum(float(np.linalg.norm(force[3*k+1:3*k+3])) for k in range(len(gaps)))
    work_ceiling = 1e-8 * max(np.linalg.norm(force) * scale, 1e-30) + tangential_norm * ceiling
    if tangential_work > work_ceiling:
        raise RuntimeError("friction generates energy")
    return contact_model.finite(velocity), {
        "iterations": iteration+1, "residual": residual/scale,
        "force_residual": float(force_residual), "dissipation": -tangential_work,
        "reactions": force.tolist(),
        # additive reporting; the Stage50 metric above is unchanged
        "residual_velocity_units": float(residual),
        "velocity_ceiling": float(ceiling),
        "residual_over_geometric": float(residual * dt / delta_geom) if delta_geom > 0 else float("inf"),
        "legacy_gate_pass": bool(residual / scale <= tol),
        "work_ceiling": float(work_ceiling),
        "delta_geom_m": float(delta_geom),
        "warm_started": force0 is not None,
    }


def independent_gates(vfree, mobility, jacobian, gaps, dt, friction, velocity, health,
                      delta_geom=0.0, contact_relative=1e-10):
    """Recheck every unchanged physical gate from the returned reaction alone.

    Deliberately does not call solve_prepared: a solver cannot certify itself.
    """
    f = np.asarray(health["reactions"], float)
    n = len(gaps)
    A = jacobian @ mobility @ jacobian.T
    z = jacobian @ vfree
    scale = max(float(np.linalg.norm(vfree)), 1e-15)
    ceiling = max(contact_relative * scale, delta_geom / dt)
    steps = [np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max() for k in range(n)]
    vel = z + A @ f
    residual = 0.0
    for k in range(n):
        i = 3*k
        residual = max(residual, abs(min(A[i, i]*f[i], vel[i] + gaps[k]/dt)))
        t = f[i+1:i+3] - vel[i+1:i+3]/steps[k]
        tn = np.linalg.norm(t)
        proj = t * min(1., friction*f[i]/max(tn, 1e-300))
        residual = max(residual, np.linalg.norm(f[i+1:i+3]-proj)*steps[k])
    nonnegative = bool(np.all(f[::3] >= 0.0))
    cone = all(np.linalg.norm(f[3*k+1:3*k+3]) <= friction*f[3*k] + 1e-12*max(np.linalg.norm(f), 1e-30)
               for k in range(n))
    reproduces = bool(np.linalg.norm((vfree + mobility @ jacobian.T @ f) - velocity) <= 1e-12*scale)
    closure = float(np.linalg.norm(np.linalg.solve(mobility, velocity-vfree) - jacobian.T @ f)
                    / max(np.linalg.norm(jacobian.T @ f), 1e-30))
    work = sum(float(f[3*k+1:3*k+3] @ vel[3*k+1:3*k+3]) for k in range(n))
    tangential_norm = sum(float(np.linalg.norm(f[3*k+1:3*k+3])) for k in range(n))
    work_ceiling = 1e-8*max(np.linalg.norm(f)*scale, 1e-30) + tangential_norm*ceiling
    checks = {"nonnegative_normal": nonnegative, "circular_cone": bool(cone),
              "residual_within_ceiling": bool(residual <= ceiling),
              "force_closure": bool(closure <= 1e-8),
              "no_energy_generation": bool(work <= work_ceiling),
              "velocity_reproduced_from_reaction": reproduces}
    return {"passed": all(checks.values()), "checks": checks,
            "residual_velocity_units": float(residual), "velocity_ceiling": float(ceiling),
            "residual_over_scale": float(residual/scale), "force_residual": closure,
            "legacy_gate_pass": bool(residual/scale <= contact_relative),
            "backward_error_m": float(np.max(np.abs(-dt*vel[::3] - np.asarray(gaps, float)))) if n else 0.0}
