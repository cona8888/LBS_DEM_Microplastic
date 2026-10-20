"""Cold Coulomb solves with invariant algebra hoisted out of inner loops.

The projected Gauss-Seidel order, zero reaction initialization, force updates,
residual calculation, tolerances, and iteration ceilings match Stage40 cold v1.
Only geometry at a frozen pose and tangential Lipschitz constants for a fixed
Delassus matrix are reused. No force, mobility, or Delassus matrix survives a
solve. In particular, finite-Re updates always rebuild A = J M J.T.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage40_staging"))
import inertial_contact_cold_v1 as previous

base = previous.base
generalized_mass_matrix = previous.generalized_mass_matrix
stokes_generalized_resistance = previous.stokes_generalized_resistance
contact_model = previous.contact_model
finite_re = previous.finite_re


def _prepare_geometry(contacts, ell):
    """Create per-call geometry; caller must not reuse after any pose change."""
    rows, gaps, frames = [], [], []
    for _, gap, normal, lever in contacts:
        frame = contact_model.contact_frame(normal)
        rows.extend(np.c_[frame, np.cross(lever, frame) / ell])
        gaps.append(gap)
        frames.append(frame)
    return np.asarray(rows, float).reshape(-1, 6), np.asarray(gaps), frames


def _solve_prepared(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
    vfree = contact_model.finite(vfree)
    mobility = contact_model.finite(mobility)
    if not len(gaps):
        return vfree, {"iterations": 0, "residual": 0., "force_residual": 0.,
                       "dissipation": 0., "reactions": []}
    # A changes with finite-Re compliance, so it is deliberately rebuilt here.
    A = jacobian @ mobility @ jacobian.T
    z = jacobian @ vfree
    force = np.zeros(len(z))
    scale = max(np.linalg.norm(vfree), 1e-15)
    # The identical eigensolve used by Stage37; evaluated once instead of twice
    # per block per iteration. No analytic eigenvalue formula or fast-math.
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
        if residual / scale <= tol:
            break
    else:
        raise RuntimeError("contact nonconvergence")
    velocity = vfree + mobility @ jacobian.T @ force
    force_residual = np.linalg.norm(np.linalg.solve(mobility, velocity-vfree) - jacobian.T @ force) / max(np.linalg.norm(jacobian.T @ force), 1e-30)
    tangential_work = sum(float(force[3*k+1:3*k+3] @ vel[3*k+1:3*k+3]) for k in range(len(gaps)))
    if tangential_work > 1e-8 * max(np.linalg.norm(force) * scale, 1e-30):
        raise RuntimeError("friction generates energy")
    return contact_model.finite(velocity), {
        "iterations": iteration+1, "residual": residual/scale,
        "force_residual": float(force_residual), "dissipation": -tangential_work,
        "reactions": force.tolist(),
    }


def contact_solve(vfree, mobility, contacts, ell, dt, friction, tol=1e-9, maxiter=2000):
    """Stage37-compatible entry point for independent primitive comparisons."""
    if dt <= 0 or ell <= 0 or friction < 0:
        raise ValueError("invalid contact parameter")
    jacobian, gaps, _ = _prepare_geometry(contacts, ell)
    return _solve_prepared(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter)


def inertial_contact_step(old_velocity, fluid_background_velocity, body_load,
                          stokes_resistance, lubrication_resistance, mass_matrix,
                          contacts, ell, dt, friction, fluid_density, viscosity,
                          equivalent_diameter, sphericity, world_reactions=None,
                          tolerance=1e-10, max_iterations=80):
    old_velocity = np.asarray(old_velocity, float)
    background = np.asarray(fluid_background_velocity, float)
    body_load = np.asarray(body_load, float)
    stokes = np.asarray(stokes_resistance, float)
    lubrication = np.asarray(lubrication_resistance, float)
    mass = np.asarray(mass_matrix, float)
    if dt <= 0 or ell <= 0 or friction < 0:
        raise ValueError("invalid contact parameter")
    # These arrays are scoped to this frozen-pose call, including rejected steps.
    jacobian, gaps, frames = _prepare_geometry(contacts, ell)
    candidate = old_velocity.copy()
    velocity_scale = max(np.linalg.norm(old_velocity), np.linalg.norm(background), 1e-30)
    total_contact_iterations = 0
    for iteration in range(max_iterations):
        reynolds = finite_re.reynolds_number(candidate[:3] - background[:3], fluid_density, viscosity, equivalent_diameter)
        multiplier = finite_re.inertial_multiplier(reynolds, sphericity)
        drag = stokes.copy()
        drag[:3, :3] *= multiplier
        system = mass / dt + drag + lubrication
        compliance = np.linalg.inv(system)
        free_velocity = compliance @ (mass @ old_velocity / dt + drag @ background + body_load)
        updated, contact_health = _solve_prepared(
            free_velocity, compliance, jacobian, gaps, dt, friction,
            tol=1e-10, maxiter=10000,
        )
        total_contact_iterations += contact_health["iterations"]
        if np.linalg.norm(updated - candidate) / velocity_scale <= tolerance:
            candidate = updated
            break
        candidate = updated
    else:
        raise RuntimeError("inertial/contact fixed point did not converge")
    reaction = np.asarray(contact_health["reactions"], float)
    reaction_load = jacobian.T @ reaction if len(reaction) else np.zeros(6)
    acceleration_load = mass @ (candidate - old_velocity) / dt
    slip_drag = drag @ (candidate - background)
    lubrication_load = lubrication @ candidate
    residual = acceleration_load + slip_drag + lubrication_load - body_load - reaction_load
    denominator = max(np.linalg.norm(acceleration_load), np.linalg.norm(slip_drag),
                      np.linalg.norm(lubrication_load), np.linalg.norm(body_load),
                      np.linalg.norm(reaction_load), np.linalg.norm(drag @ background), 1e-30)
    momentum_residual = float(np.linalg.norm(residual) / denominator)
    if momentum_residual > 1e-8 or not np.isfinite(candidate).all():
        raise RuntimeError("inertial momentum closure failed")
    world = {str(int(contact[0])): (frames[k].T @ reaction[3*k:3*k+3]).tolist()
             for k, contact in enumerate(contacts)}
    return candidate, {"iterations": iteration + 1, "reynolds": reynolds,
                       "finite_re_multiplier": multiplier, "momentum_residual": momentum_residual,
                       "momentum_reference_load": float(denominator), "contact": contact_health,
                       "total_contact_iterations": total_contact_iterations,
                       "reaction_world_by_grain": world,
                       "load_bearing_grain_ids": [int(contacts[k][0]) for k in range(len(contacts))
                                                   if reaction[3*k] > 0],
                       "cache_policy": "discard_between_all_solves",
                       "minimum_system_eigenvalue": float(np.linalg.eigvalsh((system + system.T) / 2).min())}
