"""Build a Stage33C-Q freeze-before-reveal blinded acquisition release.

The tool produces two logically separate artifacts:
  * a restricted custodian package containing source-to-blind mappings; and
  * a sanitized analyst package containing opaque IDs and pixel-identical images.

It never modifies source files and never writes the custodian secret to output.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import json
import os
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont


VERSION = "1.0.0"
REQUIRED_COLUMNS = {
    "source_batch_id", "source_aliquot_id", "source_image_id", "source_mount_id",
    "source_field_id", "condition_id", "condition_role", "target_temperature_C",
    "challenge_arm", "randomization_block", "field_selection_method",
    "field_selection_probability", "expected_field_count", "selected_field_ordinal",
    "raw_file_path", "raw_sha256", "pixel_size_x_um", "pixel_size_y_um",
    "image_qc_status", "calibration_valid", "calibration_file_path", "calibration_sha256",
    "pet_confirmed", "pet_identity_record_path", "pet_identity_record_sha256",
    "psf_fwhm_px", "psf_record_path", "psf_record_sha256", "flow_axis_deg", "candidate_polarity",
    "operator_id", "instrument_id", "objective_id", "camera_id", "acquisition_utc",
    "image_width_px", "image_height_px", "bit_depth",
}

DEFAULT_CONFIG: dict[str, Any] = {
    "minimum_secret_bytes": 32,
    "blind_code_hex_chars": 32,
    "allowed_source_extensions": [".png", ".tif", ".tiff"],
    "allowed_image_modes": ["L", "I;16", "RGB"],
    "allowed_field_selection_methods": ["systematic_random", "simple_random", "stratified_random"],
    "allowed_condition_roles": ["process_control", "heated_treatment", "as_received_reference"],
    "forbidden_analyst_tokens": [
        "120c", "140c", "160c", "180c", "untreated", "control",
        "as_received", "as-received", "pxar", "t20",
    ],
    "sanitized_image_format": "PNG",
    "analyst_analysis_role": "locked_primary",
    "analyst_segmentation_status": "candidate_unadjudicated",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def bool_value(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def load_config(path: Path | None) -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    if path is not None:
        supplied = json.loads(path.read_text(encoding="utf-8"))
        unknown = set(supplied) - set(DEFAULT_CONFIG)
        if unknown:
            raise RuntimeError(f"fail-closed: unknown configuration keys: {sorted(unknown)}")
        config.update(supplied)
    return config


def resolve_path(value: str, manifest: Path) -> Path:
    path = Path(value)
    return (manifest.parent / path).resolve() if not path.is_absolute() else path.resolve()


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def blind_code(secret: bytes, release_id: str, namespace: str, value: str, chars: int) -> str:
    message = f"{release_id}|{namespace}|{value}".encode("utf-8")
    digest = hmac.new(secret, message, hashlib.sha256).hexdigest().upper()[:chars]
    prefix = {"batch": "B", "aliquot": "A", "image": "I", "mount": "M", "field": "F"}[namespace]
    return f"{prefix}-{digest}"


def normalized_challenge_role(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"pre", "pre_challenge", "unchallenged", "before_challenge"}:
        return "pre_challenge"
    if normalized in {"post", "post_challenge", "standardized_challenge", "after_challenge"}:
        return "post_challenge"
    if normalized in {"none", "not_applicable", "na"}:
        return "not_applicable"
    raise RuntimeError(f"fail-closed: unsupported challenge_arm value: {value!r}")


def pixel_digest(array: np.ndarray, mode: str) -> str:
    little_dtype = array.dtype.newbyteorder("<")
    canonical = np.ascontiguousarray(array.astype(little_dtype, copy=False))
    header = json.dumps(
        {"dtype": canonical.dtype.str, "mode": mode, "shape": list(canonical.shape)},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(b"STAGE33CQ_PIXEL_V1\0" + header + b"\0" + canonical.tobytes(order="C"))


def metadata_text(image: Image.Image) -> str:
    return json.dumps({"info": image.info, "exif": dict(image.getexif())}, default=str, sort_keys=True).lower()


def sanitize_image(source: Path, destination: Path, config: dict[str, Any]) -> dict[str, Any]:
    with Image.open(source) as image:
        if int(getattr(image, "n_frames", 1)) != 1:
            raise RuntimeError(f"fail-closed: multi-frame image not supported: {source}")
        if image.mode not in set(config["allowed_image_modes"]):
            raise RuntimeError(f"fail-closed: unsupported image mode {image.mode!r}: {source}")
        source_metadata = metadata_text(image)
        array = np.asarray(image).copy()
        source_mode = image.mode
    destination.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(array).save(destination, format=config["sanitized_image_format"])
    with Image.open(destination) as check_image:
        check_array = np.asarray(check_image)
        output_metadata = metadata_text(check_image)
        output_mode = check_image.mode
    if array.dtype != check_array.dtype or array.shape != check_array.shape or not np.array_equal(array, check_array):
        raise RuntimeError(f"fail-closed: sanitization changed pixel data: {source}")
    forbidden = [str(v).lower() for v in config["forbidden_analyst_tokens"]]
    leaked = sorted(token for token in forbidden if token and token in output_metadata)
    if leaked:
        raise RuntimeError(f"fail-closed: treatment token remained in sanitized metadata {leaked}: {destination}")
    return {
        "source_mode": source_mode,
        "sanitized_mode": output_mode,
        "pixel_sha256": pixel_digest(array, source_mode),
        "source_metadata_present": bool(source_metadata not in {"{\"exif\": {}, \"info\": {}}", ""}),
        "sanitized_metadata_text_sha256": sha256_bytes(output_metadata.encode()),
        "pixel_identity_pass": True,
        "image_width_px": int(array.shape[1]),
        "image_height_px": int(array.shape[0]),
        "bit_depth": int(array.dtype.itemsize * 8),
    }


def build_visual_montage(images_dir: Path, analyst_rows: list[dict[str, Any]], destination: Path) -> None:
    tile_w, tile_h, columns = 240, 220, 4
    row_n = (len(analyst_rows) + columns - 1) // columns
    canvas = Image.new("RGB", (tile_w * columns, tile_h * row_n), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for index, row in enumerate(analyst_rows):
        source = images_dir / f"{row['image_id']}.png"
        image = Image.open(source).convert("RGB")
        image.thumbnail((tile_w - 12, tile_h - 34))
        x = (index % columns) * tile_w + 6
        y = (index // columns) * tile_h + 24
        canvas.paste(image, (x, y))
        draw.text((x, y - 18), str(row["image_id"]), fill="black", font=font)
    canvas.save(destination, format="PNG")


def validate_source_rows(rows: list[dict[str, str]], manifest: Path, config: dict[str, Any]) -> None:
    if not rows:
        raise RuntimeError("fail-closed: acquisition manifest has no rows")
    missing = REQUIRED_COLUMNS - set(rows[0])
    if missing:
        raise RuntimeError(f"fail-closed: acquisition manifest missing columns: {sorted(missing)}")
    hash_pattern = re.compile(r"^[0-9a-fA-F]{64}$")
    image_ids: set[str] = set()
    image_paths: set[Path] = set()
    batch_map: dict[str, tuple[str, str, str, str]] = {}
    aliquot_map: dict[str, tuple[str, str]] = {}
    field_plan: dict[str, tuple[int, list[int]]] = {}
    allowed_fields = {str(v).lower() for v in config["allowed_field_selection_methods"]}
    allowed_roles = {str(v).lower() for v in config["allowed_condition_roles"]}
    allowed_extensions = {str(v).lower() for v in config["allowed_source_extensions"]}
    for row_no, row in enumerate(rows, start=2):
        for field in ("source_batch_id", "source_aliquot_id", "source_image_id", "source_mount_id", "source_field_id"):
            if not row[field].strip():
                raise RuntimeError(f"fail-closed: blank {field} at row {row_no}")
        image_id = row["source_image_id"].strip()
        if image_id in image_ids:
            raise RuntimeError(f"fail-closed: duplicate source_image_id at row {row_no}: {image_id}")
        image_ids.add(image_id)
        source = resolve_path(row["raw_file_path"], manifest)
        if source in image_paths:
            raise RuntimeError(f"fail-closed: duplicate raw file binding at row {row_no}: {source}")
        image_paths.add(source)
        if not source.is_file():
            raise RuntimeError(f"fail-closed: source image missing at row {row_no}: {source}")
        if source.suffix.lower() not in allowed_extensions:
            raise RuntimeError(f"fail-closed: lossy or unsupported source-image extension at row {row_no}: {source}")
        if not hash_pattern.fullmatch(row["raw_sha256"].strip()) or sha256(source) != row["raw_sha256"].strip().lower():
            raise RuntimeError(f"fail-closed: source raw hash mismatch at row {row_no}: {source}")
        evidence_bindings = (
            ("calibration_file_path", "calibration_sha256"),
            ("pet_identity_record_path", "pet_identity_record_sha256"),
            ("psf_record_path", "psf_record_sha256"),
        )
        for path_field, hash_field in evidence_bindings:
            evidence_path = resolve_path(row[path_field], manifest)
            expected_hash = row[hash_field].strip().lower()
            if not evidence_path.is_file():
                raise RuntimeError(f"fail-closed: {path_field} does not resolve at row {row_no}: {evidence_path}")
            if not hash_pattern.fullmatch(expected_hash) or sha256(evidence_path) != expected_hash:
                raise RuntimeError(f"fail-closed: {hash_field} mismatch at row {row_no}: {evidence_path}")
        if float(row["pixel_size_x_um"]) <= 0 or float(row["pixel_size_y_um"]) <= 0:
            raise RuntimeError(f"fail-closed: invalid pixel scale at row {row_no}")
        if float(row["psf_fwhm_px"]) <= 0:
            raise RuntimeError(f"fail-closed: invalid PSF FWHM at row {row_no}")
        probability = float(row["field_selection_probability"])
        expected_count = int(row["expected_field_count"])
        ordinal = int(row["selected_field_ordinal"])
        if not (0.0 < probability <= 1.0) or expected_count <= 0 or not (1 <= ordinal <= expected_count):
            raise RuntimeError(f"fail-closed: invalid field-sampling plan at row {row_no}")
        if row["field_selection_method"].strip().lower() not in allowed_fields:
            raise RuntimeError(f"fail-closed: non-probability field selection at row {row_no}")
        if row["condition_role"].strip().lower() not in allowed_roles:
            raise RuntimeError(f"fail-closed: invalid condition_role at row {row_no}")
        role = row["condition_role"].strip().lower()
        temperature = row["target_temperature_C"].strip()
        if role == "heated_treatment" and (not temperature or float(temperature) <= 20):
            raise RuntimeError(f"fail-closed: heated treatment lacks valid target temperature at row {row_no}")
        if role == "process_control" and temperature and abs(float(temperature) - 20.0) > 5.0:
            raise RuntimeError(f"fail-closed: process control is not ambient-water at row {row_no}")
        batch = row["source_batch_id"].strip()
        batch_value = (
            row["condition_id"].strip(), role, temperature,
            row["randomization_block"].strip(),
        )
        if batch in batch_map and batch_map[batch] != batch_value:
            raise RuntimeError(f"fail-closed: inconsistent batch treatment binding at row {row_no}")
        batch_map[batch] = batch_value
        aliquot = row["source_aliquot_id"].strip()
        aliquot_value = (batch, row["challenge_arm"].strip())
        if aliquot in aliquot_map and aliquot_map[aliquot] != aliquot_value:
            raise RuntimeError(f"fail-closed: inconsistent aliquot binding at row {row_no}")
        aliquot_map[aliquot] = aliquot_value
        previous = field_plan.get(aliquot)
        if previous is None:
            field_plan[aliquot] = (expected_count, [ordinal])
        else:
            if previous[0] != expected_count:
                raise RuntimeError(f"fail-closed: inconsistent expected_field_count for aliquot {aliquot}")
            previous[1].append(ordinal)
    for aliquot, (expected, ordinals) in field_plan.items():
        if len(ordinals) != expected or sorted(ordinals) != list(range(1, expected + 1)):
            raise RuntimeError(
                f"fail-closed: incomplete or duplicate probability field plan for {aliquot}: "
                f"expected 1..{expected}, observed {sorted(ordinals)}"
            )


def validate_roles(path: Path) -> dict[str, list[str]]:
    roles = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "key_custodian_ids", "acquisition_operator_ids", "release_officer_ids",
        "morphology_analyst_ids", "freeze_auditor_ids", "reveal_authority_ids",
    }
    if set(roles) != required:
        raise RuntimeError(f"fail-closed: roles file must contain exactly {sorted(required)}")
    normalized: dict[str, list[str]] = {}
    for name in sorted(required):
        values = [str(v).strip() for v in roles[name]]
        if not values or any(not v for v in values) or len(values) != len(set(values)):
            raise RuntimeError(f"fail-closed: role {name} must contain unique nonblank IDs")
        normalized[name] = values
    privileged = set(normalized["key_custodian_ids"]) | set(normalized["acquisition_operator_ids"]) | set(normalized["release_officer_ids"])
    blinded = set(normalized["morphology_analyst_ids"]) | set(normalized["freeze_auditor_ids"])
    if privileged & blinded:
        raise RuntimeError(f"fail-closed: prohibited custody/analysis role overlap: {sorted(privileged & blinded)}")
    reveal = set(normalized["reveal_authority_ids"])
    if len(reveal) < 2:
        raise RuntimeError("fail-closed: at least two distinct reveal authorities are required")
    if reveal & set(normalized["morphology_analyst_ids"]):
        raise RuntimeError(f"fail-closed: reveal authorities cannot be morphology analysts: {sorted(reveal & set(normalized['morphology_analyst_ids']))}")
    return normalized


def build_release(
    acquisition_manifest: Path,
    secret_path: Path,
    roles_path: Path,
    release_id: str,
    restricted_output: Path,
    analyst_output: Path,
    config_path: Path | None,
) -> dict[str, Any]:
    if restricted_output.exists() or analyst_output.exists():
        raise RuntimeError("fail-closed: restricted and analyst output paths must not already exist")
    if restricted_output.resolve() == analyst_output.resolve():
        raise RuntimeError("fail-closed: restricted and analyst outputs must be distinct")
    config = load_config(config_path)
    if config_path is not None:
        config_sha256 = sha256(config_path)
        config_hash_basis = "exact_supplied_config_file_bytes"
    else:
        config_sha256 = sha256_bytes(
            (json.dumps(config, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        )
        config_hash_basis = "canonical_resolved_default_config"
    builder_sha256 = sha256(Path(__file__).resolve())
    roles = validate_roles(roles_path)
    roles_sha256 = sha256(roles_path)
    secret = secret_path.read_bytes()
    if len(secret) < int(config["minimum_secret_bytes"]):
        raise RuntimeError(f"fail-closed: custodian secret must be at least {config['minimum_secret_bytes']} bytes")
    with acquisition_manifest.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    validate_source_rows(rows, acquisition_manifest, config)
    allowed_operators = set(roles["acquisition_operator_ids"])
    unknown_operators = sorted({row["operator_id"].strip() for row in rows} - allowed_operators)
    if unknown_operators:
        raise RuntimeError(f"fail-closed: acquisition operator is absent from roles file: {unknown_operators}")
    dynamic_forbidden = {str(v).lower() for v in config["forbidden_analyst_tokens"]}
    for row in rows:
        for field in (
            "source_batch_id", "source_aliquot_id", "source_image_id", "source_mount_id",
            "condition_id", "condition_role", "randomization_block",
            "instrument_id", "operator_id",
        ):
            token = row[field].strip().lower()
            if len(token) >= 5:
                dynamic_forbidden.add(token)
        source_path = resolve_path(row["raw_file_path"], acquisition_manifest)
        for part in source_path.parts[-2:]:
            token = Path(part).stem.lower()
            if len(token) >= 5 and token not in {"images", "microscopy", "stage33d"}:
                dynamic_forbidden.add(token)

    tag = uuid.uuid4().hex
    restricted_tmp = restricted_output.parent / f".{restricted_output.name}.building-{tag}"
    analyst_tmp = analyst_output.parent / f".{analyst_output.name}.building-{tag}"
    for path in (restricted_tmp, analyst_tmp):
        if path.exists():
            raise RuntimeError(f"fail-closed: temporary output collision: {path}")
        path.mkdir(parents=True)
    try:
        restricted_rows: list[dict[str, Any]] = []
        analyst_seed_rows: list[dict[str, Any]] = []
        chars = int(config["blind_code_hex_chars"])
        key_nonce_hex = hmac.new(secret, f"{release_id}|restricted-key-nonce".encode(), hashlib.sha256).hexdigest()
        for row in rows:
            codes = {
                "blind_batch_code": blind_code(secret, release_id, "batch", row["source_batch_id"], chars),
                "blind_aliquot_code": blind_code(secret, release_id, "aliquot", row["source_aliquot_id"], chars),
                "blind_image_code": blind_code(secret, release_id, "image", row["source_image_id"], chars),
                "blind_mount_code": blind_code(secret, release_id, "mount", row["source_mount_id"], chars),
                "blind_field_code": blind_code(secret, release_id, "field", f"{row['source_image_id']}|{row['source_field_id']}", chars),
            }
            sanitized_name = f"{codes['blind_image_code']}.png"
            source = resolve_path(row["raw_file_path"], acquisition_manifest)
            sanitized_tmp_path = analyst_tmp / "images" / sanitized_name
            image_record = sanitize_image(source, sanitized_tmp_path, config)
            if (
                image_record["image_width_px"] != int(row["image_width_px"])
                or image_record["image_height_px"] != int(row["image_height_px"])
                or image_record["bit_depth"] != int(row["bit_depth"])
            ):
                raise RuntimeError(f"fail-closed: decoded image dimensions/bit depth disagree with acquisition manifest: {source}")
            sanitized_hash = sha256(sanitized_tmp_path)
            restricted_rows.append(
                {
                    "blind_release_id": release_id,
                    "restricted_key_nonce_hex": key_nonce_hex,
                    **codes,
                    "source_batch_id": row["source_batch_id"],
                    "source_aliquot_id": row["source_aliquot_id"],
                    "source_image_id": row["source_image_id"],
                    "source_mount_id": row["source_mount_id"],
                    "source_field_id": row["source_field_id"],
                    "condition_id": row["condition_id"],
                    "condition_role": row["condition_role"],
                    "target_temperature_C": row["target_temperature_C"],
                    "challenge_arm": row["challenge_arm"],
                    "randomization_block": row["randomization_block"],
                    "source_raw_file_path": str(source),
                    "source_raw_sha256": row["raw_sha256"].lower(),
                    "calibration_file_path": str(resolve_path(row["calibration_file_path"], acquisition_manifest)),
                    "calibration_sha256": row["calibration_sha256"].lower(),
                    "pet_identity_record_path": str(resolve_path(row["pet_identity_record_path"], acquisition_manifest)),
                    "pet_identity_record_sha256": row["pet_identity_record_sha256"].lower(),
                    "psf_record_path": str(resolve_path(row["psf_record_path"], acquisition_manifest)),
                    "psf_record_sha256": row["psf_record_sha256"].lower(),
                    "sanitized_filename": sanitized_name,
                    "sanitized_raw_sha256": sanitized_hash,
                    "pixel_sha256": image_record["pixel_sha256"],
                    "source_metadata_present": image_record["source_metadata_present"],
                    "sanitized_metadata_text_sha256": image_record["sanitized_metadata_text_sha256"],
                }
            )
            final_sanitized_path = analyst_output / "images" / sanitized_name
            analyst_seed_rows.append(
                {
                    "blind_release_id": release_id,
                    "blind_key_manifest_sha256": "PENDING",
                    "analyst_batch_code": codes["blind_batch_code"],
                    "analyst_aliquot_code": codes["blind_aliquot_code"],
                    "aliquot_id": codes["blind_aliquot_code"],
                    "image_id": codes["blind_image_code"],
                    "mount_id": codes["blind_mount_code"],
                    "field_id": codes["blind_field_code"],
                    "field_selection_method": row["field_selection_method"],
                    "challenge_role": normalized_challenge_role(row["challenge_arm"]),
                    "raw_file_path": str(final_sanitized_path),
                    "raw_sha256": sanitized_hash,
                    "mask_file_path": "",
                    "mask_sha256": "",
                    "pixel_size_x_um": row["pixel_size_x_um"],
                    "pixel_size_y_um": row["pixel_size_y_um"],
                    "analysis_run_id": f"{release_id}_PRIMARY_V1",
                    "analysis_role": config["analyst_analysis_role"],
                    "canonical_run": True,
                    "segmentation_status": config["analyst_segmentation_status"],
                    "treatment_blinded": True,
                    "image_qc_status": row["image_qc_status"],
                    "calibration_valid": bool_value(row["calibration_valid"]),
                    "calibration_sha256": row["calibration_sha256"].lower(),
                    "pet_confirmed": bool_value(row["pet_confirmed"]),
                    "psf_fwhm_px": row["psf_fwhm_px"],
                    "flow_axis_deg": row["flow_axis_deg"],
                    "candidate_polarity": row["candidate_polarity"],
                    "pixel_sha256": image_record["pixel_sha256"],
                    "pixel_identity_pass": image_record["pixel_identity_pass"],
                }
            )

        for namespace in ("blind_batch_code", "blind_aliquot_code", "blind_image_code", "blind_mount_code", "blind_field_code"):
            values = [row[namespace] for row in restricted_rows]
            source_field = {
                "blind_batch_code": "source_batch_id", "blind_aliquot_code": "source_aliquot_id",
                "blind_image_code": "source_image_id", "blind_mount_code": "source_mount_id",
                "blind_field_code": "source_field_id",
            }[namespace]
            unique_sources = len(
                {(row["source_image_id"], row["source_field_id"]) for row in restricted_rows}
                if namespace == "blind_field_code" else {row[source_field] for row in restricted_rows}
            )
            if len(set(values)) != unique_sources:
                raise RuntimeError(f"fail-closed: blind-code collision or inconsistent mapping in {namespace}")

        restricted_columns = list(restricted_rows[0])
        key_path = restricted_tmp / "custodian_key.csv"
        write_csv(key_path, restricted_rows, restricted_columns)
        key_hash = sha256(key_path)
        for row in analyst_seed_rows:
            row["blind_key_manifest_sha256"] = key_hash
        analyst_columns = list(analyst_seed_rows[0])
        analyst_manifest_path = analyst_tmp / "blinded_image_manifest.csv"
        write_csv(analyst_manifest_path, analyst_seed_rows, analyst_columns)
        montage_path = analyst_tmp / "visual_leakage_montage.png"
        build_visual_montage(analyst_tmp / "images", analyst_seed_rows, montage_path)
        visual_review_rows = [
            {
                "blind_release_id": release_id, "image_id": row["image_id"],
                "reviewer_slot": slot, "reviewer_id": "", "review_status": "pending",
                "burned_label_absent": "", "burned_scale_bar_absent": "",
                "other_visual_leakage_absent": "", "findings": "", "review_utc": "",
            }
            for row in analyst_seed_rows for slot in (1, 2)
        ]
        visual_review_path = analyst_tmp / "visual_leakage_review_template.csv"
        write_csv(visual_review_path, visual_review_rows, list(visual_review_rows[0]))
        shutil.copy2(acquisition_manifest, restricted_tmp / "source_acquisition_manifest.csv")
        shutil.copy2(roles_path, restricted_tmp / "roles_and_key_custody.json")

        scan_fields = (
            "blind_release_id", "analyst_batch_code", "analyst_aliquot_code",
            "aliquot_id", "image_id", "mount_id", "field_id", "challenge_role",
            "raw_file_path", "analysis_run_id", "analysis_role", "segmentation_status",
        )
        analyst_text = "\n".join(str(row[field]).lower() for row in analyst_seed_rows for field in scan_fields)
        leaks = sorted(token for token in dynamic_forbidden if token and token in analyst_text)
        forbidden_headers = {
            "condition_id", "condition_role", "target_temperature_c", "challenge_arm",
            "randomization_block", "source_batch_id", "source_aliquot_id", "source_image_id",
        }
        if leaks or forbidden_headers.intersection(map(str.lower, analyst_columns)):
            raise RuntimeError(f"fail-closed: analyst release leaks treatment/source information: tokens={leaks}")
        leakage_scan = {
            "stage": "Stage33C-Q",
            "release_id": release_id,
            "created_utc": utc_now(),
            "status": "pass",
            "finding_n": 0,
            "findings": [],
            "dynamic_forbidden_token_n": len(dynamic_forbidden),
            "scanned_manifest_row_n": len(analyst_seed_rows),
            "scanned_manifest_fields": list(scan_fields),
            "scanned_image_metadata_n": len(analyst_seed_rows),
            "resolved_config_sha256": config_sha256,
            "visual_pixel_review": "pending_two_independent_release_officers",
        }
        leakage_scan_path = analyst_tmp / "leakage_scan.json"
        json_dump(leakage_scan_path, leakage_scan)

        restricted_manifest = {
            "stage": "Stage33C-Q", "release_id": release_id, "created_utc": utc_now(),
            "status": "restricted_custodian_record", "source_manifest_path": str(acquisition_manifest),
            "source_manifest_sha256": sha256(acquisition_manifest), "custodian_key_sha256": key_hash,
            "custodian_secret_sha256": sha256(secret_path), "code_method": "HMAC-SHA256",
            "restricted_key_nonce_sha256": sha256_bytes(bytes.fromhex(key_nonce_hex)),
            "roles_and_key_custody_sha256": roles_sha256,
            "resolved_config_sha256": config_sha256,
            "resolved_config_hash_basis": config_hash_basis,
            "release_builder_sha256": builder_sha256,
            "blind_code_hex_chars": chars, "row_n": len(restricted_rows),
            "claim_boundary": "key custody only; no treatment effect or degradation inference",
        }
        json_dump(restricted_tmp / "restricted_manifest.json", restricted_manifest)
        analyst_manifest = {
            "stage": "Stage33C-Q", "release_id": release_id, "created_utc": utc_now(),
            "status": "sanitized_blinded_analyst_package", "custodian_key_sha256": key_hash,
            "roles_and_key_custody_sha256": roles_sha256,
            "resolved_config_sha256": config_sha256,
            "resolved_config_hash_basis": config_hash_basis,
            "release_builder_sha256": builder_sha256,
            "blinded_image_manifest_sha256": sha256(analyst_manifest_path), "image_n": len(analyst_seed_rows),
            "pixel_identity_all_pass": all(bool(row["pixel_identity_pass"]) for row in analyst_seed_rows),
            "metadata_leak_scan": "pass", "leakage_scan_sha256": sha256(leakage_scan_path),
            "dynamic_forbidden_token_n": len(dynamic_forbidden),
            "visual_leakage_review": "pending_two_independent_reviewers",
            "visual_leakage_montage_sha256": sha256(montage_path),
            "visual_leakage_review_template_sha256": sha256(visual_review_path),
            "state": "SANITIZED_PENDING_VISUAL_REVIEW", "treatment_key_present": False,
            "claim_boundary": "acquisition/blinding artifact only; no empirical analysis or degradation inference",
        }
        json_dump(analyst_tmp / "analyst_manifest.json", analyst_manifest)
        analyst_package_hashes = {
            path.relative_to(analyst_tmp).as_posix(): sha256(path)
            for path in sorted(analyst_tmp.rglob("*")) if path.is_file()
        }
        package_hashes_path = analyst_tmp / "package_hashes.json"
        json_dump(package_hashes_path, analyst_package_hashes)
        cross_release_commitment = {
            "stage": "Stage33C-Q",
            "release_id": release_id,
            "created_utc": utc_now(),
            "state": "CUSTODIAN_COMMITTED_PENDING_VISUAL_REVIEW",
            "restricted_manifest_sha256": sha256(restricted_tmp / "restricted_manifest.json"),
            "custodian_key_sha256": key_hash,
            "roles_and_key_custody_sha256": roles_sha256,
            "resolved_config_sha256": config_sha256,
            "resolved_config_hash_basis": config_hash_basis,
            "release_builder_sha256": builder_sha256,
            "blinded_image_manifest_sha256": sha256(analyst_manifest_path),
            "analyst_manifest_sha256": sha256(analyst_tmp / "analyst_manifest.json"),
            "analyst_package_hashes_sha256": sha256(package_hashes_path),
            "treatment_key_present_in_analyst_package": False,
        }
        cross_commitment_path = restricted_tmp / "cross_release_commitment.json"
        json_dump(cross_commitment_path, cross_release_commitment)

        analyst_tmp.replace(analyst_output)
        restricted_tmp.replace(restricted_output)
    except Exception:
        for path in (restricted_tmp, analyst_tmp):
            if path.exists():
                shutil.rmtree(path)
        raise
    return {
        "stage": "Stage33C-Q", "release_id": release_id,
        "restricted_output": str(restricted_output), "analyst_output": str(analyst_output),
        "custodian_key_sha256": key_hash, "image_n": len(rows),
        "cross_release_commitment_sha256": sha256(restricted_output / "cross_release_commitment.json"),
        "status": "sanitized_pending_visual_review", "no_empirical_analysis": True, "no_simulation": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acquisition-manifest", type=Path, required=True)
    parser.add_argument("--secret-file", type=Path, required=True)
    parser.add_argument("--roles-file", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--restricted-output", type=Path, required=True)
    parser.add_argument("--analyst-output", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args(argv)
    result = build_release(
        args.acquisition_manifest.resolve(), args.secret_file.resolve(), args.roles_file.resolve(), args.release_id,
        args.restricted_output.resolve(), args.analyst_output.resolve(),
        args.config.resolve() if args.config else None,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
