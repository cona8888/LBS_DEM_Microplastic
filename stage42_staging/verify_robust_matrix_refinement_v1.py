"""Qualify the packaged Stage42 solver on the difficult frictional replay."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage41_staging"),
                str(ROOT / "stage42_staging")]
import matrix_case_v1
import geometry_exact_v1
import trajectory_robust_v1 as trajectory


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def angle(left, right):
    left, right = np.asarray(left, float), np.asarray(right, float)
    return float(np.arctan2(np.linalg.norm(np.cross(left, right)), np.dot(left, right)))


def sources():
    paths = {Path(__file__).resolve()}
    for module in list(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if path and Path(path).suffix == ".py" and Path(path).resolve().is_relative_to(ROOT):
            paths.add(Path(path).resolve())
    return {str(path): sha(path) for path in sorted(paths)}


def main():
    output = ROOT / "stage42_evaluations" / "robust_matrix_refinement_01"
    output.mkdir(parents=True, exist_ok=False)
    before = sources()
    field, old_geometry, length, spacing, matrix_inputs = matrix_case_v1.load(2)
    geometry = geometry_exact_v1.GrainGeometry.from_geometry(old_geometry)
    start_path = ROOT / "stage39_evaluations" / "matrix_profile_01" / "results.json"
    prior_path = ROOT / "stage41_evaluations" / "matrix_replay_refinement_02" / "results.json"
    probe_path = ROOT / "stage42_evaluations" / "contact_iteration_ceiling_probe_02" / "results.json"
    start = json.loads(start_path.read_text())["result"]
    prior = json.loads(prior_path.read_text())
    previous_fine = next(row["pair"]["candidate"] for row in prior["values"]["rows"]
                         if row["friction"] == 0.3 and row["fraction"] == 0.00625)
    probe = json.loads(probe_path.read_text())["result"]
    result = trajectory.integrate(
        field, geometry, start["position_m"], start["orientation"],
        start["velocity_generalized"], 2e-4, 5e-5, 0.001002, 1380, 998.2,
        [0, 0, -9.80665], 0.3, length, 0.02,
        added_mass_fraction=1, cutoff_ratio=0.2, roughness_ratio=0.01,
        displacement_fraction=0.00625, relaxation_fraction=0.015625,
        max_dt=0.01, wall_budget=480, trap_reference_speed=1e-4,
        trap_dwell_time=0.5)
    shift = float(np.linalg.norm(np.asarray(previous_fine["position_m"])
                                 - np.asarray(result["position_m"])) / 5e-5)
    orientation_shift = angle(previous_fine["orientation"], result["orientation"])
    exact_probe_match = (result["status"] == probe["status"]
                         and result["steps"] == probe["steps"]
                         and result["position_m"] == probe["position_m"]
                         and result["orientation"] == probe["orientation"]
                         and result["velocity_generalized"] == probe["velocity_generalized"]
                         and result["minimum_gap_m"] == probe["minimum_gap_m"]
                         and result["total_contact_iterations"] == probe["total_contact_iterations"])
    after = sources()
    checks = {
        "completed_horizon": bool(result["status"] == "present_at_horizon"),
        "clearance": bool(result["minimum_gap_m"] >= -5e-10),
        "contact_closure": bool(result["max_contact_residual"] <= 1e-8),
        "momentum_closure": bool(result["max_momentum_residual"] <= 1e-8),
        "reynolds_envelope": bool(result["max_reynolds"] <= 3),
        "fine_extra_fine_position_shift": bool(shift <= 0.01),
        "fine_extra_fine_orientation_shift": bool(orientation_shift <= 1e-3),
        "exact_match_to_50000_ceiling_probe": bool(exact_probe_match),
        "sources_stable": bool(before == after),
    }
    record = {"passed": bool(all(checks.values())), "checks": checks,
              "fine_extra_fine_shift_minor_radii": shift,
              "fine_extra_fine_orientation_rad": orientation_shift,
              "result": result, "source_hashes": after,
              "source_hashes_at_start": before,
              "input_hashes": {str(path): sha(path) for path in
                               (*matrix_inputs, start_path, prior_path, probe_path)},
              "scope": "packaged solver numerical qualification; no release claim"}
    results_path = output / "results.json"
    results_path.write_text(json.dumps(record, indent=2))
    (output / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if record["passed"] else "complete_failed",
        "results_sha256": sha(results_path)}, indent=2))
    print(json.dumps({"passed": record["passed"], "checks": checks,
                      "shift_minor_radii": shift,
                      "orientation_shift_rad": orientation_shift,
                      "runtime_seconds": result["runtime_seconds"],
                      "max_contact_iterations": result["max_contact_iterations_per_nonlinear_solve"]}, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
