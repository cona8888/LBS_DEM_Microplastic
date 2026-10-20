"""One-start real-matrix profile of the verified cold-contact/trap state machine."""
import argparse, hashlib, json, platform
from pathlib import Path
import numpy as np
import matrix_case_v1
import trajectory_cold_trap_v1 as trajectory

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    target_velocity = 1e-4
    field, geometry, length, spacing, inputs = matrix_case_v1.load(2, target_velocity)
    starts_path = ROOT / "stage37_runs/stage4_farfield_bound_20260912/pilot_01/starts_s2.json"
    start = json.loads(starts_path.read_text())[0]
    horizon_pore_volumes = 0.02
    horizon = horizon_pore_volumes * length / target_velocity
    dwell_time = 5e-5 / target_velocity
    result = trajectory.integrate(
        field, geometry, start["position_m"], start["orientation"], np.zeros(6),
        2e-4, 5e-5, 0.001002, 1380, 998.2, [0, 0, -9.80665], 0.3,
        length, horizon, added_mass_fraction=1, cutoff_ratio=0.2,
        roughness_ratio=0.01, displacement_fraction=0.1,
        relaxation_fraction=0.5, max_dt=0.01, max_steps=500000,
        wall_budget=180, trap_reference_speed=target_velocity,
        trap_dwell_time=dwell_time, trap_speed_ratio=0.01,
        trap_drift_over_minor_radius=0.02,
    )
    terminal = {"full_window_exit", "persistent_contact_trap", "present_at_horizon"}
    checks = {
        "declared_terminal_status": result["status"] in terminal,
        "no_failure_or_budget_censoring": result["status"] not in {
            "numerical_failure", "unresolved_field", "incomplete_budget"},
        "no_material_penetration": result["minimum_gap_m"] is None or result["minimum_gap_m"] >= -5e-10,
        "momentum_closure": result["max_momentum_residual"] <= 1e-8,
        "contact_closure": result["max_contact_residual"] <= 1e-8,
        "reynolds_in_domain": result["max_reynolds"] <= 3,
    }
    sources = [Path(__file__), Path(matrix_case_v1.__file__), Path(trajectory.__file__),
               Path(trajectory.inertial.__file__), Path(trajectory.trap_event_v2.__file__),
               starts_path, *inputs]
    audit = {
        "completed": True, "passed": all(checks.values()),
        "checks": {key: bool(value) for key, value in checks.items()},
        "resolved_config": {
            "packing_seed": 2, "start_id": start["id"], "shape": "rigid_AR4_prolate",
            "semiaxes_m": [2e-4, 5e-5, 5e-5], "density_kg_m3": 1380,
            "mean_interstitial_velocity_m_s": target_velocity,
            "gravity_m_s2": [0, 0, -9.80665], "friction": 0.3,
            "roughness_over_grain_radius": 0.01, "added_mass_fraction": 1,
            "horizon_pore_volumes": horizon_pore_volumes,
            "trap_speed_over_mean_flow": 0.01,
            "trap_drift_over_minor_radius": 0.02,
            "trap_dwell_time_s": dwell_time,
        },
        "result": result,
        "input_hashes": {str(path.resolve()): sha(path) for path in sources},
        "environment": {"python": platform.python_version(), "numpy": np.__version__},
        "claim_boundary": "single-start performance/status profile; not a release estimate",
    }
    (output / "results.json").write_text(json.dumps(audit, indent=2))
    (output / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if audit["passed"] else "complete_failed",
        "results_sha256": sha(output / "results.json")}, indent=2))
    print(json.dumps({"passed": audit["passed"], "checks": audit["checks"],
                      "status": result["status"], "simulated_time_s": result["time_s"],
                      "steps": result["steps"], "runtime_s": result["runtime_seconds"],
                      "contact_iterations": result["total_contact_iterations"],
                      "max_reynolds": result["max_reynolds"]}, indent=2))
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
