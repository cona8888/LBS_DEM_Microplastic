"""Sequential Stage48 trajectory entry point with direct-fallback accounting."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage41_staging"),str(ROOT/"stage48_staging")]
import trajectory_optimized_v1 as stage41
import inertial_contact_direct_fallback_v1 as contact
def integrate(*args,**kwargs):
    original=stage41.inertial; before=contact.stats(); stage41.inertial=contact
    try: result=stage41.integrate(*args,**kwargs)
    finally: stage41.inertial=original
    after=contact.stats(); result["direct_fallback_stats"]={key:after[key]-before[key] for key in after}; return result
lubrication_matrix=stage41.lubrication_matrix
enrich=stage41.enrich
