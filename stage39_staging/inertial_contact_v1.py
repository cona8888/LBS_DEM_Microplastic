"""Semi-implicit rigid-body inertia, drag, lubrication, and hard contact.

Generalized velocity q=(U,a*omega); generalized load=(F,T/a).  Contact
reactions are forces, not impulses.  The step is backward Euler with a
finite-Re fixed point and the verified Stage37 Coulomb complementarity solve.
"""
import sys
from pathlib import Path

import numpy as np
from scipy.integrate import quad

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage37_staging"))
sys.path.insert(0, str(ROOT / "stage38_staging"))
import transport_contact as contact_model
import finite_re_relaxation_v2 as finite_re


def ellipsoid_added_mass_coefficients(a, b):
    """Potential-flow added-mass/displaced-mass ratios for a prolate spheroid."""
    if a < b or b <= 0:
        raise ValueError("requires a >= b > 0")
    if np.isclose(a, b):
        return 0.5, 0.5
    eccentricity = np.sqrt(1.0 - (b / a) ** 2)
    depolarization_parallel = (
        (1.0 - eccentricity**2)
        / (2.0 * eccentricity**3)
        * (np.log((1.0 + eccentricity) / (1.0 - eccentricity)) - 2.0 * eccentricity)
    )
    depolarization_perpendicular = (1.0 - depolarization_parallel) / 2.0
    return (
        float(depolarization_parallel / (1.0 - depolarization_parallel)),
        float(depolarization_perpendicular / (1.0 - depolarization_perpendicular)),
    )


def generalized_mass_matrix(axis, a, b, particle_density, fluid_density,
                            added_mass_fraction=1.0):
    """Rigid mass/inertia plus a scaled potential-flow translational added mass."""
    if min(a, b, particle_density, fluid_density) <= 0 or not 0 <= added_mass_fraction <= 1:
        raise ValueError("invalid mass properties")
    axis = contact_model.unit(axis)
    projector = np.outer(axis, axis)
    identity = np.eye(3)
    volume = 4.0 * np.pi * a * b * b / 3.0
    mass = particle_density * volume
    displaced_mass = fluid_density * volume
    added_parallel, added_perpendicular = ellipsoid_added_mass_coefficients(a, b)
    added = added_mass_fraction * displaced_mass * (
        added_parallel * projector + added_perpendicular * (identity - projector)
    )
    inertia_parallel = 2.0 * mass * b * b / 5.0
    inertia_perpendicular = mass * (a * a + b * b) / 5.0
    physical_inertia = inertia_parallel * projector + inertia_perpendicular * (identity - projector)
    generalized = np.zeros((6, 6))
    generalized[:3, :3] = mass * identity + added
    generalized[3:, 3:] = physical_inertia / (a * a)
    return generalized, {
        "particle_mass": mass,
        "displaced_fluid_mass": displaced_mass,
        "added_mass_coefficients": [added_parallel, added_perpendicular],
        "added_mass_fraction": added_mass_fraction,
    }


def _contact_jacobian(contacts, ell):
    rows = []
    for _grain, _gap, normal, lever in contacts:
        frame = contact_model.contact_frame(normal)
        rows.extend(np.c_[frame, np.cross(lever, frame) / ell])
    return np.asarray(rows, float).reshape(-1, 6)


def inertial_contact_step(old_velocity, background_velocity, body_load,
                          stokes_resistance, lubrication_resistance, mass_matrix,
                          contacts, ell, dt, friction, fluid_density, viscosity,
                          equivalent_diameter, sphericity, tolerance=1e-10,
                          max_iterations=80):
    """One implicit velocity/contact step at a frozen pose and fluid state."""
    old_velocity = np.asarray(old_velocity, float)
    background_velocity = np.asarray(background_velocity, float)
    body_load = np.asarray(body_load, float)
    stokes_resistance = np.asarray(stokes_resistance, float)
    lubrication_resistance = np.asarray(lubrication_resistance, float)
    mass_matrix = np.asarray(mass_matrix, float)
    if any(vector.shape != (6,) for vector in (old_velocity, background_velocity, body_load)):
        raise ValueError("generalized vectors must have length six")
    if any(matrix.shape != (6, 6) for matrix in (stokes_resistance, lubrication_resistance, mass_matrix)):
        raise ValueError("generalized matrices must be 6x6")
    if dt <= 0:
        raise ValueError("positive dt required")
    candidate = old_velocity.copy()
    scale = max(np.linalg.norm(old_velocity), np.linalg.norm(background_velocity), 1e-30)
    for iteration in range(max_iterations):
        reynolds = finite_re.reynolds_number(
            candidate[:3] - background_velocity[:3], fluid_density, viscosity, equivalent_diameter
        )
        multiplier = finite_re.inertial_multiplier(reynolds, sphericity)
        drag_resistance = stokes_resistance.copy()
        drag_resistance[:3, :3] *= multiplier
        total_resistance = drag_resistance + lubrication_resistance
        system = mass_matrix / dt + total_resistance
        compliance = np.linalg.inv(system)
        free_velocity = compliance @ (
            mass_matrix @ old_velocity / dt
            + total_resistance @ background_velocity
            + body_load
        )
        updated, contact_health = contact_model.contact_solve(
            free_velocity, compliance, contacts, ell, dt, friction, tol=1e-10
        )
        if np.linalg.norm(updated - candidate) / scale <= tolerance:
            candidate = updated
            break
        candidate = updated
    else:
        raise RuntimeError("inertial/contact fixed point did not converge")

    jacobian = _contact_jacobian(contacts, ell)
    reaction = np.asarray(contact_health["reactions"], float)
    reaction_load = jacobian.T @ reaction if len(reaction) else np.zeros(6)
    residual = (
        mass_matrix @ (candidate - old_velocity) / dt
        + total_resistance @ (candidate - background_velocity)
        - body_load
        - reaction_load
    )
    denominator = max(
        np.linalg.norm(mass_matrix @ (candidate - old_velocity) / dt),
        np.linalg.norm(total_resistance @ (candidate - background_velocity)),
        np.linalg.norm(body_load),
        np.linalg.norm(reaction_load),
        1e-30,
    )
    momentum_residual = float(np.linalg.norm(residual) / denominator)
    if momentum_residual > 1e-8 or not np.isfinite(candidate).all():
        raise RuntimeError("inertial momentum closure failed")
    return candidate, {
        "iterations": iteration + 1,
        "reynolds": reynolds,
        "finite_re_multiplier": multiplier,
        "momentum_residual": momentum_residual,
        "contact": contact_health,
        "minimum_system_eigenvalue": float(np.linalg.eigvalsh((system + system.T) / 2).min()),
    }


def stokes_generalized_resistance(axis, a, b, viscosity):
    """Inverse of the already verified free-space mobility."""
    return np.linalg.inv(contact_model.mobility(axis, a, b, viscosity))
