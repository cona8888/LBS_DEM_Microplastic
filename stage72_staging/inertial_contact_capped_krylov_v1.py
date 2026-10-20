"""Stage70 recovery with a bounded Krylov search before unchanged fallbacks.

Only the maximum search iterations change (1000 -> 250). The contact equations,
Stage50 acceptance gates, projected-SOR fallback, and Stage53 default remain
unchanged. This module is single-threaded because it temporarily scopes a
Python function binding during a solve.
"""
import sys
from pathlib import Path

from scipy.optimize import root as scipy_root

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage70_staging"))
import inertial_contact_runtime_portfolio_v1 as parent

base = parent.base
generalized_mass_matrix = parent.generalized_mass_matrix
stokes_generalized_resistance = parent.stokes_generalized_resistance
contact_model = parent.contact_model
finite_re = parent.finite_re
contact_solve = parent.contact_solve
stats = parent.stats
set_recovery_mode = parent.set_recovery_mode
recovery_mode = parent.recovery_mode

KRYLOV_ITERATION_CAP = 250


def _capped_root(fun, x0, method, options):
    bounded = dict(options)
    if method == "krylov":
        bounded["maxiter"] = min(bounded["maxiter"], KRYLOV_ITERATION_CAP)
    return scipy_root(fun, x0, method=method, options=bounded)


def _solve(*args, **kwargs):
    original = parent.root
    parent.root = _capped_root
    try:
        return parent._solve(*args, **kwargs)
    finally:
        parent.root = original


def inertial_contact_step(*args, **kwargs):
    original = parent.root
    parent.root = _capped_root
    try:
        return parent.inertial_contact_step(*args, **kwargs)
    finally:
        parent.root = original
