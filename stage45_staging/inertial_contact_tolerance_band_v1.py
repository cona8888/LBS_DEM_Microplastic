"""Tolerance-consistent contact solve for rigid multi-contact states.

The trajectory integrator independently rejects any initial or swept overlap
deeper than its geometry tolerance.  This adapter therefore maps the remaining
negative, tolerance-scale gaps to zero only in the complementarity solve,
avoiding mutually incompatible one-step overlap-correction demands.  Actual
geometry gaps remain unchanged for clearance acceptance and reporting.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage42_staging")]
import inertial_contact_robust_v1 as stage42

base = stage42.base
generalized_mass_matrix = stage42.generalized_mass_matrix
stokes_generalized_resistance = stage42.stokes_generalized_resistance
contact_model = stage42.contact_model
finite_re = stage42.finite_re
contact_solve = stage42.contact_solve

_stats = {"solves": 0, "solves_with_clipped_gaps": 0, "clipped_gaps": 0,
          "most_negative_clipped_gap_m": 0.0}


def stats():
    return dict(_stats)


def inertial_contact_step(old_velocity, fluid_background_velocity, body_load,
                          stokes_resistance, lubrication_resistance, mass_matrix,
                          contacts, ell, dt, friction, fluid_density, viscosity,
                          equivalent_diameter, sphericity, world_reactions=None,
                          tolerance=1e-10, max_iterations=80):
    negative = [float(contact[1]) for contact in contacts if contact[1] < 0]
    adjusted = [(contact[0], max(0.0, float(contact[1])), contact[2], contact[3])
                for contact in contacts]
    _stats["solves"] += 1
    if negative:
        _stats["solves_with_clipped_gaps"] += 1
        _stats["clipped_gaps"] += len(negative)
        _stats["most_negative_clipped_gap_m"] = min(
            _stats["most_negative_clipped_gap_m"], min(negative))
    result, health = stage42.inertial_contact_step(
        old_velocity, fluid_background_velocity, body_load,
        stokes_resistance, lubrication_resistance, mass_matrix,
        adjusted, ell, dt, friction, fluid_density, viscosity,
        equivalent_diameter, sphericity, world_reactions=world_reactions,
        tolerance=tolerance, max_iterations=max_iterations)
    health["tolerance_band_clipped_gap_count"] = len(negative)
    health["most_negative_clipped_gap_m"] = min(negative) if negative else 0.0
    return result, health
