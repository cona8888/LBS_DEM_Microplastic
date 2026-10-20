"""Sequential Stage46 trajectory entry point with regularization accounting."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage41_staging"), str(ROOT / "stage46_staging")]
import trajectory_optimized_v1 as stage41
import inertial_contact_multicontact_band_v1 as contact

def integrate(*args, **kwargs):
    original = stage41.inertial; before = contact.stats(); stage41.inertial = contact
    try: result = stage41.integrate(*args, **kwargs)
    finally: stage41.inertial = original
    after = contact.stats()
    result["multicontact_band_stats"] = {key: after[key]-before[key] for key in
        ("solves", "multicontact_solves", "regularized_solves", "regularized_gaps")}
    result["multicontact_band_stats"]["most_negative_regularized_gap_m"] = (
        after["most_negative_regularized_gap_m"] if
        after["regularized_solves"] > before["regularized_solves"] else 0.0)
    return result

lubrication_matrix = stage41.lubrication_matrix
enrich = stage41.enrich
