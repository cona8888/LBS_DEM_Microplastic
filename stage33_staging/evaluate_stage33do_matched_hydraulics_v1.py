#!/usr/bin/env python3
"""Evaluate a frozen Stage33D-O matched hydraulic release, fail closed.

The evaluator is deliberately split into a blinded phase and a reveal phase.
Raw constant-head observations, exclusions, matched PET/clean ratios, and the
15 batch endpoints are recomputed before the restricted treatment key is read.
Their canonical hashes must match an independently frozen primary commitment.
The CLI therefore has two explicit phases. ``pre_reveal`` cannot read the
treatment key and emits immutable blinded records.  A separate sealer binds
those records. ``post_reveal`` accepts the key only through that frozen chain
and then emits bounded condition summaries.

This program performs data reduction only.  It does not run a laboratory test,
DEM/LBM calculation, model calibration, or absolute permeability validation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import statistics
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


RELEASE_SCHEMA = "pet.stage33do-matched-hydraulics-operational-release.v1"
OPERATOR_MANIFEST_SCHEMA = "pet.stage33do-hydraulic-operator-package.v1"
ANALYST_MANIFEST_SCHEMA = "pet.stage33do-hydraulic-analyst-package.v1"
RESTRICTED_MANIFEST_SCHEMA = "pet.stage33do-hydraulic-restricted-package.v1"
COMMITMENT_SCHEMA = "pet.stage33do-cross-release-commitment.v1"
PRIMARY_FREEZE_SCHEMA = "pet.stage33do-primary-freeze-commitment.v1"
LINEARITY_ATTESTATION_SCHEMA = "pet.stage33do-linearity-gate-attestation.v1"
REVEAL_DECLARATION_SCHEMA = "pet.stage33do-reveal-declaration.v1"
EVALUATION_SCHEMA = "pet.stage33do-matched-hydraulics-evaluation.v1"

DESIGN_SCHEMA = "pet.stage33d-matched-pet-lbs-physical-validation-design.v1"
GATES_SCHEMA = "pet.stage33d-matched-pet-lbs-acceptance-gates.v1"
DESIGN_COMPLETION_SCHEMA = (
    "pet.stage33d-matched-pet-lbs-physical-validation-design-completion.v1"
)

CONDITIONS = ("T20", "T120", "T140", "T160", "T180")
TRUE_TOKENS = {"1", "true", "yes", "y"}
FALSE_TOKENS = {"0", "false", "no", "n"}

OPERATOR_CAPTURE_FIELDS = [
    "operational_release_id",
    "opaque_specimen_id",
    "water_temperature_c",
    "specimen_diameter_mm",
    "specimen_length_mm",
    "head_difference_m",
    "collection_time_s",
    "collected_water_mass_g",
    "calculated_K20_m_s",
    "saturated",
    "leak_free",
    "steady_state",
    "effluent_pet_detected",
    "measurement_valid",
    "measurement_rejection_reason",
]

LINEARITY_FIELDS = [
    "operational_release_id",
    "opaque_linearity_id",
    "gradient_sequence",
    "water_temperature_c",
    "specimen_diameter_mm",
    "specimen_length_mm",
    "head_difference_m",
    "collection_time_s",
    "collected_water_mass_g",
    "particle_reynolds_number",
    "measurement_valid",
    "measurement_rejection_reason",
    "measured_utc",
    "operator_id",
]

ANALYST_KEY_FIELDS = [
    "operational_release_id",
    "opaque_specimen_id",
    "opaque_matched_set_id",
    "analyst_batch_code",
    "specimen_role",
]

PREPARATION_FIELDS = [
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

LINEARITY_CROSSWALK_FIELDS = [
    "operational_release_id",
    "opaque_linearity_id",
    "opaque_specimen_id",
]

REVEAL_FIELDS = [
    "operational_release_id",
    "analyst_batch_code",
    "reactor_block",
    "condition_id",
    "source_batch_slot",
]

MORPHOLOGY_FIELDS = [
    "operational_release_id",
    "analyst_batch_code",
    "log_d50_max_feret",
    "measurement_se",
]

SPECIMEN_OUTPUT_FIELDS = [
    "operational_release_id",
    "opaque_specimen_id",
    "opaque_matched_set_id",
    "analyst_batch_code",
    "specimen_role",
    "pre_reveal_eligible",
    "eligibility_reasons",
    "K_raw_m_s",
    "K20_m_s",
    "matched_clean_K20_m_s",
    "log_ratio_to_matched_clean",
    "ratio_to_matched_clean",
]

BATCH_OUTPUT_FIELDS = [
    "operational_release_id",
    "analyst_batch_code",
    "valid_matched_sets",
    "batch_log_ratio",
    "batch_geometric_ratio",
    "within_batch_log_ratio_sd",
]

CONDITION_OUTPUT_FIELDS = [
    "condition_id",
    "n_batches",
    "mean_batch_log_ratio",
    "geometric_mean_ratio",
    "sample_sd_log_ratio",
    "ci95_low_log_ratio",
    "ci95_high_log_ratio",
    "reactor_blocks_complete",
]

EXCLUSION_OUTPUT_FIELDS = [
    "operational_release_id",
    "opaque_specimen_id",
    "pre_reveal_eligible",
    "eligibility_reasons",
    "exclusion_rule_source",
]

REQUIRED_SOURCE_BINDINGS = {
    "stage33d_resolved_design",
    "stage33d_acceptance_gates",
    "stage33d_design_completion",
}

REQUIRED_ARTIFACTS = {
    "operator_manifest": "operator/operator_manifest.json",
    "analyst_manifest": "analyst/analyst_manifest.json",
    "restricted_manifest": "restricted/restricted_manifest.json",
    "cross_release_commitment": "restricted/cross_release_commitment.json",
    "blinded_analysis_key": "analyst/blinded_analysis_key.csv",
    "preparation_records": "restricted/preparation_records.csv",
    "reveal_key": "restricted/reveal_key.csv",
    "linearity_crosswalk": "restricted/linearity_crosswalk.csv",
    "custodian_crosswalk": "restricted/custodian_crosswalk.csv",
    "synthetic_morphology_summary": "analyst/synthetic_morphology_summary.csv",
}

T95 = {1: 12.7062, 2: 4.3027, 3: 3.1824, 4: 2.7764, 5: 2.5706,
       6: 2.4469, 7: 2.3646, 8: 2.3060, 9: 2.2622, 10: 2.2281}


class EvaluationError(RuntimeError):
    """Structured fail-closed error."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def binding(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": sha256_file(path)}


def canonical_json_bytes(value: Any, domain: str) -> bytes:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return (domain + "\n" + payload + "\n").encode("utf-8")


def canonical_records_hash(records: list[dict[str, Any]], domain: str) -> str:
    return sha256_bytes(canonical_json_bytes(records, domain))


def read_json(path: Path, schema: str | None = None, passed: bool | None = None) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvaluationError("D33DO_MALFORMED_JSON", f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvaluationError("D33DO_SCHEMA_MISMATCH", f"JSON root is not an object: {path}")
    if schema is not None and value.get("schema") != schema:
        raise EvaluationError(
            "D33DO_SCHEMA_MISMATCH",
            f"unexpected schema in {path}: {value.get('schema')!r}; expected {schema!r}",
        )
    if passed is not None and value.get("passed") is not passed:
        raise EvaluationError("D33DO_RELEASE_NOT_ACCEPTED", f"passed flag is not {passed}: {path}")
    return value


def read_csv_exact(path: Path, fields: list[str]) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            actual = reader.fieldnames or []
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise EvaluationError("D33DO_MALFORMED_CSV", f"cannot read CSV {path}: {exc}") from exc
    if actual != fields:
        raise EvaluationError(
            "D33DO_SCHEMA_MISMATCH",
            f"unexpected CSV columns in {path}: {actual}; expected {fields}",
        )
    return rows


def resolve_binding_path(base: Path, item: dict[str, Any], label: str) -> Path:
    raw = item.get("path")
    expected_hash = item.get("sha256")
    if not isinstance(raw, str) or not raw or not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_hash):
        raise EvaluationError("D33DO_LINEAGE_MISMATCH", f"invalid path/hash binding: {label}")
    path = Path(raw)
    if not path.is_absolute():
        path = base / path
    path = path.resolve()
    if not path.is_file():
        raise EvaluationError("D33DO_LINEAGE_MISMATCH", f"bound file missing: {label}: {path}")
    actual = sha256_file(path)
    if actual.lower() != expected_hash.lower():
        raise EvaluationError(
            "D33DO_LINEAGE_MISMATCH",
            f"SHA-256 mismatch for {label}: expected {expected_hash.lower()}, got {actual}",
        )
    return path


def verify_fixed_artifact(
    release: Path, artifacts: dict[str, Any], name: str, relative: str
) -> Path:
    item = artifacts.get(name)
    if not isinstance(item, dict):
        raise EvaluationError("D33DO_LINEAGE_MISMATCH", f"missing artifact binding: {name}")
    path = resolve_binding_path(release, item, f"artifact:{name}")
    expected = (release / relative).resolve()
    if path != expected:
        raise EvaluationError(
            "D33DO_LINEAGE_MISMATCH",
            f"artifact {name} is not at frozen release path {expected}",
        )
    return path


def verify_nested_binding(
    manifest: dict[str, Any], base: Path, key: str, expected: Path, label: str
) -> None:
    items = manifest.get("artifacts")
    if not isinstance(items, dict) or not isinstance(items.get(key), dict):
        raise EvaluationError("D33DO_LINEAGE_MISMATCH", f"missing nested binding {label}:{key}")
    path = resolve_binding_path(base, items[key], f"{label}:{key}")
    if path != expected.resolve():
        raise EvaluationError("D33DO_LINEAGE_MISMATCH", f"nested binding path mismatch {label}:{key}")


def require_release_id(rows: Iterable[dict[str, str]], release_id: str, context: str) -> None:
    for index, row in enumerate(rows, 2):
        if row.get("operational_release_id", "").strip() != release_id:
            raise EvaluationError(
                "D33DO_RELEASE_ID_MISMATCH",
                f"wrong operational_release_id in {context} row {index}",
            )


def require_text(row: dict[str, str], field: str, context: str) -> str:
    value = row.get(field, "").strip()
    if not value:
        raise EvaluationError("D33DO_MALFORMED_DATA", f"blank {field} for {context}")
    return value


def parse_float(
    row: dict[str, str], field: str, context: str, *, positive: bool = False,
    nonnegative: bool = False,
) -> float:
    raw = row.get(field, "").strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise EvaluationError("D33DO_MALFORMED_DATA", f"invalid {field} for {context}: {raw!r}") from exc
    if not math.isfinite(value):
        raise EvaluationError("D33DO_MALFORMED_DATA", f"nonfinite {field} for {context}")
    if positive and value <= 0.0:
        raise EvaluationError("D33DO_MALFORMED_DATA", f"nonpositive {field} for {context}")
    if nonnegative and value < 0.0:
        raise EvaluationError("D33DO_MALFORMED_DATA", f"negative {field} for {context}")
    return value


def parse_int(row: dict[str, str], field: str, context: str, *, positive: bool = False) -> int:
    raw = row.get(field, "").strip()
    if not re.fullmatch(r"[+-]?\d+", raw):
        raise EvaluationError("D33DO_MALFORMED_DATA", f"invalid integer {field} for {context}: {raw!r}")
    value = int(raw)
    if positive and value <= 0:
        raise EvaluationError("D33DO_MALFORMED_DATA", f"nonpositive {field} for {context}")
    return value


def parse_bool(raw: str, context: str) -> bool:
    token = raw.strip().lower()
    if token in TRUE_TOKENS:
        return True
    if token in FALSE_TOKENS:
        return False
    raise EvaluationError("D33DO_MALFORMED_DATA", f"invalid boolean for {context}: {raw!r}")


def assert_unique(rows: Iterable[dict[str, str]], fields: tuple[str, ...], context: str) -> None:
    seen: set[tuple[str, ...]] = set()
    for index, row in enumerate(rows, 2):
        key = tuple(row.get(field, "").strip() for field in fields)
        if any(not value for value in key):
            raise EvaluationError("D33DO_MALFORMED_DATA", f"blank identity in {context} row {index}: {fields}")
        if key in seen:
            raise EvaluationError("D33DO_DUPLICATE_IDENTITY", f"duplicate {context} identity: {key}")
        seen.add(key)


def assert_blinded_package_no_treatment_leak(paths: Iterable[Path]) -> None:
    pattern = re.compile(rb"(?<![A-Za-z0-9])(?:T20|T120|T140|T160|T180|S33A-B\d+)(?![A-Za-z0-9])", re.IGNORECASE)
    for path in paths:
        data = path.read_bytes()
        if pattern.search(data):
            raise EvaluationError(
                "D33DO_TREATMENT_KEY_LEAKAGE",
                f"treatment/source token detected in nonrestricted package: {path}",
            )


def water_density_kg_m3(temp_c: float) -> float:
    return 1000.0 * (
        1.0
        - ((temp_c + 288.9414) / (508929.2 * (temp_c + 68.12963)))
        * (temp_c - 3.9863) ** 2
    )


def water_viscosity_pa_s(temp_c: float) -> float:
    return 2.414e-5 * 10.0 ** (247.8 / (temp_c + 133.15))


def hydraulic_values(
    temp_c: float,
    diameter_mm: float,
    length_mm: float,
    head_m: float,
    time_s: float,
    collected_water_mass_g: float,
) -> dict[str, float]:
    rho = water_density_kg_m3(temp_c)
    rho20 = water_density_kg_m3(20.0)
    mu = water_viscosity_pa_s(temp_c)
    mu20 = water_viscosity_pa_s(20.0)
    volume_m3 = (collected_water_mass_g / 1000.0) / rho
    discharge = volume_m3 / time_s
    area = math.pi * (diameter_mm / 2000.0) ** 2
    length_m = length_mm / 1000.0
    gradient = head_m / length_m
    k_raw = discharge * length_m / (area * head_m)
    k20 = k_raw * (mu / mu20) * (rho20 / rho)
    values = {
        "water_density_kg_m3": rho,
        "water_viscosity_pa_s": mu,
        "discharge_m3_s": discharge,
        "gradient": gradient,
        "K_raw_m_s": k_raw,
        "K20_m_s": k20,
    }
    if any(not math.isfinite(v) or v <= 0.0 for v in values.values()):
        raise EvaluationError("D33DO_HYDRAULIC_CALCULATION_FAILED", "nonpositive/nonfinite hydraulic result")
    return values


def relative_error(supplied: float, calculated: float) -> float:
    return abs(supplied - calculated) / max(abs(calculated), sys.float_info.min)


def r_squared(x: list[float], y: list[float]) -> float:
    if len(x) < 2 or len(set(x)) < 2:
        return float("nan")
    xm = statistics.fmean(x)
    ym = statistics.fmean(y)
    sxx = sum((value - xm) ** 2 for value in x)
    slope = sum((a - xm) * (b - ym) for a, b in zip(x, y)) / sxx
    intercept = ym - slope * xm
    residual = sum((b - (intercept + slope * a)) ** 2 for a, b in zip(x, y))
    total = sum((b - ym) ** 2 for b in y)
    if total == 0.0:
        return 1.0 if residual == 0.0 else float("nan")
    return 1.0 - residual / total


def sample_cv(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = statistics.fmean(values)
    return statistics.stdev(values) / mean if mean > 0.0 else None


def mean_ci(values: list[float]) -> dict[str, float | int | None]:
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": None, "sd": None, "low": None, "high": None}
    mean = statistics.fmean(values)
    if n == 1:
        return {"n": 1, "mean": mean, "sd": None, "low": None, "high": None}
    sd = statistics.stdev(values)
    critical = T95.get(n - 1, 1.96)
    half = critical * sd / math.sqrt(n)
    return {"n": n, "mean": mean, "sd": sd, "low": mean - half, "high": mean + half}


def csv_bytes(fields: list[str], rows: list[dict[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    for row in rows:
        rendered = dict(row)
        if "eligibility_reasons" in rendered and isinstance(rendered["eligibility_reasons"], list):
            rendered["eligibility_reasons"] = json.dumps(
                rendered["eligibility_reasons"], separators=(",", ":"), ensure_ascii=True
            )
        writer.writerow({field: rendered.get(field) for field in fields})
    return buffer.getvalue().encode("utf-8")


def validate_release(release: Path) -> dict[str, Any]:
    manifest_path = release / "release_manifest.json"
    if not manifest_path.is_file():
        raise EvaluationError("D33DO_LINEAGE_MISMATCH", "release_manifest.json is missing")
    manifest = read_json(manifest_path, RELEASE_SCHEMA, passed=True)
    if manifest.get("stage") != "Stage33D-O" or manifest.get("test_only") is not True or manifest.get("no_empirical_data") is not True:
        raise EvaluationError("D33DO_RELEASE_NOT_ACCEPTED", "release is not Stage33D-O synthetic-only")
    if any(value is not False for value in (manifest.get("authority") or {}).values()):
        raise EvaluationError("D33DO_RELEASE_NOT_ACCEPTED", "release authority is not fully closed")
    release_id = manifest.get("release_id")
    if not isinstance(release_id, str) or not release_id.strip():
        raise EvaluationError("D33DO_SCHEMA_MISMATCH", "operational_release_id missing from release manifest")

    sources = manifest.get("source_bindings")
    if not isinstance(sources, dict) or not REQUIRED_SOURCE_BINDINGS.issubset(sources):
        raise EvaluationError("D33DO_LINEAGE_MISMATCH", "required Stage33D source bindings are absent")
    source_paths = {
        name: resolve_binding_path(release, sources[name], f"source:{name}")
        for name in REQUIRED_SOURCE_BINDINGS
    }
    for name, item in sources.items():
        if not isinstance(item, dict):
            raise EvaluationError("D33DO_LINEAGE_MISMATCH", f"malformed source binding: {name}")
        resolve_binding_path(release, item, f"source:{name}")
    design = read_json(source_paths["stage33d_resolved_design"], DESIGN_SCHEMA, passed=True)
    gates = read_json(source_paths["stage33d_acceptance_gates"], GATES_SCHEMA)
    completion = read_json(
        source_paths["stage33d_design_completion"], DESIGN_COMPLETION_SCHEMA, passed=True
    )
    if design.get("release_id") != "STAGE33D-PREDATA-DESIGN-01":
        raise EvaluationError("D33DO_LINEAGE_MISMATCH", "wrong frozen Stage33D design release")
    frozen = design.get("design", {})
    if not (
        frozen.get("total_columns") == 54
        and frozen.get("pet_columns") == 45
        and frozen.get("clean_columns") == 9
        and frozen.get("independent_pet_batches") == 15
    ):
        raise EvaluationError("D33DO_LINEAGE_MISMATCH", "Stage33D design counts are not frozen 54/45/9/15")
    if gates.get("required_batch_endpoints") != 15 or gates.get("monotonicity_is_not_a_gate") is not True:
        raise EvaluationError("D33DO_LINEAGE_MISMATCH", "Stage33D acceptance gates were altered")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise EvaluationError("D33DO_LINEAGE_MISMATCH", "release artifact bindings missing")
    for name, item in artifacts.items():
        if not isinstance(item, dict):
            raise EvaluationError("D33DO_LINEAGE_MISMATCH", f"malformed artifact binding: {name}")
        resolve_binding_path(release, item, f"artifact:{name}")
    paths = {
        name: verify_fixed_artifact(release, artifacts, name, relative)
        for name, relative in REQUIRED_ARTIFACTS.items()
    }
    morphology_path = paths["synthetic_morphology_summary"]
    added_files = {
        "operator_capture": release / "operator" / "operator_capture.csv",
        "darcy_linearity_capture": release / "operator" / "darcy_linearity_capture.csv",
        "sanitized_hydraulic_capture": release / "analyst" / "sanitized_hydraulic_capture.csv",
        "linearity_gate_attestation": release / "restricted" / "linearity_gate_attestation.json",
    }
    if any(not path.is_file() for path in added_files.values()):
        raise EvaluationError("D33DO_LINEAGE_MISMATCH", "prepared release additions are incomplete")
    paths.update({name: path.resolve() for name, path in added_files.items()})
    prepared_path = (release / "prepared_release_state.json").resolve()
    prepared = read_json(
        prepared_path, "pet.stage33do-prepared-release-state.v1", passed=True
    )
    if (
        prepared.get("operational_release_id") != release_id
        or prepared.get("state") != "CAPTURE_SANITIZED_AND_LINEARITY_ATTESTED_PRE_REVEAL"
        or prepared.get("test_only") is not True
    ):
        raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", "prepared release state is invalid")
    prepared_hashes = {
        "raw_operator_capture_sha256": paths["operator_capture"],
        "raw_linearity_capture_sha256": paths["darcy_linearity_capture"],
        "sanitized_hydraulic_capture_sha256": paths["sanitized_hydraulic_capture"],
        "linearity_gate_attestation_sha256": paths["linearity_gate_attestation"],
    }
    for field, path in prepared_hashes.items():
        if prepared.get(field) != sha256_file(path):
            raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", f"prepared hash mismatch: {field}")

    operator_manifest = read_json(paths["operator_manifest"], OPERATOR_MANIFEST_SCHEMA, passed=True)
    analyst_manifest = read_json(paths["analyst_manifest"], ANALYST_MANIFEST_SCHEMA, passed=True)
    restricted_manifest = read_json(paths["restricted_manifest"], RESTRICTED_MANIFEST_SCHEMA, passed=True)
    commitment = read_json(paths["cross_release_commitment"], COMMITMENT_SCHEMA, passed=True)
    attestation = read_json(
        paths["linearity_gate_attestation"], LINEARITY_ATTESTATION_SCHEMA, passed=True
    )
    for label, package, base in [
        ("operator_manifest", operator_manifest, release / "operator"),
        ("analyst_manifest", analyst_manifest, release / "analyst"),
        ("restricted_manifest", restricted_manifest, release / "restricted"),
    ]:
        declared = package.get("artifacts")
        if not isinstance(declared, dict):
            raise EvaluationError("D33DO_LINEAGE_MISMATCH", f"{label} artifact bindings absent")
        for name, item in declared.items():
            if not isinstance(item, dict):
                raise EvaluationError("D33DO_LINEAGE_MISMATCH", f"malformed {label} binding: {name}")
            resolve_binding_path(base, item, f"{label}:{name}")
    for label, item in [
        ("operator manifest", operator_manifest),
        ("analyst manifest", analyst_manifest),
        ("restricted manifest", restricted_manifest),
        ("cross-release commitment", commitment),
        ("linearity attestation", attestation),
    ]:
        if item.get("operational_release_id") != release_id:
            raise EvaluationError("D33DO_RELEASE_ID_MISMATCH", f"{label} release ID mismatch")

    verify_nested_binding(
        analyst_manifest,
        release / "analyst",
        "blinded_analysis_key",
        paths["blinded_analysis_key"],
        "analyst_manifest",
    )
    if morphology_path is not None:
        verify_nested_binding(
            analyst_manifest,
            release / "analyst",
            "synthetic_morphology_summary",
            morphology_path,
            "analyst_manifest",
        )
    for key in ["preparation_records"]:
        verify_nested_binding(
            restricted_manifest, release / "restricted", key, paths[key], "restricted_manifest"
        )

    if commitment.get("state") != "CUSTODIAN_COMMITTED_PREMEASUREMENT":
        raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", "wrong premeasurement commitment status")
    if commitment.get("operational_release_id", commitment.get("release_id")) != release_id:
        raise EvaluationError("D33DO_RELEASE_ID_MISMATCH", "premesurement commitment release ID mismatch")
    if not (
        commitment.get("test_only") is True
        and commitment.get("contains_raw_secret") is False
        and commitment.get("contains_treatment_key") is False
        and commitment.get("nonrestricted_contains_condition") is False
    ):
        raise EvaluationError("D33DO_TREATMENT_KEY_LEAKAGE", "key-separation commitment is incomplete")
    separation = commitment.get("key_separation")
    if not isinstance(separation, dict) or not all(
        separation.get(field) is True
        for field in [
            "treatment_key_absent_from_operator", "source_batch_absent_from_operator",
            "treatment_key_absent_from_analyst", "source_batch_absent_from_analyst",
            "operator_and_analyst_access_separated", "linearity_to_specimen_mapping_restricted",
        ]
    ):
        raise EvaluationError("D33DO_TREATMENT_KEY_LEAKAGE", "detailed key separation gates are incomplete")
    manifest_bindings = commitment.get("manifest_bindings")
    if not isinstance(manifest_bindings, dict):
        raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", "premesurement manifest bindings absent")
    for key, path in [
        ("operator_manifest", paths["operator_manifest"]),
        ("analyst_manifest", paths["analyst_manifest"]),
        ("restricted_manifest", paths["restricted_manifest"]),
    ]:
        if str(manifest_bindings.get(key, "")).lower() != sha256_file(path):
            raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", f"commitment hash mismatch: {key}")
    templates = commitment.get("template_sha256")
    if not isinstance(templates, dict):
        raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", "premesurement template hashes absent")
    template_paths = {
        "blinded_analysis_key": paths["blinded_analysis_key"],
        "synthetic_morphology_summary": paths["synthetic_morphology_summary"],
        "custodian_crosswalk": paths["custodian_crosswalk"],
        "preparation_records": paths["preparation_records"],
        "reveal_key": paths["reveal_key"],
        "linearity_crosswalk": paths["linearity_crosswalk"],
    }
    for key, path in template_paths.items():
        if str(templates.get(key, "")).lower() != sha256_file(path):
            raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", f"premesurement template mismatch: {key}")

    if attestation.get("darcy_linearity_capture_sha256") != sha256_file(paths["darcy_linearity_capture"]):
        raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", "linearity attestation raw hash mismatch")
    if attestation.get("evaluator_sha256") != sha256_file(Path(__file__).resolve()):
        raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", "linearity attestation evaluator hash mismatch")
    attested_rows = attestation.get("sentinels")
    if not isinstance(attested_rows, list) or len(attested_rows) != 6:
        raise EvaluationError("D33DO_DARCY_LINEARITY_FAILED", "linearity attestation is not six opaque rows")
    attested_ids: set[str] = set()
    for row in attested_rows:
        if not isinstance(row, dict):
            raise EvaluationError("D33DO_SCHEMA_MISMATCH", "malformed linearity attestation row")
        lid = row.get("opaque_linearity_id")
        if not isinstance(lid, str) or not lid or lid in attested_ids:
            raise EvaluationError("D33DO_DUPLICATE_IDENTITY", "bad/duplicate attested linearity ID")
        attested_ids.add(lid)
        if row.get("determination_n", 0) < 3 or row.get("passed") is not True:
            raise EvaluationError("D33DO_DARCY_LINEARITY_FAILED", f"failed attested linearity ID: {lid}")

    assert_blinded_package_no_treatment_leak(
        [
            paths["operator_manifest"],
            paths["operator_capture"],
            paths["darcy_linearity_capture"],
            paths["analyst_manifest"],
            paths["blinded_analysis_key"],
            paths["sanitized_hydraulic_capture"],
        ] + ([morphology_path] if morphology_path is not None else [])
    )
    return {
        "release_id": release_id,
        "manifest_path": manifest_path,
        "manifest": manifest,
        "design": design,
        "gates": gates,
        "completion": completion,
        "paths": paths,
        "morphology_path": morphology_path,
        "attestation": {**attestation, "rows": attested_rows},
    }


def evaluate_blinded(context: dict[str, Any]) -> dict[str, Any]:
    release_id = context["release_id"]
    paths = context["paths"]
    gates = context["gates"]
    capture_rows = read_csv_exact(paths["sanitized_hydraulic_capture"], OPERATOR_CAPTURE_FIELDS)
    analyst_rows = read_csv_exact(paths["blinded_analysis_key"], ANALYST_KEY_FIELDS)
    prep_rows = read_csv_exact(paths["preparation_records"], PREPARATION_FIELDS)
    linearity_rows = read_csv_exact(paths["darcy_linearity_capture"], LINEARITY_FIELDS)
    for name, rows in [
        ("sanitized_hydraulic_capture", capture_rows),
        ("blinded_analysis_key", analyst_rows),
        ("preparation_records", prep_rows),
        ("darcy_linearity_capture", linearity_rows),
    ]:
        require_release_id(rows, release_id, name)

    if len(capture_rows) != 54 or len(analyst_rows) != 54 or len(prep_rows) != 54:
        raise EvaluationError("D33DO_INCOMPLETE_RELEASE", "capture/map/preparation must each have exactly 54 rows")
    assert_unique(capture_rows, ("opaque_specimen_id",), "operator capture")
    assert_unique(analyst_rows, ("opaque_specimen_id",), "analyst key")
    assert_unique(prep_rows, ("opaque_specimen_id",), "preparation records")
    capture_by_id = {row["opaque_specimen_id"].strip(): row for row in capture_rows}
    analyst_by_id = {row["opaque_specimen_id"].strip(): row for row in analyst_rows}
    prep_by_id = {row["opaque_specimen_id"].strip(): row for row in prep_rows}
    if set(capture_by_id) != set(analyst_by_id) or set(capture_by_id) != set(prep_by_id):
        raise EvaluationError("D33DO_IDENTITY_MISMATCH", "specimen identities differ across frozen inputs")

    matched_sets: dict[str, list[dict[str, str]]] = {}
    pet_codes: dict[str, list[str]] = {}
    clean_count = 0
    pet_count = 0
    for sid, row in analyst_by_id.items():
        matched = require_text(row, "opaque_matched_set_id", f"analyst map {sid}")
        role = row["specimen_role"].strip()
        code = row["analyst_batch_code"].strip()
        if role not in {"clean_lbs_control", "pet_mixture"}:
            raise EvaluationError("D33DO_SCHEMA_MISMATCH", f"unsupported specimen_role for {sid}: {role}")
        if role == "clean_lbs_control":
            clean_count += 1
            if code:
                raise EvaluationError("D33DO_TREATMENT_KEY_LEAKAGE", f"clean specimen has analyst batch code: {sid}")
        else:
            pet_count += 1
            if not code:
                raise EvaluationError("D33DO_BATCH_MISSING_OR_POOLED", f"PET specimen lacks batch code: {sid}")
            if code.upper() in CONDITIONS or re.search(r"S33A-B\d+", code, re.IGNORECASE):
                raise EvaluationError("D33DO_TREATMENT_KEY_LEAKAGE", "analyst batch code leaks treatment/source")
            pet_codes.setdefault(code, []).append(sid)
        matched_sets.setdefault(matched, []).append(row)
        if prep_by_id[sid]["opaque_matched_set_id"].strip() != matched:
            raise EvaluationError("D33DO_IDENTITY_MISMATCH", f"preparation matched-set mismatch: {sid}")
    if clean_count != 9 or pet_count != 45 or len(matched_sets) != 9 or len(pet_codes) != 15:
        raise EvaluationError("D33DO_BATCH_MISSING_OR_POOLED", "design is not exactly 9 clean/45 PET/9 sets/15 batches")
    for matched, rows in matched_sets.items():
        roles = [row["specimen_role"].strip() for row in rows]
        codes = [row["analyst_batch_code"].strip() for row in rows if row["specimen_role"].strip() == "pet_mixture"]
        if len(rows) != 6 or roles.count("clean_lbs_control") != 1 or len(set(codes)) != 5:
            raise EvaluationError("D33DO_BATCH_MISSING_OR_POOLED", f"malformed matched set: {matched}")
    for code, ids in pet_codes.items():
        sets = {analyst_by_id[sid]["opaque_matched_set_id"].strip() for sid in ids}
        if len(ids) != 3 or len(sets) != 3:
            raise EvaluationError("D33DO_BATCH_MISSING_OR_POOLED", f"batch is not three independent matched columns: {code}")

    calc_tol = float(gates["calculation_crosscheck_maximum_relative_error"])
    target_e = float(gates["target_total_solid_void_ratio"])
    e_tol = float(gates["void_ratio_absolute_tolerance"])
    target_temp = float(gates["water_temperature_c"])
    temp_tol = float(gates["water_temperature_tolerance_c"])
    target_dose = float(gates["target_pet_dry_mass_percent"])
    dose_abs = float(gates["pet_dose_absolute_tolerance_wt_percent"])
    dose_rel = float(gates["pet_dose_relative_tolerance"])

    specimens: list[dict[str, Any]] = []
    for sid in sorted(capture_by_id):
        capture = capture_by_id[sid]
        analyst = analyst_by_id[sid]
        prep = prep_by_id[sid]
        role = analyst["specimen_role"].strip()
        reasons: list[str] = []

        for field in [
            "balance_calibration_id", "sand_lot_id", "mixing_protocol_id", "packing_protocol_id",
            "preparation_utc", "custodian_id",
        ]:
            require_text(prep, field, f"preparation {sid}")
        operator_valid = parse_bool(capture["measurement_valid"], f"capture eligibility {sid}")
        operator_reason = capture["measurement_rejection_reason"].strip()
        prep_valid = parse_bool(prep["pre_measurement_eligible"], f"preparation eligibility {sid}")
        prep_reason = prep["pre_measurement_rejection_reason"].strip()
        if operator_valid != prep_valid:
            raise EvaluationError("D33DO_ELIGIBILITY_CONFLICT", f"capture/preparation eligibility conflict: {sid}")
        if operator_valid and (operator_reason or prep_reason):
            raise EvaluationError("D33DO_ELIGIBILITY_CONFLICT", f"eligible specimen has rejection reason: {sid}")
        if not operator_valid and not (operator_reason and prep_reason):
            raise EvaluationError("D33DO_ELIGIBILITY_CONFLICT", f"ineligible specimen lacks both rejection reasons: {sid}")
        if not operator_valid:
            reasons.append("premeasurement_ineligible")

        prep_dry_sand = parse_float(prep, "dry_sand_mass_g", f"preparation {sid}", positive=True)
        dry_pet = parse_float(prep, "dry_pet_mass_g", f"preparation {sid}", nonnegative=True)
        achieved = 100.0 * dry_pet / prep_dry_sand
        supplied_achieved = parse_float(
            prep, "achieved_pet_dry_mass_percent", f"preparation {sid}", nonnegative=True
        )
        if abs(supplied_achieved - achieved) > max(1e-12, calc_tol * max(achieved, dose_abs)):
            raise EvaluationError("D33DO_CROSSCHECK_FAILED", f"achieved PET dose mismatch: {sid}")
        if role == "clean_lbs_control":
            if achieved > dose_abs:
                reasons.append("clean_pet_dose_above_frozen_blank_tolerance")
        elif abs(achieved - target_dose) > max(dose_abs, dose_rel * target_dose):
            reasons.append("pet_dose_outside_frozen_tolerance")

        initial_e = parse_float(prep, "initial_total_solid_void_ratio", f"preparation {sid}")
        temp = parse_float(capture, "water_temperature_c", sid)
        if abs(initial_e - target_e) > e_tol:
            reasons.append("initial_void_ratio_outside_frozen_tolerance")
        if abs(temp - target_temp) > temp_tol:
            reasons.append("water_temperature_outside_frozen_tolerance")
        if not parse_bool(capture["saturated"], f"saturated {sid}"):
            reasons.append("saturation_qc_failed")
        if not parse_bool(capture["leak_free"], f"leak_free {sid}"):
            reasons.append("leak_qc_failed")
        if not parse_bool(capture["steady_state"], f"steady_state {sid}"):
            reasons.append("steady_flow_qc_failed")
        if parse_bool(capture["effluent_pet_detected"], f"effluent_pet_detected {sid}"):
            reasons.append("fixed_solid_effluent_pet_detected")

        diameter = parse_float(capture, "specimen_diameter_mm", sid, positive=True)
        length = parse_float(capture, "specimen_length_mm", sid, positive=True)
        head = parse_float(capture, "head_difference_m", sid, positive=True)
        time_s = parse_float(capture, "collection_time_s", sid, positive=True)
        mass = parse_float(capture, "collected_water_mass_g", sid, positive=True)
        values = hydraulic_values(temp, diameter, length, head, time_s, mass)
        supplied_k20 = parse_float(capture, "calculated_K20_m_s", sid, positive=True)
        if relative_error(supplied_k20, values["K20_m_s"]) > calc_tol:
            raise EvaluationError("D33DO_CROSSCHECK_FAILED", f"supplied K20 mismatch: {sid}")
        specimens.append({
            "operational_release_id": release_id,
            "opaque_specimen_id": sid,
            "opaque_matched_set_id": analyst["opaque_matched_set_id"].strip(),
            "analyst_batch_code": analyst["analyst_batch_code"].strip(),
            "specimen_role": role,
            "pre_reveal_eligible": not reasons,
            "eligibility_reasons": reasons,
            "K_raw_m_s": values["K_raw_m_s"],
            "K20_m_s": values["K20_m_s"],
            "matched_clean_K20_m_s": None,
            "log_ratio_to_matched_clean": None,
            "ratio_to_matched_clean": None,
        })

    specimens_by_set: dict[str, list[dict[str, Any]]] = {}
    for row in specimens:
        specimens_by_set.setdefault(row["opaque_matched_set_id"], []).append(row)
    for matched, rows in specimens_by_set.items():
        clean = [row for row in rows if row["specimen_role"] == "clean_lbs_control"]
        if len(clean) != 1:
            raise EvaluationError("D33DO_BATCH_MISSING_OR_POOLED", f"matched clean count is not one: {matched}")
        clean_row = clean[0]
        for row in rows:
            if row["specimen_role"] != "pet_mixture":
                continue
            if not clean_row["pre_reveal_eligible"]:
                row["pre_reveal_eligible"] = False
                row["eligibility_reasons"].append("matched_clean_ineligible")
            if row["pre_reveal_eligible"]:
                row["matched_clean_K20_m_s"] = clean_row["K20_m_s"]
                log_ratio = math.log(row["K20_m_s"]) - math.log(clean_row["K20_m_s"])
                row["log_ratio_to_matched_clean"] = log_ratio
                row["ratio_to_matched_clean"] = math.exp(log_ratio)

    batch_rows: list[dict[str, Any]] = []
    for code in sorted(pet_codes):
        ratios = [
            row["log_ratio_to_matched_clean"]
            for row in specimens
            if row["analyst_batch_code"] == code and row["pre_reveal_eligible"]
        ]
        if len(ratios) < int(gates["minimum_valid_matched_sets_per_batch"]):
            raise EvaluationError(
                "D33DO_ELIGIBILITY_GATE_FAILED",
                f"batch {code} lacks minimum valid matched sets",
            )
        mean_log = statistics.fmean(ratios)
        batch_rows.append({
            "operational_release_id": release_id,
            "analyst_batch_code": code,
            "valid_matched_sets": len(ratios),
            "batch_log_ratio": mean_log,
            "batch_geometric_ratio": math.exp(mean_log),
            "within_batch_log_ratio_sd": statistics.stdev(ratios) if len(ratios) > 1 else None,
        })
    if len(batch_rows) != int(gates["required_batch_endpoints"]):
        raise EvaluationError("D33DO_ELIGIBILITY_GATE_FAILED", "not all 15 blinded batch endpoints are available")

    # Independent raw linearity recomputation occurs without the restricted
    # linearity-to-specimen crosswalk or treatment reveal.
    if len(linearity_rows) != 18:
        raise EvaluationError("D33DO_DARCY_LINEARITY_FAILED", "linearity capture is not exactly 18 determinations")
    assert_unique(linearity_rows, ("opaque_linearity_id", "gradient_sequence"), "linearity")
    linearity_by_id: dict[str, list[dict[str, float]]] = {}
    for row in linearity_rows:
        lid = require_text(row, "opaque_linearity_id", "linearity")
        sequence = parse_int(row, "gradient_sequence", f"linearity {lid}", positive=True)
        valid = parse_bool(row["measurement_valid"], f"linearity valid {lid}/{sequence}")
        reason = row["measurement_rejection_reason"].strip()
        require_text(row, "measured_utc", f"linearity {lid}/{sequence}")
        require_text(row, "operator_id", f"linearity {lid}/{sequence}")
        if valid and reason:
            raise EvaluationError("D33DO_ELIGIBILITY_CONFLICT", f"valid linearity row has reason: {lid}/{sequence}")
        if not valid:
            if not reason:
                raise EvaluationError("D33DO_ELIGIBILITY_CONFLICT", f"invalid linearity row lacks reason: {lid}/{sequence}")
            continue
        temp = parse_float(row, "water_temperature_c", f"linearity {lid}/{sequence}")
        diameter = parse_float(row, "specimen_diameter_mm", f"linearity {lid}/{sequence}", positive=True)
        length = parse_float(row, "specimen_length_mm", f"linearity {lid}/{sequence}", positive=True)
        head = parse_float(row, "head_difference_m", f"linearity {lid}/{sequence}", positive=True)
        time_s = parse_float(row, "collection_time_s", f"linearity {lid}/{sequence}", positive=True)
        mass = parse_float(row, "collected_water_mass_g", f"linearity {lid}/{sequence}", positive=True)
        if abs(temp - target_temp) > temp_tol:
            raise EvaluationError("D33DO_DARCY_LINEARITY_FAILED", f"linearity temperature outside gate: {lid}")
        values = hydraulic_values(temp, diameter, length, head, time_s, mass)
        reynolds = parse_float(
            row, "particle_reynolds_number", f"linearity {lid}/{sequence}", nonnegative=True
        )
        linearity_by_id.setdefault(lid, []).append({
            "sequence": float(sequence),
            "gradient": values["gradient"],
            "discharge": values["discharge_m3_s"],
            "K20": values["K20_m_s"],
            "particle_reynolds_number": reynolds,
        })
    if len(linearity_by_id) != 6:
        raise EvaluationError("D33DO_DARCY_LINEARITY_FAILED", "linearity gate is not exactly six opaque IDs")
    linearity_summary: dict[str, dict[str, Any]] = {}
    linearity_gates = gates["darcy_linearity"]
    for lid, rows in sorted(linearity_by_id.items()):
        sequences = {int(row["sequence"]) for row in rows}
        gradients = [row["gradient"] for row in rows]
        discharges = [row["discharge"] for row in rows]
        ks = [row["K20"] for row in rows]
        r2 = r_squared(gradients, discharges)
        cv = sample_cv(ks)
        max_re = max(row["particle_reynolds_number"] for row in rows)
        passed = bool(
            len(rows) >= int(linearity_gates["minimum_distinct_positive_gradients"])
            and len(set(gradients)) >= int(linearity_gates["minimum_distinct_positive_gradients"])
            and len(sequences) == len(rows)
            and sequences == {1, 2, 3}
            and math.isfinite(r2)
            and r2 >= float(linearity_gates["minimum_discharge_gradient_r_squared"])
            and cv is not None
            and cv <= float(linearity_gates["maximum_K20_cv"])
            and max_re <= float(linearity_gates["maximum_particle_reynolds_number"])
        )
        if not passed:
            raise EvaluationError("D33DO_DARCY_LINEARITY_FAILED", f"frozen linearity gate failed: {lid}")
        linearity_summary[lid] = {
            "n": len(rows), "r_squared": r2, "K20_cv": cv,
            "maximum_particle_reynolds_number": max_re, "passed": True,
        }

    attested_by_id = {
        row["opaque_linearity_id"]: row for row in context["attestation"]["rows"]
    }
    if set(attested_by_id) != set(linearity_summary):
        raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", "attested/recomputed linearity IDs differ")
    for lid, summary in linearity_summary.items():
        attested = attested_by_id[lid]
        comparisons = [
            ("discharge_gradient_r_squared", summary["r_squared"]),
            ("K20_coefficient_of_variation", summary["K20_cv"]),
            ("maximum_particle_reynolds_number", summary["maximum_particle_reynolds_number"]),
        ]
        if int(attested.get("determination_n", -1)) != summary["n"]:
            raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", f"linearity n mismatch: {lid}")
        for field, calculated in comparisons:
            try:
                supplied = float(attested[field])
            except (KeyError, TypeError, ValueError) as exc:
                raise EvaluationError(
                    "D33DO_SCHEMA_MISMATCH", f"invalid attested {field}: {lid}"
                ) from exc
            if not math.isfinite(supplied) or relative_error(supplied, calculated) > calc_tol:
                raise EvaluationError(
                    "D33DO_COMMITMENT_CHAIN_FAILED", f"attested {field} mismatch: {lid}"
                )

    # Freeze hashes use treatment-free, source-free canonical rows.  The key
    # has not been read at this point.
    specimens.sort(key=lambda row: row["opaque_specimen_id"])
    batch_rows.sort(key=lambda row: row["analyst_batch_code"])
    specimen_freeze_records = [
        {field: row[field] for field in SPECIMEN_OUTPUT_FIELDS} for row in specimens
    ]
    batch_freeze_records = [
        {field: row[field] for field in BATCH_OUTPUT_FIELDS} for row in batch_rows
    ]
    specimen_freeze_hash = canonical_records_hash(
        specimen_freeze_records, "pet.stage33do.blinded-specimen-records.v1"
    )
    batch_freeze_hash = canonical_records_hash(
        batch_freeze_records, "pet.stage33do.blinded-batch-endpoints.v1"
    )
    exclusion_rows = [
        {
            "operational_release_id": row["operational_release_id"],
            "opaque_specimen_id": row["opaque_specimen_id"],
            "pre_reveal_eligible": row["pre_reveal_eligible"],
            "eligibility_reasons": row["eligibility_reasons"],
            "exclusion_rule_source": "frozen_stage33d_acceptance_gates_v1",
        }
        for row in specimens
    ]
    exclusion_freeze_hash = canonical_records_hash(
        exclusion_rows, "pet.stage33do.blinded-exclusion-ledger.v1"
    )
    return {
        "capture_rows": capture_rows,
        "analyst_rows": analyst_rows,
        "analyst_by_id": analyst_by_id,
        "specimens": specimens,
        "batch_rows": batch_rows,
        "linearity_summary": linearity_summary,
        "specimen_freeze_hash": specimen_freeze_hash,
        "batch_freeze_hash": batch_freeze_hash,
        "exclusion_rows": exclusion_rows,
        "exclusion_freeze_hash": exclusion_freeze_hash,
    }


def _optional_float(raw: str, context: str) -> float | None:
    token = raw.strip()
    if not token:
        return None
    try:
        value = float(token)
    except ValueError as exc:
        raise EvaluationError("D33DO_MALFORMED_DATA", f"invalid numeric value for {context}") from exc
    if not math.isfinite(value):
        raise EvaluationError("D33DO_MALFORMED_DATA", f"nonfinite numeric value for {context}")
    return value


def load_frozen_pre_reveal(
    context: dict[str, Any], pre_dir: Path
) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    """Verify primary freeze before opening either restricted reveal mapping."""
    release_id = context["release_id"]
    required = {
        "specimen_results.csv": pre_dir / "specimen_results.csv",
        "batch_endpoints.csv": pre_dir / "batch_endpoints.csv",
        "exclusion_ledger.csv": pre_dir / "exclusion_ledger.csv",
        "pre_reveal_evaluation.json": pre_dir / "pre_reveal_evaluation.json",
        "completion.json": pre_dir / "completion.json",
    }
    if any(not path.is_file() for path in required.values()):
        raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", "pre-reveal artifact set is incomplete")
    completion = read_json(
        required["completion.json"],
        "pet.stage33do-matched-hydraulics-pre-reveal-completion.v1",
        passed=True,
    )
    pre_eval = read_json(
        required["pre_reveal_evaluation.json"],
        "pet.stage33do-matched-hydraulics-pre-reveal-evaluation.v1",
        passed=True,
    )
    if completion.get("operational_release_id") != release_id or pre_eval.get("operational_release_id") != release_id:
        raise EvaluationError("D33DO_RELEASE_ID_MISMATCH", "pre-reveal release ID mismatch")
    completion_artifacts = completion.get("artifacts")
    if not isinstance(completion_artifacts, dict):
        raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", "pre-reveal completion bindings absent")
    for name, path in required.items():
        if name == "completion.json":
            continue
        item = completion_artifacts.get(name)
        if not isinstance(item, dict):
            raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", f"completion binding missing: {name}")
        bound = resolve_binding_path(pre_dir, item, f"pre_reveal_completion:{name}")
        if bound != path.resolve():
            raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", f"completion path mismatch: {name}")

    raw_specimens = read_csv_exact(required["specimen_results.csv"], SPECIMEN_OUTPUT_FIELDS)
    raw_batches = read_csv_exact(required["batch_endpoints.csv"], BATCH_OUTPUT_FIELDS)
    raw_exclusions = read_csv_exact(required["exclusion_ledger.csv"], EXCLUSION_OUTPUT_FIELDS)
    if len(raw_specimens) != 54 or len(raw_batches) != 15 or len(raw_exclusions) != 54:
        raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", "pre-reveal record counts are not 54/15/54")
    assert_unique(raw_specimens, ("opaque_specimen_id",), "frozen specimen results")
    assert_unique(raw_batches, ("analyst_batch_code",), "frozen batch endpoints")
    assert_unique(raw_exclusions, ("opaque_specimen_id",), "frozen exclusion ledger")

    specimen_rows: list[dict[str, Any]] = []
    for row in raw_specimens:
        reasons_raw = row["eligibility_reasons"].strip()
        try:
            reasons = json.loads(reasons_raw)
        except json.JSONDecodeError as exc:
            raise EvaluationError("D33DO_MALFORMED_DATA", "invalid frozen eligibility reasons") from exc
        if not isinstance(reasons, list) or any(not isinstance(value, str) for value in reasons):
            raise EvaluationError("D33DO_MALFORMED_DATA", "eligibility reasons are not a string list")
        specimen_rows.append({
            **row,
            "pre_reveal_eligible": parse_bool(
                row["pre_reveal_eligible"], f"frozen specimen {row['opaque_specimen_id']}"
            ),
            "eligibility_reasons": reasons,
            "K_raw_m_s": _optional_float(row["K_raw_m_s"], "K_raw_m_s"),
            "K20_m_s": _optional_float(row["K20_m_s"], "K20_m_s"),
            "matched_clean_K20_m_s": _optional_float(
                row["matched_clean_K20_m_s"], "matched_clean_K20_m_s"
            ),
            "log_ratio_to_matched_clean": _optional_float(
                row["log_ratio_to_matched_clean"], "log_ratio_to_matched_clean"
            ),
            "ratio_to_matched_clean": _optional_float(
                row["ratio_to_matched_clean"], "ratio_to_matched_clean"
            ),
        })
    batch_rows: list[dict[str, Any]] = []
    for row in raw_batches:
        batch_rows.append({
            **row,
            "valid_matched_sets": int(row["valid_matched_sets"]),
            "batch_log_ratio": float(row["batch_log_ratio"]),
            "batch_geometric_ratio": float(row["batch_geometric_ratio"]),
            "within_batch_log_ratio_sd": _optional_float(
                row["within_batch_log_ratio_sd"], "within_batch_log_ratio_sd"
            ),
        })
    exclusion_by_id = {row["opaque_specimen_id"]: row for row in raw_exclusions}
    for row in specimen_rows:
        excluded = exclusion_by_id[row["opaque_specimen_id"]]
        if parse_bool(excluded["pre_reveal_eligible"], "frozen exclusion") != row["pre_reveal_eligible"]:
            raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", "exclusion/specimen eligibility mismatch")
        try:
            reasons = json.loads(excluded["eligibility_reasons"])
        except json.JSONDecodeError as exc:
            raise EvaluationError("D33DO_MALFORMED_DATA", "invalid exclusion ledger reasons") from exc
        if reasons != row["eligibility_reasons"]:
            raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", "exclusion/specimen reasons mismatch")

    specimen_hash = canonical_records_hash(
        [{field: row[field] for field in SPECIMEN_OUTPUT_FIELDS} for row in specimen_rows],
        "pet.stage33do.blinded-specimen-records.v1",
    )
    batch_hash = canonical_records_hash(
        [{field: row[field] for field in BATCH_OUTPUT_FIELDS} for row in batch_rows],
        "pet.stage33do.blinded-batch-endpoints.v1",
    )
    if pre_eval.get("blinded_specimen_records_sha256") != specimen_hash:
        raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", "pre-reveal specimen canonical hash mismatch")
    if pre_eval.get("blinded_batch_endpoints_sha256") != batch_hash:
        raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", "pre-reveal batch canonical hash mismatch")
    exclusion_records = [
        {
            "operational_release_id": row["operational_release_id"],
            "opaque_specimen_id": row["opaque_specimen_id"],
            "pre_reveal_eligible": row["pre_reveal_eligible"],
            "eligibility_reasons": row["eligibility_reasons"],
            "exclusion_rule_source": "frozen_stage33d_acceptance_gates_v1",
        }
        for row in specimen_rows
    ]
    exclusion_hash = canonical_records_hash(
        exclusion_records, "pet.stage33do.blinded-exclusion-ledger.v1"
    )
    if pre_eval.get("blinded_exclusion_ledger_sha256") != exclusion_hash:
        raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", "pre-reveal exclusion canonical hash mismatch")

    release = context["manifest_path"].parent
    primary_path = (release / "restricted" / "primary_freeze_commitment.json").resolve()
    declaration_path = (release / "restricted" / "reveal_declaration.json").resolve()
    reveal_path = (release / "restricted" / "reveal_key.csv").resolve()
    crosswalk_path = (release / "restricted" / "linearity_crosswalk.csv").resolve()
    for path in [primary_path, declaration_path, reveal_path, crosswalk_path]:
        if not path.is_file():
            raise EvaluationError("D33DO_REVEAL_NOT_AUTHORIZED", f"post-reveal artifact missing: {path.name}")
    primary = read_json(primary_path, PRIMARY_FREEZE_SCHEMA, passed=True)
    if primary.get("operational_release_id") != release_id:
        raise EvaluationError("D33DO_RELEASE_ID_MISMATCH", "primary-freeze release ID mismatch")
    if (
        primary.get("status") != "PRIMARY_ENDPOINTS_FROZEN_REVEAL_AUTHORIZED"
        or primary.get("state") != "PRIMARY_ENDPOINTS_FROZEN_REVEAL_AUTHORIZED"
        or primary.get("test_only") is not True
        or primary.get("no_empirical_data") is not True
        or primary.get("pre_reveal_phase") != "pre_reveal"
    ):
        raise EvaluationError("D33DO_REVEAL_NOT_AUTHORIZED", "primary freeze does not authorize reveal")
    if primary.get("cross_release_commitment_sha256") != sha256_file(context["paths"]["cross_release_commitment"]):
        raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", "primary freeze premeasurement hash mismatch")
    primary_file_fields = {
        "sanitized_hydraulic_capture_sha256": context["paths"]["sanitized_hydraulic_capture"],
        "raw_operator_capture_sha256": context["paths"]["operator_capture"],
        "raw_linearity_capture_sha256": context["paths"]["darcy_linearity_capture"],
        "linearity_gate_attestation_sha256": context["paths"]["linearity_gate_attestation"],
        "blinded_analysis_key_sha256": context["paths"]["blinded_analysis_key"],
        "preparation_records_sha256": context["paths"]["preparation_records"],
        "synthetic_morphology_summary_sha256": context["morphology_path"],
        "pre_reveal_specimen_results_sha256": required["specimen_results.csv"],
        "pre_reveal_batch_endpoints_sha256": required["batch_endpoints.csv"],
        "pre_reveal_exclusion_ledger_sha256": required["exclusion_ledger.csv"],
        "pre_reveal_evaluation_sha256": required["pre_reveal_evaluation.json"],
        "release_manifest_sha256": context["manifest_path"],
    }
    for field, path in primary_file_fields.items():
        if primary.get(field) != sha256_file(path):
            raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", f"primary freeze mismatch: {field}")
    if primary.get("evaluator_sha256") != sha256_file(Path(__file__).resolve()):
        raise EvaluationError("D33DO_LINEAGE_MISMATCH", "primary freeze evaluator mismatch")
    sealer_binding = context["manifest"]["source_bindings"].get("stage33do_primary_freeze_sealer")
    if not isinstance(sealer_binding, dict):
        raise EvaluationError("D33DO_LINEAGE_MISMATCH", "sealer source binding absent")
    sealer_path = resolve_binding_path(release, sealer_binding, "source:stage33do_primary_freeze_sealer")
    if primary.get("sealer_sha256") != sha256_file(sealer_path):
        raise EvaluationError("D33DO_LINEAGE_MISMATCH", "primary freeze sealer mismatch")

    declaration = read_json(declaration_path, REVEAL_DECLARATION_SCHEMA, passed=True)
    if declaration.get("operational_release_id") != release_id:
        raise EvaluationError("D33DO_RELEASE_ID_MISMATCH", "reveal declaration release ID mismatch")
    if (
        declaration.get("status") != "REVEAL_DECLARED_AFTER_PRIMARY_FREEZE"
        or declaration.get("state") != "REVEAL_DECLARED_AFTER_PRIMARY_FREEZE"
        or declaration.get("test_only") is not True
    ):
        raise EvaluationError("D33DO_REVEAL_NOT_AUTHORIZED", "wrong reveal declaration status")
    if declaration.get("primary_freeze_commitment_sha256") != sha256_file(primary_path):
        raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", "reveal declaration primary hash mismatch")
    if declaration.get("reveal_key_sha256") != sha256_file(reveal_path):
        raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", "reveal declaration key hash mismatch")
    if declaration.get("pre_reveal_batch_endpoints_sha256") != sha256_file(required["batch_endpoints.csv"]):
        raise EvaluationError("D33DO_COMMITMENT_CHAIN_FAILED", "reveal declaration batch freeze mismatch")

    # The two restricted mappings are parsed only after every preceding freeze
    # check has succeeded.
    reveal_rows = read_csv_exact(reveal_path, REVEAL_FIELDS)
    crosswalk_rows = read_csv_exact(crosswalk_path, LINEARITY_CROSSWALK_FIELDS)
    analyst_rows = read_csv_exact(context["paths"]["blinded_analysis_key"], ANALYST_KEY_FIELDS)
    analyst_by_id = {row["opaque_specimen_id"].strip(): row for row in analyst_rows}
    attestation_rows = context["attestation"]["rows"]
    linearity_summary = {
        row["opaque_linearity_id"]: {
            "n": row["determination_n"],
            "r_squared": row["discharge_gradient_r_squared"],
            "K20_cv": row["K20_coefficient_of_variation"],
            "maximum_particle_reynolds_number": row["maximum_particle_reynolds_number"],
            "passed": row["passed"],
        }
        for row in attestation_rows
    }
    blinded = {
        "specimens": specimen_rows,
        "batch_rows": batch_rows,
        "analyst_rows": analyst_rows,
        "analyst_by_id": analyst_by_id,
        "linearity_summary": linearity_summary,
        "specimen_freeze_hash": specimen_hash,
        "batch_freeze_hash": batch_hash,
    }
    post_bindings = {
        "primary_freeze_commitment": binding(primary_path),
        "reveal_declaration": binding(declaration_path),
        "reveal_key": binding(reveal_path),
        "linearity_crosswalk": binding(crosswalk_path),
    }
    return blinded, reveal_rows, crosswalk_rows, post_bindings


def evaluate_revealed(
    context: dict[str, Any], blinded: dict[str, Any], reveal_rows: list[dict[str, str]],
    crosswalk_rows: list[dict[str, str]],
) -> dict[str, Any]:
    """Use mappings supplied only after the primary freeze chain passed."""
    release_id = context["release_id"]
    require_release_id(reveal_rows, release_id, "reveal_key")
    require_release_id(crosswalk_rows, release_id, "linearity_crosswalk")
    if len(reveal_rows) != 15 or len(crosswalk_rows) != 6:
        raise EvaluationError("D33DO_REVEAL_KEY_INVALID", "reveal/crosswalk counts are not 15/6")
    assert_unique(reveal_rows, ("analyst_batch_code",), "reveal key")
    assert_unique(reveal_rows, ("source_batch_slot",), "reveal source batch")
    assert_unique(crosswalk_rows, ("opaque_linearity_id",), "linearity crosswalk")
    assert_unique(crosswalk_rows, ("opaque_specimen_id",), "linearity specimen crosswalk")

    reveal_by_code: dict[str, dict[str, Any]] = {}
    condition_block_pairs: set[tuple[str, int]] = set()
    for row in reveal_rows:
        code = require_text(row, "analyst_batch_code", "reveal key")
        condition = row["condition_id"].strip()
        block = parse_int(row, "reactor_block", f"reveal {code}", positive=True)
        require_text(row, "source_batch_slot", f"reveal {code}")
        if condition not in CONDITIONS or block not in {1, 2, 3}:
            raise EvaluationError("D33DO_REVEAL_KEY_INVALID", f"invalid condition/block for {code}")
        pair = (condition, block)
        if pair in condition_block_pairs:
            raise EvaluationError("D33DO_REVEAL_KEY_INVALID", f"duplicate condition/block: {pair}")
        condition_block_pairs.add(pair)
        reveal_by_code[code] = {"condition_id": condition, "reactor_block": block}
    batch_codes = {row["analyst_batch_code"] for row in blinded["batch_rows"]}
    if set(reveal_by_code) != batch_codes or condition_block_pairs != {
        (condition, block) for condition in CONDITIONS for block in (1, 2, 3)
    }:
        raise EvaluationError("D33DO_REVEAL_KEY_INVALID", "reveal is not the exact 5-condition x 3-block key")

    analyst_by_id = blinded["analyst_by_id"]
    lids = set(blinded["linearity_summary"])
    if {row["opaque_linearity_id"].strip() for row in crosswalk_rows} != lids:
        raise EvaluationError("D33DO_REVEAL_KEY_INVALID", "linearity crosswalk identity set mismatch")
    sentinel_counts = {"clean_lbs_control": 0, "pet_mixture": 0}
    sentinel_blocks = {"clean_lbs_control": set(), "pet_mixture": set()}
    for row in crosswalk_rows:
        sid = row["opaque_specimen_id"].strip()
        if sid not in analyst_by_id:
            raise EvaluationError("D33DO_REVEAL_KEY_INVALID", f"unknown sentinel specimen: {sid}")
        analyst = analyst_by_id[sid]
        role = analyst["specimen_role"].strip()
        sentinel_counts[role] += 1
        if role == "pet_mixture":
            revealed = reveal_by_code[analyst["analyst_batch_code"].strip()]
            if revealed["condition_id"] != "T180":
                raise EvaluationError("D33DO_DARCY_LINEARITY_FAILED", "PET linearity sentinel is not T180")
            sentinel_blocks[role].add(revealed["reactor_block"])
        else:
            matched = analyst["opaque_matched_set_id"].strip()
            pet_codes = {
                item["analyst_batch_code"].strip()
                for item in analyst_by_id.values()
                if item["opaque_matched_set_id"].strip() == matched
                and item["specimen_role"].strip() == "pet_mixture"
            }
            blocks = {reveal_by_code[code]["reactor_block"] for code in pet_codes}
            if len(blocks) != 1:
                raise EvaluationError("D33DO_REVEAL_KEY_INVALID", "clean sentinel matched set spans blocks")
            sentinel_blocks[role].update(blocks)
    if sentinel_counts != {"clean_lbs_control": 3, "pet_mixture": 3} or any(
        blocks != {1, 2, 3} for blocks in sentinel_blocks.values()
    ):
        raise EvaluationError("D33DO_DARCY_LINEARITY_FAILED", "sentinels are not 3 clean + 3 T180 across blocks")

    endpoints: dict[tuple[str, int], float] = {}
    for row in blinded["batch_rows"]:
        code = row["analyst_batch_code"]
        revealed = reveal_by_code[code]
        endpoints[(revealed["condition_id"], revealed["reactor_block"])] = row["batch_log_ratio"]

    # Each matched set must contain the five batches from one and only one
    # reactor block, one per condition.
    sets: dict[str, list[dict[str, str]]] = {}
    for row in blinded["analyst_rows"]:
        sets.setdefault(row["opaque_matched_set_id"].strip(), []).append(row)
    set_to_block: dict[str, int] = {}
    for matched, rows in sets.items():
        codes = [row["analyst_batch_code"].strip() for row in rows if row["specimen_role"].strip() == "pet_mixture"]
        blocks = {reveal_by_code[code]["reactor_block"] for code in codes}
        conditions = {reveal_by_code[code]["condition_id"] for code in codes}
        if len(blocks) != 1 or conditions != set(CONDITIONS):
            raise EvaluationError("D33DO_REVEAL_KEY_INVALID", f"matched set not a complete within-block set: {matched}")
        set_to_block[matched] = next(iter(blocks))
    if any(list(set_to_block.values()).count(block) != 3 for block in (1, 2, 3)):
        raise EvaluationError("D33DO_REVEAL_KEY_INVALID", "reactor blocks do not each contain three matched sets")

    eligible_clean_by_block: dict[int, list[float]] = {1: [], 2: [], 3: []}
    for row in blinded["specimens"]:
        if row["specimen_role"] == "clean_lbs_control" and row["pre_reveal_eligible"]:
            eligible_clean_by_block[set_to_block[row["opaque_matched_set_id"]]].append(row["K20_m_s"])
    clean_cv_by_block: dict[str, float] = {}
    for block, values in eligible_clean_by_block.items():
        if len(values) < int(context["gates"]["minimum_valid_clean_controls_per_block"]):
            raise EvaluationError("D33DO_CLEAN_REPEATABILITY_FAILED", f"block {block} lacks valid clean controls")
        cv = sample_cv(values)
        if cv is None or cv > float(context["gates"]["maximum_clean_cv_within_block"]):
            raise EvaluationError("D33DO_CLEAN_REPEATABILITY_FAILED", f"block {block} clean CV exceeds gate")
        clean_cv_by_block[str(block)] = cv

    condition_rows: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        values = [endpoints[(condition, block)] for block in (1, 2, 3)]
        summary = mean_ci(values)
        condition_rows.append({
            "condition_id": condition,
            "n_batches": summary["n"],
            "mean_batch_log_ratio": summary["mean"],
            "geometric_mean_ratio": math.exp(float(summary["mean"])),
            "sample_sd_log_ratio": summary["sd"],
            "ci95_low_log_ratio": summary["low"],
            "ci95_high_log_ratio": summary["high"],
            "reactor_blocks_complete": True,
        })

    high_contrasts = [endpoints[("T180", b)] - endpoints[("T20", b)] for b in (1, 2, 3)]
    high_summary = mean_ci(high_contrasts)
    treated_slopes = []
    treated_conditions = ("T120", "T140", "T160", "T180")
    x = [0.0, 1.0, 2.0, 3.0]
    xm = statistics.fmean(x)
    sxx = sum((value - xm) ** 2 for value in x)
    for block in (1, 2, 3):
        y = [endpoints[(condition, block)] for condition in treated_conditions]
        ym = statistics.fmean(y)
        treated_slopes.append(sum((a - xm) * (b - ym) for a, b in zip(x, y)) / sxx)
    trend_summary = mean_ci(treated_slopes)

    morphology = None
    morphology_path = context["morphology_path"]
    if morphology_path is not None:
        rows = read_csv_exact(morphology_path, MORPHOLOGY_FIELDS)
        require_release_id(rows, release_id, "synthetic_morphology_summary")
        if len(rows) != 15:
            raise EvaluationError("D33DO_MORPHOLOGY_FIXTURE_INVALID", "morphology fixture is not 15 batches")
        assert_unique(rows, ("analyst_batch_code",), "morphology fixture")
        morphology_by_code = {}
        for row in rows:
            code = row["analyst_batch_code"].strip()
            morphology_by_code[code] = (
                parse_float(row, "log_d50_max_feret", f"morphology {code}"),
                parse_float(row, "measurement_se", f"morphology {code}", nonnegative=True),
            )
        if set(morphology_by_code) != batch_codes:
            raise EvaluationError("D33DO_MORPHOLOGY_FIXTURE_INVALID", "morphology batch identities mismatch")
        batch_by_code = {row["analyst_batch_code"]: row["batch_log_ratio"] for row in blinded["batch_rows"]}
        x_res: list[float] = []
        y_res: list[float] = []
        for block in (1, 2, 3):
            codes = [code for code, value in reveal_by_code.items() if value["reactor_block"] == block]
            xs = [morphology_by_code[code][0] for code in codes]
            ys = [batch_by_code[code] for code in codes]
            xbar, ybar = statistics.fmean(xs), statistics.fmean(ys)
            x_res.extend(value - xbar for value in xs)
            y_res.extend(value - ybar for value in ys)
        denominator = sum(value * value for value in x_res)
        slope = sum(a * b for a, b in zip(x_res, y_res)) / denominator if denominator > 0 else None
        morphology = {
            "evidence_role": "synthetic_test_only_no_empirical_or_degradation_claim",
            "n_independent_batches": 15,
            "block_adjusted_association_slope": slope,
            "measurement_uncertainty_propagated": False,
        }

    return {
        "condition_rows": condition_rows,
        "clean_cv_by_block": clean_cv_by_block,
        "high_severity_T180_minus_T20": high_summary,
        "treated_only_log_ratio_slope_per_20c": trend_summary,
        "morphology_association": morphology,
        "sentinel_counts": sentinel_counts,
    }


def _closed_authority() -> dict[str, bool]:
    return {
        "empirical_claim": False,
        "laboratory_execution": False,
        "numerical_execution": False,
        "model_calibration": False,
        "absolute_permeability_validation": False,
        "molecular_degradation_claim": False,
        "length_as_degradation_proxy_claim": False,
        "migration_or_clogging_claim": False,
        "mechanics_or_coupling_claim": False,
    }


def build_pre_evaluation(context: dict[str, Any], blinded: dict[str, Any]) -> dict[str, Any]:
    paths = context["paths"]
    input_bindings = {
        "release_manifest": binding(context["manifest_path"]),
        "sanitized_hydraulic_capture": binding(paths["sanitized_hydraulic_capture"]),
        "raw_operator_capture": binding(paths["operator_capture"]),
        "darcy_linearity_capture": binding(paths["darcy_linearity_capture"]),
        "blinded_analysis_key": binding(paths["blinded_analysis_key"]),
        "preparation_records": binding(paths["preparation_records"]),
        "linearity_gate_attestation": binding(paths["linearity_gate_attestation"]),
    }
    return {
        "schema": "pet.stage33do-matched-hydraulics-pre-reveal-evaluation.v1",
        "stage": "Stage33D-O",
        "phase": "pre_reveal",
        "test_only": True,
        "no_empirical_data": True,
        "authority": _closed_authority(),
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "operational_release_id": context["release_id"],
        "status": "blinded_primary_endpoints_computed_treatment_key_unread",
        "evidence_role": "synthetic_workflow_verification_only",
        "input_bindings": input_bindings,
        "specimen_n": len(blinded["specimens"]),
        "pet_n": sum(r["specimen_role"] == "pet_mixture" for r in blinded["specimens"]),
        "clean_n": sum(r["specimen_role"] == "clean_lbs_control" for r in blinded["specimens"]),
        "batch_n": len(blinded["batch_rows"]),
        "excluded_specimen_n": sum(not r["pre_reveal_eligible"] for r in blinded["specimens"]),
        "blinded_specimen_records_sha256": blinded["specimen_freeze_hash"],
        "blinded_batch_endpoints_sha256": blinded["batch_freeze_hash"],
        "blinded_exclusion_ledger_sha256": blinded["exclusion_freeze_hash"],
        "treatment_key_read": False,
        "recomputed": {
            "K20_exact_recomputation": True,
            "ratio_exact_recomputation": True,
            "water_density_formula": "Kell-type freshwater density equation as implemented",
            "water_viscosity_formula": "mu=2.414e-5*10^(247.8/(T+133.15)) Pa s",
            "K20_correction": "K20=Kraw*(mu_T/mu_20)*(rho_20/rho_T)",
        },
        "gates": {
            "lineage_schema_and_premeasurement_commitment_passed": True,
            "zero_treatment_source_leakage_in_operator_analyst_packages": True,
            "all_15_batch_endpoints_available": True,
            "minimum_two_valid_matched_sets_per_batch": True,
            "darcy_linearity_all_six_passed": True,
            "linearity_summary_by_opaque_id": blinded["linearity_summary"],
            "dose_state_temperature_saturation_leak_steady_fixed_solid_applied": True,
            "monotonicity_imposed": False,
            "condition_profile_authorized_before_reveal": False,
        },
        "claim_boundary": (
            "Blinded synthetic workflow verification only; no condition profile, empirical result, "
            "absolute-permeability validation, degradation, migration, clogging, mechanics, or coupling claim."
        ),
        "passed": True,
    }


def build_post_evaluation(
    context: dict[str, Any], blinded: dict[str, Any], revealed: dict[str, Any],
    post_bindings: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": EVALUATION_SCHEMA,
        "stage": "Stage33D-O",
        "phase": "post_reveal",
        "test_only": True,
        "no_empirical_data": True,
        "authority": _closed_authority(),
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "operational_release_id": context["release_id"],
        "status": "condition_profile_derived_after_primary_freeze_and_declared_reveal",
        "evidence_role": "synthetic_workflow_verification_only",
        "input_bindings": post_bindings,
        "primary_freeze_commitment_sha256": post_bindings["primary_freeze_commitment"]["sha256"],
        "reveal_declaration_sha256": post_bindings["reveal_declaration"]["sha256"],
        "pre_reveal": {
            "specimen_n": 54,
            "pet_n": 45,
            "clean_n": 9,
            "batch_n": 15,
            "blinded_specimen_records_sha256": blinded["specimen_freeze_hash"],
            "blinded_batch_endpoints_sha256": blinded["batch_freeze_hash"],
            "treatment_key_read_before_primary_freeze_verification": False,
        },
        "gates": {
            "primary_freeze_chain_passed": True,
            "separate_reveal_declaration_passed": True,
            "exact_five_condition_by_three_block_reveal": True,
            "clean_repeatability_cv_at_most_0p05_each_block": True,
            "clean_cv_by_block": revealed["clean_cv_by_block"],
            "sentinels_three_clean_three_T180_across_blocks": True,
            "monotonicity_imposed": False,
            "confirmatory_complete_block_profile_authorized": True,
        },
        "estimands": {
            "high_severity_T180_minus_T20": revealed["high_severity_T180_minus_T20"],
            "treated_only_log_ratio_slope_per_20c": revealed["treated_only_log_ratio_slope_per_20c"],
            "morphology_association": revealed["morphology_association"],
        },
        "claim_boundary": (
            "Synthetic batch-level matched K20 workflow only. No empirical, absolute-permeability, "
            "numerical-validation, degradation, migration, clogging, mechanics, deformation, or coupling claim."
        ),
        "passed": True,
    }


def _atomic_output_dir(output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.parent / f".{output.name}.tmp-{uuid.uuid4().hex}"
    temp.mkdir()
    return temp


def write_pre_success(
    output: Path, evaluation: dict[str, Any], specimen_rows: list[dict[str, Any]],
    batch_rows: list[dict[str, Any]], exclusion_rows: list[dict[str, Any]],
) -> None:
    temp = _atomic_output_dir(output)
    try:
        (temp / "specimen_results.csv").write_bytes(csv_bytes(SPECIMEN_OUTPUT_FIELDS, specimen_rows))
        (temp / "batch_endpoints.csv").write_bytes(csv_bytes(BATCH_OUTPUT_FIELDS, batch_rows))
        (temp / "exclusion_ledger.csv").write_bytes(csv_bytes(EXCLUSION_OUTPUT_FIELDS, exclusion_rows))
        evaluation["output_bindings"] = {
            name: binding(temp / name)
            for name in ["specimen_results.csv", "batch_endpoints.csv", "exclusion_ledger.csv"]
        }
        for name, item in evaluation["output_bindings"].items():
            item["path"] = str((output / name).resolve())
        evaluation_path = temp / "pre_reveal_evaluation.json"
        evaluation_path.write_text(
            json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        completion = {
            "schema": "pet.stage33do-matched-hydraulics-pre-reveal-completion.v1",
            "status": "complete",
            "operational_release_id": evaluation["operational_release_id"],
            "evaluation_sha256": sha256_file(evaluation_path),
            "artifacts": {
                name: {
                    "path": str((output / name).resolve()),
                    "sha256": sha256_file(temp / name),
                }
                for name in [
                    "specimen_results.csv", "batch_endpoints.csv", "exclusion_ledger.csv",
                    "pre_reveal_evaluation.json",
                ]
            },
            "passed": True,
        }
        (temp / "completion.json").write_text(
            json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        os.replace(temp, output)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def write_post_success(
    output: Path, pre_dir: Path, evaluation: dict[str, Any],
    condition_rows: list[dict[str, Any]],
) -> None:
    temp = _atomic_output_dir(output)
    try:
        shutil.copy2(pre_dir / "specimen_results.csv", temp / "specimen_results.csv")
        shutil.copy2(pre_dir / "batch_endpoints.csv", temp / "batch_endpoints.csv")
        condition_path = temp / "condition_summary.csv"
        condition_path.write_bytes(csv_bytes(CONDITION_OUTPUT_FIELDS, condition_rows))
        condition_hash = sha256_file(condition_path)
        evaluation["condition_summary_sha256"] = condition_hash
        evaluation["output_bindings"] = {
            "specimen_results.csv": {
                "path": str((output / "specimen_results.csv").resolve()),
                "sha256": sha256_file(temp / "specimen_results.csv"),
            },
            "batch_endpoints.csv": {
                "path": str((output / "batch_endpoints.csv").resolve()),
                "sha256": sha256_file(temp / "batch_endpoints.csv"),
            },
            "condition_summary.csv": {
                "path": str((output / "condition_summary.csv").resolve()),
                "sha256": condition_hash,
            }
        }
        evaluation_path = temp / "evaluation.json"
        evaluation_path.write_text(
            json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        completion = {
            "schema": "pet.stage33do-matched-hydraulics-evaluation-completion.v1",
            "status": "complete",
            "operational_release_id": evaluation["operational_release_id"],
            "evaluation_sha256": sha256_file(evaluation_path),
            "artifacts": {
                name: {
                    "path": str((output / name).resolve()),
                    "sha256": sha256_file(temp / name),
                }
                for name in [
                    "specimen_results.csv", "batch_endpoints.csv", "condition_summary.csv",
                    "evaluation.json",
                ]
            },
            "passed": True,
        }
        (temp / "completion.json").write_text(
            json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        os.replace(temp, output)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def write_failure(output: Path, exc: Exception) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.parent / f".{output.name}.tmp-{uuid.uuid4().hex}"
    temp.mkdir()
    try:
        failure = {
            "schema": "pet.stage33do-matched-hydraulics-evaluation-failure.v1",
            "status": "failed_closed",
            "error_code": exc.code if isinstance(exc, EvaluationError) else "D33DO_UNEXPECTED_ERROR",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "passed": False,
        }
        (temp / "failure.json").write_text(
            json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        os.replace(temp, output)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    release = args.release_dir.resolve()
    context = validate_release(release)
    if args.phase == "pre_reveal":
        if args.capture is None or args.linearity is None or args.pre_reveal_dir is not None:
            raise EvaluationError(
                "D33DO_CLI_INVALID",
                "pre_reveal requires --capture and --linearity and forbids --pre-reveal-dir",
            )
        capture = args.capture.resolve()
        linearity = args.linearity.resolve()
        expected_capture = (release / "analyst" / "sanitized_hydraulic_capture.csv").resolve()
        expected_linearity = (release / "operator" / "darcy_linearity_capture.csv").resolve()
        if capture != expected_capture or linearity != expected_linearity:
            raise EvaluationError(
                "D33DO_LINEAGE_MISMATCH",
                "pre_reveal capture/linearity must be the prepared hash-bound release files",
            )
        blinded = evaluate_blinded(context)
        evaluation = build_pre_evaluation(context, blinded)
        write_pre_success(
            args.output_dir.resolve(), evaluation, blinded["specimens"], blinded["batch_rows"],
            blinded["exclusion_rows"],
        )
        return evaluation

    if args.pre_reveal_dir is None or args.capture is not None or args.linearity is not None:
        raise EvaluationError(
            "D33DO_CLI_INVALID",
            "post_reveal requires --pre-reveal-dir and forbids --capture/--linearity",
        )
    pre_dir = args.pre_reveal_dir.resolve()
    blinded, reveal_rows, crosswalk_rows, post_bindings = load_frozen_pre_reveal(
        context, pre_dir
    )
    revealed = evaluate_revealed(context, blinded, reveal_rows, crosswalk_rows)
    evaluation = build_post_evaluation(context, blinded, revealed, post_bindings)
    write_post_success(
        args.output_dir.resolve(), pre_dir, evaluation, revealed["condition_rows"]
    )
    return evaluation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["pre_reveal", "post_reveal"], required=True)
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--linearity", type=Path)
    parser.add_argument("--pre-reveal-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        print(f"Refusing to overwrite immutable output: {output}", file=sys.stderr)
        return 2
    try:
        evaluation = evaluate(args)
    except Exception as exc:
        write_failure(output, exc)
        print(
            json.dumps(
                {
                    "status": "failed_closed",
                    "error_code": exc.code if isinstance(exc, EvaluationError) else "D33DO_UNEXPECTED_ERROR",
                    "error": str(exc),
                    "passed": False,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
                "output_dir": str(output),
                "phase": args.phase,
                "batch_n": evaluation.get("batch_n", evaluation.get("pre_reveal", {}).get("batch_n")),
                "confirmatory_complete_block_profile_authorized": evaluation["gates"].get(
                    "confirmatory_complete_block_profile_authorized", False
                ),
                "passed": True,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
