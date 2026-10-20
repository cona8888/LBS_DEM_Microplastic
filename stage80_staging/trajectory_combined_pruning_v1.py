"""Stage76 proven sweep pruning plus Stage79 frozen-pose contact reuse.

Both optimizations retain the existing Stage68 adaptive controller, Stage70
fallback portfolio, and strict original contact/momentum acceptance gates.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage68_staging"), str(ROOT / "stage76_staging"),
                str(ROOT / "stage79_staging")]
import trajectory_extended_recovery_v1 as core
import geometry_fail_fast_sweep_v1 as fast
import inertial_contact_within_pose_reuse_v1 as contact


def integrate(*args, **kwargs):
    original_sweep = core.geometry_tools.swept_gap
    original_inertial = core.inertial
    before_sweep = fast.stats()
    before_contact = contact.reuse_stats()
    core.geometry_tools.swept_gap = fast.swept_gap
    core.inertial = contact
    contact.set_recovery_mode(False)
    try:
        result = core.integrate(*args, **kwargs)
    finally:
        core.geometry_tools.swept_gap = original_sweep
        core.inertial = original_inertial
        contact.set_recovery_mode(False)
    after_sweep = fast.stats()
    after_contact = contact.reuse_stats()
    result["fail_fast_sweep_stats"] = {
        k: after_sweep[k] - before_sweep[k] for k in before_sweep}
    result["within_pose_reuse_stats"] = {
        k: after_contact[k] - before_contact[k] for k in before_contact}
    return result


lubrication_matrix = core.lubrication_matrix
enrich = core.enrich
