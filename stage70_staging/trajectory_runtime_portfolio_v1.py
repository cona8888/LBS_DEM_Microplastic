"""Stage68 adaptive controller with Stage70 pruned recovery portfolio."""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage68_staging"),str(ROOT/"stage70_staging")]
import trajectory_extended_recovery_v1 as trajectory
import inertial_contact_runtime_portfolio_v1 as contact


def integrate(*args,**kwargs):
    original=trajectory.inertial
    before=contact.stats()
    contact.set_recovery_mode(False)
    trajectory.inertial=contact
    try:
        result=trajectory.integrate(*args,**kwargs)
    finally:
        trajectory.inertial=original
        contact.set_recovery_mode(False)
    after=contact.stats()
    result["recovery_portfolio_stats"]={k:after[k]-before[k] for k in after}
    return result


lubrication_matrix=trajectory.lubrication_matrix
enrich=trajectory.enrich
