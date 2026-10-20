#!/usr/bin/env python3
"""Independently audit the immutable, empirical-empty Stage33E handoff."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STAGING = ROOT / "stage33_staging"
DEFAULT_RELEASE = ROOT / "stage33_designs" / "stage33e_empirical_readiness_handoff_20260901" / "release_01"
DEFAULT_OUTPUT = ROOT / "stage33_evaluations" / "stage33e_empirical_readiness_handoff_20260901" / "design_audit_01"
RELEASE_ID = "STAGE33E-EMPIRICAL-READINESS-HANDOFF-01"

STAGE33D_RELEASE = ROOT / "stage33_designs" / "stage33d_matched_pet_lbs_physical_validation_20260901" / "release_01"
STAGE33D_AUDIT = ROOT / "stage33_evaluations" / "stage33d_matched_pet_lbs_physical_validation_20260901" / "design_audit_01"
STAGE33DO_VERIFICATION = ROOT / "stage33_evaluations" / "stage33do_operational_workflow_synthetic_qualification_20260901" / "verification_01"
STAGE33DO_AUDIT = ROOT / "stage33_evaluations" / "stage33do_operational_workflow_synthetic_qualification_20260901" / "release_audit_01"
STAGE33A_PROTOCOL = ROOT / "outputs" / "019f7799-ad23-7f90-bf22-04cd842ccd22" / "stage33a_pet_fragmentation_characterization_20260829" / "preflight_design_03" / "resolved_protocol.json"
STAGE33CQ_RELEASE = ROOT / "stage33_designs" / "stage33cq_acquisition_qualification_20260831" / "release_01"

EXPECTED_SOURCES = {
    "stage33d_contract": STAGING / "STAGE33D_MATCHED_PET_LBS_PHYSICAL_VALIDATION_CONTRACT_V1.md",
    "stage33d_resolved_design": STAGE33D_RELEASE / "resolved_design.json",
    "stage33d_acceptance_gates": STAGE33D_RELEASE / "acceptance_gates.json",
    "stage33d_completion": STAGE33D_RELEASE / "completion.json",
    "stage33d_custodian_design_matrix": STAGE33D_RELEASE / "custodian_design_matrix.csv",
    "stage33d_design_audit": STAGE33D_AUDIT / "design_audit.json",
    "stage33d_design_audit_completion": STAGE33D_AUDIT / "completion.json",
    "stage33do_contract": STAGING / "STAGE33DO_OPERATIONAL_WORKFLOW_SYNTHETIC_QUALIFICATION_CONTRACT_V1.md",
    "stage33do_synthetic_verification": STAGE33DO_VERIFICATION / "verification.json",
    "stage33do_synthetic_verification_completion": STAGE33DO_VERIFICATION / "completion.json",
    "stage33do_release_audit": STAGE33DO_AUDIT / "audit.json",
    "stage33do_release_audit_completion": STAGE33DO_AUDIT / "completion.json",
    "stage33a_resolved_protocol": STAGE33A_PROTOCOL,
    "stage33cq_resolved_design": STAGE33CQ_RELEASE / "resolved_design.json",
    "stage33cq_acceptance_gates": STAGE33CQ_RELEASE / "acceptance_gates.json",
    "stage33cq_release_audit": ROOT / "stage33_evaluations" / "stage33cq_acquisition_qualification_20260831" / "release_audit_03" / "audit.json",
    "stage33cq_synthetic_verification": ROOT / "stage33_evaluations" / "stage33cq_acquisition_and_masks_synthetic_verification_20260831" / "verification_06" / "verification.json",
    "stage33e_contract": STAGING / "STAGE33E_EMPIRICAL_READINESS_HANDOFF_CONTRACT_V1.md",
    "stage33e_builder": STAGING / "build_stage33e_empirical_readiness_handoff_v1.py",
    "stage33e_auditor": Path(__file__).resolve(),
    "stage33e_verifier": STAGING / "verify_stage33e_empirical_readiness_handoff_v1.py",
}

EXPECTED_FILES = {
    "RUNBOOK.md",
    "STAGE33E_EMPIRICAL_READINESS_HANDOFF_CONTRACT_V1.md",
    "apparatus_calibration_requirements.csv",
    "authority_matrix.json",
    "completion.json",
    "effluent_method_requirements.csv",
    "evidence_register_template.csv",
    "evidence_requirements.json",
    "evidence_slot_registry.json",
    "evidence_submission_envelope_template.json",
    "failure_codes.json",
    "lineage_manifest.json",
    "mass_split_requirements.csv",
    "negative_challenge_plan.json",
    "packing_capability_capture_template.csv",
    "production_operational_toolchain_audit_template.json",
    "readiness_decision.json",
    "readiness_gate_graph.json",
    "readiness_state_machine.json",
    "resolved_handoff.json",
    "roles_and_key_custody_template.json",
    "split_representativeness_capture_template.csv",
    "uncertainty_budget_requirements.csv",
}

EXPECTED_SLOTS = {
    "stage33a_empirical_readiness_closure",
    "stage33cq_adjudicated_morphology_release",
    "stage33cq_empirical_heldout_gate_report",
    "real_cross_release_commitment",
    "hydraulic_apparatus_calibration_release",
    "pet_mass_budget_and_split_qualification",
    "effluent_pet_detection_method_release",
    "molecular_and_orthogonal_chemistry_release_for_degradation_claim",
    "pet_specific_frozen_numerical_predictions_for_model_validation",
}

EXPECTED_STAGE33D_GATES = {
    "calculation_crosscheck_maximum_relative_error": 0.005,
    "completeness_gate": "all five condition-by-three-block batch endpoints are required for confirmatory complete-block inference",
    "darcy_linearity": {
        "maximum_K20_cv": 0.05,
        "maximum_particle_reynolds_number": 1.0,
        "minimum_discharge_gradient_r_squared": 0.99,
        "minimum_distinct_positive_gradients": 3,
    },
    "degradation_proxy_additional_gates": [
        "independent molecular molar-mass endpoint",
        "orthogonal chain-scission or product endpoint",
        "recovery and mass-balance acceptance",
        "new independent confirmation wave with frozen directional and minimum-effect criteria",
    ],
    "fixed_solid_gate": "effluent PET must not exceed the prospectively validated detection limit and flow must remain stationary",
    "maximum_clean_cv_within_block": 0.05,
    "minimum_relevant_log_ratio_effect": 0.05129329438755058,
    "minimum_valid_clean_controls_per_block": 2,
    "minimum_valid_matched_sets_per_batch": 2,
    "monotonicity_is_not_a_gate": True,
    "pet_dose_absolute_tolerance_wt_percent": 0.0005,
    "pet_dose_relative_tolerance": 0.05,
    "required_batch_endpoints": 15,
    "schema": "pet.stage33d-matched-pet-lbs-acceptance-gates.v1",
    "target_pet_dry_mass_percent": 0.09841784362759924,
    "target_total_solid_void_ratio": 0.744,
    "void_ratio_absolute_tolerance": 0.01,
    "water_temperature_c": 20.0,
    "water_temperature_tolerance_c": 0.5,
}

BLANK_SLOT_FIELDS = {
    "expected_schema",
    "manifest_path",
    "manifest_sha256",
    "completion_path",
    "completion_sha256",
    "audit_path",
    "audit_sha256",
    "submission_id",
    "receipt_utc",
    "freeze_utc",
}


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require_regular(path: Path, role: str, *, single_link: bool = False) -> None:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"E33E_UNEXPECTED_FILE: {role} is not a regular non-symlink file: {path}")
    if single_link and os.stat(path, follow_symlinks=False).st_nlink != 1:
        raise RuntimeError(f"E33E_UNEXPECTED_FILE: {role} has unsafe link count: {path}")


def load_json(path: Path) -> Any:
    require_regular(path, path.name)
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    require_regular(path, path.name)
    with path.open("r", newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise RuntimeError(f"E33E_UNEXPECTED_FILE: CSV missing header: {path}")
        return list(reader.fieldnames), list(reader)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def tree_snapshot(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*"), key=lambda p: str(p).lower()):
        if path.is_dir():
            continue
        require_regular(path, f"release:{path.name}", single_link=True)
        result[path.relative_to(root).as_posix()] = sha256(path)
    return result


def source_snapshot(source_records: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for role, record in source_records.items():
        path = Path(record["path"])
        require_regular(path, f"source:{role}")
        result[role] = sha256(path)
    return result


def audit_release(release: Path) -> tuple[dict[str, Any], dict[str, str], dict[str, str]]:
    if not release.is_dir() or release.is_symlink():
        raise RuntimeError(f"E33E_UNEXPECTED_FILE: release is not a regular directory: {release}")
    if any(path.is_dir() for path in release.iterdir()):
        raise RuntimeError("E33E_UNEXPECTED_FILE: nested release directories are forbidden")

    observed_files = {path.name for path in release.iterdir() if path.is_file()}
    if observed_files != EXPECTED_FILES:
        raise RuntimeError(
            f"E33E_UNEXPECTED_FILE: file set mismatch; missing={sorted(EXPECTED_FILES-observed_files)}, extra={sorted(observed_files-EXPECTED_FILES)}"
        )
    release_before = tree_snapshot(release)

    resolved = load_json(release / "resolved_handoff.json")
    lineage = load_json(release / "lineage_manifest.json")
    slots = load_json(release / "evidence_slot_registry.json")
    requirements = load_json(release / "evidence_requirements.json")
    graph = load_json(release / "readiness_gate_graph.json")
    state_machine = load_json(release / "readiness_state_machine.json")
    authority = load_json(release / "authority_matrix.json")
    roles = load_json(release / "roles_and_key_custody_template.json")
    toolchain = load_json(release / "production_operational_toolchain_audit_template.json")
    envelope = load_json(release / "evidence_submission_envelope_template.json")
    decision = load_json(release / "readiness_decision.json")
    failures = load_json(release / "failure_codes.json")
    challenges = load_json(release / "negative_challenge_plan.json")
    completion = load_json(release / "completion.json")

    checks: dict[str, bool] = {}

    def check(name: str, condition: bool) -> None:
        checks[name] = bool(condition)

    check(
        "resolved_identity_and_empty_state",
        resolved.get("schema") == "pet.stage33e-empirical-readiness-handoff.v1"
        and resolved.get("stage") == "Stage33E"
        and resolved.get("release_id") == RELEASE_ID
        and resolved.get("status") == "frozen_design_only_all_empirical_inputs_unpopulated"
        and resolved.get("current_state") == "S10_DESIGN_FROZEN_EMPIRICAL_EMPTY"
        and resolved.get("passed") is True
        and resolved.get("no_empirical_data") is True
        and resolved.get("no_real_identifiers") is True
        and resolved.get("no_real_key") is True
        and resolved.get("no_laboratory_execution") is True
        and resolved.get("no_numerical_execution") is True,
    )
    check(
        "design_counts_and_experimental_unit_exact",
        resolved.get("design_counts")
        == {
            "reactor_blocks": 3,
            "conditions": 5,
            "independent_pet_batches": 15,
            "technical_pet_columns": 45,
            "matched_clean_controls": 9,
            "total_columns": 54,
        }
        and resolved.get("experimental_unit") == "independent PET process batch"
        and resolved.get("monotonicity_is_not_a_gate") is True,
    )
    check("all_resolved_authority_closed", bool(resolved.get("authority")) and all(v is False for v in resolved["authority"].values()))
    check("all_four_readiness_states_closed", all(v is False for k, v in resolved.get("readiness", {}).items() if k != "design_lineage_verified") and resolved.get("readiness", {}).get("design_lineage_verified") is True)

    source_records = lineage.get("sources", {})
    check(
        "lineage_identity_and_exact_roles",
        lineage.get("schema") == "pet.stage33e-readiness-lineage-manifest.v1"
        and lineage.get("release_id") == RELEASE_ID
        and lineage.get("source_n") == len(EXPECTED_SOURCES)
        and set(source_records) == set(EXPECTED_SOURCES),
    )
    seen_paths: set[str] = set()
    source_hashes_exact = True
    source_paths_exact = True
    source_links_safe = True
    for role, expected_path in EXPECTED_SOURCES.items():
        record = source_records.get(role, {})
        actual_path = Path(record.get("path", "")) if record.get("path") else Path(".")
        expected_resolved = str(expected_path.resolve())
        source_paths_exact &= record.get("path") == expected_resolved
        source_links_safe &= not (role.startswith("stage33do_") and "successful_release" in record.get("path", "").lower())
        source_hashes_exact &= expected_path.is_file() and record.get("sha256") == sha256(expected_path)
        seen_paths.add(record.get("path", "").lower())
    check("source_paths_exact", source_paths_exact)
    check("source_hashes_exact", source_hashes_exact)
    check("source_paths_unique", len(seen_paths) == len(EXPECTED_SOURCES))
    check("stage33do_successful_release_not_bound", source_links_safe)
    sources_before = source_snapshot(source_records)

    stage33d = load_json(EXPECTED_SOURCES["stage33d_resolved_design"])
    stage33d_gates = load_json(EXPECTED_SOURCES["stage33d_acceptance_gates"])
    stage33d_audit = load_json(EXPECTED_SOURCES["stage33d_design_audit"])
    stage33do_verification = load_json(EXPECTED_SOURCES["stage33do_synthetic_verification"])
    stage33do_audit = load_json(EXPECTED_SOURCES["stage33do_release_audit"])
    stage33a = load_json(EXPECTED_SOURCES["stage33a_resolved_protocol"])
    stage33cq = load_json(EXPECTED_SOURCES["stage33cq_resolved_design"])
    check(
        "stage33d_parent_passed_but_execution_closed",
        stage33d.get("schema") == "pet.stage33d-matched-pet-lbs-physical-validation-design.v1"
        and stage33d.get("status") == "frozen_predata_design_only_execution_closed"
        and stage33d.get("passed") is True
        and stage33d_audit.get("passed") is True
        and stage33d_audit.get("failed_checks") == []
        and all(v is False for v in stage33d.get("authority", {}).values()),
    )
    check("inherited_stage33d_thresholds_byte_semantically_exact", stage33d_gates == EXPECTED_STAGE33D_GATES and requirements.get("stage33d_acceptance_gates") == EXPECTED_STAGE33D_GATES)
    check(
        "stage33do_top_level_is_synthetic_only",
        stage33do_verification.get("pass") is True
        and stage33do_verification.get("test_only") is True
        and stage33do_verification.get("no_empirical_data") is True
        and stage33do_verification.get("no_real_key") is True
        and stage33do_audit.get("pass") is True
        and stage33do_audit.get("passed_check_n") == 50
        and stage33do_audit.get("failed_check_n") == 0
        and all(v is False for v in stage33do_verification.get("authority", {}).values()),
    )
    blocker_state = {row.get("blocker_id"): row.get("status") for row in stage33a.get("blockers", [])}
    check(
        "stage33a_exactly_one_closed_and_eleven_open",
        stage33a.get("execution_ready") is False
        and blocker_state.get("B01") == "CLOSED"
        and all(blocker_state.get(f"B{i:02d}") == "OPEN" for i in range(2, 13)),
    )
    check(
        "stage33cq_empirical_evidence_absent",
        stage33cq.get("status") == "preflight_ready_no_empirical_data" and "Synthetic software" in stage33cq.get("claim_boundary", ""),
    )

    slot_rows = slots.get("slots", [])
    slot_ids = [row.get("slot_id") for row in slot_rows]
    check(
        "exact_nine_inherited_slots",
        slots.get("schema") == "pet.stage33e-empirical-evidence-slot-registry.v1"
        and slots.get("slot_n") == 9
        and len(slot_rows) == 9
        and len(set(slot_ids)) == 9
        and set(slot_ids) == EXPECTED_SLOTS,
    )
    slot_blank = True
    slot_state_exact = True
    for row in slot_rows:
        slot_blank &= all(row.get(field) == "" for field in BLANK_SLOT_FIELDS)
        slot_state_exact &= row.get("populated") is False and row.get("verified") is False and row.get("decision") == "not_submitted"
    check("all_empirical_slot_bindings_blank", slot_blank)
    check("all_empirical_slot_states_unsubmitted", slot_state_exact)

    reg_headers, reg_rows = load_csv(release / "evidence_register_template.csv")
    check(
        "evidence_register_exactly_mirrors_nine_slots",
        len(reg_rows) == 9
        and {row.get("slot_id") for row in reg_rows} == EXPECTED_SLOTS
        and all(row.get(field, "") == "" for row in reg_rows for field in BLANK_SLOT_FIELDS)
        and all(row.get("populated") == "false" and row.get("verified") == "false" and row.get("decision") == "not_submitted" for row in reg_rows),
    )

    gate_rows = graph.get("gates", [])
    pass_gates = [row.get("gate_id") for row in gate_rows if row.get("current_pass") is True]
    check(
        "only_design_lineage_gate_passes",
        graph.get("schema") == "pet.stage33e-readiness-gate-graph.v1"
        and [row.get("gate_id") for row in gate_rows] == ["G00", "G10", "G20", "G30", "G40", "G50", "G60", "G70"]
        and pass_gates == ["G00"],
    )
    core_prereqs = set(next(row["prerequisites"] for row in gate_rows if row["gate_id"] == "G20"))
    check(
        "optional_evidence_cannot_unlock_core_gate",
        "molecular_and_orthogonal_chemistry_release_for_degradation_claim" not in core_prereqs
        and "pet_specific_frozen_numerical_predictions_for_model_validation" not in core_prereqs
        and graph.get("optional_evidence_cannot_unlock_core_execution") is True,
    )
    active_states = [row.get("state_id") for row in state_machine.get("states", []) if row.get("active") is True]
    check(
        "only_s10_state_active_and_no_in_place_transition",
        state_machine.get("schema") == "pet.stage33e-readiness-state-machine.v1"
        and state_machine.get("current_state") == "S10"
        and active_states == ["S10"]
        and state_machine.get("transition_policy", {}).get("in_place_edits_allowed") is False
        and state_machine.get("transition_policy", {}).get("each_transition_requires_new_immutable_release") is True
        and state_machine.get("transition_policy", {}).get("skipped_or_replayed_transitions_rejected") is True,
    )

    check(
        "authority_matrix_closed",
        authority.get("schema") == "pet.stage33e-authority-matrix.v1"
        and authority.get("status") == "all_authority_closed"
        and bool(authority.get("authority"))
        and all(v is False for v in authority["authority"].values()),
    )
    check(
        "readiness_decision_closed",
        decision.get("schema") == "pet.stage33e-readiness-decision.v1"
        and decision.get("decision") == "DESIGN_ONLY_ALL_EMPIRICAL_INPUTS_UNPOPULATED"
        and all(v is False for v in decision.get("readiness", {}).values())
        and all(v is False for v in decision.get("authority", {}).values()),
    )
    blank_role_fields = ["release_id", "operator_id", "analyst_id", "custodian_id", "independent_auditor_id", "institutional_restricted_store_id", "real_secret_or_key_path", "real_secret_or_key_sha256", "production_builder_path", "production_builder_sha256", "production_auditor_path", "production_auditor_sha256"]
    check(
        "roles_template_has_no_real_identifiers_or_key",
        roles.get("schema") == "pet.stage33e-roles-key-custody-template.v1"
        and roles.get("status") == "template_only_no_real_identifiers"
        and all(roles.get(field) == "" for field in blank_role_fields)
        and roles.get("all_roles_distinct_required") is True
        and roles.get("fresh_secret_namespace_required") is True
        and roles.get("stage33do_test_secret_or_identifiers_reusable") is False,
    )
    check(
        "production_toolchain_blocker_empty_and_false",
        toolchain.get("blocker_id") == "production_operational_toolchain_audit"
        and all(toolchain.get(field) == "" for field in ["path", "sha256", "audit_path", "audit_sha256", "schema_expected"])
        and toolchain.get("status") == "not_submitted"
        and all(toolchain.get(field) is False for field in ["populated", "verified", "production_mode_supported", "fresh_secret_namespace_verified", "restricted_store_verified", "hostile_challenges_passed"]),
    )
    envelope_blank_fields = [field for field in envelope if field not in {"schema", "current_status"}]
    check(
        "evidence_submission_envelope_blank",
        envelope.get("schema") == "pet.stage33e-evidence-submission-envelope.v1"
        and envelope.get("current_status") == "template_only_unpopulated"
        and all(envelope.get(field) == "" for field in envelope_blank_fields),
    )

    apparatus_headers, apparatus_rows = load_csv(release / "apparatus_calibration_requirements.csv")
    expected_apparatus = {
        "dry_sand_balance", "pet_aliquot_filter_balance", "effluent_collection_balance_or_volumetric_device",
        "water_temperature_measurement", "timer", "head_sensor_or_gauge", "specimen_diameter_gauge",
        "specimen_length_gauge", "saturation_and_leak_assessment", "effluent_collection_train",
    }
    check(
        "apparatus_roles_exact_and_unpopulated",
        len(apparatus_rows) == 10
        and {row.get("instrument_role") for row in apparatus_rows} == expected_apparatus
        and all(row.get("current_status") == "UNPOPULATED" for row in apparatus_rows)
        and all(row.get(key, "") == "" for row in apparatus_rows for key in apparatus_headers if key not in {"instrument_role", "current_status"}),
    )
    _, uncertainty_rows = load_csv(release / "uncertainty_budget_requirements.csv")
    check(
        "four_uncertainty_budgets_required_but_unpopulated",
        {row.get("derived_quantity") for row in uncertainty_rows} == {"total_solid_void_ratio", "achieved_pet_dose_wt_percent", "K20_m_s", "matched_log_ratio"}
        and all(row.get("current_status") == "UNPOPULATED" for row in uncertainty_rows)
        and all(row.get(field, "") == "" for row in uncertainty_rows for field in ["equation_or_budget_path", "equation_or_budget_sha256", "combined_standard_uncertainty", "coverage_factor", "expanded_uncertainty_U95", "prospective_decision_rule", "rationale", "independent_reviewer_id"]),
    )
    _, packing_rows = load_csv(release / "packing_capability_capture_template.csv")
    check("packing_capture_empty", packing_rows == [])
    _, mass_rows = load_csv(release / "mass_split_requirements.csv")
    expected_batch_slots = {f"B{block}-{condition}" for block in range(1, 4) for condition in ("T20", "T120", "T140", "T160", "T180")}
    mass_empirical_fields = [
        "operational_batch_id", "charge_dry_pet_g", "blank_correction_g", "moisture_correction_fraction",
        "recovered_dry_pet_g", "process_transfer_loss_g", "filter_loss_g", "process_other_loss_g",
        "process_closure_fraction", "process_closure_threshold", "process_closure_U95", "process_closure_pass",
        "morphology_aliquot_g", "chemistry_aliquot_g", "hydraulic_aliquot_g", "archive_aliquot_g", "residual_g",
        "split_loss_g", "split_closure_fraction", "split_closure_threshold", "split_closure_U95", "split_closure_pass",
        "split_protocol", "split_qualification_path", "split_qualification_sha256", "unpooled_observed", "independent_reviewer_id",
    ]
    check(
        "exact_15_unpooled_mass_split_slots_all_empty",
        len(mass_rows) == 15
        and {row.get("source_batch_slot") for row in mass_rows} == expected_batch_slots
        and all(row.get("unpooled_required") == "true" and row.get("current_status") == "UNPOPULATED" for row in mass_rows)
        and all(row.get(field, "") == "" for row in mass_rows for field in mass_empirical_fields),
    )
    _, split_rows = load_csv(release / "split_representativeness_capture_template.csv")
    check("split_representativeness_capture_empty", split_rows == [])
    _, effluent_rows = load_csv(release / "effluent_method_requirements.csv")
    expected_effluent = {"pet_identity", "capture_strategy", "filter_train", "matrix_blanks", "procedural_blanks", "positive_controls", "false_positive_negative", "filter_transfer_recovery", "LoB_LoD_LoQ", "sample_volume", "mass_equivalent_LoD", "maximum_undetected_fraction", "fixed_solid_decision"}
    effluent_empirical_fields = ["method_value", "units", "method_record_path", "method_record_sha256", "prospective_acceptance_rule", "rationale", "independent_reviewer_id"]
    check(
        "effluent_requirements_exact_and_unpopulated",
        len(effluent_rows) == 13
        and {row.get("requirement_id") for row in effluent_rows} == expected_effluent
        and all(row.get("current_status") == "UNPOPULATED" for row in effluent_rows)
        and all(row.get(field, "") == "" for row in effluent_rows for field in effluent_empirical_fields),
    )
    check(
        "fixed_solid_decision_is_detection_aware",
        requirements.get("fixed_solid_policy")
        == {
            "pet_at_or_above_validated_LoD_fails": True,
            "detected_below_LoQ_still_fails": True,
            "below_LoD_means": "nondetect_not_zero",
            "visual_nondetect_is_sufficient": False,
        },
    )
    check(
        "scope_aware_stage33a_policy_present",
        requirements.get("stage33a_scope_policy", {}).get("every_blocker_requires_disposition") is True
        and set(requirements.get("stage33a_scope_policy", {}).get("mandatory_for_hydraulic", [])) == {"B02", "B03", "B05", "B07", "B10", "B11", "B12"}
        and set(requirements.get("stage33a_scope_policy", {}).get("conditional", {})) == {"B04", "B06", "B08", "B09"},
    )

    required_codes = {"E33E_PARENT_LINEAGE_MISMATCH", "E33E_THRESHOLD_MUTATION", "E33E_NONEMPTY_EMPIRICAL_SLOT", "E33E_SYNTHETIC_AS_EMPIRICAL", "E33E_PRODUCTION_TOOLCHAIN_MISSING", "E33E_AUTHORITY_LEAK", "E33E_OVERWRITE_REFUSED"}
    check("failure_code_set_substantive", failures.get("schema") == "pet.stage33e-failure-codes.v1" and required_codes.issubset(failures.get("codes", {})) and len(failures.get("codes", {})) >= 20)
    check("negative_challenge_plan_substantive", challenges.get("schema") == "pet.stage33e-negative-challenge-plan.v1" and challenges.get("challenge_n") == 18 and len(challenges.get("challenges", [])) == 18)

    contract_text = (release / "STAGE33E_EMPIRICAL_READINESS_HANDOFF_CONTRACT_V1.md").read_text(encoding="utf-8")
    check(
        "contract_preserves_claim_boundary_and_production_blocker",
        "DESIGN_ONLY_ALL_EMPIRICAL_INPUTS_UNPOPULATED" in contract_text
        and "production_operational_toolchain_audit" in contract_text
        and "below LoD means `nondetect`, never zero" in contract_text
        and "scope-resolved" in contract_text,
    )
    release_text = "\n".join((release / name).read_text(encoding="utf-8", errors="ignore") for name in sorted(EXPECTED_FILES))
    forbidden_exact = [
        "STAGE33DO-TEST_ONLY-SYNTHETIC-QUALIFICATION-01",
        "1ec7bda776fa270043eff091ea99971928956a2705a075c45352fb95141c6cb6",
    ]
    check("no_stage33do_test_identifier_or_secret_hash_copied", not any(token in release_text for token in forbidden_exact))

    completion_artifacts = completion.get("artifacts", {})
    expected_artifact_names = EXPECTED_FILES - {"completion.json"}
    completion_exact = set(completion_artifacts) == expected_artifact_names and completion.get("artifact_n") == len(expected_artifact_names)
    for name in expected_artifact_names:
        record = completion_artifacts.get(name, {})
        completion_exact &= record.get("path") == str(release / name)
        completion_exact &= record.get("sha256") == sha256(release / name)
        completion_exact &= record.get("bytes") == (release / name).stat().st_size
    check(
        "completion_hash_closure_exact",
        completion.get("schema") == "pet.stage33e-empirical-readiness-handoff-completion.v1"
        and completion.get("passed") is True
        and completion.get("all_empirical_slots_empty") is True
        and completion.get("production_toolchain_ready") is False
        and completion.get("all_authority_closed") is True
        and completion_exact,
    )

    failed = sorted(name for name, value in checks.items() if not value)
    if failed:
        raise RuntimeError("E33E_DESIGN_AUDIT_FAILED: " + ", ".join(failed))

    release_after = tree_snapshot(release)
    sources_after = source_snapshot(source_records)
    if release_before != release_after or sources_before != sources_after:
        raise RuntimeError("E33E_INPUT_MUTATION: release or source changed during audit")

    audit = {
        "schema": "pet.stage33e-empirical-readiness-handoff-audit.v1",
        "stage": "Stage33E",
        "release_id": RELEASE_ID,
        "created_utc": now_utc(),
        "status": "passed_design_only_empirical_empty_audit",
        "passed": True,
        "check_n": len(checks),
        "passed_check_n": sum(checks.values()),
        "failed_check_n": 0,
        "failed_checks": [],
        "checks": checks,
        "input_mutation": False,
        "counts": {
            "source_bindings": len(source_records),
            "release_artifacts": len(EXPECTED_FILES),
            "inherited_evidence_slots": len(slot_rows),
            "populated_evidence_slots": 0,
            "passing_readiness_gates": 1,
            "active_states": 1,
            "apparatus_roles": len(apparatus_rows),
            "mass_split_batch_slots": len(mass_rows),
            "effluent_method_requirements": len(effluent_rows),
        },
        "readiness": {
            "laboratory_hydraulic_execution_ready": False,
            "cross_domain_unblinding_ready": False,
            "pet_specific_model_validation_ready": False,
            "degradation_proxy_claim_ready": False,
        },
        "authority": dict(authority["authority"]),
        "conclusion": "The Stage33E empty intake architecture is internally consistent and hash-bound. All empirical evidence slots and production authority remain closed.",
        "claim_boundary": "design/audit evidence only; no empirical, physical, model-validation or degradation claim",
        "stop_boundary": resolved["stop_boundary"],
    }
    return audit, release_before, sources_before


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    release = args.release.resolve()
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError(f"E33E_OVERWRITE_REFUSED: output exists: {output}")
    if output == release or release in output.parents or output in release.parents:
        raise RuntimeError("E33E_UNEXPECTED_FILE: audit output must be disjoint from release")
    output.parent.mkdir(parents=True, exist_ok=True)

    audit, _, _ = audit_release(release)
    temp = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=str(output.parent)))
    try:
        write_json(temp / "audit.json", audit)
        write_json(
            temp / "completion.json",
            {
                "schema": "pet.stage33e-empirical-readiness-handoff-audit-completion.v1",
                "stage": "Stage33E",
                "release_id": RELEASE_ID,
                "created_utc": now_utc(),
                "status": "complete",
                "passed": True,
                "audit_path": str(output / "audit.json"),
                "audit_sha256": sha256(temp / "audit.json"),
                "failed_checks": [],
                "input_mutation": False,
                "all_empirical_slots_empty": True,
                "all_authority_closed": True,
                "next_handoff": "hostile synthetic mutation verification of this design audit only",
            },
        )
        os.replace(temp, output)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise

    print(json.dumps({"passed": True, "output": str(output), "check_n": audit["check_n"]}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL-CLOSED: {type(exc).__name__}: {exc}", file=os.sys.stderr)
        raise SystemExit(2)
