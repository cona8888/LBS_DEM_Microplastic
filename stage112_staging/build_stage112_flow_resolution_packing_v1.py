"""Freeze the minimal Stage112 packing and spatial-flow verification design."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "stage110_evaluations/flow_similarity_design_20260915/results.json"
SIM_COMPLETION = SIM.with_name("completion.json")
STAGE111_DESIGN = ROOT / "stage111_designs/seed2_clean_physical_re_flow_validation_20260915/design_01/resolved_design.json"
STAGE111_RUN = ROOT / "stage111_runs/seed2_clean_physical_re_flow_validation_20260915/gpu_validation_01"
STAGE111_EVAL = ROOT / "stage111_evaluations/seed2_clean_physical_re_flow_validation_20260915/independent_evaluation_01/results.json"
STAGE111_EVAL_COMPLETION = STAGE111_EVAL.with_name("completion.json")
BASE2 = ROOT / "stage31_designs/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_01/resolved_config.json"
BASE2_COMPLETION = BASE2.with_name("completion.json")
BASE4 = ROOT / "stage31_designs/stage31f_selected_replicated_cpd4_20260827/geometry_01/resolved_config.json"
BASE4_COMPLETION = BASE4.with_name("completion.json")
STAGE27 = ROOT / "stage27_designs/stage27a_stage26x_mechanics_hydraulic_bridge_20260823/geometry_01/resolved_config.json"
STAGE17 = Path(r"C:\Users\wonjuncha-admin\Documents\Codex\2026-07-19\skill-creator-c-users-wonjuncha-admin\yade_benchmark\lbs_calibration\scripts\stage17_relaxed_fibre_gpu_lbm_run.py")
OUT = ROOT / "stage112_designs/reference_flow_resolution_packing_20260915/design_01"


def sha(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path: Path | str) -> dict:
    return json.loads(Path(path).read_text())


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def mean_interstitial(field_path: Path) -> float:
    with np.load(field_path) as data:
        return float(np.mean(data["velocity_xyz_lu"][0][data["phase"] == 0], dtype=np.float64))


def main() -> None:
    if OUT.exists():
        raise FileExistsError(OUT)
    sim = read(SIM)
    sim_completion = read(SIM_COMPLETION)
    d111 = read(STAGE111_DESIGN)
    r111 = read(STAGE111_RUN / "completion.json")
    e111 = read(STAGE111_EVAL)
    ec111 = read(STAGE111_EVAL_COMPLETION)
    b2, bc2, b4, bc4, s27 = map(read, (BASE2, BASE2_COMPLETION, BASE4, BASE4_COMPLETION, STAGE27))
    if (sha(SIM) != sim_completion["results_sha256"]
            or sim["status"] != "re_similarity_targets_derived_no_flow_solve"
            or not r111["passed"] or not e111["passed"]
            or e111["status"] != "complete_passed_direct_fields_required_seed2_cpd2"
            or sha(STAGE111_EVAL) != ec111["results_sha256"]
            or not bc2["passed"] or not bc4["passed"]):
        raise RuntimeError("Stage112 prerequisite status failed")
    for path, expected in ((STAGE111_DESIGN, r111["design_sha256"]),
                           (BASE2, bc2["config_sha256"]),
                           (BASE4, bc4["config_sha256"])):
        if sha(path) != expected:
            raise RuntimeError(f"prerequisite hash drift: {path}")

    rows = {(int(row["packing_seed"]), float(row["flow_factor"])): row for row in sim["rows"]}
    cases = []
    for seed in (1, 3):
        row = rows[(seed, 1.0)]
        geometry = ROOT / f"stage31_designs/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_01/s31b_n216_s{seed}_clean/geometry_cpd2.npz"
        archive_dir = ROOT / f"stage31_runs/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_screen_01/stage31e_s31b_n216_s{seed}_clean_cpd2"
        archive_field = archive_dir / "final_fields.npz"
        archive_record = archive_dir / "record.json"
        record = read(archive_record)
        scale = float(row["candidate_Re_matched_mean_interstitial_velocity_lu"] / mean_interstitial(archive_field))
        cases.append({
            "case_id": f"stage112_s{seed}_clean_f1p0_cpd2",
            "packing_seed": seed,
            "cpd": 2,
            "geometry": str(geometry),
            "target_physical_mean_interstitial_velocity_m_s": row["physical_mean_interstitial_velocity_m_s"],
            "target_physical_median_grain_Re": row["physical_median_grain_Re_at_mean_speed"],
            "target_mean_interstitial_velocity_lu": row["candidate_Re_matched_mean_interstitial_velocity_lu"],
            "initial_acceleration_lu": float(record["acceleration_lu"] * scale),
            "warm_start": {"path": str(archive_field), "sha256": sha(archive_field),
                           "velocity_scale": scale, "density_deviation_scale": scale},
            "archive_record": {"path": str(archive_record), "sha256": sha(archive_record)},
        })

    geometry4 = ROOT / "stage31_designs/stage31f_selected_replicated_cpd4_20260827/geometry_01/s31b_n216_s2_clean/geometry_cpd4.npz"
    archive4_dir = ROOT / "stage31_runs/stage31f_selected_replicated_cpd4_20260827/gpu_confirmation_01/stage31f_s31b_n216_s2_clean_cpd4"
    archive4_field = archive4_dir / "final_fields.npz"
    archive4_record = archive4_dir / "record.json"
    stage111_field = STAGE111_RUN / "stage111_s2_clean_f1p0_cpd2/final_fields.npz"
    stage111_record = STAGE111_RUN / "stage111_s2_clean_f1p0_cpd2/record.json"
    with np.load(geometry4) as g4:
        d4_lu = float(np.median(2.0 * g4["sand_radii_m"]) / float(g4["spacing_m"][0]))
    target_re = rows[(2, 1.0)]["physical_median_grain_Re_at_mean_speed"]
    target_u4 = float(target_re * float(b4["solver"]["kinematic_viscosity_lu"]) / d4_lu)
    archived_u4 = mean_interstitial(archive4_field)
    archived4 = read(archive4_record)
    achieved_u2 = mean_interstitial(stage111_field)
    achieved_a2 = float(read(stage111_record)["acceleration_lu"])
    cases.append({
        "case_id": "stage112_s2_clean_f1p0_cpd4",
        "packing_seed": 2,
        "cpd": 4,
        "geometry": str(geometry4),
        "target_physical_mean_interstitial_velocity_m_s": rows[(2, 1.0)]["physical_mean_interstitial_velocity_m_s"],
        "target_physical_median_grain_Re": target_re,
        "target_mean_interstitial_velocity_lu": target_u4,
        "initial_acceleration_lu": float(archived4["acceleration_lu"] * target_u4 / archived_u4),
        "warm_start": {"path": str(stage111_field), "sha256": sha(stage111_field),
                       "velocity_scale": target_u4 / achieved_u2,
                       "density_deviation_scale": (archived4["acceleration_lu"] * target_u4 / archived_u4) / achieved_a2},
        "archive_record": {"path": str(archive4_record), "sha256": sha(archive4_record)},
        "source_cpd2_direct_record": {"path": str(stage111_record), "sha256": sha(stage111_record)},
    })

    cuda = Path(s27["lineage"]["cuda_source"]["path"])
    design = {
        "schema": "matdem.stage112.reference-flow-resolution-packing.v1",
        "status": "designed_independent_audit_required",
        "research_question": "Are direct reference-flow fields numerically healthy across all three frozen packings, and what spatial-flow uncertainty remains between CPD2 and CPD4 for seed 2?",
        "claim_boundary": "Clean fixed beds only. Packing variability and CPD2-to-CPD4 flow differences are verification evidence, not permeability validation or particle-release evidence.",
        "cases": cases,
        "reference_cpd2": {
            "case_id": "stage111_s2_clean_f1p0_cpd2",
            "record": str(stage111_record), "record_sha256": sha(stage111_record),
            "field": str(stage111_field), "field_sha256": sha(stage111_field),
        },
        "solver": {
            "tau": float(b4["solver"]["tau"]),
            "kinematic_viscosity_lu": float(b4["solver"]["kinematic_viscosity_lu"]),
            "maximum_steps": int(b4["solver"]["maximum_steps"]),
            "sample_interval_steps": int(b4["solver"]["sample_interval_steps"]),
            "steady_window_samples": int(b4["solver"]["steady_window_samples"]),
            "steady_successive_relative_change_max": float(b4["solver"]["steady_successive_relative_change_max"]),
            "steady_normalized_slope_max": float(b4["solver"]["steady_normalized_slope_max"]),
            "steady_coefficient_of_variation_max": float(b4["solver"]["steady_coefficient_of_variation_max"]),
            "threads_per_block": int(b4["solver"]["threads_per_block"]),
        },
        "numerical_acceptance": {k: b4["acceptance"][k] for k in (
            "maximum_mach_number", "maximum_mean_density_drift", "maximum_momentum_balance_relative",
            "maximum_reynolds_number_diameter", "maximum_torque_over_drag_diameter",
            "maximum_transverse_force_over_drag")},
        "evaluation": {
            "target_mean_Re_relative_error_max": 0.05,
            "gross_dimensionless_mobility_relative_shift_max": 0.10,
            "spatial_profile_rule": "Quantify normalized common-fully-fluid CPD2/CPD4 differences; do not convert field RMS directly into release-fraction error. Require later matched trajectory resolution.",
            "packing_rule": "Report all three direct CPD2 mobilities and their CV/range; stochastic packing spread is measured rather than treated as a failure.",
        },
        "execution": dict(b4["execution"]),
        "lineage": {
            "builder": {"path": str(Path(__file__).resolve()), "sha256": sha(__file__)},
            "flow_similarity": {"path": str(SIM), "sha256": sha(SIM)},
            "flow_similarity_completion": {"path": str(SIM_COMPLETION), "sha256": sha(SIM_COMPLETION)},
            "stage111_design": {"path": str(STAGE111_DESIGN), "sha256": sha(STAGE111_DESIGN)},
            "stage111_completion": {"path": str(STAGE111_RUN / "completion.json"), "sha256": sha(STAGE111_RUN / "completion.json")},
            "stage111_evaluation": {"path": str(STAGE111_EVAL), "sha256": sha(STAGE111_EVAL)},
            "stage111_evaluation_completion": {"path": str(STAGE111_EVAL_COMPLETION), "sha256": sha(STAGE111_EVAL_COMPLETION)},
            "base_cpd2_config": {"path": str(BASE2), "sha256": sha(BASE2)},
            "base_cpd2_completion": {"path": str(BASE2_COMPLETION), "sha256": sha(BASE2_COMPLETION)},
            "base_cpd4_config": {"path": str(BASE4), "sha256": sha(BASE4)},
            "base_cpd4_completion": {"path": str(BASE4_COMPLETION), "sha256": sha(BASE4_COMPLETION)},
            "stage27_config": {"path": str(STAGE27), "sha256": sha(STAGE27)},
            "stage17_runner": {"path": str(STAGE17), "sha256": sha(STAGE17)},
            "cuda_source": {"path": str(cuda), "sha256": sha(cuda)},
            "qualified_ptx_sha256": s27["lineage"]["qualified_ptx_sha256"],
        },
        "authority": {"independent_audit": True, "gpu_execution": False,
                      "particle_transport": False, "campaign": False},
    }
    for case in cases:
        design["lineage"][case["case_id"] + "_geometry"] = {"path": case["geometry"], "sha256": sha(case["geometry"])}
        design["lineage"][case["case_id"] + "_warm_start"] = {"path": case["warm_start"]["path"], "sha256": case["warm_start"]["sha256"]}
        design["lineage"][case["case_id"] + "_archive_record"] = case["archive_record"]

    OUT.mkdir(parents=True, exist_ok=False)
    write(OUT / "resolved_design.json", design)
    write(OUT / "completion.json", {"status": design["status"],
                                    "design_sha256": sha(OUT / "resolved_design.json")})
    print(json.dumps({"status": design["status"], "cases": [(c["case_id"], c["initial_acceleration_lu"]) for c in cases]}))


if __name__ == "__main__":
    main()
