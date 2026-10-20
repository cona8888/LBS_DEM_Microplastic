"""Run the frozen Stage41 smoke suite against explicit Stage53 binding."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'stage41_staging'))
import verify_trajectory_optimized_v1 as verification
import trajectory_explicit_v1
verification.candidate=trajectory_explicit_v1
if __name__=='__main__':verification.main()
