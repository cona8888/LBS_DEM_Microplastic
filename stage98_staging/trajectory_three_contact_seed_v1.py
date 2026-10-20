"""Experimental 64-sweep three-contact initialization; unchanged physics gates."""
import sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stage89_staging'))
import trajectory_short_pgs_seed_v1 as prior
_stats = dict(attempts=0, accepted=0, fallbacks=0)

def solve(*args):
    if len(args[3]) == 3 and not prior.portfolio.recovery_mode():
        _stats['attempts'] += 1
        try:
            result = prior.stage50._solve(*args[:-1], min(args[-1], 64))
        except (RuntimeError, ValueError, FloatingPointError, np.linalg.LinAlgError, OverflowError):
            _stats['fallbacks'] += 1
        else:
            _stats['accepted'] += 1
            return result
    return prior.solve(*args)

def integrate(*args, **kwargs):
    original = prior.stage53._solve
    before = dict(_stats)
    prior.stage53._solve = solve
    try:
        result = prior.parent.integrate(*args, **kwargs)
    finally:
        prior.stage53._solve = original
    result['three_contact_seed_stats'] = {k: _stats[k]-before[k] for k in before}
    return result
