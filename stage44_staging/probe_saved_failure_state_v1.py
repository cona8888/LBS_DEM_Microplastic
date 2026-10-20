"""Probe Stage44 from the last accepted state before Stage43 contact failure."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage41_staging"),
                str(ROOT / "stage44_staging")]
import matrix_case_v1
import geometry_exact_v1
import trajectory_fallback_v1 as trajectory


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output = ROOT / "stage44_evaluations" / "saved_failure_state_probe_02"
    output.mkdir(parents=True, exist_ok=False)
    source = ROOT / "stage43_runs" / "release_pilot_20260912" / "pilot_01" / "coarse.json"
    saved = json.loads(source.read_text())["result"]
    field, old_geometry, length, spacing, inputs = matrix_case_v1.load(2)
    geometry = geometry_exact_v1.GrainGeometry.from_geometry(old_geometry)
    result = trajectory.integrate(
        field, geometry, saved["position_m"], saved["orientation"],
        saved["velocity_generalized"], 2e-4, 5e-5, 0.001002, 1380, 998.2,
        [0, 0, -9.80665], 0.3, length, 0.002,
        added_mass_fraction=1, cutoff_ratio=0.2, roughness_ratio=0.01,
        displacement_fraction=0.1, relaxation_fraction=0.5,
        max_dt=0.01, wall_budget=300, trap_reference_speed=1e-4,
        trap_dwell_time=0.5, stop_on_trap=False, reynolds_limit=3.0)
    checks = {
        "advanced_past_saved_state": bool(result["time_s"] > 0),
        "no_numerical_failure": bool(result["status"] != "numerical_failure"),
        "fallback_used": bool(result["contact_solver_stats"]["fallback_solves"] > 0),
        "fallback_did_not_fail": bool(result["contact_solver_stats"]["fallback_failures"] == 0),
        "clearance": bool(result["minimum_gap_m"] is not None
                          and result["minimum_gap_m"] >= -5e-10),
        "closure": bool(result["max_contact_residual"] <= 1e-8
                        and result["max_momentum_residual"] <= 1e-8),
        "reynolds_envelope": bool(result["max_reynolds"] <= 3),
    }
    record = {"passed": bool(all(checks.values())), "checks": checks,
              "result": result, "source_failure_record": str(source),
              "input_hashes": {str(path.resolve()): sha(path) for path in (*inputs, source)},
              "source_hashes": {str(Path(__file__).resolve()): sha(__file__),
                                str(Path(trajectory.__file__).resolve()): sha(trajectory.__file__)},
              "scope": "saved difficult-state algorithm probe; no release claim"}
    results_path = output / "results.json"
    results_path.write_text(json.dumps(record, indent=2))
    (output / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if record["passed"] else "complete_failed",
        "results_sha256": sha(results_path)}, indent=2))
    print(json.dumps({"passed": record["passed"], "checks": checks,
                      "status": result["status"], "reason": result["reason"],
                      "time_s": result["time_s"], "steps": result["steps"],
                      "contact_solver_stats": result["contact_solver_stats"],
                      "runtime_seconds": result["runtime_seconds"]}, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
