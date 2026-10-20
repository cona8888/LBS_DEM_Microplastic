from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage31f_selected_replicated_cpd4_20260827"
RUN = ROOT / "stage31_runs" / STUDY / "gpu_confirmation_01"
SUPERVISOR = ROOT / "stage31_runs" / STUDY / "gpu_confirmation_01_supervisor"
CONFIG = ROOT / "stage31_designs" / STUDY / "geometry_01/resolved_config.json"
GEOMETRY_COMPLETION = CONFIG.parent / "completion.json"
DESIGN_AUDIT = ROOT / "stage31_evaluations" / STUDY / "design_audit_01/design_audit.json"
RELEASE_AUDIT = ROOT / "stage31_evaluations" / STUDY / "execution_release_01/release_audit.json"
HANDOFF = RELEASE_AUDIT.parent / "handoff.json"
RUNNER = ROOT / "stage31_staging/run_stage31f_selected_replicated_cpd4_gpu_v1.py"
STAGE30_COMPLETION = ROOT / "stage30_runs/stage30a_selected_low_concentration_cpd4_20260826/gpu_confirmation_01/completion.json"
STAGE30_EVALUATION = ROOT / "stage30_evaluations/stage30a_selected_low_concentration_cpd4_20260826/gpu_evaluation_01/evaluation.json"
OUT = ROOT / "stage31_evaluations" / STUDY / "gpu_evaluation_02"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def finite_tree(value: object) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, list):
        return all(finite_tree(x) for x in value)
    if isinstance(value, dict):
        return all(finite_tree(x) for x in value.values())
    return False


def main() -> int:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")

    completion_path = RUN / "completion.json"
    config, geometry_done, design, release, handoff, completion = map(
        load, (CONFIG, GEOMETRY_COMPLETION, DESIGN_AUDIT, RELEASE_AUDIT, HANDOFF, completion_path)
    )
    stage30_done, stage30_eval = map(load, (STAGE30_COMPLETION, STAGE30_EVALUATION))
    rows = {row["case_id"]: row for row in completion["paired_results"]}
    order = tuple(case["case_id"] for case in config["geometry"]["cases"])

    lineage_checks = {}
    for key, binding in config["lineage"].items():
        if isinstance(binding, dict) and "path" in binding and "sha256" in binding:
            path = Path(binding["path"])
            lineage_checks[key] = (
                path.is_file()
                and sha(path) == binding["sha256"]
                and completion["lineage_hashes"].get(key) == binding["sha256"]
            )

    geometry_checks = {}
    for case_id, binding in config["geometry"]["artifacts"].items():
        checks = {}
        for path_key, hash_key in (
            ("geometry", "geometry_sha256"),
            ("material_vtk", "material_vtk_sha256"),
            ("source_cpd2_geometry", "source_cpd2_geometry_sha256"),
        ):
            path = Path(binding[path_key])
            checks[path_key] = path.is_file() and sha(path) == binding[hash_key]
        geometry_checks[case_id] = {"passed": all(checks.values()), "checks": checks}

    artifact_names = {
        "audit_npz_sha256": "audit.npz",
        "final_fields_npz_sha256": "final_fields.npz",
        "final_flow_vtk_sha256": "final_flow.vtk",
        "final_shifted_state_npz_sha256": "final_shifted_state.npz",
    }
    warm_bindings = config["cpd2_reference"]["warm_starts"]
    case_checks = {}
    recomputed_rows = []
    for case_id in order:
        row = rows[case_id]
        case_dir = RUN / row["solver_case_id"]
        record_path = case_dir / "record.json"
        record = load(record_path)
        artifacts = {
            filename: (case_dir / filename).is_file()
            and sha(case_dir / filename) == record["artifacts"][hash_key]
            for hash_key, filename in artifact_names.items()
        }
        closure_exact = all(
            int(value) == 0
            for key, values in record["exact_equilibrium_closure"].items()
            if key.endswith("numerator_xyz")
            for value in values
        )
        warm = record["initialization"]
        frozen_warm = warm_bindings[case_id]
        warm_path = Path(warm["path"])
        conductance = float(record["final"]["superficial_velocity_lu"]) / float(record["acceleration_lu"])
        clean = (
            float(config["reused_s1_clean_cpd4"]["conductance_proxy_lu"])
            if row["packing_id"] == "n216_s1"
            else float(rows["s31b_n216_s2_clean"]["conductance_proxy_lu"])
        )
        ratio = conductance / clean
        checks = {
            "record_hash_bound": sha(record_path) == row["record_sha256"] == completion["case_records"][case_id],
            "case_id_bound": record["case_id"] == row["solver_case_id"],
            "cpd4_dimensions": record["cpd"] == 4 and record["dimensions_lu"] == [186, 186, 186],
            "stage_bound": record["stage"] == "STAGE31F_SELECTED_REPLICATED_CPD4_SOLUTION_VERIFICATION",
            "passed_and_converged": record.get("passed") is True and record.get("converged") is True,
            "all_solver_checks_true": all(record.get("checks", {}).values()),
            "numerical_health_zero": all(int(v) == 0 for v in record["numerical_health"].values())
            and all(int(record["final"][k]) == 0 for k in ("fatal_health_code", "full_health_code", "reporting_only_health_code")),
            "exact_equilibrium_closure": closure_exact,
            "finite_record_values": finite_tree(record),
            "positive_flow": conductance > 0.0 and record["final"]["superficial_velocity_lu"] > 0.0,
            "step_binding": record["steps_completed"] == row["steps_completed"] == 88000,
            "conductance_recomputed": math.isclose(conductance, row["conductance_proxy_lu"], rel_tol=0.0, abs_tol=1e-14),
            "paired_ratio_recomputed": math.isclose(ratio, row["paired_permeability_ratio"], rel_tol=0.0, abs_tol=1e-14),
            "warm_start_bound": all(warm.get(key) == value for key, value in frozen_warm.items())
            and warm.get("mode") == "resampled_local_equilibrium_from_verified_lower_resolution"
            and warm_path.is_file() and sha(warm_path) == warm["sha256"],
            "artifact_hashes": all(artifacts.values()),
        }
        case_checks[case_id] = {
            "passed": all(checks.values()),
            "checks": checks,
            "artifact_checks": artifacts,
            "momentum_residual_relative": record["final"]["momentum_residual_relative"],
            "mach_number": record["metrics"]["mach_number"],
            "reynolds_number_diameter": record["metrics"]["reynolds_number_diameter"],
        }
        recomputed_rows.append({**row, "recomputed_conductance_proxy_lu": conductance, "recomputed_ratio": ratio})

    reused = config["reused_s1_clean_cpd4"]
    reused_checks = {
        key: Path(binding["path"]).is_file() and sha(Path(binding["path"])) == binding["sha256"]
        for key, binding in reused.items()
        if isinstance(binding, dict) and "path" in binding
    }
    reused_record = load(Path(reused["record"]["path"]))
    reused_checks["conductance_exact"] = math.isclose(
        reused_record["final"]["superficial_velocity_lu"] / reused_record["acceleration_lu"],
        reused["conductance_proxy_lu"], rel_tol=0.0, abs_tol=1e-14,
    )
    reused_checks["accepted_stage30_chain"] = stage30_done.get("passed") is True and stage30_eval.get("passed") is True

    contrasts = completion["contrasts"]
    nonclean = [row for row in recomputed_rows if row["fibre_count"] > 0]
    checks = {
        "completion_passed": completion.get("passed") is True and all(completion["checks"].values()),
        "config_runner_handoff_bound": completion["config_sha256"] == sha(CONFIG)
        and completion["runner_sha256"] == sha(RUNNER)
        and completion["handoff_sha256"] == sha(HANDOFF)
        and handoff["bindings"]["runner_sha256"] == sha(RUNNER),
        "preflight_chain_passed": geometry_done.get("passed") is True and design.get("passed") is True
        and release.get("passed") is True and handoff.get("passed") is True,
        "preflight_hash_chain_bound": design["bindings"]["config"]["sha256"] == sha(CONFIG)
        and release["bindings"]["design_audit_sha256"] == sha(DESIGN_AUDIT)
        and handoff["bindings"]["release_audit_sha256"] == sha(RELEASE_AUDIT)
        and handoff["bindings"]["geometry_completion_sha256"] == sha(GEOMETRY_COMPLETION),
        "all_lineage_bound": bool(lineage_checks) and all(lineage_checks.values()),
        "all_geometry_bound": len(geometry_checks) == 7 and all(v["passed"] for v in geometry_checks.values()),
        "all_seven_case_bundles_pass": len(case_checks) == 7 and all(v["passed"] for v in case_checks.values()),
        "reused_s1_clean_hash_bound": all(reused_checks.values()),
        "new_s2_clean_exact": rows["s31b_n216_s2_clean"]["paired_permeability_ratio"] == 1.0,
        "selected_ratio_shifts_within_0p002": all(abs(row["cpd2_to_cpd4_ratio_shift"]) <= 0.002 for row in recomputed_rows),
        "all_selected_obstructive": all(row["paired_permeability_ratio"] < 1.0 for row in nonclean),
        "both_block_contrast_shifts_within_0p001": all(abs(v["cpd2_to_cpd4_contrast_shift"]) <= 0.001 for v in contrasts.values()),
        "opposite_block_contrast_signs_preserved": contrasts["n216_s1"]["cpd2_B_minus_A"] > 0
        and contrasts["n216_s1"]["cpd4_B_minus_A"] > 0
        and contrasts["n216_s2"]["cpd2_B_minus_A"] < 0
        and contrasts["n216_s2"]["cpd4_B_minus_A"] < 0,
        "completion_status_exact": completion["status"] == "passed_selected_replicated_cpd4_solution_verification",
        "stderr_empty": (SUPERVISOR / "stderr.log").is_file() and (SUPERVISOR / "stderr.log").stat().st_size == 0,
        "no_failure_marker": not any(RUN.rglob("failure.json")) and not any(SUPERVISOR.rglob("failure.json")),
        "authority_boundary_preserved": all(
            completion["authority"][key] is False
            for key in ("absolute_permeability_validation_claim", "mechanics_rerun", "mobile_sand", "migration", "clogging", "deformation", "transient_coupling", "two_way_coupling")
        ),
    }
    passed = all(checks.values())
    evaluation = {
        "schema": "lbs.stage31f-selected-replicated-cpd4-independent-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_selected_replicated_cpd4_solution_verification" if passed else "failed_selected_replicated_cpd4_solution_verification",
        "checks": checks,
        "lineage_checks": lineage_checks,
        "geometry_checks": geometry_checks,
        "reused_s1_clean_checks": reused_checks,
        "case_checks": case_checks,
        "paired_results": recomputed_rows,
        "contrasts": contrasts,
        "maximum_absolute_ratio_shift": max(abs(row["cpd2_to_cpd4_ratio_shift"]) for row in recomputed_rows),
        "maximum_absolute_contrast_shift": max(abs(v["cpd2_to_cpd4_contrast_shift"]) for v in contrasts.values()),
        "interpretation": "Selected replicated count and placement-block responses retain their obstruction and block-contrast signs from CPD2 to CPD4. The four-fibre block effect remains packing-dependent, with opposite signs in s1 and s2.",
        "claim_boundary": completion["claim_boundary"],
        "bindings": {
            "completion_sha256": sha(completion_path), "config_sha256": sha(CONFIG),
            "runner_sha256": sha(RUNNER), "handoff_sha256": sha(HANDOFF),
            "design_audit_sha256": sha(DESIGN_AUDIT), "release_audit_sha256": sha(RELEASE_AUDIT),
            "geometry_completion_sha256": sha(GEOMETRY_COMPLETION),
        },
        "authority": {
            "rendering": passed, "absolute_permeability_validation_claim": False,
            "mechanics_rerun": False, "mobile_sand": False, "migration": False,
            "clogging": False, "deformation": False, "transient_coupling": False, "two_way_coupling": False,
        },
    }
    OUT.mkdir(parents=True)
    evaluation_path = OUT / "evaluation.json"
    evaluation_path.write_text(json.dumps(evaluation, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    checkpoint = {
        "schema": evaluation["schema"] + ".checkpoint", "passed": passed,
        "evaluation_sha256": sha(evaluation_path), "completion_sha256": sha(completion_path),
        "config_sha256": sha(CONFIG), "runner_sha256": sha(RUNNER),
        "authority": {"authorized": "render selected Stage31f CPD4 evidence" if passed else "diagnosis only"},
    }
    (OUT / "checkpoint_manifest.json").write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "passed": passed, "checks": checks,
                      "maximum_absolute_ratio_shift": evaluation["maximum_absolute_ratio_shift"],
                      "maximum_absolute_contrast_shift": evaluation["maximum_absolute_contrast_shift"]}, indent=2))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
