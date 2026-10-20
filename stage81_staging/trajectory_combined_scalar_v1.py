"""Stage80 trajectory with scoped Stage74 algebraically equivalent kernels.

Single-threaded experiment only. All monkeypatches are restored in finally.
The Stage80 clearance/contact equations, controller, and physical gates remain.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage50_staging"), str(ROOT / "stage63_staging"),
                str(ROOT / "stage74_staging"), str(ROOT / "stage80_staging")]
import inertial_contact_seeded_lm_v1 as s50
import inertial_contact_projected_sor_v1 as s63
import scalar_contact_kernels_v1 as kernels
import trajectory_combined_pruning_v1 as parent


def integrate(*args, **kwargs):
    original = (s50._project, s50._residual, s63._solve)
    s50._project = kernels.project
    s50._residual = kernels.residual
    s63._solve = kernels.sor_solve
    try:
        result = parent.integrate(*args, **kwargs)
    finally:
        s50._project, s50._residual, s63._solve = original
    result["scalar_contact_kernel_policy"] = "scoped_stage74_v1"
    return result


lubrication_matrix = parent.lubrication_matrix
enrich = parent.enrich
