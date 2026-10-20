"""Independently evaluate Stage112 clean packing and spatial-flow evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def sha(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path: Path | str) -> dict:
    return json.loads(Path(path).read_text())


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def artifact_checks(case_dir: Path, record: dict) -> dict:
    mapping = {
        "audit": ("audit.npz", "audit_npz_sha256"),
        "final_fields": ("final_fields.npz", "final_fields_npz_sha256"),
        "shifted_state": ("final_shifted_state.npz", "final_shifted_state_npz_sha256"),
        "vtk": ("final_flow.vtk", "final_flow_vtk_sha256"),
    }
    return {name: (case_dir / filename).is_file() and sha(case_dir / filename) == record.get("artifacts", {}).get(key)
            for name, (filename, key) in mapping.items()}


def direct_case(case: dict, case_dir: Path, completion: dict, nu: float, re_tol: float) -> dict:
    record_path = case_dir / "record.json"
    require(record_path.is_file(), f"missing record: {case['case_id']}")
    record = read(record_path)
    with np.load(case_dir / "final_fields.npz") as fields, np.load(case["geometry"]) as geometry:
        require(np.array_equal(fields["phase"], geometry["phase"]), f"phase mismatch: {case['case_id']}")
        fluid = fields["phase"] == 0
        mean_u = float(np.mean(fields["velocity_xyz_lu"][0][fluid], dtype=np.float64))
        finite = bool(np.all(np.isfinite(fields["velocity_xyz_lu"])))
        diameter_lu = float(np.median(2.0 * geometry["sand_radii_m"]) / geometry["spacing_m"][0])
    achieved_re = mean_u * diameter_lu / nu
    target_re = float(case["target_physical_median_grain_Re"])
    re_error = abs(achieved_re - target_re) / target_re
    artifacts = artifact_checks(case_dir, record)
    checks = {
        "record_completion_binding": completion.get("case_records", {}).get(case["case_id"]) == sha(record_path),
        "record_passed": record.get("passed") is True,
        "record_converged": record.get("converged") is True,
        "all_record_checks": bool(record.get("checks")) and all(record["checks"].values()),
        "fatal_health_zero": record.get("final", {}).get("fatal_health_code") == 0,
        "full_health_zero": record.get("final", {}).get("full_health_code") == 0,
        "exact_equilibrium_closure": all(all(v == 0 for v in values) for values in record.get("exact_equilibrium_closure", {}).values()),
        "artifacts_bound": all(artifacts.values()),
        "finite_velocity": finite,
        "positive_mean_flow": mean_u > 0.0,
        "target_Re": re_error <= re_tol,
    }
    return {
        "case_id": case["case_id"], "packing_seed": case["packing_seed"], "cpd": case["cpd"],
        "target_mean_grain_Re": target_re, "achieved_mean_grain_Re": achieved_re,
        "target_Re_relative_error": re_error, "mean_interstitial_velocity_lu": mean_u,
        "dimensionless_mobility": record["metrics"]["dimensionless_mobility"],
        "wall_seconds": record["performance"]["wall_seconds"], "steps_completed": record["steps_completed"],
        "artifact_checks": artifacts, "checks": checks, "passed": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", type=Path, required=True)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    design_path, handoff_path, run, output = (p.resolve() for p in (args.design, args.handoff, args.run, args.output))
    require(not output.exists(), f"refusing to overwrite immutable output: {output}")
    completion_path = run / "completion.json"
    require(completion_path.is_file(), "Stage112 completion missing")
    design, handoff, completion = read(design_path), read(handoff_path), read(completion_path)
    lineage_checks = {
        "handoff_passed": handoff.get("passed") is True,
        "handoff_status": handoff.get("status") == "stage112_gpu_execution_authorized",
        "handoff_design_binding": handoff.get("bindings", {}).get("design_sha256") == sha(design_path),
        "completion_passed": completion.get("passed") is True,
        "completion_status": completion.get("status") == "complete_solver_passed_pending_independent_evaluation",
        "completion_design_binding": completion.get("design_sha256") == sha(design_path),
        "completion_handoff_binding": completion.get("handoff_sha256") == sha(handoff_path),
        "completion_runner_binding": completion.get("runner_sha256") == handoff.get("bindings", {}).get("runner_sha256"),
        "no_failure_marker": not (run / "failure.json").exists(),
    }
    for name, item in design["lineage"].items():
        if isinstance(item, dict) and "path" in item and "sha256" in item:
            lineage_checks["lineage_" + name] = Path(item["path"]).is_file() and sha(item["path"]) == item["sha256"]

    nu = float(design["solver"]["kinematic_viscosity_lu"])
    re_tol = float(design["evaluation"]["target_mean_Re_relative_error_max"])
    cases = [direct_case(case, run / case["case_id"], completion, nu, re_tol) for case in design["cases"]]

    reference = design["reference_cpd2"]
    reference_record = read(reference["record"])
    require(sha(reference["record"]) == reference["record_sha256"] and sha(reference["field"]) == reference["field_sha256"],
            "Stage111 seed-2 reference drift")
    cpd2_mobilities = [cases[0]["dimensionless_mobility"], reference_record["metrics"]["dimensionless_mobility"],
                       cases[1]["dimensionless_mobility"]]
    cpd2_mean = float(np.mean(cpd2_mobilities))
    packing = {
        "seed_order": [1, 2, 3],
        "dimensionless_mobilities": cpd2_mobilities,
        "mean": cpd2_mean,
        "sample_standard_deviation": float(np.std(cpd2_mobilities, ddof=1)),
        "coefficient_of_variation": float(np.std(cpd2_mobilities, ddof=1) / cpd2_mean),
        "relative_range_over_mean": float((max(cpd2_mobilities) - min(cpd2_mobilities)) / cpd2_mean),
        "interpretation": "Measured three-packing spread; no population-level universal estimate is claimed.",
    }

    stage111_design = read(design["lineage"]["stage111_design"]["path"])
    geometry2_path = Path(stage111_design["geometry"])
    geometry4_path = Path(design["cases"][2]["geometry"])
    field2_path = Path(reference["field"])
    field4_path = run / design["cases"][2]["case_id"] / "final_fields.npz"
    with np.load(geometry2_path) as g2, np.load(geometry4_path) as g4, np.load(field2_path) as f2, np.load(field4_path) as f4:
        require(g4["phase"].shape == tuple(2 * n for n in g2["phase"].shape), "CPD4 is not exact 2x grid")
        require(np.array_equal(g2["sand_centres_m"], g4["sand_centres_m"]), "grain centres differ")
        require(np.array_equal(g2["sand_radii_m"], g4["sand_radii_m"]), "grain radii differ")
        fluid2, fluid4 = g2["phase"] == 0, g4["phase"] == 0
        n = g2["phase"].shape[0]
        full_fluid4 = fluid4.reshape(n, 2, n, 2, n, 2).all(axis=(1, 3, 5))
        mask = fluid2 & full_fluid4
        v2 = f2["velocity_xyz_lu"].astype(np.float64)
        v4 = f4["velocity_xyz_lu"].astype(np.float64)
        v2 /= float(np.mean(v2[0, fluid2]))
        v4 /= float(np.mean(v4[0, fluid4]))
        v4_mean = v4.reshape(3, n, 2, n, 2, n, 2).mean(axis=(2, 4, 6))
        delta = np.linalg.norm(v2[:, mask] - v4_mean[:, mask], axis=0)
        base = np.linalg.norm(v4_mean[:, mask], axis=0)
    m2 = float(reference_record["metrics"]["dimensionless_mobility"])
    m4 = float(cases[2]["dimensionless_mobility"])
    mobility_shift = abs(m4 / m2 - 1.0)
    spatial = {
        "common_fully_fluid_cpd2_cells": int(mask.sum()),
        "common_fraction_of_cpd2_fluid": float(mask.sum() / fluid2.sum()),
        "rms_vector_difference_over_rms_cpd4_speed": float(np.sqrt(np.mean(delta * delta) / np.mean(base * base))),
        "median_vector_difference_over_mean_speed": float(np.median(delta)),
        "p90_vector_difference_over_mean_speed": float(np.quantile(delta, 0.90)),
        "p99_vector_difference_over_mean_speed": float(np.quantile(delta, 0.99)),
        "cpd2_dimensionless_mobility": m2, "cpd4_dimensionless_mobility": m4,
        "absolute_relative_mobility_shift": mobility_shift,
        "gross_mobility_shift_passed": mobility_shift <= float(design["evaluation"]["gross_dimensionless_mobility_relative_shift_max"]),
        "interpretation": design["evaluation"]["spatial_profile_rule"],
    }

    direct_passed = all(lineage_checks.values()) and all(case["passed"] for case in cases)
    gross_spatial_passed = spatial["gross_mobility_shift_passed"]
    passed = direct_passed and gross_spatial_passed
    if not direct_passed:
        status = "complete_failed_direct_flow_or_lineage"
    elif not gross_spatial_passed:
        status = "complete_direct_flows_healthy_spatial_resolution_failed"
    else:
        status = "complete_direct_flows_healthy_spatial_error_quantified_transport_resolution_required"
    results = {
        "schema": "matdem.stage112.flow-resolution-packing.independent-evaluation.v1",
        "status": status, "passed": passed, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "claim_boundary": design["claim_boundary"], "lineage_checks": lineage_checks,
        "cases": cases, "packing_variability": packing, "spatial_resolution": spatial,
        "decision": {"direct_reference_fields_passed": direct_passed,
                     "gross_spatial_mobility_gate_passed": gross_spatial_passed,
                     "matched_transport_resolution_still_required": True,
                     "particle_transport_authorized": False, "campaign_authorized": False},
        "bindings": {"design_sha256": sha(design_path), "handoff_sha256": sha(handoff_path),
                     "run_completion_sha256": sha(completion_path), "evaluator_sha256": sha(__file__)},
    }
    output.mkdir(parents=True, exist_ok=False)
    write(output / "results.json", results)
    write(output / "completion.json", {"schema": "matdem.stage112.evaluation-completion.v1",
                                        "status": status, "passed": passed,
                                        "results_sha256": sha(output / "results.json"),
                                        "timestamp_utc": datetime.now(timezone.utc).isoformat()})
    print(json.dumps({"status": status, "passed": passed,
                      "packing_cv": packing["coefficient_of_variation"],
                      "spatial_rms": spatial["rms_vector_difference_over_rms_cpd4_speed"],
                      "mobility_shift": mobility_shift}, sort_keys=True))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
