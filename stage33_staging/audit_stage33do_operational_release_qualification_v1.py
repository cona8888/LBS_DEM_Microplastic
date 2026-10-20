#!/usr/bin/env python3
"""Independent fail-closed auditor for Stage33D-O synthetic qualification.

The auditor re-hashes the frozen Stage33D design, every production script and
every file declared by the synthetic verifier.  It also inspects the release
domains independently, recomputes K20 and matched clean ratios from raw
constant-head measurements, checks the evaluator's 15 batch endpoints, and
requires all negative challenges to reject their hostile fixture.

This program is deliberately read-only with respect to ``--design-dir`` and
``--verification-dir``.  It writes only ``audit.json`` and ``completion.json``
to a new or empty, disjoint ``--output`` directory.  Passing it qualifies a
synthetic software/release workflow only; it does not authorize empirical
data, laboratory work, simulation, unblinding, or any physical claim.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
STAGE = "Stage33D-O"
VERIFICATION_SCHEMA = "pet.stage33do-operational-workflow-synthetic-verification.v1"
AUDIT_SCHEMA = "pet.stage33do-operational-release-qualification-audit.v1"
COMPLETION_SCHEMA = "pet.stage33do-operational-release-qualification-audit-completion.v1"
DESIGN_SCHEMA = "pet.stage33d-matched-pet-lbs-physical-validation-design.v1"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")

EXPECTED_PRODUCTION_SCRIPTS = {
    "stage33do_contract": ROOT / "stage33_staging" / "STAGE33DO_OPERATIONAL_WORKFLOW_SYNTHETIC_QUALIFICATION_CONTRACT_V1.md",
    "stage33do_release_builder": ROOT / "stage33_staging" / "build_stage33do_synthetic_blinded_release_v1.py",
    "stage33do_evaluator": ROOT / "stage33_staging" / "evaluate_stage33do_matched_hydraulics_v1.py",
    "stage33do_primary_freeze_sealer": ROOT / "stage33_staging" / "seal_stage33do_primary_freeze_v1.py",
    "stage33do_verifier": ROOT / "stage33_staging" / "verify_stage33do_operational_workflow_v1.py",
    "stage33do_release_auditor": Path(__file__).resolve(),
}
EXPECTED_PARENT_ROLES = {"stage33d_design", "stage33d_design_audit"}
EXPECTED_RELEASE_FILES = {
    "release_manifest.json",
    "prepared_release_state.json",
    "frozen_release_state.json",
    "restricted/restricted_manifest.json",
    "restricted/custodian_crosswalk.csv",
    "restricted/reveal_key.csv",
    "restricted/cross_release_commitment.json",
    "restricted/primary_freeze_commitment.json",
    "restricted/preparation_records.csv",
    "restricted/linearity_crosswalk.csv",
    "restricted/linearity_gate_attestation.json",
    "restricted/roles.json",
    "restricted/reveal_declaration.json",
    "operator/operator_capture.csv",
    "operator/darcy_linearity_capture.csv",
    "operator/operator_manifest.json",
    "analyst/blinded_analysis_key.csv",
    "analyst/sanitized_hydraulic_capture.csv",
    "analyst/synthetic_morphology_summary.csv",
    "analyst/analyst_manifest.json",
}
EXPECTED_EVALUATION_FILES = {
    "specimen_results.csv", "batch_endpoints.csv", "condition_summary.csv",
    "evaluation.json", "completion.json",
}
EXPECTED_PRE_REVEAL_FILES = {
    "specimen_results.csv", "batch_endpoints.csv", "exclusion_ledger.csv",
    "pre_reveal_evaluation.json", "completion.json",
}
REQUIRED_NEGATIVE_CONCEPTS = {
    "duplicate_specimen": ("duplicate", "specimen"),
    "capture_binding": ("capture",),
    "operator_leakage": ("operator", "leak"),
    "reveal_key_mutation": ("reveal", "key"),
    "commitment_mutation": ("commitment",),
    "void_ratio": ("void", "ratio"),
    "darcy_linearity": ("linearity",),
    "role_overlap": ("role", "overlap"),
    "non_test_mode": ("non", "test"),
    "secret_leakage": ("secret", "leak"),
    "public_design_joinability": ("design", "join"),
}

OPERATOR_FORBIDDEN_HEADERS = {
    "condition_id", "condition_role", "target_temperature_c", "temperature_condition",
    "source_batch_slot", "source_batch_id", "source_aliquot_id", "analyst_batch_code",
    "specimen_role", "target_pet_dry_mass_percent", "dry_pet_mass_g",
    "morphology_d50_um", "feret_max_um", "contour_length_um", "shape_class",
    "molecular_endpoint", "chemistry_endpoint", "numerical_prediction",
    "predicted_k20_m_s", "predicted_ratio", "reactor_block",
    "run_order", "matched_set_sequence", "technical_replicate", "within_set_order",
    "design_specimen_slot", "planned_linearity_sentinel",
}
OPERATOR_FORBIDDEN_TOKENS = {
    "condition_id", "source_batch", "analyst_batch", "reactor_block",
    "pet_mixture", "clean_lbs_control", "target_temperature", "morphology",
    "feret", "contour_length", "chemistry", "molecular", "prediction",
    "t120", "t140", "t160", "t180", "t20",
}
ANALYST_FORBIDDEN_HEADERS = {
    "condition_id", "target_temperature_c", "temperature_condition",
    "source_batch_slot", "source_batch_id", "reactor_block",
    "numerical_prediction", "predicted_k20_m_s", "predicted_ratio",
    "run_order", "operator_run_order", "matched_set_sequence", "technical_replicate",
    "within_set_order", "design_specimen_slot", "planned_linearity_sentinel",
}
TEXT_SUFFIXES = {".csv", ".json", ".txt", ".md", ".yaml", ".yml", ".tsv"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def valid_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA_RE.fullmatch(value.lower()))


def contained(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def same_path(left: Path, right: Path) -> bool:
    return str(left.resolve()).casefold() == str(right.resolve()).casefold()


def resolve_path(value: Any, anchor: Path) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    if not path.is_absolute():
        path = anchor / path
    return path.resolve()


def load_json(path: Path) -> tuple[Any, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]], str | None]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            return list(reader.fieldnames or []), rows, None
    except Exception as exc:
        return [], [], f"{type(exc).__name__}: {exc}"


def json_dump(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    temporary.replace(path)


def tree_snapshot(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold())
        if path.is_file()
    }


def first(row: dict[str, Any], names: Iterable[str], default: Any = None) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return default


def parse_float(value: Any) -> float:
    number = float(str(value).strip())
    if not math.isfinite(number):
        raise ValueError(f"not finite: {value!r}")
    return number


def close(left: float, right: float, rel: float = 2e-12, abs_: float = 1e-18) -> bool:
    return math.isclose(left, right, rel_tol=rel, abs_tol=abs_)


def water_density_kg_m3(temp_c: float) -> float:
    return 1000.0 * (
        1.0 - ((temp_c + 288.9414) / (508929.2 * (temp_c + 68.12963)))
        * (temp_c - 3.9863) ** 2
    )


def water_viscosity_pa_s(temp_c: float) -> float:
    return 2.414e-5 * 10.0 ** (247.8 / (temp_c + 133.15))


def hydraulic_values(row: dict[str, Any]) -> tuple[float, float]:
    temp_c = parse_float(row["water_temperature_c"])
    diameter_mm = parse_float(row["specimen_diameter_mm"])
    length_mm = parse_float(row["specimen_length_mm"])
    head_m = parse_float(row["head_difference_m"])
    time_s = parse_float(row["collection_time_s"])
    water_mass_g = parse_float(row["collected_water_mass_g"])
    if min(diameter_mm, length_mm, head_m, time_s, water_mass_g) <= 0:
        raise ValueError("non-positive hydraulic input")
    rho = water_density_kg_m3(temp_c)
    volume_m3 = (water_mass_g / 1000.0) / rho
    area_m2 = math.pi * (diameter_mm / 2000.0) ** 2
    length_m = length_mm / 1000.0
    k_raw = (volume_m3 / time_s) * length_m / (area_m2 * head_m)
    rho20 = water_density_kg_m3(20.0)
    k20 = k_raw * (water_viscosity_pa_s(temp_c) / water_viscosity_pa_s(20.0)) * (rho20 / rho)
    return k_raw, k20


class Audit:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []

    def add(self, check_id: str, passed: bool, requirement: str, observed: Any = None) -> None:
        self.checks.append({
            "check_id": check_id,
            "pass": bool(passed),
            "requirement": requirement,
            "observed": observed,
        })

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(item["pass"] for item in self.checks)


def binding_entries(value: Any) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
    entries: list[tuple[str, dict[str, Any]]] = []
    errors: list[str] = []
    if isinstance(value, dict):
        for role, item in value.items():
            if isinstance(item, dict):
                entries.append((str(role), item))
            elif valid_sha(item):
                entries.append((str(role), {"path": str(role), "sha256": item}))
            else:
                errors.append(f"{role}: not a path/hash object")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if not isinstance(item, dict) or "path" not in item or "sha256" not in item:
                errors.append(f"entry {index}: not a path/hash object")
            else:
                entries.append((str(item.get("role", index)), item))
    else:
        errors.append("bindings are neither an object nor a list")
    return entries, errors


def recursive_binding_entries(value: Any, prefix: str = "release") -> list[tuple[str, dict[str, Any]]]:
    """Collect nested ``{path, sha256}`` objects without trusting container shape."""
    found: list[tuple[str, dict[str, Any]]] = []
    if isinstance(value, dict):
        if "path" in value and "sha256" in value:
            found.append((prefix, value))
        else:
            for key, child in value.items():
                found.extend(recursive_binding_entries(child, f"{prefix}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(recursive_binding_entries(child, f"{prefix}[{index}]"))
    return found


def audit_bindings(
    audit: Audit,
    check_id: str,
    value: Any,
    anchor: Path,
    expected: dict[str, Path] | None = None,
    require_exact_roles: bool = False,
) -> dict[str, Path]:
    entries, errors = binding_entries(value)
    paths: dict[str, Path] = {}
    seen_paths: set[str] = set()
    for role, item in entries:
        path = resolve_path(item.get("path"), anchor)
        declared = item.get("sha256")
        if role in paths:
            errors.append(f"duplicate role: {role}")
            continue
        if path is None or not path.is_file():
            errors.append(f"{role}: missing regular file: {path}")
            continue
        key = str(path).casefold()
        if key in seen_paths:
            errors.append(f"{role}: duplicate bound path: {path}")
        seen_paths.add(key)
        if not valid_sha(declared):
            errors.append(f"{role}: invalid SHA-256")
        else:
            actual = sha256(path)
            if actual != str(declared).lower():
                errors.append(f"{role}: SHA-256 mismatch ({actual})")
        if expected is not None and role in expected and not same_path(path, expected[role]):
            errors.append(f"{role}: path is not authoritative {expected[role]}")
        paths[role] = path
    if expected is not None:
        missing = set(expected) - set(paths)
        extra = set(paths) - set(expected)
        if missing:
            errors.append(f"missing roles: {sorted(missing)}")
        if require_exact_roles and extra:
            errors.append(f"unexpected roles: {sorted(extra)}")
    audit.add(
        check_id, bool(entries) and not errors,
        "every binding must resolve to a unique regular file with the exact SHA-256 and authoritative role/path",
        {"roles": sorted(paths), "errors": errors},
    )
    return paths


def authority_closed(value: Any) -> bool:
    return isinstance(value, dict) and bool(value) and all(item is False for item in value.values())


def scan_domain(root: Path, forbidden_headers: set[str], forbidden_tokens: set[str]) -> dict[str, Any]:
    findings: list[str] = []
    files = [path for path in root.rglob("*") if path.is_file()] if root.is_dir() else []
    for path in files:
        relative = path.relative_to(root).as_posix()
        if path.suffix.lower() == ".csv":
            headers, _, error = read_csv(path)
            if error:
                findings.append(f"{relative}: unreadable CSV: {error}")
            leaked = sorted(set(header.casefold() for header in headers) & forbidden_headers)
            if leaked:
                findings.append(f"{relative}: forbidden headers {leaked}")
        if path.suffix.lower() in TEXT_SUFFIXES:
            try:
                text = path.read_text(encoding="utf-8-sig").casefold()
            except Exception as exc:
                findings.append(f"{relative}: unreadable text: {type(exc).__name__}")
                continue
            for token in sorted(forbidden_tokens):
                if token.casefold() in text:
                    findings.append(f"{relative}: forbidden token {token!r}")
    return {"file_n": len(files), "findings": findings, "pass": bool(files) and not findings}


def challenge_concepts(challenges: Any) -> tuple[bool, dict[str, Any]]:
    if not isinstance(challenges, dict):
        return False, {"error": "negative_challenges is not an object"}
    normalized = {str(key).casefold(): value for key, value in challenges.items()}
    failures: list[str] = []
    matches: dict[str, list[str]] = {}
    for concept, tokens in REQUIRED_NEGATIVE_CONCEPTS.items():
        candidates = [key for key in normalized if all(token in key for token in tokens)]
        matches[concept] = candidates
        if not candidates:
            failures.append(f"missing conceptual challenge: {concept}")
    for key, record in normalized.items():
        if not isinstance(record, dict):
            failures.append(f"{key}: record is not an object")
            continue
        passed = record.get("passed", record.get("pass")) is True
        rejected = record.get("rejected", record.get("observed_rejected", True)) is True
        expected = record.get("expected_rejection", record.get("expected_reject", True)) is True
        exit_code = record.get("exit_code", record.get("return_code"))
        if not (passed and rejected and expected):
            failures.append(f"{key}: did not demonstrate expected rejection")
        if exit_code is not None and (not isinstance(exit_code, int) or exit_code == 0):
            failures.append(f"{key}: rejection exit code is not nonzero")
    return bool(normalized) and not failures, {
        "challenge_n": len(normalized), "concept_matches": matches, "failures": failures,
    }


def independently_check_hydraulics(
    release_dir: Path, evaluation_dir: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    capture_path = release_dir / "operator" / "operator_capture.csv"
    key_path = release_dir / "analyst" / "blinded_analysis_key.csv"
    specimen_path = evaluation_dir / "specimen_results.csv"
    batch_path = evaluation_dir / "batch_endpoints.csv"
    capture_fields, capture_rows, capture_error = read_csv(capture_path)
    key_fields, key_rows, key_error = read_csv(key_path)
    specimen_fields, specimen_rows, specimen_error = read_csv(specimen_path)
    batch_fields, batch_rows, batch_error = read_csv(batch_path)
    failures: list[str] = [
        value for value in (capture_error, key_error, specimen_error, batch_error) if value
    ]
    required_raw = {
        "opaque_specimen_id", "water_temperature_c",
        "specimen_diameter_mm", "specimen_length_mm", "head_difference_m",
        "collection_time_s", "collected_water_mass_g",
    }
    if not required_raw.issubset(capture_fields):
        failures.append(f"operator capture lacks raw fields: {sorted(required_raw - set(capture_fields))}")
    required_key = {
        "opaque_specimen_id", "opaque_matched_set_id", "analyst_batch_code", "specimen_role",
    }
    if not required_key.issubset(key_fields):
        failures.append(f"analyst key lacks fields: {sorted(required_key - set(key_fields))}")

    capture_by_id = {row.get("opaque_specimen_id", ""): row for row in capture_rows}
    key_by_id = {row.get("opaque_specimen_id", ""): row for row in key_rows}
    result_by_id = {
        str(first(row, ("opaque_specimen_id", "specimen_id"), "")): row
        for row in specimen_rows
    }
    if len(capture_by_id) != len(capture_rows) or "" in capture_by_id:
        failures.append("operator specimen IDs are blank or duplicated")
    if len(key_by_id) != len(key_rows) or "" in key_by_id:
        failures.append("analyst-key specimen IDs are blank or duplicated")
    if len(result_by_id) != len(specimen_rows) or "" in result_by_id:
        failures.append("evaluator specimen IDs are blank or duplicated")
    if not (set(capture_by_id) == set(key_by_id) == set(result_by_id)):
        failures.append("capture, analyst key and evaluator specimen identity sets differ")

    k20_by_id: dict[str, float] = {}
    k_errors: list[str] = []
    for sid, capture in capture_by_id.items():
        try:
            k_raw, k20 = hydraulic_values(capture)
            k20_by_id[sid] = k20
            evaluator_row = result_by_id[sid]
            reported_k20 = parse_float(first(evaluator_row, ("K20_m_s", "calculated_K20_m_s")))
            if not close(reported_k20, k20):
                k_errors.append(f"{sid}: evaluator K20 {reported_k20:.17g} != {k20:.17g}")
            reported_raw = first(evaluator_row, ("K_raw_m_s", "calculated_K_raw_m_s"))
            if reported_raw not in (None, "") and not close(parse_float(reported_raw), k_raw):
                k_errors.append(f"{sid}: evaluator raw K mismatch")
            supplied = capture.get("calculated_K20_m_s", "").strip()
            if supplied and not close(parse_float(supplied), k20, rel=5e-3):
                k_errors.append(f"{sid}: supplied K20 differs by more than 0.5%")
        except Exception as exc:
            k_errors.append(f"{sid}: {type(exc).__name__}: {exc}")
    failures.extend(k_errors)

    clean_by_set: dict[str, list[str]] = defaultdict(list)
    pet_ids: list[str] = []
    for sid, key in key_by_id.items():
        role = key.get("specimen_role", "")
        set_id = key.get("opaque_matched_set_id", "")
        if role == "clean_lbs_control":
            clean_by_set[set_id].append(sid)
        elif role == "pet_mixture":
            pet_ids.append(sid)
        else:
            failures.append(f"{sid}: invalid specimen_role {role!r}")
    if any(len(ids) != 1 for ids in clean_by_set.values()):
        failures.append("each matched set must have exactly one clean specimen")

    z_by_batch: dict[str, list[float]] = defaultdict(list)
    ratio_errors: list[str] = []
    for sid in pet_ids:
        key = key_by_id[sid]
        set_id = key["opaque_matched_set_id"]
        clean_ids = clean_by_set.get(set_id, [])
        if len(clean_ids) != 1 or sid not in k20_by_id or clean_ids[0] not in k20_by_id:
            ratio_errors.append(f"{sid}: matched clean is not uniquely calculable")
            continue
        ratio = k20_by_id[sid] / k20_by_id[clean_ids[0]]
        z = math.log(ratio)
        z_by_batch[key["analyst_batch_code"]].append(z)
        result = result_by_id[sid]
        reported_ratio = first(result, ("ratio_to_matched_clean", "matched_clean_ratio", "K20_ratio"))
        reported_z = first(result, ("log_ratio_to_matched_clean", "z_btr", "matched_log_ratio"))
        if reported_ratio not in (None, "") and not close(parse_float(reported_ratio), ratio):
            ratio_errors.append(f"{sid}: matched ratio mismatch")
        if reported_z not in (None, "") and not close(parse_float(reported_z), z):
            ratio_errors.append(f"{sid}: log matched ratio mismatch")
        if reported_ratio in (None, "") and reported_z in (None, ""):
            ratio_errors.append(f"{sid}: evaluator emitted neither matched ratio nor log ratio")
    failures.extend(ratio_errors)

    endpoint_by_batch = {
        str(first(row, ("analyst_batch_code", "batch_code"), "")): row
        for row in batch_rows
    }
    endpoint_errors: list[str] = []
    if len(endpoint_by_batch) != len(batch_rows) or "" in endpoint_by_batch:
        endpoint_errors.append("batch endpoint IDs are blank or duplicated")
    if set(endpoint_by_batch) != set(z_by_batch):
        endpoint_errors.append("batch endpoint identity set differs from independently aggregated PET batches")
    for batch_code, values in z_by_batch.items():
        if batch_code not in endpoint_by_batch:
            continue
        mean_z = statistics.fmean(values)
        endpoint = endpoint_by_batch[batch_code]
        reported = first(endpoint, ("R_bt", "mean_log_ratio", "batch_mean_log_ratio", "batch_log_ratio"))
        if reported in (None, "") or not close(parse_float(reported), mean_z):
            endpoint_errors.append(f"{batch_code}: R_bt mismatch")
        n_value = first(endpoint, ("valid_matched_set_n", "valid_technical_replicate_n", "valid_matched_sets", "n"))
        if n_value not in (None, "") and int(str(n_value)) != len(values):
            endpoint_errors.append(f"{batch_code}: valid matched-set count mismatch")
    failures.extend(endpoint_errors)

    counts = {
        "capture_n": len(capture_rows), "analyst_key_n": len(key_rows),
        "specimen_result_n": len(specimen_rows), "clean_n": sum(map(len, clean_by_set.values())),
        "pet_n": len(pet_ids), "matched_set_n": len(clean_by_set),
        "batch_endpoint_n": len(batch_rows), "independent_batch_n": len(z_by_batch),
    }
    counts_exact = counts == {
        "capture_n": 54, "analyst_key_n": 54, "specimen_result_n": 54,
        "clean_n": 9, "pet_n": 45, "matched_set_n": 9,
        "batch_endpoint_n": 15, "independent_batch_n": 15,
    }
    replicate_counts = sorted(len(values) for values in z_by_batch.values())
    checks = {
        "counts_exact": counts_exact,
        "all_K20_exact": not k_errors and len(k20_by_id) == 54,
        "matched_ratios_exact": not ratio_errors and len(pet_ids) == 45,
        "batch_endpoints_exact": not endpoint_errors and len(z_by_batch) == 15,
        "three_technical_sets_per_batch": replicate_counts == [3] * 15,
    }
    return {
        "pass": not failures and all(checks.values()),
        "checks": checks, "counts": counts, "failures": failures,
    }, {
        "capture_fields": capture_fields, "key_fields": key_fields,
        "specimen_fields": specimen_fields, "batch_fields": batch_fields,
    }


def perform_audit(design_dir: Path, verification_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    audit = Audit()
    started = utc_now()
    design_before = tree_snapshot(design_dir)
    verification_before = tree_snapshot(verification_dir)

    design_path = design_dir / "resolved_design.json"
    design, design_error = load_json(design_path)
    design = design if isinstance(design, dict) else {}
    audit.add(
        "parent_design_identity",
        design_error is None
        and design.get("schema") == DESIGN_SCHEMA
        and design.get("stage") == "Stage33D"
        and design.get("status") == "frozen_predata_design_only_execution_closed"
        and design.get("passed") is True,
        "parent must be the passed, execution-closed Stage33D design",
        {"error": design_error, "schema": design.get("schema"), "status": design.get("status")},
    )
    parent_design_counts = design.get("design", {})
    audit.add(
        "parent_design_counts_and_authority",
        parent_design_counts.get("total_columns") == 54
        and parent_design_counts.get("pet_columns") == 45
        and parent_design_counts.get("clean_columns") == 9
        and parent_design_counts.get("independent_pet_batches") == 15
        and authority_closed(design.get("authority")),
        "parent design must freeze 54/45/9 columns, 15 independent batches, and no execution authority",
        {"design": parent_design_counts, "authority": design.get("authority")},
    )
    audit_bindings(audit, "parent_source_lineage", design.get("source_bindings"), design_dir)

    verification_path = verification_dir / "verification.json"
    completion_path = verification_dir / "completion.json"
    verification, verification_error = load_json(verification_path)
    verification = verification if isinstance(verification, dict) else {}
    completion, completion_error = load_json(completion_path)
    completion = completion if isinstance(completion, dict) else {}
    audit.add(
        "verification_identity",
        verification_error is None
        and verification.get("schema") == VERIFICATION_SCHEMA
        and verification.get("stage") == STAGE
        and verification.get("status") == "passed_synthetic_workflow_qualification"
        and verification.get("pass") is True,
        "verification must be the passing Stage33D-O v1 synthetic qualification",
        {"error": verification_error, "schema": verification.get("schema"),
         "stage": verification.get("stage"), "status": verification.get("status")},
    )
    audit.add(
        "verification_is_synthetic_and_authority_closed",
        verification.get("no_empirical_data") is True
        and authority_closed(verification.get("authority")),
        "verification must explicitly contain no empirical data and close every authority",
        {"no_empirical_data": verification.get("no_empirical_data"),
         "authority": verification.get("authority")},
    )

    parent_entries, parent_errors = binding_entries(verification.get("design"))
    parent_map = {role: item for role, item in parent_entries}
    parent_expected = {
        "stage33d_design": design_path,
        "stage33d_design_audit": ROOT / "stage33_evaluations"
        / "stage33d_matched_pet_lbs_physical_validation_20260901" / "design_audit_01" / "design_audit.json",
    }
    audit_bindings(
        audit, "verification_parent_bindings", parent_map, verification_dir,
        expected=parent_expected, require_exact_roles=True,
    )
    if parent_errors:
        audit.add("verification_parent_binding_shape", False, "design bindings must be role keyed", parent_errors)

    production_paths = audit_bindings(
        audit, "production_script_bindings", verification.get("production_scripts"), verification_dir,
        expected=EXPECTED_PRODUCTION_SCRIPTS, require_exact_roles=True,
    )
    audit.add(
        "auditor_self_binding",
        production_paths.get("stage33do_release_auditor") is not None
        and same_path(production_paths["stage33do_release_auditor"], Path(__file__)),
        "the verifier must bind this exact auditor source",
        str(production_paths.get("stage33do_release_auditor")),
    )
    verification_bound_paths = audit_bindings(
        audit, "verification_hash_bindings", verification.get("hash_bindings"), verification_dir
    )

    release_binding_entries = recursive_binding_entries(verification.get("release"))
    release_binding_map = {role: item for role, item in release_binding_entries}
    release_paths = audit_bindings(
        audit, "verification_release_bindings", release_binding_map, verification_dir
    )
    bound_release_names = {path.name for path in release_paths.values()}
    audit.add(
        "verification_release_bindings_cover_key_states",
        {"release_manifest.json", "primary_freeze_commitment.json", "reveal_declaration.json"}
        <= bound_release_names,
        "verification release section must directly hash-bind manifest, primary freeze and reveal declaration",
        {"bound_names": sorted(bound_release_names)},
    )

    release_dir = verification_dir / "successful_release" / "release"
    pre_reveal_dir = verification_dir / "successful_release" / "pre_reveal_evaluation"
    evaluation_dir = verification_dir / "successful_release" / "evaluation"
    release_missing = sorted(
        relative for relative in EXPECTED_RELEASE_FILES if not (release_dir / relative).is_file()
    )
    evaluation_missing = sorted(
        relative for relative in EXPECTED_EVALUATION_FILES if not (evaluation_dir / relative).is_file()
    )
    secret_candidates = [
        path for role, path in verification_bound_paths.items()
        if "secret" in role.casefold() or "secret" in path.name.casefold()
    ]
    secret_findings: list[str] = []
    package_files = [
        path for domain in (release_dir / "operator", release_dir / "analyst")
        for path in domain.rglob("*") if path.is_file()
    ]
    for secret_path in secret_candidates:
        secret_bytes = secret_path.read_bytes()
        if not secret_bytes:
            secret_findings.append(f"empty test secret: {secret_path}")
            continue
        for package_file in package_files:
            if secret_bytes in package_file.read_bytes():
                secret_findings.append(
                    f"test secret bytes from {secret_path.name} leaked into {package_file}"
                )
    audit.add(
        "test_secret_bytes_absent_from_nonrestricted_packages",
        len(secret_candidates) == 1 and not secret_findings,
        "exactly one hash-bound test secret must exist and its bytes must be absent from operator and analyst domains",
        {"secret_candidates": [str(path) for path in secret_candidates], "findings": secret_findings},
    )
    pre_reveal_missing = sorted(
        relative for relative in EXPECTED_PRE_REVEAL_FILES if not (pre_reveal_dir / relative).is_file()
    )
    audit.add(
        "expected_release_tree_complete", not release_missing,
        "synthetic release must contain every frozen restricted/operator/analyst artifact",
        {"release_dir": str(release_dir), "missing": release_missing},
    )
    audit.add(
        "expected_evaluation_tree_complete", not evaluation_missing,
        "synthetic evaluation must contain specimen, batch, condition, evaluation and completion artifacts",
        {"evaluation_dir": str(evaluation_dir), "missing": evaluation_missing},
    )
    audit.add(
        "expected_pre_reveal_tree_complete", not pre_reveal_missing,
        "pre-reveal evaluation must freeze specimen results, 15 batch endpoints, exclusions and completion before reveal",
        {"pre_reveal_dir": str(pre_reveal_dir), "missing": pre_reveal_missing},
    )

    release_manifest_path = release_dir / "release_manifest.json"
    release_manifest, release_error = load_json(release_manifest_path)
    release_manifest = release_manifest if isinstance(release_manifest, dict) else {}
    audit.add(
        "release_manifest_synthetic_identity",
        release_error is None
        and release_manifest.get("stage") == STAGE
        and release_manifest.get("passed") is True
        and release_manifest.get("test_only") is True
        and release_manifest.get("no_empirical_data") is True,
        "release manifest must be passing, test-only Stage33D-O with no empirical data",
        {"error": release_error, "schema": release_manifest.get("schema"),
         "stage": release_manifest.get("stage"), "test_only": release_manifest.get("test_only"),
         "no_empirical_data": release_manifest.get("no_empirical_data")},
    )
    audit.add(
        "release_authority_closed", authority_closed(release_manifest.get("authority")),
        "release manifest must close every authority",
        release_manifest.get("authority"),
    )
    audit.add(
        "release_manifest_schema_exact",
        release_manifest.get("schema") == "pet.stage33do-matched-hydraulics-operational-release.v1",
        "top-level release manifest schema must be the frozen Stage33D-O v1 schema",
        release_manifest.get("schema"),
    )
    audit_bindings(
        audit, "release_manifest_source_bindings",
        release_manifest.get("source_bindings", release_manifest.get("sources")), release_dir,
    )
    audit_bindings(
        audit, "release_manifest_artifact_bindings",
        release_manifest.get("artifacts"), release_dir,
    )

    prepared_state_path = release_dir / "prepared_release_state.json"
    frozen_state_path = release_dir / "frozen_release_state.json"
    prepared_state, prepared_state_error = load_json(prepared_state_path)
    frozen_state, frozen_state_error = load_json(frozen_state_path)
    prepared_state = prepared_state if isinstance(prepared_state, dict) else {}
    frozen_state = frozen_state if isinstance(frozen_state, dict) else {}
    prepared_expected = {
        "source_release_manifest_sha256": sha256(release_manifest_path) if release_manifest_path.is_file() else None,
        "raw_operator_capture_sha256": sha256(release_dir / "operator" / "operator_capture.csv") if (release_dir / "operator" / "operator_capture.csv").is_file() else None,
        "raw_linearity_capture_sha256": sha256(release_dir / "operator" / "darcy_linearity_capture.csv") if (release_dir / "operator" / "darcy_linearity_capture.csv").is_file() else None,
        "sanitized_hydraulic_capture_sha256": sha256(release_dir / "analyst" / "sanitized_hydraulic_capture.csv") if (release_dir / "analyst" / "sanitized_hydraulic_capture.csv").is_file() else None,
        "linearity_gate_attestation_sha256": sha256(release_dir / "restricted" / "linearity_gate_attestation.json") if (release_dir / "restricted" / "linearity_gate_attestation.json").is_file() else None,
    }
    audit.add(
        "prepared_release_state_exact",
        prepared_state_error is None
        and prepared_state.get("schema") == "pet.stage33do-prepared-release-state.v1"
        and prepared_state.get("state") == "CAPTURE_SANITIZED_AND_LINEARITY_ATTESTED_PRE_REVEAL"
        and prepared_state.get("passed") is True and prepared_state.get("test_only") is True
        and all(prepared_state.get(field) == actual for field, actual in prepared_expected.items()),
        "prepared state must bind the manifest and exact raw/sanitized capture plus linearity evidence before reveal",
        {"error": prepared_state_error, "schema": prepared_state.get("schema"),
         "state": prepared_state.get("state"), "expected_hashes": prepared_expected},
    )

    restricted_manifest, restricted_error = load_json(release_dir / "restricted" / "restricted_manifest.json")
    operator_manifest, operator_manifest_error = load_json(release_dir / "operator" / "operator_manifest.json")
    analyst_manifest, analyst_manifest_error = load_json(release_dir / "analyst" / "analyst_manifest.json")
    restricted_manifest = restricted_manifest if isinstance(restricted_manifest, dict) else {}
    operator_manifest = operator_manifest if isinstance(operator_manifest, dict) else {}
    analyst_manifest = analyst_manifest if isinstance(analyst_manifest, dict) else {}
    audit.add(
        "domain_manifest_schemas_exact",
        restricted_error is None
        and operator_manifest_error is None
        and analyst_manifest_error is None
        and restricted_manifest.get("schema") == "pet.stage33do-hydraulic-restricted-package.v1"
        and operator_manifest.get("schema") == "pet.stage33do-hydraulic-operator-package.v1"
        and analyst_manifest.get("schema") == "pet.stage33do-hydraulic-analyst-package.v1",
        "restricted, operator and analyst manifests must use the frozen domain schemas",
        {"errors": [value for value in (restricted_error, operator_manifest_error, analyst_manifest_error) if value],
         "restricted_schema": restricted_manifest.get("schema"),
         "operator_schema": operator_manifest.get("schema"),
         "analyst_schema": analyst_manifest.get("schema")},
    )
    audit_bindings(
        audit, "restricted_manifest_artifact_bindings",
        restricted_manifest.get("artifacts"), release_dir / "restricted",
    )
    audit_bindings(
        audit, "operator_manifest_artifact_bindings",
        operator_manifest.get("artifacts"), release_dir / "operator",
    )
    audit_bindings(
        audit, "analyst_manifest_artifact_bindings",
        analyst_manifest.get("artifacts"), release_dir / "analyst",
    )

    roles_path = release_dir / "restricted" / "roles.json"
    roles, roles_error = load_json(roles_path)
    roles = roles if isinstance(roles, dict) else {}
    role_container = roles.get("roles") if isinstance(roles.get("roles"), dict) else roles
    role_ids = [
        role_container.get(name, {}).get("role_id")
        if isinstance(role_container.get(name), dict) else None
        for name in ("operator", "analyst", "custodian")
    ]
    audit.add(
        "semantic_roles_distinct_and_test_only",
        roles_error is None
        and roles.get("schema") == "pet.stage33do-semantic-roles.v1"
        and roles.get("test_only") is True
        and all(isinstance(role_id, str) and role_id.strip() for role_id in role_ids)
        and len(set(role_ids)) == 3,
        "operator, analyst and custodian must have three distinct nonempty test-only role IDs",
        {"error": roles_error, "schema": roles.get("schema"), "test_only": roles.get("test_only"),
         "role_ids": role_ids},
    )

    operator_scan = scan_domain(
        release_dir / "operator", OPERATOR_FORBIDDEN_HEADERS, OPERATOR_FORBIDDEN_TOKENS
    )
    audit.add(
        "operator_package_has_no_treatment_morphology_prediction_leakage",
        operator_scan["pass"],
        "operator domain must omit treatment, source, PET/clean role, morphology, chemistry and predictions",
        operator_scan,
    )
    analyst_scan = scan_domain(
        release_dir / "analyst", ANALYST_FORBIDDEN_HEADERS,
        {"condition_id", "source_batch", "reactor_block", "target_temperature", "prediction", "t120", "t140", "t160", "t180", "t20"},
    )
    audit.add(
        "analyst_package_has_no_treatment_source_prediction_leakage",
        analyst_scan["pass"],
        "analyst domain may expose role/morphology but must omit treatment, source batch and predictions",
        analyst_scan,
    )

    cross_fields, cross_rows, cross_error = read_csv(release_dir / "restricted" / "custodian_crosswalk.csv")
    reveal_fields, reveal_rows, reveal_error = read_csv(release_dir / "restricted" / "reveal_key.csv")
    operator_fields, operator_rows, operator_error = read_csv(release_dir / "operator" / "operator_capture.csv")
    analyst_fields, analyst_rows, analyst_error = read_csv(release_dir / "analyst" / "blinded_analysis_key.csv")
    role_counts = Counter(row.get("specimen_role", "") for row in cross_rows)
    source_batches = {row.get("source_batch_slot", "") for row in cross_rows if row.get("specimen_role") == "pet_mixture"}
    operator_ids = [row.get("opaque_specimen_id", "") for row in operator_rows]
    analyst_ids = [row.get("opaque_specimen_id", "") for row in analyst_rows]
    cross_ids = [row.get("opaque_specimen_id", "") for row in cross_rows]
    count_ok = (
        not any((cross_error, reveal_error, operator_error, analyst_error))
        and len(cross_rows) == len(operator_rows) == len(analyst_rows) == 54
        and role_counts == Counter({"pet_mixture": 45, "clean_lbs_control": 9})
        and len(source_batches) == 15 and "" not in source_batches
        and len(reveal_rows) == 15
        and len(set(operator_ids)) == len(set(analyst_ids)) == len(set(cross_ids)) == 54
        and set(operator_ids) == set(analyst_ids) == set(cross_ids)
    )
    audit.add(
        "release_count_and_identity_closure", count_ok,
        "crosswalk/operator/analyst must close 54 unique identities with 45 PET, 9 clean and 15 unpooled batches",
        {"errors": [value for value in (cross_error, reveal_error, operator_error, analyst_error) if value],
         "crosswalk_n": len(cross_rows), "operator_n": len(operator_rows), "analyst_n": len(analyst_rows),
         "reveal_n": len(reveal_rows), "role_counts": dict(role_counts), "batch_n": len(source_batches)},
    )
    audit.add(
        "operator_headers_exactly_blinded",
        not (set(field.casefold() for field in operator_fields) & OPERATOR_FORBIDDEN_HEADERS),
        "operator capture headers must contain no restricted, treatment, morphology, chemistry or prediction fields",
        {"headers": operator_fields,
         "forbidden_intersection": sorted(set(field.casefold() for field in operator_fields) & OPERATOR_FORBIDDEN_HEADERS)},
    )
    expected_analyst_fields = {
        "operational_release_id", "opaque_specimen_id", "opaque_matched_set_id",
        "specimen_role", "analyst_batch_code",
    }
    audit.add(
        "analyst_key_fields_exact_and_nonjoinable",
        set(analyst_fields) == expected_analyst_fields,
        "analyst key must expose exactly specimen, matched set, role and opaque batch code—no design order or sentinel",
        {"headers": analyst_fields, "expected": sorted(expected_analyst_fields)},
    )

    linearity_fields, linearity_rows, linearity_error = read_csv(
        release_dir / "operator" / "darcy_linearity_capture.csv"
    )
    linearity_cross_fields, linearity_cross_rows, linearity_cross_error = read_csv(
        release_dir / "restricted" / "linearity_crosswalk.csv"
    )
    linearity_ids = [row.get("opaque_linearity_id", "") for row in linearity_rows]
    cross_linearity_ids = [row.get("opaque_linearity_id", "") for row in linearity_cross_rows]
    audit.add(
        "opaque_linearity_separation_and_counts",
        not any((linearity_error, linearity_cross_error))
        and "opaque_linearity_id" in linearity_fields
        and "opaque_specimen_id" not in linearity_fields
        and len(linearity_rows) == 18
        and len(set(linearity_ids)) == 6 and "" not in linearity_ids
        and len(linearity_cross_rows) == 6
        and len(set(cross_linearity_ids)) == 6 and set(cross_linearity_ids) == set(linearity_ids)
        and {row.get("opaque_specimen_id", "") for row in linearity_cross_rows} <= set(operator_ids),
        "operator linearity must use six unjoinable opaque IDs × three gradients; only restricted crosswalk may map them",
        {"errors": [value for value in (linearity_error, linearity_cross_error) if value],
         "linearity_headers": linearity_fields, "linearity_row_n": len(linearity_rows),
         "opaque_linearity_id_n": len(set(linearity_ids)), "crosswalk_row_n": len(linearity_cross_rows)},
    )

    freeze_path = release_dir / "restricted" / "primary_freeze_commitment.json"
    freeze, freeze_error = load_json(freeze_path)
    freeze = freeze if isinstance(freeze, dict) else {}
    capture_sha = sha256(release_dir / "operator" / "operator_capture.csv") if (release_dir / "operator" / "operator_capture.csv").is_file() else None
    linearity_sha = sha256(release_dir / "operator" / "darcy_linearity_capture.csv") if (release_dir / "operator" / "darcy_linearity_capture.csv").is_file() else None
    analyst_key_path = release_dir / "analyst" / "blinded_analysis_key.csv"
    sanitized_capture_path = release_dir / "analyst" / "sanitized_hydraulic_capture.csv"
    morphology_path = release_dir / "analyst" / "synthetic_morphology_summary.csv"
    preparation_path = release_dir / "restricted" / "preparation_records.csv"
    reveal_path = release_dir / "restricted" / "reveal_key.csv"
    linearity_crosswalk_path = release_dir / "restricted" / "linearity_crosswalk.csv"
    linearity_attestation_path = release_dir / "restricted" / "linearity_gate_attestation.json"
    commitment_path = release_dir / "restricted" / "cross_release_commitment.json"
    precommit, precommit_error = load_json(commitment_path)
    precommit = precommit if isinstance(precommit, dict) else {}
    release_id = first(release_manifest, ("operational_release_id", "release_id"))
    commitment_manifest_expected = {
        "operator_manifest_sha256": sha256(release_dir / "operator" / "operator_manifest.json") if (release_dir / "operator" / "operator_manifest.json").is_file() else None,
        "analyst_manifest_sha256": sha256(release_dir / "analyst" / "analyst_manifest.json") if (release_dir / "analyst" / "analyst_manifest.json").is_file() else None,
        "restricted_manifest_sha256": sha256(release_dir / "restricted" / "restricted_manifest.json") if (release_dir / "restricted" / "restricted_manifest.json").is_file() else None,
    }
    commitment_template_expected = {
        "custodian_crosswalk_sha256": sha256(release_dir / "restricted" / "custodian_crosswalk.csv") if (release_dir / "restricted" / "custodian_crosswalk.csv").is_file() else None,
        "preparation_records_sha256": sha256(preparation_path) if preparation_path.is_file() else None,
        "reveal_key_sha256": sha256(reveal_path) if reveal_path.is_file() else None,
        "linearity_crosswalk_sha256": sha256(linearity_crosswalk_path) if linearity_crosswalk_path.is_file() else None,
        "roles_sha256": sha256(roles_path) if roles_path.is_file() else None,
    }
    manifest_bindings = precommit.get("manifest_bindings") if isinstance(precommit.get("manifest_bindings"), dict) else {}
    template_bindings = precommit.get("template_sha256") if isinstance(precommit.get("template_sha256"), dict) else {}
    commitment_manifest_links_exact = all(
        manifest_bindings.get(field.removesuffix("_sha256")) == actual
        for field, actual in commitment_manifest_expected.items()
    )
    commitment_template_links_exact = all(
        template_bindings.get(field.removesuffix("_sha256")) == actual
        for field, actual in commitment_template_expected.items()
    )
    lineage_bindings = precommit.get("lineage_bindings") if isinstance(precommit.get("lineage_bindings"), dict) else {}
    expected_lineage_hashes = {
        "stage33d_design_sha256": sha256(design_path) if design_path.is_file() else None,
        "acceptance_gates_sha256": sha256(design_dir / "acceptance_gates.json") if (design_dir / "acceptance_gates.json").is_file() else None,
        "builder_sha256": sha256(EXPECTED_PRODUCTION_SCRIPTS["stage33do_release_builder"]) if EXPECTED_PRODUCTION_SCRIPTS["stage33do_release_builder"].is_file() else None,
        "roles_sha256": sha256(roles_path) if roles_path.is_file() else None,
    }
    lineage_hashes_valid = all(
        lineage_bindings.get(key) == actual for key, actual in expected_lineage_hashes.items()
    )
    audit.add(
        "premeasurement_commitment_schema_exact",
        precommit_error is None
        and precommit.get("schema") == "pet.stage33do-cross-release-commitment.v1"
        and precommit.get("state") == "CUSTODIAN_COMMITTED_PREMEASUREMENT"
        and first(precommit, ("operational_release_id", "release_id")) == release_id
        and precommit.get("test_only") is True
        and precommit.get("contains_raw_secret") is False
        and precommit.get("contains_treatment_key") is False
        and precommit.get("nonrestricted_contains_condition") is False
        and commitment_manifest_links_exact and commitment_template_links_exact
        and lineage_hashes_valid,
        "premesurement commitment must be test-only, nonrevealing, release-matched and exactly bind all three domains",
        {"error": precommit_error, "schema": precommit.get("schema"), "state": precommit.get("state"),
         "release_id": first(precommit, ("operational_release_id", "release_id")), "expected_release_id": release_id,
         "test_only": precommit.get("test_only"), "contains_raw_secret": precommit.get("contains_raw_secret"),
         "contains_treatment_key": precommit.get("contains_treatment_key"),
         "nonrestricted_contains_condition": precommit.get("nonrestricted_contains_condition"),
         "expected_manifest_links": commitment_manifest_expected,
         "manifest_links_exact": commitment_manifest_links_exact,
         "expected_template_links": commitment_template_expected,
         "template_links_exact": commitment_template_links_exact,
         "lineage_bindings": lineage_bindings, "expected_lineage_hashes": expected_lineage_hashes,
         "lineage_hashes_valid": lineage_hashes_valid},
    )

    attestation, attestation_error = load_json(linearity_attestation_path)
    attestation = attestation if isinstance(attestation, dict) else {}
    attestation_rows = first(attestation, ("rows", "sentinels", "linearity_gates", "records"), [])
    attestation_rows = attestation_rows if isinstance(attestation_rows, list) else []
    attestation_ids = [str(first(row, ("opaque_linearity_id",), "")) for row in attestation_rows if isinstance(row, dict)]
    attestation_all_pass = all(
        isinstance(row, dict) and row.get("passed", row.get("pass")) is True
        for row in attestation_rows
    )
    evaluator_script_hash = sha256(EXPECTED_PRODUCTION_SCRIPTS["stage33do_evaluator"]) if EXPECTED_PRODUCTION_SCRIPTS["stage33do_evaluator"].is_file() else None
    audit.add(
        "linearity_gate_attestation_exact",
        attestation_error is None
        and len(attestation_rows) == 6 and len(set(attestation_ids)) == 6
        and set(attestation_ids) == set(linearity_ids)
        and attestation_all_pass
        and first(attestation, ("raw_linearity_sha256", "darcy_linearity_capture_sha256", "linearity_sha256")) == linearity_sha
        and first(attestation, ("evaluator_sha256", "evaluator_script_sha256")) == evaluator_script_hash
        and all("opaque_specimen_id" not in row and "condition_id" not in row for row in attestation_rows),
        "attestation must contain six opaque-ID-only passing sentinel gates and bind raw linearity plus evaluator source",
        {"error": attestation_error, "row_n": len(attestation_rows), "ids": attestation_ids,
         "all_pass": attestation_all_pass, "declared_linearity": first(attestation, ("raw_linearity_sha256", "darcy_linearity_capture_sha256", "linearity_sha256")),
         "actual_linearity": linearity_sha, "declared_evaluator": first(attestation, ("evaluator_sha256", "evaluator_script_sha256")),
         "actual_evaluator": evaluator_script_hash},
    )

    pre_specimen_path = pre_reveal_dir / "specimen_results.csv"
    pre_batch_path = pre_reveal_dir / "batch_endpoints.csv"
    exclusion_path = pre_reveal_dir / "exclusion_ledger.csv"
    pre_eval_path = pre_reveal_dir / "pre_reveal_evaluation.json"
    pre_batch_fields, pre_batch_rows, pre_batch_error = read_csv(pre_batch_path)
    exclusion_fields, exclusion_rows, exclusion_error = read_csv(exclusion_path)
    pre_eval, pre_eval_error = load_json(pre_eval_path)
    pre_eval = pre_eval if isinstance(pre_eval, dict) else {}
    pre_reveal_forbidden = {
        "condition_id", "target_temperature_c", "source_batch_slot", "source_batch_id",
        "reactor_block", "design_specimen_slot", "run_order", "numerical_prediction",
    }
    audit.add(
        "pre_reveal_batch_endpoints_exact_and_blinded",
        pre_batch_error is None
        and len(pre_batch_rows) == 15
        and "analyst_batch_code" in pre_batch_fields
        and len({row.get("analyst_batch_code", "") for row in pre_batch_rows}) == 15
        and "" not in {row.get("analyst_batch_code", "") for row in pre_batch_rows}
        and not (set(field.casefold() for field in pre_batch_fields) & pre_reveal_forbidden)
        and exclusion_error is None
        and not (set(field.casefold() for field in exclusion_fields) & pre_reveal_forbidden),
        "exactly 15 analyst-code-only primary batch endpoints and a treatment-blind exclusion ledger must exist before reveal",
        {"batch_error": pre_batch_error, "batch_row_n": len(pre_batch_rows),
         "batch_headers": pre_batch_fields, "exclusion_error": exclusion_error,
         "exclusion_row_n": len(exclusion_rows), "exclusion_headers": exclusion_fields},
    )
    audit.add(
        "pre_reveal_evaluation_synthetic_and_nonrevealing",
        pre_eval_error is None
        and pre_eval.get("stage") == STAGE
        and pre_eval.get("passed") is True
        and pre_eval.get("test_only") is True
        and pre_eval.get("no_empirical_data") is True
        and first(pre_eval, ("reveal_used", "treatment_key_read")) is False,
        "pre-reveal evaluation must pass synthetically without using a treatment reveal",
        {"error": pre_eval_error, "schema": pre_eval.get("schema"), "stage": pre_eval.get("stage"),
         "passed": pre_eval.get("passed"), "test_only": pre_eval.get("test_only"),
         "no_empirical_data": pre_eval.get("no_empirical_data"),
         "reveal_used": first(pre_eval, ("reveal_used", "treatment_key_read"))},
    )

    sealer_hash = sha256(EXPECTED_PRODUCTION_SCRIPTS["stage33do_primary_freeze_sealer"]) if EXPECTED_PRODUCTION_SCRIPTS["stage33do_primary_freeze_sealer"].is_file() else None
    freeze_expected = {
        "cross_release_commitment_sha256": sha256(commitment_path) if commitment_path.is_file() else None,
        "raw_operator_capture_sha256": capture_sha,
        "raw_linearity_capture_sha256": linearity_sha,
        "linearity_gate_attestation_sha256": sha256(linearity_attestation_path) if linearity_attestation_path.is_file() else None,
        "blinded_analysis_key_sha256": sha256(analyst_key_path) if analyst_key_path.is_file() else None,
        "preparation_records_sha256": sha256(preparation_path) if preparation_path.is_file() else None,
        "synthetic_morphology_summary_sha256": sha256(morphology_path) if morphology_path.is_file() else None,
        "pre_reveal_specimen_results_sha256": sha256(pre_specimen_path) if pre_specimen_path.is_file() else None,
        "pre_reveal_batch_endpoints_sha256": sha256(pre_batch_path) if pre_batch_path.is_file() else None,
        "pre_reveal_exclusion_ledger_sha256": sha256(exclusion_path) if exclusion_path.is_file() else None,
        "pre_reveal_evaluation_sha256": sha256(pre_eval_path) if pre_eval_path.is_file() else None,
        "evaluator_sha256": evaluator_script_hash,
        "sealer_sha256": sealer_hash,
        "release_manifest_sha256": sha256(release_manifest_path) if release_manifest_path.is_file() else None,
    }
    freeze_links_exact = all(freeze.get(field) == actual for field, actual in freeze_expected.items())
    sanitized_hash = freeze.get("sanitized_hydraulic_capture_sha256")
    actual_sanitized_hash = sha256(sanitized_capture_path) if sanitized_capture_path.is_file() else None
    sanitized_hash_resolves = valid_sha(sanitized_hash) and sanitized_hash == actual_sanitized_hash
    audit.add(
        "primary_inputs_frozen_before_reveal",
        freeze_error is None
        and freeze.get("schema") == "pet.stage33do-primary-freeze-commitment.v1"
        and freeze.get("status") == "PRIMARY_ENDPOINTS_FROZEN_REVEAL_AUTHORIZED"
        and first(freeze, ("operational_release_id", "release_id")) == release_id
        and freeze.get("test_only") is True
        and freeze_links_exact and sanitized_hash_resolves,
        "primary freeze must exactly bind premeasurement commitment, raw/QC inputs, blinded inputs, exclusions, 15 endpoints, evaluator, sealer and manifest before reveal",
        {"error": freeze_error, "schema": freeze.get("schema"), "status": freeze.get("status"),
         "release_id": first(freeze, ("operational_release_id", "release_id")), "expected_release_id": release_id,
         "expected_links": freeze_expected, "links_exact": freeze_links_exact,
         "sanitized_hydraulic_capture_sha256": sanitized_hash,
         "actual_sanitized_hydraulic_capture_sha256": actual_sanitized_hash,
         "sanitized_hash_resolves_to_frozen_artifact": sanitized_hash_resolves},
    )

    reveal_declaration_path = release_dir / "restricted" / "reveal_declaration.json"
    reveal_declaration, reveal_declaration_error = load_json(reveal_declaration_path)
    reveal_declaration = reveal_declaration if isinstance(reveal_declaration, dict) else {}
    freeze_sha = sha256(freeze_path) if freeze_path.is_file() else None
    reveal_sha = sha256(reveal_path) if reveal_path.is_file() else None
    audit.add(
        "reveal_declared_after_primary_freeze",
        reveal_declaration_error is None
        and reveal_declaration.get("state") == "REVEAL_DECLARED_AFTER_PRIMARY_FREEZE"
        and first(reveal_declaration, ("operational_release_id", "release_id")) == release_id
        and reveal_declaration.get("test_only") is True
        and reveal_declaration.get("primary_freeze_commitment_sha256") == freeze_sha
        and reveal_declaration.get("reveal_key_sha256") == reveal_sha,
        "separate reveal declaration must release only the exact key after the exact primary freeze",
        {"error": reveal_declaration_error, "state": reveal_declaration.get("state"),
         "release_id": first(reveal_declaration, ("operational_release_id", "release_id")), "expected_release_id": release_id,
         "declared_freeze": reveal_declaration.get("primary_freeze_commitment_sha256"), "actual_freeze": freeze_sha,
         "declared_reveal_key": reveal_declaration.get("reveal_key_sha256"), "actual_reveal_key": reveal_sha},
    )
    frozen_expected = {
        "source_prepared_release_sha256": sha256(prepared_state_path) if prepared_state_path.is_file() else None,
        "primary_freeze_commitment_sha256": freeze_sha,
        "reveal_declaration_sha256": sha256(reveal_declaration_path) if reveal_declaration_path.is_file() else None,
    }
    audit.add(
        "frozen_release_state_exact",
        frozen_state_error is None
        and frozen_state.get("schema") == "pet.stage33do-frozen-release-state.v1"
        and frozen_state.get("state") == "PRIMARY_FROZEN_AND_REVEAL_DECLARED_TEST_ONLY"
        and frozen_state.get("passed") is True and frozen_state.get("test_only") is True
        and all(frozen_state.get(field) == actual for field, actual in frozen_expected.items()),
        "frozen state must bind the exact prepared state, primary freeze and post-freeze reveal declaration",
        {"error": frozen_state_error, "schema": frozen_state.get("schema"),
         "state": frozen_state.get("state"), "expected_hashes": frozen_expected},
    )

    design_slots = {row.get("design_specimen_slot", "") for row in cross_rows} - {""}
    condition_values = {row.get("condition_id", "") for row in cross_rows} - {""}
    source_values = {row.get("source_batch_slot", "") for row in cross_rows} - {""}
    nonrestricted_values = {
        value for row in operator_rows + analyst_rows for value in row.values() if isinstance(value, str)
    }
    leaked_exact_values = sorted((design_slots | condition_values | source_values) & nonrestricted_values)
    _, parent_matrix_rows, parent_matrix_error = read_csv(design_dir / "custodian_design_matrix.csv")
    parent_order_by_slot = {
        row.get("design_specimen_slot", ""): int(row.get("run_order", "0") or 0)
        for row in parent_matrix_rows
    }
    public_orders = []
    sequence_field = "operator_run_order" if "operator_run_order" in cross_fields else "operator_sequence"
    for row in sorted(cross_rows, key=lambda item: int(item.get(sequence_field, "0") or 0)):
        raw = first(row, ("design_run_order", "parent_run_order", "run_order"))
        if raw in (None, ""):
            raw = parent_order_by_slot.get(row.get("design_specimen_slot", ""))
        if raw not in (None, ""):
            public_orders.append(int(str(raw)))
    audit.add(
        "public_design_is_not_joinable_to_nonrestricted_packages",
        not leaked_exact_values
        and bool(public_orders) and public_orders != list(range(1, 55))
        and set(public_orders) == set(range(1, 55)),
        "fresh operator permutation must break public design order; design slots, conditions and source batches must not appear outside restricted custody",
        {"parent_matrix_error": parent_matrix_error, "leaked_exact_values": leaked_exact_values,
         "public_order_n": len(public_orders),
         "identity_permutation": public_orders == list(range(1, 55))},
    )

    hydraulic, hydraulic_schema = independently_check_hydraulics(release_dir, evaluation_dir)
    audit.add(
        "independent_K20_ratio_and_batch_endpoint_recalculation", hydraulic["pass"],
        "auditor must independently reproduce all 54 K20 values, 45 matched ratios and 15 batch endpoints",
        {**hydraulic, "schemas": hydraulic_schema},
    )

    evaluation_path = evaluation_dir / "evaluation.json"
    evaluation, evaluation_error = load_json(evaluation_path)
    evaluation = evaluation if isinstance(evaluation, dict) else {}
    audit.add(
        "evaluation_synthetic_identity_and_authority",
        evaluation_error is None and evaluation.get("stage") == STAGE
        and evaluation.get("passed") is True
        and evaluation.get("test_only") is True
        and evaluation.get("no_empirical_data") is True
        and authority_closed(evaluation.get("authority")),
        "evaluation must remain test-only, empirical-empty, passed and authority-closed",
        {"error": evaluation_error, "schema": evaluation.get("schema"),
         "stage": evaluation.get("stage"), "passed": evaluation.get("passed"),
         "test_only": evaluation.get("test_only"), "no_empirical_data": evaluation.get("no_empirical_data"),
         "authority": evaluation.get("authority")},
    )
    final_specimen_path = evaluation_dir / "specimen_results.csv"
    final_batch_path = evaluation_dir / "batch_endpoints.csv"
    condition_path = evaluation_dir / "condition_summary.csv"
    condition_fields, condition_rows, condition_error = read_csv(condition_path)
    condition_ids = {row.get("condition_id", "") for row in condition_rows}
    audit.add(
        "post_reveal_preserves_frozen_primary_tables",
        final_specimen_path.is_file() and final_batch_path.is_file()
        and sha256(final_specimen_path) == freeze.get("pre_reveal_specimen_results_sha256")
        and sha256(final_batch_path) == freeze.get("pre_reveal_batch_endpoints_sha256"),
        "post-reveal specimen and batch tables must be byte-identical to the primary tables frozen before reveal",
        {"final_specimen_sha256": sha256(final_specimen_path) if final_specimen_path.is_file() else None,
         "frozen_specimen_sha256": freeze.get("pre_reveal_specimen_results_sha256"),
         "final_batch_sha256": sha256(final_batch_path) if final_batch_path.is_file() else None,
         "frozen_batch_sha256": freeze.get("pre_reveal_batch_endpoints_sha256")},
    )
    audit.add(
        "condition_summary_is_post_freeze_and_reveal_bound",
        condition_error is None and len(condition_rows) == 5
        and condition_ids == {"T20", "T120", "T140", "T160", "T180"}
        and evaluation.get("primary_freeze_commitment_sha256") == freeze_sha
        and evaluation.get("reveal_declaration_sha256") == (
            sha256(reveal_declaration_path) if reveal_declaration_path.is_file() else None
        )
        and evaluation.get("condition_summary_sha256") == (
            sha256(condition_path) if condition_path.is_file() else None
        ),
        "five-condition summary may appear only in the post-reveal evaluation bound to the frozen primaries and reveal declaration",
        {"error": condition_error, "row_n": len(condition_rows), "condition_ids": sorted(condition_ids),
         "declared_freeze": evaluation.get("primary_freeze_commitment_sha256"), "actual_freeze": freeze_sha,
         "declared_reveal": evaluation.get("reveal_declaration_sha256"),
         "actual_reveal": sha256(reveal_declaration_path) if reveal_declaration_path.is_file() else None,
         "declared_condition_summary": evaluation.get("condition_summary_sha256"),
         "actual_condition_summary": sha256(condition_path) if condition_path.is_file() else None},
    )
    evaluation_completion, eval_completion_error = load_json(evaluation_dir / "completion.json")
    evaluation_completion = evaluation_completion if isinstance(evaluation_completion, dict) else {}
    audit.add(
        "evaluation_completion_hash_binding",
        eval_completion_error is None
        and evaluation_completion.get("status") == "complete"
        and evaluation_completion.get("passed") is True
        and first(evaluation_completion, ("evaluation_sha256",)) == sha256(evaluation_path),
        "evaluation completion must hash-bind the passing evaluation",
        {"error": eval_completion_error, "completion": evaluation_completion},
    )

    positive = verification.get("positive_release")
    positive = positive if isinstance(positive, dict) else {}
    positive_required_true = (
        "operator_package_blinded", "test_only_key_isolated", "capture_hash_bound",
        "linearity_hash_bound", "K20_exact_recomputation", "matched_ratio_exact_recomputation",
        "evaluator_checks_passed", "package_hashes_exact",
    )
    positive_counts = {
        "specimen_n": positive.get("specimen_n"), "pet_n": positive.get("pet_n"),
        "clean_n": positive.get("clean_n"), "batch_n": positive.get("batch_n"),
    }
    audit.add(
        "positive_release_summary_closure",
        positive.get("passed", positive.get("pass")) is True
        and positive_counts == {"specimen_n": 54, "pet_n": 45, "clean_n": 9, "batch_n": 15}
        and all(positive.get(field) is True for field in positive_required_true),
        "positive summary must affirm exact counts, isolation, bindings, K20/ratio arithmetic and evaluator checks",
        {"summary": positive, "required_true_fields": positive_required_true},
    )

    challenges_pass, challenge_detail = challenge_concepts(verification.get("negative_challenges"))
    audit.add(
        "negative_challenges_fail_closed", challenges_pass,
        "every required hostile lineage/leakage/state/linearity/key/role/non-test concept must be rejected",
        challenge_detail,
    )

    audit.add(
        "no_real_empirical_or_execution_artifacts",
        all(
            item is True for item in (
                verification.get("no_empirical_data") is True,
                release_manifest.get("no_empirical_data") is True,
                release_manifest.get("test_only") is True,
                evaluation.get("no_empirical_data") is True,
                evaluation.get("test_only") is True,
            )
        ),
        "all three layers must identify the evidence as synthetic-only and empirical-empty",
        {"verification": verification.get("no_empirical_data"),
         "release": {"test_only": release_manifest.get("test_only"), "no_empirical_data": release_manifest.get("no_empirical_data")},
         "evaluation": {"test_only": evaluation.get("test_only"), "no_empirical_data": evaluation.get("no_empirical_data")}},
    )

    completion_expected_sha = sha256(verification_path) if verification_path.is_file() else None
    audit.add(
        "verification_completion_hash_binding",
        completion_error is None and completion.get("status") == "complete"
        and completion.get("passed") is True
        and first(completion, ("verification_sha256",)) == completion_expected_sha,
        "verification completion must hash-bind the passing verification",
        {"error": completion_error, "declared": completion.get("verification_sha256"),
         "actual": completion_expected_sha},
    )

    design_after = tree_snapshot(design_dir)
    verification_after = tree_snapshot(verification_dir)
    unchanged = design_before == design_after and verification_before == verification_after
    audit.add(
        "inputs_remained_immutable", unchanged,
        "complete before/after SHA-256 snapshots of design and verification trees must be identical",
        {"design_file_n": len(design_before), "verification_file_n": len(verification_before)},
    )

    failed = [item["check_id"] for item in audit.checks if not item["pass"]]
    record = {
        "schema": AUDIT_SCHEMA,
        "stage": STAGE,
        "audit_id": "STAGE33DO-SYNTHETIC-QUALIFICATION-RELEASE-AUDIT-V1",
        "created_utc": started,
        "completed_utc": utc_now(),
        "status": "passed_synthetic_release_audit" if audit.passed else "failed_synthetic_release_audit",
        "pass": audit.passed,
        "check_n": len(audit.checks),
        "passed_check_n": len(audit.checks) - len(failed),
        "failed_check_n": len(failed),
        "failed_checks": failed,
        "checks": audit.checks,
        "inputs": {
            "design_dir": str(design_dir), "resolved_design_sha256": sha256(design_path) if design_path.is_file() else None,
            "verification_dir": str(verification_dir), "verification_sha256": completion_expected_sha,
        },
        "counts": hydraulic.get("counts", {}),
        "claim_boundary": (
            "synthetic software/release qualification only; no empirical PET morphology, hydraulic, "
            "temperature, molecular-degradation, length-proxy, prediction-validation, migration, "
            "clogging, deformation or coupling claim"
        ),
        "stop_boundary": (
            "stop before real keys or data, laboratory/DEM/LBM execution, unblinding, retuning, "
            "physical validation or degradation/permeability/coupling claims"
        ),
        "authority": verification.get("authority"),
        "input_mutation": False if unchanged else "DETECTED",
    }
    completion_record = {
        "schema": COMPLETION_SCHEMA,
        "stage": STAGE,
        "audit_id": record["audit_id"],
        "status": "complete" if audit.passed else "failed",
        "completed_utc": utc_now(),
        "passed": audit.passed,
        "failed_checks": failed,
        "no_input_modified": unchanged,
        "no_empirical_data": True,
        "no_real_key": True,
        "no_laboratory_execution": True,
        "no_simulation": True,
        "authority_closed": True,
    }
    return record, completion_record


def prepare_output(output: Path, design_dir: Path, verification_dir: Path) -> Path:
    unresolved = output.absolute()
    if unresolved.exists():
        if unresolved.is_symlink() or not unresolved.is_dir():
            raise RuntimeError(f"fail-closed: output must be a real directory: {unresolved}")
        if any(unresolved.iterdir()):
            raise RuntimeError(f"fail-closed: output directory is not empty: {unresolved}")
    resolved = unresolved.resolve()
    if contained(resolved, design_dir) or contained(resolved, verification_dir):
        raise RuntimeError("fail-closed: output must be disjoint from both read-only input trees")
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
    outer_design = tree_snapshot(design_dir)
    outer_verification = tree_snapshot(verification_dir)
    try:
        audit, completion = perform_audit(design_dir, verification_dir)
    except Exception as exc:
        try:
            unchanged = outer_design == tree_snapshot(design_dir) and outer_verification == tree_snapshot(verification_dir)
        except Exception:
            unchanged = False
        now = utc_now()
        audit = {
            "schema": AUDIT_SCHEMA, "stage": STAGE,
            "audit_id": "STAGE33DO-SYNTHETIC-QUALIFICATION-RELEASE-AUDIT-V1",
            "created_utc": now, "completed_utc": now,
            "status": "failed_synthetic_release_audit", "pass": False,
            "check_n": 1, "passed_check_n": 0, "failed_check_n": 1,
            "failed_checks": ["unexpected_auditor_exception"],
            "checks": [{
                "check_id": "unexpected_auditor_exception", "pass": False,
                "requirement": "malformed or hostile evidence must fail closed with a preserved record",
                "observed": {"exception_type": type(exc).__name__, "message": str(exc)},
            }],
            "claim_boundary": "audit aborted; no release or empirical claim is authorized",
            "stop_boundary": "fail closed and investigate the preserved exception",
            "authority": {}, "input_mutation": False if unchanged else "DETECTED",
        }
        completion = {
            "schema": COMPLETION_SCHEMA, "stage": STAGE,
            "audit_id": audit["audit_id"], "status": "failed", "completed_utc": now,
            "passed": False, "failed_checks": ["unexpected_auditor_exception"],
            "no_input_modified": unchanged, "no_empirical_data": True, "no_real_key": True,
            "no_laboratory_execution": True, "no_simulation": True, "authority_closed": True,
        }
    json_dump(output / "audit.json", audit)
    completion["audit_sha256"] = sha256(output / "audit.json")
    json_dump(output / "completion.json", completion)
    print(json.dumps(completion, indent=2, sort_keys=True))
    return 0 if audit.get("pass") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
