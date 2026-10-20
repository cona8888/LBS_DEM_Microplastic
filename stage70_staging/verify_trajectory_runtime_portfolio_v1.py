"""Frozen Stage41 smoke verification for Stage70 runtime portfolio."""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage41_staging"),str(ROOT/"stage70_staging")]
import verify_trajectory_optimized_v1 as verification
import trajectory_runtime_portfolio_v1 as candidate

verification.candidate=candidate
if __name__=="__main__":
    verification.main()
