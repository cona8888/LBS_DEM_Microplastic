"""Stage146: is the quasi-static rotation approximation earned?

`checkpoint_core_v3` retains the translational mass and sets `mass[3:,3:] = 0`.
Stage145 established that 96.6 % of the difference between the two admissible
branches at the Stage141 fibre state is rotational, i.e. the bifurcation lives
almost entirely in the block that has been zeroed.  This stage asks whether that
zeroing is a small approximation, and whether the bifurcation survives undoing it.

Read-only with respect to every prior stage.  No trajectory is dispatched, no
geometry recomputed, no campaign launched, no release result claimed.

  F1  RECONSTRUCTION VALIDITY.  With mass[3:,3:] = 0 the rotational block of
      B = M^-1 must be exactly stokes_rot + lubrication_rot, so B_rot - stokes_rot
      must be symmetric positive semi-definite.  Checking it on every frozen
      system simultaneously confirms the records really are quasi-static in
      rotation and validates the pose and material constants used here.  Nothing
      downstream is believable without it.

  F2  SCALE AUDIT.  Compare the DISCARDED rotational term ||I_gen/dt|| with the
      rotational block the solver actually sees, and the RETAINED translational
      term ||m/dt|| with its own.  Also report the crossover step below which the
      discarded term exceeds the retained one.

  F3  FIBRE BRANCHES WITH INERTIA RESTORED.  Rebuild both Stage141 systems with
      the rotational mass put back and re-run the complete enumeration.  Does the
      bifurcation persist, and does the branch separation change?

  F4  SPHERE CONTROL.  The same restoration on the seven Stage142 sphere systems,
      which should remain single-branch and static: a change there would indicate
      the reconstruction, not the physics.

  F5  ROTATIONAL RELAXATION.  Free spin decay, exact versus backward Euler with
      and without the inertia.  Quantifies the approximation directly rather than
      by a Stokes-number argument.
"""
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage38_staging"), str(ROOT / "stage39_staging"),
                str(ROOT / "stage41_staging"), str(ROOT / "stage145_staging"),
                str(ROOT / "stage146_staging")]
import inertial_contact_cold_optimized_v1 as stage41
import geometric_tolerance_v1 as contract
import frozen_systems_v1 as frozen
import branch_enumeration_v1 as branches
import rotational_inertia_v1 as rotation

BASE = "rotational_inertia_20260920"
LABEL = sys.argv[1] if len(sys.argv) > 1 else "run_01"
OUT = ROOT / "stage146_evaluations" / BASE / LABEL

# From stage139_designs/sphere_only_sticking_verification_20260918/design_01.json,
# the frozen spec every one of these systems was produced under.
CONFIG = {"prolate_semiaxes_m": (2.0e-4, 5.0e-5), "sphere_radius_m": 7.9370e-5,
          "particle_density_kg_m3": 1380.0, "fluid_density_kg_m3": 998.2,
          "dynamic_viscosity_Pa_s": 0.001002, "added_mass_fraction": 1.0,
          "max_dt_s": 0.000625, "dwell_time_s": 0.5}
DESIGN = ROOT / "stage139_designs/sphere_only_sticking_verification_20260918/design_01.json"

# Poses and incoming velocities of the frozen systems, from the sealed records they
# were assembled at.  The fibre pair comes from the Stage141 checkpoint state; the
# sphere systems from the source records the Stage142 probe names in each row.
SPHERE_SOURCES = {
    "initial": ROOT / "stage136_runs/compiled_contact_continuation_20260918/continuation_01/sphere_12/segment_04/record.json",
    "endpoint_02": ROOT / "stage140_runs/sphere_finite_dwell_refinement_20260918/refinement_01/sphere_dwell_factor_1/segment_02/record.json",
    "endpoint_09": ROOT / "stage140_runs/sphere_finite_dwell_refinement_20260918/refinement_01/sphere_dwell_factor_1/segment_09/record.json",
}
FIBRE_SOURCE = ROOT / "stage141_evaluations/fibre_identical_system_branch_check_20260918/probe_01/results.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def _json(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(type(value))


def write(path, value):
    encoded = json.dumps(value, indent=2, sort_keys=True, allow_nan=True, default=_json) + "\n"
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(encoded)


def poses():
    """(pose, incoming velocity) for every frozen system, from its own sealed record."""
    out = {}
    fibre = json.loads(FIBRE_SOURCE.read_text())["result"]["checkpoint"]["state"]
    for index in (0, 1):
        out[f"fibre_identical_{index}"] = (np.array(fibre["p"], float), np.array(fibre["q"], float), "prolate")
    for key, path in SPHERE_SOURCES.items():
        record = json.loads(Path(path).read_text())["result"]
        p = np.array(record["orientation"], float)
        q = np.array(record["velocity_generalized"], float)
        if key == "initial":
            for suffix in ("normal", "half", "quarter"):
                out[f"initial_{suffix}"] = (p, q, "sphere")
        else:
            for suffix in ("remaining", "pending"):
                out[f"{key}_{suffix}"] = (p, q, "sphere")
    return out


def axes(kind):
    if kind == "sphere":
        r = CONFIG["sphere_radius_m"]
        return r, r
    return CONFIG["prolate_semiaxes_m"]


def material():
    return (CONFIG["dynamic_viscosity_Pa_s"], CONFIG["particle_density_kg_m3"],
            CONFIG["fluid_density_kg_m3"], CONFIG["added_mass_fraction"])


# ----------------------------------------------------------------- F1
def experiment_reconstruction_validity(systems, pose):
    viscosity, rho_p, rho_f, amf = material()
    rows = []
    for s in systems:
        p, q_old, kind = pose[s["id"]]
        a, b = axes(kind)
        check = rotation.validate_zeroed_rotational_mass(s, p, a, b, viscosity)
        check.update(id=s["id"], kind=kind)
        rows.append(check)
    return {"passed": all(r["passed"] for r in rows), "rows": rows,
            "meaning": "B_rot - stokes_rot is symmetric PSD on every system, so the records do have "
                       "mass[3:,3:] = 0 and the pose/material constants used here are the right ones."}


# ----------------------------------------------------------------- F2
def experiment_scale_audit(systems, pose):
    viscosity, rho_p, rho_f, amf = material()
    rows = []
    for s in systems:
        p, q_old, kind = pose[s["id"]]
        a, b = axes(kind)
        audit = rotation.scale_audit(s, p, a, b, viscosity, rho_p, rho_f, amf)
        audit.update(id=s["id"], kind=kind,
                     discarded_exceeds_retained=bool(audit["discarded_rotational_over_kept"] > 1.0),
                     dt_below_crossover=bool(s["dt"] < audit["crossover_dt_s"]),
                     max_dt_below_crossover=bool(CONFIG["max_dt_s"] < audit["crossover_dt_s"]))
        rows.append(audit)
    fibre = [r for r in rows if r["kind"] == "prolate"]
    sphere = [r for r in rows if r["kind"] == "sphere"]
    return {"rows": rows,
            "all_dt_below_crossover": all(r["dt_below_crossover"] for r in rows),
            "fibre_discarded_over_kept": [r["discarded_rotational_over_kept"] for r in fibre],
            "fibre_retained_translational_over_kept": [r["retained_translational_over_kept"] for r in fibre],
            "sphere_discarded_over_kept": [r["discarded_rotational_over_kept"] for r in sphere],
            "crossover_dt_s": {r["id"]: r["crossover_dt_s"] for r in rows},
            "passed": True,
            "meaning": "The discarded rotational term is compared with the rotational block the solver "
                       "actually assembles (drag + lubrication). A ratio above one means zeroing the "
                       "rotational mass removes the dominant term of the rotational rows."}


# ----------------------------------------------------------------- F3 / F4
def compare_branches(systems, pose, delta):
    viscosity, rho_p, rho_f, amf = material()
    rows = []
    for s in systems:
        p, q_old, kind = pose[s["id"]]
        a, b = axes(kind)
        before, _ = branches.enumerate_branches(s, delta)
        restored, info = rotation.restore(s, p, q_old, a, b, viscosity, rho_p, rho_f, amf)
        after, P_after = branches.enumerate_branches(restored, delta)
        chosen, rule = branches.select_branch(after, P_after) if after else (None, "none")
        rows.append({
            "id": s["id"], "kind": kind, "dt_s": s["dt"],
            "branches_without_inertia": len(before),
            "modes_without_inertia": [x["mode_name"] for x in before],
            "separation_without_inertia": branches.branch_spread(before),
            "branches_with_inertia": len(after),
            "modes_with_inertia": [x["mode_name"] for x in after],
            "separation_with_inertia": branches.branch_spread(after),
            "bifurcation_survives": bool(len(after) >= 2) if len(before) >= 2 else None,
            "branch_velocities_with_inertia": [{"mode": x["mode_name"],
                                                "velocity_norm": float(np.linalg.norm(x["velocity"])),
                                                "translational_norm": float(np.linalg.norm(x["velocity"][:3])),
                                                "rotational_norm": float(np.linalg.norm(x["velocity"][3:])),
                                                "residual": x["report"]["residual"]} for x in after],
            "declared_cold_selection": {"rule": rule, "mode": chosen["mode_name"] if chosen else None},
            "restoration": info,
        })
    return rows


def experiment_fibre(fibre, pose, delta):
    rows = compare_branches(fibre, pose, delta)
    for r in rows:
        if r["branches_with_inertia"] >= 2:
            a = r["branch_velocities_with_inertia"]
            spread_rot = max(abs(x["rotational_norm"] - y["rotational_norm"]) for x in a for y in a)
            spread_trans = max(abs(x["translational_norm"] - y["translational_norm"]) for x in a for y in a)
            r["rotational_share_of_separation"] = float(spread_rot / max(spread_rot + spread_trans, 1e-300))
    return {"passed": all(r["branches_without_inertia"] >= 2 for r in rows), "rows": rows}


def experiment_sphere(sphere, pose, delta):
    rows = compare_branches(sphere, pose, delta)
    ok = all(r["branches_with_inertia"] == 1 and r["modes_with_inertia"] == ["stick/stick/stick"] for r in rows)
    return {"passed": bool(ok), "rows": rows,
            "meaning": "The spheres must stay single-branch and sticking under the same restoration; "
                       "a change here would implicate the reconstruction rather than the physics."}


# ----------------------------------------------------------------- F5
def experiment_relaxation(pose):
    viscosity, rho_p, rho_f, amf = material()
    out = {}
    for kind, sid in (("prolate", "fibre_identical_0"), ("sphere", "initial_normal")):
        p, q_old, _ = pose[sid]
        a, b = axes(kind)
        dt = 4.9250836726338306e-05 if kind == "prolate" else 2.0510347749444327e-05
        data = rotation.rotational_relaxation_error(p, a, b, viscosity, rho_p, rho_f, amf, dt, steps=64)
        keep = [r for r in data["rows"] if r["step"] in (1, 2, 5, 12, 32, 64)]
        out[kind] = {"relaxation_times_s": data["relaxation_times_s"],
                     "steps_per_relaxation_time": data["steps_per_relaxation_time"],
                     "dt_s": dt,
                     "remaining_spin_fraction": [{"step": r["step"], "time_s": r["time_s"],
                                                  "exact": r["exact"],
                                                  "euler_with_inertia": r["euler_with_inertia"],
                                                  "quasi_static": r["quasi_static"]} for r in keep],
                     "dwell_windows_per_relaxation_time":
                         float(CONFIG["dwell_time_s"] / max(data["relaxation_times_s"])) }
    return {"passed": True, "per_shape": out,
            "meaning": "With the rotational mass zeroed the angular velocity is annihilated in one step: "
                       "the model carries no rotational memory. With it retained, spin decays over the "
                       "relaxation time, which spans several timesteps. The difference is a transient at "
                       "contact onset and release, not a steady-state bias."}


def main():
    sphere, fibre, source_hashes = frozen.load()
    require(len(sphere) == 7 and len(fibre) == 2, "expected seven sphere and two fibre systems")
    pose = poses()
    require(set(pose) >= {s["id"] for s in sphere + fibre}, "missing pose for some frozen system")
    delta = contract.length_budget(frozen.CELL_LENGTH_M, contract.DEFAULT_MULTIPLIER)
    OUT.mkdir(parents=True, exist_ok=False)
    sources = {str(p): sha(p) for p in [Path(__file__), Path(rotation.__file__), Path(contract.__file__),
                                        Path(frozen.__file__), Path(branches.__file__), Path(stage41.__file__)]}
    inputs = dict(source_hashes)
    inputs[str(DESIGN)] = sha(DESIGN)
    for path in SPHERE_SOURCES.values():
        inputs[str(path)] = sha(path)
    protocol = {
        "stage": "Stage146",
        "question": "Is setting mass[3:,3:] = 0 a small approximation, and does the Stage141 contact "
                    "bifurcation survive restoring the rotational inertia?",
        "method": "Rebuild each frozen system with the rotational mass block restored, exactly, from the "
                  "recorded mobility and free velocity plus the sealed pose and incoming velocity. "
                  "B' = B + blkdiag(0, I/dt), rhs' = B vfree + [0, I q_old_rot/dt]. Contact Jacobian, "
                  "gaps, dt and friction untouched. I comes from the project's own generalized_mass_matrix.",
        "physical_changes": ["rotational generalized mass restored, in the reconstructed systems only; "
                             "no production module is modified and no trajectory is re-integrated"],
        "acceptance": {"F1_reconstruction_validated_on_all_nine": True,
                       "F2_scale_audit_reported": True,
                       "F3_fibre_bifurcation_re_enumerated": True,
                       "F4_spheres_remain_single_branch_static": True,
                       "F5_relaxation_error_quantified": True},
        "claim": "Local, per-state analysis of one modelling choice. It does NOT establish that restoring "
                 "rotational inertia changes any trajectory, dwell, retention or release result: that "
                 "requires the three-level refinement named in the next actions. No campaign launched.",
        "config": CONFIG, "geometric_multiplier": contract.DEFAULT_MULTIPLIER, "delta_geom_m": delta,
        "sources": sources, "inputs": inputs,
        "environment": {"python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__,
                        "platform": platform.platform()},
        "limitations": "The reconstruction restores inertia at a frozen state; it does not propagate it. "
                       "Lubrication, drag and geometry are taken exactly as recorded.",
    }
    write(OUT / "protocol.json", protocol)

    started = time.perf_counter()
    f1 = experiment_reconstruction_validity(sphere + fibre, pose)
    print("F1 reconstruction validity:", f1["passed"], flush=True)
    require(f1["passed"], "F1 failed: the frozen systems are not what the reconstruction assumes")
    f2 = experiment_scale_audit(sphere + fibre, pose)
    print("F2 scale audit: fibre discarded/kept =", [round(x, 3) for x in f2["fibre_discarded_over_kept"]],
          " sphere =", [round(x, 3) for x in f2["sphere_discarded_over_kept"]], flush=True)
    f3 = experiment_fibre(fibre, pose, delta)
    print("F3 fibre with inertia:", [(r["branches_without_inertia"], r["branches_with_inertia"]) for r in f3["rows"]], flush=True)
    f4 = experiment_sphere(sphere, pose, delta)
    print("F4 sphere control:", f4["passed"], flush=True)
    f5 = experiment_relaxation(pose)
    print("F5 relaxation: steps per relaxation time =",
          {k: round(v["steps_per_relaxation_time"], 2) for k, v in f5["per_shape"].items()}, flush=True)

    for name, digest in sources.items():
        require(sha(name) == digest, "source drift during the run: " + name)
    passed = all(x["passed"] for x in (f1, f2, f3, f4, f5))
    result = {
        "stage": "Stage146", "label": LABEL, "passed": bool(passed),
        "wall_s": time.perf_counter() - started,
        "F1_reconstruction_validity": f1, "F2_scale_audit": f2,
        "F3_fibre_branches_with_inertia": f3, "F4_sphere_control": f4,
        "F5_rotational_relaxation": f5,
        "headline": {
            "discarded_rotational_over_kept_fibre": f2["fibre_discarded_over_kept"],
            "retained_translational_over_kept_fibre": f2["fibre_retained_translational_over_kept"],
            "discarded_rotational_over_kept_sphere": f2["sphere_discarded_over_kept"],
            "every_dt_below_crossover": f2["all_dt_below_crossover"],
            "fibre_branches_without_inertia": [r["branches_without_inertia"] for r in f3["rows"]],
            "fibre_branches_with_inertia": [r["branches_with_inertia"] for r in f3["rows"]],
            "fibre_separation_without_inertia": [r["separation_without_inertia"] for r in f3["rows"]],
            "fibre_separation_with_inertia": [r["separation_with_inertia"] for r in f3["rows"]],
            "spheres_unchanged": f4["passed"],
            "steps_per_rotational_relaxation_time":
                {k: v["steps_per_relaxation_time"] for k, v in f5["per_shape"].items()},
        },
        "not_claimed": ["that any trajectory changes", "population release fraction",
                        "irreversible retention", "experimental validation",
                        "promotion of a rotational-inertia model into production"],
        "next": ["Restore mass[3:,3:] in checkpoint_core_v3 behind an explicit flag and re-run the two "
                 "fibre cases at three timestep levels, with and without, comparing at matched clocks.",
                 "If the trajectories agree the quasi-static statement is earned and can be written down; "
                 "if they do not, the fibre claim requires the inertia.",
                 "Either way, record the per-step branch count (Stage145 E6/E7 machinery) so bifurcating "
                 "steps stay visible.",
                 "Only then resume the unchanged sphere/fibre release objective."],
        "claim": protocol["claim"], "environment": protocol["environment"],
    }
    write(OUT / "results.json", result)
    write(OUT / "completion.json", {"results_sha256": sha(OUT / "results.json"),
                                    "protocol_sha256": sha(OUT / "protocol.json")})
    print("STAGE146_PASS", passed, flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
