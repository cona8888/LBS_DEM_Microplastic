"""Stage58 persistent contact-step controller with frozen Stage42 cold PGS."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage42_staging"), str(ROOT / "stage58_staging")]
import inertial_contact_robust_v1 as contact
import trajectory_contact_dt_controller_v1 as trajectory


def integrate(*args, **kwargs):
    original = trajectory.inertial
    trajectory.inertial = contact
    try:
        return trajectory.integrate(*args, **kwargs)
    finally:
        trajectory.inertial = original


lubrication_matrix = trajectory.lubrication_matrix
enrich = trajectory.enrich
