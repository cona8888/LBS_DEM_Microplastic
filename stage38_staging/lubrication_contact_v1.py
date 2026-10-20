"""Matched normal-lubrication correction for a rigid body near fixed grains.

This module augments a verified far-field 6-DOF mobility below a declared
clearance cutoff.  It adds only the positive normal squeeze resistance in
excess of its cutoff value; tangential lubrication, adhesion, deformation,
and surface roughness physics are not inferred here.

Generalized velocity is (U, ell*omega), and generalized load is
(F, torque/ell), matching stage37_staging.transport_contact.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage37_staging"))
from transport_contact import finite, unit


def prolate_principal_curvatures(lever, axis, a, b):
    """Return the two positive principal curvatures at a prolate surface point."""
    if a < b or b <= 0:
        raise ValueError("requires prolate semiaxes a >= b > 0")
    lever = finite(lever)
    axis = unit(axis)
    cosine = np.clip(np.dot(lever, axis) / a, -1.0, 1.0)
    sine2 = max(0.0, 1.0 - cosine**2)
    metric = np.sqrt(a * a * sine2 + b * b * cosine**2)
    meridional = a * b / metric**3
    azimuthal = a / (b * metric)
    return float(meridional), float(azimuthal)


def squeeze_prefactor(mu, grain_radius, body_curvatures):
    """Coefficient C in R_normal = C/h for two locally convex surfaces.

    For gap H=h+A*x^2/2+B*y^2/2, the Reynolds equation gives
    C=12*pi*mu/((A+B)*sqrt(A*B)).
    """
    if mu <= 0 or grain_radius <= 0:
        raise ValueError("positive viscosity and grain radius required")
    k1, k2 = map(float, body_curvatures)
    if min(k1, k2) <= 0:
        raise ValueError("positive convex body curvatures required")
    A = 1.0 / grain_radius + k1
    B = 1.0 / grain_radius + k2
    return float(12.0 * np.pi * mu / ((A + B) * np.sqrt(A * B)))


def normal_jacobian(normal, lever, ell):
    """Map generalized body velocity to normal relative velocity."""
    normal = unit(normal)
    lever = finite(lever)
    if ell <= 0:
        raise ValueError("positive generalized length required")
    return np.r_[normal, np.cross(lever, normal) / ell]


def matched_excess_resistance(gap, cutoff, roughness, prefactor):
    """Positive C*(1/max(h,roughness)-1/cutoff) below the cutoff."""
    if cutoff <= 0 or roughness <= 0 or roughness >= cutoff or prefactor <= 0:
        raise ValueError("invalid cutoff, roughness, or prefactor")
    if gap >= cutoff:
        return 0.0
    effective = max(float(gap), roughness)
    return float(prefactor * (1.0 / effective - 1.0 / cutoff))


def lubricated_motion(vfree, far_mobility, contacts, axis, a, b, ell, mu, cutoff, roughness):
    """Return motion and mobility after additive normal pair resistances.

    Each contact tuple is (grain_id, gap, normal, body lever, grain_radius).
    Fixed-grain relative velocity is assumed.  The far-field driving load is
    preserved as inv(M_far) @ vfree.
    """
    vfree = finite(vfree)
    far_mobility = finite(far_mobility)
    if far_mobility.shape != (6, 6):
        raise ValueError("expected 6x6 mobility")
    resistance = np.linalg.inv(far_mobility)
    additions = []
    for contact in contacts:
        if len(contact) != 5:
            raise ValueError("contact requires grain radius")
        grain_id, gap, normal, lever, grain_radius = contact
        curvatures = prolate_principal_curvatures(lever, axis, a, b)
        prefactor = squeeze_prefactor(mu, grain_radius, curvatures)
        coefficient = matched_excess_resistance(gap, cutoff, roughness, prefactor)
        jacobian = normal_jacobian(normal, lever, ell)
        resistance += coefficient * np.outer(jacobian, jacobian)
        additions.append(
            {
                "grain_id": int(grain_id),
                "gap": float(gap),
                "grain_radius": float(grain_radius),
                "body_curvatures": list(curvatures),
                "prefactor": prefactor,
                "excess_coefficient": coefficient,
            }
        )
    mobility = np.linalg.inv(resistance)
    motion = mobility @ np.linalg.solve(far_mobility, vfree)
    symmetric_error = np.linalg.norm(mobility - mobility.T) / np.linalg.norm(mobility)
    eigenvalue = np.linalg.eigvalsh((mobility + mobility.T) / 2.0).min()
    if symmetric_error > 1e-10 or eigenvalue <= 0 or not np.isfinite(motion).all():
        raise RuntimeError("nonphysical lubricated mobility")
    return motion, mobility, {
        "contacts": additions,
        "mobility_symmetry_residual": float(symmetric_error),
        "minimum_mobility_eigenvalue": float(eigenvalue),
    }

