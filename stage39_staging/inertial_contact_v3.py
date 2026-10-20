"""Inertial/contact step with a non-degenerate momentum-closure scale.

The mechanics are unchanged from v2.  The residual is normalised by the
largest resolved load or by the imposed outer-drag scale.  The latter keeps
the diagnostic well conditioned as a particle asymptotically follows a
uniform fluid and both acceleration and slip drag vanish.
"""
import numpy as np
import inertial_contact_v2 as previous

base = previous.base
ellipsoid_added_mass_coefficients = previous.ellipsoid_added_mass_coefficients
generalized_mass_matrix = previous.generalized_mass_matrix
stokes_generalized_resistance = previous.stokes_generalized_resistance
contact_model = previous.contact_model
finite_re = previous.finite_re


def inertial_contact_step(old_velocity, fluid_background_velocity, body_load,
                          stokes_resistance, lubrication_resistance, mass_matrix,
                          contacts, ell, dt, friction, fluid_density, viscosity,
                          equivalent_diameter, sphericity, tolerance=1e-10,
                          max_iterations=80):
    old_velocity = np.asarray(old_velocity, float)
    background = np.asarray(fluid_background_velocity, float)
    body_load = np.asarray(body_load, float)
    stokes = np.asarray(stokes_resistance, float)
    lubrication = np.asarray(lubrication_resistance, float)
    mass = np.asarray(mass_matrix, float)
    if any(vector.shape != (6,) for vector in (old_velocity, background, body_load)):
        raise ValueError("generalized vectors must have length six")
    if any(matrix.shape != (6, 6) for matrix in (stokes, lubrication, mass)):
        raise ValueError("generalized matrices must be 6x6")
    if dt <= 0:
        raise ValueError("positive dt required")
    candidate = old_velocity.copy()
    velocity_scale = max(np.linalg.norm(old_velocity), np.linalg.norm(background), 1e-30)
    for iteration in range(max_iterations):
        reynolds = finite_re.reynolds_number(
            candidate[:3] - background[:3], fluid_density, viscosity, equivalent_diameter
        )
        multiplier = finite_re.inertial_multiplier(reynolds, sphericity)
        drag = stokes.copy()
        drag[:3, :3] *= multiplier
        system = mass / dt + drag + lubrication
        compliance = np.linalg.inv(system)
        free_velocity = compliance @ (
            mass @ old_velocity / dt + drag @ background + body_load
        )
        updated, contact_health = contact_model.contact_solve(
            free_velocity, compliance, contacts, ell, dt, friction, tol=1e-10
        )
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
    imposed_drag_scale = np.linalg.norm(drag @ background)
    denominator = max(
        np.linalg.norm(acceleration_load), np.linalg.norm(slip_drag),
        np.linalg.norm(lubrication_load), np.linalg.norm(body_load),
        np.linalg.norm(reaction_load), imposed_drag_scale, 1e-30,
    )
    momentum_residual = float(np.linalg.norm(residual) / denominator)
    if momentum_residual > 1e-8 or not np.isfinite(candidate).all():
        raise RuntimeError("inertial momentum closure failed")
    return candidate, {
        "iterations": iteration + 1,
        "reynolds": reynolds,
        "finite_re_multiplier": multiplier,
        "momentum_residual": momentum_residual,
        "momentum_reference_load": float(denominator),
        "contact": contact_health,
        "minimum_system_eigenvalue": float(np.linalg.eigvalsh((system + system.T) / 2).min()),
    }
