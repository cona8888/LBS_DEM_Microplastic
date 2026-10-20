"""Stage70 solver with scoped, algebraically identical scalar contact kernels.

Single-threaded only: module functions are temporarily rebound and restored
in finally. This isolates the experiment from immutable prior implementations.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage50_staging"), str(ROOT / "stage63_staging"),
                str(ROOT / "stage70_staging"), str(ROOT / "stage74_staging")]
import inertial_contact_seeded_lm_v1 as s50
import inertial_contact_projected_sor_v1 as s63
import inertial_contact_runtime_portfolio_v1 as parent
import scalar_contact_kernels_v1 as kernels

base = parent.base
generalized_mass_matrix = parent.generalized_mass_matrix
stokes_generalized_resistance = parent.stokes_generalized_resistance
contact_model = parent.contact_model
finite_re = parent.finite_re
contact_solve = parent.contact_solve
stats = parent.stats
set_recovery_mode = parent.set_recovery_mode
recovery_mode = parent.recovery_mode


def _scoped(call, *args, **kwargs):
    original = (s50._project, s50._residual, s63._solve)
    s50._project = kernels.project
    s50._residual = kernels.residual
    s63._solve = kernels.sor_solve
    try:
        return call(*args, **kwargs)
    finally:
        s50._project, s50._residual, s63._solve = original


def _solve(*args, **kwargs):
    return _scoped(parent._solve, *args, **kwargs)


def inertial_contact_step(*args, **kwargs):
    return _scoped(parent.inertial_contact_step, *args, **kwargs)
