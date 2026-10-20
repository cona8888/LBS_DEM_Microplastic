#!/usr/bin/env python3
"""Build the immutable, empirical-empty Stage33E readiness handoff.

This builder intentionally has no empirical-input or key-input argument.  It
qualifies only the empty intake architecture and refuses to overwrite output.
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
    / "stage33e_empirical_readiness_handoff_20260901"
    / "release_01"
)
RELEASE_ID = "STAGE33E-EMPIRICAL-READINESS-HANDOFF-01"

STAGE33D_RELEASE = (
    ROOT
    / "stage33_designs"
    / "stage33d_matched_pet_lbs_physical_validation_20260901"
    / "release_01"
)
STAGE33D_AUDIT = (
    ROOT
    / "stage33_evaluations"
    / "stage33d_matched_pet_lbs_physical_validation_20260901"
    / "design_audit_01"
)
STAGE33DO_VERIFICATION = (
    ROOT
    / "stage33_evaluations"
    / "stage33do_operational_workflow_synthetic_qualification_20260901"
    / "verification_01"
)
STAGE33DO_AUDIT = (
    ROOT
    / "stage33_evaluations"
    / "stage33do_operational_workflow_synthetic_qualification_20260901"
    / "release_audit_01"
)
STAGE33A_PROTOCOL = (
    ROOT
    / "outputs"
    / "019f7799-ad23-7f90-bf22-04cd842ccd22"
    / "stage33a_pet_fragmentation_characterization_20260829"
    / "preflight_design_03"
    / "resolved_protocol.json"
)
STAGE33CQ_RELEASE = (
    ROOT
    / "stage33_designs"
    / "stage33cq_acquisition_qualification_20260831"
    / "release_01"
)
STAGE33CQ_AUDIT = (
    ROOT
    / "stage33_evaluations"
    / "stage33cq_acquisition_qualification_20260831"
    / "release_audit_03"
    / "audit.json"
)
STAGE33CQ_SYNTHETIC = (
    ROOT
    / "stage33_evaluations"
    / "stage33cq_acquisition_and_masks_synthetic_verification_20260831"
    / "verification_06"
    / "verification.json"
)

CONTRACT = STAGING / "STAGE33E_EMPIRICAL_READINESS_HANDOFF_CONTRACT_V1.md"
BUILDER = Path(__file__).resolve()
AUDITOR = STAGING / "audit_stage33e_empirical_readiness_handoff_v1.py"
VERIFIER = STAGING / "verify_stage33e_empirical_readiness_handoff_v1.py"

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

EVIDENCE_SLOTS: tuple[dict[str, Any], ...] = (
    {
        "slot_id": "stage33a_empirical_readiness_closure",
        "track": "core",
        "required_for_gates": ["G20", "G30", "G40", "G50", "G60", "G70"],
        "expected_schema_policy": "scope-resolved Stage33A empirical closure with every blocker dispositioned and independently audited",
    },
    {
        "slot_id": "stage33cq_adjudicated_morphology_release",
        "track": "cross_domain",
        "required_for_gates": ["G40", "G50", "G60", "G70"],
        "expected_schema_policy": "same-batch empirical adjudicated morphology release passing the locked Stage33C-Q gates",
    },
    {
        "slot_id": "stage33cq_empirical_heldout_gate_report",
        "track": "cross_domain",
        "required_for_gates": ["G40", "G50", "G60", "G70"],
        "expected_schema_policy": "real held-out Stage33C-Q gate report; synthetic qualification is ineligible",
    },
    {
        "slot_id": "real_cross_release_commitment",
        "track": "restricted_operational",
        "required_for_gates": ["G30", "G40", "G50", "G60", "G70"],
        "expected_schema_policy": "fresh production premeasurement commitment binding real restricted, operator, morphology and analysis domains",
    },
    {
        "slot_id": "hydraulic_apparatus_calibration_release",
        "track": "core",
        "required_for_gates": ["G20", "G30", "G40", "G50", "G60", "G70"],
        "expected_schema_policy": "traceable calibration, capability and uncertainty release covering every apparatus role",
    },
    {
        "slot_id": "pet_mass_budget_and_split_qualification",
        "track": "core",
        "required_for_gates": ["G20", "G30", "G40", "G50", "G60", "G70"],
        "expected_schema_policy": "dry-basis process and split closures plus fibrous split-representativeness qualification",
    },
    {
        "slot_id": "effluent_pet_detection_method_release",
        "track": "core",
        "required_for_gates": ["G20", "G30", "G40", "G50", "G60", "G70"],
        "expected_schema_policy": "validated PET effluent method with blanks, recovery, LoB/LoD/LoQ and maximum-undetected-loss bound",
    },
    {
        "slot_id": "molecular_and_orthogonal_chemistry_release_for_degradation_claim",
        "track": "optional_degradation",
        "required_for_gates": ["G60"],
        "expected_schema_policy": "independent molar-mass plus orthogonal chain-scission/product evidence and accepted recovery/mass balance",
    },
    {
        "slot_id": "pet_specific_frozen_numerical_predictions_for_model_validation",
        "track": "optional_numerical",
        "required_for_gates": ["G70"],
        "expected_schema_policy": "PET-specific predictions and independent numerical audit frozen before empirical reveal",
    },
)

SOURCES = {
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
    "stage33cq_release_audit": STAGE33CQ_AUDIT,
    "stage33cq_synthetic_verification": STAGE33CQ_SYNTHETIC,
    "stage33e_contract": CONTRACT,
    "stage33e_builder": BUILDER,
    "stage33e_auditor": AUDITOR,
    "stage33e_verifier": VERIFIER,
}

AUTHORITY = {
    "real_identifier_or_key_ingest": False,
    "laboratory_execution": False,
    "empirical_image_processing": False,
    "hydraulic_measurement": False,
    "treatment_reveal": False,
    "empirical_analysis": False,
    "physical_validation_claim": False,
    "absolute_permeability_validation_claim": False,
    "pet_specific_model_validation_claim": False,
    "length_as_degradation_proxy_claim": False,
    "molecular_degradation_claim": False,
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
        raise RuntimeError(f"E33E_PARENT_LINEAGE_MISMATCH: {role} is not a regular non-symlink file: {path}")


def load_json(path: Path) -> Any:
    require_regular(path, path.name)
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, headers: Iterable[str], rows: Iterable[dict[str, Any]]) -> None:
    headers = list(headers)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in headers})


def assert_parent_state() -> dict[str, Any]:
    design = load_json(SOURCES["stage33d_resolved_design"])
    gates = load_json(SOURCES["stage33d_acceptance_gates"])
    design_completion = load_json(SOURCES["stage33d_completion"])
    design_audit = load_json(SOURCES["stage33d_design_audit"])
    design_audit_completion = load_json(SOURCES["stage33d_design_audit_completion"])
    verification = load_json(SOURCES["stage33do_synthetic_verification"])
    verification_completion = load_json(SOURCES["stage33do_synthetic_verification_completion"])
    release_audit = load_json(SOURCES["stage33do_release_audit"])
    release_audit_completion = load_json(SOURCES["stage33do_release_audit_completion"])
    stage33a = load_json(SOURCES["stage33a_resolved_protocol"])
    stage33cq = load_json(SOURCES["stage33cq_resolved_design"])
    stage33cq_audit = load_json(SOURCES["stage33cq_release_audit"])
    stage33cq_synthetic = load_json(SOURCES["stage33cq_synthetic_verification"])

    expected_slots = {item["slot_id"] for item in EVIDENCE_SLOTS}
    observed_inputs = design.get("future_required_inputs", {})
    if set(observed_inputs) != expected_slots:
        raise RuntimeError("E33E_PARENT_LINEAGE_MISMATCH: Stage33D future evidence roles changed")
    for role, record in observed_inputs.items():
        if record != {"path": "", "populated": False, "sha256": ""}:
            raise RuntimeError(f"E33E_NONEMPTY_EMPIRICAL_SLOT: parent Stage33D slot is not empty: {role}")

    if not (
        design.get("schema") == "pet.stage33d-matched-pet-lbs-physical-validation-design.v1"
        and design.get("status") == "frozen_predata_design_only_execution_closed"
        and design.get("passed") is True
        and all(value is False for value in design.get("authority", {}).values())
    ):
        raise RuntimeError("E33E_PARENT_LINEAGE_MISMATCH: Stage33D design state is not exact")
    if gates != EXPECTED_STAGE33D_GATES:
        raise RuntimeError("E33E_THRESHOLD_MUTATION: Stage33D acceptance gates changed")
    if not (
        design_completion.get("schema") == "pet.stage33d-matched-pet-lbs-physical-validation-design-completion.v1"
        and design_completion.get("passed") is True
        and design_audit.get("schema") == "pet.stage33d-matched-pet-lbs-physical-validation-design-audit.v1"
        and design_audit.get("passed") is True
        and design_audit.get("failed_checks") == []
        and design_audit_completion.get("passed") is True
    ):
        raise RuntimeError("E33E_PARENT_LINEAGE_MISMATCH: Stage33D audit/completion is not passing")

    if not (
        verification.get("schema") == "pet.stage33do-operational-workflow-synthetic-verification.v1"
        and verification.get("status") == "passed_synthetic_workflow_qualification"
        and verification.get("pass") is True
        and verification.get("test_only") is True
        and verification.get("no_empirical_data") is True
        and verification.get("no_real_key") is True
        and all(value is False for value in verification.get("authority", {}).values())
        and verification_completion.get("passed") is True
        and release_audit.get("schema") == "pet.stage33do-operational-release-qualification-audit.v1"
        and release_audit.get("status") == "passed_synthetic_release_audit"
        and release_audit.get("pass") is True
        and release_audit.get("passed_check_n") == 50
        and release_audit.get("failed_check_n") == 0
        and release_audit_completion.get("passed") is True
    ):
        raise RuntimeError("E33E_SYNTHETIC_AS_EMPIRICAL: Stage33D-O top-level qualification is not exact")

    blockers = stage33a.get("blockers", [])
    blocker_state = {row.get("blocker_id"): row.get("status") for row in blockers}
    if not (
        stage33a.get("schema") == "pet.stage33a-fragmentation-characterization-preflight.v2"
        and stage33a.get("status") == "prospective_preflight_not_execution_ready"
        and stage33a.get("execution_ready") is False
        and len(blocker_state) == 12
        and blocker_state.get("B01") == "CLOSED"
        and all(blocker_state.get(f"B{i:02d}") == "OPEN" for i in range(2, 13))
    ):
        raise RuntimeError("E33E_PARENT_LINEAGE_MISMATCH: Stage33A blocker snapshot changed")

    if not (
        stage33cq.get("stage") == "Stage33C-Q"
        and stage33cq.get("status") == "preflight_ready_no_empirical_data"
        and "Synthetic software" in stage33cq.get("claim_boundary", "")
        and stage33cq_audit.get("pass") is True
        and stage33cq_synthetic.get("overall_pass") is True
    ):
        raise RuntimeError("E33E_SYNTHETIC_AS_EMPIRICAL: Stage33C-Q remains preflight/synthetic only")

    return {
        "stage33d_design": design,
        "stage33d_gates": gates,
        "stage33a_blockers": blockers,
        "stage33cq_status": stage33cq.get("status"),
    }


def source_snapshot() -> dict[str, dict[str, str]]:
    snapshot: dict[str, dict[str, str]] = {}
    seen: set[str] = set()
    for role, path in SOURCES.items():
        require_regular(path, role)
        resolved = str(path.resolve())
        if resolved.lower() in seen:
            raise RuntimeError(f"E33E_PARENT_LINEAGE_MISMATCH: duplicate source path: {resolved}")
        if role.startswith("stage33do_") and "successful_release" in resolved.lower():
            raise RuntimeError("E33E_SYNTHETIC_AS_EMPIRICAL: Stage33D-O successful_release path is forbidden")
        seen.add(resolved.lower())
        snapshot[role] = {"path": resolved, "sha256": sha256(path)}
    return snapshot


def make_slot_registry(created: str) -> dict[str, Any]:
    slots = []
    for spec in EVIDENCE_SLOTS:
        row = dict(spec)
        row.update(
            {
                "expected_schema": "",
                "manifest_path": "",
                "manifest_sha256": "",
                "completion_path": "",
                "completion_sha256": "",
                "audit_path": "",
                "audit_sha256": "",
                "submission_id": "",
                "receipt_utc": "",
                "freeze_utc": "",
                "populated": False,
                "verified": False,
                "decision": "not_submitted",
            }
        )
        slots.append(row)
    return {
        "schema": "pet.stage33e-empirical-evidence-slot-registry.v1",
        "stage": "Stage33E",
        "release_id": RELEASE_ID,
        "created_utc": created,
        "status": "all_nine_inherited_slots_empty",
        "slot_n": 9,
        "slots": slots,
    }


def build_release(temp: Path, final: Path, created: str, parents: dict[str, Any], lineage: dict[str, Any]) -> None:
    contract_name = "STAGE33E_EMPIRICAL_READINESS_HANDOFF_CONTRACT_V1.md"
    shutil.copyfile(CONTRACT, temp / contract_name)

    resolved = {
        "schema": "pet.stage33e-empirical-readiness-handoff.v1",
        "stage": "Stage33E",
        "release_id": RELEASE_ID,
        "created_utc": created,
        "status": "frozen_design_only_all_empirical_inputs_unpopulated",
        "current_state": "S10_DESIGN_FROZEN_EMPIRICAL_EMPTY",
        "passed": True,
        "no_empirical_data": True,
        "no_real_identifiers": True,
        "no_real_key": True,
        "no_laboratory_execution": True,
        "no_numerical_execution": True,
        "research_question": "At fixed dry-PET loading and matched LBS state, do independent water-only temperature-conditioned PET batches change K20/K20_clean?",
        "experimental_unit": "independent PET process batch",
        "design_counts": {
            "reactor_blocks": 3,
            "conditions": 5,
            "independent_pet_batches": 15,
            "technical_pet_columns": 45,
            "matched_clean_controls": 9,
            "total_columns": 54,
        },
        "primary_estimand": "batch mean log(K20_PET / matched K20_clean)",
        "primary_morphology_covariate": "same-batch log(D50 maximum Feret) only after empirical Stage33C-Q qualification",
        "monotonicity_is_not_a_gate": True,
        "readiness": {
            "design_lineage_verified": True,
            "production_operational_toolchain_ready": False,
            "laboratory_hydraulic_execution_ready": False,
            "cross_domain_unblinding_ready": False,
            "pet_specific_model_validation_ready": False,
            "degradation_proxy_claim_ready": False,
        },
        "current_empirical_blockers": {
            "inherited_evidence_slot_n": 9,
            "populated_evidence_slot_n": 0,
            "verified_evidence_slot_n": 0,
            "production_operational_toolchain_audit": False,
            "stage33a_closed_blocker_n": 1,
            "stage33a_open_blocker_n": 11,
            "stage33cq_empirical_gate_present": False,
            "stage33cq_empirical_morphology_present": False,
        },
        "authority": dict(AUTHORITY),
        "claim_boundary": "Passing this release proves only that an empirical-empty intake architecture is internally consistent; it does not validate PET, permeability, degradation, morphology, or a model.",
        "stop_boundary": "stop before real evidence, identities or keys; specimen/reactor/column execution; empirical microscopy or chemistry; reveal; DEM/LBM; migration, clogging, deformation or coupling",
    }
    write_json(temp / "resolved_handoff.json", resolved)

    write_json(
        temp / "lineage_manifest.json",
        {
            "schema": "pet.stage33e-readiness-lineage-manifest.v1",
            "stage": "Stage33E",
            "release_id": RELEASE_ID,
            "created_utc": created,
            "status": "source_hashes_frozen",
            "source_n": len(lineage),
            "sources": lineage,
            "stage33do_binding_policy": "top-level synthetic verification/audit only; successful_release and test secrets/IDs are excluded",
        },
    )

    slot_registry = make_slot_registry(created)
    write_json(temp / "evidence_slot_registry.json", slot_registry)
    register_headers = [
        "slot_id",
        "track",
        "required_for_gates",
        "expected_schema_policy",
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
        "populated",
        "verified",
        "decision",
    ]
    register_rows = []
    for slot in slot_registry["slots"]:
        row = dict(slot)
        row["required_for_gates"] = ";".join(slot["required_for_gates"])
        row["populated"] = "false"
        row["verified"] = "false"
        register_rows.append(row)
    write_csv(temp / "evidence_register_template.csv", register_headers, register_rows)

    evidence_requirements = {
        "schema": "pet.stage33e-evidence-requirements.v1",
        "stage": "Stage33E",
        "release_id": RELEASE_ID,
        "created_utc": created,
        "stage33d_acceptance_gates": parents["stage33d_gates"],
        "threshold_policy": "Only parent-frozen hydraulic and Stage33C-Q morphology gates may be inherited. Apparatus, closure, split, packing, leak, stationarity and effluent capability numbers remain blank until justified and prospectively frozen.",
        "stage33a_scope_policy": {
            "every_blocker_requires_disposition": True,
            "mandatory_for_hydraulic": ["B02", "B03", "B05", "B07", "B10", "B11", "B12"],
            "conditional": {
                "B04": "required if historical 180 C source images are used as empirical evidence",
                "B06": "required if a mechanical challenge is part of the locked preparation/fragmentation question",
                "B08": "required before empirical morphology release and cross-domain reveal",
                "B09": "required for molecular-degradation or length-as-degradation-proxy claim, not a strictly hydraulic-response measurement",
            },
            "silent_omission_or_unjustified_not_applicable_is_blocking": True,
        },
        "fixed_solid_policy": {
            "pet_at_or_above_validated_LoD_fails": True,
            "detected_below_LoQ_still_fails": True,
            "below_LoD_means": "nondetect_not_zero",
            "visual_nondetect_is_sufficient": False,
        },
        "replication_policy": {
            "treatment_experimental_unit": "independent PET process batch",
            "batch_n": 15,
            "columns_fields_images_and_fibres_are_subsamples": True,
            "pooling_batches_allowed": False,
        },
    }
    write_json(temp / "evidence_requirements.json", evidence_requirements)

    gates = [
        {"gate_id": "G00", "name": "DESIGN_LINEAGE", "prerequisites": [], "current_pass": True},
        {"gate_id": "G10", "name": "PRODUCTION_TOOLCHAIN", "prerequisites": ["G00", "production_operational_toolchain_audit"], "current_pass": False},
        {"gate_id": "G20", "name": "CORE_PREFLIGHT", "prerequisites": ["G10", "stage33a_empirical_readiness_closure", "hydraulic_apparatus_calibration_release", "pet_mass_budget_and_split_qualification", "effluent_pet_detection_method_release", "real_role_separation"], "current_pass": False},
        {"gate_id": "G30", "name": "PREMEASUREMENT_CUSTODY", "prerequisites": ["G20", "per_batch_mass_budget_complete", "real_cross_release_commitment"], "current_pass": False},
        {"gate_id": "G40", "name": "PREREVEAL_MORPHOLOGY", "prerequisites": ["G30", "primary_hydraulic_endpoints_frozen", "stage33cq_empirical_heldout_gate_report", "stage33cq_adjudicated_morphology_release"], "current_pass": False},
        {"gate_id": "G50", "name": "CORE_EMPIRICAL_ANALYSIS_ELIGIBILITY", "prerequisites": ["G40", "all_15_batch_endpoints_complete", "hydraulic_evidence_independently_audited"], "current_pass": False},
        {"gate_id": "G60", "name": "DEGRADATION_CLAIM_ELIGIBILITY", "prerequisites": ["G50", "molecular_and_orthogonal_chemistry_release_for_degradation_claim", "recovery_mass_balance_accepted", "independent_confirmation_wave", "directional_and_minimum_effect_criteria_frozen"], "current_pass": False},
        {"gate_id": "G70", "name": "NUMERICAL_VALIDATION_ELIGIBILITY", "prerequisites": ["G50", "pet_specific_frozen_numerical_predictions_for_model_validation", "predictions_frozen_before_empirical_reveal", "pet_model_independently_audited"], "current_pass": False},
    ]
    write_json(
        temp / "readiness_gate_graph.json",
        {
            "schema": "pet.stage33e-readiness-gate-graph.v1",
            "stage": "Stage33E",
            "release_id": RELEASE_ID,
            "created_utc": created,
            "only_passing_gate": "G00",
            "gates": gates,
            "optional_evidence_cannot_unlock_core_execution": True,
        },
    )

    states = [
        {"state_id": "S00", "name": "DESIGN_DRAFT", "active": False},
        {"state_id": "S10", "name": "DESIGN_FROZEN_EMPIRICAL_EMPTY", "active": True},
        {"state_id": "S20", "name": "EVIDENCE_STAGED_UNVERIFIED", "active": False},
        {"state_id": "S30", "name": "PREFLIGHT_CORE_VERIFIED", "active": False},
        {"state_id": "S40", "name": "REAL_OPERATIONAL_COMMITMENT_VERIFIED", "active": False},
        {"state_id": "S50", "name": "PRIMARY_DATA_FROZEN_PREREVEAL", "active": False},
        {"state_id": "S60", "name": "MORPHOLOGY_QUALIFIED_REVEAL_HANDOFF_ELIGIBLE", "active": False},
        {"state_id": "S70", "name": "CORE_EMPIRICAL_EVALUATION_ELIGIBLE", "active": False},
    ]
    write_json(
        temp / "readiness_state_machine.json",
        {
            "schema": "pet.stage33e-readiness-state-machine.v1",
            "stage": "Stage33E",
            "release_id": RELEASE_ID,
            "created_utc": created,
            "current_state": "S10",
            "states": states,
            "transition_policy": {
                "in_place_edits_allowed": False,
                "each_transition_requires_new_immutable_release": True,
                "required_bindings": ["previous_completion_sha256", "submission_envelope_sha256", "evaluator_sha256", "independent_audit_sha256"],
                "skipped_or_replayed_transitions_rejected": True,
                "eligibility_never_grants_automatic_execution_authority": True,
            },
        },
    )

    write_json(
        temp / "authority_matrix.json",
        {
            "schema": "pet.stage33e-authority-matrix.v1",
            "stage": "Stage33E",
            "release_id": RELEASE_ID,
            "created_utc": created,
            "status": "all_authority_closed",
            "authority": dict(AUTHORITY),
        },
    )

    roles_template = {
        "schema": "pet.stage33e-roles-key-custody-template.v1",
        "stage": "Stage33E",
        "release_id": "",
        "status": "template_only_no_real_identifiers",
        "operator_id": "",
        "analyst_id": "",
        "custodian_id": "",
        "independent_auditor_id": "",
        "institutional_restricted_store_id": "",
        "real_secret_or_key_path": "",
        "real_secret_or_key_sha256": "",
        "production_builder_path": "",
        "production_builder_sha256": "",
        "production_auditor_path": "",
        "production_auditor_sha256": "",
        "all_roles_distinct_required": True,
        "operator_view": "raw hydraulics only",
        "analyst_view": "opaque specimens, matched sets and specimen role; no treatment/source identity",
        "custodian_view": "restricted batch, dose, preparation and reveal records",
        "fresh_secret_namespace_required": True,
        "stage33do_test_secret_or_identifiers_reusable": False,
    }
    write_json(temp / "roles_and_key_custody_template.json", roles_template)

    write_json(
        temp / "production_operational_toolchain_audit_template.json",
        {
            "schema": "pet.stage33e-production-operational-toolchain-audit-slot.v1",
            "blocker_id": "production_operational_toolchain_audit",
            "path": "",
            "sha256": "",
            "audit_path": "",
            "audit_sha256": "",
            "schema_expected": "",
            "status": "not_submitted",
            "populated": False,
            "verified": False,
            "production_mode_supported": False,
            "fresh_secret_namespace_verified": False,
            "restricted_store_verified": False,
            "hostile_challenges_passed": False,
        },
    )

    write_json(
        temp / "evidence_submission_envelope_template.json",
        {
            "schema": "pet.stage33e-evidence-submission-envelope.v1",
            "submission_id": "",
            "slot_id": "",
            "manifest_path": "",
            "manifest_sha256": "",
            "completion_path": "",
            "completion_sha256": "",
            "audit_path": "",
            "audit_sha256": "",
            "evidence_schema": "",
            "evidence_release_id": "",
            "evidence_status": "",
            "frozen_utc": "",
            "submitted_utc": "",
            "submitter_role_id": "",
            "synthetic_or_test_evidence": "",
            "declaration": "",
            "current_status": "template_only_unpopulated",
        },
    )

    apparatus_roles = [
        "dry_sand_balance",
        "pet_aliquot_filter_balance",
        "effluent_collection_balance_or_volumetric_device",
        "water_temperature_measurement",
        "timer",
        "head_sensor_or_gauge",
        "specimen_diameter_gauge",
        "specimen_length_gauge",
        "saturation_and_leak_assessment",
        "effluent_collection_train",
    ]
    apparatus_headers = [
        "instrument_role", "instrument_id", "model", "serial_number", "measurement_quantity",
        "use_range_low", "use_range_high", "use_range_units", "resolution", "reference_standard_id",
        "reference_certificate_path", "reference_certificate_sha256", "traceability_chain", "calibration_points",
        "observed_values", "reference_values", "corrections", "as_found_result", "as_left_result", "repeatability",
        "drift", "calibration_uncertainty", "coverage_factor", "valid_from_utc", "valid_to_utc",
        "operating_environment", "sop_path", "sop_sha256", "prospective_pass_rule", "guard_band_decision",
        "independent_reviewer_id", "current_status",
    ]
    write_csv(
        temp / "apparatus_calibration_requirements.csv",
        apparatus_headers,
        [{"instrument_role": role, "current_status": "UNPOPULATED"} for role in apparatus_roles],
    )

    uncertainty_headers = [
        "derived_quantity", "equation_or_budget_path", "equation_or_budget_sha256", "input_binding_paths",
        "input_binding_sha256s", "combined_standard_uncertainty", "coverage_factor", "expanded_uncertainty_U95",
        "capability_anchor", "prospective_decision_rule", "rationale", "independent_reviewer_id", "current_status",
    ]
    uncertainty_rows = [
        {"derived_quantity": "total_solid_void_ratio", "capability_anchor": "frozen e=0.744 +/- 0.010 window", "current_status": "UNPOPULATED"},
        {"derived_quantity": "achieved_pet_dose_wt_percent", "capability_anchor": "frozen Stage33D dose target/tolerance", "current_status": "UNPOPULATED"},
        {"derived_quantity": "K20_m_s", "capability_anchor": "minimum relevant log-ratio effect; not a generic instrument tolerance", "current_status": "UNPOPULATED"},
        {"derived_quantity": "matched_log_ratio", "capability_anchor": "minimum relevant log-ratio effect 0.05129329438755058", "current_status": "UNPOPULATED"},
    ]
    write_csv(temp / "uncertainty_budget_requirements.csv", uncertainty_headers, uncertainty_rows)

    packing_headers = [
        "qualification_id", "nonconfirmatory_material_id", "cell_id", "operator_id", "day_id", "replicate_id",
        "dry_sand_mass_g", "dry_pet_mass_g", "sand_density_g_cm3", "pet_density_g_cm3", "cell_volume_cm3",
        "calculated_total_solid_void_ratio", "void_ratio_U95", "initial_postflow_dimension_or_e_drift",
        "protocol_path", "protocol_sha256", "vibration_or_pressure_settings_frozen", "visible_segregation_or_orientation",
        "qualification_mean_e", "qualification_sd_e", "qualification_range_e", "out_of_window_fraction",
        "prospective_capability_rule", "independent_reviewer_id", "current_status",
    ]
    write_csv(temp / "packing_capability_capture_template.csv", packing_headers, [])

    mass_headers = [
        "source_batch_slot", "reactor_block", "condition_code", "operational_batch_id", "charge_dry_pet_g",
        "blank_correction_g", "moisture_correction_fraction", "recovered_dry_pet_g", "process_transfer_loss_g",
        "filter_loss_g", "process_other_loss_g", "process_closure_fraction", "process_closure_threshold",
        "process_closure_U95", "process_closure_pass", "morphology_aliquot_g", "chemistry_aliquot_g",
        "hydraulic_aliquot_g", "archive_aliquot_g", "residual_g", "split_loss_g", "split_closure_fraction",
        "split_closure_threshold", "split_closure_U95", "split_closure_pass", "split_protocol",
        "split_qualification_path", "split_qualification_sha256", "unpooled_required", "unpooled_observed",
        "independent_reviewer_id", "current_status",
    ]
    mass_rows = []
    for block in range(1, 4):
        for condition in ("T20", "T120", "T140", "T160", "T180"):
            mass_rows.append(
                {
                    "source_batch_slot": f"B{block}-{condition}",
                    "reactor_block": block,
                    "condition_code": condition,
                    "unpooled_required": "true",
                    "current_status": "UNPOPULATED",
                }
            )
    write_csv(temp / "mass_split_requirements.csv", mass_headers, mass_rows)

    split_headers = [
        "qualification_id", "source_material_id", "split_method", "replicate_id", "daughter_id", "dry_mass_g",
        "feret_d50", "width_d50", "class_distribution_record_path", "class_distribution_record_sha256",
        "mass_bias", "feret_bias", "width_bias", "class_bias", "precision", "confidence_interval",
        "prospective_pass_rule", "hand_picked", "independent_reviewer_id", "current_status",
    ]
    write_csv(temp / "split_representativeness_capture_template.csv", split_headers, [])

    effluent_requirements = [
        ("pet_identity", "Method must distinguish PET from matrix/background material."),
        ("capture_strategy", "Full-volume capture or validated representative subsampling."),
        ("filter_train", "Filter materials, cutoffs and complete transfer chain must be frozen."),
        ("matrix_blanks", "Matrix blanks must establish background and false-positive behavior."),
        ("procedural_blanks", "Procedural blanks must cover the full collection and analysis chain."),
        ("positive_controls", "Representative PET positive controls must cover size, shape and mass range."),
        ("false_positive_negative", "False-positive and false-negative handling must be prospectively defined."),
        ("filter_transfer_recovery", "Recovery, precision, bias and confidence bounds must be quantified."),
        ("LoB_LoD_LoQ", "LoB, LoD and LoQ or a justified method-equivalent must be validated."),
        ("sample_volume", "Sample volume and any subsampling factor must be traceable."),
        ("mass_equivalent_LoD", "Detection capability must be converted to a mass-equivalent bound."),
        ("maximum_undetected_fraction", "Maximum PET fraction that could remain undetected must be calculated."),
        ("fixed_solid_decision", "Any PET at or above LoD fails fixed-solid interpretation; below LoD is nondetect, not zero."),
    ]
    effluent_headers = [
        "requirement_id", "requirement", "method_value", "units", "method_record_path", "method_record_sha256",
        "prospective_acceptance_rule", "rationale", "independent_reviewer_id", "current_status",
    ]
    write_csv(
        temp / "effluent_method_requirements.csv",
        effluent_headers,
        [{"requirement_id": rid, "requirement": text, "current_status": "UNPOPULATED"} for rid, text in effluent_requirements],
    )

    failure_codes = {
        "schema": "pet.stage33e-failure-codes.v1",
        "codes": {
            "E33E_PARENT_LINEAGE_MISMATCH": "Parent source/hash/schema/status or completion mismatch.",
            "E33E_THRESHOLD_MUTATION": "A frozen Stage33D gate or nonmonotonicity policy changed.",
            "E33E_NONEMPTY_EMPIRICAL_SLOT": "The design-only release contains a populated empirical slot.",
            "E33E_SLOT_SET_MISMATCH": "Inherited slot set is missing, duplicated or extended.",
            "E33E_DUPLICATE_EVIDENCE_PATH": "Two future evidence roles resolve to the same file.",
            "E33E_EVIDENCE_BINDING_MISMATCH": "Future path/hash/schema/status/audit tuple is incomplete or inconsistent.",
            "E33E_SYNTHETIC_AS_EMPIRICAL": "Synthetic/test evidence was presented as production or empirical evidence.",
            "E33E_STAGE33A_SCOPE_UNRESOLVED": "A scope-relevant Stage33A blocker lacks a justified disposition.",
            "E33E_PRODUCTION_TOOLCHAIN_MISSING": "A fresh production-capable builder/auditor/secret-store chain is absent.",
            "E33E_CALIBRATION_INCOMPLETE_OR_EXPIRED": "Calibration/capability/uncertainty evidence is incomplete or expired.",
            "E33E_CAPABILITY_RULE_MISSING": "A method-specific prospective capability rule is absent.",
            "E33E_MASS_OR_SPLIT_GATE_FAILED": "Process/split closure, unpooled status or fibrous representativeness failed.",
            "E33E_PACKING_CAPABILITY_FAILED": "Fixed packing capability or uncertainty evidence failed.",
            "E33E_EFFLUENT_METHOD_FAILED": "Effluent identity, blanks, recovery, detection or undetected-loss gate failed.",
            "E33E_ROLE_OVERLAP_OR_SECRET_LEAK": "Operational roles overlap or restricted key material leaked.",
            "E33E_PREMATURE_REVEAL": "Reveal occurred before primary hydraulic and morphology freezes.",
            "E33E_PREDICTIONS_POST_REVEAL": "Numerical predictions were not frozen before empirical reveal.",
            "E33E_DEGRADATION_FROM_MORPHOLOGY_ONLY": "A degradation claim was attempted without molecular, orthogonal and confirmation evidence.",
            "E33E_AUTHORITY_LEAK": "Design-only release enabled an execution or claim authority.",
            "E33E_UNEXPECTED_FILE": "Release contains an unmanifested or unsafe file.",
            "E33E_INPUT_MUTATION": "A source changed during build or audit.",
            "E33E_OVERWRITE_REFUSED": "Immutable output already exists.",
        },
    }
    write_json(temp / "failure_codes.json", failure_codes)

    challenges = [
        "mutated_stage33d_lineage", "mutated_stage33do_lineage", "failed_or_missing_parent_audit",
        "synthetic_release_submitted_as_empirical", "prepopulated_or_inconsistent_slot", "missing_duplicate_or_unknown_slot",
        "state_advance", "authority_enabled", "optional_chemistry_or_prediction_unlocks_core_gate",
        "role_overlap_or_secret_leakage", "extra_unmanifested_artifact", "altered_threshold_or_monotonicity",
        "production_toolchain_falsely_enabled", "successful_release_path_in_lineage", "source_mutation",
        "output_overwrite", "prediction_timestamp_after_reveal", "chemistry_only_degradation_claim",
    ]
    write_json(
        temp / "negative_challenge_plan.json",
        {
            "schema": "pet.stage33e-negative-challenge-plan.v1",
            "stage": "Stage33E",
            "release_id": RELEASE_ID,
            "challenge_n": len(challenges),
            "expected_result": "every challenge rejected fail-closed",
            "challenges": challenges,
        },
    )

    decision = {
        "schema": "pet.stage33e-readiness-decision.v1",
        "stage": "Stage33E",
        "release_id": RELEASE_ID,
        "created_utc": created,
        "passed": True,
        "decision": "DESIGN_ONLY_ALL_EMPIRICAL_INPUTS_UNPOPULATED",
        "readiness": {
            "laboratory_hydraulic_execution_ready": False,
            "cross_domain_unblinding_ready": False,
            "pet_specific_model_validation_ready": False,
            "degradation_proxy_claim_ready": False,
        },
        "only_passing_gate": "G00_DESIGN_LINEAGE",
        "active_state": "S10_DESIGN_FROZEN_EMPIRICAL_EMPTY",
        "blocking_reasons": [
            "all nine inherited Stage33D evidence slots are empty",
            "production_operational_toolchain_audit is empty and false",
            "Stage33A has eleven open preflight blockers",
            "Stage33C-Q has only preflight/synthetic qualification, not empirical same-batch evidence",
            "no real roles, secret, key, calibration, mass/split, effluent, hydraulic, morphology, chemistry or prediction evidence is present",
        ],
        "authority": dict(AUTHORITY),
    }
    write_json(temp / "readiness_decision.json", decision)

    runbook = f"""# Stage33E empirical-readiness handoff runbook

**Current state:** `S10_DESIGN_FROZEN_EMPIRICAL_EMPTY`  
**Release:** `{RELEASE_ID}`

This release is an audited blank intake design. Do not edit it in place and do not place real identities, keys or measurements here.

1. Close the scope-relevant Stage33A blockers in a separately audited empirical-readiness release. Every blocker must have an applicability disposition; chemistry is conditional for a strictly hydraulic response but mandatory for a degradation-proxy claim.
2. Build and hostile-test a new production operational toolchain. It must use a fresh secret namespace and institution-approved restricted store. The Stage33D-O synthetic secret, IDs, fixtures and `successful_release` are forbidden.
3. Qualify the apparatus, uncertainty budgets, packing protocol, dry-basis process/split closures, fibrous split representativeness and effluent PET method using the blank interfaces in this release. Freeze method-specific capability rules before any confirmatory specimen is measured.
4. Create a new immutable Stage33E transition release binding completed evidence envelopes and their independent audits. Never populate this release in place.
5. Before hydraulic execution, verify core preflight and a real premeasurement cross-release commitment. Operators, analysts, custodians and auditors must be distinct.
6. Freeze hydraulic exclusions and all 15 batch primary endpoints before a separate reveal declaration. Cross-domain reveal additionally requires an empirical held-out Stage33C-Q gate and adjudicated same-batch morphology release.
7. Model validation requires PET-specific predictions frozen before empirical reveal. A length-as-degradation-proxy claim separately requires molecular, orthogonal chemical, recovery/mass-balance and independent confirmation evidence.

Passing Stage33E design audit means only that these dependencies are explicit and hash-bound. It does not authorize laboratory work, empirical analysis, DEM/LBM, or any physical/degradation claim.
"""
    (temp / "RUNBOOK.md").write_text(runbook, encoding="utf-8")

    artifacts: dict[str, dict[str, Any]] = {}
    for path in sorted(temp.iterdir(), key=lambda p: p.name.lower()):
        if path.name == "completion.json":
            continue
        require_regular(path, f"artifact:{path.name}")
        artifacts[path.name] = {
            "path": str(final / path.name),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
    write_json(
        temp / "completion.json",
        {
            "schema": "pet.stage33e-empirical-readiness-handoff-completion.v1",
            "stage": "Stage33E",
            "release_id": RELEASE_ID,
            "created_utc": created,
            "status": "complete_design_ready_for_independent_audit_execution_closed",
            "passed": True,
            "no_empirical_data": True,
            "all_empirical_slots_empty": True,
            "production_toolchain_ready": False,
            "all_authority_closed": True,
            "artifact_n": len(artifacts),
            "artifacts": artifacts,
            "next_handoff": "independent Stage33E design audit and hostile verification only",
            "stop_boundary": resolved["stop_boundary"],
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError(f"E33E_OVERWRITE_REFUSED: output exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    before = source_snapshot()
    parents = assert_parent_state()
    created = now_utc()
    temp = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=str(output.parent)))
    try:
        build_release(temp, output, created, parents, before)
        after = source_snapshot()
        if before != after:
            raise RuntimeError("E33E_INPUT_MUTATION: source hashes changed during build")
        os.replace(temp, output)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise

    print(json.dumps({"passed": True, "output": str(output), "release_id": RELEASE_ID}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL-CLOSED: {type(exc).__name__}: {exc}", file=os.sys.stderr)
        raise SystemExit(2)
