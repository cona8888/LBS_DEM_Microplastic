"""Synthetic-only end-to-end verification of the Stage33C-Q release tools.

The driver creates no empirical PET observations and uses no operational key.
It exercises the immutable acquisition, two-person visual-release, and
independent-mask qualification paths with deterministic synthetic fixtures, then
checks that specified invalid inputs fail closed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PIL import Image


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
DESIGN_CONFIG_PATH = (
    SCRIPT_DIR.parent / "stage33_designs" / "stage33cq_acquisition_qualification_20260831"
    / "release_01" / "builder_config.json"
)

from build_stage33cq_blinded_acquisition_release_v1 import build_release  # noqa: E402
from qualify_stage33cq_independent_masks_v1 import qualify  # noqa: E402
from seal_stage33cq_analyst_release_v1 import seal  # noqa: E402


VERSION = "1.0.0"
VERIFICATION_ID = "STAGE33CQ_SYNTHETIC_ACQUISITION_AND_MASKS_V1"
RELEASE_ID = "STAGE33CQ-SYNTHETIC-TEST-V1"
TEST_SECRET_LABEL = "TEST_ONLY_FIXED_SECRET_NOT_FOR_EMPIRICAL_OR_OPERATIONAL_USE"
TEST_SECRET = b"STAGE33CQ_TEST_ONLY_SECRET_V1__NOT_FOR_EMPIRICAL_DATA__0001"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str] | None = None) -> None:
    if columns is None:
        if not rows:
            raise RuntimeError(f"synthetic fixture has no rows: {path}")
        columns = list(rows[0])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def ensure_new_output(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise RuntimeError(f"fail-closed: verification output is not empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def bool_value(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def make_raw_image(path: Path, object_index: int) -> None:
    """Write an 8-bit synthetic microscopy-like image without metadata."""
    height, width = 96, 128
    yy, xx = np.mgrid[0:height, 0:width]
    background = 222.0 + 4.0 * xx / (width - 1)
    array = np.clip(background, 0, 255).astype(np.uint8)
    if object_index == 1:
        array[40:56, 20:80] = 35
    elif object_index == 2:
        array[38:58, 15:105] = 42
    else:
        raise ValueError(object_index)
    Image.fromarray(array, mode="L").save(path, format="PNG")


def make_label_mask(path: Path, object_index: int, shift_x: int = 0) -> None:
    mask = np.zeros((96, 128), dtype=np.uint16)
    if object_index == 1:
        x0, x1, y0, y1 = 20 + shift_x, 80 + shift_x, 40, 56
    elif object_index == 2:
        x0, x1, y0, y1 = 15 + shift_x, 105 + shift_x, 38, 58
    else:
        raise ValueError(object_index)
    if not (0 <= x0 < x1 <= mask.shape[1]):
        raise RuntimeError("synthetic shifted mask left the test canvas")
    mask[y0:y1, x0:x1] = 1
    Image.fromarray(mask, mode="I;16").save(path, format="PNG")


def create_inputs(output: Path) -> dict[str, Any]:
    inputs = output / "inputs"
    raw_dir = inputs / "raw"
    evidence_dir = inputs / "synthetic_evidence"
    raw_dir.mkdir(parents=True)
    evidence_dir.mkdir(parents=True)

    secret_path = inputs / "TEST_ONLY_fixed_secret.bin"
    secret_path.write_bytes(TEST_SECRET)
    calibration_path = evidence_dir / "TEST_ONLY_calibration_record.json"
    pet_identity_path = evidence_dir / "TEST_ONLY_pet_identity_record.json"
    psf_path = evidence_dir / "TEST_ONLY_psf_record.json"
    json_dump(calibration_path, {
        "record_type": "synthetic_stage_micrometer_fixture",
        "test_only": True,
        "pixel_size_x_um": 0.5,
        "pixel_size_y_um": 0.5,
        "not_empirical": True,
    })
    json_dump(pet_identity_path, {
        "record_type": "synthetic_identity_fixture",
        "test_only": True,
        "identity": "synthetic_PET_label_for_software_test_only",
        "not_a_material_measurement": True,
    })
    json_dump(psf_path, {
        "record_type": "synthetic_psf_fixture",
        "test_only": True,
        "psf_fwhm_px": 1.5,
        "not_empirical": True,
    })

    raw_paths = [raw_dir / "field_01.png", raw_dir / "field_02.png"]
    for index, path in enumerate(raw_paths, start=1):
        make_raw_image(path, index)

    roles = {
        "key_custodian_ids": ["TEST_CUSTODIAN"],
        "acquisition_operator_ids": ["TEST_OPERATOR"],
        "release_officer_ids": ["TEST_RELEASE_OFFICER_1", "TEST_RELEASE_OFFICER_2"],
        "morphology_analyst_ids": ["TEST_MASK_REVIEWER_A", "TEST_MASK_REVIEWER_B"],
        "freeze_auditor_ids": ["TEST_FREEZE_AUDITOR"],
        "reveal_authority_ids": ["TEST_REVEAL_AUTHORITY_1", "TEST_REVEAL_AUTHORITY_2"],
    }
    roles_path = inputs / "TEST_ONLY_roles.json"
    json_dump(roles_path, roles)

    common = {
        "source_batch_id": "SYNTH_BATCH_01",
        "source_aliquot_id": "SYNTH_ALIQUOT_01",
        "source_mount_id": "SYNTH_MOUNT_01",
        "condition_id": "SYNTH_CONDITION_A",
        "condition_role": "process_control",
        "target_temperature_C": "20",
        "challenge_arm": "none",
        "randomization_block": "SYNTH_BLOCK_01",
        "field_selection_method": "systematic_random",
        "field_selection_probability": "0.5",
        "expected_field_count": "2",
        "pixel_size_x_um": "0.5",
        "pixel_size_y_um": "0.5",
        "image_qc_status": "pass",
        "calibration_valid": "true",
        "calibration_file_path": str(calibration_path.relative_to(inputs)),
        "calibration_sha256": sha256(calibration_path),
        "pet_confirmed": "true",
        "pet_identity_record_path": str(pet_identity_path.relative_to(inputs)),
        "pet_identity_record_sha256": sha256(pet_identity_path),
        "psf_fwhm_px": "1.5",
        "psf_record_path": str(psf_path.relative_to(inputs)),
        "psf_record_sha256": sha256(psf_path),
        "flow_axis_deg": "0",
        "candidate_polarity": "dark_on_light",
        "operator_id": "TEST_OPERATOR",
        "instrument_id": "SYNTH_SCOPE",
        "objective_id": "SYNTH_OBJECTIVE",
        "camera_id": "SYNTH_CAMERA",
        "acquisition_utc": "2026-01-01T00:00:00Z",
        "image_width_px": "128",
        "image_height_px": "96",
        "bit_depth": "8",
    }
    rows: list[dict[str, Any]] = []
    for index, raw_path in enumerate(raw_paths, start=1):
        rows.append({
            **common,
            "source_image_id": f"SYNTH_IMAGE_{index:02d}",
            "source_field_id": f"FIELD_{index:02d}",
            "selected_field_ordinal": str(index),
            "raw_file_path": str(raw_path.relative_to(inputs)),
            "raw_sha256": sha256(raw_path),
        })
    manifest_path = inputs / "TEST_ONLY_acquisition_manifest.csv"
    write_csv(manifest_path, rows)
    return {
        "inputs_dir": inputs,
        "manifest_path": manifest_path,
        "manifest_rows": rows,
        "roles_path": roles_path,
        "roles": roles,
        "secret_path": secret_path,
        "raw_paths": raw_paths,
        "evidence_paths": [calibration_path, pet_identity_path, psf_path],
    }


def create_visual_review(pending: Path, destination: Path, incomplete: bool = False) -> list[dict[str, Any]]:
    rows = read_csv(pending / "visual_leakage_review_template.csv")
    reviewers = {"1": "TEST_RELEASE_OFFICER_1", "2": "TEST_RELEASE_OFFICER_2"}
    completed: list[dict[str, Any]] = []
    for row in rows:
        completed.append({
            **row,
            "reviewer_id": reviewers[row["reviewer_slot"]],
            "review_status": "pass",
            "burned_label_absent": "true",
            "burned_scale_bar_absent": "true",
            "other_visual_leakage_absent": "true",
            "findings": "",
            "review_utc": "2026-01-02T00:00:00Z",
        })
    if incomplete:
        completed = completed[:-1]
    write_csv(destination, completed, list(rows[0]))
    return completed


def create_reviewer_submission(
    blinded_manifest_path: Path,
    root: Path,
    reviewer_id: str,
    reviewer_prefix: str,
    perturb_first_mask_px: int = 0,
) -> Path:
    root.mkdir(parents=True)
    image_rows = read_csv(blinded_manifest_path)
    submission_rows: list[dict[str, Any]] = []
    for index, image_row in enumerate(sorted(image_rows, key=lambda row: row["image_id"]), start=1):
        image_id = image_row["image_id"]
        mask_path = root / f"{image_id}_instances.png"
        annotation_path = root / f"{image_id}_annotations.csv"
        shift = perturb_first_mask_px if index == 1 else 0
        make_label_mask(mask_path, index, shift_x=shift)
        annotation = [{
            "image_id": image_id,
            "reviewer_object_id": f"{reviewer_prefix}_{index:03d}",
            "mask_label": "1",
            "morphology_class": "straight_fibre",
            "border_touch": "false",
            "counting_frame_status": "accepted",
            "censor_type": "none",
            "topology_status": "two_endpoints_no_branch",
            "segmentation_disposition": "retained",
            "ambiguity_flag": "false",
            "confidence_code": "high",
            "exclusion_reason": "",
        }]
        write_csv(annotation_path, annotation)
        submission_rows.append({
            "blind_release_id": image_row["blind_release_id"],
            "reviewer_id": reviewer_id,
            "review_pass": "true",
            "image_id": image_id,
            "instance_mask_path": str(mask_path),
            "instance_mask_sha256": sha256(mask_path),
            "annotation_path": str(annotation_path),
            "annotation_sha256": sha256(annotation_path),
            "submission_utc": "2026-01-03T00:00:00Z",
        })
    submission_path = root / "submissions.csv"
    write_csv(submission_path, submission_rows)
    return submission_path


def analyst_pixel_identity_check(pending: Path, restricted: Path, secret_path: Path) -> dict[str, Any]:
    analyst_rows = read_csv(pending / "blinded_image_manifest.csv")
    restricted_rows = read_csv(restricted / "custodian_key.csv")
    by_blind = {row["blind_image_code"]: row for row in restricted_rows}
    exact_arrays = []
    cross_table_pixel_hashes = []
    for analyst in analyst_rows:
        restricted_row = by_blind[analyst["image_id"]]
        with Image.open(restricted_row["source_raw_file_path"]) as source_image:
            source = np.asarray(source_image)
        with Image.open(analyst["raw_file_path"]) as sanitized_image:
            sanitized = np.asarray(sanitized_image)
        exact_arrays.append(source.dtype == sanitized.dtype and source.shape == sanitized.shape and np.array_equal(source, sanitized))
        cross_table_pixel_hashes.append(analyst["pixel_sha256"] == restricted_row["pixel_sha256"])
    analyst_header = set(analyst_rows[0])
    restricted_only_metadata = {"source_metadata_present", "sanitized_metadata_text_sha256"}
    secret = secret_path.read_bytes()
    secret_absent = all(secret not in path.read_bytes() for path in pending.rglob("*") if path.is_file())
    return {
        "image_n": len(analyst_rows),
        "manifest_pixel_identity_flags_all_true": all(bool_value(row["pixel_identity_pass"]) for row in analyst_rows),
        "independent_source_to_sanitized_arrays_equal": all(exact_arrays),
        "restricted_to_analyst_pixel_hashes_equal": all(cross_table_pixel_hashes),
        "restricted_source_metadata_fields_absent_from_analyst_csv": not bool(restricted_only_metadata & analyst_header),
        "fixed_test_secret_bytes_absent_from_analyst_package": secret_absent,
    }


def expect_failure(
    name: str,
    operation: Callable[[], Any],
    expected_message_fragment: str,
    challenge_root: Path,
) -> dict[str, Any]:
    try:
        operation()
    except Exception as error:  # deliberate broad catch: unexpected exception types are recorded as failures
        message = str(error)
        observed = True
        expected_type = isinstance(error, RuntimeError)
        message_match = expected_message_fragment.lower() in message.lower()
        completed_artifacts = sorted(
            str(path.relative_to(challenge_root))
            for path in challenge_root.rglob("completion.json")
            if path.is_file()
        )
        return {
            "challenge": name,
            "expected_failure": True,
            "observed_failure": observed,
            "exception_type": type(error).__name__,
            "message": message,
            "expected_message_fragment": expected_message_fragment,
            "runtime_error": expected_type,
            "message_match": message_match,
            "unexpected_completion_artifacts": completed_artifacts,
            "passed": observed and expected_type and message_match and not completed_artifacts,
        }
    return {
        "challenge": name,
        "expected_failure": True,
        "observed_failure": False,
        "exception_type": "",
        "message": "operation unexpectedly succeeded",
        "expected_message_fragment": expected_message_fragment,
        "runtime_error": False,
        "message_match": False,
        "unexpected_completion_artifacts": [],
        "passed": False,
    }


def copy_manifest_variant(rows: list[dict[str, Any]], path: Path, source_base: Path) -> Path:
    normalized = deepcopy(rows)
    for row in normalized:
        for field in (
            "raw_file_path", "calibration_file_path", "pet_identity_record_path", "psf_record_path",
        ):
            bound = Path(str(row[field]))
            if not bound.is_absolute():
                row[field] = str((source_base / bound).resolve())
    write_csv(path, normalized)
    return path


def run_verification(output: Path) -> dict[str, Any]:
    if not DESIGN_CONFIG_PATH.is_file():
        raise RuntimeError(f"synthetic verification design config is missing: {DESIGN_CONFIG_PATH}")
    frozen_design_dir = output / "design"
    frozen_design_dir.mkdir()
    frozen_design_config = frozen_design_dir / "builder_config.json"
    shutil.copy2(DESIGN_CONFIG_PATH, frozen_design_config)
    fixture = create_inputs(output)
    successful = output / "successful_release"
    restricted = successful / "restricted"
    pending = successful / "pending_analyst"
    sealed = successful / "sealed_analyst"
    build_result = build_release(
        fixture["manifest_path"], fixture["secret_path"], fixture["roles_path"], RELEASE_ID,
        restricted, pending, frozen_design_config,
    )

    completed_review_path = successful / "completed_visual_review.csv"
    completed_review_rows = create_visual_review(pending, completed_review_path)
    seal_result = seal(
        pending, completed_review_path, fixture["roles_path"],
        restricted / "cross_release_commitment.json", sealed,
    )
    pixel_checks = analyst_pixel_identity_check(pending, restricted, fixture["secret_path"])
    pending_manifest = json.loads((pending / "analyst_manifest.json").read_text(encoding="utf-8"))
    leakage_scan = json.loads((pending / "leakage_scan.json").read_text(encoding="utf-8"))
    reviewer_ids = sorted({row["reviewer_id"] for row in completed_review_rows})
    successful_checks = {
        "build_status": build_result["status"],
        "sanitized_release_status": pending_manifest["status"],
        "image_n": build_result["image_n"],
        "pixel_identity": pixel_checks,
        "treatment_key_present": pending_manifest["treatment_key_present"],
        "sealed_state": seal_result["state"],
        "two_person_visual_review": seal_result["two_person_visual_review"],
        "machine_leakage_scan_status": leakage_scan["status"],
        "machine_leakage_finding_n": leakage_scan["finding_n"],
        "leakage_scan_hash_bound": (
            pending_manifest["leakage_scan_sha256"] == sha256(pending / "leakage_scan.json")
        ),
        "custodian_cross_commitment_hash_bound": (
            build_result["cross_release_commitment_sha256"]
            == sha256(restricted / "cross_release_commitment.json")
            == seal_result["restricted_cross_release_commitment_sha256"]
        ),
        "reviewer_ids": reviewer_ids,
    }
    successful_checks["passed"] = all([
        successful_checks["build_status"] == "sanitized_pending_visual_review",
        successful_checks["sanitized_release_status"] == "sanitized_blinded_analyst_package",
        successful_checks["image_n"] == 2,
        all(pixel_checks.values()) if pixel_checks else False,
        successful_checks["treatment_key_present"] is False,
        successful_checks["sealed_state"] == "ANALYST_RELEASED",
        successful_checks["two_person_visual_review"] == "pass",
        successful_checks["machine_leakage_scan_status"] == "pass",
        successful_checks["machine_leakage_finding_n"] == 0,
        successful_checks["leakage_scan_hash_bound"] is True,
        successful_checks["custodian_cross_commitment_hash_bound"] is True,
        reviewer_ids == ["TEST_RELEASE_OFFICER_1", "TEST_RELEASE_OFFICER_2"],
    ])

    blinded_manifest = pending / "blinded_image_manifest.csv"
    mask_root = output / "mask_qualification"
    identical_root = mask_root / "identical_inputs"
    identical_a = create_reviewer_submission(
        blinded_manifest, identical_root / "reviewer_a", "TEST_MASK_REVIEWER_A", "A",
    )
    identical_b = create_reviewer_submission(
        blinded_manifest, identical_root / "reviewer_b", "TEST_MASK_REVIEWER_B", "B",
    )
    identical_output = mask_root / "identical_pass"
    identical_summary = qualify(
        blinded_manifest, identical_a, identical_b, fixture["roles_path"], identical_output,
    )
    identical_checks = {
        "preconsensus_gate_pass": identical_summary["preconsensus_gate_pass"],
        "discrepancy_n": identical_summary["discrepancy_n"],
        "median_dice": identical_summary["median_dice"],
        "median_boundary_f1_2px": identical_summary["median_boundary_f1_2px"],
        "median_hausdorff95_px": identical_summary["median_hausdorff95_px"],
        "morphology_class_cohen_kappa": identical_summary["morphology_class_cohen_kappa"],
        "feret_max_icc_A1": identical_summary["feret_max_icc_A1"],
    }
    identical_checks["passed"] = all([
        identical_checks["preconsensus_gate_pass"] is True,
        identical_checks["discrepancy_n"] == 0,
        identical_checks["median_dice"] == 1.0,
        identical_checks["median_boundary_f1_2px"] == 1.0,
        identical_checks["median_hausdorff95_px"] == 0.0,
    ])

    perturbed_root = mask_root / "perturbed_inputs"
    perturbed_a = create_reviewer_submission(
        blinded_manifest, perturbed_root / "reviewer_a", "TEST_MASK_REVIEWER_A", "A",
    )
    perturbed_b = create_reviewer_submission(
        blinded_manifest, perturbed_root / "reviewer_b", "TEST_MASK_REVIEWER_B", "B", perturb_first_mask_px=8,
    )
    perturbed_output = mask_root / "perturbed_fail"
    perturbed_summary = qualify(
        blinded_manifest, perturbed_a, perturbed_b, fixture["roles_path"], perturbed_output,
    )
    discrepancy_rows = read_csv(perturbed_output / "discrepancy_queue.csv")
    perturbed_checks = {
        "preconsensus_gate_pass": perturbed_summary["preconsensus_gate_pass"],
        "discrepancy_n": perturbed_summary["discrepancy_n"],
        "median_dice": perturbed_summary["median_dice"],
        "median_hausdorff95_px": perturbed_summary["median_hausdorff95_px"],
        "discrepancy_types": sorted({row["discrepancy_type"] for row in discrepancy_rows}),
        "discrepancy_queue_sha256": sha256(perturbed_output / "discrepancy_queue.csv"),
    }
    perturbed_checks["passed"] = all([
        perturbed_checks["preconsensus_gate_pass"] is False,
        perturbed_checks["discrepancy_n"] >= 1,
        len(discrepancy_rows) == perturbed_checks["discrepancy_n"],
        "matched_object_boundary_or_class" in perturbed_checks["discrepancy_types"],
    ])

    challenges = output / "challenges"
    challenges.mkdir()
    challenge_results: dict[str, dict[str, Any]] = {}

    duplicate_rows = deepcopy(fixture["manifest_rows"])
    duplicate_rows[1]["source_image_id"] = duplicate_rows[0]["source_image_id"]
    duplicate_manifest = copy_manifest_variant(
        duplicate_rows, challenges / "duplicate_source_image_manifest.csv", fixture["inputs_dir"],
    )
    challenge_results["duplicate_source_image"] = expect_failure(
        "duplicate_source_image",
        lambda: build_release(
            duplicate_manifest, fixture["secret_path"], fixture["roles_path"], RELEASE_ID,
            challenges / "duplicate_restricted", challenges / "duplicate_analyst", frozen_design_config,
        ),
        "duplicate source_image_id", challenges,
    )

    bad_hash_rows = deepcopy(fixture["manifest_rows"])
    bad_hash_rows[0]["raw_sha256"] = "0" * 64
    bad_hash_manifest = copy_manifest_variant(
        bad_hash_rows, challenges / "bad_raw_hash_manifest.csv", fixture["inputs_dir"],
    )
    challenge_results["bad_raw_hash"] = expect_failure(
        "bad_raw_hash",
        lambda: build_release(
            bad_hash_manifest, fixture["secret_path"], fixture["roles_path"], RELEASE_ID,
            challenges / "bad_hash_restricted", challenges / "bad_hash_analyst", frozen_design_config,
        ),
        "source raw hash mismatch", challenges,
    )

    bad_calibration_rows = deepcopy(fixture["manifest_rows"])
    bad_calibration_rows[0]["calibration_sha256"] = "0" * 64
    bad_calibration_manifest = copy_manifest_variant(
        bad_calibration_rows, challenges / "bad_calibration_hash_manifest.csv", fixture["inputs_dir"],
    )
    challenge_results["bad_calibration_hash"] = expect_failure(
        "bad_calibration_hash",
        lambda: build_release(
            bad_calibration_manifest, fixture["secret_path"], fixture["roles_path"], RELEASE_ID,
            challenges / "bad_calibration_restricted", challenges / "bad_calibration_analyst",
            frozen_design_config,
        ),
        "calibration_sha256 mismatch", challenges,
    )

    overlap_roles = deepcopy(fixture["roles"])
    overlap_roles["morphology_analyst_ids"].append("TEST_CUSTODIAN")
    overlap_roles_path = challenges / "role_overlap.json"
    json_dump(overlap_roles_path, overlap_roles)
    challenge_results["role_overlap"] = expect_failure(
        "role_overlap",
        lambda: build_release(
            fixture["manifest_path"], fixture["secret_path"], overlap_roles_path, RELEASE_ID,
            challenges / "overlap_restricted", challenges / "overlap_analyst", frozen_design_config,
        ),
        "prohibited custody/analysis role overlap", challenges,
    )

    incomplete_manifest = copy_manifest_variant(
        deepcopy(fixture["manifest_rows"][:1]), challenges / "incomplete_field_plan_manifest.csv",
        fixture["inputs_dir"],
    )
    challenge_results["incomplete_field_plan"] = expect_failure(
        "incomplete_field_plan",
        lambda: build_release(
            incomplete_manifest, fixture["secret_path"], fixture["roles_path"], RELEASE_ID,
            challenges / "incomplete_restricted", challenges / "incomplete_analyst", frozen_design_config,
        ),
        "incomplete or duplicate probability field plan", challenges,
    )

    wrong_release_rows = read_csv(identical_b)
    for row in wrong_release_rows:
        row["blind_release_id"] = "STAGE33CQ-WRONG-TEST-RELEASE"
    wrong_release_submission = challenges / "wrong_release_submissions.csv"
    write_csv(wrong_release_submission, wrong_release_rows)
    challenge_results["wrong_release_id"] = expect_failure(
        "wrong_release_id",
        lambda: qualify(
            blinded_manifest, identical_a, wrong_release_submission, fixture["roles_path"],
            challenges / "wrong_release_qualification",
        ),
        "reviewer submission release binding mismatch", challenges,
    )

    incomplete_review_path = challenges / "incomplete_visual_review.csv"
    create_visual_review(pending, incomplete_review_path, incomplete=True)
    challenge_results["incomplete_visual_review"] = expect_failure(
        "incomplete_visual_review",
        lambda: seal(
            pending, incomplete_review_path, fixture["roles_path"],
            restricted / "cross_release_commitment.json", challenges / "incomplete_visual_seal",
        ),
        "requires reviewer slots 1 and 2", challenges,
    )

    commitment_challenge_dir = challenges / "mutated_cross_commitment"
    commitment_challenge_dir.mkdir()
    shutil.copy2(restricted / "restricted_manifest.json", commitment_challenge_dir / "restricted_manifest.json")
    mutated_commitment = json.loads(
        (restricted / "cross_release_commitment.json").read_text(encoding="utf-8")
    )
    mutated_commitment["analyst_manifest_sha256"] = "0" * 64
    mutated_commitment_path = commitment_challenge_dir / "cross_release_commitment.json"
    json_dump(mutated_commitment_path, mutated_commitment)
    challenge_results["mutated_cross_release_commitment"] = expect_failure(
        "mutated_cross_release_commitment",
        lambda: seal(
            pending, completed_review_path, fixture["roles_path"], mutated_commitment_path,
            challenges / "mutated_commitment_seal",
        ),
        "cross-release commitment does not bind", challenges,
    )

    script_paths = {
        "build_stage33cq_blinded_acquisition_release_v1.py": SCRIPT_DIR / "build_stage33cq_blinded_acquisition_release_v1.py",
        "seal_stage33cq_analyst_release_v1.py": SCRIPT_DIR / "seal_stage33cq_analyst_release_v1.py",
        "qualify_stage33cq_independent_masks_v1.py": SCRIPT_DIR / "qualify_stage33cq_independent_masks_v1.py",
        "verify_stage33cq_acquisition_and_masks_v1.py": Path(__file__).resolve(),
    }
    hash_bindings = {
        "inputs/TEST_ONLY_acquisition_manifest.csv": sha256(fixture["manifest_path"]),
        "inputs/TEST_ONLY_roles.json": sha256(fixture["roles_path"]),
        "design/builder_config.json": sha256(frozen_design_config),
        "successful_release/restricted/restricted_manifest.json": sha256(restricted / "restricted_manifest.json"),
        "successful_release/restricted/cross_release_commitment.json": sha256(
            restricted / "cross_release_commitment.json"
        ),
        "successful_release/pending_analyst/package_hashes.json": sha256(pending / "package_hashes.json"),
        "successful_release/sealed_analyst/release_declaration.json": sha256(sealed / "release_declaration.json"),
        "mask_qualification/identical_pass/preconsensus_freeze_manifest.json": sha256(identical_output / "preconsensus_freeze_manifest.json"),
        "mask_qualification/perturbed_fail/preconsensus_freeze_manifest.json": sha256(perturbed_output / "preconsensus_freeze_manifest.json"),
        "mask_qualification/perturbed_fail/discrepancy_queue.csv": sha256(perturbed_output / "discrepancy_queue.csv"),
    }
    overall_pass = all([
        successful_checks["passed"],
        identical_checks["passed"],
        perturbed_checks["passed"],
        all(result["passed"] for result in challenge_results.values()),
    ])
    return {
        "stage": "Stage33C-Q",
        "verification_id": VERIFICATION_ID,
        "version": VERSION,
        "created_utc": utc_now(),
        "production_scripts_sha256": {name: sha256(path) for name, path in script_paths.items()},
        "test_only_fixture": {
            "secret_label": TEST_SECRET_LABEL,
            "secret_sha256": sha256(fixture["secret_path"]),
            "test_only": True,
            "no_real_key": True,
            "no_empirical_data": True,
            "image_n": 2,
            "source_manifest_sha256": sha256(fixture["manifest_path"]),
            "roles_sha256": sha256(fixture["roles_path"]),
            "evidence_records_sha256": {path.name: sha256(path) for path in fixture["evidence_paths"]},
        },
        "successful_release_checks": successful_checks,
        "identical_mask_checks": identical_checks,
        "perturbed_mask_checks": perturbed_checks,
        "fail_closed_challenges": challenge_results,
        "hash_bindings": hash_bindings,
        "overall_pass": overall_pass,
        "claim_boundary": (
            "synthetic software verification of acquisition blinding, visual release, mask comparison, and "
            "fail-closed behavior only; no empirical PET morphology, treatment effect, chemical degradation, "
            "or simulation qualification"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    ensure_new_output(output)
    try:
        verification = run_verification(output)
    except Exception as error:  # preserve a diagnostic record for unexpected synthetic-driver failures
        verification = {
            "stage": "Stage33C-Q",
            "verification_id": VERIFICATION_ID,
            "version": VERSION,
            "created_utc": utc_now(),
            "overall_pass": False,
            "fatal_error": {"type": type(error).__name__, "message": str(error)},
            "claim_boundary": "synthetic software verification only; verification aborted",
        }
    verification_path = output / "verification.json"
    json_dump(verification_path, verification)
    completion = {
        "stage": "Stage33C-Q",
        "verification_id": VERIFICATION_ID,
        "status": "complete" if verification.get("overall_pass") is True else "failed",
        "completed_utc": utc_now(),
        "verification_sha256": sha256(verification_path),
        "overall_pass": verification.get("overall_pass") is True,
        "no_empirical_data": True,
        "no_real_secret": True,
        "no_treatment_reveal": True,
        "no_simulation": True,
    }
    json_dump(output / "completion.json", completion)
    print(json.dumps(completion, indent=2, sort_keys=True))
    return 0 if completion["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
