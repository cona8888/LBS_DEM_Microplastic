#!/usr/bin/env python3
"""Build the immutable, design-only Stage33F method-qualification pilot.

The builder has no laboratory, empirical, identifier, secret, key, or numerical
execution input.  It freezes only a prospective Q0/Q1/Q2/Q3 architecture and
refuses to overwrite an existing release.
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
from typing import Any, Iterable


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STAGING = ROOT / "stage33_staging"
DEFAULT_OUTPUT = (
    ROOT
    / "stage33_designs"
    / "stage33f_core_method_qualification_pilot_20260901"
    / "release_01"
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
STAGE33E_VERIFY = (
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

CONTRACT = STAGING / "STAGE33F_CORE_METHOD_QUALIFICATION_PILOT_CONTRACT_V1.md"
BUILDER = Path(__file__).resolve()
AUDITOR = STAGING / "audit_stage33f_core_method_qualification_pilot_v1.py"
VERIFIER = STAGING / "verify_stage33f_core_method_qualification_pilot_v1.py"

EXPECTED_SOURCE_HASHES = {
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

SOURCE_PATHS = {
    "stage33e_resolved_handoff": STAGE33E_RELEASE / "resolved_handoff.json",
    "stage33e_completion": STAGE33E_RELEASE / "completion.json",
    "stage33e_evidence_requirements": STAGE33E_RELEASE / "evidence_requirements.json",
    "stage33e_evidence_slot_registry": STAGE33E_RELEASE / "evidence_slot_registry.json",
    "stage33e_readiness_state_machine": STAGE33E_RELEASE / "readiness_state_machine.json",
    "stage33e_readiness_gate_graph": STAGE33E_RELEASE / "readiness_gate_graph.json",
    "stage33e_authority_matrix": STAGE33E_RELEASE / "authority_matrix.json",
    "stage33e_design_audit": STAGE33E_AUDIT / "audit.json",
    "stage33e_design_audit_completion": STAGE33E_AUDIT / "completion.json",
    "stage33e_hostile_verification": STAGE33E_VERIFY / "verification.json",
    "stage33e_hostile_verification_completion": STAGE33E_VERIFY / "completion.json",
    "stage33d_acceptance_gates": STAGE33D_GATES,
    "stage32a_contract": STAGING.parent / "stage32_staging" / "STAGE32A_MATCHED_CONSTANT_HEAD_VALIDATION_CONTRACT.md",
    "stage32a_resolved_protocol": STAGE32A_RELEASE / "resolved_protocol.json",
    "stage32a_data_capture_template": STAGE32A_RELEASE / "data_capture_template.csv",
    "stage32c_evaluator": STAGING.parent / "stage32_staging" / "evaluate_stage32c_matched_validation_v1.py",
    "stage33f_contract": CONTRACT,
    "stage33f_builder": BUILDER,
    "stage33f_auditor": AUDITOR,
    "stage33f_verifier": VERIFIER,
}

INTERFACE_FILES = {
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

EXPECTED_INTERFACE_HASHES = {
    "evidence_register_template.csv": "bed069da45da10358a59a6c1e3523dd60d9a421885da3f4baa169a74afce7bbb",
    "apparatus_calibration_requirements.csv": "876ac2173a541c2390aa69e9d7a0a59bf42637a16409b526da84a9d3bff1cece",
    "uncertainty_budget_requirements.csv": "13a2a51ddbdf73e2475ed6e5927352ac710bd424b90e56bde1932d6770f33906",
    "packing_capability_capture_template.csv": "69375d17216db9a8cbc987ea57807d4bb02e4ffb71edad5aa05080fb985b0737",
    "mass_split_requirements.csv": "5c1606f35186a82627388935b2652b82ff771a275ee41bee7359d5208e43f7ab",
    "split_representativeness_capture_template.csv": "a40c45c0b4eb93a37c10cf800fecd35279590c0869d5927bacc017ea0e826897",
    "effluent_method_requirements.csv": "3ac2f68c881a681ce3560d4c0371ef994741cf802755239c9694e8756e5c445c",
    "roles_and_key_custody_template.json": "302c677677d5d3e4468c3484ba2c913602d9d100ad694e8c91546bc5dcf738e1",
    "production_operational_toolchain_audit_template.json": "76bd547102c4ed357b12b69da96a9ae5fad31422a39f5f94fa21e695322cb8f1",
    "evidence_submission_envelope_template.json": "706a2500f68a66620017622b4d98b361529473ad4ff59e934b936bdcb3de408a",
}

EXPECTED_STAGE33D_GATES: dict[str, Any] = {
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

WORK_PACKAGES = (
    ("WP00", "production_toolchain_dry_run", []),
    ("WP10", "apparatus_traceability_and_uncertainty", ["WP00"]),
    ("WP20", "packing_repeatability_and_hydraulic_blank", ["WP00"]),
    ("WP30", "dry_mass_budget_and_split_representativeness", ["WP00"]),
    ("WP40", "effluent_pet_detection_method", ["WP00"]),
    ("WP50", "end_to_end_blinded_nonconfirmatory_pilot", ["WP10", "WP20", "WP30", "WP40"]),
    ("WP60", "independent_pilot_adjudication", ["WP50"]),
)

AUTHORITY = {
    "real_identifier_or_key_ingest": False,
    "pilot_execution": False,
    "pilot_data_ingest": False,
    "pilot_evidence_acceptance": False,
    "laboratory_execution": False,
    "hydraulic_measurement": False,
    "empirical_analysis": False,
    "treatment_reveal": False,
    "physical_validation_claim": False,
    "absolute_permeability_validation_claim": False,
    "length_as_degradation_proxy_claim": False,
    "molecular_degradation_claim": False,
    "pet_specific_model_validation_claim": False,
    "numerical_execution": False,
    "migration_or_clogging_claim": False,
    "deformation_or_coupling_claim": False,
}


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require_regular(path: Path, role: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"E33F_SOURCE_INVALID: {role}: {path}")


def load_json(path: Path) -> Any:
    require_regular(path, path.name)
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, fieldnames: Iterable[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fieldnames), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def validate_sources() -> dict[str, dict[str, Any]]:
    bindings: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    for role, path in SOURCE_PATHS.items():
        require_regular(path, role)
        resolved = str(path.resolve())
        if resolved.lower() in seen:
            raise RuntimeError(f"E33F_SOURCE_INVALID: duplicate source path for {role}")
        seen.add(resolved.lower())
        digest = sha256(path)
        expected = EXPECTED_SOURCE_HASHES.get(role)
        if expected and digest != expected:
            raise RuntimeError(f"E33F_SOURCE_HASH_MISMATCH: {role}: {digest} != {expected}")
        bindings[role] = {
            "path": resolved,
            "sha256": digest,
            "bytes": path.stat().st_size,
        }

    resolved = load_json(SOURCE_PATHS["stage33e_resolved_handoff"])
    if not (
        resolved.get("schema") == "pet.stage33e-empirical-readiness-handoff.v1"
        and resolved.get("status") == "frozen_design_only_all_empirical_inputs_unpopulated"
        and resolved.get("current_state") == "S10_DESIGN_FROZEN_EMPIRICAL_EMPTY"
        and resolved.get("no_empirical_data") is True
        and resolved.get("no_laboratory_execution") is True
        and resolved.get("no_numerical_execution") is True
        and all(value is False for value in resolved.get("authority", {}).values())
    ):
        raise RuntimeError("E33F_PARENT_NOT_EMPTY: Stage33E resolved state is not the audited empty state")

    parent_completion = load_json(SOURCE_PATHS["stage33e_completion"])
    if not (
        parent_completion.get("passed") is True
        and parent_completion.get("all_empirical_slots_empty") is True
        and parent_completion.get("all_authority_closed") is True
        and parent_completion.get("no_empirical_data") is True
    ):
        raise RuntimeError("E33F_PARENT_NOT_EMPTY: Stage33E completion is not closed")

    slots = load_json(SOURCE_PATHS["stage33e_evidence_slot_registry"])
    if slots.get("slot_n") != 9 or len(slots.get("slots", [])) != 9:
        raise RuntimeError("E33F_PARENT_NOT_EMPTY: Stage33E slot set changed")
    blank_keys = (
        "manifest_path", "manifest_sha256", "completion_path", "completion_sha256",
        "audit_path", "audit_sha256", "submission_id", "receipt_utc", "freeze_utc",
        "expected_schema",
    )
    for slot in slots["slots"]:
        if any(slot.get(key) not in ("", None) for key in blank_keys):
            raise RuntimeError("E33F_PARENT_NOT_EMPTY: Stage33E slot binding is populated")
        if slot.get("populated") is not False or slot.get("verified") is not False:
            raise RuntimeError("E33F_PARENT_NOT_EMPTY: Stage33E slot state is populated")
        if slot.get("decision") != "not_submitted":
            raise RuntimeError("E33F_PARENT_NOT_EMPTY: Stage33E slot decision changed")

    audit = load_json(SOURCE_PATHS["stage33e_design_audit"])
    if not (audit.get("passed") is True and audit.get("check_n") == 39 and audit.get("failed_check_n") == 0):
        raise RuntimeError("E33F_PARENT_AUDIT_FAILED: Stage33E design audit is not 39/39")
    verification = load_json(SOURCE_PATHS["stage33e_hostile_verification"])
    if not (
        verification.get("passed") is True
        and verification.get("negative_challenge_n") == 18
        and verification.get("negative_challenges_passed_n") == 18
    ):
        raise RuntimeError("E33F_PARENT_AUDIT_FAILED: Stage33E hostile verification is not 18/18")

    if load_json(STAGE33D_GATES) != EXPECTED_STAGE33D_GATES:
        raise RuntimeError("E33F_INHERITED_GATE_MUTATION: Stage33D gates changed")

    for filename, expected_hash in EXPECTED_INTERFACE_HASHES.items():
        path = STAGE33E_RELEASE / filename
        require_regular(path, filename)
        if sha256(path) != expected_hash:
            raise RuntimeError(f"E33F_INTERFACE_BINDING_MISMATCH: {filename}")
        completion_entry = parent_completion.get("artifacts", {}).get(filename, {})
        if completion_entry.get("sha256") != expected_hash:
            raise RuntimeError(f"E33F_INTERFACE_BINDING_MISMATCH: completion map for {filename}")

    return bindings


def inherited_rule_rows() -> list[dict[str, Any]]:
    fixed = [
        ("R001", "WP50", "K20_calculation_crosscheck_relative_error", "<=", 0.005, "fraction"),
        ("R002", "WP20", "target_total_solid_void_ratio", "==", 0.744, "dimensionless"),
        ("R003", "WP20", "void_ratio_absolute_tolerance", "<=", 0.01, "dimensionless"),
        ("R004", "WP50", "water_temperature_target", "==", 20.0, "degree_C"),
        ("R005", "WP50", "water_temperature_absolute_tolerance", "<=", 0.5, "degree_C"),
        ("R006", "WP30", "target_pet_dry_mass_percent", "==", 0.09841784362759924, "wt_percent"),
        ("R007", "WP30", "pet_dose_absolute_tolerance", "<=", 0.0005, "wt_percent"),
        ("R008", "WP30", "pet_dose_relative_tolerance", "<=", 0.05, "fraction"),
        ("R009", "WP50", "distinct_positive_gradients", ">=", 3, "count"),
        ("R010", "WP50", "discharge_gradient_r_squared", ">=", 0.99, "dimensionless"),
        ("R011", "WP50", "within_sentinel_K20_cv", "<=", 0.05, "fraction"),
        ("R012", "WP50", "particle_reynolds_number", "<=", 1.0, "dimensionless"),
        ("R013", "WP20", "clean_K20_cv_within_block", "<=", 0.05, "fraction"),
        ("R014", "WP20", "valid_clean_controls_per_block", ">=", 2, "count"),
        ("R015", "WP50", "valid_matched_sets_per_pilot_batch", ">=", 2, "count"),
        ("R016", "WP50", "minimum_relevant_production_log_ratio_effect", "==", 0.05129329438755058, "log_ratio"),
        ("R017", "WP50", "monotonicity_is_not_a_gate", "==", "true", "boolean"),
        ("R018", "WP40", "PET_at_or_above_validated_LoD", "==", "fails_fixed_solid", "decision"),
        ("R019", "WP50", "future_required_batch_endpoints", "==", 15, "count"),
    ]
    rows: list[dict[str, Any]] = []
    source = str(STAGE33D_GATES.resolve())
    source_hash = sha256(STAGE33D_GATES)
    for rule_id, wp, metric, op, value, units in fixed:
        rows.append({
            "rule_id": rule_id,
            "work_package_id": wp,
            "metric": metric,
            "operator": op,
            "threshold_value": value,
            "threshold_units": units,
            "threshold_source_role": "stage33d_acceptance_gates",
            "threshold_source_path": source,
            "threshold_source_sha256": source_hash,
            "prospective_rule_frozen": "true",
            "method_specific": "false",
            "blocking_if_blank": "false",
            "current_status": "INHERITED_FROZEN",
        })

    unresolved = [
        ("R101", "WP10", "instrument_role_tolerance_and_guard_band"),
        ("R102", "WP10", "combined_uncertainty_target_by_measurand"),
        ("R103", "WP20", "maximum_external_leak_or_bypass"),
        ("R104", "WP20", "quantitative_saturation_endpoint"),
        ("R105", "WP20", "stationarity_slope_and_variation_limits"),
        ("R106", "WP20", "packing_yield_or_capability_rule"),
        ("R107", "WP30", "process_mass_closure_interval"),
        ("R108", "WP30", "split_mass_closure_interval"),
        ("R109", "WP30", "split_morphology_equivalence_margins"),
        ("R110", "WP40", "blank_acceptance_and_false_positive_rule"),
        ("R111", "WP40", "transfer_and_filter_recovery_acceptance"),
        ("R112", "WP40", "precision_and_bias_acceptance"),
        ("R113", "WP40", "LoB_LoD_LoQ_or_equivalent"),
        ("R114", "WP40", "maximum_undetected_PET_fraction"),
        ("R115", "WP50", "actual_gradient_values_and_order"),
        ("R116", "WP50", "minimum_collection_mass_time_and_windows"),
        ("R117", "WP50", "particle_Re_definition_and_characteristic_length"),
        ("R118", "WP50", "Q2_holdout_counts_and_sentinel_bracketing"),
    ]
    for rule_id, wp, metric in unresolved:
        rows.append({
            "rule_id": rule_id,
            "work_package_id": wp,
            "metric": metric,
            "operator": "",
            "threshold_value": "",
            "threshold_units": "",
            "threshold_source_role": "",
            "threshold_source_path": "",
            "threshold_source_sha256": "",
            "prospective_rule_frozen": "false",
            "method_specific": "true",
            "blocking_if_blank": "true",
            "current_status": "UNRESOLVED_BLOCKING",
        })
    return rows


def build(output: Path) -> None:
    if output.exists():
        raise RuntimeError(f"E33F_OVERWRITE_REFUSED: output exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    before = validate_sources()
    created = now_utc()
    tmp = Path(tempfile.mkdtemp(prefix=".stage33f_build.", dir=str(output.parent)))
    try:
        shutil.copyfile(CONTRACT, tmp / CONTRACT.name)

        resolved = {
            "schema": "pet.stage33f-core-method-qualification-pilot-design.v1",
            "stage": "Stage33F",
            "release_id": RELEASE_ID,
            "created_utc": created,
            "status": "frozen_design_only_q0_unpopulated_execution_closed",
            "current_state": "P10_PILOT_PROTOCOL_FROZEN_EMPIRICAL_EMPTY",
            "research_question": "Can the future nonconfirmatory laboratory chain be independently qualified before confirmatory PET batches are consumed?",
            "experimental_boundary": "method capability only; no treatment or temperature-effect inference",
            "no_empirical_data": True,
            "no_real_identifiers": True,
            "no_real_key": True,
            "no_laboratory_execution": True,
            "no_numerical_execution": True,
            "q0_requirements_populated": False,
            "q1_development_executed": False,
            "q2_independent_holdout_executed": False,
            "q3_evidence_eligible": False,
            "candidate_minimum_holdout": {
                "adopted_at_q0": False,
                "status": "recommended_but_unresolved_blocking",
                "qualification_blocks": 3,
                "clean_columns_per_block": 3,
                "long_coarse_PET_columns_per_block": 3,
                "short_fine_PET_columns_per_block": 3,
                "total_columns": 27,
                "independent_PET_parent_batches": 6,
                "rationale": "three days, two morphology bounds, three technical columns per batch and enough clean controls to retain two after one invalid control",
                "binding_condition": "Q0 must demonstrate sentinel bracketing and bind actual cells/operators/ranges/uncertainty before adoption",
            },
            "future_stage33e_candidate_roles": [
                "hydraulic_apparatus_calibration_release",
                "pet_mass_budget_and_split_qualification",
                "effluent_pet_detection_method_release",
            ],
            "automatic_stage33e_acceptance": False,
            "monotonicity_is_not_a_gate": True,
            "authority": AUTHORITY,
            "claim_boundary": "A future pass means method readiness only; it does not establish PET effects, absolute permeability validity, degradation, model validation, migration, clogging, deformation or coupling.",
            "stop_boundary": "stop before real inventory, identifiers, certificates, SOP adoption, material use, laboratory measurements, production keys, Stage33D work, empirical analysis, DEM/LBM or physics claims",
        }
        write_json(tmp / "resolved_pilot_design.json", resolved)

        standards = {
            "schema": "pet.stage33f-standards-register.v1",
            "stage": "Stage33F",
            "release_id": RELEASE_ID,
            "checked_utc": created,
            "catalogue_metadata_only": True,
            "licensed_full_text_required_before_q0_freeze_where_applicable": True,
            "standards": [
                {"id": "ISO 17892-11:2019", "status": "current_confirmed_2025", "role": "soil permeability test framework", "url": "https://www.iso.org/cms/%20render/live/en/sites/isoorg/contents/data/standard/07/20/72016.html"},
                {"id": "ASTM D2434-26", "status": "active", "role": "constant-head saturated coarse-grained soil framework", "url": "https://store.astm.org/standards/d2434"},
                {"id": "ISO/IEC 17025:2017", "status": "current_confirmed_2023", "role": "laboratory competence and impartiality", "url": "https://www.iso.org/standard/66912.html"},
                {"id": "JCGM 100:2008", "status": "listed_current_GUM_suite", "role": "measurement uncertainty", "url": "https://www.bipm.org/en/committees/jc/jcgm/publications"},
                {"id": "JCGM 106:2012", "status": "published", "role": "conformity decision rules", "url": "https://www.bipm.org/en/doi/10.59161/jcgm106-2012"},
                {"id": "Eurachem Fitness for Purpose 2025", "status": "third_edition", "role": "method validation planning and reporting", "url": "https://www.eurachem.org/index.php/component/content/article/3-publications/guides/144-gdmv2014"},
                {"id": "Eurachem Equipment and Systems 2025", "status": "first_edition", "role": "equipment qualification", "url": "https://www.eurachem.org/index.php/publications/guides/gd-aesq"},
                {"id": "Eurachem Blanks Supplement", "status": "published", "role": "blank design and interpretation", "url": "https://www.eurachem.org/index.php/publications/guides/blanks-in-method-validation"},
                {"id": "ISO 24187:2023", "status": "published", "role": "environmental microplastic analysis principles", "url": "https://www.iso.org/standard/78033.html"},
                {"id": "ISO 5667-27:2025", "status": "published", "role": "sampling suspended microplastics in water", "url": "https://www.iso.org/standard/82612.html"},
                {"id": "ISO 16094-2:2025", "status": "published", "role": "microscopy and vibrational-spectroscopy identification including PET", "url": "https://www.iso.org/cms/%20render/live/en/sites/isoorg/contents/data/standard/08/44/84460.html?browse=tc"},
            ],
            "qualification_rule": "A citation supplies structure only; actual intended-use transfer, capability and uncertainty must be independently validated.",
        }
        write_json(tmp / "standards_register.json", standards)

        parent_completion = load_json(STAGE33E_RELEASE / "completion.json")
        interfaces = []
        for role, filename in INTERFACE_FILES.items():
            interfaces.append({
                "interface_role": role,
                "source_path": str((STAGE33E_RELEASE / filename).resolve()),
                "source_sha256": EXPECTED_INTERFACE_HASHES[filename],
                "parent_completion_sha256": parent_completion["artifacts"][filename]["sha256"],
                "current_state": "BOUND_PARENT_TEMPLATE_EMPTY",
                "automatic_population": False,
            })
        write_json(tmp / "stage33e_interface_bindings.json", {
            "schema": "pet.stage33f-stage33e-interface-bindings.v1",
            "stage": "Stage33F",
            "release_id": RELEASE_ID,
            "created_utc": created,
            "parent_release_id": "STAGE33E-EMPIRICAL-READINESS-HANDOFF-01",
            "parent_completion_path": str((STAGE33E_RELEASE / "completion.json").resolve()),
            "parent_completion_sha256": sha256(STAGE33E_RELEASE / "completion.json"),
            "interface_n": len(interfaces),
            "interfaces": interfaces,
            "candidate_evidence_only": True,
            "automatic_stage33e_acceptance": False,
        })

        write_json(tmp / "pilot_work_package_registry.json", {
            "schema": "pet.stage33f-pilot-work-package-registry.v1",
            "stage": "Stage33F",
            "release_id": RELEASE_ID,
            "created_utc": created,
            "work_package_n": len(WORK_PACKAGES),
            "work_packages": [
                {
                    "work_package_id": wp,
                    "name": name,
                    "dependencies": deps,
                    "current_status": "NOT_EXECUTED",
                    "nonconfirmatory_only": True,
                    "confirmatory_reuse_forbidden": True,
                    "observations_present": False,
                    "completion_path": "",
                    "completion_sha256": "",
                    "audit_path": "",
                    "audit_sha256": "",
                }
                for wp, name, deps in WORK_PACKAGES
            ],
        })

        gates = [
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
        write_json(tmp / "pilot_gate_graph.json", {
            "schema": "pet.stage33f-pilot-gate-graph.v1",
            "stage": "Stage33F",
            "release_id": RELEASE_ID,
            "created_utc": created,
            "passing_gate_n": 1,
            "gates": [
                {"gate_id": gid, "name": name, "dependencies": deps, "current_status": status}
                for gid, name, deps, status in gates
            ],
            "rule": "Eligibility never grants laboratory or production authority; missing or indeterminate criteria are blocking.",
        })

        states = [
            ("P00_DESIGN_DRAFT", False),
            ("P10_PILOT_PROTOCOL_FROZEN_EMPIRICAL_EMPTY", True),
            ("P20_REAL_PILOT_INPUTS_STAGED_UNVERIFIED", False),
            ("P30_PREEXECUTION_AUDIT_PASSED", False),
            ("P40_NONCONFIRMATORY_PILOT_ELIGIBLE_NOT_AUTHORIZED", False),
            ("P50_PILOT_EVIDENCE_FROZEN", False),
            ("P60_PILOT_QUALIFICATION_INDEPENDENTLY_AUDITED", False),
            ("P70_CANDIDATE_STAGE33E_TRANSITION_ENVELOPES_ELIGIBLE", False),
        ]
        write_json(tmp / "pilot_state_machine.json", {
            "schema": "pet.stage33f-pilot-state-machine.v1",
            "stage": "Stage33F",
            "release_id": RELEASE_ID,
            "created_utc": created,
            "active_state": "P10_PILOT_PROTOCOL_FROZEN_EMPIRICAL_EMPTY",
            "states": [{"state_id": sid, "active": active} for sid, active in states],
            "transition_requirements": [
                "new immutable release",
                "prior completion SHA-256",
                "submission envelope SHA-256",
                "evaluator SHA-256 and result",
                "independent audit SHA-256 and result",
                "no in-place edit, state skip, replay or automatic authority",
            ],
        })

        write_json(tmp / "authority_matrix.json", {
            "schema": "pet.stage33f-authority-matrix.v1",
            "stage": "Stage33F",
            "release_id": RELEASE_ID,
            "created_utc": created,
            "authority": AUTHORITY,
            "all_authority_closed": True,
        })

        q0 = {
            "schema": "pet.stage33f-q0-requirements-freeze-template.v1",
            "stage": "Stage33F",
            "release_id": RELEASE_ID,
            "template_status": "UNPOPULATED_BLOCKING",
            "q0_release_id": "",
            "freeze_utc": "",
            "institution_or_site_id": "",
            "method_owner_id": "",
            "independent_reviewer_id": "",
            "operator_role_ids": [],
            "cell_ids": [],
            "instrument_ids": [],
            "material_ids": [],
            "sop_bindings": [],
            "risk_assessment_path": "",
            "risk_assessment_sha256": "",
            "working_ranges": [],
            "measurement_models": [],
            "uncertainty_models": [],
            "decision_rules": [],
            "q1_sample_counts": {},
            "q2_sample_counts": {},
            "sentinel_bracketing_evidence_path": "",
            "sentinel_bracketing_evidence_sha256": "",
            "candidate_27_column_holdout_adopted": False,
            "all_method_specific_rules_frozen": False,
            "independent_review_passed": False,
            "execution_authorized": False,
            "completion_path": "",
            "completion_sha256": "",
        }
        write_json(tmp / "q0_requirements_freeze_template.json", q0)

        execution_fields = [
            "pilot_slot_id", "work_package_id", "qualification_role", "sequence_block",
            "randomization_stratum", "nonconfirmatory_only", "confirmatory_reuse_forbidden",
            "material_id", "operator_id", "instrument_ids", "scheduled_utc",
            "execution_authorized", "execution_status", "resolved_protocol_path",
            "resolved_protocol_sha256", "raw_manifest_path", "raw_manifest_sha256",
            "completion_path", "completion_sha256", "audit_path", "audit_sha256",
        ]
        execution_rows = [
            {
                "pilot_slot_id": f"PILOT-{wp}", "work_package_id": wp,
                "qualification_role": name, "sequence_block": index,
                "randomization_stratum": "", "nonconfirmatory_only": "true",
                "confirmatory_reuse_forbidden": "true", "material_id": "",
                "operator_id": "", "instrument_ids": "", "scheduled_utc": "",
                "execution_authorized": "false", "execution_status": "NOT_EXECUTED",
                "resolved_protocol_path": "", "resolved_protocol_sha256": "",
                "raw_manifest_path": "", "raw_manifest_sha256": "",
                "completion_path": "", "completion_sha256": "", "audit_path": "",
                "audit_sha256": "",
            }
            for index, (wp, name, _) in enumerate(WORK_PACKAGES[:-1], start=1)
        ]
        write_csv(tmp / "pilot_execution_manifest_template.csv", execution_fields, execution_rows)

        rule_fields = [
            "rule_id", "work_package_id", "metric", "operator", "threshold_value",
            "threshold_units", "threshold_source_role", "threshold_source_path",
            "threshold_source_sha256", "prospective_rule_frozen", "method_specific",
            "blocking_if_blank", "current_status",
        ]
        write_csv(tmp / "pilot_acceptance_rule_registry.csv", rule_fields, inherited_rule_rows())

        header_only = {
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
        for filename, fields in header_only.items():
            write_csv(tmp / filename, fields, [])

        write_json(tmp / "effluent_method_plan_template.json", {
            "schema": "pet.stage33f-effluent-method-plan-template.v1",
            "stage": "Stage33F", "release_id": RELEASE_ID,
            "template_status": "UNPOPULATED_BLOCKING", "method_id": "",
            "q0_freeze_utc": "", "sample_vessel_and_train": [], "filter_cutoffs": [],
            "full_volume_capture": None, "subsampling_validation_path": "",
            "subsampling_validation_sha256": "", "pet_identity_method": "",
            "matrix_blank_plan": {}, "procedural_blank_plan": {}, "positive_control_plan": {},
            "morphology_bracketing_plan": {}, "recovery_plan": {}, "precision_bias_plan": {},
            "false_positive_negative_plan": {}, "lob_lod_loq_plan": {},
            "mass_equivalent_detection_model": {}, "maximum_undetected_fraction_rule": {},
            "q1_development_data_reuse_in_q2": False, "q2_independent_holdout_plan": {},
            "independent_review_passed": False, "execution_authorized": False,
        })

        products = [
            ("hydraulic_apparatus_calibration_release", ["WP10", "WP20", "WP50"]),
            ("pet_mass_budget_and_split_qualification", ["WP30"]),
            ("effluent_pet_detection_method_release", ["WP40"]),
        ]
        write_json(tmp / "pilot_evidence_product_registry.json", {
            "schema": "pet.stage33f-pilot-evidence-product-registry.v1",
            "stage": "Stage33F", "release_id": RELEASE_ID, "created_utc": created,
            "product_n": 3,
            "products": [
                {
                    "target_stage33e_slot_id": role, "source_work_packages": wps,
                    "manifest_path": "", "manifest_sha256": "", "completion_path": "",
                    "completion_sha256": "", "audit_path": "", "audit_sha256": "",
                    "generated": False, "submitted": False, "verified": False,
                    "automatic_stage33e_acceptance": False,
                }
                for role, wps in products
            ],
            "current_status": "ALL_CANDIDATE_PRODUCTS_EMPTY",
        })

        failure_codes = {
            "E33F_OVERWRITE_REFUSED": "An immutable output already exists.",
            "E33F_UNEXPECTED_FILE": "Release file set differs from the exact contract.",
            "E33F_SOURCE_INVALID": "A source is missing, aliased, linked or invalid.",
            "E33F_SOURCE_HASH_MISMATCH": "A lineage source differs from its frozen digest.",
            "E33F_PARENT_NOT_EMPTY": "The Stage33E parent is not the audited empirical-empty state.",
            "E33F_PARENT_AUDIT_FAILED": "The parent audit or hostile verification is not fully passed.",
            "E33F_INTERFACE_BINDING_MISMATCH": "A Stage33E interface path/hash differs from its completion map.",
            "E33F_AUTHORITY_LEAK": "Execution, empirical, numerical or claim authority is enabled.",
            "E33F_REAL_IDENTIFIER_OR_SECRET_PRESENT": "A real material/operator/instrument/store/key identifier is present.",
            "E33F_CONFIRMATORY_CONTAMINATION": "Pilot evidence or material is marked reusable for confirmation.",
            "E33F_EXECUTION_STATE_ADVANCE": "The design advanced beyond the empirical-empty P10 state.",
            "E33F_UNJUSTIFIED_RULE": "A method-specific rule was populated without a bound prospective source.",
            "E33F_INHERITED_GATE_MUTATION": "A frozen Stage33D gate changed or monotonicity was imposed.",
            "E33F_WORK_PACKAGE_SET_INVALID": "The work-package set, order or dependency graph changed.",
            "E33F_EVIDENCE_AUTOACCEPTED": "Candidate evidence was automatically accepted into Stage33E.",
            "E33F_TEMPLATE_POPULATED": "A Q0, empirical, calibration or observation template contains data.",
            "E33F_LINK_ALIAS": "A symlink, reparse point or hard-link alias was detected.",
            "E33F_HASH_CLOSURE_FAILED": "Completion or lineage hash closure failed.",
            "E33F_AUDIT_FAILED": "One or more independent design-audit checks failed.",
        }
        write_json(tmp / "failure_codes.json", {
            "schema": "pet.stage33f-failure-codes.v1", "stage": "Stage33F",
            "release_id": RELEASE_ID, "created_utc": created,
            "failure_codes": failure_codes,
        })

        challenges = [
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
        write_json(tmp / "negative_challenge_plan.json", {
            "schema": "pet.stage33f-negative-challenge-plan.v1", "stage": "Stage33F",
            "release_id": RELEASE_ID, "created_utc": created,
            "challenge_n": len(challenges), "challenges": challenges,
            "pass_rule": "The positive audit passes and every hostile mutation is rejected fail-closed.",
        })

        runbook = f"""# Stage33F core method-qualification pilot runbook

This immutable release is a design-only, empirical-empty package. It does not
authorize laboratory work, real identifiers, keys, materials, measurements,
microscopy, chemistry, DEM/LBM, or claims.

## Current permitted actions

1. Independently audit this exact release.
2. Hostile-test the auditor using synthetic mutations only.
3. Review the candidate Q0 requirements with the future laboratory, metrology,
   analytical and independent-review roles.

## Future Q0 handoff

Create a new immutable release. Populate actual inventory, working ranges,
certificates, SOPs, risk assessment, measurement and uncertainty models,
decision rules, cells/operators/days, Q1/Q2 counts, and evidence that the two
sentinel morphologies bracket intended use. Do not edit this release.

The recommended 27-column holdout is a justified candidate minimum, not an
executed or presently adopted design: three blocks, each with three clean,
three long/coarse PET and three short/fine PET columns; six independent PET
parent batches. Q1 development observations may define a rule but cannot also
test it. Q2 must use fresh material/runs and frozen rules.

## Stop boundary

Stop before real inventory or identities, certificate/SOP adoption, material
consumption, laboratory measurement, production keys, Stage33D confirmatory
work, empirical analysis, absolute permeability or degradation claims, DEM/LBM,
migration, clogging, deformation, transient or two-way coupling.

Release: `{RELEASE_ID}`
"""
        (tmp / "RUNBOOK.md").write_text(runbook, encoding="utf-8")

        sources_after = validate_sources()
        if before != sources_after:
            raise RuntimeError("E33F_SOURCE_HASH_MISMATCH: source changed during build")
        write_json(tmp / "lineage_manifest.json", {
            "schema": "pet.stage33f-lineage-manifest.v1", "stage": "Stage33F",
            "release_id": RELEASE_ID, "created_utc": created,
            "source_n": len(before), "sources": before,
            "source_snapshot_unchanged_during_build": True,
            "stage33e_parent_empirical_slots_empty": True,
            "stage33e_parent_audit_39_of_39": True,
            "stage33e_parent_hostile_verification_18_of_18": True,
            "stage33d_gates_semantically_exact": True,
        })

        artifact_map: dict[str, dict[str, Any]] = {}
        for path in sorted(tmp.iterdir(), key=lambda p: p.name.lower()):
            if not path.is_file() or path.is_symlink():
                raise RuntimeError(f"E33F_LINK_ALIAS: {path}")
            artifact_map[path.name] = {
                "path": str((output / path.name).resolve()),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }

        write_json(tmp / "completion.json", {
            "schema": "pet.stage33f-core-method-qualification-pilot-design-completion.v1",
            "stage": "Stage33F", "release_id": RELEASE_ID, "created_utc": created,
            "status": "complete_design_ready_for_independent_audit_execution_closed",
            "passed": True, "no_empirical_data": True, "no_real_identifiers": True,
            "no_real_key": True, "no_laboratory_execution": True,
            "no_numerical_execution": True, "q0_requirements_populated": False,
            "all_authority_closed": True, "candidate_evidence_products_empty": True,
            "artifact_n": len(artifact_map), "artifacts": artifact_map,
            "next_handoff": "independent Stage33F design audit and hostile verification only",
            "stop_boundary": resolved["stop_boundary"],
        })

        os.replace(tmp, output)
    except Exception:
        if tmp.exists():
            shutil.rmtree(tmp)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    build(args.output.resolve())
    print(json.dumps({"passed": True, "release": str(args.output.resolve())}, indent=2))


if __name__ == "__main__":
    main()
