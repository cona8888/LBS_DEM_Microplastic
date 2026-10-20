"""Run the frozen Stage41 trajectory verification against Stage42 binding."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage41_staging"), str(ROOT / "stage42_staging")]
import verify_trajectory_optimized_v1 as verification
import trajectory_robust_v1

verification.candidate = trajectory_robust_v1

if __name__ == "__main__":
    verification.main()
