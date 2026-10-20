#!/usr/bin/env python3
"""Fail-closed Stage33C-Q acquisition/qualification release auditor.

The auditor is read-only with respect to ``--design-dir`` and
``--verification-dir``.  Its only writes are ``audit.json`` and
``completion.json`` beneath a new or empty ``--output`` directory.  The output
must not be located inside either input tree.

Expected design schema (``resolved_design.json``)::

    {
      "stage": "Stage33C-Q",
      "release_id": "...",
      "status": "preflight_ready_no_empirical_data",
      "created_utc": "...",
      "source_bindings": [{"role": "...", "path": "...", "sha256": "..."}],
      "design_files": [{"role": "...", "path": "...", "sha256": "..."}],
      "verification": {
        "path": ".../verify_stage33cq_acquisition_and_masks_v1.py",
        "sha256": "...", "output_path": "...", "verification_sha256": "..."
      },
      "claim_boundary": "...", "stop_boundary": "..."
    }

The nine required ``source_bindings`` roles are fixed in ``REQUIRED_SOURCES``.
Every source/design binding and every verification ``hash_bindings`` entry is
resolved and re-hashed.  Synthetic verification must contain a passing release,
an exact identical-reviewer comparison, a deliberately perturbed comparison
that fails its pre-consensus gate, and passing fail-closed challenge records.
This is software/release qualification only; it does not validate empirical
PET morphology, degradation, treatment effects, or simulation physics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import numpy as np
    from PIL import Image
except Exception:  # recorded as a failed exact-pixel gate, not silently skipped
    np = None
    Image = None


STAGE = "Stage33C-Q"
DESIGN_STATUS = "preflight_ready_no_empirical_data"
AUDIT_SCHEMA = "pet.stage33cq-acquisition-qualification-release-audit.v1"
COMPLETION_SCHEMA = "pet.stage33cq-acquisition-qualification-release-audit-completion.v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "stage33_staging"
REQUIRED_SOURCES = {
    "stage33a_workbook": ROOT / "outputs" / "019f7799-ad23-7f90-bf22-04cd842ccd22"
    / "stage33a_pet_fragmentation_characterization_20260829" / "preflight_design_03"
    / "Stage33A_PET_Characterization_Preflight.xlsx",
    "stage33cm_pipeline": STAGING / "analyze_stage33c_blinded_morphology_v1.py",
    "stage33cm_verifier": STAGING / "verify_stage33cm_blinded_morphology_v1.py",
    "stage33cm_release_auditor": STAGING / "audit_stage33cm_blinded_morphology_release_v1.py",
    "stage33cq_release_builder": STAGING / "build_stage33cq_blinded_acquisition_release_v1.py",
    "stage33cq_visual_sealer": STAGING / "seal_stage33cq_analyst_release_v1.py",
    "stage33cq_mask_qualifier": STAGING / "qualify_stage33cq_independent_masks_v1.py",
    "stage33cq_synthetic_verifier": STAGING / "verify_stage33cq_acquisition_and_masks_v1.py",
    "stage33cq_release_auditor": Path(__file__).resolve(),
}
PRODUCTION_SCRIPT_ROLES = {
    "stage33cq_release_builder", "stage33cq_visual_sealer", "stage33cq_mask_qualifier",
    "stage33cq_synthetic_verifier",
}

FORBIDDEN_HEADERS = {
    "condition_id", "condition_role", "target_temperature_c", "temperature_c",
    "challenge_arm", "randomization_block", "source_batch_id", "source_aliquot_id",
    "source_image_id", "source_mount_id", "source_field_id", "source_raw_file_path",
    "source_raw_sha256", "treatment_id", "treatment_group", "treatment_temperature_c",
}
STATIC_FORBIDDEN_TOKENS = {
    "120c", "140c", "160c", "180c", "120 c", "140 c", "160 c", "180 c",
    "t120", "t140", "t160", "t180", "untreated", "as_received", "as-received",
    "heated_treatment", "process_control",
}
TEXT_SUFFIXES = {".csv", ".json", ".txt", ".md", ".yaml", ".yml", ".tsv"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def valid_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value.lower()))


def same_path(left: Path, right: Path) -> bool:
    return str(left.resolve()).casefold() == str(right.resolve()).casefold()


def contained(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_declared(value: Any, anchor: Path) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = anchor / candidate
    return candidate.resolve()


def json_dump(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_json(path: Path) -> tuple[Any, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def load_csv(path: Path) -> tuple[list[dict[str, str]], list[str], str | None]:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
            return rows, list(reader.fieldnames or []), None
    except Exception as exc:
        return [], [], f"{type(exc).__name__}: {exc}"


def tree_snapshot(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold())
        if path.is_file()
    }


def pixel_digest(array: Any, mode: str) -> str:
    little_dtype = array.dtype.newbyteorder("<")
    canonical = np.ascontiguousarray(array.astype(little_dtype, copy=False))
    header = json.dumps(
        {"dtype": canonical.dtype.str, "mode": mode, "shape": list(canonical.shape)},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(
        b"STAGE33CQ_PIXEL_V1\0" + header + b"\0" + canonical.tobytes(order="C")
    )


def image_pixels(path: Path) -> tuple[Any, str]:
    if Image is None or np is None:
        raise RuntimeError("Pillow and NumPy are required for exact decoded-pixel comparison")
    with Image.open(path) as image:
        if int(getattr(image, "n_frames", 1)) != 1:
            raise RuntimeError(f"multi-frame image is not auditable: {path}")
        array = np.asarray(image).copy()
        return array, image.mode


def image_metadata_digest(path: Path) -> str:
    if Image is None:
        raise RuntimeError("Pillow is required for image metadata hashing")
    with Image.open(path) as image:
        text = json.dumps(
            {"info": image.info, "exif": dict(image.getexif())},
            default=str, sort_keys=True,
        ).lower()
    return sha256_bytes(text.encode())


def bool_is(value: Any, expected: bool) -> bool:
    return value is expected


class Audit:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []

    def add(self, check_id: str, passed: bool, requirement: str, observed: Any = None) -> None:
        self.checks.append(
            {
                "check_id": check_id,
                "pass": bool(passed),
                "requirement": requirement,
                "observed": observed,
            }
        )

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(item["pass"] for item in self.checks)


def binding_check(
    audit: Audit,
    check_id: str,
    entry: Any,
    anchor: Path,
    expected_path: Path | None = None,
) -> tuple[Path | None, str | None]:
    requirement = "declared path must resolve to a regular file whose SHA-256 equals the binding"
    if not isinstance(entry, dict):
        audit.add(check_id, False, requirement, "binding is not an object")
        return None, None
    path = resolve_declared(entry.get("path"), anchor)
    declared = entry.get("sha256")
    failures: list[str] = []
    if path is None:
        failures.append("missing path")
    elif not path.is_file():
        failures.append(f"not a regular file: {path}")
    if not valid_sha(declared):
        failures.append("missing/invalid sha256")
    if path is not None and expected_path is not None and not same_path(path, expected_path):
        failures.append(f"path differs from authoritative path {expected_path.resolve()}")
    actual = None
    if path is not None and path.is_file():
        actual = sha256(path)
        if valid_sha(declared) and actual != str(declared).lower():
            failures.append(f"hash mismatch: declared={declared}, actual={actual}")
    audit.add(
        check_id, not failures, requirement,
        {"path": str(path) if path else None, "declared_sha256": declared,
         "actual_sha256": actual, "failures": failures},
    )
    return path, actual


def normalized_hash_bindings(value: Any) -> tuple[list[tuple[str, str]], list[str]]:
    entries: list[tuple[str, str]] = []
    errors: list[str] = []
    if isinstance(value, dict):
        for path, digest in value.items():
            entries.append((str(path), str(digest)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if not isinstance(item, dict) or "path" not in item or "sha256" not in item:
                errors.append(f"entry {index} is not a path/sha256 object")
                continue
            entries.append((str(item["path"]), str(item["sha256"])))
    else:
        errors.append("hash_bindings is neither an object nor a list")
    return entries, errors


def verify_hash_binding_list(
    audit: Audit, verification_dir: Path, value: Any
) -> tuple[set[str], dict[str, str]]:
    entries, failures = normalized_hash_bindings(value)
    resolved_hashes: set[str] = set()
    resolved_paths: dict[str, str] = {}
    seen: set[str] = set()
    for declared_path, declared_sha in entries:
        path = Path(declared_path)
        if path.is_absolute():
            failures.append(f"absolute evidence path is forbidden: {declared_path}")
            continue
        resolved = (verification_dir / path).resolve()
        if not contained(resolved, verification_dir):
            failures.append(f"evidence path escapes verification directory: {declared_path}")
            continue
        key = resolved.as_posix().casefold()
        if key in seen:
            failures.append(f"duplicate evidence path: {declared_path}")
            continue
        seen.add(key)
        if not valid_sha(declared_sha):
            failures.append(f"invalid SHA-256 for {declared_path}")
            continue
        if not resolved.is_file():
            failures.append(f"missing evidence file: {declared_path}")
            continue
        actual = sha256(resolved)
        if actual != declared_sha.lower():
            failures.append(f"hash mismatch for {declared_path}: {actual} != {declared_sha}")
            continue
        resolved_hashes.add(actual)
        resolved_paths[declared_path] = actual
    audit.add(
        "verification_hash_bindings",
        bool(entries) and not failures,
        "every listed verification input/output hash must be relative, contained, unique, present, and exact",
        {"entry_n": len(entries), "resolved_n": len(resolved_paths), "failures": failures},
    )
    return resolved_hashes, resolved_paths


def manifest_hashes_check(audit: Audit, pending_dir: Path) -> dict[str, str]:
    manifest_path = pending_dir / "package_hashes.json"
    value, error = load_json(manifest_path)
    failures: list[str] = []
    resolved: dict[str, str] = {}
    if error or not isinstance(value, dict):
        failures.append(error or "package_hashes.json is not an object")
    else:
        for relative, declared in value.items():
            path = (pending_dir / str(relative)).resolve()
            if Path(str(relative)).is_absolute() or not contained(path, pending_dir):
                failures.append(f"unsafe package path: {relative}")
            elif not valid_sha(declared) or not path.is_file():
                failures.append(f"invalid or missing package binding: {relative}")
            else:
                actual = sha256(path)
                if actual != str(declared).lower():
                    failures.append(f"package hash mismatch: {relative}")
                else:
                    resolved[str(relative)] = actual
        actual_files = {
            path.relative_to(pending_dir).as_posix()
            for path in pending_dir.rglob("*") if path.is_file()
        } - {"package_hashes.json"}
        missing_bindings = sorted(actual_files - set(map(str, value)))
        stale_bindings = sorted(set(map(str, value)) - actual_files)
        if missing_bindings:
            failures.append(f"unbound package files: {missing_bindings}")
        if stale_bindings:
            failures.append(f"stale package bindings: {stale_bindings}")
    audit.add(
        "pending_analyst_package_hashes", not failures,
        "package_hashes.json must exactly bind every pending analyst package file except itself",
        {"resolved_n": len(resolved), "failures": failures},
    )
    return resolved


def validate_named_links(
    audit: Audit, check_id: str, links: list[tuple[str, Any, Path | None]]
) -> None:
    failures: list[str] = []
    observations: list[dict[str, Any]] = []
    for name, declared, path in links:
        actual = sha256(path) if path is not None and path.is_file() else None
        good = valid_sha(declared) and actual == str(declared).lower()
        if not good:
            failures.append(name)
        observations.append(
            {"name": name, "path": str(path) if path else None,
             "declared_sha256": declared, "actual_sha256": actual, "pass": good}
        )
    audit.add(
        check_id, not failures,
        "each named artifact hash must resolve to and match its intended file",
        {"links": observations, "failed_names": failures},
    )


def evidence_and_pixel_checks(
    audit: Audit, restricted_dir: Path, pending_dir: Path
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    key_path = restricted_dir / "custodian_key.csv"
    blinded_path = pending_dir / "blinded_image_manifest.csv"
    key_rows, key_headers, key_error = load_csv(key_path)
    blinded_rows, blinded_headers, blinded_error = load_csv(blinded_path)
    evidence_failures: list[str] = []
    evidence_pairs = [
        ("source_raw_file_path", "source_raw_sha256", True),
        ("calibration_file_path", "calibration_sha256", False),
        ("pet_identity_record_path", "pet_identity_record_sha256", False),
        ("psf_record_path", "psf_record_sha256", False),
    ]
    optional_presence: dict[str, bool] = {}
    if key_error or not key_rows:
        evidence_failures.append(key_error or "custodian key has no rows")
    for path_field, hash_field, required in evidence_pairs:
        pair_present = path_field in key_headers or hash_field in key_headers
        optional_presence[path_field] = pair_present
        if required and not ({path_field, hash_field} <= set(key_headers)):
            evidence_failures.append(f"missing required columns {path_field}/{hash_field}")
            continue
        if pair_present and not ({path_field, hash_field} <= set(key_headers)):
            evidence_failures.append(f"incomplete optional binding columns {path_field}/{hash_field}")
            continue
        if not pair_present:
            continue
        for row_index, row in enumerate(key_rows, start=2):
            path = resolve_declared(row.get(path_field), key_path.parent)
            declared = row.get(hash_field, "")
            if path is None or not path.is_file() or not valid_sha(declared):
                evidence_failures.append(f"row {row_index} invalid {path_field}/{hash_field}")
            elif sha256(path) != declared.lower():
                evidence_failures.append(f"row {row_index} hash mismatch for {path_field}")
    audit.add(
        "restricted_evidence_bindings", not evidence_failures,
        "all source bindings and every present calibration/PET-identity/PSF binding must resolve exactly",
        {"row_n": len(key_rows), "binding_columns_present": optional_presence,
         "failures": evidence_failures},
    )

    pixel_failures: list[str] = []
    if blinded_error or not blinded_rows:
        pixel_failures.append(blinded_error or "blinded manifest has no rows")
    if Image is None or np is None:
        pixel_failures.append("Pillow/NumPy unavailable")
    blinded_by_id: dict[str, list[dict[str, str]]] = {}
    for row in blinded_rows:
        blinded_by_id.setdefault(row.get("image_id", ""), []).append(row)
    if len(blinded_by_id) != len(blinded_rows):
        pixel_failures.append("blinded image IDs are not unique")
    if len({row.get("blind_image_code", "") for row in key_rows}) != len(key_rows):
        pixel_failures.append("restricted blind image codes are not unique")
    matched = 0
    custodian_key_actual = sha256(key_path) if key_path.is_file() else None
    for row_index, key_row in enumerate(key_rows, start=2):
        image_id = key_row.get("blind_image_code", "")
        matches = blinded_by_id.get(image_id, [])
        if len(matches) != 1:
            pixel_failures.append(f"row {row_index} maps to {len(matches)} analyst rows")
            continue
        analyst_row = matches[0]
        source = resolve_declared(key_row.get("source_raw_file_path"), key_path.parent)
        sanitized = resolve_declared(analyst_row.get("raw_file_path"), blinded_path.parent)
        expected_sanitized = pending_dir / "images" / key_row.get("sanitized_filename", "")
        if sanitized is None or not same_path(sanitized, expected_sanitized):
            pixel_failures.append(f"row {row_index} sanitized path/filename binding mismatch")
            continue
        if source is None or not source.is_file() or not sanitized.is_file():
            pixel_failures.append(f"row {row_index} source or sanitized image missing")
            continue
        sanitized_hash = sha256(sanitized)
        if sanitized_hash != key_row.get("sanitized_raw_sha256", "").lower():
            pixel_failures.append(f"row {row_index} restricted sanitized file hash mismatch")
        if sanitized_hash != analyst_row.get("raw_sha256", "").lower():
            pixel_failures.append(f"row {row_index} analyst sanitized file hash mismatch")
        if analyst_row.get("blind_key_manifest_sha256", "").lower() != custodian_key_actual:
            pixel_failures.append(f"row {row_index} analyst blind-key hash binding mismatch")
        try:
            source_pixels, source_mode = image_pixels(source)
            sanitized_pixels, sanitized_mode = image_pixels(sanitized)
            source_digest = pixel_digest(source_pixels, source_mode)
            sanitized_digest = pixel_digest(sanitized_pixels, sanitized_mode)
            expected_digest = key_row.get("pixel_sha256", "").lower()
            exact = (
                source_mode == sanitized_mode
                and source_pixels.dtype == sanitized_pixels.dtype
                and source_pixels.shape == sanitized_pixels.shape
                and bool(np.array_equal(source_pixels, sanitized_pixels))
                and source_digest == sanitized_digest == expected_digest
                and analyst_row.get("pixel_sha256", "").lower() == expected_digest
                and str(analyst_row.get("pixel_identity_pass", "")).strip().lower() in {"true", "1", "yes"}
                and image_metadata_digest(sanitized)
                == key_row.get("sanitized_metadata_text_sha256", "").lower()
            )
            if not exact:
                pixel_failures.append(f"row {row_index} decoded pixels/digests are not identical")
            else:
                matched += 1
        except Exception as exc:
            pixel_failures.append(f"row {row_index} pixel comparison failed: {type(exc).__name__}: {exc}")
    audit.add(
        "independent_exact_pixel_identity", bool(key_rows) and not pixel_failures,
        "every restricted source image and released sanitized image must be exactly identical in decoded pixels",
        {"restricted_row_n": len(key_rows), "analyst_row_n": len(blinded_rows),
         "exact_match_n": matched, "failures": pixel_failures},
    )
    return key_rows, blinded_rows


def source_manifest_and_nonce_checks(
    audit: Audit,
    restricted_dir: Path,
    restricted_manifest: dict[str, Any],
    key_rows: list[dict[str, str]],
) -> None:
    source_manifest_path = resolve_declared(
        restricted_manifest.get("source_manifest_path"), restricted_dir
    )
    source_rows: list[dict[str, str]] = []
    source_error: str | None = "source manifest path is missing"
    if source_manifest_path is not None:
        source_rows, _, source_error = load_csv(source_manifest_path)
    failures: list[str] = []
    if source_error or not source_rows:
        failures.append(source_error or "source manifest has no rows")
    source_by_key: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in source_rows:
        key = (row.get("source_image_id", ""), row.get("source_field_id", ""))
        source_by_key.setdefault(key, []).append(row)
    if len(source_by_key) != len(source_rows):
        failures.append("source manifest image/field keys are not unique")
    key_keys = [(row.get("source_image_id", ""), row.get("source_field_id", "")) for row in key_rows]
    if len(set(key_keys)) != len(key_keys):
        failures.append("custodian-key image/field keys are not unique")
    direct_fields = (
        "source_batch_id", "source_aliquot_id", "source_image_id", "source_mount_id",
        "source_field_id", "condition_id", "condition_role", "target_temperature_C",
        "challenge_arm", "randomization_block",
    )
    path_hash_fields = (
        ("raw_file_path", "raw_sha256", "source_raw_file_path", "source_raw_sha256"),
        ("calibration_file_path", "calibration_sha256", "calibration_file_path", "calibration_sha256"),
        ("pet_identity_record_path", "pet_identity_record_sha256", "pet_identity_record_path", "pet_identity_record_sha256"),
        ("psf_record_path", "psf_record_sha256", "psf_record_path", "psf_record_sha256"),
    )
    matched = 0
    for row_index, key_row in enumerate(key_rows, start=2):
        key = (key_row.get("source_image_id", ""), key_row.get("source_field_id", ""))
        matches = source_by_key.get(key, [])
        if len(matches) != 1:
            failures.append(f"custodian row {row_index} resolves to {len(matches)} source rows")
            continue
        source_row = matches[0]
        row_failed = False
        for field in direct_fields:
            if source_row.get(field) != key_row.get(field):
                failures.append(f"custodian row {row_index} differs from source manifest field {field}")
                row_failed = True
        for source_path_field, source_hash_field, key_path_field, key_hash_field in path_hash_fields:
            source_bound_path = resolve_declared(source_row.get(source_path_field), source_manifest_path.parent)
            key_bound_path = resolve_declared(key_row.get(key_path_field), restricted_dir)
            if source_bound_path is None or key_bound_path is None or not same_path(source_bound_path, key_bound_path):
                failures.append(f"custodian row {row_index} path lineage mismatch for {key_path_field}")
                row_failed = True
            if source_row.get(source_hash_field, "").lower() != key_row.get(key_hash_field, "").lower():
                failures.append(f"custodian row {row_index} hash lineage mismatch for {key_hash_field}")
                row_failed = True
        if not row_failed:
            matched += 1
    if len(source_rows) != len(key_rows):
        failures.append(f"row count differs: source={len(source_rows)}, custodian={len(key_rows)}")
    audit.add(
        "source_manifest_to_custodian_key_row_lineage", bool(key_rows) and not failures,
        "every custodian-key source/treatment/evidence row must exactly reproduce the hash-bound acquisition-manifest row",
        {"source_manifest_path": str(source_manifest_path) if source_manifest_path else None,
         "source_row_n": len(source_rows), "custodian_row_n": len(key_rows),
         "matched_row_n": matched, "failures": failures},
    )

    nonce_failures: list[str] = []
    nonce_values = {
        str(row.get("restricted_key_nonce_hex", "")) for row in key_rows
        if isinstance(row.get("restricted_key_nonce_hex"), str)
    }
    actual_nonce_sha = None
    if len(nonce_values) != 1:
        nonce_failures.append(f"expected one shared restricted nonce, observed {len(nonce_values)}")
    else:
        nonce = next(iter(nonce_values))
        try:
            if len(nonce) != 64:
                raise ValueError("nonce must contain exactly 32 bytes")
            actual_nonce_sha = sha256_bytes(bytes.fromhex(nonce))
        except Exception as exc:
            nonce_failures.append(f"invalid nonce encoding: {exc}")
    declared_nonce_sha = restricted_manifest.get("restricted_key_nonce_sha256")
    if not valid_sha(declared_nonce_sha) or actual_nonce_sha != str(declared_nonce_sha).lower():
        nonce_failures.append("restricted_key_nonce_sha256 does not bind the custodian-key nonce")
    audit.add(
        "restricted_key_nonce_commitment", bool(key_rows) and not nonce_failures,
        "all custodian-key rows must share one 32-byte nonce whose digest matches restricted_manifest",
        {"declared_sha256": declared_nonce_sha, "actual_sha256": actual_nonce_sha,
         "failures": nonce_failures},
    )


def dynamic_forbidden_tokens(key_rows: list[dict[str, str]]) -> set[str]:
    tokens = set(STATIC_FORBIDDEN_TOKENS)
    fields = (
        "source_batch_id", "source_aliquot_id", "source_image_id", "source_mount_id",
        "source_field_id", "condition_id", "condition_role", "challenge_arm",
        "randomization_block",
    )
    for row in key_rows:
        for field in fields:
            token = str(row.get(field, "")).strip().casefold()
            if len(token) >= 5:
                tokens.add(token)
        source_value = str(row.get("source_raw_file_path", "")).strip()
        if source_value:
            source = Path(source_value)
            for part in (source.stem, source.parent.name):
                token = part.strip().casefold()
                if len(token) >= 5:
                    tokens.add(token)
    return tokens


def json_forbidden_keys(value: Any, location: str = "$") -> list[str]:
    leaks: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).strip().casefold() in FORBIDDEN_HEADERS:
                leaks.append(f"{location}.{key}")
            leaks.extend(json_forbidden_keys(child, f"{location}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            leaks.extend(json_forbidden_keys(child, f"{location}[{index}]"))
    return leaks


def scan_analyst_packages(
    audit: Audit, package_dirs: list[Path], key_rows: list[dict[str, str]]
) -> None:
    tokens = dynamic_forbidden_tokens(key_rows)
    header_leaks: list[str] = []
    token_leaks: list[str] = []
    forbidden_file_leaks: list[str] = []
    forbidden_names = {
        "custodian_key.csv", "source_acquisition_manifest.csv", "restricted_manifest.json",
        "roles_and_key_custody.json", "treatment_key.csv", "treatment_key.json",
    }
    scanned_n = 0
    scanned_image_n = 0
    image_suffixes = {".png", ".tif", ".tiff", ".jpg", ".jpeg", ".bmp"}
    for package_dir in package_dirs:
        if not package_dir.is_dir():
            forbidden_file_leaks.append(f"missing analyst package directory: {package_dir}")
            continue
        for path in sorted(package_dir.rglob("*"), key=lambda item: item.as_posix().casefold()):
            if not path.is_file():
                continue
            relative = path.relative_to(package_dir).as_posix()
            lowered_relative = relative.casefold()
            if path.name.casefold() in forbidden_names:
                forbidden_file_leaks.append(str(path))
            for token in tokens:
                if token and token in lowered_relative:
                    token_leaks.append(f"path:{relative}:{token}")
            if path.suffix.casefold() in image_suffixes:
                scanned_image_n += 1
                try:
                    raw_lower = path.read_bytes().lower()
                    if Image is None:
                        raise RuntimeError("Pillow unavailable")
                    with Image.open(path) as image:
                        metadata_text = json.dumps(
                            {"info": image.info, "exif": dict(image.getexif())},
                            default=str, sort_keys=True,
                        ).casefold()
                    for token in tokens | FORBIDDEN_HEADERS:
                        if not token:
                            continue
                        if token in metadata_text:
                            token_leaks.append(f"image-metadata:{relative}:{token}")
                        encoded = token.encode("utf-8", errors="ignore").lower()
                        if encoded and encoded in raw_lower:
                            token_leaks.append(f"image-binary:{relative}:{token}")
                except Exception as exc:
                    forbidden_file_leaks.append(f"image metadata scan failed {path}: {exc}")
            if path.suffix.casefold() not in TEXT_SUFFIXES:
                continue
            scanned_n += 1
            try:
                text = path.read_text(encoding="utf-8-sig", errors="strict")
            except Exception as exc:
                forbidden_file_leaks.append(f"unreadable text artifact {path}: {exc}")
                continue
            lowered = text.casefold()
            for token in tokens:
                if token and token in lowered:
                    token_leaks.append(f"content:{relative}:{token}")
            if path.suffix.casefold() in {".csv", ".tsv"}:
                delimiter = "\t" if path.suffix.casefold() == ".tsv" else ","
                try:
                    with path.open("r", newline="", encoding="utf-8-sig") as stream:
                        reader = csv.reader(stream, delimiter=delimiter)
                        headers = next(reader, [])
                    for header in headers:
                        if header.strip().casefold() in FORBIDDEN_HEADERS:
                            header_leaks.append(f"{relative}:{header}")
                except Exception as exc:
                    forbidden_file_leaks.append(f"CSV scan failed {path}: {exc}")
            elif path.suffix.casefold() == ".json":
                value, error = load_json(path)
                if error:
                    forbidden_file_leaks.append(f"JSON scan failed {path}: {error}")
                else:
                    header_leaks.extend(f"{relative}:{item}" for item in json_forbidden_keys(value))
    token_leaks = sorted(set(token_leaks))
    header_leaks = sorted(set(header_leaks))
    forbidden_file_leaks = sorted(set(forbidden_file_leaks))
    audit.add(
        "analyst_package_forbidden_information_scan",
        not (header_leaks or token_leaks or forbidden_file_leaks),
        "pending and sealed analyst packages must contain no source/treatment headers, tokens, or restricted key artifacts",
        {"text_file_n": scanned_n, "image_file_n": scanned_image_n,
         "dynamic_token_n": len(tokens),
         "header_leaks": header_leaks, "token_leaks": token_leaks,
         "forbidden_or_unreadable_files": forbidden_file_leaks},
    )


def qualifier_hash_links(
    audit: Audit, label: str, directory: Path, blinded_manifest: Path, roles_path: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    summary_path = directory / "preconsensus_agreement_summary.json"
    freeze_path = directory / "preconsensus_freeze_manifest.json"
    completion_path = directory / "completion.json"
    summary, summary_error = load_json(summary_path)
    freeze, freeze_error = load_json(freeze_path)
    completion, completion_error = load_json(completion_path)
    parse_failures = [item for item in (summary_error, freeze_error, completion_error) if item]
    audit.add(
        f"{label}_qualification_records_parse", not parse_failures,
        "summary, freeze manifest, and completion records must all be readable JSON",
        parse_failures,
    )
    summary = summary if isinstance(summary, dict) else {}
    freeze = freeze if isinstance(freeze, dict) else {}
    completion = completion if isinstance(completion, dict) else {}
    validate_named_links(
        audit, f"{label}_qualification_artifact_hashes",
        [
            ("blinded_manifest_sha256", freeze.get("blinded_manifest_sha256"), blinded_manifest),
            ("roles_and_key_custody_sha256", freeze.get("roles_and_key_custody_sha256"), roles_path),
            ("mask_qualifier_sha256", freeze.get("mask_qualifier_sha256"), REQUIRED_SOURCES["stage33cq_mask_qualifier"]),
            ("stage33cm_geometry_helper_sha256", freeze.get("stage33cm_geometry_helper_sha256"), REQUIRED_SOURCES["stage33cm_pipeline"]),
            ("preconsensus_matches_sha256", freeze.get("preconsensus_matches_sha256"), directory / "preconsensus_matches.csv"),
            ("reviewer_instances_sha256", freeze.get("reviewer_instances_sha256"), directory / "reviewer_instances.csv"),
            ("discrepancy_queue_sha256", freeze.get("discrepancy_queue_sha256"), directory / "discrepancy_queue.csv"),
            ("summary_sha256", freeze.get("summary_sha256"), summary_path),
            ("freeze_manifest_sha256", completion.get("freeze_manifest_sha256"), freeze_path),
        ],
    )
    submission_root = directory.parent / f"{label}_inputs"
    submission_candidates = sorted(
        submission_root.rglob("submissions.csv"), key=lambda item: item.as_posix().casefold()
    ) if submission_root.is_dir() else []
    submission_hashes = {
        path: sha256(path) for path in submission_candidates if path.is_file()
    }
    submission_failures: list[str] = []
    matched_submission_paths: list[str] = []
    for field in ("submission_A_sha256", "submission_B_sha256"):
        declared = freeze.get(field)
        matches = [path for path, digest in submission_hashes.items()
                   if valid_sha(declared) and digest == str(declared).lower()]
        if len(matches) != 1:
            submission_failures.append(f"{field} resolved to {len(matches)} files")
        else:
            matched_submission_paths.append(str(matches[0]))
    if len(submission_candidates) != 2:
        submission_failures.append(f"expected exactly two submissions.csv inputs, found {len(submission_candidates)}")
    if len(set(matched_submission_paths)) != len(matched_submission_paths):
        submission_failures.append("submission A and B hashes resolve to the same file")
    audit.add(
        f"{label}_reviewer_submission_hashes", not submission_failures,
        "submission_A_sha256 and submission_B_sha256 must each resolve uniquely to the two frozen reviewer submission files",
        {"candidate_paths": [str(path) for path in submission_candidates],
         "matched_paths": matched_submission_paths, "failures": submission_failures},
    )
    evidence_failures: list[str] = []
    reviewer_evidence = freeze.get("reviewer_evidence")
    if not isinstance(reviewer_evidence, list) or not reviewer_evidence:
        evidence_failures.append("reviewer_evidence is missing or empty")
    else:
        for index, item in enumerate(reviewer_evidence):
            if not isinstance(item, dict):
                evidence_failures.append(f"reviewer evidence {index} is not an object")
                continue
            for path_field, hash_field in (
                ("instance_mask_path", "instance_mask_sha256"),
                ("annotation_path", "annotation_sha256"),
            ):
                path = resolve_declared(item.get(path_field), freeze_path.parent)
                declared = item.get(hash_field)
                if path is None or not path.is_file() or not valid_sha(declared):
                    evidence_failures.append(f"reviewer evidence {index} invalid {path_field}/{hash_field}")
                elif sha256(path) != str(declared).lower():
                    evidence_failures.append(f"reviewer evidence {index} hash mismatch: {path_field}")
    audit.add(
        f"{label}_reviewer_evidence_hashes", not evidence_failures,
        "every reviewer mask and annotation evidence binding must resolve exactly",
        {"evidence_n": len(reviewer_evidence) if isinstance(reviewer_evidence, list) else 0,
         "failures": evidence_failures},
    )
    return summary, completion


def perform_audit(design_dir: Path, verification_dir: Path, output: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    audit = Audit()
    started_utc = utc_now()
    design_snapshot_before = tree_snapshot(design_dir)
    verification_snapshot_before = tree_snapshot(verification_dir)

    design_path = design_dir / "resolved_design.json"
    verification_path = verification_dir / "verification.json"
    verification_completion_path = verification_dir / "completion.json"
    design, design_error = load_json(design_path)
    verification, verification_error = load_json(verification_path)
    verification_completion, completion_error = load_json(verification_completion_path)
    audit.add("resolved_design_parse", design_error is None and isinstance(design, dict),
              "resolved_design.json must be readable JSON object", design_error)
    audit.add("synthetic_verification_parse", verification_error is None and isinstance(verification, dict),
              "verification.json must be readable JSON object", verification_error)
    audit.add("synthetic_completion_parse", completion_error is None and isinstance(verification_completion, dict),
              "verification completion.json must be readable JSON object", completion_error)
    design = design if isinstance(design, dict) else {}
    verification = verification if isinstance(verification, dict) else {}
    verification_completion = verification_completion if isinstance(verification_completion, dict) else {}

    audit.add("design_stage", design.get("stage") == STAGE, f"design stage must equal {STAGE}", design.get("stage"))
    audit.add("design_status", design.get("status") == DESIGN_STATUS,
              f"design status must equal {DESIGN_STATUS}", design.get("status"))
    release_id = design.get("release_id")
    audit.add("design_release_id", isinstance(release_id, str) and bool(release_id.strip()),
              "design release_id must be non-empty", release_id)
    audit.add("design_boundaries", all(isinstance(design.get(key), str) and design[key].strip()
                                       for key in ("claim_boundary", "stop_boundary")),
              "claim_boundary and stop_boundary must both be explicit non-empty text",
              {key: design.get(key) for key in ("claim_boundary", "stop_boundary")})

    source_bindings = design.get("source_bindings")
    source_bindings = source_bindings if isinstance(source_bindings, list) else []
    roles = [item.get("role") for item in source_bindings if isinstance(item, dict)]
    source_roles_are_strings = all(isinstance(role, str) and role.strip() for role in roles)
    string_roles = [role for role in roles if isinstance(role, str)]
    audit.add(
        "source_binding_roles_exact",
        len(roles) == len(source_bindings) == len(REQUIRED_SOURCES)
        and source_roles_are_strings
        and len(set(string_roles)) == len(string_roles)
        and set(string_roles) == set(REQUIRED_SOURCES),
        "source_bindings roles must be exactly the nine authoritative Stage33A/Stage33C-M/Stage33C-Q roles",
        {"observed": roles, "required": sorted(REQUIRED_SOURCES)},
    )
    source_by_role = {
        item.get("role"): item for item in source_bindings
        if isinstance(item, dict) and isinstance(item.get("role"), str)
    }
    source_hashes: dict[str, str | None] = {}
    for role, expected in REQUIRED_SOURCES.items():
        _, actual = binding_check(
            audit, f"source_binding_{role}", source_by_role.get(role), design_dir, expected
        )
        source_hashes[role] = actual

    design_files = design.get("design_files")
    design_files = design_files if isinstance(design_files, list) else []
    design_roles = [item.get("role") for item in design_files if isinstance(item, dict)]
    design_roles_are_strings = all(isinstance(role, str) and role.strip() for role in design_roles)
    string_design_roles = [role for role in design_roles if isinstance(role, str)]
    audit.add(
        "design_file_roles",
        bool(design_files) and len(design_roles) == len(design_files)
        and design_roles_are_strings
        and len(string_design_roles) == len(set(string_design_roles)),
        "design_files must be non-empty and use unique non-empty roles",
        design_roles,
    )
    design_file_hashes: set[str] = set()
    for index, entry in enumerate(design_files):
        role = entry.get("role") if isinstance(entry, dict) else f"index_{index}"
        _, actual = binding_check(audit, f"design_file_{role}", entry, design_dir)
        if actual:
            design_file_hashes.add(actual)

    verification_design = design.get("verification")
    verification_design = verification_design if isinstance(verification_design, dict) else {}
    _, verifier_actual = binding_check(
        audit, "design_verification_script", verification_design, design_dir,
        REQUIRED_SOURCES["stage33cq_synthetic_verifier"],
    )
    audit.add(
        "design_verifier_binding_consistency",
        verifier_actual is not None and verifier_actual == source_hashes.get("stage33cq_synthetic_verifier"),
        "verification.path/sha256 must duplicate the authoritative synthetic-verifier source binding exactly",
        {"verification_sha256": verifier_actual,
         "source_binding_sha256": source_hashes.get("stage33cq_synthetic_verifier")},
    )
    declared_verification_output = resolve_declared(verification_design.get("output_path"), design_dir)
    audit.add(
        "design_verification_output_binding",
        declared_verification_output is not None and same_path(declared_verification_output, verification_dir),
        "design verification.output_path must equal the supplied verification directory",
        {"declared": str(declared_verification_output) if declared_verification_output else None,
         "supplied": str(verification_dir)},
    )
    actual_verification_sha = sha256(verification_path) if verification_path.is_file() else None
    audit.add(
        "design_verification_record_hash",
        valid_sha(verification_design.get("verification_sha256"))
        and actual_verification_sha == str(verification_design.get("verification_sha256")).lower(),
        "design verification.verification_sha256 must bind verification.json",
        {"declared": verification_design.get("verification_sha256"), "actual": actual_verification_sha},
    )

    resolved_verification_hashes, resolved_verification_paths = verify_hash_binding_list(
        audit, verification_dir, verification.get("hash_bindings")
    )
    production = verification.get("production_scripts_sha256")
    production = production if isinstance(production, dict) else {}
    production_failures: list[str] = []
    for role in sorted(PRODUCTION_SCRIPT_ROLES):
        filename = REQUIRED_SOURCES[role].name
        if production.get(filename) != source_hashes.get(role):
            production_failures.append(filename)
    audit.add(
        "verification_production_script_hashes", not production_failures,
        "verification production_scripts_sha256 must bind the builder, sealer, qualifier, and synthetic verifier",
        {"mapping": production, "failed_or_missing": production_failures},
    )

    fixture = verification.get("test_only_fixture")
    fixture = fixture if isinstance(fixture, dict) else {}
    fixture_hashes_resolve = all(
        valid_sha(fixture.get(key)) and str(fixture.get(key)).lower() in resolved_verification_hashes
        for key in ("source_manifest_sha256", "roles_sha256")
    )
    audit.add(
        "test_only_fixture_boundary",
        bool_is(fixture.get("test_only"), True)
        and bool_is(fixture.get("no_empirical_data"), True)
        and bool_is(fixture.get("no_real_key"), True)
        and isinstance(fixture.get("image_n"), int) and fixture.get("image_n", 0) > 0
        and isinstance(fixture.get("secret_label"), str) and "test" in fixture["secret_label"].casefold()
        and fixture_hashes_resolve,
        "fixture must be explicitly test-only/no-empirical, non-empty, and hash-bind its manifest and roles",
        fixture,
    )
    fixture_evidence = fixture.get("evidence_records_sha256")
    fixture_evidence = fixture_evidence if isinstance(fixture_evidence, dict) else {}
    fixture_evidence_failures: list[str] = []
    for filename, declared in fixture_evidence.items():
        if Path(str(filename)).name != str(filename):
            fixture_evidence_failures.append(f"unsafe evidence filename: {filename}")
            continue
        evidence_path = verification_dir / "inputs" / "synthetic_evidence" / str(filename)
        if not evidence_path.is_file() or not valid_sha(declared):
            fixture_evidence_failures.append(f"missing or invalid evidence binding: {filename}")
        elif sha256(evidence_path) != str(declared).lower():
            fixture_evidence_failures.append(f"evidence hash mismatch: {filename}")
    fixture_secret_path = verification_dir / "inputs" / "TEST_ONLY_fixed_secret.bin"
    if (
        not fixture_secret_path.is_file()
        or not valid_sha(fixture.get("secret_sha256"))
        or sha256(fixture_secret_path) != str(fixture.get("secret_sha256", "")).lower()
    ):
        fixture_evidence_failures.append("fixed synthetic secret hash does not resolve")
    audit.add(
        "test_only_fixture_evidence_hashes",
        bool(fixture_evidence) and not fixture_evidence_failures,
        "all listed calibration/PET-identity/PSF fixture records and the fixed test secret must resolve exactly",
        {"evidence_record_n": len(fixture_evidence), "failures": fixture_evidence_failures},
    )
    completion_status = str(verification_completion.get("status", "")).casefold()
    audit.add(
        "synthetic_verification_status",
        verification.get("stage") == STAGE and bool_is(verification.get("overall_pass"), True)
        and verification_completion.get("stage") == STAGE
        and completion_status in {"complete", "pass", "passed"}
        and bool_is(verification_completion.get("overall_pass"), True)
        and bool_is(verification_completion.get("no_empirical_data"), True)
        and bool_is(verification_completion.get("no_real_secret"), True)
        and bool_is(verification_completion.get("no_treatment_reveal"), True)
        and bool_is(verification_completion.get("no_simulation"), True),
        "synthetic verification and completion must pass while declaring no empirical data, real secret, reveal, or simulation",
        {"verification_stage": verification.get("stage"), "overall_pass": verification.get("overall_pass"),
         "completion": verification_completion},
    )
    audit.add(
        "synthetic_completion_verification_hash",
        valid_sha(verification_completion.get("verification_sha256"))
        and actual_verification_sha == str(verification_completion.get("verification_sha256")).lower(),
        "verification completion must hash-bind verification.json",
        {"declared": verification_completion.get("verification_sha256"), "actual": actual_verification_sha},
    )
    challenges = verification.get("fail_closed_challenges")
    challenges = challenges if isinstance(challenges, dict) else {}
    bad_challenges = [
        name for name, record in challenges.items()
        if not isinstance(record, dict)
        or not bool_is(record.get("expected_failure"), True)
        or not bool_is(record.get("observed_failure"), True)
        or not bool_is(record.get("passed"), True)
        or not bool_is(record.get("runtime_error"), True)
        or not bool_is(record.get("message_match"), True)
        or record.get("unexpected_completion_artifacts") != []
        or not isinstance(record.get("exception_type"), str) or not record.get("exception_type")
        or not isinstance(record.get("message"), str) or not record.get("message")
        or not isinstance(record.get("expected_message_fragment"), str)
        or not record.get("expected_message_fragment")
    ]
    audit.add(
        "declared_fail_closed_challenge_gates", bool(challenges) and not bad_challenges,
        "every declared challenge must expect and observe failure, capture exception evidence, and pass",
        {"challenge_n": len(challenges), "failed": bad_challenges, "records": challenges},
    )

    restricted_dir = verification_dir / "successful_release" / "restricted"
    pending_dir = verification_dir / "successful_release" / "pending_analyst"
    sealed_dir = verification_dir / "successful_release" / "sealed_analyst"
    release_declaration_path = sealed_dir / "release_declaration.json"
    sealed_completion_path = sealed_dir / "completion.json"
    analyst_manifest_path = pending_dir / "analyst_manifest.json"
    blinded_manifest_path = pending_dir / "blinded_image_manifest.csv"
    leakage_scan_path = pending_dir / "leakage_scan.json"
    restricted_manifest_path = restricted_dir / "restricted_manifest.json"
    cross_commitment_path = restricted_dir / "cross_release_commitment.json"
    roles_path = restricted_dir / "roles_and_key_custody.json"
    key_path = restricted_dir / "custodian_key.csv"
    release_declaration, release_error = load_json(release_declaration_path)
    sealed_completion, sealed_error = load_json(sealed_completion_path)
    analyst_manifest, analyst_error = load_json(analyst_manifest_path)
    leakage_scan, leakage_error = load_json(leakage_scan_path)
    restricted_manifest, restricted_error = load_json(restricted_manifest_path)
    cross_commitment, commitment_error = load_json(cross_commitment_path)
    release_declaration = release_declaration if isinstance(release_declaration, dict) else {}
    sealed_completion = sealed_completion if isinstance(sealed_completion, dict) else {}
    analyst_manifest = analyst_manifest if isinstance(analyst_manifest, dict) else {}
    leakage_scan = leakage_scan if isinstance(leakage_scan, dict) else {}
    restricted_manifest = restricted_manifest if isinstance(restricted_manifest, dict) else {}
    cross_commitment = cross_commitment if isinstance(cross_commitment, dict) else {}
    package_parse_errors = [
        error for error in (
            release_error, sealed_error, analyst_error, leakage_error, restricted_error,
            commitment_error,
        ) if error
    ]
    audit.add("release_manifests_parse", not package_parse_errors,
              "restricted, commitment, analyst, leakage, sealed release, and completion manifests must parse",
              package_parse_errors)
    pending_declared = resolve_declared(release_declaration.get("pending_package_path"), sealed_dir)
    reviewer_ids = release_declaration.get("reviewer_ids")
    reviewer_ids_valid = (
        isinstance(reviewer_ids, list)
        and all(isinstance(value, str) and value.strip() for value in reviewer_ids)
        and len(set(value for value in reviewer_ids if isinstance(value, str))) >= 2
    )
    release_state_pass = (
        release_declaration.get("stage") == STAGE
        and release_declaration.get("state") == "ANALYST_RELEASED"
        and release_declaration.get("machine_leakage_scan") == "pass"
        and release_declaration.get("two_person_visual_review") == "pass"
        and bool_is(release_declaration.get("treatment_key_present"), False)
        and reviewer_ids_valid
        and pending_declared is not None and same_path(pending_declared, pending_dir)
        and sealed_completion.get("stage") == STAGE
        and sealed_completion.get("state") == "ANALYST_RELEASED"
        and sealed_completion.get("status") == "complete"
        and bool_is(sealed_completion.get("no_treatment_reveal"), True)
        and analyst_manifest.get("state") == "SANITIZED_PENDING_VISUAL_REVIEW"
        and analyst_manifest.get("metadata_leak_scan") == "pass"
        and bool_is(analyst_manifest.get("pixel_identity_all_pass"), True)
        and bool_is(analyst_manifest.get("treatment_key_present"), False)
    )
    audit.add(
        "analyst_release_state", release_state_pass,
        "sealed package must be ANALYST_RELEASED after machine and two-person visual leakage gates, with no treatment key",
        {"release_declaration": release_declaration, "sealed_completion": sealed_completion,
         "analyst_manifest_state": analyst_manifest.get("state")},
    )
    leakage_scan_pass = (
        leakage_scan.get("stage") == STAGE
        and leakage_scan.get("release_id") == release_declaration.get("release_id")
        and leakage_scan.get("status") == "pass"
        and leakage_scan.get("finding_n") == 0
        and leakage_scan.get("findings") == []
        and isinstance(leakage_scan.get("scanned_manifest_row_n"), int)
        and leakage_scan.get("scanned_manifest_row_n", 0) > 0
        and leakage_scan.get("scanned_image_metadata_n") == leakage_scan.get("scanned_manifest_row_n")
        and valid_sha(analyst_manifest.get("leakage_scan_sha256"))
        and leakage_scan_path.is_file()
        and sha256(leakage_scan_path) == str(analyst_manifest.get("leakage_scan_sha256")).lower()
        and release_declaration.get("leakage_scan_sha256") == analyst_manifest.get("leakage_scan_sha256")
    )
    audit.add(
        "explicit_machine_leakage_scan_evidence", leakage_scan_pass,
        "the analyst leakage_scan.json must pass with zero findings and be hash-bound by analyst and sealed manifests",
        {"record": leakage_scan, "analyst_hash": analyst_manifest.get("leakage_scan_sha256"),
         "sealed_hash": release_declaration.get("leakage_scan_sha256")},
    )
    manifest_hashes_check(audit, pending_dir)
    commitment_state_pass = (
        cross_commitment.get("stage") == STAGE
        and cross_commitment.get("release_id") == release_declaration.get("release_id")
        and cross_commitment.get("state") == "CUSTODIAN_COMMITTED_PENDING_VISUAL_REVIEW"
        and bool_is(cross_commitment.get("treatment_key_present_in_analyst_package"), False)
        and cross_commitment.get("custodian_key_sha256") == analyst_manifest.get("custodian_key_sha256")
        and cross_commitment.get("roles_and_key_custody_sha256") == analyst_manifest.get("roles_and_key_custody_sha256")
        and cross_commitment.get("resolved_config_sha256") == analyst_manifest.get("resolved_config_sha256")
        and cross_commitment.get("release_builder_sha256") == analyst_manifest.get("release_builder_sha256")
        and restricted_manifest.get("custodian_key_sha256") == cross_commitment.get("custodian_key_sha256")
        and restricted_manifest.get("roles_and_key_custody_sha256") == cross_commitment.get("roles_and_key_custody_sha256")
        and restricted_manifest.get("resolved_config_sha256") == cross_commitment.get("resolved_config_sha256")
        and restricted_manifest.get("release_builder_sha256") == cross_commitment.get("release_builder_sha256")
    )
    audit.add(
        "restricted_cross_release_commitment_state", commitment_state_pass,
        "custodian commitment must bind one release and agree with restricted/analyst key, roles, config, and builder lineage",
        cross_commitment,
    )
    validate_named_links(
        audit, "release_manifest_artifact_hashes",
        [
            ("restricted.source_manifest_sha256", restricted_manifest.get("source_manifest_sha256"),
             resolve_declared(restricted_manifest.get("source_manifest_path"), restricted_dir)),
            ("restricted.copied_source_manifest_sha256", restricted_manifest.get("source_manifest_sha256"),
             restricted_dir / "source_acquisition_manifest.csv"),
            ("restricted.custodian_key_sha256", restricted_manifest.get("custodian_key_sha256"), key_path),
            ("restricted.roles_and_key_custody_sha256", restricted_manifest.get("roles_and_key_custody_sha256"), roles_path),
            ("restricted.release_builder_sha256", restricted_manifest.get("release_builder_sha256"), REQUIRED_SOURCES["stage33cq_release_builder"]),
            ("commitment.restricted_manifest_sha256", cross_commitment.get("restricted_manifest_sha256"), restricted_manifest_path),
            ("commitment.custodian_key_sha256", cross_commitment.get("custodian_key_sha256"), key_path),
            ("commitment.roles_and_key_custody_sha256", cross_commitment.get("roles_and_key_custody_sha256"), roles_path),
            ("commitment.release_builder_sha256", cross_commitment.get("release_builder_sha256"), REQUIRED_SOURCES["stage33cq_release_builder"]),
            ("commitment.blinded_image_manifest_sha256", cross_commitment.get("blinded_image_manifest_sha256"), blinded_manifest_path),
            ("commitment.analyst_manifest_sha256", cross_commitment.get("analyst_manifest_sha256"), analyst_manifest_path),
            ("commitment.analyst_package_hashes_sha256", cross_commitment.get("analyst_package_hashes_sha256"), pending_dir / "package_hashes.json"),
            ("analyst.blinded_image_manifest_sha256", analyst_manifest.get("blinded_image_manifest_sha256"), blinded_manifest_path),
            ("analyst.leakage_scan_sha256", analyst_manifest.get("leakage_scan_sha256"), leakage_scan_path),
            ("analyst.visual_leakage_montage_sha256", analyst_manifest.get("visual_leakage_montage_sha256"), pending_dir / "visual_leakage_montage.png"),
            ("analyst.visual_leakage_review_template_sha256", analyst_manifest.get("visual_leakage_review_template_sha256"), pending_dir / "visual_leakage_review_template.csv"),
            ("analyst.custodian_key_sha256", analyst_manifest.get("custodian_key_sha256"), key_path),
            ("release.pending_package_hashes_sha256", release_declaration.get("pending_package_hashes_sha256"), pending_dir / "package_hashes.json"),
            ("release.blinded_image_manifest_sha256", release_declaration.get("blinded_image_manifest_sha256"), blinded_manifest_path),
            ("release.analyst_manifest_sha256", release_declaration.get("analyst_manifest_sha256"), analyst_manifest_path),
            ("release.visual_leakage_montage_sha256", release_declaration.get("visual_leakage_montage_sha256"), pending_dir / "visual_leakage_montage.png"),
            ("release.visual_leakage_review_sha256", release_declaration.get("visual_leakage_review_sha256"), sealed_dir / "visual_leakage_review.csv"),
            ("release.roles_and_key_custody_sha256", release_declaration.get("roles_and_key_custody_sha256"), roles_path),
            ("release.restricted_cross_release_commitment_sha256", release_declaration.get("restricted_cross_release_commitment_sha256"), cross_commitment_path),
            ("release.restricted_manifest_sha256", release_declaration.get("restricted_manifest_sha256"), restricted_manifest_path),
            ("release.leakage_scan_sha256", release_declaration.get("leakage_scan_sha256"), leakage_scan_path),
            ("release.visual_sealer_sha256", release_declaration.get("visual_sealer_sha256"), REQUIRED_SOURCES["stage33cq_visual_sealer"]),
            ("completion.release_declaration_sha256", sealed_completion.get("release_declaration_sha256"), release_declaration_path),
        ],
    )
    config_hash_values_list = [
        restricted_manifest.get("resolved_config_sha256"), analyst_manifest.get("resolved_config_sha256"),
        cross_commitment.get("resolved_config_sha256"), leakage_scan.get("resolved_config_sha256"),
    ]
    config_hash_values = {
        value for value in config_hash_values_list if isinstance(value, str)
    }
    audit.add(
        "release_config_hash_resolves",
        len(config_hash_values) == 1
        and all(isinstance(value, str) for value in config_hash_values_list)
        and next(iter(config_hash_values), None) in design_file_hashes,
        "restricted and analyst manifests must agree on a config hash that resolves through design_files",
        {"manifest_hashes": sorted(str(value) for value in config_hash_values),
         "design_file_hashes": sorted(design_file_hashes)},
    )
    secret_hash = restricted_manifest.get("custodian_secret_sha256")
    audit.add(
        "synthetic_secret_hash_resolves",
        valid_sha(secret_hash) and fixture_secret_path.is_file()
        and sha256(fixture_secret_path) == str(secret_hash).lower()
        and fixture.get("secret_sha256") == secret_hash,
        "the restricted secret, test-fixture declaration, and fixed synthetic secret file must hash-identify one artifact",
        {"restricted_secret_sha256": secret_hash, "fixture_secret_sha256": fixture.get("secret_sha256"),
         "path": str(fixture_secret_path)},
    )

    key_rows, blinded_rows = evidence_and_pixel_checks(audit, restricted_dir, pending_dir)
    source_manifest_and_nonce_checks(audit, restricted_dir, restricted_manifest, key_rows)
    scan_analyst_packages(audit, [pending_dir, sealed_dir], key_rows)
    image_counts = {
        "fixture": fixture.get("image_n"), "analyst_manifest": analyst_manifest.get("image_n"),
        "release": release_declaration.get("image_n"), "key_rows": len(key_rows),
        "blinded_rows": len(blinded_rows),
    }
    audit.add(
        "release_image_count_closure",
        bool(key_rows)
        and all(isinstance(value, int) for value in image_counts.values())
        and len({value for value in image_counts.values() if isinstance(value, int)}) == 1,
        "fixture, manifests, release, restricted key, and analyst manifest image counts must agree exactly",
        image_counts,
    )

    success_checks = verification.get("successful_release_checks")
    success_checks = success_checks if isinstance(success_checks, dict) else {}
    success_reviewer_ids = success_checks.get("reviewer_ids")
    success_reviewer_ids_valid = (
        isinstance(success_reviewer_ids, list)
        and all(isinstance(value, str) and value.strip() for value in success_reviewer_ids)
        and len(set(value for value in success_reviewer_ids if isinstance(value, str))) >= 2
    )
    pixel_identity_record = success_checks.get("pixel_identity")
    pixel_identity_record = pixel_identity_record if isinstance(pixel_identity_record, dict) else {}
    pixel_identity_fields = (
        "manifest_pixel_identity_flags_all_true",
        "independent_source_to_sanitized_arrays_equal",
        "restricted_to_analyst_pixel_hashes_equal",
        "restricted_source_metadata_fields_absent_from_analyst_csv",
        "fixed_test_secret_bytes_absent_from_analyst_package",
    )
    audit.add(
        "verification_successful_release_checks",
        bool_is(success_checks.get("passed"), True)
        and success_checks.get("build_status") == "sanitized_pending_visual_review"
        and success_checks.get("sanitized_release_status") == "sanitized_blinded_analyst_package"
        and pixel_identity_record.get("image_n") == len(blinded_rows)
        and all(bool_is(pixel_identity_record.get(field), True) for field in pixel_identity_fields)
        and bool_is(success_checks.get("treatment_key_present"), False)
        and success_checks.get("sealed_state") == "ANALYST_RELEASED"
        and str(success_checks.get("two_person_visual_review", "")).casefold() == "pass"
        and success_checks.get("machine_leakage_scan_status") == "pass"
        and success_checks.get("machine_leakage_finding_n") == 0
        and bool_is(success_checks.get("leakage_scan_hash_bound"), True)
        and bool_is(success_checks.get("custodian_cross_commitment_hash_bound"), True)
        and success_reviewer_ids_valid
        and success_checks.get("image_n") == len(blinded_rows),
        "synthetic successful-release summary must affirm exact pixels, no key, released state, and two reviewers",
        success_checks,
    )

    identical_dir = verification_dir / "mask_qualification" / "identical_pass"
    perturbed_dir = verification_dir / "mask_qualification" / "perturbed_fail"
    identical_summary, identical_completion = qualifier_hash_links(
        audit, "identical", identical_dir, blinded_manifest_path, roles_path
    )
    perturbed_summary, perturbed_completion = qualifier_hash_links(
        audit, "perturbed", perturbed_dir, blinded_manifest_path, roles_path
    )
    identical_gates = identical_summary.get("preconsensus_gates")
    identical_gates = identical_gates if isinstance(identical_gates, dict) else {}
    identical_ids = [identical_summary.get("reviewer_A_id"), identical_summary.get("reviewer_B_id")]
    identical_record = verification.get("identical_mask_checks")
    identical_record = identical_record if isinstance(identical_record, dict) else {}
    identical_pass = (
        identical_summary.get("stage") == STAGE
        and bool_is(identical_summary.get("preconsensus_gate_pass"), True)
        and identical_summary.get("discrepancy_n") == 0
        and identical_summary.get("median_dice") == 1.0
        and identical_summary.get("median_boundary_f1_2px") == 1.0
        and identical_summary.get("median_hausdorff95_px") == 0.0
        and identical_summary.get("morphology_class_cohen_kappa") == 1.0
        and identical_summary.get("feret_max_icc_A1") == 1.0
        and bool(identical_gates) and all(value is True for value in identical_gates.values())
        and all(isinstance(value, str) and value for value in identical_ids)
        and len({value for value in identical_ids if isinstance(value, str)}) == 2
        and identical_completion.get("status") == "complete"
        and bool_is(identical_completion.get("preconsensus_gate_pass"), True)
        and bool_is(identical_record.get("passed"), True)
        and bool_is(identical_record.get("preconsensus_gate_pass"), True)
        and identical_record.get("discrepancy_n") == 0
        and identical_record.get("median_dice") == 1.0
        and identical_record.get("median_boundary_f1_2px") == 1.0
        and identical_record.get("median_hausdorff95_px") == 0.0
        and identical_record.get("morphology_class_cohen_kappa") == 1.0
        and identical_record.get("feret_max_icc_A1") == 1.0
    )
    audit.add(
        "exact_reviewer_comparison", identical_pass,
        "identical independent reviewer inputs must pass every gate with exact overlap and zero discrepancies",
        {"summary": identical_summary, "verification_record": identical_record},
    )

    perturbed_gates = perturbed_summary.get("preconsensus_gates")
    perturbed_gates = perturbed_gates if isinstance(perturbed_gates, dict) else {}
    perturbed_record = verification.get("perturbed_mask_checks")
    perturbed_record = perturbed_record if isinstance(perturbed_record, dict) else {}
    discrepancy_rows, _, discrepancy_error = load_csv(perturbed_dir / "discrepancy_queue.csv")
    queue_sha = sha256(perturbed_dir / "discrepancy_queue.csv") if (perturbed_dir / "discrepancy_queue.csv").is_file() else None
    perturbed_pass = (
        perturbed_summary.get("stage") == STAGE
        and bool_is(perturbed_summary.get("preconsensus_gate_pass"), False)
        and isinstance(perturbed_summary.get("discrepancy_n"), int)
        and perturbed_summary.get("discrepancy_n", 0) > 0
        and bool(perturbed_gates) and any(value is False for value in perturbed_gates.values())
        and perturbed_completion.get("status") == "complete"
        and bool_is(perturbed_completion.get("preconsensus_gate_pass"), False)
        and discrepancy_error is None
        and len(discrepancy_rows) == perturbed_summary.get("discrepancy_n")
        and bool_is(perturbed_record.get("passed"), True)
        and bool_is(perturbed_record.get("preconsensus_gate_pass"), False)
        and perturbed_record.get("discrepancy_n") == perturbed_summary.get("discrepancy_n")
        and "matched_object_boundary_or_class" in perturbed_record.get("discrepancy_types", [])
        and valid_sha(perturbed_record.get("discrepancy_queue_sha256"))
        and str(perturbed_record.get("discrepancy_queue_sha256")).lower() == queue_sha
    )
    audit.add(
        "negative_reviewer_comparison", perturbed_pass,
        "deliberately perturbed reviewer inputs must complete but fail pre-consensus, create discrepancies, and hash-bind the queue",
        {"summary": perturbed_summary, "verification_record": perturbed_record,
         "queue_row_n": len(discrepancy_rows), "queue_sha256": queue_sha,
         "queue_error": discrepancy_error},
    )

    design_snapshot_after = tree_snapshot(design_dir)
    verification_snapshot_after = tree_snapshot(verification_dir)
    inputs_unchanged = (
        design_snapshot_before == design_snapshot_after
        and verification_snapshot_before == verification_snapshot_after
    )
    audit.add(
        "inputs_remained_unchanged", inputs_unchanged,
        "complete before/after SHA-256 snapshots of both input trees must be identical",
        {"design_file_n": len(design_snapshot_before),
         "verification_file_n": len(verification_snapshot_before)},
    )

    passed_n = sum(item["pass"] for item in audit.checks)
    failed = [item["check_id"] for item in audit.checks if not item["pass"]]
    audit_record = {
        "schema": AUDIT_SCHEMA,
        "stage": STAGE,
        "audit_id": f"{release_id or 'UNRESOLVED'}_RELEASE_AUDIT_V1",
        "created_utc": started_utc,
        "completed_utc": utc_now(),
        "status": "passed_release_audit" if audit.passed else "failed_release_audit",
        "pass": audit.passed,
        "check_n": len(audit.checks),
        "passed_check_n": passed_n,
        "failed_check_n": len(failed),
        "failed_checks": failed,
        "checks": audit.checks,
        "inputs": {
            "design_dir": str(design_dir),
            "resolved_design_path": str(design_path),
            "resolved_design_sha256": sha256(design_path) if design_path.is_file() else None,
            "verification_dir": str(verification_dir),
            "verification_path": str(verification_path),
            "verification_sha256": actual_verification_sha,
            "verification_hash_binding_n": len(resolved_verification_paths),
        },
        "release": {
            "release_id": release_id,
            "analyst_state": release_declaration.get("state"),
            "image_n": len(blinded_rows),
            "reviewer_ids": reviewer_ids,
        },
        "claim_boundary": (
            "synthetic software/release qualification only; no empirical PET morphology, "
            "degradation, treatment-effect, or simulation validation claim"
        ),
        "stop_boundary": design.get("stop_boundary"),
        "input_mutation": False if inputs_unchanged else "DETECTED",
    }
    return audit_record, {
        "schema": COMPLETION_SCHEMA,
        "stage": STAGE,
        "audit_id": audit_record["audit_id"],
        "status": "complete" if audit.passed else "failed",
        "completed_utc": utc_now(),
        "passed": audit.passed,
        "failed_checks": failed,
        "no_input_modified": inputs_unchanged,
        "no_empirical_data": True,
        "no_treatment_reveal": True,
        "no_simulation": True,
    }


def prepare_output(output: Path, design_dir: Path, verification_dir: Path) -> Path:
    unresolved = output.absolute()
    if unresolved.exists():
        if unresolved.is_symlink():
            raise RuntimeError(f"fail-closed: output must not be a symbolic link: {unresolved}")
        if not unresolved.is_dir():
            raise RuntimeError(f"fail-closed: output exists and is not a directory: {unresolved}")
        if any(unresolved.iterdir()):
            raise RuntimeError(f"fail-closed: output directory is not empty: {unresolved}")
    resolved = unresolved.resolve()
    if contained(resolved, design_dir) or contained(resolved, verification_dir):
        raise RuntimeError("fail-closed: output must be disjoint from both read-only input directories")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design-dir", type=Path, required=True)
    parser.add_argument("--verification-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    design_dir = args.design_dir.resolve()
    verification_dir = args.verification_dir.resolve()
    output = prepare_output(args.output, design_dir, verification_dir)
    outer_design_snapshot: dict[str, str] = {}
    outer_verification_snapshot: dict[str, str] = {}
    try:
        outer_design_snapshot = tree_snapshot(design_dir)
        outer_verification_snapshot = tree_snapshot(verification_dir)
        audit_record, completion = perform_audit(design_dir, verification_dir, output)
    except Exception as exc:
        try:
            inputs_unchanged = (
                outer_design_snapshot == tree_snapshot(design_dir)
                and outer_verification_snapshot == tree_snapshot(verification_dir)
            )
        except Exception:
            inputs_unchanged = False
        completed_utc = utc_now()
        audit_record = {
            "schema": AUDIT_SCHEMA,
            "stage": STAGE,
            "audit_id": "UNRESOLVED_RELEASE_AUDIT_V1",
            "created_utc": completed_utc,
            "completed_utc": completed_utc,
            "status": "failed_release_audit",
            "pass": False,
            "check_n": 1,
            "passed_check_n": 0,
            "failed_check_n": 1,
            "failed_checks": ["unexpected_auditor_exception"],
            "checks": [{
                "check_id": "unexpected_auditor_exception",
                "pass": False,
                "requirement": "malformed or hostile evidence must fail closed with a preserved audit record",
                "observed": {"exception_type": type(exc).__name__, "message": str(exc)},
            }],
            "inputs": {"design_dir": str(design_dir), "verification_dir": str(verification_dir)},
            "claim_boundary": "audit aborted; no release or empirical claim is authorized",
            "stop_boundary": "fail closed and investigate the recorded exception",
            "input_mutation": False if inputs_unchanged else "DETECTED",
        }
        completion = {
            "schema": COMPLETION_SCHEMA,
            "stage": STAGE,
            "audit_id": audit_record["audit_id"],
            "status": "failed",
            "completed_utc": completed_utc,
            "passed": False,
            "failed_checks": ["unexpected_auditor_exception"],
            "no_input_modified": inputs_unchanged,
            "no_empirical_data": True,
            "no_treatment_reveal": True,
            "no_simulation": True,
        }
    json_dump(output / "audit.json", audit_record)
    completion["audit_sha256"] = sha256(output / "audit.json")
    json_dump(output / "completion.json", completion)
    print(json.dumps(completion, indent=2, sort_keys=True))
    return 0 if audit_record["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
