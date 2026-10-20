"""Run the frozen Stage41 suite against Stage50."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage41_staging"),str(ROOT/"stage50_staging")]
import verify_trajectory_optimized_v1 as verification
import trajectory_seeded_lm_v1
verification.candidate=trajectory_seeded_lm_v1
if __name__=="__main__": verification.main()
