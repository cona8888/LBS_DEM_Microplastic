#!/usr/bin/env python3
"""Build an immutable, test-only Stage33D-O blinded release.

This builder qualifies package separation only.  It accepts a test secret and
synthetic preparation/morphology fixtures, derives fresh opaque identifiers,
and writes *blank measurement templates*.  It never accepts a real mode, never
stores the secret (or a fingerprint of it), and never authorizes reveal,
laboratory work, simulation, or a physical claim.

The output is created in a sibling temporary directory and atomically renamed
only after all lineage, count, schema, role-separation, and leakage checks pass.
An existing output path is never overwritten.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import io
import json
import math
import os
import re
import shutil
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DESIGN_DIR = (
    ROOT
    / "stage33_designs"
    / "stage33d_matched_pet_lbs_physical_validation_20260901"
    / "release_01"
)
DEFAULT_DESIGN_AUDIT = (
    ROOT
    / "stage33_evaluations"
    / "stage33d_matched_pet_lbs_physical_validation_20260901"
    / "design_audit_01"
    / "design_audit.json"
)
DEFAULT_CONTRACT = (
    ROOT
    / "stage33_staging"
    / "STAGE33DO_OPERATIONAL_WORKFLOW_SYNTHETIC_QUALIFICATION_CONTRACT_V1.md"
)

RELEASE_SCHEMA = "pet.stage33do-matched-hydraulics-operational-release.v1"
OPERATOR_MANIFEST_SCHEMA = "pet.stage33do-hydraulic-operator-package.v1"
ANALYST_MANIFEST_SCHEMA = "pet.stage33do-hydraulic-analyst-package.v1"
RESTRICTED_MANIFEST_SCHEMA = "pet.stage33do-hydraulic-restricted-package.v1"
COMMITMENT_SCHEMA = "pet.stage33do-cross-release-commitment.v1"
ROLES_SCHEMA = "pet.stage33do-semantic-roles.v1"
COMPLETION_SCHEMA = "pet.stage33do-synthetic-blinded-release-completion.v1"

DESIGN_SCHEMA = "pet.stage33d-matched-pet-lbs-physical-validation-design.v1"
DESIGN_COMPLETION_SCHEMA = (
    "pet.stage33d-matched-pet-lbs-physical-validation-design-completion.v1"
)
DESIGN_AUDIT_SCHEMA = "pet.stage33d-matched-pet-lbs-physical-validation-design-audit.v1"
GATES_SCHEMA = "pet.stage33d-matched-pet-lbs-acceptance-gates.v1"

INPUT_MODE = "synthetic_qualification"
PRECOMMIT_STATUS = "CUSTODIAN_COMMITTED_PREMEASUREMENT"
CONDITIONS = {"T20", "T120", "T140", "T160", "T180"}
TRUE_TOKENS = {"true", "1", "yes", "y"}
FALSE_TOKENS = {"false", "0", "no", "n"}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")

DESIGN_FIELDS = [
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

PREPARATION_INPUT_FIELDS = [
    "design_specimen_slot",
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

PREPARATION_OUTPUT_FIELDS = [
    "operational_release_id",
    "opaque_specimen_id",
    "opaque_matched_set_id",
    *PREPARATION_INPUT_FIELDS[1:],
]

MORPHOLOGY_INPUT_FIELDS = [
    "source_batch_slot",
    "log_d50_max_feret",
    "measurement_se",
]

MORPHOLOGY_OUTPUT_FIELDS = [
    "operational_release_id",
    "analyst_batch_code",
    "log_d50_max_feret",
    "measurement_se",
]

ANALYST_KEY_FIELDS = [
    "operational_release_id",
    "opaque_specimen_id",
    "opaque_matched_set_id",
    "analyst_batch_code",
    "specimen_role",
]

OPERATOR_SCHEDULE_FIELDS = [
    "operational_release_id",
    "operator_sequence",
    "opaque_specimen_id",
]

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
    "measured_utc",
    "operator_id",
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

CUSTODIAN_CROSSWALK_FIELDS = [
    "operational_release_id",
    "opaque_specimen_id",
    "opaque_matched_set_id",
    "operator_sequence",
    "design_run_order",
    "design_specimen_slot",
    "reactor_block",
    "matched_set_sequence",
    "technical_replicate",
    "within_set_order",
    "specimen_role",
    "condition_id",
    "source_batch_slot",
    "analyst_batch_code",
    "planned_linearity_sentinel",
    "opaque_linearity_id",
]

REVEAL_FIELDS = [
    "operational_release_id",
    "analyst_batch_code",
    "reactor_block",
    "condition_id",
    "source_batch_slot",
]

LINEARITY_CROSSWALK_FIELDS = [
    "operational_release_id",
    "opaque_linearity_id",
    "opaque_specimen_id",
]

AUTHORITY_CLOSED = {
    "absolute_permeability_validation_claim": False,
    "deformation_or_coupling_claim": False,
    "empirical_data_ingest": False,
    "laboratory_execution": False,
    "length_as_degradation_proxy_claim": False,
    "migration_or_clogging_claim": False,
    "model_recalibration": False,
    "molecular_degradation_claim": False,
    "numerical_execution": False,
    "physical_validation_claim": False,
    "real_key_ingest": False,
    "reveal_authorization": False,
}


class ReleaseBuildError(RuntimeError):
    """Fail-closed builder error with a stable diagnostic code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise ReleaseBuildError(code, message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def binding(path: Path, *, relative_to: Path | None = None) -> dict[str, str]:
    resolved = path.resolve()
    rendered = str(resolved)
    if relative_to is not None:
        rendered = resolved.relative_to(relative_to.resolve()).as_posix()
    return {"path": rendered, "sha256": sha256_file(resolved)}


def read_json(path: Path, expected_schema: str | None = None) -> dict[str, Any]:
    if not path.is_file():
        fail("D33DO_LINEAGE_MISSING", f"required JSON is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail("D33DO_MALFORMED_JSON", f"cannot read JSON {path}: {exc}")
    if not isinstance(value, dict):
        fail("D33DO_MALFORMED_JSON", f"JSON root is not an object: {path}")
    if expected_schema is not None and value.get("schema") != expected_schema:
        fail(
            "D33DO_SCHEMA_MISMATCH",
            f"unexpected schema in {path}: {value.get('schema')!r}; expected {expected_schema!r}",
        )
    return value


def read_csv_exact(path: Path, fields: list[str]) -> list[dict[str, str]]:
    if not path.is_file():
        fail("D33DO_INPUT_MISSING", f"required CSV is missing: {path}")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            actual = reader.fieldnames or []
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        fail("D33DO_MALFORMED_CSV", f"cannot read CSV {path}: {exc}")
    if actual != fields:
        fail(
            "D33DO_SCHEMA_MISMATCH",
            f"unexpected columns in {path}: {actual}; expected {fields}",
        )
    return rows


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def csv_bytes(fields: list[str], rows: Iterable[dict[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer, fieldnames=fields, lineterminator="\n", extrasaction="raise"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return buffer.getvalue().encode("utf-8")


def write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        fail("D33DO_IMMUTABILITY_VIOLATION", f"refusing to overwrite: {path}")
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def write_json(path: Path, value: Any) -> None:
    write_bytes(path, json_bytes(value))


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    write_bytes(path, csv_bytes(fields, rows))


def parse_bool(raw: str, context: str) -> bool:
    token = raw.strip().casefold()
    if token in TRUE_TOKENS:
        return True
    if token in FALSE_TOKENS:
        return False
    fail("D33DO_MALFORMED_INPUT", f"invalid boolean for {context}: {raw!r}")


def parse_int(raw: str, context: str, allowed: set[int] | None = None) -> int:
    if not re.fullmatch(r"[+-]?\d+", raw.strip()):
        fail("D33DO_MALFORMED_INPUT", f"invalid integer for {context}: {raw!r}")
    value = int(raw)
    if allowed is not None and value not in allowed:
        fail("D33DO_DESIGN_MISMATCH", f"out-of-range {context}: {value}")
    return value


def parse_float(raw: str, context: str, *, positive: bool = False, nonnegative: bool = False) -> float:
    try:
        value = float(raw.strip())
    except ValueError:
        fail("D33DO_MALFORMED_INPUT", f"invalid number for {context}: {raw!r}")
    if not math.isfinite(value):
        fail("D33DO_MALFORMED_INPUT", f"nonfinite number for {context}")
    if positive and value <= 0.0:
        fail("D33DO_MALFORMED_INPUT", f"nonpositive number for {context}")
    if nonnegative and value < 0.0:
        fail("D33DO_MALFORMED_INPUT", f"negative number for {context}")
    return value


def numeric(value: float) -> str:
    return format(value, ".17g")


def require_text(raw: str, context: str) -> str:
    value = raw.strip()
    if not value:
        fail("D33DO_MALFORMED_INPUT", f"blank required value for {context}")
    if any(ord(char) < 32 for char in value):
        fail("D33DO_MALFORMED_INPUT", f"control character in {context}")
    return value


def validate_bound_file(item: Any, expected_path: Path, context: str) -> None:
    if not isinstance(item, dict):
        fail("D33DO_LINEAGE_MISMATCH", f"missing binding for {context}")
    declared_path = item.get("path")
    declared_hash = item.get("sha256")
    if not isinstance(declared_path, str) or not isinstance(declared_hash, str):
        fail("D33DO_LINEAGE_MISMATCH", f"malformed binding for {context}")
    if not SHA_RE.fullmatch(declared_hash):
        fail("D33DO_LINEAGE_MISMATCH", f"invalid SHA-256 for {context}")
    bound = Path(declared_path)
    if bound.resolve() != expected_path.resolve():
        fail("D33DO_LINEAGE_MISMATCH", f"wrong path bound for {context}")
    if not bound.is_file() or sha256_file(bound) != declared_hash:
        fail("D33DO_LINEAGE_MISMATCH", f"hash mismatch for {context}")


def validate_design(
    design_dir: Path, design_audit_path: Path
) -> tuple[list[dict[str, str]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    design_path = design_dir / "resolved_design.json"
    gates_path = design_dir / "acceptance_gates.json"
    completion_path = design_dir / "completion.json"
    matrix_path = design_dir / "custodian_design_matrix.csv"
    design = read_json(design_path, DESIGN_SCHEMA)
    gates = read_json(gates_path, GATES_SCHEMA)
    completion = read_json(completion_path, DESIGN_COMPLETION_SCHEMA)
    audit = read_json(design_audit_path, DESIGN_AUDIT_SCHEMA)
    rows = read_csv_exact(matrix_path, DESIGN_FIELDS)

    if design.get("passed") is not True or completion.get("passed") is not True or audit.get("passed") is not True:
        fail("D33DO_LINEAGE_MISMATCH", "Stage33D design/completion/audit is not passing")
    if design.get("release_id") != "STAGE33D-PREDATA-DESIGN-01":
        fail("D33DO_LINEAGE_MISMATCH", "wrong Stage33D design release")
    if design.get("status") != "frozen_predata_design_only_execution_closed":
        fail("D33DO_LINEAGE_MISMATCH", "Stage33D execution boundary is not closed")
    authority = design.get("authority")
    if not isinstance(authority, dict) or not authority or any(value is not False for value in authority.values()):
        fail("D33DO_AUTHORITY_OPEN", "Stage33D design has open authority")
    future = design.get("future_required_inputs")
    if not isinstance(future, dict) or not future:
        fail("D33DO_LINEAGE_MISMATCH", "Stage33D future-input gates are absent")
    for name, item in future.items():
        if not isinstance(item, dict) or item.get("populated") is not False or item.get("path") or item.get("sha256"):
            fail("D33DO_REAL_INPUT_PROHIBITED", f"Stage33D future input is populated: {name}")

    frozen = design.get("design")
    if not isinstance(frozen, dict) or not (
        frozen.get("total_columns") == 54
        and frozen.get("pet_columns") == 45
        and frozen.get("clean_columns") == 9
        and frozen.get("independent_pet_batches") == 15
        and frozen.get("technical_columns_per_pet_batch") == 3
    ):
        fail("D33DO_DESIGN_MISMATCH", "Stage33D frozen counts are not 54/45/9/15/3")
    if not (
        gates.get("required_batch_endpoints") == 15
        and gates.get("monotonicity_is_not_a_gate") is True
        and float(gates.get("target_total_solid_void_ratio", math.nan)) == 0.744
    ):
        fail("D33DO_DESIGN_MISMATCH", "Stage33D acceptance gates were altered")

    artifacts = completion.get("artifacts")
    if not isinstance(artifacts, dict):
        fail("D33DO_LINEAGE_MISMATCH", "Stage33D completion artifact bindings are absent")
    for name, path in {
        "resolved_design.json": design_path,
        "acceptance_gates.json": gates_path,
        "custodian_design_matrix.csv": matrix_path,
    }.items():
        validate_bound_file(artifacts.get(name), path, f"Stage33D {name}")
    bindings = audit.get("bindings")
    if not isinstance(bindings, dict) or (
        bindings.get("resolved_design_sha256") != sha256_file(design_path)
        or bindings.get("acceptance_gates_sha256") != sha256_file(gates_path)
        or bindings.get("custodian_design_matrix_sha256") != sha256_file(matrix_path)
        or bindings.get("completion_sha256") != sha256_file(completion_path)
    ):
        fail("D33DO_LINEAGE_MISMATCH", "Stage33D audit does not bind the selected design")

    if len(rows) != 54:
        fail("D33DO_DESIGN_MISMATCH", f"design matrix has {len(rows)} rows, expected 54")
    slots: set[str] = set()
    run_orders: set[int] = set()
    set_members: dict[tuple[int, int], list[dict[str, str]]] = defaultdict(list)
    batch_members: dict[str, list[dict[str, str]]] = defaultdict(list)
    role_counts: Counter[str] = Counter()
    sentinel_rows: list[dict[str, str]] = []
    for index, row in enumerate(rows, 2):
        context = f"design row {index}"
        run_order = parse_int(row["run_order"], f"{context} run_order")
        block = parse_int(row["reactor_block"], f"{context} reactor_block", {1, 2, 3})
        set_sequence = parse_int(
            row["matched_set_sequence"], f"{context} matched_set_sequence", {1, 2, 3}
        )
        replicate = parse_int(
            row["technical_replicate"], f"{context} technical_replicate", {1, 2, 3}
        )
        parse_int(row["within_set_order"], f"{context} within_set_order", set(range(1, 7)))
        slot = require_text(row["design_specimen_slot"], f"{context} design_specimen_slot")
        role = row["specimen_role"].strip()
        condition = row["condition_id"].strip()
        batch = row["source_batch_slot"].strip()
        sentinel = parse_bool(row["planned_linearity_sentinel"], f"{context} sentinel")
        if slot in slots or run_order in run_orders:
            fail("D33DO_DUPLICATE_IDENTITY", f"duplicate design slot/run order at {context}")
        slots.add(slot)
        run_orders.add(run_order)
        if row["operational_id_status"].strip() != "not_assigned_predata_design_only":
            fail("D33DO_REAL_KEY_PROHIBITED", f"design already has operational identity at {context}")
        if role == "clean_lbs_control":
            if condition != "CLEAN" or batch:
                fail("D33DO_DESIGN_MISMATCH", f"malformed clean row at {context}")
        elif role == "pet_mixture":
            if condition not in CONDITIONS or not re.fullmatch(r"S33A-B\d{3}", batch):
                fail("D33DO_DESIGN_MISMATCH", f"malformed PET row at {context}")
            batch_members[batch].append(row)
        else:
            fail("D33DO_DESIGN_MISMATCH", f"unsupported role at {context}: {role!r}")
        role_counts[role] += 1
        set_members[(block, set_sequence)].append(row)
        if sentinel:
            sentinel_rows.append(row)

    if run_orders != set(range(1, 55)) or role_counts != Counter(
        {"pet_mixture": 45, "clean_lbs_control": 9}
    ):
        fail("D33DO_DESIGN_MISMATCH", "design order/role counts do not close")
    if len(set_members) != 9 or any(len(members) != 6 for members in set_members.values()):
        fail("D33DO_DESIGN_MISMATCH", "design is not nine six-column matched sets")
    for key, members in set_members.items():
        roles = Counter(row["specimen_role"].strip() for row in members)
        conditions = {row["condition_id"].strip() for row in members}
        replicates = {int(row["technical_replicate"]) for row in members}
        if (
            roles != Counter({"pet_mixture": 5, "clean_lbs_control": 1})
            or conditions != CONDITIONS | {"CLEAN"}
            or len(replicates) != 1
        ):
            fail("D33DO_DESIGN_MISMATCH", f"malformed matched set: {key}")
    for block in (1, 2, 3):
        block_replicates = {
            int(members[0]["technical_replicate"])
            for (member_block, _), members in set_members.items()
            if member_block == block
        }
        if block_replicates != {1, 2, 3}:
            fail("D33DO_DESIGN_MISMATCH", f"block {block} does not contain replicates 1..3")
    if len(batch_members) != 15:
        fail("D33DO_DESIGN_MISMATCH", "design does not contain 15 PET batches")
    for batch, members in batch_members.items():
        if len(members) != 3:
            fail("D33DO_DESIGN_MISMATCH", f"PET batch does not have three columns: {batch}")
        if len({row["condition_id"] for row in members}) != 1 or len({row["reactor_block"] for row in members}) != 1:
            fail("D33DO_DESIGN_MISMATCH", f"PET batch crosses condition/block: {batch}")
        if {int(row["matched_set_sequence"]) for row in members} != {1, 2, 3}:
            fail("D33DO_DESIGN_MISMATCH", f"PET batch does not span three matched sets: {batch}")
        if {int(row["technical_replicate"]) for row in members} != {1, 2, 3}:
            fail("D33DO_DESIGN_MISMATCH", f"PET batch does not span three technical replicates: {batch}")
    if len(sentinel_rows) != 6:
        fail("D33DO_DESIGN_MISMATCH", "linearity sentinel count is not six")
    sentinels = Counter(
        "clean" if row["specimen_role"] == "clean_lbs_control" else row["condition_id"]
        for row in sentinel_rows
    )
    if sentinels != Counter({"clean": 3, "T180": 3}) or {
        int(row["reactor_block"]) for row in sentinel_rows if row["specimen_role"] == "clean_lbs_control"
    } != {1, 2, 3} or {
        int(row["reactor_block"]) for row in sentinel_rows if row["specimen_role"] == "pet_mixture"
    } != {1, 2, 3}:
        fail("D33DO_DESIGN_MISMATCH", "linearity sentinels are not 3 clean + 3 T180 across blocks")
    return rows, design, gates, completion


def validate_roles(path: Path) -> dict[str, Any]:
    value = read_json(path, ROLES_SCHEMA)
    if value.get("test_only") is not True:
        fail("D33DO_REAL_KEY_PROHIBITED", "roles input is not explicitly test-only")
    nested_roles = value.get("roles")
    roles = nested_roles if isinstance(nested_roles, dict) else value
    sanitized: dict[str, dict[str, str]] = {}
    for name in ("operator", "analyst", "custodian"):
        item = roles.get(name)
        if not isinstance(item, dict):
            fail("D33DO_ROLE_SEPARATION_FAILED", f"role object is missing: {name}")
        role_id = require_text(str(item.get("role_id", "")), f"{name} role_id")
        if "test" not in role_id.casefold():
            fail("D33DO_REAL_KEY_PROHIBITED", f"role ID is not visibly test-only: {name}")
        sanitized[name] = {"role_id": role_id}
    ids = [item["role_id"].casefold() for item in sanitized.values()]
    if len(set(ids)) != 3:
        fail("D33DO_ROLE_SEPARATION_FAILED", "operator, analyst and custodian role IDs overlap")
    return {
        "schema": ROLES_SCHEMA,
        "stage": "Stage33D-O",
        "test_only": True,
        "passed": True,
        **sanitized,
        "required_separation": {
            "analyst_is_not_custodian": True,
            "operator_is_not_analyst": True,
            "operator_is_not_custodian": True,
        },
        "status": "test_only_roles_separated",
    }


def validate_secret(path: Path) -> bytes:
    if not path.is_file():
        fail("D33DO_SECRET_MISSING", f"test secret is missing: {path}")
    secret = path.read_bytes()
    if len(secret) < 32:
        fail("D33DO_SECRET_INVALID", "test secret must contain at least 32 bytes")
    if not secret.startswith(b"TEST_ONLY_"):
        fail("D33DO_REAL_KEY_PROHIBITED", "secret lacks the required TEST_ONLY_ marker")
    if secret.strip() != secret or b"\x00" in secret:
        fail("D33DO_SECRET_INVALID", "test secret must have no outer whitespace or NUL byte")
    return secret


def hmac_token(secret: bytes, prefix: str, domain: str, label: str) -> str:
    digest = hmac.new(
        secret,
        (f"pet.stage33do.{domain}.v1\x00{label}").encode("utf-8"),
        hashlib.sha256,
    ).hexdigest().upper()
    return f"{prefix}-{digest[:24]}"


def validate_preparation(
    path: Path,
    design_by_slot: dict[str, dict[str, str]],
    gates: dict[str, Any],
) -> dict[str, dict[str, str]]:
    rows = read_csv_exact(path, PREPARATION_INPUT_FIELDS)
    if len(rows) != 54:
        fail("D33DO_INCOMPLETE_INPUT", f"preparation input has {len(rows)} rows, expected 54")
    output: dict[str, dict[str, str]] = {}
    target_e = float(gates["target_total_solid_void_ratio"])
    e_tol = float(gates["void_ratio_absolute_tolerance"])
    target_dose = float(gates["target_pet_dry_mass_percent"])
    dose_tol = max(
        float(gates["pet_dose_absolute_tolerance_wt_percent"]),
        float(gates["pet_dose_relative_tolerance"]) * target_dose,
    )
    for index, row in enumerate(rows, 2):
        slot = require_text(row["design_specimen_slot"], f"preparation row {index} slot")
        if slot in output:
            fail("D33DO_DUPLICATE_IDENTITY", f"duplicate preparation slot: {slot}")
        design = design_by_slot.get(slot)
        if design is None:
            fail("D33DO_IDENTITY_MISMATCH", f"unknown preparation slot: {slot}")
        for field in (
            "balance_calibration_id",
            "sand_lot_id",
            "mixing_protocol_id",
            "packing_protocol_id",
            "custodian_id",
        ):
            text = require_text(row[field], f"preparation {slot} {field}")
            if "test" not in text.casefold():
                fail("D33DO_REAL_INPUT_PROHIBITED", f"{field} is not visibly test-only for {slot}")
        require_text(row["preparation_utc"], f"preparation {slot} preparation_utc")
        sand = parse_float(row["dry_sand_mass_g"], f"preparation {slot} dry sand", positive=True)
        pet = parse_float(row["dry_pet_mass_g"], f"preparation {slot} dry PET", nonnegative=True)
        achieved = parse_float(
            row["achieved_pet_dry_mass_percent"], f"preparation {slot} achieved dose", nonnegative=True
        )
        calculated = 100.0 * pet / sand
        if abs(achieved - calculated) > max(1e-12, 5e-7 * max(calculated, 1.0)):
            fail("D33DO_PREPARATION_GATE_FAILED", f"PET dose arithmetic mismatch for {slot}")
        pet_density = parse_float(
            row["pet_density_g_cm3"], f"preparation {slot} PET density", nonnegative=True
        )
        pet_solid_fraction = parse_float(
            row["achieved_pet_solid_volume_fraction"],
            f"preparation {slot} PET solid volume fraction",
            nonnegative=True,
        )
        initial_e = parse_float(
            row["initial_total_solid_void_ratio"], f"preparation {slot} initial void ratio"
        )
        if abs(initial_e - target_e) > e_tol + 1e-12:
            fail("D33DO_VOID_RATIO_GATE_FAILED", f"initial void ratio outside gate for {slot}")
        eligible = parse_bool(row["pre_measurement_eligible"], f"preparation {slot} eligibility")
        reason = row["pre_measurement_rejection_reason"].strip()
        if not eligible or reason:
            fail("D33DO_PREPARATION_GATE_FAILED", f"preparation is not eligible for release: {slot}")
        if design["specimen_role"] == "clean_lbs_control":
            if pet > 1e-12 or achieved > 1e-12 or pet_solid_fraction > 1e-12:
                fail("D33DO_PREPARATION_GATE_FAILED", f"clean preparation contains PET: {slot}")
        else:
            if abs(achieved - target_dose) > dose_tol + 1e-12:
                fail("D33DO_PREPARATION_GATE_FAILED", f"PET dose outside frozen gate: {slot}")
            if pet <= 0.0 or pet_density <= 0.0 or pet_solid_fraction <= 0.0:
                fail("D33DO_PREPARATION_GATE_FAILED", f"PET preparation has nonpositive PET property: {slot}")
        sanitized = dict(row)
        sanitized["dry_sand_mass_g"] = numeric(sand)
        sanitized["dry_pet_mass_g"] = numeric(pet)
        sanitized["achieved_pet_dry_mass_percent"] = numeric(achieved)
        sanitized["pet_density_g_cm3"] = numeric(pet_density)
        sanitized["achieved_pet_solid_volume_fraction"] = numeric(pet_solid_fraction)
        sanitized["initial_total_solid_void_ratio"] = numeric(initial_e)
        sanitized["pre_measurement_eligible"] = "true"
        sanitized["pre_measurement_rejection_reason"] = ""
        output[slot] = sanitized
    if set(output) != set(design_by_slot):
        fail("D33DO_IDENTITY_MISMATCH", "preparation identity set does not equal the 54-column design")
    return output


def validate_morphology(
    path: Path, source_batches: set[str]
) -> dict[str, dict[str, str]]:
    rows = read_csv_exact(path, MORPHOLOGY_INPUT_FIELDS)
    if len(rows) != 15:
        fail("D33DO_INCOMPLETE_INPUT", f"morphology input has {len(rows)} rows, expected 15")
    output: dict[str, dict[str, str]] = {}
    for index, row in enumerate(rows, 2):
        source = require_text(row["source_batch_slot"], f"morphology row {index} source")
        if source in output:
            fail("D33DO_DUPLICATE_IDENTITY", f"duplicate morphology source batch: {source}")
        if source not in source_batches:
            fail("D33DO_IDENTITY_MISMATCH", f"unknown morphology source batch: {source}")
        log_d50 = parse_float(row["log_d50_max_feret"], f"morphology {source} log D50")
        measurement_se = parse_float(
            row["measurement_se"], f"morphology {source} measurement SE", positive=True
        )
        output[source] = {
            "source_batch_slot": source,
            "log_d50_max_feret": numeric(log_d50),
            "measurement_se": numeric(measurement_se),
        }
    if set(output) != source_batches:
        fail("D33DO_IDENTITY_MISMATCH", "morphology identity set does not equal the 15 PET batches")
    return output


def source_bindings(
    design_dir: Path, design_audit: Path, contract: Path
) -> dict[str, dict[str, str]]:
    paths = {
        "stage33d_resolved_design": design_dir / "resolved_design.json",
        "stage33d_acceptance_gates": design_dir / "acceptance_gates.json",
        "stage33d_design_completion": design_dir / "completion.json",
        "stage33d_custodian_design_matrix": design_dir / "custodian_design_matrix.csv",
        "stage33d_design_audit": design_audit,
        "stage33do_contract": contract,
        "stage33do_release_builder": Path(__file__).resolve(),
        "stage33do_primary_freeze_sealer": ROOT / "stage33_staging" / "seal_stage33do_primary_freeze_v1.py",
        "stage33do_evaluator": ROOT / "stage33_staging" / "evaluate_stage33do_matched_hydraulics_v1.py",
        "stage33do_verifier": ROOT / "stage33_staging" / "verify_stage33do_operational_workflow_v1.py",
        "stage33do_release_auditor": ROOT / "stage33_staging" / "audit_stage33do_operational_release_qualification_v1.py",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        fail("D33DO_LINEAGE_MISSING", f"production source file(s) missing: {missing}")
    resolved = [str(path.resolve()).casefold() for path in paths.values()]
    if len(set(resolved)) != len(resolved):
        fail("D33DO_LINEAGE_MISMATCH", "source roles bind duplicate files")
    return {role: binding(path) for role, path in paths.items()}


def package_artifacts(directory: Path, names: dict[str, str]) -> dict[str, dict[str, str]]:
    return {role: binding(directory / filename, relative_to=directory) for role, filename in names.items()}


def scan_nonrestricted(temp_root: Path, secret: bytes) -> None:
    forbidden_operator_headers = {
        "analyst_batch_code",
        "condition_id",
        "design_specimen_slot",
        "dry_pet_mass_g",
        "matched_set_sequence",
        "planned_linearity_sentinel",
        "reactor_block",
        "run_order",
        "source_batch_slot",
        "specimen_role",
        "technical_replicate",
        "target_pet_dry_mass_percent",
        "within_set_order",
    }
    forbidden_analyst_headers = {
        "condition_id",
        "design_specimen_slot",
        "matched_set_sequence",
        "operator_sequence",
        "opaque_linearity_id",
        "planned_linearity_sentinel",
        "reactor_block",
        "run_order",
        "source_batch_slot",
        "technical_replicate",
        "within_set_order",
    }
    forbidden_design_token = re.compile(
        rb"(?<![A-Za-z0-9])(?:D33D-B\d|S33A-B\d+|T20|T120|T140|T160|T180)(?![A-Za-z0-9])",
        re.IGNORECASE,
    )
    forbidden_operator_token = re.compile(
        rb"(?:pet_mixture|clean_lbs_control|condition_id|source_batch_slot|reactor_block|planned_linearity_sentinel)",
        re.IGNORECASE,
    )
    for domain, forbidden_headers in (
        ("operator", forbidden_operator_headers),
        ("analyst", forbidden_analyst_headers),
    ):
        root = temp_root / domain
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            payload = path.read_bytes()
            if secret in payload:
                fail("D33DO_SECRET_LEAKAGE", f"test secret leaked into {domain}: {path.name}")
            if forbidden_design_token.search(payload):
                fail("D33DO_TREATMENT_KEY_LEAKAGE", f"design/treatment token leaked into {domain}: {path.name}")
            if domain == "operator" and forbidden_operator_token.search(payload):
                fail("D33DO_TREATMENT_KEY_LEAKAGE", f"role/source token leaked into operator: {path.name}")
            if path.suffix.casefold() == ".csv":
                with path.open("r", encoding="utf-8", newline="") as handle:
                    headers = [item.casefold() for item in (csv.DictReader(handle).fieldnames or [])]
                overlap = set(headers) & forbidden_headers
                if overlap:
                    fail(
                        "D33DO_TREATMENT_KEY_LEAKAGE",
                        f"forbidden header(s) in {domain}/{path.name}: {sorted(overlap)}",
                    )


def build_release(args: argparse.Namespace) -> Path:
    if args.input_mode != INPUT_MODE:
        fail(
            "D33DO_MODE_NOT_ALLOWED",
            f"only {INPUT_MODE!r} is implemented; production/real modes are closed",
        )
    release_id = args.release_id.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,95}", release_id):
        fail("D33DO_RELEASE_ID_INVALID", "release ID has an invalid format")
    normalized_release_id = re.sub(r"[^a-z0-9]", "", release_id.casefold())
    if "testonly" not in normalized_release_id:
        fail("D33DO_REAL_KEY_PROHIBITED", "release ID must visibly contain TEST_ONLY")

    output = args.output_dir.resolve()
    if output.exists():
        fail("D33DO_IMMUTABILITY_VIOLATION", f"output already exists: {output}")
    if output == output.parent:
        fail("D33DO_IMMUTABILITY_VIOLATION", "output cannot be a filesystem root")
    output.parent.mkdir(parents=True, exist_ok=True)

    design_dir = args.design_dir.resolve()
    design_audit = args.design_audit.resolve()
    contract = args.contract.resolve()
    if not contract.is_file():
        fail("D33DO_LINEAGE_MISSING", f"contract is missing: {contract}")
    design_rows, design, gates, _ = validate_design(design_dir, design_audit)
    roles = validate_roles(args.roles.resolve())
    secret = validate_secret(args.secret_file.resolve())
    design_by_slot = {row["design_specimen_slot"]: row for row in design_rows}
    source_batches = {
        row["source_batch_slot"] for row in design_rows if row["specimen_role"] == "pet_mixture"
    }
    preparation = validate_preparation(args.preparation.resolve(), design_by_slot, gates)
    morphology = validate_morphology(args.morphology.resolve(), source_batches)
    sources = source_bindings(design_dir, design_audit, contract)

    specimen_id = {
        slot: hmac_token(secret, "SPX", "specimen", slot) for slot in design_by_slot
    }
    matched_labels = {
        (row["reactor_block"], row["technical_replicate"]) for row in design_rows
    }
    matched_id = {
        label: hmac_token(secret, "MSX", "matched-set", "|".join(label))
        for label in matched_labels
    }
    batch_code = {
        source: hmac_token(secret, "BAX", "analyst-batch", source)
        for source in source_batches
    }
    sentinel_slots = {
        row["design_specimen_slot"]
        for row in design_rows
        if parse_bool(row["planned_linearity_sentinel"], row["design_specimen_slot"])
    }
    linearity_id = {
        slot: hmac_token(secret, "LNX", "linearity", slot) for slot in sentinel_slots
    }
    all_opaque = [
        *specimen_id.values(),
        *matched_id.values(),
        *batch_code.values(),
        *linearity_id.values(),
    ]
    if len(all_opaque) != len(set(all_opaque)):
        fail("D33DO_OPAQUE_ID_COLLISION", "derived opaque identity collision")
    if any(
        original.casefold() in opaque.casefold() or opaque.casefold() in original.casefold()
        for original in [*design_by_slot, *source_batches]
        for opaque in all_opaque
    ):
        fail("D33DO_OPAQUE_ID_INVALID", "derived opaque identity contains a design key")

    order_slots = sorted(
        design_by_slot,
        key=lambda slot: hmac.new(
            secret,
            ("pet.stage33do.operator-order.v1\x00" + slot).encode("utf-8"),
            hashlib.sha256,
        ).digest(),
    )
    design_order_slots = [
        row["design_specimen_slot"] for row in sorted(design_rows, key=lambda row: int(row["run_order"]))
    ]
    if order_slots == design_order_slots:
        fail("D33DO_FRESH_PERMUTATION_FAILED", "secret-derived order equals the public design order")
    operator_sequence = {slot: index for index, slot in enumerate(order_slots, 1)}

    enriched: list[dict[str, Any]] = []
    for row in design_rows:
        slot = row["design_specimen_slot"]
        label = (row["reactor_block"], row["technical_replicate"])
        enriched.append(
            {
                **row,
                "opaque_specimen_id": specimen_id[slot],
                "opaque_matched_set_id": matched_id[label],
                "analyst_batch_code": batch_code.get(row["source_batch_slot"], ""),
                "opaque_linearity_id": linearity_id.get(slot, ""),
                "operator_sequence": operator_sequence[slot],
            }
        )

    temp = output.parent / f".{output.name}.tmp-{uuid.uuid4().hex}"
    if temp.exists():
        fail("D33DO_IMMUTABILITY_VIOLATION", f"temporary path unexpectedly exists: {temp}")
    temp.mkdir()
    try:
        created = utc_now()
        restricted_dir = temp / "restricted"
        operator_dir = temp / "operator"
        analyst_dir = temp / "analyst"

        crosswalk_rows = []
        for row in sorted(enriched, key=lambda item: item["opaque_specimen_id"]):
            crosswalk_rows.append(
                {
                    "operational_release_id": release_id,
                    "opaque_specimen_id": row["opaque_specimen_id"],
                    "opaque_matched_set_id": row["opaque_matched_set_id"],
                    "operator_sequence": row["operator_sequence"],
                    "design_run_order": row["run_order"],
                    "design_specimen_slot": row["design_specimen_slot"],
                    "reactor_block": row["reactor_block"],
                    "matched_set_sequence": row["matched_set_sequence"],
                    "technical_replicate": row["technical_replicate"],
                    "within_set_order": row["within_set_order"],
                    "specimen_role": row["specimen_role"],
                    "condition_id": row["condition_id"],
                    "source_batch_slot": row["source_batch_slot"],
                    "analyst_batch_code": row["analyst_batch_code"],
                    "planned_linearity_sentinel": row["planned_linearity_sentinel"].lower(),
                    "opaque_linearity_id": row["opaque_linearity_id"],
                }
            )
        write_csv(
            restricted_dir / "custodian_crosswalk.csv",
            CUSTODIAN_CROSSWALK_FIELDS,
            crosswalk_rows,
        )

        prep_rows = []
        for row in sorted(enriched, key=lambda item: item["opaque_specimen_id"]):
            source = preparation[row["design_specimen_slot"]]
            prep_rows.append(
                {
                    "operational_release_id": release_id,
                    "opaque_specimen_id": row["opaque_specimen_id"],
                    "opaque_matched_set_id": row["opaque_matched_set_id"],
                    **{field: source[field] for field in PREPARATION_INPUT_FIELDS[1:]},
                }
            )
        write_csv(
            restricted_dir / "preparation_records.csv",
            PREPARATION_OUTPUT_FIELDS,
            prep_rows,
        )

        reveal_rows = []
        for source in sorted(source_batches, key=lambda item: batch_code[item]):
            members = [row for row in design_rows if row["source_batch_slot"] == source]
            reveal_rows.append(
                {
                    "operational_release_id": release_id,
                    "analyst_batch_code": batch_code[source],
                    "reactor_block": members[0]["reactor_block"],
                    "condition_id": members[0]["condition_id"],
                    "source_batch_slot": source,
                }
            )
        write_csv(restricted_dir / "reveal_key.csv", REVEAL_FIELDS, reveal_rows)

        linearity_crosswalk_rows = [
            {
                "operational_release_id": release_id,
                "opaque_linearity_id": linearity_id[slot],
                "opaque_specimen_id": specimen_id[slot],
            }
            for slot in sorted(sentinel_slots, key=lambda item: linearity_id[item])
        ]
        write_csv(
            restricted_dir / "linearity_crosswalk.csv",
            LINEARITY_CROSSWALK_FIELDS,
            linearity_crosswalk_rows,
        )
        write_json(restricted_dir / "roles.json", roles)

        schedule_rows = []
        capture_template_rows = []
        for row in sorted(enriched, key=lambda item: item["operator_sequence"]):
            schedule_rows.append(
                {
                    "operational_release_id": release_id,
                    "operator_sequence": row["operator_sequence"],
                    "opaque_specimen_id": row["opaque_specimen_id"],
                }
            )
            capture_template_rows.append(
                {
                    "operational_release_id": release_id,
                    "opaque_specimen_id": row["opaque_specimen_id"],
                }
            )
        write_csv(operator_dir / "operator_schedule.csv", OPERATOR_SCHEDULE_FIELDS, schedule_rows)
        write_csv(
            operator_dir / "operator_capture_template.csv",
            OPERATOR_CAPTURE_FIELDS,
            capture_template_rows,
        )

        linearity_template_rows = []
        for lid in sorted(linearity_id.values()):
            for sequence in (1, 2, 3):
                linearity_template_rows.append(
                    {
                        "operational_release_id": release_id,
                        "opaque_linearity_id": lid,
                        "gradient_sequence": sequence,
                    }
                )
        write_csv(
            operator_dir / "darcy_linearity_capture_template.csv",
            LINEARITY_FIELDS,
            linearity_template_rows,
        )

        analyst_rows = [
            {
                "operational_release_id": release_id,
                "opaque_specimen_id": row["opaque_specimen_id"],
                "opaque_matched_set_id": row["opaque_matched_set_id"],
                "analyst_batch_code": row["analyst_batch_code"],
                "specimen_role": row["specimen_role"],
            }
            for row in sorted(enriched, key=lambda item: item["opaque_specimen_id"])
        ]
        write_csv(
            analyst_dir / "blinded_analysis_key.csv", ANALYST_KEY_FIELDS, analyst_rows
        )
        morphology_rows = [
            {
                "operational_release_id": release_id,
                "analyst_batch_code": batch_code[source],
                "log_d50_max_feret": morphology[source]["log_d50_max_feret"],
                "measurement_se": morphology[source]["measurement_se"],
            }
            for source in sorted(source_batches, key=lambda item: batch_code[item])
        ]
        write_csv(
            analyst_dir / "synthetic_morphology_summary.csv",
            MORPHOLOGY_OUTPUT_FIELDS,
            morphology_rows,
        )

        operator_names = {
            "operator_schedule": "operator_schedule.csv",
            "operator_capture_template": "operator_capture_template.csv",
            "darcy_linearity_capture_template": "darcy_linearity_capture_template.csv",
        }
        operator_manifest = {
            "schema": OPERATOR_MANIFEST_SCHEMA,
            "stage": "Stage33D-O",
            "operational_release_id": release_id,
            "created_utc": created,
            "passed": True,
            "test_only": True,
            "no_empirical_data": True,
            "status": "frozen_blank_measurement_templates_only",
            "artifacts": package_artifacts(operator_dir, operator_names),
            "counts": {
                "scheduled_specimens": 54,
                "blank_capture_rows": 54,
                "opaque_linearity_ids": 6,
                "blank_linearity_rows": 18,
            },
            "claim_boundary": "software package-separation qualification only",
        }
        write_json(operator_dir / "operator_manifest.json", operator_manifest)

        analyst_names = {
            "blinded_analysis_key": "blinded_analysis_key.csv",
            "synthetic_morphology_summary": "synthetic_morphology_summary.csv",
        }
        analyst_manifest = {
            "schema": ANALYST_MANIFEST_SCHEMA,
            "stage": "Stage33D-O",
            "operational_release_id": release_id,
            "created_utc": created,
            "passed": True,
            "test_only": True,
            "no_empirical_data": True,
            "status": "blinded_test_inputs_frozen_no_reveal",
            "artifacts": package_artifacts(analyst_dir, analyst_names),
            "counts": {
                "specimens": 54,
                "clean_roles": 9,
                "mixture_roles": 45,
                "opaque_batches": 15,
                "opaque_matched_sets": 9,
            },
            "claim_boundary": "synthetic batch-safe arithmetic fixture only",
        }
        write_json(analyst_dir / "analyst_manifest.json", analyst_manifest)

        restricted_names = {
            "custodian_crosswalk": "custodian_crosswalk.csv",
            "preparation_records": "preparation_records.csv",
            "reveal_key": "reveal_key.csv",
            "linearity_crosswalk": "linearity_crosswalk.csv",
            "roles": "roles.json",
        }
        restricted_manifest = {
            "schema": RESTRICTED_MANIFEST_SCHEMA,
            "stage": "Stage33D-O",
            "operational_release_id": release_id,
            "created_utc": created,
            "passed": True,
            "test_only": True,
            "no_empirical_data": True,
            "status": "restricted_test_custody_inputs_frozen_no_reveal",
            "artifacts": package_artifacts(restricted_dir, restricted_names),
            "counts": {
                "specimens": 54,
                "PET_columns": 45,
                "clean_columns": 9,
                "independent_batches": 15,
                "opaque_linearity_crosswalk_rows": 6,
            },
            "claim_boundary": "test-only custody and reveal-key fixture",
        }
        write_json(restricted_dir / "restricted_manifest.json", restricted_manifest)

        manifest_bindings = {
            "operator_manifest": sha256_file(operator_dir / "operator_manifest.json"),
            "analyst_manifest": sha256_file(analyst_dir / "analyst_manifest.json"),
            "restricted_manifest": sha256_file(restricted_dir / "restricted_manifest.json"),
        }
        cross_commitment = {
            "schema": COMMITMENT_SCHEMA,
            "stage": "Stage33D-O",
            "operational_release_id": release_id,
            "created_utc": created,
            "passed": True,
            "test_only": True,
            "no_empirical_data": True,
            "input_mode": INPUT_MODE,
            "status": PRECOMMIT_STATUS,
            "state": PRECOMMIT_STATUS,
            "contains_raw_secret": False,
            "contains_treatment_key": False,
            "nonrestricted_contains_condition": False,
            "manifest_bindings": manifest_bindings,
            "operator_manifest_sha256": manifest_bindings["operator_manifest"],
            "analyst_manifest_sha256": manifest_bindings["analyst_manifest"],
            "restricted_manifest_sha256": manifest_bindings["restricted_manifest"],
            "custodian_crosswalk_sha256": sha256_file(
                restricted_dir / "custodian_crosswalk.csv"
            ),
            "preparation_records_sha256": sha256_file(
                restricted_dir / "preparation_records.csv"
            ),
            "reveal_key_sha256": sha256_file(restricted_dir / "reveal_key.csv"),
            "linearity_crosswalk_sha256": sha256_file(
                restricted_dir / "linearity_crosswalk.csv"
            ),
            "roles_sha256": sha256_file(restricted_dir / "roles.json"),
            "lineage_bindings": {
                "stage33d_design_sha256": sources["stage33d_resolved_design"]["sha256"],
                "acceptance_gates_sha256": sources["stage33d_acceptance_gates"]["sha256"],
                "builder_sha256": sources["stage33do_release_builder"]["sha256"],
                "roles_sha256": sha256_file(restricted_dir / "roles.json"),
            },
            "template_sha256": {
                "operator_schedule": sha256_file(operator_dir / "operator_schedule.csv"),
                "operator_capture_template": sha256_file(
                    operator_dir / "operator_capture_template.csv"
                ),
                "darcy_linearity_capture_template": sha256_file(
                    operator_dir / "darcy_linearity_capture_template.csv"
                ),
                "blinded_analysis_key": sha256_file(analyst_dir / "blinded_analysis_key.csv"),
                "synthetic_morphology_summary": sha256_file(
                    analyst_dir / "synthetic_morphology_summary.csv"
                ),
                "custodian_crosswalk": sha256_file(restricted_dir / "custodian_crosswalk.csv"),
                "preparation_records": sha256_file(restricted_dir / "preparation_records.csv"),
                "reveal_key": sha256_file(restricted_dir / "reveal_key.csv"),
                "linearity_crosswalk": sha256_file(restricted_dir / "linearity_crosswalk.csv"),
                "roles": sha256_file(restricted_dir / "roles.json"),
            },
            "key_separation": {
                "treatment_key_absent_from_operator": True,
                "source_batch_absent_from_operator": True,
                "treatment_key_absent_from_analyst": True,
                "source_batch_absent_from_analyst": True,
                "operator_and_analyst_access_separated": True,
                "linearity_to_specimen_mapping_restricted": True,
            },
            "premeasurement_state": {
                "completed_operator_capture_present": False,
                "completed_linearity_capture_present": False,
                "primary_endpoints_frozen": False,
                "reveal_authorized": False,
            },
            "joinability_proof": {
                "identifier_derivation": "domain-separated HMAC-SHA256 using an unstored test secret",
                "fresh_operator_permutation": True,
                "operator_order_is_not_public_design_order": True,
                "analyst_design_quasi_identifiers_present": False,
                "analyst_linearity_identity_present": False,
                "public_design_condition_recoverability": "zero exact labels without the restricted crosswalk/reveal key",
                "secret_or_secret_fingerprint_stored": False,
            },
            "next_state": "synthetic captures may be added only in a new immutable final release by the audited sealer",
        }
        write_json(restricted_dir / "cross_release_commitment.json", cross_commitment)

        scan_nonrestricted(temp, secret)

        top_artifact_paths = {
            "operator_schedule": operator_dir / "operator_schedule.csv",
            "operator_capture_template": operator_dir / "operator_capture_template.csv",
            "darcy_linearity_capture_template": operator_dir / "darcy_linearity_capture_template.csv",
            "operator_manifest": operator_dir / "operator_manifest.json",
            "blinded_analysis_key": analyst_dir / "blinded_analysis_key.csv",
            "synthetic_morphology_summary": analyst_dir / "synthetic_morphology_summary.csv",
            "analyst_manifest": analyst_dir / "analyst_manifest.json",
            "custodian_crosswalk": restricted_dir / "custodian_crosswalk.csv",
            "preparation_records": restricted_dir / "preparation_records.csv",
            "reveal_key": restricted_dir / "reveal_key.csv",
            "linearity_crosswalk": restricted_dir / "linearity_crosswalk.csv",
            "roles": restricted_dir / "roles.json",
            "restricted_manifest": restricted_dir / "restricted_manifest.json",
            "cross_release_commitment": restricted_dir / "cross_release_commitment.json",
        }
        top_artifacts = {
            role: binding(path, relative_to=temp) for role, path in top_artifact_paths.items()
        }
        release_manifest = {
            "schema": RELEASE_SCHEMA,
            "stage": "Stage33D-O",
            "operational_release_id": release_id,
            "release_id": release_id,
            "created_utc": created,
            "passed": True,
            "test_only": True,
            "no_empirical_data": True,
            "input_mode": INPUT_MODE,
            "status": "premeasurement_committed_synthetic_qualification_only",
            "source_bindings": sources,
            "artifacts": top_artifacts,
            "counts": {
                "total_columns": 54,
                "PET_columns": 45,
                "clean_columns": 9,
                "independent_PET_batches": 15,
                "matched_sets": 9,
                "linearity_sentinels": 6,
                "linearity_template_rows": 18,
            },
            "blinding": {
                "fresh_secret_derived_operational_order": True,
                "public_design_order_exposed_outside_restricted": False,
                "condition_exposed_outside_restricted": False,
                "source_batch_exposed_outside_restricted": False,
                "linearity_specimen_crosswalk_exposed_outside_restricted": False,
                "secret_stored": False,
            },
            "authority": dict(AUTHORITY_CLOSED),
            "claim_boundary": "synthetic software/release-process qualification only; no empirical or physical conclusion",
            "next_handoff": "new immutable synthetic capture/freeze release via the audited Stage33D-O sealer only",
            "stop_boundary": "stop before real keys/data, laboratory or numerical execution, physical validation, degradation, permeability, migration, clogging, deformation or coupling claims",
        }
        write_json(temp / "release_manifest.json", release_manifest)

        completion_artifacts = {
            **top_artifacts,
            "release_manifest": binding(temp / "release_manifest.json", relative_to=temp),
        }
        completion = {
            "schema": COMPLETION_SCHEMA,
            "stage": "Stage33D-O",
            "operational_release_id": release_id,
            "created_utc": created,
            "passed": True,
            "test_only": True,
            "no_empirical_data": True,
            "status": "complete_premeasurement_templates_committed",
            "artifacts": completion_artifacts,
            "checks": {
                "design_lineage_passed": True,
                "exact_54_45_9_15_counts": True,
                "fresh_secret_derived_operator_permutation": True,
                "separate_opaque_linearity_namespace": True,
                "operator_package_leakage_scan_passed": True,
                "analyst_package_leakage_scan_passed": True,
                "semantic_roles_distinct": True,
                "premesurement_commitment_frozen": True,
                "completed_measurements_absent": True,
                "reveal_authority_closed": True,
                "secret_not_stored": True,
            },
            "authority": dict(AUTHORITY_CLOSED),
            "next_handoff": "synthetic capture generation and audited primary-freeze sealing only",
        }
        write_json(temp / "completion.json", completion)

        # Final secret scan includes manifests/completion; restricted output is
        # scanned for the raw secret too, but design values are expected there.
        for path in (item for item in temp.rglob("*") if item.is_file()):
            if secret in path.read_bytes():
                fail("D33DO_SECRET_LEAKAGE", f"test secret leaked into release: {path}")

        temp.rename(output)
        return output
    except Exception:
        if temp.exists():
            shutil.rmtree(temp)
        raise


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Build a test-only Stage33D-O blinded premeasurement release"
    )
    value.add_argument("--design-dir", type=Path, default=DEFAULT_DESIGN_DIR)
    value.add_argument("--design-audit", type=Path, default=DEFAULT_DESIGN_AUDIT)
    value.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    value.add_argument("--secret-file", type=Path, required=True)
    value.add_argument("--roles", type=Path, required=True)
    value.add_argument("--preparation", type=Path, required=True)
    value.add_argument("--morphology", type=Path, required=True)
    value.add_argument("--output-dir", type=Path, required=True)
    value.add_argument("--release-id", required=True)
    value.add_argument("--input-mode", required=True)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        output = build_release(args)
    except ReleaseBuildError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # defensive fail-closed boundary
        print(f"D33DO_INTERNAL_ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3
    print(str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
