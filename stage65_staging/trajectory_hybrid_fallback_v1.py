"""Stage64 adaptive controller with Stage65 SOR/Stage53 recovery fallback."""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage64_staging"),str(ROOT/"stage65_staging")]
import trajectory_hybrid_recovery_v1 as trajectory
import inertial_contact_hybrid_fallback_v1 as contact


def integrate(*args,**kwargs):
    original=trajectory.inertial; before=contact.stats(); contact.set_recovery_mode(False); trajectory.inertial=contact
    try: result=trajectory.integrate(*args,**kwargs)
    finally: trajectory.inertial=original; contact.set_recovery_mode(False)
    after=contact.stats(); result["hybrid_solver_stats"]={k:after[k]-before[k] for k in after}; return result


lubrication_matrix=trajectory.lubrication_matrix
enrich=trajectory.enrich
