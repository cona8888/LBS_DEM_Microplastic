from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage30a_selected_low_concentration_cpd4_20260826"
RUN = ROOT / "stage30_runs" / STUDY / "gpu_confirmation_01"
CONFIG = ROOT / "stage30_designs" / STUDY / "geometry_01/resolved_config.json"
GEOMETRY_COMPLETION = CONFIG.parent / "completion.json"
DESIGN_AUDIT = ROOT / "stage30_evaluations" / STUDY / "design_audit_02/design_audit.json"
RELEASE_AUDIT = ROOT / "stage30_evaluations" / STUDY / "gpu_release_audit_01/audit.json"
HANDOFF = RELEASE_AUDIT.parent / "execution_handoff.json"
RUNNER = ROOT / "stage30_staging/run_stage30a_selected_low_concentration_cpd4_gpu_v1.py"
STAGE28_COMPLETION = ROOT / "stage28_runs/stage28c_selected_two_fibre_cpd4_20260825/gpu_confirmation_01/completion.json"
STAGE28_EVALUATION = ROOT / "stage28_evaluations/stage28c_selected_two_fibre_cpd4_20260825/gpu_evaluation_01/evaluation.json"
STAGE28_CHECKPOINT = STAGE28_EVALUATION.parent / "checkpoint_manifest.json"
OUT = ROOT / "stage30_evaluations" / STUDY / "gpu_evaluation_01"


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
    config, geometry_done, design, release, handoff, completion = map(load, (CONFIG, GEOMETRY_COMPLETION, DESIGN_AUDIT, RELEASE_AUDIT, HANDOFF, completion_path))
    stage28_done, stage28_eval, stage28_checkpoint = map(load, (STAGE28_COMPLETION, STAGE28_EVALUATION, STAGE28_CHECKPOINT))
    rows = {row["case_id"]: row for row in completion["paired_results"]}
    order = ("clean", "s29e_f001_isolated_B", "s29e_f004_zero_contact_context_B", "s29e_f004_one_contact_context_B")
    lineage_checks = {}
    for key, binding in config["lineage"].items():
        if isinstance(binding, dict) and "path" in binding and "sha256" in binding:
            path = Path(binding["path"])
            lineage_checks[key] = path.is_file() and sha(path) == binding["sha256"] == completion["lineage_hashes"].get(key)
    geometry_checks = {case: Path(v["geometry"]).is_file() and sha(Path(v["geometry"])) == v["geometry_sha256"] for case, v in config["geometry"]["artifacts"].items()}
    case_checks = {}
    artifacts = {"audit_npz_sha256": "audit.npz", "final_fields_npz_sha256": "final_fields.npz",
                 "final_flow_vtk_sha256": "final_flow.vtk", "final_shifted_state_npz_sha256": "final_shifted_state.npz"}
    for case_id in order:
        row = rows[case_id]
        case_dir = RUN / row["solver_case_id"]
        record_path = case_dir / "record.json"
        record = load(record_path)
        artifact_checks = {filename: (case_dir / filename).is_file() and sha(case_dir / filename) == record["artifacts"][key] for key, filename in artifacts.items()}
        closure_exact = all(int(v) == 0 for key, values in record["exact_equilibrium_closure"].items() if key.endswith("numerator_xyz") for v in values)
        checks = {
            "record_hash_bound": sha(record_path) == row["record_sha256"] == completion["case_records"][case_id],
            "case_id_bound": record["case_id"] == row["solver_case_id"],
            "cpd4": record["cpd"] == 4 and record["dimensions_lu"] == [186, 186, 186],
            "passed_and_converged": record.get("passed") is True and record.get("converged") is True,
            "all_solver_checks_true": all(record.get("checks", {}).values()),
            "numerical_health_zero": all(int(v) == 0 for v in record["numerical_health"].values())
            and record["final"]["fatal_health_code"] == 0 and record["final"]["full_health_code"] == 0
            and record["final"]["reporting_only_health_code"] == 0,
            "exact_equilibrium_closure": closure_exact,
            "finite_record_values": finite_tree(record),
            "positive_flow": record["final"]["superficial_velocity_lu"] > 0 and row["conductance_proxy_lu"] > 0,
            "step_binding": record["steps_completed"] == row["steps_completed"] == 88000,
            "artifact_hashes": all(artifact_checks.values()),
        }
        case_checks[case_id] = {"passed": all(checks.values()), "checks": checks, "artifact_checks": artifact_checks,
        "momentum_residual_relative": record["final"]["momentum_residual_relative"], "mach_number": record["metrics"]["mach_number"],
        "reynolds_number_diameter": record["metrics"]["reynolds_number_diameter"]}
    stage28_rows = {row["case_id"]: row for row in stage28_done["paired_results"]}
    combined = [
        {"label": "clean", "fibre_count": 0, "topology": "clean", "dry_mass_percent": 0.0, "cpd2_ratio": rows["clean"]["cpd2_ratio"], "cpd4_ratio": rows["clean"]["paired_permeability_ratio"]},
        {"label": "1 isolated B", "fibre_count": 1, "topology": "single_isolated", "dry_mass_percent": 0.004690960879927048, "cpd2_ratio": rows["s29e_f001_isolated_B"]["cpd2_ratio"], "cpd4_ratio": rows["s29e_f001_isolated_B"]["paired_permeability_ratio"]},
        {"label": "2 separated", "fibre_count": 2, "topology": "separated", "dry_mass_percent": 0.009381481678218612, "cpd2_ratio": stage28_rows["separated_open_open"]["cpd2_ratio"], "cpd4_ratio": stage28_rows["separated_open_open"]["paired_permeability_ratio"]},
        {"label": "2 crossing", "fibre_count": 2, "topology": "crossing", "dry_mass_percent": 0.009381481678218612, "cpd2_ratio": stage28_rows["crossing_interaction"]["cpd2_ratio"], "cpd4_ratio": stage28_rows["crossing_interaction"]["paired_permeability_ratio"]},
        {"label": "4 zero contact B", "fibre_count": 4, "topology": "zero_contact", "dry_mass_percent": 0.018761203277589126, "cpd2_ratio": rows["s29e_f004_zero_contact_context_B"]["cpd2_ratio"], "cpd4_ratio": rows["s29e_f004_zero_contact_context_B"]["paired_permeability_ratio"]},
        {"label": "4 one contact B", "fibre_count": 4, "topology": "one_contact", "dry_mass_percent": 0.018761203277589126, "cpd2_ratio": rows["s29e_f004_one_contact_context_B"]["cpd2_ratio"], "cpd4_ratio": rows["s29e_f004_one_contact_context_B"]["paired_permeability_ratio"]},
    ]
    for item in combined:
        item["cpd2_to_cpd4_shift"] = item["cpd4_ratio"] - item["cpd2_ratio"]
    two_cpd2 = stage28_rows["crossing_interaction"]["cpd2_ratio"] - stage28_rows["separated_open_open"]["cpd2_ratio"]
    two_cpd4 = stage28_rows["crossing_interaction"]["paired_permeability_ratio"] - stage28_rows["separated_open_open"]["paired_permeability_ratio"]
    four_cpd2 = completion["contrasts"]["cpd2_one_minus_zero"]
    four_cpd4 = completion["contrasts"]["cpd4_one_minus_zero"]
    checks = {
        "completion_passed": completion.get("passed") is True and all(completion["checks"].values()),
        "config_runner_handoff_bound": completion["config_sha256"] == sha(CONFIG) and completion["runner_sha256"] == sha(RUNNER)
        and completion["handoff_sha256"] == sha(HANDOFF) and handoff["bindings"]["runner_sha256"] == sha(RUNNER),
        "preflight_chain_passed": geometry_done.get("passed") is True and design.get("passed") is True and release.get("passed") is True and handoff.get("passed") is True,
        "all_lineage_bound": all(lineage_checks.values()), "all_geometry_bound": all(geometry_checks.values()),
        "all_four_case_bundles_pass": len(case_checks) == 4 and all(v["passed"] for v in case_checks.values()),
        "clean_reproduced_exactly": completion["clean_reproduction_relative_error"] == 0.0,
        "selected_ratio_shifts_within_0p002": all(abs(item["cpd2_to_cpd4_shift"]) <= 0.002 for item in combined),
        "stage28c_reuse_hash_bound_and_passed": sha(STAGE28_COMPLETION) == completion["reused_stage28c_cpd4"]["completion_sha256"]
        and sha(STAGE28_EVALUATION) == completion["reused_stage28c_cpd4"]["evaluation_sha256"]
        and sha(STAGE28_CHECKPOINT) == completion["reused_stage28c_cpd4"]["checkpoint_sha256"]
        and stage28_done.get("passed") is True and stage28_eval.get("passed") is True and stage28_checkpoint.get("passed") is True,
        "all_fibre_cases_obstructive": all(item["cpd4_ratio"] < 1.0 for item in combined if item["fibre_count"] > 0),
        "two_fibre_crossing_more_obstructive": two_cpd4 < 0.0,
        "four_fibre_zero_more_obstructive": four_cpd4 > 0.0,
        "two_fibre_contrast_shift_within_0p001": abs(two_cpd4 - two_cpd2) <= 0.001,
        "four_fibre_contrast_shift_within_0p001": abs(four_cpd4 - four_cpd2) <= 0.001,
        "no_failure_marker": not any(RUN.rglob("failure.json")),
        "authority_boundary_preserved": all(completion["authority"][k] is False for k in ("permeability_validation_claim", "mechanics_rerun", "mobile_sand", "migration", "clogging", "two_way_coupling")),
    }
    passed = all(checks.values())
    evaluation = {"schema": "lbs.stage30a-selected-low-concentration-cpd4-independent-evaluation.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(), "passed": passed,
    "status": "passed_selected_cpd4_solution_verification" if passed else "failed_selected_cpd4_solution_verification",
    "checks": checks, "lineage_checks": lineage_checks, "geometry_checks": geometry_checks, "case_checks": case_checks,
    "combined_selected_evidence": combined, "contrasts": {
    "two_fibre_crossing_minus_separated": {"cpd2": two_cpd2, "cpd4": two_cpd4, "shift": two_cpd4 - two_cpd2},
    "four_fibre_one_minus_zero_B": {"cpd2": four_cpd2, "cpd4": four_cpd4, "shift": four_cpd4 - four_cpd2}},
    "maximum_absolute_ratio_shift": max(abs(item["cpd2_to_cpd4_shift"]) for item in combined),
    "interpretation": "All six selected clean/one-/two-/four-fibre mechanism points retain their obstruction signs at CPD4. The two-fibre crossing penalty and four-fibre paired contact relief retain opposite signs, so topology interacts with multi-fibre context rather than defining one universal contact rule.",
    "claim_boundary": "Selected CPD2-to-CPD4 solution verification in one fixed 216-grain periodic LBS packing; not laboratory validation, population inference, or a monotonic concentration law.",
    "bindings": {"completion_sha256": sha(completion_path), "config_sha256": sha(CONFIG), "runner_sha256": sha(RUNNER),
    "handoff_sha256": sha(HANDOFF), "stage28c_completion_sha256": sha(STAGE28_COMPLETION)},
    "authority": {"rendering": passed, "permeability_validation_claim": False, "mechanics_rerun": False,
    "mobile_sand": False, "migration": False, "clogging": False, "deformation": False, "transient_coupling": False, "two_way_coupling": False},
    "next_handoff": {"authorized": "render combined selected CPD4 solution-verification evidence" if passed else "diagnosis only",
    "not_authorized": "permeability validation claims, mechanics reruns, mobile sand, migration, clogging, deformation, transient coupling, or two-way coupling"}}
    OUT.mkdir(parents=True)
    ep = OUT / "evaluation.json"
    ep.write_text(json.dumps(evaluation, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    checkpoint = {"schema": evaluation["schema"] + ".checkpoint", "passed": passed, "evaluation_sha256": sha(ep),
    "completion_sha256": sha(completion_path), "config_sha256": sha(CONFIG), "runner_sha256": sha(RUNNER), "authority": evaluation["next_handoff"]}
    (OUT / "checkpoint_manifest.json").write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "passed": passed, "checks": checks,
                      "maximum_absolute_ratio_shift": evaluation["maximum_absolute_ratio_shift"], "contrasts": evaluation["contrasts"]}, indent=2))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
