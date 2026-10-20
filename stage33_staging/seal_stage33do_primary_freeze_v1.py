#!/usr/bin/env python3
"""Create immutable prepared and primary-frozen Stage33D-O synthetic releases.

This sealer is deliberately synthetic-only and has two state transitions:

``prepare`` copies a premeasurement release into a new directory, adds completed
operator captures, creates an analyst-safe hydraulic capture, and evaluates the
six opaque Darcy-linearity sentinels without resolving their specimen identities.

``freeze`` copies that prepared release into another new directory and adds a
primary commitment binding the blinded pre-reveal endpoints.  Only after that
commitment exists does it add the separately hash-bound reveal declaration.

No existing input is modified.  Passing this program qualifies release-process
software only; it does not authorize real data, laboratory work, simulation, or
any physical or degradation claim.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import statistics
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "Stage33D-O"
RELEASE_SCHEMA = "pet.stage33do-matched-hydraulics-operational-release.v1"
PRECOMMIT_SCHEMA = "pet.stage33do-cross-release-commitment.v1"
ATTESTATION_SCHEMA = "pet.stage33do-linearity-gate-attestation.v1"
FREEZE_SCHEMA = "pet.stage33do-primary-freeze-commitment.v1"
REVEAL_SCHEMA = "pet.stage33do-reveal-declaration.v1"
PRE_EVAL_SCHEMA = "pet.stage33do-matched-hydraulics-pre-reveal-evaluation.v1"
TEST_RELEASE_RE = re.compile(r"(?:TEST|SYNTHETIC|QUALIFICATION)", re.IGNORECASE)

RAW_CAPTURE_FIELDS = [
    "operational_release_id", "opaque_specimen_id", "water_temperature_c",
    "specimen_diameter_mm", "specimen_length_mm", "head_difference_m",
    "collection_time_s", "collected_water_mass_g", "calculated_K20_m_s",
    "saturated", "leak_free", "steady_state", "effluent_pet_detected",
    "measurement_valid", "measurement_rejection_reason", "measured_utc",
    "operator_id",
]
SANITIZED_CAPTURE_FIELDS = [
    "operational_release_id", "opaque_specimen_id", "water_temperature_c",
    "specimen_diameter_mm", "specimen_length_mm", "head_difference_m",
    "collection_time_s", "collected_water_mass_g", "calculated_K20_m_s",
    "saturated", "leak_free", "steady_state", "effluent_pet_detected",
    "measurement_valid", "measurement_rejection_reason",
]
LINEARITY_FIELDS = [
    "operational_release_id", "opaque_linearity_id", "gradient_sequence",
    "water_temperature_c", "specimen_diameter_mm", "specimen_length_mm",
    "head_difference_m", "collection_time_s", "collected_water_mass_g",
    "particle_reynolds_number", "measurement_valid",
    "measurement_rejection_reason", "measured_utc", "operator_id",
]
ANALYST_KEY_FIELDS = [
    "operational_release_id", "opaque_specimen_id", "opaque_matched_set_id",
    "analyst_batch_code", "specimen_role",
]
FORBIDDEN_NONRESTRICTED_HEADERS = {
    "condition_id", "source_batch_slot", "reactor_block", "run_order",
    "operator_run_order", "design_run_order", "matched_set_sequence",
    "technical_replicate", "within_set_order", "design_specimen_slot",
    "planned_linearity_sentinel", "target_temperature_c", "treatment",
    "morphology_d50_um", "molecular_endpoint", "numerical_prediction",
}
FORBIDDEN_VALUE_PATTERNS = (
    re.compile(r"\bD33D-", re.IGNORECASE),
    re.compile(r"\bS33A-", re.IGNORECASE),
    re.compile(r"\bT(?:20|120|140|160|180)\b", re.IGNORECASE),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def json_dump(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8", newline="\n",
    )


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def finite_float(value: Any, label: str) -> float:
    number = float(str(value).strip())
    if not math.isfinite(number):
        raise ValueError(f"{label} is not finite")
    return number


def truth(value: Any) -> bool:
    return str(value).strip().casefold() in {"true", "1", "yes", "pass", "passed"}


def falsehood(value: Any) -> bool:
    return str(value).strip().casefold() in {"false", "0", "no", ""}


def density_kg_m3(temp_c: float) -> float:
    return 1000.0 * (
        1.0 - ((temp_c + 288.9414) / (508929.2 * (temp_c + 68.12963)))
        * (temp_c - 3.9863) ** 2
    )


def viscosity_pa_s(temp_c: float) -> float:
    return 2.414e-5 * 10.0 ** (247.8 / (temp_c + 133.15))


def hydraulics(row: dict[str, str]) -> tuple[float, float, float, float]:
    temp_c = finite_float(row["water_temperature_c"], "water_temperature_c")
    diameter_mm = finite_float(row["specimen_diameter_mm"], "specimen_diameter_mm")
    length_mm = finite_float(row["specimen_length_mm"], "specimen_length_mm")
    head_m = finite_float(row["head_difference_m"], "head_difference_m")
    time_s = finite_float(row["collection_time_s"], "collection_time_s")
    mass_g = finite_float(row["collected_water_mass_g"], "collected_water_mass_g")
    if min(diameter_mm, length_mm, head_m, time_s, mass_g) <= 0.0:
        raise ValueError("hydraulic dimensions, head, time and mass must be positive")
    rho = density_kg_m3(temp_c)
    volume_m3 = mass_g / 1000.0 / rho
    area_m2 = math.pi * (diameter_mm / 2000.0) ** 2
    length_m = length_mm / 1000.0
    flow_m3_s = volume_m3 / time_s
    gradient = head_m / length_m
    k_t = flow_m3_s * length_m / (area_m2 * head_m)
    k20 = k_t * (viscosity_pa_s(temp_c) / viscosity_pa_s(20.0)) * (
        density_kg_m3(20.0) / rho
    )
    return flow_m3_s, gradient, k_t, k20


def r_squared(xs: list[float], ys: list[float]) -> float:
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(ys)
    sxx = sum((x - x_mean) ** 2 for x in xs)
    syy = sum((y - y_mean) ** 2 for y in ys)
    if sxx <= 0.0 or syy <= 0.0:
        return 1.0 if syy <= 1e-30 else 0.0
    sxy = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    return max(0.0, min(1.0, (sxy * sxy) / (sxx * syy)))


def require_new_output(output: Path, inputs: list[Path]) -> None:
    output_abs = output.absolute()
    if output_abs.exists():
        raise RuntimeError(f"fail-closed: output already exists: {output_abs}")
    resolved_parent = output_abs.parent.resolve()
    output_resolved = resolved_parent / output_abs.name
    for item in inputs:
        source = item.resolve()
        if output_resolved == source or source in output_resolved.parents:
            raise RuntimeError("fail-closed: output cannot be equal to or nested in an input")


def validate_base_release(release: Path) -> tuple[dict[str, Any], str]:
    if not release.is_dir() or release.is_symlink():
        raise RuntimeError("fail-closed: source release must be a real directory")
    manifest = load_json(release / "release_manifest.json")
    if manifest.get("schema") != RELEASE_SCHEMA or manifest.get("stage") != STAGE:
        raise RuntimeError("fail-closed: wrong release schema or stage")
    if manifest.get("test_only") is not True or manifest.get("no_empirical_data") is not True:
        raise RuntimeError("fail-closed: release is not synthetic-only")
    release_id = str(manifest.get("release_id", ""))
    if not TEST_RELEASE_RE.search(release_id):
        raise RuntimeError("fail-closed: release ID is not conspicuously test-only")
    precommit = load_json(release / "restricted" / "cross_release_commitment.json")
    if (
        precommit.get("schema") != PRECOMMIT_SCHEMA
        or precommit.get("state") != "CUSTODIAN_COMMITTED_PREMEASUREMENT"
        or precommit.get("operational_release_id") != release_id
        or precommit.get("test_only") is not True
        or precommit.get("contains_raw_secret") is not False
        or precommit.get("contains_treatment_key") is not False
        or precommit.get("nonrestricted_contains_condition") is not False
    ):
        raise RuntimeError("fail-closed: invalid premeasurement commitment")
    roles = load_json(release / "restricted" / "roles.json")
    role_ids = [str(roles.get(name, {}).get("role_id", "")) for name in ("operator", "analyst", "custodian")]
    if roles.get("test_only") is not True or any(not item for item in role_ids) or len(set(role_ids)) != 3:
        raise RuntimeError("fail-closed: semantic roles are absent or overlapping")
    return manifest, release_id


def scan_nonrestricted_rows(fields: list[str], rows: list[dict[str, str]], label: str) -> None:
    leaked_headers = set(field.casefold() for field in fields) & FORBIDDEN_NONRESTRICTED_HEADERS
    if leaked_headers:
        raise RuntimeError(f"fail-closed: {label} forbidden headers: {sorted(leaked_headers)}")
    for row in rows:
        for value in row.values():
            for pattern in FORBIDDEN_VALUE_PATTERNS:
                if pattern.search(str(value)):
                    raise RuntimeError(f"fail-closed: {label} contains a public-design/treatment token")


def validate_capture(path: Path, release: Path, release_id: str) -> list[dict[str, str]]:
    fields, rows = read_csv(path)
    if fields != RAW_CAPTURE_FIELDS or len(rows) != 54:
        raise RuntimeError("fail-closed: operator capture schema/count mismatch")
    scan_nonrestricted_rows(fields, rows, "operator capture")
    key_fields, key_rows = read_csv(release / "analyst" / "blinded_analysis_key.csv")
    if key_fields != ANALYST_KEY_FIELDS or len(key_rows) != 54:
        raise RuntimeError("fail-closed: analyst key schema/count mismatch")
    expected = {row["opaque_specimen_id"] for row in key_rows}
    observed = [row["opaque_specimen_id"] for row in rows]
    if len(set(observed)) != 54 or set(observed) != expected:
        raise RuntimeError("fail-closed: completed capture identity set mismatch")
    for row in rows:
        if row["operational_release_id"] != release_id:
            raise RuntimeError("fail-closed: capture release ID mismatch")
        _, _, _, k20 = hydraulics(row)
        supplied = finite_float(row["calculated_K20_m_s"], "calculated_K20_m_s")
        if abs(supplied - k20) / k20 > 0.005:
            raise RuntimeError("fail-closed: supplied K20 cross-check differs by more than 0.5%")
        if not all(truth(row[field]) for field in ("saturated", "leak_free", "steady_state", "measurement_valid")):
            raise RuntimeError("fail-closed: positive synthetic capture contains a failed hydraulic QC gate")
        if not falsehood(row["effluent_pet_detected"]):
            raise RuntimeError("fail-closed: PET detected in effluent")
    return rows


def validate_linearity(path: Path, release: Path, release_id: str) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    fields, rows = read_csv(path)
    if fields != LINEARITY_FIELDS or len(rows) != 18:
        raise RuntimeError("fail-closed: Darcy-linearity capture schema/count mismatch")
    scan_nonrestricted_rows(fields, rows, "Darcy-linearity capture")
    cross_fields, cross_rows = read_csv(release / "restricted" / "linearity_crosswalk.csv")
    if "opaque_linearity_id" not in cross_fields or len(cross_rows) != 6:
        raise RuntimeError("fail-closed: restricted linearity crosswalk mismatch")
    expected = {row["opaque_linearity_id"] for row in cross_rows}
    groups: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        if row["operational_release_id"] != release_id:
            raise RuntimeError("fail-closed: linearity release ID mismatch")
        groups.setdefault(row["opaque_linearity_id"], []).append(row)
    if set(groups) != expected or any(len(group) != 3 for group in groups.values()):
        raise RuntimeError("fail-closed: linearity sentinel identity/count mismatch")
    attestations: list[dict[str, Any]] = []
    for opaque_id in sorted(groups):
        group = sorted(groups[opaque_id], key=lambda row: int(row["gradient_sequence"]))
        if [int(row["gradient_sequence"]) for row in group] != [1, 2, 3]:
            raise RuntimeError("fail-closed: linearity gradient sequence mismatch")
        flows: list[float] = []
        gradients: list[float] = []
        k20_values: list[float] = []
        reynolds: list[float] = []
        for row in group:
            if not truth(row["measurement_valid"]):
                raise RuntimeError("fail-closed: invalid linearity determination")
            flow, gradient, _, k20 = hydraulics(row)
            flows.append(flow)
            gradients.append(gradient)
            k20_values.append(k20)
            reynolds.append(finite_float(row["particle_reynolds_number"], "particle_reynolds_number"))
        r2 = r_squared(gradients, flows)
        cv = statistics.stdev(k20_values) / statistics.fmean(k20_values)
        max_re = max(reynolds)
        passed = r2 >= 0.99 and cv <= 0.05 and max_re <= 1.0
        attestations.append({
            "opaque_linearity_id": opaque_id,
            "determination_n": 3,
            "discharge_gradient_r_squared": r2,
            "K20_coefficient_of_variation": cv,
            "maximum_particle_reynolds_number": max_re,
            "passed": passed,
        })
    if not all(row["passed"] for row in attestations):
        raise RuntimeError("fail-closed: one or more Darcy-linearity gates failed")
    return rows, attestations


def atomic_copy(source: Path, output: Path, add_files: Any) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=str(output.parent)))
    work = temporary / "release"
    try:
        shutil.copytree(source, work, symlinks=False)
        add_files(work)
        work.replace(output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def prepare(source: Path, capture: Path, linearity: Path, output: Path) -> None:
    manifest, release_id = validate_base_release(source)
    if any((source / "operator" / name).exists() for name in ("operator_capture.csv", "darcy_linearity_capture.csv")):
        raise RuntimeError("fail-closed: source release already contains completed captures")
    capture_rows = validate_capture(capture, source, release_id)
    _, attestations = validate_linearity(linearity, source, release_id)
    evaluator = ROOT / "stage33_staging" / "evaluate_stage33do_matched_hydraulics_v1.py"
    if not evaluator.is_file():
        raise RuntimeError("fail-closed: evaluator source is absent")
    require_new_output(output, [source, capture, linearity])

    def add(work: Path) -> None:
        shutil.copy2(capture, work / "operator" / "operator_capture.csv")
        shutil.copy2(linearity, work / "operator" / "darcy_linearity_capture.csv")
        sanitized = [{field: row[field] for field in SANITIZED_CAPTURE_FIELDS} for row in capture_rows]
        write_csv(work / "analyst" / "sanitized_hydraulic_capture.csv", SANITIZED_CAPTURE_FIELDS, sanitized)
        attestation = {
            "schema": ATTESTATION_SCHEMA,
            "stage": STAGE,
            "operational_release_id": release_id,
            "created_utc": utc_now(),
            "status": "PASSED_OPAQUE_LINEARITY_GATE_PRE_REVEAL",
            "passed": True,
            "test_only": True,
            "no_empirical_data": True,
            "darcy_linearity_capture_sha256": sha256(work / "operator" / "darcy_linearity_capture.csv"),
            "evaluator_sha256": sha256(evaluator),
            "sentinels": attestations,
            "contains_specimen_mapping": False,
            "contains_condition": False,
        }
        json_dump(work / "restricted" / "linearity_gate_attestation.json", attestation)
        state = {
            "schema": "pet.stage33do-prepared-release-state.v1",
            "stage": STAGE,
            "operational_release_id": release_id,
            "created_utc": utc_now(),
            "state": "CAPTURE_SANITIZED_AND_LINEARITY_ATTESTED_PRE_REVEAL",
            "passed": True,
            "test_only": True,
            "source_release_manifest_sha256": sha256(source / "release_manifest.json"),
            "raw_operator_capture_sha256": sha256(work / "operator" / "operator_capture.csv"),
            "raw_linearity_capture_sha256": sha256(work / "operator" / "darcy_linearity_capture.csv"),
            "sanitized_hydraulic_capture_sha256": sha256(work / "analyst" / "sanitized_hydraulic_capture.csv"),
            "linearity_gate_attestation_sha256": sha256(work / "restricted" / "linearity_gate_attestation.json"),
            "authority": manifest.get("authority"),
        }
        json_dump(work / "prepared_release_state.json", state)

    atomic_copy(source, output, add)


def ensure_pre_reveal_safe(pre_dir: Path, release_id: str) -> dict[str, Any]:
    required = [
        "specimen_results.csv", "batch_endpoints.csv", "exclusion_ledger.csv",
        "pre_reveal_evaluation.json", "completion.json",
    ]
    if not pre_dir.is_dir() or any(not (pre_dir / name).is_file() for name in required):
        raise RuntimeError("fail-closed: incomplete pre-reveal evaluation")
    evaluation = load_json(pre_dir / "pre_reveal_evaluation.json")
    completion = load_json(pre_dir / "completion.json")
    if (
        evaluation.get("schema") != PRE_EVAL_SCHEMA
        or evaluation.get("operational_release_id") != release_id
        or evaluation.get("passed") is not True
        or evaluation.get("test_only") is not True
        or completion.get("passed") is not True
    ):
        raise RuntimeError("fail-closed: pre-reveal evaluation state did not pass")
    batch_fields, batch_rows = read_csv(pre_dir / "batch_endpoints.csv")
    if len(batch_rows) != 15 or "analyst_batch_code" not in batch_fields:
        raise RuntimeError("fail-closed: pre-reveal batch endpoint count/schema mismatch")
    forbidden_headers = {"condition_id", "reactor_block", "source_batch_slot", "target_temperature_c"}
    for name in required:
        path = pre_dir / name
        if path.suffix == ".csv":
            fields, rows = read_csv(path)
            if set(field.casefold() for field in fields) & forbidden_headers:
                raise RuntimeError("fail-closed: treatment information appears in pre-reveal CSV")
            scan_nonrestricted_rows(fields, rows, f"pre-reveal {name}")
        else:
            text = path.read_text(encoding="utf-8-sig")
            if any(pattern.search(text) for pattern in FORBIDDEN_VALUE_PATTERNS):
                raise RuntimeError("fail-closed: treatment/design token appears in pre-reveal JSON")
    return evaluation


def freeze(source: Path, pre_dir: Path, output: Path) -> None:
    manifest, release_id = validate_base_release(source)
    prepared = load_json(source / "prepared_release_state.json")
    if prepared.get("state") != "CAPTURE_SANITIZED_AND_LINEARITY_ATTESTED_PRE_REVEAL":
        raise RuntimeError("fail-closed: source is not a prepared pre-reveal release")
    for name in ("operator_capture.csv", "darcy_linearity_capture.csv"):
        if not (source / "operator" / name).is_file():
            raise RuntimeError("fail-closed: prepared release lacks completed capture")
    pre_eval = ensure_pre_reveal_safe(pre_dir, release_id)
    evaluator = ROOT / "stage33_staging" / "evaluate_stage33do_matched_hydraulics_v1.py"
    sealer = Path(__file__).resolve()
    require_new_output(output, [source, pre_dir])

    def add(work: Path) -> None:
        restricted = work / "restricted"
        if any((restricted / name).exists() for name in ("primary_freeze_commitment.json", "reveal_declaration.json")):
            raise RuntimeError("fail-closed: primary freeze/reveal already exists")
        bindings = {
            "cross_release_commitment_sha256": sha256(restricted / "cross_release_commitment.json"),
            "sanitized_hydraulic_capture_sha256": sha256(work / "analyst" / "sanitized_hydraulic_capture.csv"),
            "raw_operator_capture_sha256": sha256(work / "operator" / "operator_capture.csv"),
            "raw_linearity_capture_sha256": sha256(work / "operator" / "darcy_linearity_capture.csv"),
            "linearity_gate_attestation_sha256": sha256(restricted / "linearity_gate_attestation.json"),
            "blinded_analysis_key_sha256": sha256(work / "analyst" / "blinded_analysis_key.csv"),
            "preparation_records_sha256": sha256(restricted / "preparation_records.csv"),
            "synthetic_morphology_summary_sha256": sha256(work / "analyst" / "synthetic_morphology_summary.csv"),
            "pre_reveal_specimen_results_sha256": sha256(pre_dir / "specimen_results.csv"),
            "pre_reveal_batch_endpoints_sha256": sha256(pre_dir / "batch_endpoints.csv"),
            "pre_reveal_exclusion_ledger_sha256": sha256(pre_dir / "exclusion_ledger.csv"),
            "pre_reveal_evaluation_sha256": sha256(pre_dir / "pre_reveal_evaluation.json"),
            "evaluator_sha256": sha256(evaluator),
            "sealer_sha256": sha256(sealer),
            "release_manifest_sha256": sha256(work / "release_manifest.json"),
        }
        commitment = {
            "schema": FREEZE_SCHEMA,
            "stage": STAGE,
            "operational_release_id": release_id,
            "created_utc": utc_now(),
            "state": "PRIMARY_ENDPOINTS_FROZEN_REVEAL_AUTHORIZED",
            "status": "PRIMARY_ENDPOINTS_FROZEN_REVEAL_AUTHORIZED",
            "passed": True,
            "test_only": True,
            "no_empirical_data": True,
            "pre_reveal_phase": pre_eval.get("phase"),
            **bindings,
            "contains_condition_summary": False,
            "authority": manifest.get("authority"),
        }
        json_dump(restricted / "primary_freeze_commitment.json", commitment)
        declaration = {
            "schema": REVEAL_SCHEMA,
            "stage": STAGE,
            "operational_release_id": release_id,
            "created_utc": utc_now(),
            "state": "REVEAL_DECLARED_AFTER_PRIMARY_FREEZE",
            "status": "REVEAL_DECLARED_AFTER_PRIMARY_FREEZE",
            "passed": True,
            "test_only": True,
            "primary_freeze_commitment_sha256": sha256(restricted / "primary_freeze_commitment.json"),
            "reveal_key_sha256": sha256(restricted / "reveal_key.csv"),
            "pre_reveal_batch_endpoints_sha256": bindings["pre_reveal_batch_endpoints_sha256"],
            "condition_summary_existed_before_declaration": False,
        }
        json_dump(restricted / "reveal_declaration.json", declaration)
        final_state = {
            "schema": "pet.stage33do-frozen-release-state.v1",
            "stage": STAGE,
            "operational_release_id": release_id,
            "created_utc": utc_now(),
            "state": "PRIMARY_FROZEN_AND_REVEAL_DECLARED_TEST_ONLY",
            "passed": True,
            "test_only": True,
            "source_prepared_release_sha256": sha256(source / "prepared_release_state.json"),
            "primary_freeze_commitment_sha256": sha256(restricted / "primary_freeze_commitment.json"),
            "reveal_declaration_sha256": sha256(restricted / "reveal_declaration.json"),
        }
        json_dump(work / "frozen_release_state.json", final_state)

    atomic_copy(source, output, add)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("prepare", "freeze"), required=True)
    parser.add_argument("--source-release", type=Path, required=True)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--linearity", type=Path)
    parser.add_argument("--pre-reveal-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.phase == "prepare":
            if args.capture is None or args.linearity is None or args.pre_reveal_dir is not None:
                raise RuntimeError("prepare requires --capture and --linearity only")
            prepare(args.source_release.resolve(), args.capture.resolve(), args.linearity.resolve(), args.output_dir.absolute())
        else:
            if args.pre_reveal_dir is None or args.capture is not None or args.linearity is not None:
                raise RuntimeError("freeze requires --pre-reveal-dir only")
            freeze(args.source_release.resolve(), args.pre_reveal_dir.resolve(), args.output_dir.absolute())
    except Exception as exc:
        print(f"FAIL-CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "stage": STAGE, "phase": args.phase, "passed": True,
        "output_dir": str(args.output_dir.absolute()), "test_only": True,
        "no_empirical_data": True,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
