"""Stage64 adaptive trajectory using bounded Stage53/SOR recovery episodes."""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage64_staging")]
import inertial_contact_hybrid_recovery_v1 as contact
import trajectory_hybrid_recovery_v1 as trajectory


def integrate(*args,**kwargs):
    original=trajectory.inertial; before=contact.stats(); contact.set_recovery_mode(False); trajectory.inertial=contact
    try: result=trajectory.integrate(*args,**kwargs)
    finally: trajectory.inertial=original; contact.set_recovery_mode(False)
    after=contact.stats(); result["hybrid_solver_stats"]={k:after[k]-before[k] for k in after}; return result


lubrication_matrix=trajectory.lubrication_matrix
enrich=trajectory.enrich
