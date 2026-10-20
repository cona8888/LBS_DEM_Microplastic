"""Sequential Stage42 trajectory entry point using the robust cold solver.

The Stage41 integrator is unchanged.  A scoped solver binding selects the
Stage42 contact implementation for this call and is restored afterward.
Concurrent calls in one Python interpreter are deliberately unsupported;
campaign workers must use separate processes.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage41_staging"), str(ROOT / "stage42_staging")]
import trajectory_optimized_v1 as stage41
import inertial_contact_robust_v1 as robust_inertial


def integrate(*args, **kwargs):
    original = stage41.inertial
    if original is robust_inertial:
        raise RuntimeError("nested robust trajectory calls are unsupported")
    stage41.inertial = robust_inertial
    try:
        return stage41.integrate(*args, **kwargs)
    finally:
        stage41.inertial = original


lubrication_matrix = stage41.lubrication_matrix
enrich = stage41.enrich
