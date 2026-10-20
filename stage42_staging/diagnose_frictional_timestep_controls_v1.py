"""Isolate displacement and relaxation timestep controls in the difficult matrix replay.

This is a numerical-diagnostic stage only.  It runs the accepted Stage41 solver
for the frictional (mu=0.3) short replay and changes one control at a time.  It
does not estimate release, permeability, or a physical transport probability.
"""
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage41_staging")]
import matrix_case_v1
import geometry_exact_v1
import trajectory_optimized_v1 as trajectory


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def loaded_sources():
    sources = {Path(__file__).resolve()}
    for module in list(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if path and Path(path).suffix == ".py" and Path(path).resolve().is_relative_to(ROOT):
            sources.add(Path(path).resolve())
    return {str(path): sha(path) for path in sorted(sources)}


def angle(left, right):
    left, right = np.asarray(left, float), np.asarray(right, float)
    return float(np.arctan2(np.linalg.norm(np.cross(left, right)), np.dot(left, right)))


def main():
    output = ROOT / "stage42_evaluations" / "frictional_timestep_isolation_01"
    output.mkdir(parents=True, exist_ok=False)
    source_hashes_at_start = loaded_sources()
    field, old_geometry, length, spacing, inputs = matrix_case_v1.load(2)
    geometry = geometry_exact_v1.GrainGeometry.from_geometry(old_geometry)
    start_path = ROOT / "stage39_evaluations" / "matrix_profile_01" / "results.json"
    prior_path = ROOT / "stage41_evaluations" / "matrix_replay_refinement_02" / "results.json"
    start = json.loads(start_path.read_text())["result"]
    prior = json.loads(prior_path.read_text())
    prior_fine = next(row["pair"]["candidate"] for row in prior["values"]["rows"]
                      if row["friction"] == 0.3 and row["fraction"] == 0.00625)
    controls = [
        ("displacement_refined", 0.003125, 0.03125),
        ("relaxation_refined", 0.00625, 0.015625),
        ("both_refined", 0.003125, 0.015625),
    ]
    rows = [{"name": "accepted_fine_reused", "displacement_fraction": 0.00625,
             "relaxation_fraction": 0.03125, "result": prior_fine,
             "provenance": str(prior_path)}]
    for name, displacement, relaxation in controls:
        result = trajectory.integrate(
            field, geometry, start["position_m"], start["orientation"],
            start["velocity_generalized"], 2e-4, 5e-5, 0.001002, 1380, 998.2,
            [0, 0, -9.80665], 0.3, length, 0.02,
            added_mass_fraction=1, cutoff_ratio=0.2, roughness_ratio=0.01,
            displacement_fraction=displacement, relaxation_fraction=relaxation,
            max_dt=0.01, wall_budget=480, trap_reference_speed=1e-4,
            trap_dwell_time=0.5)
        rows.append({"name": name, "displacement_fraction": displacement,
                     "relaxation_fraction": relaxation, "result": result})
        print(json.dumps({"case": name, "status": result["status"],
                          "steps": result["steps"],
                          "runtime_seconds": result["runtime_seconds"]}), flush=True)

    reference = next(row["result"] for row in rows if row["name"] == "both_refined")
    for row in rows:
        result = row["result"]
        row["shift_to_both_refined_minor_radii"] = float(
            np.linalg.norm(np.asarray(result["position_m"])-np.asarray(reference["position_m"])) / 5e-5)
        row["orientation_to_both_refined_rad"] = angle(result["orientation"], reference["orientation"])

    health = all(row["result"]["status"] == "present_at_horizon"
                 and row["result"]["minimum_gap_m"] >= -5e-10
                 and row["result"]["max_contact_residual"] <= 1e-8
                 and row["result"]["max_momentum_residual"] <= 1e-8
                 and row["result"]["max_reynolds"] <= 3 for row in rows)
    displacement_row = next(row for row in rows if row["name"] == "displacement_refined")
    relaxation_row = next(row for row in rows if row["name"] == "relaxation_refined")
    checks = {
        "all_cases_numerically_healthy": health,
        "source_files_stable_during_run": False,
        "both_refined_meets_prior_orientation_gate_against_displacement_refined":
            displacement_row["orientation_to_both_refined_rad"] <= 1e-3,
        "both_refined_meets_prior_orientation_gate_against_relaxation_refined":
            relaxation_row["orientation_to_both_refined_rad"] <= 1e-3,
    }
    final_hashes = loaded_sources()
    checks["source_files_stable_during_run"] = final_hashes == source_hashes_at_start
    result = {
        "passed": bool(all(checks.values())), "checks": checks, "rows": rows,
        "source_hashes": final_hashes, "source_hashes_at_start": source_hashes_at_start,
        "input_hashes": {str(path): sha(path) for path in (*inputs, start_path, prior_path)},
        "environment": {"python": platform.python_version(), "numpy": np.__version__},
        "scope": "frictional short-replay timestep-control isolation; no physical release claim",
    }
    results_path = output / "results.json"
    results_path.write_text(json.dumps(result, indent=2))
    (output / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if result["passed"] else "complete_failed",
        "results_sha256": sha(results_path)}, indent=2))
    print(json.dumps({"passed": result["passed"], "checks": checks,
                      "comparison": [{k: row[k] for k in ("name", "shift_to_both_refined_minor_radii",
                                      "orientation_to_both_refined_rad")} for row in rows]}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
