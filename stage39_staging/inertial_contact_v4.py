"""Warm-started nonlinear inertial/contact solve for difficult multicontact states."""
import numpy as np
import inertial_contact_v3 as previous

base = previous.base
ellipsoid_added_mass_coefficients = previous.ellipsoid_added_mass_coefficients
generalized_mass_matrix = previous.generalized_mass_matrix
stokes_generalized_resistance = previous.stokes_generalized_resistance
contact_model = previous.contact_model
finite_re = previous.finite_re


def _warm_contact_solve(vfree, mobility, contacts, ell, dt, friction,
                        initial=None, tolerance=1e-10, max_iterations=10000):
    if not contacts:
        return vfree, {"iterations": 0, "residual": 0.0, "force_residual": 0.0,
                       "dissipation": 0.0, "reactions": []}
    jacobian = []
    gaps = []
    for _, gap, normal, lever in contacts:
        frame = contact_model.contact_frame(normal)
        jacobian.extend(np.c_[frame, np.cross(lever, frame) / ell])
        gaps.append(gap)
    jacobian = np.asarray(jacobian)
    gaps = np.asarray(gaps)
    matrix = jacobian @ mobility @ jacobian.T
    free_contact_velocity = jacobian @ vfree
    force = np.zeros(len(free_contact_velocity)) if initial is None else np.asarray(initial, float).copy()
    if force.shape != free_contact_velocity.shape:
        force = np.zeros(len(free_contact_velocity))
    scale = max(np.linalg.norm(vfree), 1e-15)
    for iteration in range(max_iterations):
        for contact_index in range(len(contacts)):
            index = 3 * contact_index
            normal_velocity = (free_contact_velocity[index] + matrix[index] @ force
                               + gaps[contact_index] / dt)
            force[index] = max(0.0, force[index] - normal_velocity / matrix[index, index])
            tangential_velocity = free_contact_velocity[index + 1:index + 3] + matrix[index + 1:index + 3] @ force
            step = np.linalg.eigvalsh(matrix[index + 1:index + 3, index + 1:index + 3]).max()
            trial = force[index + 1:index + 3] - tangential_velocity / step
            limit = friction * force[index]
            norm = np.linalg.norm(trial)
            force[index + 1:index + 3] = trial * min(1.0, limit / max(norm, 1e-300))
        contact_velocity = free_contact_velocity + matrix @ force
        residual = 0.0
        for contact_index in range(len(contacts)):
            index = 3 * contact_index
            normal = contact_velocity[index] + gaps[contact_index] / dt
            residual = max(residual, abs(min(matrix[index, index] * force[index], normal)))
            step = np.linalg.eigvalsh(matrix[index + 1:index + 3, index + 1:index + 3]).max()
            trial = force[index + 1:index + 3] - contact_velocity[index + 1:index + 3] / step
            limit = friction * force[index]
            norm = np.linalg.norm(trial)
            projected = trial * min(1.0, limit / max(norm, 1e-300))
            residual = max(residual, np.linalg.norm(force[index + 1:index + 3] - projected) * step)
        if residual / scale <= tolerance:
            break
    else:
        raise RuntimeError("contact nonconvergence")
    velocity = vfree + mobility @ jacobian.T @ force
    reaction_load = jacobian.T @ force
    force_residual = (np.linalg.norm(np.linalg.solve(mobility, velocity - vfree) - reaction_load)
                      / max(np.linalg.norm(reaction_load), 1e-30))
    tangential_work = sum(float(force[3*k+1:3*k+3] @ contact_velocity[3*k+1:3*k+3])
                          for k in range(len(contacts)))
    if tangential_work > 1e-8 * max(np.linalg.norm(force) * scale, 1e-30):
        raise RuntimeError("friction generates energy")
    return velocity, {"iterations": iteration + 1, "residual": residual / scale,
                      "force_residual": float(force_residual), "dissipation": -tangential_work,
                      "reactions": force.tolist()}


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
    candidate = old_velocity.copy()
    velocity_scale = max(np.linalg.norm(old_velocity), np.linalg.norm(background), 1e-30)
    warm_reactions = None
    total_contact_iterations = 0
    for iteration in range(max_iterations):
        reynolds = finite_re.reynolds_number(candidate[:3] - background[:3], fluid_density, viscosity, equivalent_diameter)
        multiplier = finite_re.inertial_multiplier(reynolds, sphericity)
        drag = stokes.copy()
        drag[:3, :3] *= multiplier
        system = mass / dt + drag + lubrication
        compliance = np.linalg.inv(system)
        free_velocity = compliance @ (mass @ old_velocity / dt + drag @ background + body_load)
        updated, contact_health = _warm_contact_solve(
            free_velocity, compliance, contacts, ell, dt, friction,
            initial=warm_reactions, tolerance=1e-10, max_iterations=10000,
        )
        total_contact_iterations += contact_health["iterations"]
        warm_reactions = contact_health["reactions"]
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
    return candidate, {"iterations": iteration + 1, "reynolds": reynolds,
                       "finite_re_multiplier": multiplier, "momentum_residual": momentum_residual,
                       "momentum_reference_load": float(denominator), "contact": contact_health,
                       "total_contact_iterations": total_contact_iterations,
                       "minimum_system_eigenvalue": float(np.linalg.eigvalsh((system + system.T) / 2).min())}
