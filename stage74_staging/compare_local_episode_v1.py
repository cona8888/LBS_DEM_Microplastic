"""A/B numerical and cost check from the same frozen seed-2 accepted state.

The local clock and trap history restart, so this diagnoses implementation
transfer only. It is not a release or trapping calculation.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage41_staging"),
                str(ROOT / "stage70_staging"), str(ROOT / "stage74_staging")]
import matrix_case_v1
import geometry_exact_v1
import trajectory_runtime_portfolio_v1 as baseline
import trajectory_scalar_kernel_v1 as candidate

DESIGN = ROOT / "stage55_designs" / "paired_three_packing_pilot_v1.json"
OLD = ROOT / "stage55_runs" / "paired_three_packing_pilot_20260912" / "pilot_01" / "s2_prolate_ar4.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    out = ROOT / "stage74_evaluations" / "local_episode_ab_01"
    out.mkdir(parents=True, exist_ok=False)
    config = json.loads(DESIGN.read_text())
    previous = json.loads(OLD.read_text())["result"]
    if previous["status"] != "numerical_failure":
        raise RuntimeError("unexpected prior status")
    field, old_geometry, length, dx, inputs = matrix_case_v1.load(2)
    geometry = geometry_exact_v1.GrainGeometry.from_geometry(old_geometry)
    a, b, _ = config["prolate_semiaxes_m"]
    common = dict(added_mass_fraction=config["added_mass_fraction"],
                  cutoff_ratio=.2, roughness_ratio=.01,
                  displacement_fraction=config["numerics"]["displacement_fraction"],
                  relaxation_fraction=config["numerics"]["relaxation_fraction"],
                  angle_limit=config["numerics"]["angle_limit_rad"],
                  max_dt=config["numerics"]["max_dt_s"], wall_budget=30.,
                  trap_reference_speed=config["target_mean_interstitial_velocity_m_s"],
                  trap_dwell_time=config["trap"]["dwell_time_s"],
                  trap_speed_ratio=config["trap"]["speed_ratio"],
                  trap_drift_over_minor_radius=config["trap"]["drift_over_minor_radius"],
                  stop_on_trap=config["trap"]["absorbing"],
                  reynolds_limit=config["numerics"]["reynolds_limit"])

    def run(module):
        return module.integrate(
            field, geometry, previous["position_m"], previous["orientation"],
            previous["velocity_generalized"], a, b,
            config["dynamic_viscosity_Pa_s"], config["particle_density_kg_m3"],
            config["fluid_density_kg_m3"], config["gravity_m_s2"],
            config["friction_coefficient"], length, .002, **common)

    original = run(baseline)
    revised = run(candidate)
    shifts = {
        "position_m": float(np.linalg.norm(np.asarray(revised["position_m"]) - original["position_m"])),
        "orientation_vector": float(np.linalg.norm(np.asarray(revised["orientation"]) - original["orientation"])),
        "velocity_generalized": float(np.linalg.norm(np.asarray(revised["velocity_generalized"]) - original["velocity_generalized"])),
    }
    def healthy(result):
        return bool(result["minimum_gap_m"] >= -5e-10 and
                    result["max_contact_residual"] <= 1e-8 and
                    result["max_force_residual"] <= 1e-8 and
                    result["max_momentum_residual"] <= 1e-8 and
                    result["max_reynolds"] <= 3)
    checks = {
        "both_complete_local_horizon": original["status"] == revised["status"] == "present_at_horizon" and original["time_s"] == revised["time_s"] == .002,
        "both_healthy": healthy(original) and healthy(revised),
        "position_shift": shifts["position_m"] <= 1e-8,
        "orientation_shift": shifts["orientation_vector"] <= 1e-5,
        "velocity_shift": shifts["velocity_generalized"] <= 1e-6,
    }
    checks = {k: bool(v) for k, v in checks.items()}
    record = {"passed": all(checks.values()), "checks": checks,
              "shifts": shifts, "baseline": original, "candidate": revised,
              "input_hashes": {str(OLD): sha(OLD), str(DESIGN): sha(DESIGN)},
              "source_hashes": {str(Path(__file__).resolve()): sha(__file__),
                                str(Path(baseline.__file__).resolve()): sha(baseline.__file__),
                                str(Path(candidate.__file__).resolve()): sha(candidate.__file__)},
              "claim_boundary": "Short locally restarted numerical/cost comparison only; not physical continuation."}
    path = out / "results.json"
    path.write_text(json.dumps(record, indent=2))
    (out / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if record["passed"] else "complete_failed",
        "results_sha256": sha(path)}, indent=2))
    print(json.dumps({"passed": record["passed"], "checks": checks, "shifts": shifts,
                      "baseline_runtime_s": original["runtime_seconds"],
                      "candidate_runtime_s": revised["runtime_seconds"],
                      "baseline_steps": original["steps"],
                      "candidate_steps": revised["steps"]}, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
