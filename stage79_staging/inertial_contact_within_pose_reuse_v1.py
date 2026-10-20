"""Stage70 equations with strict, frozen-pose-only inner reaction reuse.

No reaction crosses an inertial_contact_step boundary. The preceding finite-Re
inner reaction is accepted for the next inner system only after the unchanged
Stage50 normal/Coulomb/residual/force-closure/dissipation gates pass. Otherwise
the unchanged Stage70 portfolio runs from its original cold initial state.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage41_staging"), str(ROOT / "stage42_staging"),
                str(ROOT / "stage50_staging"), str(ROOT / "stage70_staging")]
import inertial_contact_cold_optimized_v1 as stage41
import inertial_contact_robust_v1 as stage42
import inertial_contact_seeded_lm_v1 as gate
import inertial_contact_runtime_portfolio_v1 as portfolio

base = portfolio.base
generalized_mass_matrix = portfolio.generalized_mass_matrix
stokes_generalized_resistance = portfolio.stokes_generalized_resistance
contact_model = portfolio.contact_model
finite_re = portfolio.finite_re
contact_solve = portfolio.contact_solve
set_recovery_mode = portfolio.set_recovery_mode
recovery_mode = portfolio.recovery_mode
stats = portfolio.stats
_stats = {"prior_checked": 0, "prior_accepted": 0,
          "prior_rejected": 0, "cold_calls": 0}


def reuse_stats():
    return dict(_stats)


def inertial_contact_step(*args, **kwargs):
    prior = None
    original = stage41._solve_prepared

    def solve(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
        nonlocal prior
        if prior is not None and len(prior) == 3 * len(gaps) and len(gaps):
            _stats["prior_checked"] += 1
            A = jacobian @ mobility @ jacobian.T
            z = jacobian @ vfree
            steps = np.array([
                np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max()
                for k in range(len(gaps))])
            try:
                answer = gate._finish(
                    vfree, mobility, jacobian, prior, z, A, gaps, dt,
                    friction, steps, 0, "within_pose_verified_prior", {})
            except (RuntimeError, ValueError, FloatingPointError,
                    np.linalg.LinAlgError):
                _stats["prior_rejected"] += 1
            else:
                _stats["prior_accepted"] += 1
                return answer
        _stats["cold_calls"] += 1
        answer = portfolio._solve(vfree, mobility, jacobian, gaps,
                                  dt, friction, tol, maxiter)
        prior = np.asarray(answer[1]["reactions"], dtype=float)
        return answer

    stage41._solve_prepared = solve
    try:
        answer = stage42.inertial_contact_step(*args, **kwargs)
        answer[1]["cache_policy"] = "strict_reuse_within_frozen_pose_only"
        return answer
    finally:
        stage41._solve_prepared = original
