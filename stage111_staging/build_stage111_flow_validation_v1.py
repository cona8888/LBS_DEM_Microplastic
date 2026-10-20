"""Freeze a seed-2 three-flow physical-Re LBM validation design."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "stage110_evaluations/flow_similarity_design_20260915/results.json"
SIM_COMPLETION = SIM.with_name("completion.json")
BASE_CONFIG = ROOT / "stage31_designs/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_01/resolved_config.json"
BASE_COMPLETION = BASE_CONFIG.with_name("completion.json")
STAGE27 = ROOT / "stage27_designs/stage27a_stage26x_mechanics_hydraulic_bridge_20260823/geometry_01/resolved_config.json"
GEOMETRY = ROOT / "stage31_designs/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_01/s31b_n216_s2_clean/geometry_cpd2.npz"
ARCHIVED_RUN = ROOT / "stage31_runs/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_screen_01/stage31e_s31b_n216_s2_clean_cpd2"
ARCHIVED_FIELD = ARCHIVED_RUN / "final_fields.npz"
ARCHIVED_RECORD = ARCHIVED_RUN / "record.json"
STAGE17 = Path(r"C:\Users\wonjuncha-admin\Documents\Codex\2026-07-19\skill-creator-c-users-wonjuncha-admin\yade_benchmark\lbs_calibration\scripts\stage17_relaxed_fibre_gpu_lbm_run.py")
OUT = ROOT / "stage111_designs/seed2_clean_physical_re_flow_validation_20260915/design_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    sim, sc = read(SIM), read(SIM_COMPLETION)
    base, bc, stage27, archived = read(BASE_CONFIG), read(BASE_COMPLETION), read(STAGE27), read(ARCHIVED_RECORD)
    if (sha(SIM) != sc["results_sha256"] or sim["status"] != "re_similarity_targets_derived_no_flow_solve"
            or not bc["passed"] or sha(BASE_CONFIG) != bc["config_sha256"]
            or sha(STAGE27) != base["lineage"]["stage27_solver_config"]["sha256"]
            or not archived["passed"] or not archived["converged"]
            or sha(ARCHIVED_FIELD) != archived["artifacts"]["final_fields_npz_sha256"]):
        raise RuntimeError("prerequisite lineage failed")
    cuda = Path(stage27["lineage"]["cuda_source"]["path"])
    if sha(cuda) != stage27["lineage"]["cuda_source"]["sha256"]:
        raise RuntimeError("CUDA source drift")
    rows = sorted((row for row in sim["rows"] if row["packing_seed"] == 2),
                  key=lambda row: row["flow_factor"])
    if [row["flow_factor"] for row in rows] != [0.5, 1.0, 2.0]:
        raise RuntimeError("seed-2 three-flow design missing")
    base_accel = float(base["solver"]["acceleration_lu"])
    cases = []
    for row in rows:
        scale = (row["candidate_Re_matched_mean_interstitial_velocity_lu"] /
                 row["archived_mean_interstitial_velocity_lu"])
        cases.append({
            "case_id": "stage111_s2_clean_f" + str(row["flow_factor"]).replace(".", "p") + "_cpd2",
            "flow_factor": row["flow_factor"],
            "target_physical_mean_interstitial_velocity_m_s": row["physical_mean_interstitial_velocity_m_s"],
            "target_physical_median_grain_Re": row["physical_median_grain_Re_at_mean_speed"],
            "target_mean_interstitial_velocity_lu": row["candidate_Re_matched_mean_interstitial_velocity_lu"],
            "initial_acceleration_lu": base_accel * scale,
            "warm_start_velocity_scale": scale,
            "warm_start_density_deviation_scale": scale,
        })
    design = {
        "schema": "matdem.stage111.seed2-clean-physical-re-flow-validation.v1",
        "status": "designed_independent_audit_required",
        "research_question": "Does a direct clean-packing LBM solve at the proposed physical Reynolds range remain numerically healthy, and is linear rescaling of the archived low-Re field adequate?",
        "claim_boundary": "One fixed seed-2 clean CPD2 packing; prescribed one-way steady flow. No particle transport, release fraction, permeability validation, or packing-general conclusion.",
        "packing_seed": 2,
        "cpd": 2,
        "geometry": str(GEOMETRY),
        "archived_field": str(ARCHIVED_FIELD),
        "archived_record": str(ARCHIVED_RECORD),
        "cases": cases,
        "solver": {
            "tau": float(base["solver"]["tau"]),
            "kinematic_viscosity_lu": float(base["solver"]["kinematic_viscosity_lu"]),
            "maximum_steps": int(base["solver"]["maximum_steps"]),
            "sample_interval_steps": int(base["solver"]["sample_interval_steps"]),
            "steady_window_samples": int(base["solver"]["steady_window_samples"]),
            "steady_successive_relative_change_max": float(base["solver"]["steady_successive_relative_change_max"]),
            "steady_normalized_slope_max": float(base["solver"]["steady_normalized_slope_max"]),
            "steady_coefficient_of_variation_max": float(base["solver"]["steady_coefficient_of_variation_max"]),
            "threads_per_block": int(base["solver"]["threads_per_block"]),
        },
        "numerical_acceptance": dict(base["acceptance"]),
        "evaluation": {
            "target_mean_Re_relative_error_max": 0.05,
            "scaled_reuse_profile_rms_over_direct_rms_max": 0.02,
            "scaled_reuse_profile_p95_over_mean_speed_max": 0.05,
            "decision_rule": "Direct cases may pass while scaled-field reuse fails; in that outcome retain direct fields per flow and do not scale the archive.",
        },
        "execution": dict(base["execution"]),
        "lineage": {
            "base_config": {"path": str(BASE_CONFIG), "sha256": sha(BASE_CONFIG)},
            "base_completion": {"path": str(BASE_COMPLETION), "sha256": sha(BASE_COMPLETION)},
            "stage27_config": {"path": str(STAGE27), "sha256": sha(STAGE27)},
            "flow_similarity": {"path": str(SIM), "sha256": sha(SIM)},
            "flow_similarity_completion": {"path": str(SIM_COMPLETION), "sha256": sha(SIM_COMPLETION)},
            "geometry": {"path": str(GEOMETRY), "sha256": sha(GEOMETRY)},
            "archived_field": {"path": str(ARCHIVED_FIELD), "sha256": sha(ARCHIVED_FIELD)},
            "archived_record": {"path": str(ARCHIVED_RECORD), "sha256": sha(ARCHIVED_RECORD)},
            "stage17_runner": {"path": str(STAGE17), "sha256": sha(STAGE17)},
            "cuda_source": {"path": str(cuda), "sha256": sha(cuda)},
            "qualified_ptx_sha256": stage27["lineage"]["qualified_ptx_sha256"],
            "builder": {"path": str(Path(__file__).resolve()), "sha256": sha(__file__)},
        },
        "authority": {"independent_audit": True, "gpu_execution": False,
                      "particle_transport": False, "campaign": False},
    }
    OUT.mkdir(parents=True, exist_ok=False)
    write(OUT / "resolved_design.json", design)
    write(OUT / "completion.json", {"status": design["status"],
                                    "design_sha256": sha(OUT / "resolved_design.json")})
    print(json.dumps({"status": design["status"], "cases": len(cases),
                      "accelerations_lu": [c["initial_acceleration_lu"] for c in cases]}))


if __name__ == "__main__":
    main()
