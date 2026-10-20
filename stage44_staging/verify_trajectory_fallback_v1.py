"""Run the frozen Stage41 trajectory suite against the Stage44 fallback."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage41_staging"), str(ROOT / "stage44_staging")]
import verify_trajectory_optimized_v1 as verification
import trajectory_fallback_v1

verification.candidate = trajectory_fallback_v1

if __name__ == "__main__":
    verification.main()
