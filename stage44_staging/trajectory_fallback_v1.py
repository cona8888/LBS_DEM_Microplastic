"""Sequential Stage44 trajectory entry point with fallback diagnostics."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage41_staging"), str(ROOT / "stage44_staging")]
import trajectory_optimized_v1 as stage41
import inertial_contact_fallback_v1 as fallback


def integrate(*args, **kwargs):
    original = stage41.inertial
    before = fallback.stats()
    stage41.inertial = fallback
    try:
        result = stage41.integrate(*args, **kwargs)
    finally:
        stage41.inertial = original
    after = fallback.stats()
    result["contact_solver_stats"] = {
        "standard_solves": after["standard_solves"] - before["standard_solves"],
        "fallback_solves": after["fallback_solves"] - before["fallback_solves"],
        "fallback_failures": after["fallback_failures"] - before["fallback_failures"],
        "damping_used": {key: after["damping_used"].get(key, 0) - before["damping_used"].get(key, 0)
                         for key in set(before["damping_used"]) | set(after["damping_used"])}
    }
    return result


lubrication_matrix = stage41.lubrication_matrix
enrich = stage41.enrich
