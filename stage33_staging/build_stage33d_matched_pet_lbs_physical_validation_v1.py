from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage33d_matched_pet_lbs_physical_validation_20260901"
OUT = ROOT / "stage33_designs" / STUDY / "release_01"
CONTRACT = ROOT / "stage33_staging" / "STAGE33D_MATCHED_PET_LBS_PHYSICAL_VALIDATION_CONTRACT_V1.md"
BUILDER = Path(__file__).resolve()
AUDITOR = ROOT / "stage33_staging" / "audit_stage33d_matched_pet_lbs_physical_validation_v1.py"

STAGE33A = (
    ROOT
    / "outputs"
    / "019f7799-ad23-7f90-bf22-04cd842ccd22"
    / "stage33a_pet_fragmentation_characterization_20260829"
    / "preflight_design_03"
)
SOURCES = {
    "stage33a_workbook": STAGE33A / "Stage33A_PET_Characterization_Preflight.xlsx",
    "stage33a_resolved_protocol": STAGE33A / "resolved_protocol.json",
    "stage33a_design_records": STAGE33A / "design_records.json",
    "stage33a_design_audit": ROOT
    / "stage33_evaluations/stage33a_pet_fragmentation_characterization_20260829/preflight_audit_04/design_audit.json",
    "stage33b_bridge_design": ROOT
    / "stage33_designs/stage33b_pet_morphology_to_pore_scale_bridge_20260831/design_01/resolved_design.json",
    "stage33b_bridge_audit": ROOT
    / "stage33_evaluations/stage33b_pet_morphology_to_pore_scale_bridge_20260831/design_audit_01/design_audit.json",
    "stage33cm_design": ROOT
    / "stage33_designs/stage33c_blinded_morphology_pipeline_20260831/release_01/resolved_design.json",
    "stage33cm_synthetic_verification": ROOT
    / "stage33_evaluations/stage33c_blinded_morphology_pipeline_20260831/synthetic_verification_01/verification.json",
    "stage33cm_release_audit": ROOT
    / "stage33_evaluations/stage33c_blinded_morphology_pipeline_20260831/release_audit_01/release_audit.json",
    "stage33cq_design": ROOT
    / "stage33_designs/stage33cq_acquisition_qualification_20260831/release_01/resolved_design.json",
    "stage33cq_synthetic_verification": ROOT
    / "stage33_evaluations/stage33cq_acquisition_and_masks_synthetic_verification_20260831/verification_06/verification.json",
    "stage33cq_visual_inspection": ROOT
    / "stage33_evaluations/stage33cq_acquisition_qualification_20260831/visual_inspection_01/visual_inspection.json",
    "stage33cq_release_audit": ROOT
    / "stage33_evaluations/stage33cq_acquisition_qualification_20260831/release_audit_03/audit.json",
    "stage32c_measurement_release_manifest": ROOT
    / "stage32_releases/stage32c_blinded_validation_release_20260829/release_01/release_manifest.json",
    "stage32c_measurement_release_audit": ROOT
    / "stage32_evaluations/stage32c_blinded_validation_release_20260829/release_audit_01/release_audit.json",
    "stage32c_measurement_evaluator": ROOT / "stage32_staging/evaluate_stage32c_matched_validation_v1.py",
    "stage33d_contract": CONTRACT,
    "stage33d_builder": BUILDER,
    "stage33d_auditor": AUDITOR,
}

CONDITIONS = ("T20", "T120", "T140", "T160", "T180")
CONDITION_ORDER = {condition: i for i, condition in enumerate(CONDITIONS)}
TARGET_PET_WT_PERCENT = 0.09841784362759924
RANDOMIZATION_SEEDS = {1: 330401, 2: 330402, 3: 330403}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def passed_record(value: dict) -> bool:
    return value.get("passed") is True or value.get("pass") is True or value.get("overall_pass") is True


def build_specimen_plan(records: dict) -> list[dict[str, object]]:
    batches = [
        row
        for row in records.get("batches", [])
        if row.get("has_pet") is True and row.get("condition_id") in CONDITIONS
    ]
    if len(batches) != 15:
        raise RuntimeError(f"expected exactly 15 Stage33A PET process batches, found {len(batches)}")

    lookup: dict[tuple[int, str], dict] = {}
    for row in batches:
        key = (int(row["randomization_block"]), str(row["condition_id"]))
        if key in lookup:
            raise RuntimeError(f"duplicate PET process batch for {key}")
        lookup[key] = row
    expected = {(block, condition) for block in (1, 2, 3) for condition in CONDITIONS}
    if set(lookup) != expected:
        raise RuntimeError("Stage33A PET process batches do not form the required 3 x 5 complete blocks")

    plan: list[dict[str, object]] = []
    run_order = 0
    for block in (1, 2, 3):
        rng = random.Random(RANDOMIZATION_SEEDS[block])
        replicate_order = [1, 2, 3]
        rng.shuffle(replicate_order)
        for set_sequence, replicate in enumerate(replicate_order, 1):
            members = ["CLEAN", *CONDITIONS]
            rng.shuffle(members)
            for within_set_order, member in enumerate(members, 1):
                run_order += 1
                is_clean = member == "CLEAN"
                source_batch = "" if is_clean else str(lookup[(block, member)]["batch_id"])
                slot = f"D33D-B{block}-R{replicate}-{'C0' if is_clean else member}"
                plan.append(
                    {
                        "run_order": run_order,
                        "reactor_block": block,
                        "matched_set_sequence": set_sequence,
                        "technical_replicate": replicate,
                        "within_set_order": within_set_order,
                        "design_specimen_slot": slot,
                        "specimen_role": "clean_lbs_control" if is_clean else "pet_mixture",
                        "condition_id": "CLEAN" if is_clean else member,
                        "source_batch_slot": source_batch,
                        "target_pet_dry_mass_percent": 0.0 if is_clean else TARGET_PET_WT_PERCENT,
                        "target_void_ratio": 0.744,
                        "planned_linearity_sentinel": bool(replicate == 1 and member in ("CLEAN", "T180")),
                        "operational_id_status": "not_assigned_predata_design_only",
                    }
                )
    if len(plan) != 54:
        raise RuntimeError("internal error: specimen plan is not 54 rows")
    return plan


def main() -> int:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    missing = [str(path) for path in SOURCES.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"required source files missing: {missing}")

    stage33a_audit = load_json(SOURCES["stage33a_design_audit"])
    stage33b_audit = load_json(SOURCES["stage33b_bridge_audit"])
    stage33cm_audit = load_json(SOURCES["stage33cm_release_audit"])
    stage33cq_audit = load_json(SOURCES["stage33cq_release_audit"])
    stage32c_audit = load_json(SOURCES["stage32c_measurement_release_audit"])
    if not all(passed_record(item) for item in (stage33a_audit, stage33b_audit, stage33cm_audit, stage33cq_audit, stage32c_audit)):
        raise RuntimeError("one or more prerequisite design/software audits is not passed")
    if stage33a_audit.get("status") != "passed_preflight_not_execution_ready":
        raise RuntimeError("Stage33A must remain explicitly preflight-only")
    if stage33cq_audit.get("claim_boundary", "").find("synthetic") < 0:
        raise RuntimeError("Stage33C-Q audit must remain explicitly synthetic-only")

    records = load_json(SOURCES["stage33a_design_records"])
    specimen_plan = build_specimen_plan(records)
    OUT.mkdir(parents=True, exist_ok=False)

    plan_fields = [
        "run_order",
        "reactor_block",
        "matched_set_sequence",
        "technical_replicate",
        "within_set_order",
        "design_specimen_slot",
        "specimen_role",
        "condition_id",
        "source_batch_slot",
        "target_pet_dry_mass_percent",
        "target_void_ratio",
        "planned_linearity_sentinel",
        "operational_id_status",
    ]
    write_csv(OUT / "custodian_design_matrix.csv", plan_fields, specimen_plan)

    operator_fields = [
        "operational_release_id",
        "opaque_specimen_id",
        "opaque_matched_set_id",
        "operator_run_order",
        "apparatus_id",
        "measurement_utc",
        "dry_sand_mass_g",
        "specimen_diameter_mm",
        "specimen_length_mm",
        "final_total_solid_void_ratio",
        "water_temperature_c",
        "head_difference_m",
        "collection_time_s",
        "collected_water_mass_g",
        "saturation_qc",
        "leak_qc",
        "steady_flow_qc",
        "effluent_filter_id",
        "effluent_pet_detected",
        "valid_pre_measurement",
        "pre_measurement_rejection_reason",
        "operator_notes",
    ]
    write_csv(OUT / "operator_capture_template.csv", operator_fields, [])

    preparation_fields = [
        "operational_release_id",
        "opaque_specimen_id",
        "opaque_matched_set_id",
        "balance_calibration_id",
        "sand_lot_id",
        "dry_sand_mass_g",
        "dry_pet_mass_g",
        "achieved_pet_dry_mass_percent",
        "pet_density_g_cm3",
        "achieved_pet_solid_volume_fraction",
        "mixing_protocol_id",
        "packing_protocol_id",
        "initial_total_solid_void_ratio",
        "pre_measurement_eligible",
        "pre_measurement_rejection_reason",
        "preparation_utc",
        "custodian_id",
    ]
    write_csv(OUT / "preparation_capture_template.csv", preparation_fields, [])

    linearity_fields = [
        "operational_release_id",
        "opaque_specimen_id",
        "gradient_sequence",
        "water_temperature_c",
        "specimen_diameter_mm",
        "specimen_length_mm",
        "head_difference_m",
        "collection_time_s",
        "collected_water_mass_g",
        "calculated_gradient",
        "calculated_discharge_m3_s",
        "calculated_K20_m_s",
        "particle_reynolds_number",
        "valid",
        "reason",
    ]
    write_csv(OUT / "darcy_linearity_capture_template.csv", linearity_fields, [])

    link_fields = [
        "operational_release_id",
        "analyst_batch_code",
        "hydraulic_specimen_id_list_sha256",
        "morphology_release_path",
        "morphology_release_sha256",
        "morphology_batch_summary_path",
        "morphology_batch_summary_sha256",
        "chemistry_release_path",
        "chemistry_release_sha256",
        "cross_release_commitment_path",
        "cross_release_commitment_sha256",
        "link_state",
    ]
    write_csv(OUT / "blinded_batch_link_template.csv", link_fields, [])

    mass_fields = [
        "restricted_release_id",
        "source_batch_id",
        "initial_dry_pet_mass_g",
        "recovered_dry_solid_mass_g",
        "morphology_aliquot_mass_g",
        "chemistry_aliquot_mass_g",
        "hydraulic_aliquot_mass_g",
        "archive_aliquot_mass_g",
        "filter_residue_mass_g",
        "transfer_loss_mass_g",
        "unaccounted_mass_g",
        "mass_closure_fraction",
        "split_protocol_id",
        "split_qualification_record_path",
        "split_qualification_record_sha256",
        "eligible_before_hydraulics",
        "reason",
    ]
    write_csv(OUT / "restricted_mass_balance_template.csv", mass_fields, [])

    calibration_fields = [
        "calibration_id",
        "instrument_role",
        "instrument_id",
        "reference_standard_id",
        "calibration_utc",
        "valid_from_utc",
        "valid_to_utc",
        "observed_value",
        "reference_value",
        "units",
        "relative_error",
        "pass",
        "record_path",
        "record_sha256",
    ]
    write_csv(OUT / "instrument_calibration_template.csv", calibration_fields, [])

    roles = {
        "schema": "pet.stage33d-role-and-key-custody-template.v1",
        "status": "template_only_no_real_identifiers",
        "roles": {
            "treatment_and_batch_custodian": "",
            "specimen_release_officer": "",
            "hydraulic_preparation_operator": "",
            "hydraulic_measurement_operator": "",
            "morphology_analyst": "",
            "hydraulic_analyst": "",
            "reveal_officer": "",
            "independent_auditor": "",
        },
        "required_separation": [
            ["treatment_and_batch_custodian", "morphology_analyst"],
            ["treatment_and_batch_custodian", "hydraulic_analyst"],
            ["reveal_officer", "morphology_analyst"],
            ["reveal_officer", "hydraulic_analyst"],
            ["independent_auditor", "treatment_and_batch_custodian"],
        ],
        "operational_rules": [
            "Generate real opaque batch, matched-set and specimen identifiers outside the analyst workspace.",
            "Store the treatment/source crosswalk in access-separated restricted custody.",
            "Hash-freeze morphology and hydraulic releases before cross-domain linkage.",
            "Reveal treatment only after the primary batch table, exclusions and analysis code are frozen.",
            "Do not reuse Stage33A PX/AX placeholders or deterministic synthetic identifiers.",
        ],
    }
    write_json(OUT / "roles_and_key_custody_template.json", roles)

    acceptance_gates = {
        "schema": "pet.stage33d-matched-pet-lbs-acceptance-gates.v1",
        "target_pet_dry_mass_percent": TARGET_PET_WT_PERCENT,
        "pet_dose_absolute_tolerance_wt_percent": 0.0005,
        "pet_dose_relative_tolerance": 0.05,
        "target_total_solid_void_ratio": 0.744,
        "void_ratio_absolute_tolerance": 0.010,
        "water_temperature_c": 20.0,
        "water_temperature_tolerance_c": 0.5,
        "maximum_clean_cv_within_block": 0.05,
        "minimum_valid_matched_sets_per_batch": 2,
        "minimum_valid_clean_controls_per_block": 2,
        "required_batch_endpoints": 15,
        "darcy_linearity": {
            "minimum_distinct_positive_gradients": 3,
            "minimum_discharge_gradient_r_squared": 0.99,
            "maximum_K20_cv": 0.05,
            "maximum_particle_reynolds_number": 1.0,
        },
        "calculation_crosscheck_maximum_relative_error": 0.005,
        "minimum_relevant_log_ratio_effect": abs(math.log(0.95)),
        "fixed_solid_gate": "effluent PET must not exceed the prospectively validated detection limit and flow must remain stationary",
        "completeness_gate": "all five condition-by-three-block batch endpoints are required for confirmatory complete-block inference",
        "monotonicity_is_not_a_gate": True,
        "degradation_proxy_additional_gates": [
            "independent molecular molar-mass endpoint",
            "orthogonal chain-scission or product endpoint",
            "recovery and mass-balance acceptance",
            "new independent confirmation wave with frozen directional and minimum-effect criteria",
        ],
    }
    write_json(OUT / "acceptance_gates.json", acceptance_gates)

    failure_codes = {
        "schema": "pet.stage33d-failure-codes.v1",
        "codes": {
            "D33D_LINEAGE_MISMATCH": "A required path or SHA-256 binding is missing or mismatched.",
            "D33D_REAL_KEY_IN_DESIGN_RELEASE": "A real treatment/source key or operational identifier entered the pre-data design release.",
            "D33D_STAGE33A_BLOCKER_OPEN": "Stage33A empirical readiness blockers remain open.",
            "D33D_EMPIRICAL_MORPHOLOGY_NOT_QUALIFIED": "The real Stage33C-Q held-out empirical morphology release is absent or failed.",
            "D33D_BATCH_MISSING_OR_POOLED": "A required independent PET process batch is absent, duplicated or pooled.",
            "D33D_SPLIT_OR_MASS_BUDGET_FAILED": "Aliquot split qualification or prospective PET mass budget failed.",
            "D33D_DOSE_OUTSIDE_TOLERANCE": "Achieved dry PET/dry sand mass fraction is outside the frozen tolerance.",
            "D33D_STATE_OUTSIDE_TOLERANCE": "Void ratio, temperature, saturation, dimensions or another pre-measurement state gate failed.",
            "D33D_DARCY_LINEARITY_FAILED": "The frozen gradient-linearity, K20-CV or Reynolds criterion failed.",
            "D33D_CLEAN_REPEATABILITY_FAILED": "A reactor block lacks sufficient valid clean controls or exceeds the clean CV gate.",
            "D33D_FIXED_SOLID_FAILED": "PET was detected in effluent or the solid geometry was demonstrably nonstationary.",
            "D33D_INCOMPLETE_BLOCK": "At least one of the 15 batch endpoints is unavailable; confirmatory inference is withheld.",
            "D33D_POST_OUTCOME_REPLACEMENT": "A specimen or batch was replaced after outcome inspection outside the frozen rule.",
            "D33D_BLINDING_OR_ROLE_OVERLAP": "Treatment leakage or prohibited role overlap occurred before primary freeze.",
            "D33D_PET_PREDICTION_NOT_FROZEN": "PET-specific numerical prediction ranges were not frozen before data reveal; model validation is prohibited.",
            "D33D_DEGRADATION_EVIDENCE_INSUFFICIENT": "Length was the only degradation indicator or the independent chemistry/confirmation gates failed.",
        },
    }
    write_json(OUT / "failure_codes.json", failure_codes)

    analysis_specification = """# Stage33D statistical analysis specification (V1)

## Unit and endpoint

The independent treatment unit is the PET process batch. Three packed columns are nested technical replicates. For every valid matched set compute `z_btr = log(K20_mix) - log(K20_clean)`, then average the valid set values to obtain one `R_bt` per batch. Never analyze fields, objects, repeated flow readings or columns as independent treatment replicates.

## Confirmatory profile

Fit `R_bt = mu + Block_b + Treatment_t + epsilon_bt` to all 15 batch endpoints. Report the unrestricted profile, raw batch points, within-block contrasts, residuals and leave-one-block-out sensitivity. Monotonicity is descriptive. The planned high-severity contrast is `T180 - T20`; the planned treated-only trend covers T120–T180 per 20 °C and excludes T20 from the numerical temperature slope.

If and only if assignment was randomized within complete blocks, use exact whole-batch randomization inference for the omnibus treatment statistic. Column repeats do not increase the treatment degrees of freedom. Missing batches are not imputed; an incomplete design is descriptive.

## Morphology–hydraulic association

The primary morphology covariate is frozen same-batch `log(D50 maximum Feret)`. Fit `R_bt = alpha + Block_b + beta log(D50_bt) + epsilon_bt`. Propagate uncertainty by resampling whole microscopy fields within batches and complete matched column sets, never individual objects. Report the slope as association, not causal mediation or a universal degradation calibration.

## Molecular evidence and confirmation

Keep `Mn`, the orthogonal chain-scission/product endpoint, crystallinity and mass balance separate. Calling length a degradation proxy requires a new independent confirmation wave with all molecular, orthogonal, recovery and reproducibility gates frozen before reveal. Stage33D supplies variance estimates for that wave; it does not use retrospective power to upgrade an inconclusive result.

## Numerical comparison

Existing F37 straight-fibre predictions are contextual solution-verification evidence only. A numerical physical-validation analysis is allowed only against PET-specific ranges frozen before hydraulic reveal. No retuning is permitted on the validation data.
"""
    (OUT / "STATISTICAL_ANALYSIS_SPECIFICATION.md").write_text(analysis_specification, encoding="utf-8")

    counts = Counter(str(row["condition_id"]) for row in specimen_plan)
    future_inputs = {
        "stage33a_empirical_readiness_closure": {"path": "", "sha256": "", "populated": False},
        "stage33cq_empirical_heldout_gate_report": {"path": "", "sha256": "", "populated": False},
        "stage33cq_adjudicated_morphology_release": {"path": "", "sha256": "", "populated": False},
        "real_cross_release_commitment": {"path": "", "sha256": "", "populated": False},
        "pet_mass_budget_and_split_qualification": {"path": "", "sha256": "", "populated": False},
        "hydraulic_apparatus_calibration_release": {"path": "", "sha256": "", "populated": False},
        "effluent_pet_detection_method_release": {"path": "", "sha256": "", "populated": False},
        "molecular_and_orthogonal_chemistry_release_for_degradation_claim": {"path": "", "sha256": "", "populated": False},
        "pet_specific_frozen_numerical_predictions_for_model_validation": {"path": "", "sha256": "", "populated": False},
    }
    resolved = {
        "schema": "pet.stage33d-matched-pet-lbs-physical-validation-design.v1",
        "stage": "Stage33D",
        "release_id": "STAGE33D-PREDATA-DESIGN-01",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "frozen_predata_design_only_execution_closed",
        "passed": True,
        "research_question": "At fixed PET dry-mass loading and matched LBS state, does water-only temperature-conditioned PET morphology change K20/K20_clean?",
        "evidence_role": "prospective matched physical-validation design; no empirical observations or operational key",
        "conditions": list(CONDITIONS),
        "experimental_unit": "independent PET process batch",
        "hierarchy": ["reactor_block", "PET_process_batch", "split_aliquot", "packed_column", "flow_determination"],
        "design": {
            "reactor_blocks": 3,
            "conditions_per_block": 5,
            "independent_pet_batches": 15,
            "technical_columns_per_pet_batch": 3,
            "pet_columns": 45,
            "clean_columns_per_block": 3,
            "clean_columns": 9,
            "total_columns": 54,
            "target_pet_dry_mass_percent": TARGET_PET_WT_PERCENT,
            "target_total_solid_void_ratio": 0.744,
            "water_temperature_c": 20.0,
            "test": "steady saturated constant-head",
            "randomization_seeds": {str(key): value for key, value in RANDOMIZATION_SEEDS.items()},
            "specimen_counts_by_condition": dict(sorted(counts.items())),
            "monotonicity_is_not_an_acceptance_gate": True,
        },
        "primary_estimand": "batch mean of log(K20_PET / matched K20_clean) across valid technical replicates",
        "primary_morphology_covariate": "same-batch log(D50 maximum Feret) from a future empirically qualified Stage33C-Q release",
        "minimum_relevant_log_ratio_effect": abs(math.log(0.95)),
        "blinding": {
            "status": "template_only_no_operational_key",
            "real_identifiers_present": False,
            "real_treatment_key_present": False,
            "operational_release_required": True,
        },
        "source_bindings": {role: {"path": str(path), "sha256": sha256(path)} for role, path in SOURCES.items()},
        "future_required_inputs": future_inputs,
        "readiness": {
            "design_ready_for_independent_audit": True,
            "operational_release_ready": False,
            "laboratory_execution_ready": False,
            "empirical_analysis_ready": False,
            "numerical_validation_ready": False,
            "degradation_proxy_claim_ready": False,
        },
        "claim_boundary": "temperature-conditioned fragmentation phenotype and matched hydraulic response only after future empirical gates; length alone is not molecular degradation",
        "stop_boundary": "stop before real keys, empirical processing, laboratory or numerical execution, unblinding, retuning, or degradation/permeability/migration/clogging/coupling claims",
        "authority": {
            "real_key_ingest": False,
            "empirical_image_processing": False,
            "laboratory_execution": False,
            "numerical_execution": False,
            "model_recalibration": False,
            "physical_validation_claim": False,
            "molecular_degradation_claim": False,
            "length_as_degradation_proxy_claim": False,
            "migration_or_clogging_claim": False,
            "deformation_or_coupling_claim": False,
        },
    }
    write_json(OUT / "resolved_design.json", resolved)

    artifact_names = [
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
        "resolved_design.json",
    ]
    completion = {
        "schema": "pet.stage33d-matched-pet-lbs-physical-validation-design-completion.v1",
        "status": "complete_design_ready_for_independent_audit_execution_closed",
        "passed": True,
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "checks": {
            "exact_15_independent_pet_batch_slots": len({row["source_batch_slot"] for row in specimen_plan if row["source_batch_slot"]}) == 15,
            "exact_45_pet_columns": sum(row["specimen_role"] == "pet_mixture" for row in specimen_plan) == 45,
            "exact_9_clean_columns": sum(row["specimen_role"] == "clean_lbs_control" for row in specimen_plan) == 9,
            "exact_54_total_columns": len(specimen_plan) == 54,
            "all_future_inputs_unpopulated": all(not item["populated"] and not item["path"] and not item["sha256"] for item in future_inputs.values()),
            "no_operational_key": resolved["blinding"]["real_treatment_key_present"] is False,
            "all_execution_authority_closed": not any(resolved["authority"].values()),
        },
        "artifacts": {name: {"path": str(OUT / name), "sha256": sha256(OUT / name)} for name in artifact_names},
        "next_handoff": "independent design audit only; empirical and operational inputs remain absent",
    }
    write_json(OUT / "completion.json", completion)
    print(
        json.dumps(
            {
                "output": str(OUT),
                "pet_batches": 15,
                "pet_columns": 45,
                "clean_columns": 9,
                "total_columns": 54,
                "operational_release_ready": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
