"""Cross-step warm start restricted to compressive normal reactions.

Tangential reactions are deliberately reset between steps because the rigid,
instantaneous Coulomb law has no elastic tangential state.  Persisting a full
tangential vector can select a different non-unique frictional fixed point.
"""
import numpy as np
import inertial_contact_cached_v1 as previous

base = previous.base
generalized_mass_matrix = previous.generalized_mass_matrix
stokes_generalized_resistance = previous.stokes_generalized_resistance
contact_model = previous.contact_model
finite_re = previous.finite_re


def normal_only_world_reactions(contacts, world_reactions):
    filtered = {}
    if not world_reactions:
        return filtered
    for grain_id, _, normal, _ in contacts:
        value = world_reactions.get(str(int(grain_id)), world_reactions.get(int(grain_id)))
        if value is None:
            continue
        normal = np.asarray(normal, float)
        magnitude = max(0.0, float(normal @ np.asarray(value, float)))
        filtered[str(int(grain_id))] = (magnitude * normal).tolist()
    return filtered


def inertial_contact_step(old_velocity, fluid_background_velocity, body_load,
                          stokes_resistance, lubrication_resistance, mass_matrix,
                          contacts, ell, dt, friction, fluid_density, viscosity,
                          equivalent_diameter, sphericity, world_reactions=None,
                          tolerance=1e-10, max_iterations=80):
    filtered = normal_only_world_reactions(contacts, world_reactions)
    return previous.inertial_contact_step(
        old_velocity, fluid_background_velocity, body_load,
        stokes_resistance, lubrication_resistance, mass_matrix,
        contacts, ell, dt, friction, fluid_density, viscosity,
        equivalent_diameter, sphericity, world_reactions=filtered,
        tolerance=tolerance, max_iterations=max_iterations,
    )
