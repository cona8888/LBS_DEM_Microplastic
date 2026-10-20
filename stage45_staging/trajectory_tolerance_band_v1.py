"""Sequential Stage45 trajectory entry point with tolerance-band diagnostics."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage41_staging"), str(ROOT / "stage45_staging")]
import trajectory_optimized_v1 as stage41
import inertial_contact_tolerance_band_v1 as tolerance_band


def integrate(*args, **kwargs):
    original = stage41.inertial
    before = tolerance_band.stats()
    stage41.inertial = tolerance_band
    try:
        result = stage41.integrate(*args, **kwargs)
    finally:
        stage41.inertial = original
    after = tolerance_band.stats()
    result["tolerance_band_stats"] = {
        key: after[key] - before[key] for key in
        ("solves", "solves_with_clipped_gaps", "clipped_gaps")}
    result["tolerance_band_stats"]["most_negative_clipped_gap_m"] = (
        after["most_negative_clipped_gap_m"] if
        after["solves_with_clipped_gaps"] > before["solves_with_clipped_gaps"] else 0.0)
    return result


lubrication_matrix = stage41.lubrication_matrix
enrich = stage41.enrich
