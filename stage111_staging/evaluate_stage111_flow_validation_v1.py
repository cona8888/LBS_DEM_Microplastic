"""Independently evaluate the immutable Stage111 clean-flow validation."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def sha256(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path: Path | str) -> dict:
    return json.loads(Path(path).read_text())


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def normalized_profile_metrics(reference: np.ndarray, direct: np.ndarray, fluid: np.ndarray) -> dict:
    # Flow is along axis 0. Normalize each full vector field by its own mean
    # interstitial axial velocity so this tests shape, not prescribed magnitude.
    reference_mean = float(np.mean(reference[0][fluid], dtype=np.float64))
    direct_mean = float(np.mean(direct[0][fluid], dtype=np.float64))
    require(reference_mean > 0.0 and direct_mean > 0.0, "non-positive interstitial velocity")
    reference_n = reference[:, fluid].astype(np.float64) / reference_mean
    direct_n = direct[:, fluid].astype(np.float64) / direct_mean
    delta = np.linalg.norm(direct_n - reference_n, axis=0)
    direct_mag = np.linalg.norm(direct_n, axis=0)
    rms_delta = float(np.sqrt(np.mean(delta * delta)))
    rms_direct = float(np.sqrt(np.mean(direct_mag * direct_mag)))
    return {
        "reference_mean_interstitial_velocity_lu": reference_mean,
        "direct_mean_interstitial_velocity_lu": direct_mean,
        "rms_vector_difference": rms_delta,
        "direct_rms_normalized_speed": rms_direct,
        "rms_difference_over_direct_rms": rms_delta / rms_direct,
        "p95_vector_difference_over_mean_speed": float(np.percentile(delta, 95.0)),
        "maximum_vector_difference_over_mean_speed": float(np.max(delta)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", type=Path, required=True)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    design_path = args.design.resolve()
    handoff_path = args.handoff.resolve()
    run = args.run.resolve()
    output = args.output.resolve()
    require(not output.exists(), f"refusing to overwrite immutable output: {output}")
    output.mkdir(parents=True, exist_ok=False)

    design = read_json(design_path)
    handoff = read_json(handoff_path)
    completion_path = run / "completion.json"
    require(completion_path.is_file(), "run completion.json is absent")
    completion = read_json(completion_path)

    lineage_checks: dict[str, bool] = {
        "handoff_passed": handoff.get("passed") is True,
        "handoff_status": handoff.get("status") == "stage111_gpu_execution_authorized",
        "handoff_design_binding": handoff.get("bindings", {}).get("design_sha256") == sha256(design_path),
        "run_completion_passed": completion.get("passed") is True,
        "run_completion_status": completion.get("status") == "complete_solver_passed_pending_independent_evaluation",
        "run_design_binding": completion.get("design_sha256") == sha256(design_path),
        "run_handoff_binding": completion.get("handoff_sha256") == sha256(handoff_path),
        "run_runner_binding": completion.get("runner_sha256") == handoff.get("bindings", {}).get("runner_sha256"),
        "no_failure_marker": not (run / "failure.json").exists(),
        "three_declared_cases": len(design.get("cases", [])) == 3,
    }
    for name, item in design.get("lineage", {}).items():
        if isinstance(item, dict) and "path" in item and "sha256" in item:
            lineage_checks[f"lineage_{name}"] = Path(item["path"]).is_file() and sha256(item["path"]) == item["sha256"]

    with np.load(design["geometry"]) as geometry:
        geometry_phase = geometry["phase"]
        spacing_m = float(geometry["spacing_m"][0])
        median_grain_diameter_lu = float(np.median(2.0 * geometry["sand_radii_m"]) / spacing_m)
    with np.load(design["archived_field"]) as archive:
        archived_phase = archive["phase"]
        archived_velocity = archive["velocity_xyz_lu"]
    require(np.array_equal(geometry_phase, archived_phase), "archived field phase is not the frozen geometry")
    fluid = geometry_phase == 0

    thresholds = design["evaluation"]
    nu_lu = float(design["solver"]["kinematic_viscosity_lu"])
    case_results: list[dict] = []
    direct_passes: list[bool] = []
    reuse_passes: list[bool] = []
    achieved_means: list[float] = []
    normalized_direct_fields: list[np.ndarray] = []

    for case in design["cases"]:
        case_id = case["case_id"]
        case_dir = run / case_id
        record_path = case_dir / "record.json"
        fields_path = case_dir / "final_fields.npz"
        require(record_path.is_file() and fields_path.is_file(), f"missing record/field bundle for {case_id}")
        record = read_json(record_path)
        record_binding = completion.get("case_records", {}).get(case_id) == sha256(record_path)
        artifact_checks = {
            "final_fields": record.get("artifacts", {}).get("final_fields_npz_sha256") == sha256(fields_path),
            "audit": record.get("artifacts", {}).get("audit_npz_sha256") == sha256(case_dir / "audit.npz"),
            "vtk": record.get("artifacts", {}).get("final_flow_vtk_sha256") == sha256(case_dir / "final_flow.vtk"),
            "shifted_state": record.get("artifacts", {}).get("final_shifted_state_npz_sha256") == sha256(case_dir / "final_shifted_state.npz"),
        }
        with np.load(fields_path) as direct_npz:
            phase = direct_npz["phase"]
            velocity = direct_npz["velocity_xyz_lu"]
        require(np.array_equal(phase, geometry_phase), f"phase mismatch for {case_id}")
        profile = normalized_profile_metrics(archived_velocity, velocity, fluid)
        mean_u = profile["direct_mean_interstitial_velocity_lu"]
        achieved_re = mean_u * median_grain_diameter_lu / nu_lu
        target_re = float(case["target_physical_median_grain_Re"])
        re_relative_error = abs(achieved_re - target_re) / target_re
        achieved_means.append(mean_u)
        normalized_direct_fields.append(velocity[:, fluid].astype(np.float64) / mean_u)

        health = {
            "record_binding": record_binding,
            "all_artifacts_bound": all(artifact_checks.values()),
            "record_passed": record.get("passed") is True,
            "record_converged": record.get("converged") is True,
            "all_record_checks": bool(record.get("checks")) and all(record["checks"].values()),
            "fatal_health_zero": record.get("final", {}).get("fatal_health_code") == 0,
            "full_health_zero": record.get("final", {}).get("full_health_code") == 0,
            "finite_velocity": bool(np.all(np.isfinite(velocity))),
            "positive_flow": mean_u > 0.0,
            "target_Re": re_relative_error <= float(thresholds["target_mean_Re_relative_error_max"]),
        }
        reuse = {
            "rms_profile": profile["rms_difference_over_direct_rms"] <= float(thresholds["scaled_reuse_profile_rms_over_direct_rms_max"]),
            "p95_profile": profile["p95_vector_difference_over_mean_speed"] <= float(thresholds["scaled_reuse_profile_p95_over_mean_speed_max"]),
        }
        direct_passes.append(all(health.values()))
        reuse_passes.append(all(reuse.values()))
        case_results.append({
            "case_id": case_id,
            "flow_factor": case["flow_factor"],
            "target_physical_median_grain_Re": target_re,
            "achieved_mean_grain_Re": achieved_re,
            "target_Re_relative_error": re_relative_error,
            "record_superficial_velocity_lu": record["final"]["superficial_velocity_lu"],
            "profile_against_archived_low_Re": profile,
            "artifact_checks": artifact_checks,
            "direct_checks": health,
            "scaled_reuse_checks": reuse,
            "direct_passed": all(health.values()),
            "scaled_reuse_passed": all(reuse.values()),
        })

    flow_ordering = all(achieved_means[i] < achieved_means[i + 1] for i in range(2))
    pairwise = []
    for i in range(2):
        delta = np.linalg.norm(normalized_direct_fields[i + 1] - normalized_direct_fields[i], axis=0)
        baseline_mag = np.linalg.norm(normalized_direct_fields[i], axis=0)
        pairwise.append({
            "lower_case": design["cases"][i]["case_id"],
            "upper_case": design["cases"][i + 1]["case_id"],
            "rms_difference_over_lower_rms": float(np.sqrt(np.mean(delta * delta)) / np.sqrt(np.mean(baseline_mag * baseline_mag))),
            "p95_difference_over_mean_speed": float(np.percentile(delta, 95.0)),
        })

    lineage_passed = all(lineage_checks.values())
    direct_passed = lineage_passed and all(direct_passes) and flow_ordering
    scaled_reuse_passed = direct_passed and all(reuse_passes)
    if not direct_passed:
        status = "complete_failed_direct_flow_validation"
    elif scaled_reuse_passed:
        status = "complete_passed_scaled_field_reuse_supported_seed2_cpd2"
    else:
        status = "complete_passed_direct_fields_required_seed2_cpd2"

    results = {
        "schema": "matdem.stage111.flow-validation.independent-evaluation.v1",
        "status": status,
        "passed": direct_passed,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "claim_boundary": design["claim_boundary"],
        "decision": {
            "direct_flow_validation_passed": direct_passed,
            "scaled_archived_field_reuse_passed": scaled_reuse_passed,
            "particle_transport_authorized": False,
            "campaign_authorized": False,
        },
        "geometry": {
            "fluid_voxels": int(np.count_nonzero(fluid)),
            "spacing_m": spacing_m,
            "median_grain_diameter_lu": median_grain_diameter_lu,
            "kinematic_viscosity_lu": nu_lu,
        },
        "thresholds": thresholds,
        "lineage_checks": lineage_checks,
        "flow_ordering_passed": flow_ordering,
        "cases": case_results,
        "pairwise_direct_normalized_profiles": pairwise,
        "bindings": {
            "design_sha256": sha256(design_path),
            "handoff_sha256": sha256(handoff_path),
            "run_completion_sha256": sha256(completion_path),
            "evaluator_sha256": sha256(__file__),
        },
    }
    write_json(output / "results.json", results)
    write_json(output / "completion.json", {
        "schema": "matdem.stage111.flow-validation.evaluation-completion.v1",
        "status": status,
        "passed": direct_passed,
        "results_sha256": sha256(output / "results.json"),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    })
    print(json.dumps({"status": status, "direct_passed": direct_passed,
                      "scaled_reuse_passed": scaled_reuse_passed}, sort_keys=True))
    return 0 if direct_passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
