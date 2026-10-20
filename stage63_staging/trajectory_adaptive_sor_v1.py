"""Stage57 adaptive rejection recovery with Stage63 projected SOR accounting."""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage57_staging"),str(ROOT/"stage63_staging")]
import trajectory_adaptive_contact_retry_v1 as trajectory
import inertial_contact_projected_sor_v1 as contact


def integrate(*args,**kwargs):
    original=trajectory.inertial; before=contact.stats(); trajectory.inertial=contact
    try: result=trajectory.integrate(*args,**kwargs)
    finally: trajectory.inertial=original
    after=contact.stats(); result["projected_sor_stats"]={k:after[k]-before[k] for k in after}; return result


lubrication_matrix=trajectory.lubrication_matrix
enrich=trajectory.enrich
