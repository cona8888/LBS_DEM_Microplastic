from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage33d_matched_pet_lbs_physical_validation_20260901"
DESIGN = ROOT / "stage33_designs" / STUDY / "release_01"
OUT = ROOT / "stage33_evaluations" / STUDY / "design_audit_01"
CONDITIONS = ("T20", "T120", "T140", "T160", "T180")
TARGET_PET_WT_PERCENT = 0.09841784362759924
RANDOMIZATION_SEEDS = {1: 330401, 2: 330402, 3: 330403}
EXPECTED_SOURCE_ROLES = {
    "stage33a_workbook",
    "stage33a_resolved_protocol",
    "stage33a_design_records",
    "stage33a_design_audit",
    "stage33b_bridge_design",
    "stage33b_bridge_audit",
    "stage33cm_design",
    "stage33cm_synthetic_verification",
    "stage33cm_release_audit",
    "stage33cq_design",
    "stage33cq_synthetic_verification",
    "stage33cq_visual_inspection",
    "stage33cq_release_audit",
    "stage32c_measurement_release_manifest",
    "stage32c_measurement_release_audit",
    "stage32c_measurement_evaluator",
    "stage33d_contract",
    "stage33d_builder",
    "stage33d_auditor",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise RuntimeError(f"CSV has no header: {path}")
        return list(reader.fieldnames), list(reader)


def expected_randomized_order() -> list[tuple[int, int, int, str]]:
    expected: list[tuple[int, int, int, str]] = []
    for block in (1, 2, 3):
        rng = random.Random(RANDOMIZATION_SEEDS[block])
        replicates = [1, 2, 3]
        rng.shuffle(replicates)
        for set_sequence, replicate in enumerate(replicates, 1):
            members = ["CLEAN", *CONDITIONS]
            rng.shuffle(members)
            for within_set_order, member in enumerate(members, 1):
                expected.append((block, set_sequence, replicate, within_set_order, member))
    return expected


def main() -> int:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    required_files = [
        "resolved_design.json",
        "completion.json",
        "custodian_design_matrix.csv",
        "operator_capture_template.csv",
        "preparation_capture_template.csv",
        "darcy_linearity_capture_template.csv",
        "blinded_batch_link_template.csv",
        "restricted_mass_balance_template.csv",
        "instrument_calibration_template.csv",
        "roles_and_key_custody_template.json",
        "acceptance_gates.json",
        "failure_codes.json",
        "STATISTICAL_ANALYSIS_SPECIFICATION.md",
    ]
    missing = [name for name in required_files if not (DESIGN / name).is_file()]
    if missing:
        raise FileNotFoundError(f"design release files missing: {missing}")

    design = load_json(DESIGN / "resolved_design.json")
    completion = load_json(DESIGN / "completion.json")
    gates = load_json(DESIGN / "acceptance_gates.json")
    roles = load_json(DESIGN / "roles_and_key_custody_template.json")
    failure_codes = load_json(DESIGN / "failure_codes.json")
    plan_fields, plan = read_csv(DESIGN / "custodian_design_matrix.csv")
    operator_fields, operator_rows = read_csv(DESIGN / "operator_capture_template.csv")
    preparation_fields, preparation_rows = read_csv(DESIGN / "preparation_capture_template.csv")
    linearity_fields, linearity_rows = read_csv(DESIGN / "darcy_linearity_capture_template.csv")
    link_fields, link_rows = read_csv(DESIGN / "blinded_batch_link_template.csv")
    mass_fields, mass_rows = read_csv(DESIGN / "restricted_mass_balance_template.csv")
    calibration_fields, calibration_rows = read_csv(DESIGN / "instrument_calibration_template.csv")

    source_checks: dict[str, bool] = {}
    for role, binding in design.get("source_bindings", {}).items():
        path = Path(str(binding.get("path", "")))
        source_checks[role] = path.is_file() and sha256(path) == binding.get("sha256")

    artifact_checks: dict[str, bool] = {}
    for name, binding in completion.get("artifacts", {}).items():
        path = Path(str(binding.get("path", "")))
        artifact_checks[name] = (
            path == DESIGN / name
            and path.is_file()
            and sha256(path) == binding.get("sha256")
        )

    block_counts = Counter(int(row["reactor_block"]) for row in plan)
    condition_counts = Counter(row["condition_id"] for row in plan)
    pet_rows = [row for row in plan if row["specimen_role"] == "pet_mixture"]
    clean_rows = [row for row in plan if row["specimen_role"] == "clean_lbs_control"]
    batch_counts = Counter(row["source_batch_slot"] for row in pet_rows)
    set_members: dict[tuple[int, int], list[dict[str, str]]] = defaultdict(list)
    for row in plan:
        set_members[(int(row["reactor_block"]), int(row["technical_replicate"]))].append(row)
    complete_sets = all(
        len(rows) == 6 and {row["condition_id"] for row in rows} == {"CLEAN", *CONDITIONS}
        for rows in set_members.values()
    ) and len(set_members) == 9

    expected_order = expected_randomized_order()
    observed_order = [
        (
            int(row["reactor_block"]),
            int(row["matched_set_sequence"]),
            int(row["technical_replicate"]),
            int(row["within_set_order"]),
            row["condition_id"],
        )
        for row in plan
    ]

    required_operator_fields = {
        "opaque_specimen_id",
        "opaque_matched_set_id",
        "water_temperature_c",
        "specimen_diameter_mm",
        "specimen_length_mm",
        "head_difference_m",
        "collection_time_s",
        "collected_water_mass_g",
        "effluent_pet_detected",
        "valid_pre_measurement",
        "pre_measurement_rejection_reason",
    }
    forbidden_operator_fields = {
        "condition_id",
        "source_batch_slot",
        "target_pet_dry_mass_percent",
        "treatment_temperature_c",
        "morphology_d50_um",
        "numerical_prediction",
    }
    required_preparation_fields = {
        "opaque_specimen_id",
        "dry_sand_mass_g",
        "dry_pet_mass_g",
        "achieved_pet_dry_mass_percent",
        "initial_total_solid_void_ratio",
        "pre_measurement_eligible",
    }
    required_linearity_fields = {
        "opaque_specimen_id",
        "gradient_sequence",
        "head_difference_m",
        "collection_time_s",
        "collected_water_mass_g",
        "particle_reynolds_number",
    }
    required_link_fields = {
        "analyst_batch_code",
        "morphology_release_sha256",
        "morphology_batch_summary_sha256",
        "cross_release_commitment_sha256",
        "link_state",
    }
    required_mass_fields = {
        "source_batch_id",
        "initial_dry_pet_mass_g",
        "hydraulic_aliquot_mass_g",
        "mass_closure_fraction",
        "split_qualification_record_sha256",
        "eligible_before_hydraulics",
    }
    required_calibration_fields = {
        "calibration_id",
        "instrument_role",
        "reference_standard_id",
        "relative_error",
        "pass",
        "record_sha256",
    }

    all_role_values_empty = all(value == "" for value in roles.get("roles", {}).values())
    future_inputs = design.get("future_required_inputs", {})
    all_future_inputs_empty = bool(future_inputs) and all(
        item.get("populated") is False and item.get("path") == "" and item.get("sha256") == ""
        for item in future_inputs.values()
    )
    source_roles = set(design.get("source_bindings", {}))
    plan_source_batches = {row["source_batch_slot"] for row in pet_rows}
    sentinels = [row for row in plan if row["planned_linearity_sentinel"].lower() == "true"]
    sentinel_ok = len(sentinels) == 6 and Counter(row["condition_id"] for row in sentinels) == Counter({"CLEAN": 3, "T180": 3})

    analysis_text = (DESIGN / "STATISTICAL_ANALYSIS_SPECIFICATION.md").read_text(encoding="utf-8")
    contract_text = Path(design["source_bindings"]["stage33d_contract"]["path"]).read_text(encoding="utf-8")
    checks = {
        "schema_and_stage_exact": design.get("schema") == "pet.stage33d-matched-pet-lbs-physical-validation-design.v1" and design.get("stage") == "Stage33D",
        "status_predata_execution_closed": design.get("status") == "frozen_predata_design_only_execution_closed",
        "design_and_completion_passed": design.get("passed") is True and completion.get("passed") is True,
        "source_roles_exact": source_roles == EXPECTED_SOURCE_ROLES,
        "all_source_hashes_match": len(source_checks) == len(EXPECTED_SOURCE_ROLES) and all(source_checks.values()),
        "all_completion_artifact_hashes_match": len(artifact_checks) == 12 and all(artifact_checks.values()),
        "exact_54_plan_rows": len(plan) == 54,
        "run_order_unique_complete": [int(row["run_order"]) for row in plan] == list(range(1, 55)),
        "block_counts_exact": block_counts == Counter({1: 18, 2: 18, 3: 18}),
        "condition_counts_exact": condition_counts == Counter({"CLEAN": 9, "T20": 9, "T120": 9, "T140": 9, "T160": 9, "T180": 9}),
        "exact_45_pet_and_9_clean": len(pet_rows) == 45 and len(clean_rows) == 9,
        "exact_15_unpooled_batch_slots": len(plan_source_batches) == 15 and "" not in plan_source_batches and set(batch_counts.values()) == {3},
        "all_nine_matched_sets_complete": complete_sets,
        "randomization_reproduces_frozen_seeds": observed_order == expected_order,
        "linearity_sentinels_exact": sentinel_ok,
        "pet_loading_exact_and_clean_zero": all(math.isclose(float(row["target_pet_dry_mass_percent"]), TARGET_PET_WT_PERCENT, rel_tol=0, abs_tol=1e-15) for row in pet_rows) and all(float(row["target_pet_dry_mass_percent"]) == 0.0 for row in clean_rows),
        "all_operational_ids_unassigned": all(row["operational_id_status"] == "not_assigned_predata_design_only" for row in plan),
        "all_capture_templates_empty": not any((operator_rows, preparation_rows, linearity_rows, link_rows, mass_rows, calibration_rows)),
        "operator_schema_complete_and_blinded": required_operator_fields.issubset(operator_fields) and forbidden_operator_fields.isdisjoint(operator_fields),
        "preparation_schema_complete": required_preparation_fields.issubset(preparation_fields),
        "linearity_schema_complete": required_linearity_fields.issubset(linearity_fields),
        "batch_link_schema_complete": required_link_fields.issubset(link_fields),
        "mass_balance_schema_complete": required_mass_fields.issubset(mass_fields),
        "calibration_schema_complete": required_calibration_fields.issubset(calibration_fields),
        "role_template_contains_no_real_people": all_role_values_empty and roles.get("status") == "template_only_no_real_identifiers",
        "future_inputs_all_unpopulated": all_future_inputs_empty,
        "readiness_remains_closed": design.get("readiness", {}).get("design_ready_for_independent_audit") is True and not any(value for key, value in design.get("readiness", {}).items() if key != "design_ready_for_independent_audit"),
        "all_authority_closed": bool(design.get("authority")) and not any(design["authority"].values()),
        "monotonicity_not_a_gate": gates.get("monotonicity_is_not_a_gate") is True and design.get("design", {}).get("monotonicity_is_not_an_acceptance_gate") is True,
        "hydraulic_gates_exact": gates.get("minimum_valid_matched_sets_per_batch") == 2 and gates.get("minimum_valid_clean_controls_per_block") == 2 and gates.get("maximum_clean_cv_within_block") == 0.05 and gates.get("darcy_linearity", {}).get("minimum_discharge_gradient_r_squared") == 0.99 and gates.get("darcy_linearity", {}).get("maximum_particle_reynolds_number") == 1.0,
        "minimum_relevant_effect_exact": math.isclose(float(gates.get("minimum_relevant_log_ratio_effect")), abs(math.log(0.95)), rel_tol=0, abs_tol=1e-15),
        "failure_code_set_substantive": len(failure_codes.get("codes", {})) >= 15 and "D33D_DEGRADATION_EVIDENCE_INSUFFICIENT" in failure_codes.get("codes", {}),
        "analysis_uses_batch_not_pseudoreplication": all(token in analysis_text for token in ("independent treatment unit is the PET process batch", "Never analyze fields, objects", "15 batch endpoints", "association, not causal")),
        "contract_distinguishes_length_from_degradation": "not, by itself, a molecular degradation scale" in contract_text and "new confirmation wave" in contract_text,
        "synthetic_evidence_not_empirical": "Synthetic Stage33C-M/Q evidence cannot fill any empirical slot" in contract_text,
        "stage32_f37_not_relabelled": "cannot be relabelled" in contract_text,
        "no_empirical_or_operational_payload": not any((operator_rows, preparation_rows, linearity_rows, link_rows, mass_rows, calibration_rows)) and design.get("blinding", {}).get("real_identifiers_present") is False and design.get("blinding", {}).get("real_treatment_key_present") is False,
    }
    passed = all(checks.values())
    audit = {
        "schema": "pet.stage33d-matched-pet-lbs-physical-validation-design-audit.v1",
        "stage": "Stage33D",
        "status": "passed_predata_design_audit_execution_closed" if passed else "failed_predata_design_audit",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "passed": passed,
        "check_n": len(checks),
        "passed_check_n": sum(checks.values()),
        "failed_checks": [name for name, value in checks.items() if not value],
        "checks": checks,
        "source_checks": source_checks,
        "artifact_checks": artifact_checks,
        "counts": {
            "reactor_blocks": 3,
            "conditions": 5,
            "independent_pet_batch_slots": len(plan_source_batches),
            "pet_columns": len(pet_rows),
            "clean_columns": len(clean_rows),
            "total_columns": len(plan),
            "linearity_sentinels": len(sentinels),
        },
        "bindings": {
            "resolved_design_sha256": sha256(DESIGN / "resolved_design.json"),
            "completion_sha256": sha256(DESIGN / "completion.json"),
            "custodian_design_matrix_sha256": sha256(DESIGN / "custodian_design_matrix.csv"),
            "acceptance_gates_sha256": sha256(DESIGN / "acceptance_gates.json"),
            "statistical_specification_sha256": sha256(DESIGN / "STATISTICAL_ANALYSIS_SPECIFICATION.md"),
        },
        "conclusion": (
            "Stage33D is a hash-bound, statistically coherent pre-data design. It contains no empirical data or real key and authorizes no laboratory or numerical execution."
            if passed
            else "Fail closed: repair and version the pre-data design before any operational release."
        ),
        "claim_boundary": design.get("claim_boundary"),
        "stop_boundary": design.get("stop_boundary"),
        "authority": design.get("authority"),
    }
    OUT.mkdir(parents=True, exist_ok=False)
    audit_path = OUT / "design_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    audit_completion = {
        "schema": "pet.stage33d-matched-pet-lbs-physical-validation-design-audit-completion.v1",
        "status": "complete" if passed else "failed",
        "passed": passed,
        "design_audit": {"path": str(audit_path), "sha256": sha256(audit_path)},
        "input_mutation": False,
        "next_handoff": "populate none of the future inputs until the relevant empirical or operational prerequisite has independently passed",
    }
    (OUT / "completion.json").write_text(json.dumps(audit_completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "passed": passed, "check_n": len(checks), "failed_checks": audit["failed_checks"]}, indent=2))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
