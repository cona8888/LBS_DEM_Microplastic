"""Finite-Re outer-drag multiplier and semi-implicit translation relaxation.

The empirical multiplier augments, but does not replace, the verified
anisotropic Stokes resistance.  It is based on equivalent-volume diameter
and sphericity and therefore does not claim orientation-resolved wake drag.
"""
import numpy as np


def prolate_sphericity(a, b):
    if a < b or b <= 0:
        raise ValueError("requires prolate semiaxes a >= b > 0")
    if np.isclose(a, b):
        return 1.0
    eccentricity = np.sqrt(1.0 - (b / a) ** 2)
    area = 2.0 * np.pi * b**2 * (1.0 + a * np.arcsin(eccentricity) / (b * eccentricity))
    equivalent_radius = (a * b * b) ** (1.0 / 3.0)
    return float(4.0 * np.pi * equivalent_radius**2 / area)


def haider_levenspiel_cd(reynolds, sphericity):
    """Haider & Levenspiel (1989), their comprehensive Eq. 11."""
    re = float(reynolds)
    phi = float(sphericity)
    if re <= 0 or not 0 < phi <= 1:
        raise ValueError("positive Reynolds number and 0<phi<=1 required")
    A = np.exp(2.3288 - 6.4581 * phi + 2.4486 * phi**2)
    B = 0.0964 + 0.5565 * phi
    C = np.exp(4.905 - 13.8944 * phi + 18.4222 * phi**2 - 10.2599 * phi**3)
    D = np.exp(1.4681 + 12.2584 * phi - 20.7322 * phi**2 + 15.8855 * phi**3)
    return float(24.0 / re * (1.0 + A * re**B) + C / (1.0 + D / re))


def sphere_cd(reynolds):
    """Haider & Levenspiel (1989) sphere correlation, their Eq. 6."""
    re = float(reynolds)
    if re <= 0:
        raise ValueError("positive Reynolds number required")
    return float(24.0 / re * (1.0 + 0.1806 * re**0.6459) + 0.4251 / (1.0 + 6880.95 / re))


def inertial_multiplier(reynolds, sphericity):
    """Ratio of empirical drag to the 24/Re Stokes drag coefficient."""
    re = float(reynolds)
    if re == 0:
        return 1.0
    return float(haider_levenspiel_cd(re, sphericity) * re / 24.0)


def reynolds_number(slip, density, viscosity, equivalent_diameter):
    if density <= 0 or viscosity <= 0 or equivalent_diameter <= 0:
        raise ValueError("positive fluid properties and diameter required")
    return float(density * np.linalg.norm(np.asarray(slip, float)) * equivalent_diameter / viscosity)


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
    """Backward-Euler step with fixed-point iteration of the drag multiplier."""
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

