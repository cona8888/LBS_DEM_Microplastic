"""Late-state local restart A/B of Stage80 versus scoped scalar kernels."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage41_staging"),
                str(ROOT / "stage80_staging"), str(ROOT / "stage81_staging")]
import matrix_case_v1
import geometry_exact_v1
import trajectory_combined_pruning_v1 as baseline
import trajectory_combined_scalar_v1 as candidate

DESIGN = ROOT / "stage55_designs" / "paired_three_packing_pilot_v1.json"
OLD = ROOT / "stage80_evaluations" / "combined_s2_long_transfer_01" / "results.json"
OLD_COMPLETION = OLD.parent / "completion.json"
OUT = ROOT / "stage81_evaluations" / "late_scalar_ab_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(module, field, geometry, previous, cfg, length):
    a, b, _ = cfg["prolate_semiaxes_m"]
    return module.integrate(
        field, geometry, previous["position_m"], previous["orientation"],
        previous["velocity_generalized"], a, b,
        cfg["dynamic_viscosity_Pa_s"], cfg["particle_density_kg_m3"],
        cfg["fluid_density_kg_m3"], cfg["gravity_m_s2"],
        cfg["friction_coefficient"], length, 0.0005,
        added_mass_fraction=cfg["added_mass_fraction"],
        cutoff_ratio=0.2, roughness_ratio=0.01,
        displacement_fraction=cfg["numerics"]["displacement_fraction"],
        relaxation_fraction=cfg["numerics"]["relaxation_fraction"],
        angle_limit=cfg["numerics"]["angle_limit_rad"],
        max_dt=cfg["numerics"]["max_dt_s"], wall_budget=30.,
        trap_reference_speed=cfg["target_mean_interstitial_velocity_m_s"],
        trap_dwell_time=cfg["trap"]["dwell_time_s"],
        trap_speed_ratio=cfg["trap"]["speed_ratio"],
        trap_drift_over_minor_radius=cfg["trap"]["drift_over_minor_radius"],
        stop_on_trap=cfg["trap"]["absorbing"],
        reynolds_limit=cfg["numerics"]["reynolds_limit"])


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    c = json.loads(OLD_COMPLETION.read_text())
    if c["status"] != "complete_failed" or c["results_sha256"] != sha(OLD):
        raise RuntimeError("frozen Stage80 result binding failed")
    previous = json.loads(OLD.read_text())["result"]
    if previous["status"] != "incomplete_budget":
        raise RuntimeError("expected frozen budget-censored state")
    cfg = json.loads(DESIGN.read_text())
    field, old_geometry, length, dx, inputs = matrix_case_v1.load(2)
    geometry = geometry_exact_v1.GrainGeometry.from_geometry(old_geometry)
    original = run(baseline, field, geometry, previous, cfg, length)
    revised = run(candidate, field, geometry, previous, cfg, length)
    deltas = {key: float(np.linalg.norm(
        np.asarray(revised[key], dtype=float) - np.asarray(original[key], dtype=float)))
        for key in ("position_m", "orientation", "velocity_generalized")}
    checks = {
        "both_complete": original["status"] == revised["status"] == "present_at_horizon",
        "same_time": abs(original["time_s"] - revised["time_s"]) <= 1e-12,
        "same_steps": original["steps"] == revised["steps"],
        "same_rejects": original["rejected"] == revised["rejected"],
        "position_agreement_m": deltas["position_m"] <= 1e-9,
        "orientation_agreement": deltas["orientation"] <= 1e-9,
        "velocity_agreement": deltas["velocity_generalized"] <= 1e-9,
        "candidate_contact": revised["max_contact_residual"] <= 1e-8,
        "candidate_force": revised["max_force_residual"] <= 1e-8,
        "candidate_momentum": revised["max_momentum_residual"] <= 1e-8,
        "candidate_reynolds": revised["max_reynolds"] <= 3,
        "scalar_exercised": revised["total_contact_iterations"] > 0,
    }
    checks = {key: bool(value) for key, value in checks.items()}
    record = {"passed": all(checks.values()), "checks": checks,
              "diagnostic_only": True, "prior_time_s": previous["time_s"],
              "local_horizon_s": 0.0005,
              "baseline": original, "candidate": revised, "state_deltas": deltas,
              "input_hashes": {str(p): sha(p) for p in (DESIGN, OLD, OLD_COMPLETION)},
              "source_hashes": {str(p): sha(p) for p in (
                  Path(__file__), Path(candidate.__file__), Path(baseline.__file__),
                  ROOT / "stage74_staging" / "scalar_contact_kernels_v1.py")},
              "claim_boundary": "Local restarted numerical/cost diagnostic only; no physical continuation or release inference."}
    path = OUT / "results.json"
    path.write_text(json.dumps(record, indent=2))
    (OUT / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if record["passed"] else "complete_failed",
        "results_sha256": sha(path)}, indent=2))
    print(json.dumps({"passed": record["passed"], "checks": checks,
                      "state_deltas": deltas,
                      "baseline_runtime_s": original["runtime_seconds"],
                      "candidate_runtime_s": revised["runtime_seconds"],
                      "baseline_iterations": original["total_contact_iterations"],
                      "candidate_iterations": revised["total_contact_iterations"],
                      "baseline_retries": original["contact_solver_retries"],
                      "candidate_retries": revised["contact_solver_retries"]}, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
