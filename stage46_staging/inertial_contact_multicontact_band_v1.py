"""Tolerance-band regularization restricted to simultaneous multi-contact.

Single-contact states retain the accepted Stage42 overlap correction exactly.
Only when two or more contacts are active are tolerance-scale negative gaps
mapped to zero in the complementarity solve; actual geometry remains unchanged.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage42_staging"))
import inertial_contact_robust_v1 as stage42

base = stage42.base
generalized_mass_matrix = stage42.generalized_mass_matrix
stokes_generalized_resistance = stage42.stokes_generalized_resistance
contact_model = stage42.contact_model
finite_re = stage42.finite_re
contact_solve = stage42.contact_solve
_stats = {"solves": 0, "multicontact_solves": 0, "regularized_solves": 0,
          "regularized_gaps": 0, "most_negative_regularized_gap_m": 0.0}

def stats(): return dict(_stats)

def inertial_contact_step(old_velocity, fluid_background_velocity, body_load,
                          stokes_resistance, lubrication_resistance, mass_matrix,
                          contacts, ell, dt, friction, fluid_density, viscosity,
                          equivalent_diameter, sphericity, world_reactions=None,
                          tolerance=1e-10, max_iterations=80):
    negative = [float(contact[1]) for contact in contacts if contact[1] < 0]
    regularize = len(contacts) >= 2 and bool(negative)
    adjusted = ([(contact[0], max(0.0, float(contact[1])), contact[2], contact[3])
                 for contact in contacts] if regularize else contacts)
    _stats["solves"] += 1
    _stats["multicontact_solves"] += int(len(contacts) >= 2)
    if regularize:
        _stats["regularized_solves"] += 1
        _stats["regularized_gaps"] += len(negative)
        _stats["most_negative_regularized_gap_m"] = min(
            _stats["most_negative_regularized_gap_m"], min(negative))
    result, health = stage42.inertial_contact_step(
        old_velocity, fluid_background_velocity, body_load,
        stokes_resistance, lubrication_resistance, mass_matrix,
        adjusted, ell, dt, friction, fluid_density, viscosity,
        equivalent_diameter, sphericity, world_reactions=world_reactions,
        tolerance=tolerance, max_iterations=max_iterations)
    health["multicontact_tolerance_band"] = bool(regularize)
    health["regularized_gap_count"] = len(negative) if regularize else 0
    return result, health
