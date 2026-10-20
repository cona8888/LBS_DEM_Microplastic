"""Local restarted A/B test; not physical continuation or release evidence."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage41_staging"),
                str(ROOT / "stage68_staging"), str(ROOT / "stage70_staging"),
                str(ROOT / "stage79_staging")]
import matrix_case_v1
import geometry_exact_v1
import trajectory_extended_recovery_v1 as trajectory
import inertial_contact_runtime_portfolio_v1 as baseline_contact
import inertial_contact_within_pose_reuse_v1 as candidate_contact

DESIGN = ROOT / "stage55_designs" / "paired_three_packing_pilot_v1.json"
OLD = (ROOT / "stage55_runs" / "paired_three_packing_pilot_20260912" /
       "pilot_01" / "s2_prolate_ar4.json")
OUT = ROOT / "stage79_evaluations" / "local_reuse_ab_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(module, field, geometry, previous, design, length):
    a, b, _ = design["prolate_semiaxes_m"]
    original = trajectory.inertial
    trajectory.inertial = module
    module.set_recovery_mode(False)
    try:
        return trajectory.integrate(
            field, geometry, previous["position_m"], previous["orientation"],
            previous["velocity_generalized"], a, b,
            design["dynamic_viscosity_Pa_s"], design["particle_density_kg_m3"],
            design["fluid_density_kg_m3"], design["gravity_m_s2"],
            design["friction_coefficient"], length, 0.002,
            added_mass_fraction=design["added_mass_fraction"],
            cutoff_ratio=0.2, roughness_ratio=0.01,
            displacement_fraction=design["numerics"]["displacement_fraction"],
            relaxation_fraction=design["numerics"]["relaxation_fraction"],
            angle_limit=design["numerics"]["angle_limit_rad"],
            max_dt=design["numerics"]["max_dt_s"], wall_budget=30.,
            trap_reference_speed=design["target_mean_interstitial_velocity_m_s"],
            trap_dwell_time=design["trap"]["dwell_time_s"],
            trap_speed_ratio=design["trap"]["speed_ratio"],
            trap_drift_over_minor_radius=design["trap"]["drift_over_minor_radius"],
            stop_on_trap=design["trap"]["absorbing"],
            reynolds_limit=design["numerics"]["reynolds_limit"])
    finally:
        module.set_recovery_mode(False)
        trajectory.inertial = original


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    design = json.loads(DESIGN.read_text())
    previous = json.loads(OLD.read_text())["result"]
    if previous["status"] != "numerical_failure":
        raise RuntimeError("expected frozen numerical-failure state")
    field, old_geometry, length, dx, inputs = matrix_case_v1.load(2)
    geometry = geometry_exact_v1.GrainGeometry.from_geometry(old_geometry)
    baseline = run(baseline_contact, field, geometry, previous, design, length)
    candidate = run(candidate_contact, field, geometry, previous, design, length)
    deltas = {key: float(np.linalg.norm(
        np.asarray(candidate[key], dtype=float) - np.asarray(baseline[key], dtype=float)))
        for key in ("position_m", "orientation", "velocity_generalized")}
    checks = {
        "same_status": candidate["status"] == baseline["status"] == "present_at_horizon",
        "same_steps": candidate["steps"] == baseline["steps"],
        "same_rejects": candidate["rejected"] == baseline["rejected"],
        "same_time": abs(candidate["time_s"] - baseline["time_s"]) <= 1e-12,
        "position_agreement_m": deltas["position_m"] <= 1e-9,
        "orientation_agreement": deltas["orientation"] <= 1e-9,
        "velocity_agreement": deltas["velocity_generalized"] <= 1e-9,
        "candidate_contact_health": candidate["max_contact_residual"] <= 1e-8,
        "candidate_force_health": candidate["max_force_residual"] <= 1e-8,
        "candidate_momentum_health": candidate["max_momentum_residual"] <= 1e-8,
        "candidate_reynolds_health": candidate["max_reynolds"] <= 3,
        "reuse_exercised": candidate_contact.reuse_stats()["prior_accepted"] > 0,
    }
    checks = {key: bool(value) for key, value in checks.items()}
    record = {
        "passed": all(checks.values()), "checks": checks,
        "baseline": baseline, "candidate": candidate, "state_deltas": deltas,
        "reuse_stats": candidate_contact.reuse_stats(),
        "input_hashes": {str(p): sha(p) for p in (DESIGN, OLD)},
        "source_hashes": {str(p): sha(p) for p in (
            Path(__file__), Path(candidate_contact.__file__),
            Path(baseline_contact.__file__), Path(trajectory.__file__),
            Path(geometry_exact_v1.__file__))},
        "claim_boundary": "Local restarted numerical A/B only; no physical continuation, trapping, release, or validation claim."
    }
    path = OUT / "results.json"
    path.write_text(json.dumps(record, indent=2))
    (OUT / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if record["passed"] else "complete_failed",
        "results_sha256": sha(path)}, indent=2))
    print(json.dumps({"passed": record["passed"], "checks": checks,
                      "state_deltas": deltas,
                      "baseline_runtime_s": baseline["runtime_seconds"],
                      "candidate_runtime_s": candidate["runtime_seconds"],
                      "baseline_iterations": baseline["total_contact_iterations"],
                      "candidate_iterations": candidate["total_contact_iterations"],
                      "baseline_retries": baseline["contact_solver_retries"],
                      "candidate_retries": candidate["contact_solver_retries"],
                      "reuse_stats": record["reuse_stats"]}, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
