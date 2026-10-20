"""Stage60 persistent reduced-step cap with the frozen Stage53 solver."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage53_staging"), str(ROOT / "stage60_staging")]
import inertial_contact_multistart_lm_v1 as contact
import trajectory_persistent_reduced_cap_v1 as trajectory


def integrate(*args, **kwargs):
    original = trajectory.inertial
    before = contact.stats()
    trajectory.inertial = contact
    try:
        result = trajectory.integrate(*args, **kwargs)
    finally:
        trajectory.inertial = original
    after = contact.stats()
    result["multistart_lm_stats"] = {key: after[key] - before[key] for key in after}
    return result


lubrication_matrix = trajectory.lubrication_matrix
enrich = trajectory.enrich
