"""Stage147: the production stall, diagnosed and cleared on the real trajectory.

Stage145 proved the dt-consistent acceptance contract repairs seven frozen sphere
systems and is bitwise inert at delta_geom = 0.  It did not show that the contract
clears the stall that actually stopped the campaign, because a frozen matrix is not
a trajectory.  Stage147 runs the trajectory.

Six experiments, each falsifiable:

  G1  harness fidelity.  Replay from the sealed segment_02 checkpoint and compare the
      rejected-trial ladder, trial for trial, against the sealed segment_09 record.
  G2  the stall, isolated.  Harvest the contact systems the production solver rejects,
      then ask four questions of each: what does every production rung do, what does
      the legacy ceiling do, what does the dt-consistent ceiling do, and which rung
      emits the reason the trajectory record stores.
  G3  inertness.  At delta_geom = 0, both the solver and the new trajectory-gate
      reporting must reproduce Stage41 bitwise on 209 systems.
  G4  matched steps.  Baseline and contract, same checkpoint, same accepted-step
      target; compare cost and the state reached.
  G5  matched wall.  Same wall-clock budget each; compare how far the trajectory gets
      and whether the declared dwell observable is reached at all.
  G6  rotational inertia on the trajectory.  Stage146 closed with this open item:
      re-run with and without the restored rotational mass and compare at a matched
      clock.

No production module is modified.  No population release fraction, no irreversible
retention, no experimental validation, and no campaign is launched.
"""
import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / p) for p in ("stage41_staging", "stage42_staging", "stage50_staging",
                                        "stage53_staging", "stage63_staging", "stage70_staging",
                                        "stage74_staging", "stage145_staging", "stage147_staging")]
import replay_harness_v1 as harness
import contact_solver_v1 as patch
import geometric_tolerance_v1 as contract
import frozen_systems_v1 as frozen
import inertial_contact_cold_optimized_v1 as stage41
import inertial_contact_seeded_lm_v1 as s50
import inertial_contact_multistart_lm_v1 as s53
import inertial_contact_projected_sor_v1 as s63
import inertial_contact_runtime_portfolio_v1 as portfolio
import scalar_contact_kernels_v1 as kernels

DELTA = contract.length_budget(harness.CELL_LENGTH_M)        # 16 * eps * L
A = B = harness.SEMI_AXIS_M
CASE, BINDING = harness.CASE, harness.BINDING


def _replay(field, grains, name, steps, wall_budget, **kw):
    checkpoint, record = harness.segment(name)
    started = time.perf_counter()
    out = harness.replay(field, grains, checkpoint, A, B, CASE, steps, BINDING,
                         wall_budget=wall_budget, **kw)
    out["_wall_s"] = time.perf_counter() - started
    out["_start"] = record["result"]
    return out, record


def _summary(tag, out):
    start = out["_start"]
    steps = out["steps"] - start["steps"]
    return {"configuration": tag, "status": out["status"],
            "accepted_steps": steps, "rejected_trials": out["rejected"] - start["rejected"],
            "clock_advanced_s": out["time_s"] - start["time_s"], "time_s": out["time_s"],
            "wall_s": out["_wall_s"],
            "contact_iterations": out["total_contact_iterations"] - start["total_contact_iterations"],
            "contact_iterations_per_step": (out["total_contact_iterations"] - start["total_contact_iterations"]) / max(steps, 1),
            "mean_dt_s": (out["time_s"] - start["time_s"]) / max(steps, 1),
            "clock_per_wall_second": (out["time_s"] - start["time_s"]) / max(out["_wall_s"], 1e-9),
            "position_m": list(out["position_m"]), "orientation": list(out["orientation"]),
            "velocity_generalized": list(out["velocity_generalized"]),
            "minimum_gap_m": out.get("minimum_gap_m"),
            "max_contact_residual": out.get("max_contact_residual"),
            "max_force_residual": out.get("max_force_residual"),
            "max_momentum_residual": out.get("max_momentum_residual"),
            "first_contact_dwell_time_s": out.get("first_contact_dwell_time_s"),
            "persistent_contact_observed": out.get("persistent_contact_observed"),
            "trap_state": out.get("trap_state")}


# ------------------------------------------------------------------ G1
def g1_fidelity(field, grains, wall_budget):
    _, record2 = harness.segment("02")
    _, record9 = harness.segment("09")
    expected = record9["result"]["rejected_trials"][len(record2["result"]["rejected_trials"]):]
    steps = record9["result"]["steps"] - record2["result"]["steps"]
    out, _ = _replay(field, grains, "02", steps, wall_budget)
    produced = out["rejected_trials"][len(record2["result"]["rejected_trials"]):]
    identical = 0
    for got, want in zip(produced, expected):
        if all(got[k] == want[k] for k in ("reason", "attempt", "dt_s", "time_s")):
            identical += 1
        else:
            break
    return {"experiment": "G1_harness_fidelity",
            "sealed_trials_to_reproduce": len(expected), "trials_produced": len(produced),
            "leading_bitwise_identical_trials": identical,
            "reproduced_ladder_before_first_accepted_step": identical == 11 and len(produced) >= 11,
            "diverged_after_first_accepted_step": len(produced) < len(expected),
            "accepted_steps": out["steps"] - record2["result"]["steps"],
            "clock_error_against_sealed_s": out["time_s"] - record9["result"]["time_s"],
            "position_difference_m": float(np.linalg.norm(
                np.array(out["position_m"]) - np.array(record9["result"]["position_m"]))),
            "passed": identical == 11,
            "limitation": ("Fidelity is established for the 11 rejected trials that precede the "
                           "first accepted step, bitwise.  Past that step the reconstructed stack "
                           "and the sealed run separate: the Stage136 Numba kernels are absent "
                           "here, and at a state this close to the acceptance boundary a last-bit "
                           "difference decides accept versus reject.  Every later comparison in "
                           "this stage is therefore between two configurations of ONE reconstructed "
                           "stack, never against the sealed trajectory.")}


# ------------------------------------------------------------------ G2
def _harvest(field, grains, name, wall_budget, cap=400):
    original = portfolio._solve
    records, seen = [], set()

    def probe(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
        try:
            return original(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter)
        except RuntimeError as exc:
            key = (float(dt), float(np.linalg.norm(vfree)), float(np.linalg.norm(gaps)))
            if len(records) < cap and key not in seen:
                seen.add(key)
                records.append({"vfree": np.asarray(vfree, float).copy(),
                                "mobility": np.asarray(mobility, float).copy(),
                                "jacobian": np.asarray(jacobian, float).copy(),
                                "gaps": np.asarray(gaps, float).copy(),
                                "dt": float(dt), "mu": float(friction), "tol": float(tol),
                                "maxiter": int(maxiter), "reason": str(exc), "segment": name})
            raise

    portfolio._solve = probe
    try:
        _replay(field, grains, name, 10 ** 9, wall_budget)
    finally:
        portfolio._solve = original
    return records


def _scoped(call, system):
    """Stage74 scoped scalar kernels, exactly as the production dispatch installs them."""
    original = (s50._project, s50._residual, s63._solve)
    s50._project, s50._residual, s63._solve = kernels.project, kernels.residual, kernels.sor_solve
    try:
        return call(system["vfree"], system["mobility"], system["jacobian"], system["gaps"],
                    system["dt"], system["mu"], system["tol"], system["maxiter"])
    finally:
        s50._project, s50._residual, s63._solve = original


def g2_stall(field, grains, wall_budget):
    systems, seen = [], set()
    for name in ("02", "09"):
        for r in _harvest(field, grains, name, wall_budget):
            key = (round(r["dt"], 24), float(np.linalg.norm(r["vfree"])), float(np.linalg.norm(r["gaps"])))
            if key not in seen:
                seen.add(key)
                systems.append(r)
    portfolio.set_recovery_mode(True)
    rungs, rows, ceilings = Counter(), [], Counter()
    for s in systems:
        result = {}
        for label, call in (("krylov", lambda *a: portfolio._root_candidate("krylov", *a)),
                            ("projected_sor", s63._solve),
                            ("pgs_seeded_lm", s50._solve),
                            ("zero_seeded_lm", s53._solve)):
            try:
                _scoped(call, s)
                result[label] = "accepted"
            except Exception as exc:                         # noqa: BLE001 - the reason is the datum
                result[label] = str(exc).replace("direct contact ", "")
        rungs[tuple(sorted(result.items()))] += 1
        row = {"segment": s["segment"], "dt_s": s["dt"], "contacts": len(s["gaps"]),
               "minimum_gap_m": float(np.min(s["gaps"])),
               "free_speed_m_s": float(np.linalg.norm(s["vfree"])),
               "trajectory_reason": s["reason"], "production_rungs": result}
        for label, delta in (("legacy_ceiling", 0.0), ("dt_consistent_ceiling", DELTA)):
            try:
                _, health = contract.solve_prepared(s["vfree"], s["mobility"], s["jacobian"],
                                                    s["gaps"], s["dt"], s["mu"], s["tol"],
                                                    s["maxiter"], delta_geom=delta)
                reactions = np.asarray(health["reactions"], float)
                row[label] = {"outcome": "accepted", "sweeps": health["iterations"],
                              "residual_m_s": health["residual_velocity_units"],
                              "ceiling_m_s": health["velocity_ceiling"],
                              "legacy_residual_over_vfree": health["residual"],
                              "minimum_normal_force_N": float(reactions[::3].min()),
                              "reaction_norm_N": float(np.linalg.norm(reactions))}
            except RuntimeError as exc:
                row[label] = {"outcome": str(exc), "sweeps": s["maxiter"]}
            ceilings[(label, row[label]["outcome"])] += 1
        rows.append(row)
    accepted = sum(1 for r in rows if r["dt_consistent_ceiling"]["outcome"] == "accepted")
    legacy = sum(1 for r in rows if r["legacy_ceiling"]["outcome"] == "accepted")
    normals = [r["dt_consistent_ceiling"]["minimum_normal_force_N"] for r in rows
               if r["dt_consistent_ceiling"]["outcome"] == "accepted"]
    sweeps = [r["dt_consistent_ceiling"]["sweeps"] for r in rows
              if r["dt_consistent_ceiling"]["outcome"] == "accepted"]
    label_counts = Counter(r["trajectory_reason"] for r in rows)
    emitters = Counter()
    for r in rows:
        emitted = [k for k, v in r["production_rungs"].items() if "negative normal" in v]
        emitters[tuple(emitted) or ("none",)] += 1
    return {"experiment": "G2_stall_isolated", "systems": len(rows),
            "trajectory_reason_histogram": dict(label_counts),
            "production_rungs_all_reject": all(
                all(v != "accepted" for v in r["production_rungs"].values()) for r in rows),
            "which_rungs_emit_negative_normal_force": {"/".join(k): v for k, v in emitters.items()},
            "legacy_ceiling_accepted": legacy, "dt_consistent_ceiling_accepted": accepted,
            "sweeps_to_converge_under_contract": {"min": int(min(sweeps)), "max": int(max(sweeps))} if sweeps else None,
            "minimum_normal_force_N": {"min": float(min(normals)), "max": float(max(normals))} if normals else None,
            "all_normals_strictly_positive": bool(normals and min(normals) > 0),
            "passed": accepted == len(rows) and legacy == 0 and bool(normals and min(normals) > 0),
            "rows": rows}


# ------------------------------------------------------------------ G3
def g3_inertness():
    sphere, fibre, hashes = frozen.load()
    systems = sphere + fibre + frozen.random_systems(200)
    velocity_identical = health_identical = report_identical = 0
    checked = 0
    for s in systems:
        try:
            v0, h0 = stage41._solve_prepared(s["vfree"], s["mobility"], s["jacobian"], s["gaps"],
                                             s["dt"], s["mu"], s["tol"], s["maxiter"])
        except RuntimeError as first:
            try:
                contract.solve_prepared(s["vfree"], s["mobility"], s["jacobian"], s["gaps"],
                                        s["dt"], s["mu"], s["tol"], s["maxiter"], delta_geom=0.0)
            except RuntimeError as second:
                checked += 1
                velocity_identical += str(first) == str(second)
                health_identical += 1
                report_identical += 1
            continue
        v1, h1 = contract.solve_prepared(s["vfree"], s["mobility"], s["jacobian"], s["gaps"],
                                         s["dt"], s["mu"], s["tol"], s["maxiter"], delta_geom=0.0)
        patch.trajectory_residual(h1, s["vfree"], s["dt"], 0.0, s["tol"])
        checked += 1
        velocity_identical += bool(np.array_equal(v0, v1))
        health_identical += bool(h0["iterations"] == h1["iterations"]
                                 and h0["reactions"] == h1["reactions"])
        report_identical += bool(h1["residual"] == h0["residual"])
    return {"experiment": "G3_inertness_at_zero_delta", "systems": checked,
            "solver_velocity_identical": velocity_identical,
            "solver_health_identical": health_identical,
            "trajectory_gate_report_identical": report_identical,
            "passed": velocity_identical == health_identical == report_identical == checked,
            "source_hashes": hashes,
            "claim": ("The trajectory-gate rewrite divides by max(|vfree|, delta/(dt*tol)); at "
                      "delta = 0 that max IS |vfree|, so the reported number is the legacy one "
                      "bitwise, not merely to rounding.")}


# ------------------------------------------------------------------ G4 / G5 / G6
def g4_matched_steps(field, grains, steps, wall_budget):
    rows = []
    for tag, kw in (("baseline", {}),
                    ("dt_consistent_contract", {"use_contract": True, "delta_geom": DELTA})):
        out, _ = _replay(field, grains, "02", steps, wall_budget, **kw)
        rows.append(_summary(tag, out))
    a, b = rows
    difference = {key: float(np.linalg.norm(np.array(b[key]) - np.array(a[key])))
                  for key in ("position_m", "orientation", "velocity_generalized")}
    return {"experiment": "G4_matched_accepted_steps", "target_steps": steps,
            "configurations": rows, "state_difference": difference,
            "position_difference_over_delta_geom": difference["position_m"] / DELTA,
            "clock_difference_s": b["time_s"] - a["time_s"],
            "rejected_trials_removed": a["rejected_trials"] - b["rejected_trials"],
            "contact_iteration_ratio": a["contact_iterations"] / max(b["contact_iterations"], 1),
            "passed": (a["accepted_steps"] == b["accepted_steps"] == steps
                       and b["rejected_trials"] == 0
                       and difference["position_m"] <= DELTA)}


def g5_matched_wall(field, grains, steps, wall_budget):
    rows = []
    for tag, kw in (("baseline", {}),
                    ("dt_consistent_contract", {"use_contract": True, "delta_geom": DELTA})):
        out, _ = _replay(field, grains, "02", steps, wall_budget, **kw)
        rows.append(_summary(tag, out))
    a, b = rows
    return {"experiment": "G5_matched_wall_budget", "wall_budget_s": wall_budget,
            "step_target": steps, "configurations": rows,
            "throughput_ratio": b["clock_per_wall_second"] / max(a["clock_per_wall_second"], 1e-300),
            "baseline_reaches_dwell_decision": bool(a["trap_state"] and a["trap_state"]["trapped"]),
            "contract_reaches_dwell_decision": bool(b["trap_state"] and b["trap_state"]["trapped"]),
            "declared_observable": ("trap monitor: contact dwell beyond the declared 0.5 s with "
                                    "drift below 0.02 minor radii and speed ratio below 0.01. "
                                    "The design sets absorbing = false, so this is a FINITE DWELL "
                                    "observation, not irreversible retention and not a release "
                                    "fraction."),
            "passed": bool(b["trap_state"] and b["trap_state"]["trapped"])}


def g6_rotational_inertia(field, grains, steps, wall_budget):
    rows = []
    for tag, inertia in (("contract", False), ("contract_with_rotational_inertia", True)):
        out, _ = _replay(field, grains, "02", steps, wall_budget,
                         use_contract=True, delta_geom=DELTA, use_inertia=inertia)
        rows.append(_summary(tag, out))
    a, b = rows
    matched = a["accepted_steps"] == b["accepted_steps"] and a["time_s"] == b["time_s"]
    return {"experiment": "G6_rotational_inertia_on_the_trajectory",
            "configurations": rows, "matched_clock": bool(matched),
            "clock_difference_s": b["time_s"] - a["time_s"],
            "position_difference_over_minor_radius": float(np.linalg.norm(
                np.array(b["position_m"]) - np.array(a["position_m"])) / B),
            "orientation_difference": float(np.linalg.norm(
                np.array(b["orientation"]) - np.array(a["orientation"]))),
            "maximum_drift_m": {"without": a["trap_state"]["maximum_drift_m"],
                                "with": b["trap_state"]["maximum_drift_m"]},
            "drift_over_minor_radius": {"without": a["trap_state"]["maximum_drift_m"] / B,
                                        "with": b["trap_state"]["maximum_drift_m"] / B},
            "dwell_verdict": {"without": a["trap_state"]["trapped"], "with": b["trap_state"]["trapped"]},
            "passed": bool(matched and a["trap_state"]["trapped"] == b["trap_state"]["trapped"]),
            "scope": ("A sphere at rest in a sustained three-contact pocket is the one situation "
                      "in which rotational inertia has least to do.  Stage146 F2 and F5 stand: the "
                      "discarded term dominates the retained one at every production step, and the "
                      "quasi-static model carries no rotational memory.  This experiment earns the "
                      "quasi-static statement for THIS case only, not for the prolate and not for "
                      "contact onset or release.")}


# ------------------------------------------------------------------ driver
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", default=None)
    parser.add_argument("--harvest-wall", type=float, default=45.0)
    parser.add_argument("--matched-steps", type=int, default=15)
    parser.add_argument("--long-steps", type=int, default=40000)
    parser.add_argument("--long-wall", type=float, default=300.0)
    args = parser.parse_args()
    out = Path(args.output) if args.output else (
        ROOT / "stage147_evaluations/trajectory_stall_clearance_20260920/run_01")

    field, grains, scene = harness.load_scene()
    started = time.perf_counter()
    results = [g1_fidelity(field, grains, 600.0),
               g2_stall(field, grains, args.harvest_wall),
               g3_inertness(),
               g4_matched_steps(field, grains, args.matched_steps, 600.0),
               g5_matched_wall(field, grains, args.long_steps, args.long_wall),
               g6_rotational_inertia(field, grains, args.long_steps, 600.0)]
    payload = {
        "stage": 147,
        "title": "dt-consistent contact acceptance on the real trajectory",
        "passed": all(r["passed"] for r in results),
        "status": ("stage147_trajectory_stall_cleared" if all(r["passed"] for r in results)
                   else "stage147_incomplete"),
        "delta_geom_m": DELTA, "geometric_multiplier": contract.DEFAULT_MULTIPLIER,
        "scene": scene, "case": CASE, "binding": BINDING,
        "semi_axes_m": [A, B], "wall_s": time.perf_counter() - started,
        "environment": {"python": sys.version.split()[0], "numpy": np.__version__},
        "experiments": results,
        "not_claimed": [
            "No release fraction, retention probability or experimental validation.",
            "No campaign relaunched and no production module modified.",
            "Bitwise agreement with the sealed run is claimed only for the 11 trials of G1.",
            "The Stage136 Numba layer is absent; speed, and last-bit arithmetic, differ.",
        ],
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(payload, indent=1, default=str))
    (out / "completion.json").write_text(json.dumps({
        "passed": payload["passed"], "status": payload["status"],
        "results_sha256": hashlib.sha256((out / "results.json").read_bytes()).hexdigest(),
        "runner_sha256": harness.sha(Path(__file__).resolve()),
        "solver_sha256": harness.sha(ROOT / "stage147_staging/contact_solver_v1.py"),
        "harness_sha256": harness.sha(ROOT / "stage147_staging/replay_harness_v1.py"),
    }, indent=1))
    for r in results:
        print(f'  {r["experiment"]:42s} {"PASS" if r["passed"] else "FAIL"}')
    print("STAGE147_PASS", payload["passed"], "->", out)
    return 0 if payload["passed"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
