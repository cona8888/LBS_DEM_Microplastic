"""Stage147: the dt-consistent contact acceptance contract, applied to the trajectory.

Injection point is `inertial_contact_runtime_portfolio_v1._solve`, the same hook
Stage138 used, so the surrounding integrator, geometry, drag and lubrication are
untouched.

Why the injection point is the portfolio and not Stage41
--------------------------------------------------------
`portfolio.inertial_contact_step` rebinds `stage41._solve_prepared = portfolio._solve`
on every call.  A patch applied to `stage41._solve_prepared` is therefore overwritten
before it is ever used, and is silently inert.  The Stage147 harness makes that
mistake impossible by patching the portfolio entry point instead.

TWO places carry the ceiling, not one
-------------------------------------
Stage145 made the *solver's* acceptance ceiling dt-consistent.  That alone is not
enough: `checkpoint_core_v3` independently rejects a step whose
``health["contact"]["residual"]`` exceeds 1e-8, and that field is the legacy ratio
``residual / |vfree|``.  Left as it is, the trajectory gate re-imposes the
dt-inconsistent contract one level up and the run dies with
``numerical_failure: contact or force closure failed``.  Measured, not argued: see
experiment G4 of `run_stage147_v1`.

The dt-consistent form of that same gate divides the residual by the scale the
ceiling actually used,

    scale_eff = max(|vfree|, delta_geom / (dt * contact_relative))
    reported  = residual / scale_eff

which reduces to ``residual / |vfree|`` *bitwise* when ``delta_geom = 0``, because
``max(scale, 0.0) is scale``.  Both numbers are kept in the health record, so the
legacy metric remains visible and nothing in the existing evidence chain becomes
unfalsifiable.

The ladder
----------
  1. projected Gauss-Seidel with the dt-consistent ceiling (Stage145).  It projects
     f_n onto the non-negative orthant every sweep, so it cannot return a negative
     normal force.
  2. semismooth Newton on the Alart-Curnier natural map, minimum-norm step
     (the generalized Jacobian is rank deficient on a hyperstatic support).
  3. complete open/stick/slide enumeration for n <= 3 with a DECLARED selection
     rule among admissible branches.

Rungs 2 and 3 are a declared safety net and a branch diagnostic.  On every one of
the 27 contact systems the production stack rejected at the stalled sphere endpoint,
rung 1 alone succeeded, so rungs 2 and 3 were never exercised there; `STATS` records
that rather than assuming it.  `ladder=False` builds the minimal patch -- rung 1 only
-- which is what this stage recommends for production.

Every rung is judged by the unchanged physical gates: non-negative normals, the
Coulomb cone, force closure and non-generation of energy.  Only the residual
threshold changes, and only in the declared dt-consistent way.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage145_staging"), str(ROOT / "stage147_staging")]
import geometric_tolerance_v1 as contract_module
import branch_enumeration_v1 as enumeration

STATS = {"calls": 0, "pgs": 0, "newton": 0, "enumeration": 0, "failures": 0,
         "branch_counts": [], "opened_contacts": 0, "selection_rules": {},
         "max_reported_residual": 0.0, "max_legacy_residual": 0.0,
         "max_residual_over_ceiling": 0.0, "pgs_iterations": 0}


def reset_stats():
    STATS.update({"calls": 0, "pgs": 0, "newton": 0, "enumeration": 0, "failures": 0,
                  "branch_counts": [], "opened_contacts": 0, "selection_rules": {},
                  "max_reported_residual": 0.0, "max_legacy_residual": 0.0,
                  "max_residual_over_ceiling": 0.0, "pgs_iterations": 0})


def effective_scale(vfree, dt, delta_geom, contact_relative):
    """The velocity scale the dt-consistent ceiling corresponds to.

    Identically ``max(|vfree|, 1e-15)`` when ``delta_geom == 0.0``.
    """
    scale = max(float(np.linalg.norm(vfree)), 1e-15)
    if delta_geom <= 0.0:
        return scale
    return max(scale, float(delta_geom) / (float(dt) * float(contact_relative)))


def trajectory_residual(health, vfree, dt, delta_geom, contact_relative):
    """Rewrite ``health['residual']`` for the trajectory gate; keep the legacy number."""
    if "residual_velocity_units" not in health:
        return health
    health["legacy_residual_over_vfree"] = health["residual"]
    health["residual"] = float(health["residual_velocity_units"]
                               / effective_scale(vfree, dt, delta_geom, contact_relative))
    return health


# ------------------------------------------------------------------ gates (unchanged physics)
def _gates(vfree, mobility, jacobian, gaps, dt, friction, force, delta_geom, tol):
    """The unchanged Stage50 gates with the dt-consistent ceiling.  Returns (ok, health|reason)."""
    n = len(gaps)
    A = jacobian @ mobility @ jacobian.T
    z = jacobian @ vfree
    scale = max(float(np.linalg.norm(vfree)), 1e-15)
    ceiling = max(tol * scale, float(delta_geom) / dt)
    steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max() for k in range(n)])
    velocity_contact = z + A @ force
    residual = 0.0
    for k in range(n):
        i = 3*k
        residual = max(residual, abs(min(A[i, i]*force[i], velocity_contact[i] + gaps[k]/dt)))
        t = force[i+1:i+3] - velocity_contact[i+1:i+3]/steps[k]
        tn = np.linalg.norm(t)
        projection = t * min(1.0, friction*force[i]/max(tn, 1e-300))
        residual = max(residual, np.linalg.norm(force[i+1:i+3] - projection)*steps[k])
    if np.any(force[::3] < 0):
        return False, "negative normal force"
    for k in range(n):
        if np.linalg.norm(force[3*k+1:3*k+3]) > friction*force[3*k] + 1e-12*max(np.linalg.norm(force), 1e-30):
            return False, "cone violation"
    if residual > ceiling:
        return False, "residual above ceiling"
    velocity = vfree + mobility @ jacobian.T @ force
    closure = float(np.linalg.norm(np.linalg.solve(mobility, velocity - vfree) - jacobian.T @ force)
                    / max(np.linalg.norm(jacobian.T @ force), 1e-30))
    if closure > 1e-8:
        return False, "force closure failed"
    work = sum(float(force[3*k+1:3*k+3] @ velocity_contact[3*k+1:3*k+3]) for k in range(n))
    tangential = sum(float(np.linalg.norm(force[3*k+1:3*k+3])) for k in range(n))
    if work > 1e-8*max(np.linalg.norm(force)*scale, 1e-30) + tangential*ceiling:
        return False, "friction generates energy"
    return True, {"iterations": 0, "residual": float(residual/scale),
                  "force_residual": closure, "dissipation": float(-work),
                  "reactions": force.tolist(), "residual_velocity_units": float(residual),
                  "velocity_ceiling": float(ceiling),
                  "legacy_gate_pass": bool(residual/scale <= tol), "velocity": velocity}


# ------------------------------------------------------------------ rung 2
def _alart_curnier(A, z, gaps, dt, friction, steps, force):
    n = len(gaps)
    v = z + A @ force
    phi = np.zeros(3*n)
    jac = np.zeros((3*n, 3*n))
    for k in range(n):
        i = 3*k
        rn, rt = 1.0/A[i, i], 1.0/steps[k]
        wn = v[i] + gaps[k]/dt
        active = force[i] - rn*wn > 0.0
        if active:
            phi[i] = rn*wn
            jac[i, :] = rn*A[i, :]
        else:
            phi[i] = force[i]
            jac[i, i] = 1.0
        ft = force[i+1:i+3]
        y = ft - rt*v[i+1:i+3]
        r = friction*max(force[i], 0.0)
        ny = float(np.linalg.norm(y))
        if not active or ny <= r:
            if ny <= r and active:
                phi[i+1:i+3] = rt*v[i+1:i+3]
                jac[i+1:i+3, :] = rt*A[i+1:i+3, :]
            else:
                phi[i+1:i+3] = ft
                jac[i+1, i+1] = jac[i+2, i+2] = 1.0
        else:
            yhat = y/ny
            phi[i+1:i+3] = ft - r*yhat
            dy = np.zeros((2, 3*n))
            dy[0, i+1] = dy[1, i+2] = 1.0
            dy -= rt*A[i+1:i+3, :]
            P = (np.eye(2) - np.outer(yhat, yhat))/ny
            block = np.zeros((2, 3*n))
            block[0, i+1] = block[1, i+2] = 1.0
            block -= r*(P @ dy)
            if force[i] > 0.0:
                block[:, i] -= friction*yhat
            jac[i+1:i+3, :] = block
    return phi, jac


def _newton(vfree, mobility, jacobian, gaps, dt, friction, seed, maxiter=60):
    n = len(gaps)
    A = jacobian @ mobility @ jacobian.T
    z = jacobian @ vfree
    steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max() for k in range(n)])
    weight = np.repeat(steps, 3)
    weight[::3] = np.diag(A)[::3]
    force = np.array(seed, float)
    for _ in range(maxiter):
        phi, jac = _alart_curnier(A, z, gaps, dt, friction, steps, force)
        merit = float(np.linalg.norm(weight*phi))
        if merit == 0.0:
            break
        step = np.linalg.lstsq(jac, -phi, rcond=1e-13)[0]
        if not np.isfinite(step).all():
            break
        alpha, moved = 1.0, False
        for _ls in range(30):
            trial = force + alpha*step
            trial[::3] = np.maximum(trial[::3], 0.0)
            phi_t, _ = _alart_curnier(A, z, gaps, dt, friction, steps, trial)
            if float(np.linalg.norm(weight*phi_t)) <= (1.0 - 1e-4*alpha)*merit:
                force, moved = trial, True
                break
            alpha *= 0.5
        if not moved:
            break
    for k in range(n):                      # always hand back a cone-feasible point
        i = 3*k
        force[i] = max(force[i], 0.0)
        nt = np.linalg.norm(force[i+1:i+3])
        limit = friction*force[i]
        if nt > limit:
            force[i+1:i+3] *= 0.0 if limit <= 0 else limit/nt
    return force


# ------------------------------------------------------------------ the drop-in
def make_solver(delta_geom, ladder=False, max_enumeration_contacts=3, contact_relative=1e-10):
    """Build `_solve(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter)`.

    `ladder=False` is the minimal production patch: rung 1 plus the consistent
    trajectory-gate reporting.  `ladder=True` adds rungs 2 and 3.
    """

    def solve(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
        vfree = np.asarray(vfree, float)
        mobility = np.asarray(mobility, float)
        gaps = np.asarray(gaps, float)
        STATS["calls"] += 1
        if not len(gaps):
            return vfree, {"iterations": 0, "residual": 0.0, "force_residual": 0.0,
                           "dissipation": 0.0, "reactions": [], "solver": "free"}
        jacobian = np.asarray(jacobian, float)
        rejections = []

        # rung 1: projected Gauss-Seidel with the dt-consistent ceiling
        try:
            velocity, health = contract_module.solve_prepared(
                vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter, delta_geom=delta_geom)
        except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
            rejections.append({"rung": "pgs", "reason": str(exc)})
        else:
            STATS["pgs"] += 1
            STATS["pgs_iterations"] += int(health["iterations"])
            trajectory_residual(health, vfree, dt, delta_geom, tol)
            health["solver"] = "stage147_pgs_contract"
            STATS["max_reported_residual"] = max(STATS["max_reported_residual"], health["residual"])
            STATS["max_legacy_residual"] = max(STATS["max_legacy_residual"],
                                               health["legacy_residual_over_vfree"])
            STATS["max_residual_over_ceiling"] = max(
                STATS["max_residual_over_ceiling"],
                health["residual_velocity_units"] / max(health["velocity_ceiling"], 1e-300))
            return velocity, health

        if not ladder:
            STATS["failures"] += 1
            raise RuntimeError("direct contact residual nonconvergence")

        # rung 2: semismooth Newton
        try:
            force = _newton(vfree, mobility, jacobian, gaps, dt, friction, np.zeros(3*len(gaps)))
            ok, health = _gates(vfree, mobility, jacobian, gaps, dt, friction, force, delta_geom, tol)
            if ok:
                STATS["newton"] += 1
                velocity = health.pop("velocity")
                trajectory_residual(health, vfree, dt, delta_geom, tol)
                health.update(solver="stage147_semismooth_newton", rejections=rejections)
                return velocity, health
            rejections.append({"rung": "newton", "reason": health})
        except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
            rejections.append({"rung": "newton", "reason": str(exc)})

        # rung 3: complete enumeration with a declared selection rule
        if len(gaps) <= max_enumeration_contacts:
            system = {"vfree": vfree, "mobility": mobility, "jacobian": jacobian,
                      "gaps": gaps, "dt": dt, "mu": friction}
            try:
                found, P = enumeration.enumerate_branches(system, delta_geom,
                                                          contact_relative=contact_relative)
            except (RuntimeError, ValueError, np.linalg.LinAlgError) as exc:
                found, P = [], None
                rejections.append({"rung": "enumeration", "reason": str(exc)})
            if found:
                STATS["branch_counts"].append(len(found))
                chosen, rule = enumeration.select_branch(found, P)
                STATS["selection_rules"][rule] = STATS["selection_rules"].get(rule, 0) + 1
                opened = sum(1 for m in chosen["mode"] if m == enumeration.OPEN)
                STATS["opened_contacts"] += opened
                ok, health = _gates(vfree, mobility, jacobian, gaps, dt, friction,
                                    np.asarray(chosen["force"], float), delta_geom, tol)
                if ok:
                    STATS["enumeration"] += 1
                    velocity = health.pop("velocity")
                    trajectory_residual(health, vfree, dt, delta_geom, tol)
                    health.update(solver="stage147_enumeration", rejections=rejections,
                                  branches=len(found), chosen_mode=chosen["mode_name"],
                                  selection_rule=rule, opened_contacts=opened,
                                  force_family_dimension=chosen["force_family_dimension"],
                                  branch_spread=enumeration.branch_spread(found))
                    return velocity, health
                rejections.append({"rung": "enumeration_gates", "reason": health})

        STATS["failures"] += 1
        raise RuntimeError("direct contact residual nonconvergence")

    return solve
