"""Stage70 trajectory with scoped Stage76 proven-violation sweep pruning."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage68_staging"), str(ROOT / "stage70_staging"),
                str(ROOT / "stage76_staging")]
import trajectory_extended_recovery_v1 as core
import trajectory_runtime_portfolio_v1 as baseline
import geometry_fail_fast_sweep_v1 as fast


def integrate(*args, **kwargs):
    original = core.geometry_tools.swept_gap
    before = fast.stats()
    core.geometry_tools.swept_gap = fast.swept_gap
    try:
        result = baseline.integrate(*args, **kwargs)
    finally:
        core.geometry_tools.swept_gap = original
    after = fast.stats()
    result["fail_fast_sweep_stats"] = {k: after[k] - before[k] for k in after}
    return result


lubrication_matrix = core.lubrication_matrix
enrich = core.enrich
