"""Fail-closed cold-start Coulomb solve with a larger declared iteration ceiling.

No reaction is persisted across time steps or finite-Re outer iterations.  This
preserves the instantaneous maximum-dissipation law's solution selection after
real-matrix tests rejected cached frictional reactions.
"""
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage39_staging"))
import inertial_contact_v3 as previous

base = previous.base
generalized_mass_matrix = previous.generalized_mass_matrix
stokes_generalized_resistance = previous.stokes_generalized_resistance
contact_model = previous.contact_model
finite_re = previous.finite_re


def _reaction_world(contacts, reactions):
    reactions = np.asarray(reactions, float)
    world = {}
    for index, contact in enumerate(contacts):
        frame = contact_model.contact_frame(contact[2])
        world[str(int(contact[0]))] = (frame.T @ reactions[3*index:3*index+3]).tolist()
    return world


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
        updated, contact_health = contact_model.contact_solve(
            free_velocity, compliance, contacts, ell, dt, friction,
            tol=1e-10, maxiter=10000,
        )
        total_contact_iterations += contact_health["iterations"]
        if np.linalg.norm(updated - candidate) / velocity_scale <= tolerance:
            candidate = updated
            break
        candidate = updated
    else:
        raise RuntimeError("inertial/contact fixed point did not converge")
    jacobian = base._contact_jacobian(contacts, ell)
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
    world = _reaction_world(contacts, reaction)
    return candidate, {"iterations": iteration + 1, "reynolds": reynolds,
                       "finite_re_multiplier": multiplier, "momentum_residual": momentum_residual,
                       "momentum_reference_load": float(denominator), "contact": contact_health,
                       "total_contact_iterations": total_contact_iterations,
                       "reaction_world_by_grain": world,
                       "load_bearing_grain_ids": [int(contacts[k][0]) for k in range(len(contacts))
                                                   if reaction[3*k] > 0],
                       "cache_policy": "discard_between_all_solves",
                       "minimum_system_eigenvalue": float(np.linalg.eigvalsh((system + system.T) / 2).min())}
