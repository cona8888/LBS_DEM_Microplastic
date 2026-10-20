"""Replay only failed Stage55 AR=4 cases and archive their rejected local systems."""
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage41_staging"), str(ROOT / "stage56_staging")]
import geometry_exact_v1
import matrix_case_v1
import trajectory_capture_v1 as trajectory

DESIGN = ROOT / "stage55_designs" / "paired_three_packing_pilot_v1.json"
STAGE55 = ROOT / "stage55_runs" / "paired_three_packing_pilot_20260912" / "pilot_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    out = ROOT / "stage56_runs" / "stage55_fibre_failure_capture_20260912" / "diagnostic_02"
    out.mkdir(parents=True, exist_ok=False)
    cfg = json.loads(DESIGN.read_text())
    expected = {r["packing_seed"]: r for r in json.loads((STAGE55 / "results.json").read_text())["rows"] if r["shape"] == "prolate_ar4"}
    a, b, _ = cfg["prolate_semiaxes_m"]
    rows = []
    begun = time.perf_counter()
    for item in cfg["packings"]:
        seed = item["seed"]
        case_out = out / f"s{seed}_prolate_ar4"
        case_out.mkdir()
        os.environ["STAGE56_CAPTURE_DIR"] = str(case_out)
        field, old, L, dx, inputs = matrix_case_v1.load(seed)
        geometry = geometry_exact_v1.GrainGeometry.from_geometry(old)
        starts_path = ROOT / f"stage37_runs/stage4_farfield_bound_20260912/pilot_01/starts_s{seed}.json"
        start = next(x for x in json.loads(starts_path.read_text()) if x["id"] == item["start_id"])
        horizon = cfg["horizon_pore_volumes"] * L / cfg["target_mean_interstitial_velocity_m_s"]
        result = trajectory.integrate(
            field, geometry, start["position_m"], start["orientation"], np.zeros(6), a, b,
            cfg["dynamic_viscosity_Pa_s"], cfg["particle_density_kg_m3"], cfg["fluid_density_kg_m3"], cfg["gravity_m_s2"],
            cfg["friction_coefficient"], L, horizon, added_mass_fraction=cfg["added_mass_fraction"], cutoff_ratio=.2,
            roughness_ratio=.01, displacement_fraction=cfg["numerics"]["displacement_fraction"],
            relaxation_fraction=cfg["numerics"]["relaxation_fraction"], angle_limit=cfg["numerics"]["angle_limit_rad"],
            max_dt=cfg["numerics"]["max_dt_s"], wall_budget=600.0,
            trap_reference_speed=cfg["target_mean_interstitial_velocity_m_s"], trap_dwell_time=cfg["trap"]["dwell_time_s"],
            trap_speed_ratio=cfg["trap"]["speed_ratio"], trap_drift_over_minor_radius=cfg["trap"]["drift_over_minor_radius"],
            stop_on_trap=cfg["trap"]["absorbing"], reynolds_limit=cfg["numerics"]["reynolds_limit"],
        )
        old_result = expected[seed]["result"]
        record = {
            "packing_seed": seed,
            "status": result["status"],
            "reason": result["reason"],
            "time_s": result["time_s"],
            "steps": result["steps"],
            "reproduces_stage55_failure": bool(result["status"] == old_result["status"] and result["reason"] == old_result["reason"] and result["time_s"] == old_result["time_s"]),
            "capture_exists": bool((case_out / "failure_state.npz").is_file()),
            "capture_sha256": sha(case_out / "failure_state.npz") if (case_out / "failure_state.npz").is_file() else None,
            "source_stage55_case_sha256": sha(STAGE55 / f"s{seed}_prolate_ar4.json"),
        }
        (case_out / "replay.json").write_text(json.dumps(record, indent=2))
        rows.append(record)
        print(json.dumps(record), flush=True)
    del os.environ["STAGE56_CAPTURE_DIR"]
    checks = {
        "all_three_replayed": len(rows) == 3,
        "all_failures_exactly_reproduced": all(r["reproduces_stage55_failure"] for r in rows),
        "all_rejected_systems_captured": all(r["capture_exists"] for r in rows),
    }
    aggregate = {
        "completed": True,
        "passed": all(checks.values()),
        "checks": checks,
        "rows": rows,
        "runtime_s": time.perf_counter() - begun,
        "input_hashes": {str(DESIGN.resolve()): sha(DESIGN), str((STAGE55 / "results.json").resolve()): sha(STAGE55 / "results.json")},
        "environment": {"python": platform.python_version(), "numpy": np.__version__},
        "claim_boundary": "Diagnostic replay only; captured rejected systems cannot support release or morphology effects.",
    }
    path = out / "results.json"
    path.write_text(json.dumps(aggregate, indent=2))
    (out / "completion.json").write_text(json.dumps({"status": "complete_passed" if aggregate["passed"] else "complete_failed", "results_sha256": sha(path)}, indent=2))
    if not aggregate["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
