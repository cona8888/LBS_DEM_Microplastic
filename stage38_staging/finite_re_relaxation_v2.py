"""Finite-Re relaxation using the source paper's shape-specific recommendation."""
import numpy as np
import finite_re_relaxation_v1 as base

prolate_sphericity = base.prolate_sphericity
haider_levenspiel_cd = base.haider_levenspiel_cd
sphere_cd = base.sphere_cd
reynolds_number = base.reynolds_number


def inertial_multiplier(reynolds, sphericity):
    re = float(reynolds)
    phi = float(sphericity)
    if re == 0:
        return 1.0
    if not 0 < phi <= 1:
        raise ValueError("require 0<phi<=1")
    cd = sphere_cd(re) if abs(phi - 1.0) <= 1e-14 else haider_levenspiel_cd(re, phi)
    return float(cd * re / 24.0)


def nonlinear_drag(stokes_resistance, slip, density, viscosity, equivalent_diameter, sphericity):
    slip = np.asarray(slip, float)
    resistance = np.asarray(stokes_resistance, float)
    if resistance.shape != (3, 3) or not np.isfinite(resistance).all() or not np.isfinite(slip).all():
        raise ValueError("invalid drag inputs")
    re = reynolds_number(slip, density, viscosity, equivalent_diameter)
    multiplier = inertial_multiplier(re, sphericity)
    return -multiplier * resistance @ slip, {"reynolds": re, "multiplier": multiplier}


def implicit_translation_step(velocity, fluid_velocity, force, stokes_resistance,
                              mass, dt, density, viscosity, equivalent_diameter,
                              sphericity, tolerance=1e-12, max_iterations=50):
    velocity = np.asarray(velocity, float)
    fluid_velocity = np.asarray(fluid_velocity, float)
    force = np.asarray(force, float)
    resistance = np.asarray(stokes_resistance, float)
    if mass <= 0 or dt <= 0 or any(x.shape != (3,) for x in (velocity, fluid_velocity, force)):
        raise ValueError("invalid relaxation state")
    candidate = velocity.copy()
    scale = max(np.linalg.norm(fluid_velocity), np.linalg.norm(velocity), 1e-30)
    for iteration in range(max_iterations):
        re = reynolds_number(candidate - fluid_velocity, density, viscosity, equivalent_diameter)
        multiplier = inertial_multiplier(re, sphericity)
        matrix = mass / dt * np.eye(3) + multiplier * resistance
        updated = np.linalg.solve(matrix, mass / dt * velocity + multiplier * resistance @ fluid_velocity + force)
        if np.linalg.norm(updated - candidate) / scale <= tolerance:
            candidate = updated
            break
        candidate = updated
    else:
        raise RuntimeError("finite-Re relaxation iteration did not converge")
    if not np.isfinite(candidate).all():
        raise FloatingPointError("nonfinite relaxed velocity")
    return candidate, {"iterations": iteration + 1, "reynolds": re, "multiplier": multiplier}

