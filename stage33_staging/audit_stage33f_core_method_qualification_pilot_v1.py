#!/usr/bin/env python3
"""Independently audit the immutable, design-only Stage33F method pilot.

This auditor never executes a laboratory method, ingests observations, resolves
real identities, or runs DEM/LBM.  A pass establishes design integrity only.
"""

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
DEFAULT_RELEASE = (
    ROOT
    / "stage33_designs"
    / "stage33f_core_method_qualification_pilot_20260901"
    / "release_01"
)
DEFAULT_OUTPUT = (
    ROOT
    / "stage33_evaluations"
    / "stage33f_core_method_qualification_pilot_20260901"
    / "design_audit_01"
)
RELEASE_ID = "STAGE33F-CORE-METHOD-QUALIFICATION-PILOT-01"

STAGE33E_RELEASE = (
    ROOT
    / "stage33_designs"
    / "stage33e_empirical_readiness_handoff_20260901"
    / "release_01"
)
STAGE33E_AUDIT = (
    ROOT
    / "stage33_evaluations"
    / "stage33e_empirical_readiness_handoff_20260901"
    / "design_audit_01"
)
STAGE33E_VERIFICATION = (
    ROOT
    / "stage33_evaluations"
    / "stage33e_empirical_readiness_handoff_20260901"
    / "synthetic_verification_01"
)
STAGE33D_GATES = (
    ROOT
    / "stage33_designs"
    / "stage33d_matched_pet_lbs_physical_validation_20260901"
    / "release_01"
    / "acceptance_gates.json"
)
STAGE32A_RELEASE = (
    ROOT
    / "stage32_designs"
    / "stage32a_matched_constant_head_validation_20260828"
    / "design_01"
)

EXPECTED_SOURCES = {
    "stage33d_acceptance_gates": STAGE33D_GATES,
    "stage33e_resolved_handoff": STAGE33E_RELEASE / "resolved_handoff.json",
    "stage33e_completion": STAGE33E_RELEASE / "completion.json",
    "stage33e_evidence_requirements": STAGE33E_RELEASE / "evidence_requirements.json",
    "stage33e_evidence_slot_registry": STAGE33E_RELEASE / "evidence_slot_registry.json",
    "stage33e_readiness_state_machine": STAGE33E_RELEASE / "readiness_state_machine.json",
    "stage33e_readiness_gate_graph": STAGE33E_RELEASE / "readiness_gate_graph.json",
    "stage33e_authority_matrix": STAGE33E_RELEASE / "authority_matrix.json",
    "stage33e_design_audit": STAGE33E_AUDIT / "audit.json",
    "stage33e_design_audit_completion": STAGE33E_AUDIT / "completion.json",
    "stage33e_hostile_verification": STAGE33E_VERIFICATION / "verification.json",
    "stage33e_hostile_verification_completion": STAGE33E_VERIFICATION / "completion.json",
    "stage32a_contract": ROOT / "stage32_staging" / "STAGE32A_MATCHED_CONSTANT_HEAD_VALIDATION_CONTRACT.md",
    "stage32a_resolved_protocol": STAGE32A_RELEASE / "resolved_protocol.json",
    "stage32a_data_capture_template": STAGE32A_RELEASE / "data_capture_template.csv",
    "stage32c_evaluator": ROOT / "stage32_staging" / "evaluate_stage32c_matched_validation_v1.py",
    "stage33f_contract": STAGING / "STAGE33F_CORE_METHOD_QUALIFICATION_PILOT_CONTRACT_V1.md",
    "stage33f_builder": STAGING / "build_stage33f_core_method_qualification_pilot_v1.py",
    "stage33f_auditor": Path(__file__).resolve(),
    "stage33f_verifier": STAGING / "verify_stage33f_core_method_qualification_pilot_v1.py",
}

EXPECTED_FROZEN_SOURCE_HASHES = {
    "stage33e_resolved_handoff": "93b77932fc73c55783ee9fafbd25430c11278a8ea9d3b505afa073814fc04c81",
    "stage33e_completion": "e2d293db2eedf7f4bc2c7917fe3c0b2d5121c2cc65ce09f23f0d9ece15242438",
    "stage33e_evidence_requirements": "6669c63138cf21da08552bb53e4b0f948f0f33d7f93b519ac3b585183b48a856",
    "stage33e_evidence_slot_registry": "dcf1f29c416a866efc059c8efa9224d649aece236a7310aac6e0ed78732eb8a3",
    "stage33e_readiness_state_machine": "6d4b93d95c9fac54edaa23c4d0225361c6c03ccd7ff56596d89976cbc99c1ab0",
    "stage33e_readiness_gate_graph": "d4e61c7641e49bc4024d70e8d874e63fa1f77ab2c96dff217ac8c89f6503e28e",
    "stage33e_authority_matrix": "47c0eb3c64c4dcb790b99d89893a66800ad2ca3cdc588356a24d0fa59b764965",
    "stage33e_design_audit": "c22f347ce20f43a9678696d624f3218fe03b04003caac198153179e0f083a518",
    "stage33e_design_audit_completion": "7354873e1eb103d885f41fd045d30a2efc20d8bcf12b73c9d9bd86c741016dca",
    "stage33e_hostile_verification": "51b40165f2bbadc02685095596ad0d73c207de8c665adf97d2f1f5d5dd22fd49",
    "stage33e_hostile_verification_completion": "c683798ce1f11ab5f3836c1b532975b028877c6ed6f5dc871d62f22d3f559a77",
    "stage33d_acceptance_gates": "c9ce9eafe68f60d0f1f264ce37c33553369fe2dd50106dc0b72999358a925d17",
    "stage32a_contract": "a3e99a82a88bcd8bdd5485f50346863d1c34ebe53fd60e24251cbcfdfa81f3ff",
    "stage32a_resolved_protocol": "1dd39461555dc21b780a67784b19f9bd703b43e5aeef5bcfa4462950504b2e6e",
    "stage32a_data_capture_template": "2be61855afdcc7b8c9fa8431f96bccddb422b1c596db52e8190b450d0d3a0ff1",
    "stage32c_evaluator": "adedcb1f04747e1cce00b3f589fa570e25a3bd9eb715f4727791bc4c5b7ed254",
}

EXPECTED_FILES = {
    "RUNBOOK.md",
    "STAGE33F_CORE_METHOD_QUALIFICATION_PILOT_CONTRACT_V1.md",
    "authority_matrix.json",
    "completion.json",
    "calibration_capture_template.csv",
    "darcy_linearity_capture_template.csv",
    "effluent_method_plan_template.json",
    "effluent_validation_capture_template.csv",
    "failure_codes.json",
    "hydraulic_sentinel_capture_template.csv",
    "instrument_inventory_template.csv",
    "lineage_manifest.json",
    "mass_balance_template.csv",
    "negative_challenge_plan.json",
    "pilot_acceptance_rule_registry.csv",
    "pilot_evidence_product_registry.json",
    "pilot_execution_manifest_template.csv",
    "pilot_gate_graph.json",
    "pilot_state_machine.json",
    "pilot_work_package_registry.json",
    "packing_attempt_template.csv",
    "q0_requirements_freeze_template.json",
    "resolved_pilot_design.json",
    "saturation_leak_stationarity_template.csv",
    "split_representativeness_template.csv",
    "stage33e_interface_bindings.json",
    "standards_register.json",
    "uncertainty_budget_template.csv",
}

EXPECTED_INTERFACES = {
    "evidence_register": "evidence_register_template.csv",
    "apparatus_calibration": "apparatus_calibration_requirements.csv",
    "uncertainty_budget": "uncertainty_budget_requirements.csv",
    "packing_capability": "packing_capability_capture_template.csv",
    "mass_split": "mass_split_requirements.csv",
    "split_representativeness": "split_representativeness_capture_template.csv",
    "effluent_method": "effluent_method_requirements.csv",
    "roles_and_key_custody": "roles_and_key_custody_template.json",
    "production_toolchain_audit": "production_operational_toolchain_audit_template.json",
    "evidence_submission_envelope": "evidence_submission_envelope_template.json",
}

EXPECTED_WORK_PACKAGES = {
    "WP00": "production_toolchain_dry_run",
    "WP10": "apparatus_traceability_and_uncertainty",
    "WP20": "packing_repeatability_and_hydraulic_blank",
    "WP30": "dry_mass_budget_and_split_representativeness",
    "WP40": "effluent_pet_detection_method",
    "WP50": "end_to_end_blinded_nonconfirmatory_pilot",
    "WP60": "independent_pilot_adjudication",
}

EXPECTED_AUTHORITY_FIELDS = {
    "real_identifier_or_key_ingest",
    "pilot_execution",
    "pilot_data_ingest",
    "pilot_evidence_acceptance",
    "laboratory_execution",
    "hydraulic_measurement",
    "empirical_analysis",
    "treatment_reveal",
    "physical_validation_claim",
    "absolute_permeability_validation_claim",
    "length_as_degradation_proxy_claim",
    "molecular_degradation_claim",
    "pet_specific_model_validation_claim",
    "numerical_execution",
    "migration_or_clogging_claim",
    "deformation_or_coupling_claim",
}

EXPECTED_WORK_PACKAGE_DEPENDENCIES = {
    "WP00": [],
    "WP10": ["WP00"],
    "WP20": ["WP00"],
    "WP30": ["WP00"],
    "WP40": ["WP00"],
    "WP50": ["WP10", "WP20", "WP30", "WP40"],
    "WP60": ["WP50"],
}

EXPECTED_GATE_GRAPH = [
    ("PF-G00", "DESIGN_LINEAGE", [], "pass"),
    ("PF-G10", "PROSPECTIVE_RULE_COMPLETENESS", ["PF-G00"], "blocked"),
    ("PF-G20", "PRODUCTION_TOOLCHAIN_AND_ROLE_CUSTODY", ["PF-G10"], "blocked"),
    ("PF-G30", "APPARATUS_TRACEABILITY_AND_UNCERTAINTY", ["PF-G20"], "blocked"),
    ("PF-G40", "PACKING_AND_MASS_SPLIT", ["PF-G20"], "blocked"),
    ("PF-G50", "EFFLUENT_METHOD", ["PF-G20"], "blocked"),
    ("PF-G60", "END_TO_END_NONCONFIRMATORY_PREFLIGHT", ["PF-G30", "PF-G40", "PF-G50"], "blocked"),
    ("PF-G70", "PILOT_ELIGIBILITY_NOT_AUTHORITY", ["PF-G60"], "blocked"),
    ("PF-G80", "PILOT_EVIDENCE_INDEPENDENT_ACCEPTANCE", ["PF-G70"], "blocked"),
]

EXPECTED_STATES = [
    ("P00_DESIGN_DRAFT", False),
    ("P10_PILOT_PROTOCOL_FROZEN_EMPIRICAL_EMPTY", True),
    ("P20_REAL_PILOT_INPUTS_STAGED_UNVERIFIED", False),
    ("P30_PREEXECUTION_AUDIT_PASSED", False),
    ("P40_NONCONFIRMATORY_PILOT_ELIGIBLE_NOT_AUTHORIZED", False),
    ("P50_PILOT_EVIDENCE_FROZEN", False),
    ("P60_PILOT_QUALIFICATION_INDEPENDENTLY_AUDITED", False),
    ("P70_CANDIDATE_STAGE33E_TRANSITION_ENVELOPES_ELIGIBLE", False),
]

EXPECTED_TRANSITION_REQUIREMENTS = [
    "new immutable release",
    "prior completion SHA-256",
    "submission envelope SHA-256",
    "evaluator SHA-256 and result",
    "independent audit SHA-256 and result",
    "no in-place edit, state skip, replay or automatic authority",
]

EXPECTED_CAPTURE_HEADERS = {
    "instrument_inventory_template.csv": [
        "instrument_role", "instrument_id", "model", "serial_number", "resolution",
        "working_range", "certificate_path", "certificate_sha256", "reference_standard_id",
        "traceability", "valid_from_utc", "valid_to_utc", "software_firmware",
        "sop_path", "sop_sha256", "current_status",
    ],
    "calibration_capture_template.csv": [
        "calibration_id", "instrument_id", "point_index", "nominal_level", "units",
        "reference_value", "observed_value", "correction", "repeat_index", "as_found",
        "as_left", "environment", "standard_uncertainty", "coverage_factor",
        "expanded_uncertainty", "decision_rule_id", "pass", "record_path", "record_sha256",
    ],
    "uncertainty_budget_template.csv": [
        "budget_id", "measurand", "component_id", "source", "value", "units",
        "standard_uncertainty", "distribution", "sensitivity_coefficient", "covariance_group",
        "degrees_of_freedom", "combined_standard_uncertainty", "coverage_factor",
        "expanded_uncertainty", "decision_rule_id", "pass", "record_path", "record_sha256",
    ],
    "packing_attempt_template.csv": [
        "attempt_id", "q_phase", "block_id", "day_id", "cell_id", "operator_id",
        "material_role", "material_id", "pack_order", "sand_dry_mass_g", "pet_dry_mass_g",
        "sand_density_g_cm3", "pet_density_g_cm3", "specimen_volume_cm3",
        "void_ratio", "void_ratio_u95", "preflow_eligible", "failure_code",
        "raw_record_path", "raw_record_sha256",
    ],
    "saturation_leak_stationarity_template.csv": [
        "attempt_id", "q_phase", "cell_id", "saturation_method", "pore_volume_target",
        "water_uptake", "water_uptake_u95", "saturation_metric", "saturation_threshold",
        "external_leak_rate", "external_leak_u95", "leak_threshold", "wall_bypass_check",
        "stationarity_window_n", "stationarity_slope", "stationarity_cv",
        "stationarity_rule_id", "influent_effluent_closure", "pass", "failure_code",
        "raw_record_path", "raw_record_sha256",
    ],
    "mass_balance_template.csv": [
        "batch_id", "q_phase", "blank_correction", "moisture_correction",
        "initial_pet_dry_mass", "recovered_pet_dry_mass", "chamber_loss", "transfer_loss",
        "filter_loss", "other_loss", "process_closure", "process_closure_u95",
        "morphology_aliquot", "chemistry_aliquot", "hydraulic_aliquot_1",
        "hydraulic_aliquot_2", "hydraulic_aliquot_3", "archive_aliquot", "residual_mass",
        "split_loss", "split_closure", "split_closure_u95", "decision_rule_id", "pass",
        "raw_record_path", "raw_record_sha256",
    ],
    "split_representativeness_template.csv": [
        "batch_id", "q_phase", "daughter_id", "comparison_id", "metric",
        "parent_estimate", "daughter_estimate", "bias", "precision", "equivalence_margin",
        "uncertainty", "method", "decision_rule_id", "pass", "raw_record_path", "raw_record_sha256",
    ],
    "effluent_validation_capture_template.csv": [
        "analytical_batch_id", "q_phase", "sample_id", "sample_role", "matrix_role",
        "pet_morphology_role", "nominal_pet_mass", "sample_volume", "subsampling_fraction",
        "filter_id", "filter_lot", "transfer_recovery", "identity_method", "identity_result",
        "blank_signal", "observed_signal", "lob", "lod", "loq", "mass_equivalent_lod",
        "maximum_undetected_fraction", "false_positive_flag", "false_negative_flag",
        "decision", "raw_record_path", "raw_record_sha256",
    ],
    "hydraulic_sentinel_capture_template.csv": [
        "column_id", "q_phase", "block_id", "batch_id", "material_role", "clean_match_id",
        "cell_id", "operator_id", "packing_attempt_id", "gradient_order_code",
        "saturation_pass", "leak_pass", "stationarity_pass", "mass_balance_pass",
        "effluent_decision", "void_ratio", "void_ratio_u95", "pet_dose_wt_percent",
        "pet_dose_u95", "water_temperature_c", "eligible", "failure_code",
        "raw_manifest_path", "raw_manifest_sha256",
    ],
    "darcy_linearity_capture_template.csv": [
        "column_id", "gradient_index", "gradient_sequence_role", "head_difference",
        "specimen_length", "collection_start_utc", "collection_end_utc", "elapsed_s",
        "effluent_mass_or_volume", "water_temperature_c", "discharge", "gradient",
        "k_t", "k20_supplied", "k20_recomputed", "crosscheck_relative_error",
        "particle_reynolds_number", "stationary", "raw_record_path", "raw_record_sha256",
    ],
}

EXPECTED_INHERITED_RULE_METRICS = {
    "K20_calculation_crosscheck_relative_error",
    "target_total_solid_void_ratio",
    "void_ratio_absolute_tolerance",
    "water_temperature_target",
    "water_temperature_absolute_tolerance",
    "target_pet_dry_mass_percent",
    "pet_dose_absolute_tolerance",
    "pet_dose_relative_tolerance",
    "distinct_positive_gradients",
    "discharge_gradient_r_squared",
    "within_sentinel_K20_cv",
    "particle_reynolds_number",
    "clean_K20_cv_within_block",
    "valid_clean_controls_per_block",
    "valid_matched_sets_per_pilot_batch",
    "minimum_relevant_production_log_ratio_effect",
    "monotonicity_is_not_a_gate",
    "PET_at_or_above_validated_LoD",
    "future_required_batch_endpoints",
}

EXPECTED_INHERITED_RULE_VALUES = {
    "K20_calculation_crosscheck_relative_error": ("WP50", "<=", "0.005", "fraction"),
    "target_total_solid_void_ratio": ("WP20", "==", "0.744", "dimensionless"),
    "void_ratio_absolute_tolerance": ("WP20", "<=", "0.01", "dimensionless"),
    "water_temperature_target": ("WP50", "==", "20.0", "degree_C"),
    "water_temperature_absolute_tolerance": ("WP50", "<=", "0.5", "degree_C"),
    "target_pet_dry_mass_percent": ("WP30", "==", "0.09841784362759924", "wt_percent"),
    "pet_dose_absolute_tolerance": ("WP30", "<=", "0.0005", "wt_percent"),
    "pet_dose_relative_tolerance": ("WP30", "<=", "0.05", "fraction"),
    "distinct_positive_gradients": ("WP50", ">=", "3", "count"),
    "discharge_gradient_r_squared": ("WP50", ">=", "0.99", "dimensionless"),
    "within_sentinel_K20_cv": ("WP50", "<=", "0.05", "fraction"),
    "particle_reynolds_number": ("WP50", "<=", "1.0", "dimensionless"),
    "clean_K20_cv_within_block": ("WP20", "<=", "0.05", "fraction"),
    "valid_clean_controls_per_block": ("WP20", ">=", "2", "count"),
    "valid_matched_sets_per_pilot_batch": ("WP50", ">=", "2", "count"),
    "minimum_relevant_production_log_ratio_effect": ("WP50", "==", "0.05129329438755058", "log_ratio"),
    "monotonicity_is_not_a_gate": ("WP50", "==", "true", "boolean"),
    "PET_at_or_above_validated_LoD": ("WP40", "==", "fails_fixed_solid", "decision"),
    "future_required_batch_endpoints": ("WP50", "==", "15", "count"),
}

EXPECTED_UNRESOLVED_RULE_METRICS = {
    "instrument_role_tolerance_and_guard_band",
    "combined_uncertainty_target_by_measurand",
    "maximum_external_leak_or_bypass",
    "quantitative_saturation_endpoint",
    "stationarity_slope_and_variation_limits",
    "packing_yield_or_capability_rule",
    "process_mass_closure_interval",
    "split_mass_closure_interval",
    "split_morphology_equivalence_margins",
    "blank_acceptance_and_false_positive_rule",
    "transfer_and_filter_recovery_acceptance",
    "precision_and_bias_acceptance",
    "LoB_LoD_LoQ_or_equivalent",
    "maximum_undetected_PET_fraction",
    "actual_gradient_values_and_order",
    "minimum_collection_mass_time_and_windows",
    "particle_Re_definition_and_characteristic_length",
    "Q2_holdout_counts_and_sentinel_bracketing",
}

EXPECTED_NEGATIVE_CHALLENGES = [
    "source_mutation", "parent_audit_failed", "parent_state_advanced",
    "parent_slot_prepopulated", "interface_path_or_hash_redirect", "authority_enabled",
    "current_state_advanced", "execution_authorized_true", "real_material_id_inserted",
    "real_operator_id_inserted", "real_instrument_or_store_id_inserted",
    "secret_or_key_path_inserted", "stage33do_test_artifact_reused",
    "confirmatory_batch_id_inserted", "pilot_marked_confirmatory_or_reusable",
    "empirical_observation_inserted", "method_specific_threshold_invented",
    "inherited_threshold_mutated", "monotonicity_gate_added",
    "missing_duplicate_or_unknown_work_package", "candidate_product_autoaccepted",
    "optional_chemistry_or_numerics_unlock_core", "missing_or_extra_artifact",
    "completion_hash_mismatch", "link_or_hardlink_alias", "audit_output_overwrite",
]

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

FORBIDDEN_RELEASE_TOKENS = {
    "STAGE33DO-TEST_ONLY-SYNTHETIC-QUALIFICATION-01",
    "1ec7bda776fa270043eff091ea99971928956a2705a075c45352fb95141c6cb6",
    "successful_release",
}


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_regular(path: Path, role: str, *, single_link: bool = False) -> None:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(
            f"E33F_UNEXPECTED_FILE: {role} is not a regular non-symlink file: {path}"
        )
    if single_link and os.stat(path, follow_symlinks=False).st_nlink != 1:
        raise RuntimeError(
            f"E33F_LINK_ALIAS: {role} has unsafe link count: {path}"
        )
    attributes = getattr(os.stat(path, follow_symlinks=False), "st_file_attributes", 0)
    if attributes & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
        raise RuntimeError(f"E33F_LINK_ALIAS: {role} is a reparse point: {path}")


def load_json(path: Path) -> Any:
    require_regular(path, path.name)
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    require_regular(path, path.name)
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise RuntimeError(f"E33F_UNEXPECTED_FILE: CSV missing header: {path}")
        return list(reader.fieldnames), list(reader)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def tree_snapshot(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*"), key=lambda value: str(value).lower()):
        if path.is_dir():
            continue
        require_regular(path, f"release:{path.name}", single_link=True)
        snapshot[path.relative_to(root).as_posix()] = sha256(path)
    return snapshot


def source_snapshot(source_records: dict[str, Any]) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for role, record in source_records.items():
        path = Path(record.get("path", ""))
        require_regular(path, f"source:{role}", single_link=True)
        snapshot[role] = sha256(path)
    return snapshot


def all_false(mapping: Any) -> bool:
    return isinstance(mapping, dict) and bool(mapping) and all(
        value is False for value in mapping.values()
    )


def blank(value: Any) -> bool:
    return value in ("", None, [], {})


def recursively_contains_nonblank_forbidden_field(value: Any) -> bool:
    """Reject populated fields that carry real identities, keys, or observations."""

    forbidden_fragments = (
        "instrument_id",
        "serial_number",
        "operator_id",
        "reviewer_id",
        "auditor_id",
        "custodian_id",
        "analyst_id",
        "material_id",
        "specimen_id",
        "cell_id",
        "site_id",
        "store_id",
        "secret",
        "key_path",
        "key_sha256",
        "measurement_value",
        "observed_value",
        "raw_value",
        "result_value",
    )

    def visit(node: Any) -> bool:
        if isinstance(node, dict):
            for key, child in node.items():
                key_lower = str(key).lower()
                if any(fragment in key_lower for fragment in forbidden_fragments):
                    if not blank(child):
                        return True
                if visit(child):
                    return True
        elif isinstance(node, list):
            return any(visit(child) for child in node)
        return False

    return visit(value)


def audit_release(
    release: Path,
) -> tuple[dict[str, Any], dict[str, str], dict[str, str]]:
    if not release.is_dir() or release.is_symlink():
        raise RuntimeError(
            f"E33F_UNEXPECTED_FILE: release is not a regular directory: {release}"
        )
    release_attributes = getattr(
        os.stat(release, follow_symlinks=False), "st_file_attributes", 0
    )
    if release_attributes & 0x400:
        raise RuntimeError(f"E33F_LINK_ALIAS: release is a reparse point: {release}")
    if any(path.is_dir() for path in release.iterdir()):
        raise RuntimeError("E33F_UNEXPECTED_FILE: nested release directories are forbidden")

    observed_files = {path.name for path in release.iterdir() if path.is_file()}
    if observed_files != EXPECTED_FILES:
        raise RuntimeError(
            "E33F_UNEXPECTED_FILE: file set mismatch; "
            f"missing={sorted(EXPECTED_FILES - observed_files)}, "
            f"extra={sorted(observed_files - EXPECTED_FILES)}"
        )
    release_before = tree_snapshot(release)

    resolved = load_json(release / "resolved_pilot_design.json")
    lineage = load_json(release / "lineage_manifest.json")
    interfaces = load_json(release / "stage33e_interface_bindings.json")
    work_packages = load_json(release / "pilot_work_package_registry.json")
    gate_graph = load_json(release / "pilot_gate_graph.json")
    state_machine = load_json(release / "pilot_state_machine.json")
    evidence_products = load_json(release / "pilot_evidence_product_registry.json")
    standards = load_json(release / "standards_register.json")
    q0 = load_json(release / "q0_requirements_freeze_template.json")
    effluent_plan = load_json(release / "effluent_method_plan_template.json")
    authority = load_json(release / "authority_matrix.json")
    failures = load_json(release / "failure_codes.json")
    challenges = load_json(release / "negative_challenge_plan.json")
    completion = load_json(release / "completion.json")

    checks: dict[str, bool] = {}

    def check(name: str, condition: bool) -> None:
        checks[name] = bool(condition)

    created_utc = resolved.get("created_utc")
    check(
        "release_timestamp_consistent",
        isinstance(created_utc, str)
        and created_utc.endswith("Z")
        and all(
            payload.get("created_utc") == created_utc
            for payload in (
                lineage,
                interfaces,
                work_packages,
                gate_graph,
                state_machine,
                evidence_products,
                authority,
                failures,
                challenges,
                completion,
            )
        )
        and standards.get("checked_utc") == created_utc,
    )

    check(
        "resolved_identity_and_design_only_state",
        resolved.get("schema")
        == "pet.stage33f-core-method-qualification-pilot-design.v1"
        and resolved.get("stage") == "Stage33F"
        and resolved.get("release_id") == RELEASE_ID
        and resolved.get("status")
        == "frozen_design_only_q0_unpopulated_execution_closed"
        and resolved.get("current_state")
        == "P10_PILOT_PROTOCOL_FROZEN_EMPIRICAL_EMPTY"
        and resolved.get("no_empirical_data") is True
        and resolved.get("no_real_identifiers") is True
        and resolved.get("no_real_key") is True
        and resolved.get("no_laboratory_execution") is True
        and resolved.get("no_numerical_execution") is True
        and resolved.get("q0_requirements_populated") is False
        and resolved.get("q1_development_executed") is False
        and resolved.get("q2_independent_holdout_executed") is False
        and resolved.get("q3_evidence_eligible") is False
        and resolved.get("automatic_stage33e_acceptance") is False
        and resolved.get("monotonicity_is_not_a_gate") is True
        and set(resolved)
        == {
            "schema",
            "stage",
            "release_id",
            "created_utc",
            "status",
            "current_state",
            "research_question",
            "experimental_boundary",
            "no_empirical_data",
            "no_real_identifiers",
            "no_real_key",
            "no_laboratory_execution",
            "no_numerical_execution",
            "q0_requirements_populated",
            "q1_development_executed",
            "q2_independent_holdout_executed",
            "q3_evidence_eligible",
            "candidate_minimum_holdout",
            "future_stage33e_candidate_roles",
            "automatic_stage33e_acceptance",
            "monotonicity_is_not_a_gate",
            "authority",
            "claim_boundary",
            "stop_boundary",
        },
    )
    check(
        "resolved_authority_closed",
        set(resolved.get("authority", {})) == EXPECTED_AUTHORITY_FIELDS
        and all_false(resolved.get("authority")),
    )
    check(
        "candidate_holdout_recommended_but_not_adopted",
        resolved.get("candidate_minimum_holdout", {}).get("adopted_at_q0") is False
        and resolved.get("candidate_minimum_holdout", {}).get("status")
        == "recommended_but_unresolved_blocking"
        and resolved.get("candidate_minimum_holdout", {}).get("total_columns") == 27
        and resolved.get("candidate_minimum_holdout", {}).get(
            "independent_PET_parent_batches"
        ) == 6
        and resolved.get("candidate_minimum_holdout", {}).get(
            "qualification_blocks"
        ) == 3
        and resolved.get("candidate_minimum_holdout", {}).get(
            "clean_columns_per_block"
        ) == 3
        and resolved.get("candidate_minimum_holdout", {}).get(
            "long_coarse_PET_columns_per_block"
        ) == 3
        and resolved.get("candidate_minimum_holdout", {}).get(
            "short_fine_PET_columns_per_block"
        ) == 3
        and set(resolved.get("candidate_minimum_holdout", {}))
        == {
            "adopted_at_q0",
            "status",
            "qualification_blocks",
            "clean_columns_per_block",
            "long_coarse_PET_columns_per_block",
            "short_fine_PET_columns_per_block",
            "total_columns",
            "independent_PET_parent_batches",
            "rationale",
            "binding_condition",
        }
        and resolved.get("future_stage33e_candidate_roles")
        == [
            "hydraulic_apparatus_calibration_release",
            "pet_mass_budget_and_split_qualification",
            "effluent_pet_detection_method_release",
        ],
    )

    source_records = lineage.get("sources", {})
    check(
        "lineage_identity_and_exact_roles",
        lineage.get("schema") == "pet.stage33f-lineage-manifest.v1"
        and lineage.get("stage") == "Stage33F"
        and lineage.get("release_id") == RELEASE_ID
        and lineage.get("source_n") == len(EXPECTED_SOURCES)
        and set(source_records) == set(EXPECTED_SOURCES),
    )
    source_paths_exact = True
    source_hashes_exact = True
    source_paths_unique: set[str] = set()
    for role, expected_path in EXPECTED_SOURCES.items():
        record = source_records.get(role, {})
        expected_resolved = str(expected_path.resolve())
        source_paths_exact &= record.get("path") == expected_resolved
        source_hashes_exact &= (
            set(record) == {"path", "sha256", "bytes"}
            and
            expected_path.is_file()
            and record.get("sha256") == sha256(expected_path)
            and record.get("bytes") == expected_path.stat().st_size
            and (
                role not in EXPECTED_FROZEN_SOURCE_HASHES
                or record.get("sha256") == EXPECTED_FROZEN_SOURCE_HASHES[role]
            )
        )
        source_paths_unique.add(str(record.get("path", "")).lower())
    check("source_paths_exact", source_paths_exact)
    check("source_hashes_exact", source_hashes_exact)
    check("source_paths_unique", len(source_paths_unique) == len(EXPECTED_SOURCES))
    check(
        "lineage_closure_flags_exact",
        lineage.get("source_snapshot_unchanged_during_build") is True
        and lineage.get("stage33e_parent_empirical_slots_empty") is True
        and lineage.get("stage33e_parent_audit_39_of_39") is True
        and lineage.get("stage33e_parent_hostile_verification_18_of_18") is True
        and lineage.get("stage33d_gates_semantically_exact") is True,
    )
    sources_before = source_snapshot(source_records)

    stage33e_resolved = load_json(EXPECTED_SOURCES["stage33e_resolved_handoff"])
    stage33e_slots = load_json(EXPECTED_SOURCES["stage33e_evidence_slot_registry"])
    stage33e_state = load_json(EXPECTED_SOURCES["stage33e_readiness_state_machine"])
    stage33e_authority = load_json(EXPECTED_SOURCES["stage33e_authority_matrix"])
    stage33e_audit = load_json(EXPECTED_SOURCES["stage33e_design_audit"])
    stage33e_audit_completion = load_json(
        EXPECTED_SOURCES["stage33e_design_audit_completion"]
    )
    stage33e_verification = load_json(
        EXPECTED_SOURCES["stage33e_hostile_verification"]
    )
    stage33e_verification_completion = load_json(
        EXPECTED_SOURCES["stage33e_hostile_verification_completion"]
    )
    stage33e_completion = load_json(EXPECTED_SOURCES["stage33e_completion"])
    stage33d_gates = load_json(EXPECTED_SOURCES["stage33d_acceptance_gates"])

    check(
        "stage33e_parent_exact_and_empirical_empty",
        stage33e_resolved.get("schema")
        == "pet.stage33e-empirical-readiness-handoff.v1"
        and stage33e_resolved.get("status")
        == "frozen_design_only_all_empirical_inputs_unpopulated"
        and stage33e_resolved.get("current_state")
        == "S10_DESIGN_FROZEN_EMPIRICAL_EMPTY"
        and stage33e_resolved.get("no_empirical_data") is True
        and stage33e_resolved.get("no_real_identifiers") is True
        and stage33e_resolved.get("no_real_key") is True
        and stage33e_resolved.get("no_laboratory_execution") is True
        and stage33e_resolved.get("no_numerical_execution") is True,
    )
    slot_rows = stage33e_slots.get("slots", [])
    check(
        "stage33e_all_nine_slots_empty",
        stage33e_slots.get("slot_n") == 9
        and len(slot_rows) == 9
        and all(
            row.get("populated") is False
            and row.get("verified") is False
            and row.get("decision") == "not_submitted"
            and all(
                row.get(field) == ""
                for field in (
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
                )
            )
            for row in slot_rows
        ),
    )
    active_e_states = [
        row.get("state_id")
        for row in stage33e_state.get("states", [])
        if row.get("active") is True
    ]
    check(
        "stage33e_parent_state_and_authority_closed",
        stage33e_state.get("current_state") == "S10"
        and active_e_states == ["S10"]
        and all_false(stage33e_authority.get("authority")),
    )
    check(
        "stage33e_parent_independent_audit_passed",
        stage33e_audit.get("passed") is True
        and stage33e_audit.get("passed_check_n") == 39
        and stage33e_audit.get("failed_check_n") == 0
        and stage33e_audit_completion.get("passed") is True,
    )
    check(
        "stage33e_parent_hostile_verification_passed",
        stage33e_verification.get("passed") is True
        and stage33e_verification.get("test_only") is True
        and stage33e_verification.get("negative_challenge_n") == 18
        and stage33e_verification.get("negative_challenges_passed_n") == 18
        and stage33e_verification_completion.get("passed") is True,
    )
    check(
        "stage33e_parent_completion_closed",
        stage33e_completion.get("passed") is True
        and stage33e_completion.get("all_empirical_slots_empty") is True
        and stage33e_completion.get("production_toolchain_ready") is False
        and stage33e_completion.get("all_authority_closed") is True,
    )
    check(
        "inherited_stage33d_thresholds_exact",
        stage33d_gates == EXPECTED_STAGE33D_GATES,
    )

    expected_standard_ids = {
        "ISO 17892-11:2019",
        "ASTM D2434-26",
        "ISO/IEC 17025:2017",
        "JCGM 100:2008",
        "JCGM 106:2012",
        "Eurachem Fitness for Purpose 2025",
        "Eurachem Equipment and Systems 2025",
        "Eurachem Blanks Supplement",
        "ISO 24187:2023",
        "ISO 5667-27:2025",
        "ISO 16094-2:2025",
    }
    standard_rows = standards.get("standards", [])
    check(
        "standards_register_is_catalogue_only",
        standards.get("schema") == "pet.stage33f-standards-register.v1"
        and standards.get("stage") == "Stage33F"
        and standards.get("release_id") == RELEASE_ID
        and standards.get("catalogue_metadata_only") is True
        and standards.get("licensed_full_text_required_before_q0_freeze_where_applicable")
        is True
        and len(standard_rows) == len(expected_standard_ids)
        and {row.get("id") for row in standard_rows} == expected_standard_ids
        and all(
            bool(row.get("status"))
            and bool(row.get("role"))
            and str(row.get("url", "")).startswith("https://")
            for row in standard_rows
        )
        and "citation supplies structure only"
        in standards.get("qualification_rule", ""),
    )

    interface_records = interfaces.get("interfaces", [])
    completion_artifacts = stage33e_completion.get("artifacts", {})
    interface_by_role = {
        record.get("interface_role"): record for record in interface_records
    }
    check(
        "stage33e_interface_identity_and_exact_roles",
        interfaces.get("schema") == "pet.stage33f-stage33e-interface-bindings.v1"
        and interfaces.get("stage") == "Stage33F"
        and interfaces.get("release_id") == RELEASE_ID
        and interfaces.get("parent_release_id")
        == "STAGE33E-EMPIRICAL-READINESS-HANDOFF-01"
        and interfaces.get("parent_completion_path")
        == str((STAGE33E_RELEASE / "completion.json").resolve())
        and interfaces.get("parent_completion_sha256")
        == sha256(STAGE33E_RELEASE / "completion.json")
        and interfaces.get("interface_n") == len(EXPECTED_INTERFACES)
        and len(interface_records) == len(EXPECTED_INTERFACES)
        and set(interface_by_role) == set(EXPECTED_INTERFACES)
        and interfaces.get("candidate_evidence_only") is True
        and interfaces.get("automatic_stage33e_acceptance") is False,
    )
    interface_exact = True
    for role, name in EXPECTED_INTERFACES.items():
        record = interface_by_role.get(role, {})
        parent_record = completion_artifacts.get(name, {})
        interface_exact &= record.get("source_path") == parent_record.get("path")
        interface_exact &= record.get("source_sha256") == parent_record.get("sha256")
        interface_exact &= record.get("parent_completion_sha256") == parent_record.get("sha256")
        interface_exact &= (
            record.get("source_path") == str((STAGE33E_RELEASE / name).resolve())
            and Path(record.get("source_path", "")).is_file()
            and record.get("source_sha256") == sha256(STAGE33E_RELEASE / name)
            and record.get("current_state") == "BOUND_PARENT_TEMPLATE_EMPTY"
            and record.get("automatic_population") is False
            and set(record)
            == {
                "interface_role",
                "source_path",
                "source_sha256",
                "parent_completion_sha256",
                "current_state",
                "automatic_population",
            }
        )
    check("stage33e_interface_bindings_exact", interface_exact)
    check(
        "stage33e_interfaces_are_referenced_not_duplicated",
        not any(name in observed_files for name in EXPECTED_INTERFACES.values()),
    )

    package_rows = work_packages.get("work_packages", [])
    observed_packages = {
        row.get("work_package_id"): row.get("name") for row in package_rows
    }
    check(
        "work_package_registry_exact",
        work_packages.get("schema")
        == "pet.stage33f-pilot-work-package-registry.v1"
        and work_packages.get("stage") == "Stage33F"
        and work_packages.get("release_id") == RELEASE_ID
        and work_packages.get("work_package_n") == len(EXPECTED_WORK_PACKAGES)
        and len(package_rows) == len(EXPECTED_WORK_PACKAGES)
        and observed_packages == EXPECTED_WORK_PACKAGES
        and all(
            row.get("dependencies")
            == EXPECTED_WORK_PACKAGE_DEPENDENCIES.get(row.get("work_package_id"))
            and set(row)
            == {
                "work_package_id",
                "name",
                "dependencies",
                "current_status",
                "nonconfirmatory_only",
                "confirmatory_reuse_forbidden",
                "observations_present",
                "completion_path",
                "completion_sha256",
                "audit_path",
                "audit_sha256",
            }
            for row in package_rows
        ),
    )
    check(
        "all_work_packages_not_executed_and_nonconfirmatory",
        all(
            row.get("current_status") == "NOT_EXECUTED"
            and row.get("nonconfirmatory_only") is True
            and row.get("confirmatory_reuse_forbidden") is True
            and row.get("observations_present") is False
            and all(
                row.get(field) == ""
                for field in (
                    "completion_path",
                    "completion_sha256",
                    "audit_path",
                    "audit_sha256",
                )
            )
            for row in package_rows
        ),
    )
    check(
        "work_packages_contain_no_real_fields",
        not recursively_contains_nonblank_forbidden_field(work_packages),
    )

    state_rows = state_machine.get("states", [])
    active_states = [row for row in state_rows if row.get("active") is True]
    check(
        "only_design_state_active",
        state_machine.get("schema") == "pet.stage33f-pilot-state-machine.v1"
        and state_machine.get("stage") == "Stage33F"
        and state_machine.get("release_id") == RELEASE_ID
        and state_machine.get("active_state")
        == "P10_PILOT_PROTOCOL_FROZEN_EMPIRICAL_EMPTY"
        and [(row.get("state_id"), row.get("active")) for row in state_rows]
        == EXPECTED_STATES
        and len(active_states) == 1,
    )
    check(
        "state_transitions_are_new_immutable_releases",
        state_machine.get("transition_requirements")
        == EXPECTED_TRANSITION_REQUIREMENTS,
    )

    gate_rows = gate_graph.get("gates", [])
    pass_gates = [row for row in gate_rows if row.get("current_status") == "pass"]
    check(
        "only_design_lineage_gate_passes",
        gate_graph.get("schema") == "pet.stage33f-pilot-gate-graph.v1"
        and gate_graph.get("stage") == "Stage33F"
        and gate_graph.get("release_id") == RELEASE_ID
        and gate_graph.get("passing_gate_n") == 1
        and len(pass_gates) == 1
        and [
            (
                row.get("gate_id"),
                row.get("name"),
                row.get("dependencies"),
                row.get("current_status"),
            )
            for row in gate_rows
        ]
        == EXPECTED_GATE_GRAPH
        and "never grants laboratory or production authority"
        in gate_graph.get("rule", ""),
    )

    check(
        "authority_matrix_closed",
        authority.get("schema") == "pet.stage33f-authority-matrix.v1"
        and authority.get("stage") == "Stage33F"
        and authority.get("release_id") == RELEASE_ID
        and authority.get("all_authority_closed") is True
        and set(authority.get("authority", {})) == EXPECTED_AUTHORITY_FIELDS
        and all_false(authority.get("authority")),
    )
    check(
        "q0_template_identity_and_closed",
        q0.get("schema") == "pet.stage33f-q0-requirements-freeze-template.v1"
        and q0.get("stage") == "Stage33F"
        and q0.get("release_id") == RELEASE_ID
        and q0.get("template_status") == "UNPOPULATED_BLOCKING"
        and q0.get("candidate_27_column_holdout_adopted") is False
        and q0.get("all_method_specific_rules_frozen") is False
        and q0.get("independent_review_passed") is False
        and q0.get("execution_authorized") is False,
    )
    q0_blank_fields = (
        "q0_release_id",
        "freeze_utc",
        "institution_or_site_id",
        "method_owner_id",
        "independent_reviewer_id",
        "operator_role_ids",
        "cell_ids",
        "instrument_ids",
        "material_ids",
        "sop_bindings",
        "risk_assessment_path",
        "risk_assessment_sha256",
        "working_ranges",
        "measurement_models",
        "uncertainty_models",
        "decision_rules",
        "q1_sample_counts",
        "q2_sample_counts",
        "sentinel_bracketing_evidence_path",
        "sentinel_bracketing_evidence_sha256",
        "completion_path",
        "completion_sha256",
    )
    check(
        "q0_real_fields_and_rules_all_blank",
        all(blank(q0.get(field)) for field in q0_blank_fields)
        and set(q0)
        == {
            "schema",
            "stage",
            "release_id",
            "template_status",
            *q0_blank_fields,
            "candidate_27_column_holdout_adopted",
            "all_method_specific_rules_frozen",
            "independent_review_passed",
            "execution_authorized",
        },
    )

    execution_headers, execution_rows = load_csv(
        release / "pilot_execution_manifest_template.csv"
    )
    expected_execution_headers = [
        "pilot_slot_id",
        "work_package_id",
        "qualification_role",
        "sequence_block",
        "randomization_stratum",
        "nonconfirmatory_only",
        "confirmatory_reuse_forbidden",
        "material_id",
        "operator_id",
        "instrument_ids",
        "scheduled_utc",
        "execution_authorized",
        "execution_status",
        "resolved_protocol_path",
        "resolved_protocol_sha256",
        "raw_manifest_path",
        "raw_manifest_sha256",
        "completion_path",
        "completion_sha256",
        "audit_path",
        "audit_sha256",
    ]
    check("execution_manifest_header_exact", execution_headers == expected_execution_headers)
    check(
        "execution_manifest_design_only",
        len(execution_rows) == 6
        and {row.get("work_package_id") for row in execution_rows}
        == set(EXPECTED_WORK_PACKAGES) - {"WP60"}
        and all(
            row.get("nonconfirmatory_only") == "true"
            and row.get("confirmatory_reuse_forbidden") == "true"
            and row.get("execution_authorized") == "false"
            and row.get("execution_status") == "NOT_EXECUTED"
            and all(
                row.get(field, "") == ""
                for field in (
                    "material_id",
                    "operator_id",
                    "instrument_ids",
                    "scheduled_utc",
                    "resolved_protocol_path",
                    "resolved_protocol_sha256",
                    "raw_manifest_path",
                    "raw_manifest_sha256",
                    "completion_path",
                    "completion_sha256",
                    "audit_path",
                    "audit_sha256",
                )
            )
            for row in execution_rows
        ),
    )

    rule_headers, rule_rows = load_csv(
        release / "pilot_acceptance_rule_registry.csv"
    )
    required_rule_headers = {
        "rule_id",
        "work_package_id",
        "metric",
        "operator",
        "threshold_value",
        "threshold_units",
        "threshold_source_role",
        "threshold_source_path",
        "threshold_source_sha256",
        "prospective_rule_frozen",
        "method_specific",
        "blocking_if_blank",
        "current_status",
    }
    check(
        "acceptance_rule_header_exact",
        rule_headers
        == [
            "rule_id",
            "work_package_id",
            "metric",
            "operator",
            "threshold_value",
            "threshold_units",
            "threshold_source_role",
            "threshold_source_path",
            "threshold_source_sha256",
            "prospective_rule_frozen",
            "method_specific",
            "blocking_if_blank",
            "current_status",
        ]
        and set(rule_headers) == required_rule_headers,
    )
    method_rows = [row for row in rule_rows if row.get("method_specific") == "true"]
    inherited_rows = [row for row in rule_rows if row.get("method_specific") == "false"]
    check(
        "acceptance_rule_sets_exact",
        len(rule_rows) == 37
        and len({row.get("rule_id") for row in rule_rows}) == 37
        and {row.get("rule_id") for row in inherited_rows}
        == {f"R{index:03d}" for index in range(1, 20)}
        and {row.get("rule_id") for row in method_rows}
        == {f"R{index:03d}" for index in range(101, 119)}
        and {row.get("metric") for row in inherited_rows}
        == EXPECTED_INHERITED_RULE_METRICS
        and {row.get("metric") for row in method_rows}
        == EXPECTED_UNRESOLVED_RULE_METRICS,
    )
    check(
        "method_specific_rules_blank_and_blocking",
        bool(method_rows)
        and all(
            row.get("threshold_value") == ""
            and row.get("threshold_units") == ""
            and row.get("operator") == ""
            and row.get("threshold_source_role") == ""
            and row.get("threshold_source_path") == ""
            and row.get("threshold_source_sha256") == ""
            and row.get("prospective_rule_frozen") == "false"
            and row.get("blocking_if_blank") == "true"
            and row.get("current_status") == "UNRESOLVED_BLOCKING"
            for row in method_rows
        ),
    )
    check(
        "inherited_rules_bound_to_stage33d",
        bool(inherited_rows)
        and all(
            (
                row.get("work_package_id"),
                row.get("operator"),
                row.get("threshold_value"),
                row.get("threshold_units"),
            )
            == EXPECTED_INHERITED_RULE_VALUES.get(row.get("metric"))
            and row.get("blocking_if_blank") == "false"
            and row.get("threshold_source_role") == "stage33d_acceptance_gates"
            and row.get("threshold_source_path") == str(STAGE33D_GATES.resolve())
            and row.get("threshold_source_sha256") == sha256(STAGE33D_GATES)
            and row.get("prospective_rule_frozen") == "true"
            and row.get("current_status") == "INHERITED_FROZEN"
            for row in inherited_rows
        ),
    )
    rule_text = "\n".join(
        "|".join(row.get(header, "") for header in rule_headers) for row in rule_rows
    ).lower()
    check(
        "monotonicity_or_direction_not_a_gate",
        "monotonicity_required" not in rule_text
        and "obstruction_sign" not in rule_text
        and "temperature_order" not in rule_text,
    )

    capture_templates_exact = True
    for filename, expected_headers in EXPECTED_CAPTURE_HEADERS.items():
        headers, rows = load_csv(release / filename)
        capture_templates_exact &= headers == expected_headers and rows == []
    check(
        "all_nine_capture_templates_exact_and_empty",
        capture_templates_exact,
    )

    effluent_plan_blank_fields = (
        "method_id",
        "q0_freeze_utc",
        "sample_vessel_and_train",
        "filter_cutoffs",
        "subsampling_validation_path",
        "subsampling_validation_sha256",
        "pet_identity_method",
        "matrix_blank_plan",
        "procedural_blank_plan",
        "positive_control_plan",
        "morphology_bracketing_plan",
        "recovery_plan",
        "precision_bias_plan",
        "false_positive_negative_plan",
        "lob_lod_loq_plan",
        "mass_equivalent_detection_model",
        "maximum_undetected_fraction_rule",
        "q2_independent_holdout_plan",
    )
    check(
        "effluent_method_plan_empty_and_closed",
        effluent_plan.get("schema")
        == "pet.stage33f-effluent-method-plan-template.v1"
        and effluent_plan.get("stage") == "Stage33F"
        and effluent_plan.get("release_id") == RELEASE_ID
        and effluent_plan.get("template_status") == "UNPOPULATED_BLOCKING"
        and effluent_plan.get("full_volume_capture") is None
        and effluent_plan.get("q1_development_data_reuse_in_q2") is False
        and effluent_plan.get("independent_review_passed") is False
        and effluent_plan.get("execution_authorized") is False
        and all(blank(effluent_plan.get(field)) for field in effluent_plan_blank_fields)
        and set(effluent_plan)
        == {
            "schema",
            "stage",
            "release_id",
            "template_status",
            *effluent_plan_blank_fields,
            "full_volume_capture",
            "q1_development_data_reuse_in_q2",
            "independent_review_passed",
            "execution_authorized",
        },
    )

    product_rows = evidence_products.get("products", [])
    expected_products = {
        "hydraulic_apparatus_calibration_release": ["WP10", "WP20", "WP50"],
        "pet_mass_budget_and_split_qualification": ["WP30"],
        "effluent_pet_detection_method_release": ["WP40"],
    }
    check(
        "evidence_products_are_candidate_only",
        evidence_products.get("schema")
        == "pet.stage33f-pilot-evidence-product-registry.v1"
        and evidence_products.get("stage") == "Stage33F"
        and evidence_products.get("release_id") == RELEASE_ID
        and evidence_products.get("product_n") == 3
        and evidence_products.get("current_status")
        == "ALL_CANDIDATE_PRODUCTS_EMPTY"
        and len(product_rows) == 3
        and {
            row.get("target_stage33e_slot_id"): row.get("source_work_packages")
            for row in product_rows
        }
        == expected_products
        and all(
            row.get("generated") is False
            and row.get("submitted") is False
            and row.get("verified") is False
            and row.get("automatic_stage33e_acceptance") is False
            and set(row)
            == {
                "target_stage33e_slot_id",
                "source_work_packages",
                "manifest_path",
                "manifest_sha256",
                "completion_path",
                "completion_sha256",
                "audit_path",
                "audit_sha256",
                "generated",
                "submitted",
                "verified",
                "automatic_stage33e_acceptance",
            }
            and all(
                blank(row.get(field))
                for field in (
                    "manifest_path",
                    "manifest_sha256",
                    "completion_path",
                    "completion_sha256",
                    "audit_path",
                    "audit_sha256",
                )
            )
            for row in product_rows
        ),
    )

    check(
        "no_real_identifiers_keys_or_observations",
        not any(
            recursively_contains_nonblank_forbidden_field(payload)
            for payload in (
                resolved,
                interfaces,
                work_packages,
                gate_graph,
                state_machine,
                evidence_products,
                q0,
                effluent_plan,
                authority,
            )
        ),
    )
    contract_text = (
        release / "STAGE33F_CORE_METHOD_QUALIFICATION_PILOT_CONTRACT_V1.md"
    ).read_text(encoding="utf-8")
    check(
        "contract_copy_hash_exact",
        sha256(release / "STAGE33F_CORE_METHOD_QUALIFICATION_PILOT_CONTRACT_V1.md")
        == sha256(EXPECTED_SOURCES["stage33f_contract"]),
    )
    check(
        "contract_claim_boundary_preserved",
        "DESIGN_ONLY_Q0_NOT_POPULATED" in contract_text
        and "method-development and independent-qualification design" in contract_text
        and "Below LoD is reported as `nondetect`, never zero" in contract_text
        and "Monotonicity is not an acceptance gate" in contract_text,
    )
    release_text = "\n".join(
        (release / name).read_text(encoding="utf-8", errors="ignore")
        for name in sorted(EXPECTED_FILES)
    ).lower()
    check(
        "no_stage33do_secret_identifier_or_successful_release",
        not any(token.lower() in release_text for token in FORBIDDEN_RELEASE_TOKENS),
    )
    check(
        "no_confirmatory_material_or_data_reuse",
        "confirmatory_reuse_allowed" not in release_text
        and "production_batch_measurement" not in release_text,
    )

    required_failure_codes = {
        "E33F_OVERWRITE_REFUSED",
        "E33F_UNEXPECTED_FILE",
        "E33F_SOURCE_HASH_MISMATCH",
        "E33F_PARENT_NOT_EMPTY",
        "E33F_INTERFACE_BINDING_MISMATCH",
        "E33F_AUTHORITY_LEAK",
        "E33F_REAL_IDENTIFIER_OR_SECRET_PRESENT",
        "E33F_CONFIRMATORY_CONTAMINATION",
        "E33F_EXECUTION_STATE_ADVANCE",
        "E33F_UNJUSTIFIED_RULE",
        "E33F_INHERITED_GATE_MUTATION",
        "E33F_WORK_PACKAGE_SET_INVALID",
        "E33F_EVIDENCE_AUTOACCEPTED",
        "E33F_TEMPLATE_POPULATED",
        "E33F_LINK_ALIAS",
        "E33F_HASH_CLOSURE_FAILED",
    }
    check(
        "failure_code_set_substantive",
        failures.get("schema") == "pet.stage33f-failure-codes.v1"
        and failures.get("stage") == "Stage33F"
        and failures.get("release_id") == RELEASE_ID
        and required_failure_codes.issubset(failures.get("failure_codes", {}))
        and len(failures.get("failure_codes", {})) == 19,
    )
    check(
        "negative_challenge_plan_substantive",
        challenges.get("schema") == "pet.stage33f-negative-challenge-plan.v1"
        and challenges.get("stage") == "Stage33F"
        and challenges.get("release_id") == RELEASE_ID
        and challenges.get("challenge_n") == len(EXPECTED_NEGATIVE_CHALLENGES)
        and challenges.get("challenges") == EXPECTED_NEGATIVE_CHALLENGES
        and "every hostile mutation is rejected fail-closed"
        in challenges.get("pass_rule", ""),
    )

    completion_records = completion.get("artifacts", {})
    expected_artifacts = EXPECTED_FILES - {"completion.json"}
    completion_exact = (
        set(completion_records) == expected_artifacts
        and completion.get("artifact_n") == len(expected_artifacts)
    )
    for name in expected_artifacts:
        record = completion_records.get(name, {})
        completion_exact &= record.get("path") == str(release / name)
        completion_exact &= record.get("sha256") == sha256(release / name)
        completion_exact &= record.get("bytes") == (release / name).stat().st_size
    check(
        "completion_hash_closure_exact",
        completion.get("schema")
        == "pet.stage33f-core-method-qualification-pilot-design-completion.v1"
        and completion.get("stage") == "Stage33F"
        and completion.get("release_id") == RELEASE_ID
        and completion.get("passed") is True
        and completion.get("no_empirical_data") is True
        and completion.get("no_real_identifiers") is True
        and completion.get("no_real_key") is True
        and completion.get("no_laboratory_execution") is True
        and completion.get("no_numerical_execution") is True
        and completion.get("q0_requirements_populated") is False
        and completion.get("all_authority_closed") is True
        and completion.get("candidate_evidence_products_empty") is True
        and completion.get("status")
        == "complete_design_ready_for_independent_audit_execution_closed"
        and completion_exact,
    )

    failed_checks = sorted(name for name, passed in checks.items() if not passed)
    if failed_checks:
        raise RuntimeError(
            "E33F_DESIGN_AUDIT_FAILED: " + ", ".join(failed_checks)
        )

    release_after = tree_snapshot(release)
    sources_after = source_snapshot(source_records)
    if release_before != release_after or sources_before != sources_after:
        raise RuntimeError(
            "E33F_INPUT_MUTATION: release or source changed during audit"
        )

    audit = {
        "schema": "pet.stage33f-core-method-qualification-pilot-design-audit.v1",
        "stage": "Stage33F",
        "release_id": RELEASE_ID,
        "created_utc": now_utc(),
        "status": "passed_design_only_q0_empty_audit",
        "passed": True,
        "check_n": len(checks),
        "passed_check_n": sum(checks.values()),
        "failed_check_n": 0,
        "failed_checks": [],
        "checks": checks,
        "input_mutation": False,
        "counts": {
            "source_bindings": len(source_records),
            "stage33e_interfaces": len(interface_records),
            "work_packages": len(package_rows),
            "acceptance_rules": len(rule_rows),
            "method_specific_blocking_rules": len(method_rows),
            "active_states": len(active_states),
            "passing_gates": len(pass_gates),
            "release_artifacts": len(EXPECTED_FILES),
            "stage33e_populated_slots": 0,
            "empty_capture_templates": len(EXPECTED_CAPTURE_HEADERS),
            "candidate_evidence_products": len(product_rows),
            "standards_catalogue_entries": len(standard_rows),
        },
        "authority": dict(authority["authority"]),
        "readiness": {
            "q0_requirements_populated": False,
            "q1_development_executed": False,
            "q2_independent_holdout_executed": False,
            "q3_evidence_eligible": False,
            "pilot_execution_ready": False,
        },
        "conclusion": (
            "The Stage33F pilot design is internally consistent and hash-bound, "
            "but Q0 is unpopulated and no pilot, laboratory, empirical, or "
            "numerical execution is ready or authorized."
        ),
        "claim_boundary": (
            "design-audit evidence only; no method qualification, PET effect, "
            "absolute permeability, degradation, or model-validation claim"
        ),
        "stop_boundary": resolved.get("stop_boundary"),
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
        raise RuntimeError(f"E33F_OVERWRITE_REFUSED: output exists: {output}")
    if output == release or release in output.parents or output in release.parents:
        raise RuntimeError(
            "E33F_UNEXPECTED_FILE: audit output must be disjoint from release"
        )
    output.parent.mkdir(parents=True, exist_ok=True)

    audit, _, _ = audit_release(release)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.", dir=str(output.parent))
    )
    try:
        write_json(temporary / "audit.json", audit)
        write_json(
            temporary / "completion.json",
            {
                "schema": "pet.stage33f-core-method-qualification-pilot-design-audit-completion.v1",
                "stage": "Stage33F",
                "release_id": RELEASE_ID,
                "created_utc": now_utc(),
                "status": "complete",
                "passed": True,
                "audit_path": str(output / "audit.json"),
                "audit_sha256": sha256(temporary / "audit.json"),
                "failed_checks": [],
                "input_mutation": False,
                "no_empirical_data": True,
                "all_authority_closed": True,
                "pilot_execution_ready": False,
                "next_handoff": (
                    "hostile synthetic mutation verification of this design "
                    "auditor only"
                ),
            },
        )
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    print(
        json.dumps(
            {
                "passed": True,
                "output": str(output),
                "check_n": audit["check_n"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL-CLOSED: {type(exc).__name__}: {exc}", file=os.sys.stderr)
        raise SystemExit(2)
