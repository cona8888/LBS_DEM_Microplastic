"""Polydisperse extension of the verified Stage38 normal lubrication primitive."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage37_staging"))
sys.path.insert(0, str(ROOT / "stage38_staging"))
from transport_contact import finite
from lubrication_contact_v1 import (
    matched_excess_resistance,
    normal_jacobian,
    prolate_principal_curvatures,
    squeeze_prefactor,
)


def lubricated_motion(vfree, far_mobility, contacts, axis, a, b, ell, mu,
                      cutoff_ratio, roughness_ratio):
    """Add pairwise normal resistance using each grain's own radius.

    Each contact is (grain_id, gap, normal, body lever, grain_radius).
    """
    vfree = finite(vfree)
    far_mobility = finite(far_mobility)
    if far_mobility.shape != (6, 6):
        raise ValueError("expected 6x6 mobility")
    if not 0 < roughness_ratio < cutoff_ratio:
        raise ValueError("require 0 < roughness_ratio < cutoff_ratio")
    resistance = np.linalg.inv(far_mobility)
    additions = []
    for grain_id, gap, normal, lever, grain_radius in contacts:
        cutoff = cutoff_ratio * grain_radius
        roughness = roughness_ratio * grain_radius
        curvatures = prolate_principal_curvatures(lever, axis, a, b)
        prefactor = squeeze_prefactor(mu, grain_radius, curvatures)
        coefficient = matched_excess_resistance(gap, cutoff, roughness, prefactor)
        jacobian = normal_jacobian(normal, lever, ell)
        resistance += coefficient * np.outer(jacobian, jacobian)
        additions.append({
            "grain_id": int(grain_id),
            "gap": float(gap),
            "grain_radius": float(grain_radius),
            "cutoff": float(cutoff),
            "roughness": float(roughness),
            "body_curvatures": list(curvatures),
            "prefactor": prefactor,
            "excess_coefficient": coefficient,
        })
    mobility = np.linalg.inv(resistance)
    motion = mobility @ np.linalg.solve(far_mobility, vfree)
    symmetry = np.linalg.norm(mobility - mobility.T) / np.linalg.norm(mobility)
    minimum_eigenvalue = np.linalg.eigvalsh((mobility + mobility.T) / 2).min()
    if symmetry > 1e-10 or minimum_eigenvalue <= 0 or not np.isfinite(motion).all():
        raise RuntimeError("nonphysical lubricated mobility")
    return motion, mobility, {
        "contacts": additions,
        "mobility_symmetry_residual": float(symmetry),
        "minimum_mobility_eigenvalue": float(minimum_eigenvalue),
    }

