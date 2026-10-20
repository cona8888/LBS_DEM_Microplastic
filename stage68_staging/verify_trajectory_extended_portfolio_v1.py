"""Run the frozen Stage41 smoke suite against Stage68."""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage41_staging"),str(ROOT/"stage68_staging")]
import verify_trajectory_optimized_v1 as verification
import trajectory_extended_portfolio_v1 as candidate

verification.candidate=candidate
if __name__=="__main__":
    verification.main()
