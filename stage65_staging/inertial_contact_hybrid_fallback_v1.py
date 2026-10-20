"""Stage53 normally; recovery SOR with authoritative Stage53 fallback."""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage41_staging"),str(ROOT/"stage42_staging"),str(ROOT/"stage53_staging"),str(ROOT/"stage63_staging")]
import inertial_contact_cold_optimized_v1 as s41
import inertial_contact_robust_v1 as s42
import inertial_contact_multistart_lm_v1 as s53
import inertial_contact_projected_sor_v1 as s63

base=s42.base; generalized_mass_matrix=s42.generalized_mass_matrix; stokes_generalized_resistance=s42.stokes_generalized_resistance
contact_model=s42.contact_model; finite_re=s42.finite_re; contact_solve=s42.contact_solve
_recovery=False
_stats={"stage53_calls":0,"recovery_sor_calls":0,"recovery_sor_failures":0,"recovery_stage53_fallbacks":0}
def set_recovery_mode(value):
    global _recovery
    _recovery=bool(value)
def recovery_mode(): return _recovery
def stats(): return dict(_stats)


def _solve(*args,**kwargs):
    if not _recovery:
        _stats["stage53_calls"]+=1
        return s53._solve(*args,**kwargs)
    try:
        answer=s63._solve(*args,**kwargs); _stats["recovery_sor_calls"]+=1; return answer
    except RuntimeError:
        _stats["recovery_sor_failures"]+=1
        answer=s53._solve(*args,**kwargs)
        _stats["recovery_stage53_fallbacks"]+=1
        return answer


def inertial_contact_step(*args,**kwargs):
    original=s41._solve_prepared; s41._solve_prepared=_solve
    try: return s42.inertial_contact_step(*args,**kwargs)
    finally: s41._solve_prepared=original
