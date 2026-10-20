"""Experimental short PGS seed for default two-contact LM solves.

Use the existing Stage50 equations, tolerance and physical acceptance gates.
Only the nonlinear initialization schedule changes: at most 64 PGS sweeps
before seeded LM for two contacts outside recovery mode. Any failure falls
back to unchanged Stage53. No reaction or history crosses a pose boundary.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage50_staging"), str(ROOT / "stage53_staging"),
                str(ROOT / "stage70_staging"), str(ROOT / "stage81_staging")]
import inertial_contact_seeded_lm_v1 as stage50
import inertial_contact_multistart_lm_v1 as stage53
import inertial_contact_runtime_portfolio_v1 as portfolio
import trajectory_combined_scalar_v1 as parent

PGS_SEED_SWEEPS = 64
_original_solve = stage53._solve
_stats = {"attempts": 0, "accepted": 0, "fallbacks": 0}


def stats():
    return dict(_stats)


def solve(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
    if len(gaps) == 2 and not portfolio.recovery_mode():
        _stats["attempts"] += 1
        try:
            result = stage50._solve(vfree, mobility, jacobian, gaps, dt,
                                    friction, tol, min(maxiter, PGS_SEED_SWEEPS))
        except (RuntimeError, ValueError, FloatingPointError,
                np.linalg.LinAlgError, OverflowError):
            _stats["fallbacks"] += 1
        else:
            _stats["accepted"] += 1
            return result
    return _original_solve(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter)


def integrate(*args, **kwargs):
    original = stage53._solve
    before = stats()
    stage53._solve = solve
    try:
        result = parent.integrate(*args, **kwargs)
    finally:
        stage53._solve = original
    after = stats()
    result["short_pgs_seed_stats"] = {key: after[key]-before[key] for key in before}
    result["short_pgs_seed_sweeps"] = PGS_SEED_SWEEPS
    return result


lubrication_matrix = parent.lubrication_matrix
enrich = parent.enrich
