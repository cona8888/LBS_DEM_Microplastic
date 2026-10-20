"""Run the frozen Stage41 trajectory suite against Stage45."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage41_staging"), str(ROOT / "stage45_staging")]
import verify_trajectory_optimized_v1 as verification
import trajectory_tolerance_band_v1

verification.candidate = trajectory_tolerance_band_v1

if __name__ == "__main__":
    verification.main()
