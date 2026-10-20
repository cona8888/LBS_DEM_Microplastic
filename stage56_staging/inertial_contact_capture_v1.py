"""Stage53 solver with fail-closed capture of the first rejected contact system."""
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage41_staging"), str(ROOT / "stage42_staging"), str(ROOT / "stage53_staging")]
import inertial_contact_cold_optimized_v1 as s41
import inertial_contact_robust_v1 as s42
import inertial_contact_multistart_lm_v1 as s53

base = s42.base
generalized_mass_matrix = s42.generalized_mass_matrix
stokes_generalized_resistance = s42.stokes_generalized_resistance
contact_model = s42.contact_model
finite_re = s42.finite_re
contact_solve = s42.contact_solve
stats = s53.stats


def _capture(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter, reason):
    target = os.environ.get("STAGE56_CAPTURE_DIR")
    if not target:
        return
    folder = Path(target)
    folder.mkdir(parents=True, exist_ok=True)
    marker = folder / "failure_state.npz"
    if marker.exists():
        return
    temporary = folder / "failure_state.tmp.npz"
    np.savez_compressed(
        temporary,
        vfree=np.asarray(vfree),
        mobility=np.asarray(mobility),
        jacobian=np.asarray(jacobian),
        gaps=np.asarray(gaps),
        dt=np.asarray(float(dt)),
        friction=np.asarray(float(friction)),
        tol=np.asarray(float(tol)),
        maxiter=np.asarray(int(maxiter)),
    )
    temporary.replace(marker)
    metadata = {
        "status": "captured_rejected_contact_system",
        "reason": str(reason),
        "contacts": int(len(gaps)),
        "dt_s": float(dt),
        "friction_coefficient": float(friction),
        "tolerance": float(tol),
        "max_iterations": int(maxiter),
    }
    (folder / "failure_state.json").write_text(json.dumps(metadata, indent=2))


def _solve(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
    try:
        return s53._solve(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter)
    except RuntimeError as exc:
        _capture(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter, exc)
        raise


def inertial_contact_step(*args, **kwargs):
    original = s41._solve_prepared
    s41._solve_prepared = _solve
    try:
        return s42.inertial_contact_step(*args, **kwargs)
    finally:
        s41._solve_prepared = original
