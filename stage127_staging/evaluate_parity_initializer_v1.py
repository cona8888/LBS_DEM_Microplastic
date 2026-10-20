"""Independent Stage127 evidence and mechanism audit."""
from pathlib import Path
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage127_staging"))
import parity_initializer_diagnosis_v1 as job
sys.path.insert(0, str(ROOT / "stage114_staging"))
import evaluate_parity_correction_v2 as cpu


def main():
    d = job.read(job.DESIGN)
    job.verify(d)
    c = job.read(job.RUN / "completion.json")
    job.require(c["status"] == "diagnostic_complete_pending_independent_evaluation", "run status drift")
    job.require(not (job.RUN / "failure.json").exists(), "failure marker present")
    for key in ("record", "field", "state"):
        job.require(job.sha(c[key]["path"]) == c[key]["sha256"], key + " drift")
    result = job.read(c["record"]["path"])
    job.require(result["steps"] == d["controls"]["steps"], "step count drift")
    job.require(result["initial_state_sha256"] == c["initializer"]["averaged_state_array_sha256"], "averaged initializer not used")
    with np.load(c["state"]["path"]) as s, np.load(c["field"]["path"]) as f, np.load(d["bindings"]["geometry"]["path"]) as g:
        state, phase = s["shifted_state"], s["phase"]
        field, density = f["velocity_xyz_lu"], f["density_lu"]
        spacing = float(g["spacing_m"][0])
        job.require(np.array_equal(phase, f["phase"]) and np.array_equal(phase, g["phase"]), "phase drift")
    job.base.s114.audit.legacy.install_generic_mask_oracle()
    case = job.base.s114.probe.case_for(phase, d["forcing"]["acceleration_lu"], "stage127_independent")
    native = job.base.s114.probe.observe(state, phase, case)
    exact = bool(np.array_equal(native["velocity_xyz_lu"], field) and np.array_equal(native["density_lu"], density))
    independent, rho, body, wall = cpu.independent_fields(state, phase, d["forcing"]["acceleration_lu"])
    reconstruction = float(np.linalg.norm(independent - field) / np.linalg.norm(independent))
    balance = float(np.linalg.norm(np.array([body, 0, 0]) - wall) / abs(body))
    nodes = cpu.cpu_node_residuals(state, phase, d["forcing"]["acceleration_lu"])
    final = result["rows"][-8:]
    before = job.read(d["bindings"]["stage126_result"]["path"])["rows"][-8:]
    adjacent = float(final[-1]["field_change_relative_l2"])
    two_step_upper_bound = float(final[-1]["field_change_relative_l2"] + final[-2]["field_change_relative_l2"])
    mean_change = abs(float(final[-1]["delta_mean_relative"]))
    fluid = phase == 0
    nu_si = 1002e-6 / 998.2
    unit = nu_si / (0.1 * spacing)
    mean_lu = float(independent[0, fluid].mean())
    mean_si = mean_lu * unit
    mean_error = mean_si / d["forcing"]["target_mean_velocity_m_s"] - 1
    gates = d["diagnostic_gates"]
    checks = {
        "bindings_and_artifacts": True,
        "exact_steps": result["steps"] == 514,
        "exact_export": exact,
        "finite": bool(np.isfinite(state).all() and np.isfinite(field).all() and np.isfinite(density).all()),
        "health": result["numerical_health"]["full_sticky_code"] == gates["fatal_health_code"],
        "density": abs(float(rho[fluid].mean()) - 1) <= gates["density_drift_max"],
        "mach": float(native["maximum_speed_lu"]) * 3 ** 0.5 <= gates["mach_max"],
        "field_reconstruction": reconstruction <= 2e-6,
        "force_balance": balance <= 0.005,
        "cpu_fixed_point": max(x["fixed_point_relative_l2"] for x in nodes) <= 5e-5,
        "adjacent_field_mode_removed": adjacent <= gates["final_adjacent_field_change_relative_l2_max"],
        "two_step_change_upper_bound": two_step_upper_bound <= gates["final_two_step_field_change_relative_l2_max"],
        "adjacent_mean_stable": mean_change <= gates["final_adjacent_mean_change_relative_max"],
        "runtime_budget": result["runtime_seconds"] <= gates["runtime_seconds_max"],
    }
    integrity = all(v for k, v in checks.items() if k != "runtime_budget")
    mechanism = all(checks[k] for k in ["adjacent_field_mode_removed", "two_step_change_upper_bound", "adjacent_mean_stable", "cpu_fixed_point"])
    overall = integrity and mechanism and checks["runtime_budget"]
    status = "parity_initializer_mechanism_verified_cost_gate_failed" if integrity and mechanism and not checks["runtime_budget"] else ("parity_initializer_diagnostic_passed" if overall else "parity_initializer_diagnostic_failed")
    out = {
        "passed": integrity,
        "all_predeclared_gates_passed": overall,
        "initializer_mechanism_verified": mechanism,
        "status": status,
        "checks": checks,
        "design": job.bind(job.DESIGN),
        "raw_completion": job.bind(job.RUN / "completion.json"),
        "before_final_adjacent_field_change_relative_l2": before[-1]["field_change_relative_l2"],
        "after_final_adjacent_field_change_relative_l2": adjacent,
        "field_change_reduction_factor": before[-1]["field_change_relative_l2"] / adjacent,
        "after_two_step_change_relative_l2_upper_bound": two_step_upper_bound,
        "after_final_mean_change_relative": mean_change,
        "reconstruction_relative_l2": reconstruction,
        "steady_force_balance_relative": balance,
        "cpu_node_checks": nodes,
        "mean_interstitial_velocity_lu": mean_lu,
        "mean_interstitial_velocity_m_s": mean_si,
        "mean_relative_error": mean_error,
        "runtime_seconds": result["runtime_seconds"],
        "runtime_limit_seconds": gates["runtime_seconds_max"],
        "decision": "The one-time average removes the CPD6 parity mode, but the 300-s diagnostic cost gate missed by 17.94 s. Preserve and stop. Use the measured cost when freezing any later longer convergence/force-correction design; this field is not transport-authorized.",
        "full_flow_solution": False,
        "spatial_convergence_established": False,
        "force_correction_authorized": False,
        "transport_authorized": False,
        "empirical_validation_passed": False,
    }
    root = job.EVAL / "independent_evaluation_01"
    root.mkdir(parents=True, exist_ok=False)
    job.write(root / "results.json", out)
    job.write(root / "completion.json", {"passed": integrity, "status": status, "results_sha256": job.sha(root / "results.json")})
    print(json.dumps(out, indent=2), flush=True)
    job.require(integrity, "independent evidence audit failed")


if __name__ == "__main__":
    main()
