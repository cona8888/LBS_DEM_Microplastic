"""Sequential Stage53 trajectory entry point with multistart-LM accounting."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage41_staging"),str(ROOT/"stage53_staging")]
import trajectory_optimized_v1 as s41
import inertial_contact_multistart_lm_v1 as contact
def integrate(*args,**kwargs):
    original=s41.inertial; before=contact.stats(); s41.inertial=contact
    try: result=s41.integrate(*args,**kwargs)
    finally: s41.inertial=original
    after=contact.stats(); result["multistart_lm_stats"]={k:after[k]-before[k] for k in after}; return result
lubrication_matrix=s41.lubrication_matrix
enrich=s41.enrich
