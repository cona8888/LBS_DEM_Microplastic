"""Stage41-equivalent cold contact step with a robust PGS iteration ceiling.

Only the inner projected Gauss--Seidel ceiling changes (10,000 to 25,000).
The equations, cold zero-force initialization, ordering and residual tolerance
are inherited unchanged from the independently verified Stage41 solver.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage41_staging"))
import inertial_contact_cold_optimized_v1 as stage41

base = stage41.base
generalized_mass_matrix = stage41.generalized_mass_matrix
stokes_generalized_resistance = stage41.stokes_generalized_resistance
contact_model = stage41.contact_model
finite_re = stage41.finite_re
contact_solve = stage41.contact_solve
CONTACT_ITERATION_CEILING = 25000


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
    jacobian, gaps, frames = stage41._prepare_geometry(contacts, ell)
    candidate = old_velocity.copy()
    velocity_scale = max(np.linalg.norm(old_velocity), np.linalg.norm(background), 1e-30)
    total_contact_iterations = 0
    for iteration in range(max_iterations):
        reynolds = finite_re.reynolds_number(
            candidate[:3] - background[:3], fluid_density, viscosity, equivalent_diameter)
        multiplier = finite_re.inertial_multiplier(reynolds, sphericity)
        drag = stokes.copy()
        drag[:3, :3] *= multiplier
        system = mass / dt + drag + lubrication
        compliance = np.linalg.inv(system)
        free_velocity = compliance @ (mass @ old_velocity / dt + drag @ background + body_load)
        updated, contact_health = stage41._solve_prepared(
            free_velocity, compliance, jacobian, gaps, dt, friction,
            tol=1e-10, maxiter=CONTACT_ITERATION_CEILING)
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
                       "finite_re_multiplier": multiplier,
                       "momentum_residual": momentum_residual,
                       "momentum_reference_load": float(denominator),
                       "contact": contact_health,
                       "total_contact_iterations": total_contact_iterations,
                       "reaction_world_by_grain": world,
                       "load_bearing_grain_ids": [int(contacts[k][0]) for k in range(len(contacts))
                                                  if reaction[3*k] > 0],
                       "cache_policy": "discard_between_all_solves",
                       "minimum_system_eigenvalue": float(
                           np.linalg.eigvalsh((system + system.T) / 2).min()),
                       "contact_iteration_ceiling": CONTACT_ITERATION_CEILING}
