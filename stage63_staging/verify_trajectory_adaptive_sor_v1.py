"""Run the frozen Stage41 manufactured suite against Stage63."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage41_staging"),str(ROOT/"stage63_staging")]
import verify_trajectory_optimized_v1 as verification
import trajectory_adaptive_sor_v1
verification.candidate=trajectory_adaptive_sor_v1
if __name__=="__main__": verification.main()
