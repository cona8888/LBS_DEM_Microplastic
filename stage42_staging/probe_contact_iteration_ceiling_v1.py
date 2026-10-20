"""Test whether the Stage41 frictional replay failure is only a PGS ceiling issue.

The physical equations and residual tolerance are unchanged.  This diagnostic
raises only the cold contact solver's iteration ceiling from 10,000 to 50,000.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage41_staging")]
import matrix_case_v1
import geometry_exact_v1
import inertial_contact_cold_optimized_v1 as inertial
import trajectory_optimized_v1 as trajectory


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output = ROOT / "stage42_evaluations" / "contact_iteration_ceiling_probe_02"
    output.mkdir(parents=True, exist_ok=False)
    source_paths = [Path(__file__).resolve(), Path(inertial.__file__).resolve(),
                    Path(trajectory.__file__).resolve(), Path(geometry_exact_v1.__file__).resolve()]
    hashes_before = {str(path): sha(path) for path in source_paths}
    original = inertial._solve_prepared

    def higher_ceiling(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
        return original(vfree, mobility, jacobian, gaps, dt, friction, tol,
                        max(maxiter, 50000))

    inertial._solve_prepared = higher_ceiling
    field, old_geometry, length, spacing, inputs = matrix_case_v1.load(2)
    geometry = geometry_exact_v1.GrainGeometry.from_geometry(old_geometry)
    start_path = ROOT / "stage39_evaluations" / "matrix_profile_01" / "results.json"
    start = json.loads(start_path.read_text())["result"]
    result = trajectory.integrate(
        field, geometry, start["position_m"], start["orientation"],
        start["velocity_generalized"], 2e-4, 5e-5, 0.001002, 1380, 998.2,
        [0, 0, -9.80665], 0.3, length, 0.02,
        added_mass_fraction=1, cutoff_ratio=0.2, roughness_ratio=0.01,
        displacement_fraction=0.00625, relaxation_fraction=0.015625,
        max_dt=0.01, wall_budget=480, trap_reference_speed=1e-4,
        trap_dwell_time=0.5)
    hashes_after = {str(path): sha(path) for path in source_paths}
    checks = {
        "completed_horizon": bool(result["status"] == "present_at_horizon"),
        "clearance": bool(result["minimum_gap_m"] >= -5e-10),
        "contact_closure": bool(result["max_contact_residual"] <= 1e-8),
        "momentum_closure": bool(result["max_momentum_residual"] <= 1e-8),
        "reynolds_envelope": bool(result["max_reynolds"] <= 3),
        "sources_stable": bool(hashes_before == hashes_after),
    }
    record = {"passed": bool(all(checks.values())), "checks": checks,
              "result": result, "iteration_ceiling": 50000,
              "source_hashes": hashes_after,
              "input_hashes": {str(path): sha(path) for path in (*inputs, start_path)},
              "scope": "solver-ceiling diagnostic only; equations and tolerance unchanged"}
    results_path = output / "results.json"
    results_path.write_text(json.dumps(record, indent=2))
    (output / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if record["passed"] else "complete_failed",
        "results_sha256": sha(results_path)}, indent=2))
    print(json.dumps({"passed": record["passed"], "checks": checks,
                      "status": result["status"], "reason": result["reason"],
                      "steps": result["steps"],
                      "max_contact_iterations": result["max_contact_iterations_per_nonlinear_solve"],
                      "runtime_seconds": result["runtime_seconds"]}, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
