"""Stage146: restore the rotational block of the generalized mass matrix, exactly.

`checkpoint_core_v3.integrate` builds the full generalized mass matrix with
`inertial.generalized_mass_matrix(...)` and then executes

    mass[3:, 3:] = 0.0

so the rotational rows of the step are algebraic: orientation is quasi-static
while translation is not.  Stage146 measures what that removes and whether the
Stage141 contact bifurcation survives its restoration.

RECONSTRUCTION WITHOUT THE SAND GEOMETRY
----------------------------------------
A frozen system records only `(vfree, M, J, g, dt, mu)`, where

    B = M^-1 = mass/dt + drag + lubrication        (with mass[3:,3:] = 0)
    M @ (mass @ q_old/dt + drag @ background + body_load) = vfree

The right-hand side is therefore recoverable as `rhs = B @ vfree` without knowing
drag, lubrication or the grain positions.  Restoring the rotational mass adds a
known block to B and a known term to rhs:

    B'   = B + blkdiag(0, I_gen/dt)
    rhs' = rhs + [0, I_gen @ q_old[3:]/dt]
    M'   = inv(B'),      vfree' = M' @ rhs'

`I_gen` comes from the project's own `generalized_mass_matrix` at the recorded
pose, so nothing is invented.  The contact Jacobian, gaps, dt and friction are
untouched, which makes the with/without comparison a controlled one.

VALIDATION
----------
The reconstruction is only trustworthy if the recorded systems really do have a
zeroed rotational mass.  That is checkable: with `mass[3:,3:] = 0` the rotational
block of B must be exactly `stokes_rot + lubrication_rot`, so

    B[3:,3:] - stokes_generalized_resistance(p, a, b, mu)[3:,3:]

must be symmetric positive semi-definite (a sum of `coefficient * outer(n, n)`
lubrication terms, hence typically rank deficient).  If that fails, the assumed
pose or material constants are wrong and the stage refuses to proceed.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage38_staging"), str(ROOT / "stage39_staging"),
                str(ROOT / "stage41_staging")]
import inertial_contact_cold_optimized_v1 as stage41


def generalized_mass(p, a, b, particle_density, fluid_density, added_mass_fraction):
    """The project's own generalized mass matrix, unmodified."""
    mass, _ = stage41.generalized_mass_matrix(np.asarray(p, float), a, b,
                                              particle_density, fluid_density, added_mass_fraction)
    return np.asarray(mass, float)


def stokes_resistance(p, a, b, viscosity):
    return np.asarray(stage41.stokes_generalized_resistance(np.asarray(p, float), a, b, viscosity), float)


def validate_zeroed_rotational_mass(system, p, a, b, viscosity, tolerance=1e-9):
    """Confirm the recorded system has mass[3:,3:] = 0, via the lubrication residue."""
    B = np.linalg.inv(np.asarray(system["mobility"], float))
    residue = B[3:, 3:] - stokes_resistance(p, a, b, viscosity)[3:, 3:]
    symmetric = 0.5 * (residue + residue.T)
    asymmetry = float(np.linalg.norm(residue - symmetric) / max(np.linalg.norm(residue), 1e-300))
    eigenvalues = np.linalg.eigvalsh(symmetric)
    scale = max(float(np.linalg.norm(symmetric)), 1e-300)
    return {"lubrication_residue_eigenvalues": eigenvalues.tolist(),
            "most_negative_eigenvalue_over_norm": float(eigenvalues.min() / scale),
            "asymmetry": asymmetry,
            "rank": int(np.sum(eigenvalues > 1e-10 * max(eigenvalues.max(), 1e-300))),
            "passed": bool(eigenvalues.min() >= -tolerance * scale and asymmetry <= 1e-9)}


def scale_audit(system, p, a, b, viscosity, particle_density, fluid_density, added_mass_fraction):
    """How large is the discarded rotational term compared with what is kept?"""
    B = np.linalg.inv(np.asarray(system["mobility"], float))
    dt = float(system["dt"])
    mass = generalized_mass(p, a, b, particle_density, fluid_density, added_mass_fraction)
    rot, trans = mass[3:, 3:], mass[:3, :3]
    kept_rot = float(np.linalg.norm(B[3:, 3:]))          # drag + lubrication: all the solver sees
    kept_trans = float(np.linalg.norm(B[:3, :3]))
    return {"dt_s": dt,
            "discarded_rotational_over_kept": float(np.linalg.norm(rot) / dt / kept_rot),
            "retained_translational_over_kept": float(np.linalg.norm(trans) / dt / kept_trans),
            "rotational_norm": float(np.linalg.norm(rot)),
            "rotational_block_norm_kept": kept_rot,
            "crossover_dt_s": float(np.linalg.norm(rot) / kept_rot),
            "stokes_rotational_norm": float(np.linalg.norm(stokes_resistance(p, a, b, viscosity)[3:, 3:]))}


def restore(system, p, q_old, a, b, viscosity, particle_density, fluid_density, added_mass_fraction):
    """Return the same contact system with the rotational mass block restored."""
    M = np.asarray(system["mobility"], float)
    vfree = np.asarray(system["vfree"], float)
    dt = float(system["dt"])
    q_old = np.asarray(q_old, float)
    B = np.linalg.inv(M)
    rhs = B @ vfree
    inertia = generalized_mass(p, a, b, particle_density, fluid_density, added_mass_fraction)[3:, 3:]
    B_new = B.copy()
    B_new[3:, 3:] += inertia / dt
    B_new = 0.5 * (B_new + B_new.T)
    rhs_new = rhs.copy()
    rhs_new[3:] += inertia @ q_old[3:] / dt
    M_new = np.linalg.inv(B_new)
    M_new = 0.5 * (M_new + M_new.T)
    out = dict(system)
    out["mobility"] = M_new
    out["vfree"] = M_new @ rhs_new
    out["id"] = str(system["id"]) + "_with_rotational_inertia"
    return out, {"inertia_block": inertia.tolist(),
                 "free_velocity_change_over_scale":
                     float(np.linalg.norm(out["vfree"] - vfree) / max(np.linalg.norm(vfree), 1e-15)),
                 "mobility_relative_change": float(np.linalg.norm(M_new - M) / np.linalg.norm(M)),
                 "restored_block_is_exact":
                     bool(np.allclose(np.linalg.inv(M_new) - B, np.block([[np.zeros((3, 3)), np.zeros((3, 3))],
                                                                         [np.zeros((3, 3)), inertia / dt]]),
                                      rtol=1e-8, atol=1e-8 * np.linalg.norm(inertia) / dt))}


def rotational_relaxation_error(p, a, b, viscosity, particle_density, fluid_density,
                                added_mass_fraction, dt, steps=64):
    """Free rotational relaxation: exact vs backward Euler with and without inertia.

    With no torque and no contact the rotational equation is  I w' = -C w,  whose
    exact solution decays with the eigen-times of C^-1 I.  Backward Euler with the
    inertia retained gives  w_{n+1} = (I/dt + C)^-1 (I/dt) w_n.  With I = 0 the same
    step gives w_{n+1} = 0: the angular velocity is annihilated in a single step,
    so the quasi-static model carries no rotational memory at all.
    """
    inertia = generalized_mass(p, a, b, particle_density, fluid_density, added_mass_fraction)[3:, 3:]
    drag = stokes_resistance(p, a, b, viscosity)[3:, 3:]
    times = np.linalg.eigvalsh(np.linalg.solve(drag, inertia))
    w0 = np.array([1.0, 0.0, 0.0])
    step = np.linalg.solve(inertia / dt + drag, inertia / dt)
    rows = []
    w = w0.copy()
    for n in range(1, steps + 1):
        w = step @ w
        rows.append({"step": n, "time_s": n * dt, "euler_with_inertia": float(np.linalg.norm(w))})
    # exact decay: expm(-I^-1 C t) w0, via the eigen-decomposition of I^-1 C
    A = np.linalg.solve(inertia, drag)
    values, vectors = np.linalg.eig(A)
    coefficients = np.linalg.solve(vectors, w0)
    for row in rows:
        t = row["time_s"]
        exact = vectors @ (np.exp(-values * t) * coefficients)
        row["exact"] = float(np.linalg.norm(exact.real))
        row["quasi_static"] = 0.0                       # annihilated at the first step
        row["euler_error"] = abs(row["euler_with_inertia"] - row["exact"]) / max(row["exact"], 1e-300)
        row["quasi_static_error"] = 1.0                 # relative to the exact remaining spin
    return {"relaxation_times_s": np.sort(times).tolist(),
            "dt_s": dt, "steps_per_relaxation_time": float(np.min(times) / dt),
            "rows": rows}
