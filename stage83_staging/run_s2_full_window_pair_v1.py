"""Frozen Stage81 solver on the Stage55 seed-2 full-window sphere/AR4 pair.

One-way flow through fixed sand; 0.1 PV observation and non-absorbing dwell are
unchanged. This is a single conditional pair, not a population release rate.
All raw case outputs are written once in a new directory.
"""
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage68_staging"),
                str(ROOT / "stage81_staging")]
import matrix_case_v1
import verify_short_fibre_crossing_v1 as source
import trajectory_combined_scalar_v1 as candidate

DESIGN = ROOT / "stage55_designs" / "paired_three_packing_pilot_v1.json"
OLD_DIR = ROOT / "stage55_runs" / "paired_three_packing_pilot_20260912" / "pilot_01"
GATES = [ROOT / "stage81_evaluations" / "scalar_s2_long_transfer_01",
         ROOT / "stage82_evaluations" / "fibre_cross_packing_01"]
OUT = ROOT / "stage83_runs" / "s2_full_window_pair_20260913" / "pair_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_completion(directory):
    result = directory / "results.json"
    completion = directory / "completion.json"
    c = json.loads(completion.read_text())
    if c["status"] != "complete_passed" or c["results_sha256"] != sha(result):
        raise RuntimeError(f"frozen prerequisite failed: {directory}")
    return {str(result): sha(result), str(completion): sha(completion)}


def case_checks(result, horizon, wall_budget):
    status = result["status"]
    complete_observation = (
        status == "present_at_horizon" and abs(result["time_s"] - horizon) <= 1e-12)
    exit_observed = (
        status == "full_window_exit" and 0 < result["time_s"] <= horizon)
    return {key: bool(value) for key, value in {
        "resolved_observation": complete_observation or exit_observed,
        "no_failure_or_censoring": status not in {
            "numerical_failure", "incomplete_budget", "unresolved_model", "unresolved_field"},
        "clearance": result["minimum_gap_m"] >= -5e-10,
        "contact_closure": result["max_contact_residual"] <= 1e-8,
        "force_closure": result["max_force_residual"] <= 1e-8,
        "momentum_closure": result["max_momentum_residual"] <= 1e-8,
        "reynolds_envelope": result["max_reynolds"] <= 3,
        "within_budget": result["runtime_seconds"] <= wall_budget,
        "nonabsorbing_dwell": result["dwell_is_absorbing"] is False,
    }.items()}


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    config = json.loads(DESIGN.read_text())
    if config["status"] != "frozen_stage55_pilot" or config["trap"]["absorbing"]:
        raise RuntimeError("frozen design status/dwell mismatch")
    input_hashes = {str(DESIGN): sha(DESIGN)}
    for directory in GATES:
        input_hashes.update(check_completion(directory))
    # Bind the exact frozen seed-2 packing, field, record, and paired start.
    old_manifest = OLD_DIR / "results.json"
    old_completion = OLD_DIR / "completion.json"
    old_c = json.loads(old_completion.read_text())
    if old_c["results_sha256"] != sha(old_manifest):
        raise RuntimeError("Stage55 source manifest binding failed")
    old_inputs = json.loads(old_manifest.read_text())["input_hashes"]
    seed2_inputs = {path: digest for path, digest in old_inputs.items()
                    if "s31b_n216_s2_clean" in path or "starts_s2.json" in path}
    if len(seed2_inputs) != 4:
        raise RuntimeError("expected four seed-2 geometry/field/record/start bindings")
    for path, digest in seed2_inputs.items():
        if sha(path) != digest:
            raise RuntimeError(f"seed-2 frozen input drift: {path}")
    input_hashes.update(seed2_inputs)
    input_hashes[str(old_manifest)] = sha(old_manifest)
    input_hashes[str(old_completion)] = sha(old_completion)
    length = matrix_case_v1.load(2)[2]
    horizon = config["horizon_pore_volumes"] * length / config["target_mean_interstitial_velocity_m_s"]
    wall_budget = config["numerics"]["wall_budget_s_per_case"]
    if not (abs(horizon - 4.680605809919908) <= 1e-12 and wall_budget == 1800.):
        raise RuntimeError("seed-2 frozen horizon/budget mismatch")
    source.trajectory = candidate
    rows = []
    for shape in config["shapes"]:
        prior = OLD_DIR / f"s2_{shape}.json"
        input_hashes[str(prior)] = sha(prior)
        started = datetime.now(timezone.utc).isoformat()
        result, _ = source.run(2, shape, horizon, wall_budget)
        checks = case_checks(result, horizon, wall_budget)
        row = {"packing_seed": 2, "shape": shape, "horizon_s": horizon,
               "wall_budget_s": wall_budget, "start_utc": started,
               "end_utc": datetime.now(timezone.utc).isoformat(),
               "passed": all(checks.values()), "checks": checks, "result": result}
        rows.append(row)
        case_path = OUT / f"s2_{shape}.json"
        case_path.write_text(json.dumps(row, indent=2))
        print(json.dumps({"shape": shape, "passed": row["passed"],
                          "status": result["status"], "time_s": result["time_s"],
                          "horizon_s": horizon, "runtime_s": result["runtime_seconds"],
                          "trap": result["trap_state"]}), flush=True)
        if not row["passed"]:
            break
    source_paths = [Path(__file__), Path(source.__file__), Path(candidate.__file__),
                    ROOT / "stage80_staging" / "trajectory_combined_pruning_v1.py",
                    ROOT / "stage79_staging" / "inertial_contact_within_pose_reuse_v1.py",
                    ROOT / "stage76_staging" / "geometry_fail_fast_sweep_v1.py",
                    ROOT / "stage74_staging" / "scalar_contact_kernels_v1.py",
                    ROOT / "stage68_staging" / "trajectory_extended_recovery_v1.py",
                    Path(matrix_case_v1.__file__)]
    record = {"completed": len(rows) == 2,
              "passed": len(rows) == 2 and all(row["passed"] for row in rows),
              "rows": rows, "horizon_s": horizon,
              "input_hashes": input_hashes,
              "case_hashes": {str(p): sha(p) for p in OUT.glob("s2_*.json")},
              "source_hashes": {str(p): sha(p) for p in source_paths},
              "environment": {"python": platform.python_version(),
                              "numpy": np.__version__},
              "claim_boundary": "One fixed-sand, one-way-flow paired conditional observation only; no population release fraction, irreversible retention, or empirical validation."}
    path = OUT / "results.json"
    path.write_text(json.dumps(record, indent=2))
    (OUT / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if record["passed"] else "complete_failed",
        "results_sha256": sha(path)}, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
