#!/usr/bin/env python3
"""End-to-end synthetic qualification of the Stage33D-O blinded workflow.

The verifier manufactures deterministic TEST_ONLY constant-head observations,
walks them through the three immutable release states, and exercises hostile
fixtures.  It never ingests a real key or datum and never launches laboratory,
DEM, LBM, or coupled-physics work.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "stage33_staging"
STAGE = "Stage33D-O"
SCHEMA = "pet.stage33do-operational-workflow-synthetic-verification.v1"
STATUS = "passed_synthetic_workflow_qualification"
RELEASE_ID = "STAGE33DO-TEST_ONLY-SYNTHETIC-QUALIFICATION-01"
DESIGN_DEFAULT = (
    ROOT / "stage33_designs" / "stage33d_matched_pet_lbs_physical_validation_20260901"
    / "release_01"
)
DESIGN_AUDIT_DEFAULT = (
    ROOT / "stage33_evaluations" / "stage33d_matched_pet_lbs_physical_validation_20260901"
    / "design_audit_01" / "design_audit.json"
)
CONTRACT = STAGING / "STAGE33DO_OPERATIONAL_WORKFLOW_SYNTHETIC_QUALIFICATION_CONTRACT_V1.md"
BUILDER = STAGING / "build_stage33do_synthetic_blinded_release_v1.py"
EVALUATOR = STAGING / "evaluate_stage33do_matched_hydraulics_v1.py"
SEALER = STAGING / "seal_stage33do_primary_freeze_v1.py"
AUDITOR = STAGING / "audit_stage33do_operational_release_qualification_v1.py"

RAW_CAPTURE_FIELDS = [
    "operational_release_id", "opaque_specimen_id", "water_temperature_c",
    "specimen_diameter_mm", "specimen_length_mm", "head_difference_m",
    "collection_time_s", "collected_water_mass_g", "calculated_K20_m_s",
    "saturated", "leak_free", "steady_state", "effluent_pet_detected",
    "measurement_valid", "measurement_rejection_reason", "measured_utc",
    "operator_id",
]
LINEARITY_FIELDS = [
    "operational_release_id", "opaque_linearity_id", "gradient_sequence",
    "water_temperature_c", "specimen_diameter_mm", "specimen_length_mm",
    "head_difference_m", "collection_time_s", "collected_water_mass_g",
    "particle_reynolds_number", "measurement_valid",
    "measurement_rejection_reason", "measured_utc", "operator_id",
]
PREPARATION_FIELDS = [
    "design_specimen_slot", "balance_calibration_id", "sand_lot_id",
    "dry_sand_mass_g", "dry_pet_mass_g", "achieved_pet_dry_mass_percent",
    "pet_density_g_cm3", "achieved_pet_solid_volume_fraction",
    "mixing_protocol_id", "packing_protocol_id", "initial_total_solid_void_ratio",
    "pre_measurement_eligible", "pre_measurement_rejection_reason",
    "preparation_utc", "custodian_id",
]
MORPHOLOGY_FIELDS = ["source_batch_slot", "log_d50_max_feret", "measurement_se"]
AUTHORITY = {
    "laboratory_execution": False,
    "numerical_execution": False,
    "real_key_ingest": False,
    "empirical_analysis": False,
    "physical_validation_claim": False,
    "temperature_effect_claim": False,
    "molecular_degradation_claim": False,
    "length_as_degradation_proxy_claim": False,
    "absolute_permeability_validation_claim": False,
    "migration_or_clogging_claim": False,
    "deformation_or_coupling_claim": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def binding(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": sha256(path)}


def internal_binding(path: Path, verification_root: Path) -> dict[str, str]:
    """Bind an artifact by relocation-safe path within the verification tree."""
    return {
        "path": path.resolve().relative_to(verification_root.resolve()).as_posix(),
        "sha256": sha256(path),
    }


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8", newline="\n",
    )


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def run(command: list[str], expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode != expected:
        raise RuntimeError(
            f"command returned {result.returncode}, expected {expected}: {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def density_kg_m3(temp_c: float) -> float:
    return 1000.0 * (
        1.0 - ((temp_c + 288.9414) / (508929.2 * (temp_c + 68.12963)))
        * (temp_c - 3.9863) ** 2
    )


def mass_for_k20(k20: float, temp_c: float, diameter_mm: float, length_mm: float,
                 head_m: float, time_s: float) -> float:
    mu = 2.414e-5 * 10.0 ** (247.8 / (temp_c + 133.15))
    mu20 = 2.414e-5 * 10.0 ** (247.8 / (20.0 + 133.15))
    rho = density_kg_m3(temp_c)
    rho20 = density_kg_m3(20.0)
    k_t = k20 / ((mu / mu20) * (rho20 / rho))
    area = math.pi * (diameter_mm / 2000.0) ** 2
    q = k_t * area * head_m / (length_mm / 1000.0)
    return q * time_s * rho * 1000.0


def make_fixture_inputs(work: Path, design_dir: Path) -> dict[str, Path]:
    fixture = work / "fixtures"
    fixture.mkdir(parents=True)
    secret = b"TEST_ONLY_STAGE33DO_20260901_6f62b1834df94b30"
    secret_path = fixture / "test_only_secret.bin"
    secret_path.write_bytes(secret)
    roles_path = fixture / "roles.json"
    roles = {
        "schema": "pet.stage33do-semantic-roles.v1",
        "test_only": True,
        "operator": {"role_id": "TEST-ONLY-HYDRAULIC-OPERATOR"},
        "analyst": {"role_id": "TEST-ONLY-BLINDED-ANALYST"},
        "custodian": {"role_id": "TEST-ONLY-KEY-CUSTODIAN"},
    }
    json_dump(roles_path, roles)
    _, design_rows = read_csv(design_dir / "custodian_design_matrix.csv")
    target = float(load_json(design_dir / "resolved_design.json")["design"]["target_pet_dry_mass_percent"])
    prep_rows: list[dict[str, Any]] = []
    for row in design_rows:
        pet = row["specimen_role"] == "pet_mixture"
        sand_mass = 1000.0
        pet_mass = sand_mass * target / 100.0 if pet else 0.0
        pet_volume = pet_mass / 1.38 if pet else 0.0
        sand_volume = sand_mass / 2.65
        prep_rows.append({
            "design_specimen_slot": row["design_specimen_slot"],
            "balance_calibration_id": "TEST-BALANCE-CAL-01",
            "sand_lot_id": "TEST-LBS-LOT-01",
            "dry_sand_mass_g": f"{sand_mass:.12g}",
            "dry_pet_mass_g": f"{pet_mass:.17g}",
            "achieved_pet_dry_mass_percent": f"{target if pet else 0.0:.17g}",
            "pet_density_g_cm3": "1.38" if pet else "0",
            "achieved_pet_solid_volume_fraction": f"{pet_volume / (sand_volume + pet_volume):.17g}" if pet else "0",
            "mixing_protocol_id": "TEST-MIX-V1",
            "packing_protocol_id": "TEST-PACK-V1",
            "initial_total_solid_void_ratio": "0.744",
            "pre_measurement_eligible": "true",
            "pre_measurement_rejection_reason": "",
            "preparation_utc": "2026-09-01T08:00:00Z",
            "custodian_id": roles["custodian"]["role_id"],
        })
    preparation_path = fixture / "preparation.csv"
    write_csv(preparation_path, PREPARATION_FIELDS, prep_rows)

    condition_log_d50 = {"T20": math.log(400.0), "T120": math.log(330.0),
                         "T140": math.log(260.0), "T160": math.log(190.0),
                         "T180": math.log(125.0)}
    source_to_condition = {
        row["source_batch_slot"]: row["condition_id"]
        for row in design_rows if row["specimen_role"] == "pet_mixture"
    }
    morph_rows = []
    for index, source in enumerate(sorted(source_to_condition)):
        morph_rows.append({
            "source_batch_slot": source,
            "log_d50_max_feret": f"{condition_log_d50[source_to_condition[source]] + (index % 3 - 1) * 0.01:.17g}",
            "measurement_se": "0.025",
        })
    morphology_path = fixture / "morphology.csv"
    write_csv(morphology_path, MORPHOLOGY_FIELDS, morph_rows)
    return {
        "secret": secret_path, "roles": roles_path, "preparation": preparation_path,
        "morphology": morphology_path,
    }


def builder_command(design_dir: Path, design_audit: Path, inputs: dict[str, Path],
                    output: Path, roles: Path | None = None, input_mode: str = "synthetic_qualification") -> list[str]:
    return [
        sys.executable, str(BUILDER), "--design-dir", str(design_dir),
        "--design-audit", str(design_audit), "--contract", str(CONTRACT),
        "--secret-file", str(inputs["secret"]), "--roles", str(roles or inputs["roles"]),
        "--preparation", str(inputs["preparation"]), "--morphology", str(inputs["morphology"]),
        "--output-dir", str(output), "--release-id", RELEASE_ID,
        "--input-mode", input_mode,
    ]


def make_completed_captures(initial: Path, output: Path) -> tuple[Path, Path]:
    _, key_rows = read_csv(initial / "analyst" / "blinded_analysis_key.csv")
    _, reveal_rows = read_csv(initial / "restricted" / "reveal_key.csv")
    reveal = {row["analyst_batch_code"]: row for row in reveal_rows}
    ratios = {"T20": 0.970, "T120": 0.945, "T140": 0.915, "T160": 0.880, "T180": 0.835}
    set_ids = sorted({row["opaque_matched_set_id"] for row in key_rows})
    set_factor = {set_id: 1.0 + (index - 4) * 0.0015 for index, set_id in enumerate(set_ids)}
    capture_rows: list[dict[str, Any]] = []
    for row in key_rows:
        clean_k = 0.008 * set_factor[row["opaque_matched_set_id"]]
        if row["specimen_role"] == "clean_lbs_control":
            k20 = clean_k
        else:
            condition = reveal[row["analyst_batch_code"]]["condition_id"]
            batch_jitter = ((int(hashlib.sha256(row["analyst_batch_code"].encode()).hexdigest()[:2], 16) % 7) - 3) * 0.0006
            k20 = clean_k * (ratios[condition] + batch_jitter)
        temp, diameter, length, head, seconds = 20.0, 50.0, 100.0, 0.05, 20.0
        mass = mass_for_k20(k20, temp, diameter, length, head, seconds)
        capture_rows.append({
            "operational_release_id": RELEASE_ID,
            "opaque_specimen_id": row["opaque_specimen_id"],
            "water_temperature_c": "20.0",
            "specimen_diameter_mm": "50.0",
            "specimen_length_mm": "100.0",
            "head_difference_m": "0.05",
            "collection_time_s": "20.0",
            "collected_water_mass_g": f"{mass:.17g}",
            "calculated_K20_m_s": f"{k20:.17g}",
            "saturated": "true", "leak_free": "true", "steady_state": "true",
            "effluent_pet_detected": "false", "measurement_valid": "true",
            "measurement_rejection_reason": "", "measured_utc": "2026-09-01T09:00:00Z",
            "operator_id": "TEST-ONLY-HYDRAULIC-OPERATOR",
        })
    capture_path = output / "operator_capture.csv"
    write_csv(capture_path, RAW_CAPTURE_FIELDS, capture_rows)

    _, linearity_cross = read_csv(initial / "restricted" / "linearity_crosswalk.csv")
    linearity_rows: list[dict[str, Any]] = []
    for opaque_id in sorted(row["opaque_linearity_id"] for row in linearity_cross):
        for sequence, head in enumerate((0.002, 0.004, 0.006), 1):
            k20, temp, diameter, length, seconds = 0.008, 20.0, 50.0, 100.0, 20.0
            mass = mass_for_k20(k20, temp, diameter, length, head, seconds)
            linearity_rows.append({
                "operational_release_id": RELEASE_ID, "opaque_linearity_id": opaque_id,
                "gradient_sequence": sequence, "water_temperature_c": "20.0",
                "specimen_diameter_mm": "50.0", "specimen_length_mm": "100.0",
                "head_difference_m": f"{head:.17g}", "collection_time_s": "20.0",
                "collected_water_mass_g": f"{mass:.17g}", "particle_reynolds_number": "0.2",
                "measurement_valid": "true", "measurement_rejection_reason": "",
                "measured_utc": "2026-09-01T09:30:00Z", "operator_id": "TEST-ONLY-HYDRAULIC-OPERATOR",
            })
    linearity_path = output / "darcy_linearity_capture.csv"
    write_csv(linearity_path, LINEARITY_FIELDS, linearity_rows)
    return capture_path, linearity_path


def evaluator_pre_command(release: Path, output: Path) -> list[str]:
    return [
        sys.executable, str(EVALUATOR), "--phase", "pre_reveal", "--release-dir", str(release),
        "--capture", str(release / "analyst" / "sanitized_hydraulic_capture.csv"),
        "--linearity", str(release / "operator" / "darcy_linearity_capture.csv"),
        "--output-dir", str(output),
    ]


def evaluator_post_command(release: Path, pre: Path, output: Path) -> list[str]:
    return [
        sys.executable, str(EVALUATOR), "--phase", "post_reveal", "--release-dir", str(release),
        "--pre-reveal-dir", str(pre), "--output-dir", str(output),
    ]


def expected_rejection(name: str, command: list[str], root: Path) -> dict[str, Any]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    record = {
        "challenge": name, "passed": result.returncode != 0,
        "expected_rejection": True, "rejected": result.returncode != 0,
        "exit_code": result.returncode,
        "stdout_tail": result.stdout[-2000:], "stderr_tail": result.stderr[-2000:],
    }
    json_dump(root / name / "challenge.json", record)
    if result.returncode == 0:
        raise RuntimeError(f"hostile challenge unexpectedly passed: {name}")
    return record


def copy_and_mutate_csv(source: Path, target: Path, mutate: Any) -> None:
    fields, rows = read_csv(source)
    mutate(fields, rows)
    write_csv(target, fields, rows)


def run_negative_challenges(work: Path, design_dir: Path, design_audit: Path,
                            inputs: dict[str, Path], initial: Path, prepared: Path,
                            final_release: Path, pre_eval: Path, capture: Path,
                            linearity: Path) -> dict[str, Any]:
    challenges_root = work / "negative_challenges"
    challenges_root.mkdir()
    records: dict[str, Any] = {}

    def sealer_prepare(challenge: str, capture_path: Path, linearity_path: Path) -> list[str]:
        return [sys.executable, str(SEALER), "--phase", "prepare", "--source-release", str(initial),
                "--capture", str(capture_path), "--linearity", str(linearity_path),
                "--output-dir", str(challenges_root / challenge / "prepared_release")]

    duplicate_dir = challenges_root / "duplicate_specimen"; duplicate_dir.mkdir()
    duplicate_capture = duplicate_dir / "capture.csv"
    copy_and_mutate_csv(capture, duplicate_capture, lambda f, r: r[1].__setitem__("opaque_specimen_id", r[0]["opaque_specimen_id"]))
    records["duplicate_specimen"] = expected_rejection(
        "duplicate_specimen", sealer_prepare("duplicate_specimen", duplicate_capture, linearity), challenges_root)

    mismatch_dir = challenges_root / "capture_binding"; mismatch_dir.mkdir()
    mismatch_capture = mismatch_dir / "capture.csv"
    copy_and_mutate_csv(capture, mismatch_capture, lambda f, r: r[0].__setitem__("opaque_specimen_id", "OPSP-HOSTILE-UNKNOWN"))
    records["capture_binding"] = expected_rejection(
        "capture_binding", sealer_prepare("capture_binding", mismatch_capture, linearity), challenges_root)

    leak_dir = challenges_root / "operator_leakage"; leak_dir.mkdir()
    leak_capture = leak_dir / "capture.csv"
    fields, rows = read_csv(capture); fields.append("condition_id")
    for row in rows: row["condition_id"] = "T180"
    write_csv(leak_capture, fields, rows)
    records["operator_leakage"] = expected_rejection(
        "operator_leakage", sealer_prepare("operator_leakage", leak_capture, linearity), challenges_root)

    reveal_dir = challenges_root / "reveal_key_mutation"; reveal_dir.mkdir()
    reveal_release = reveal_dir / "release"; shutil.copytree(final_release, reveal_release)
    reveal_path = reveal_release / "restricted" / "reveal_key.csv"
    copy_and_mutate_csv(reveal_path, reveal_path, lambda f, r: r[0].__setitem__("condition_id", "T180" if r[0]["condition_id"] != "T180" else "T20"))
    records["reveal_key_mutation"] = expected_rejection(
        "reveal_key_mutation", evaluator_post_command(reveal_release, pre_eval, reveal_dir / "evaluation"), challenges_root)

    commitment_dir = challenges_root / "commitment_mutation"; commitment_dir.mkdir()
    commitment_release = commitment_dir / "prepared_release"; shutil.copytree(prepared, commitment_release)
    commitment_path = commitment_release / "restricted" / "cross_release_commitment.json"
    commitment = load_json(commitment_path); commitment["contains_treatment_key"] = True; json_dump(commitment_path, commitment)
    records["commitment_mutation"] = expected_rejection(
        "commitment_mutation", evaluator_pre_command(commitment_release, commitment_dir / "evaluation"), challenges_root)

    void_dir = challenges_root / "void_ratio"; void_dir.mkdir()
    void_release = void_dir / "prepared_release"; shutil.copytree(prepared, void_release)
    prep_path = void_release / "restricted" / "preparation_records.csv"
    copy_and_mutate_csv(prep_path, prep_path, lambda f, r: r[0].__setitem__("initial_total_solid_void_ratio", "0.800"))
    records["void_ratio"] = expected_rejection(
        "void_ratio", evaluator_pre_command(void_release, void_dir / "evaluation"), challenges_root)

    linearity_dir = challenges_root / "darcy_linearity"; linearity_dir.mkdir()
    bad_linearity = linearity_dir / "linearity.csv"
    copy_and_mutate_csv(linearity, bad_linearity, lambda f, r: r[1].__setitem__("collected_water_mass_g", str(float(r[1]["collected_water_mass_g"]) * 0.25)))
    records["darcy_linearity"] = expected_rejection(
        "darcy_linearity", sealer_prepare("darcy_linearity", capture, bad_linearity), challenges_root)

    overlap_dir = challenges_root / "role_overlap"; overlap_dir.mkdir()
    overlap_roles = load_json(inputs["roles"]); overlap_roles["analyst"]["role_id"] = overlap_roles["operator"]["role_id"]
    overlap_roles_path = overlap_dir / "roles.json"; json_dump(overlap_roles_path, overlap_roles)
    records["role_overlap"] = expected_rejection(
        "role_overlap", builder_command(design_dir, design_audit, inputs, overlap_dir / "release", overlap_roles_path), challenges_root)

    non_test_dir = challenges_root / "non_test_mode"; non_test_dir.mkdir()
    records["non_test_mode"] = expected_rejection(
        "non_test_mode", builder_command(design_dir, design_audit, inputs, non_test_dir / "release", input_mode="empirical_operational"), challenges_root)

    secret_dir = challenges_root / "secret_leakage"; secret_dir.mkdir()
    secret_text = inputs["secret"].read_text(encoding="utf-8")
    secret_roles = load_json(inputs["roles"]); secret_roles["operator"]["role_id"] = secret_text
    secret_roles_path = secret_dir / "roles.json"; json_dump(secret_roles_path, secret_roles)
    records["secret_leakage"] = expected_rejection(
        "secret_leakage", builder_command(design_dir, design_audit, inputs, secret_dir / "release", secret_roles_path), challenges_root)

    _, design_rows = read_csv(design_dir / "custodian_design_matrix.csv")
    protected = {
        value for row in design_rows for key, value in row.items()
        if key in {"design_specimen_slot", "source_batch_slot", "condition_id"} and value
    }
    public_values: set[str] = set()
    for domain in (final_release / "operator", final_release / "analyst"):
        for path in domain.rglob("*"):
            if not path.is_file(): continue
            if path.suffix.lower() == ".csv":
                _, rows = read_csv(path)
                public_values |= {str(value) for row in rows for value in row.values() if value}
            elif path.suffix.lower() == ".json":
                public_values |= set(re.findall(r"[A-Za-z0-9_.:-]+", path.read_text(encoding="utf-8-sig")))
    leaked = sorted(protected & public_values)
    join_record = {"challenge": "public_design_joinability", "passed": not leaked,
                   "expected_rejection": True, "rejected": not leaked, "exit_code": 2,
                   "recovered_treatment_token_n": len(leaked), "recovered_tokens": leaked}
    json_dump(challenges_root / "public_design_joinability" / "challenge.json", join_record)
    if leaked: raise RuntimeError(f"public design is joinable through tokens: {leaked}")
    records["public_design_joinability"] = join_record

    analyst_text = "\n".join(path.read_text(encoding="utf-8-sig") for path in (final_release / "analyst").rglob("*") if path.is_file())
    _, cross_rows = read_csv(final_release / "restricted" / "linearity_crosswalk.csv")
    sentinel_ids = {row["opaque_linearity_id"] for row in cross_rows}
    sentinel_leaks = sorted(sentinel_ids & set(re.findall(r"[A-Za-z0-9_.:-]+", analyst_text)))
    sentinel_record = {"challenge": "sentinel_mapping_leakage", "passed": not sentinel_leaks,
                       "expected_rejection": True, "rejected": not sentinel_leaks, "exit_code": 2,
                       "leaked_specimen_n": len(sentinel_leaks)}
    json_dump(challenges_root / "sentinel_mapping_leakage" / "challenge.json", sentinel_record)
    if sentinel_leaks: raise RuntimeError("linearity sentinel specimen mapping leaked to analyst")
    records["sentinel_mapping_leakage"] = sentinel_record
    return records


def verify(design_dir: Path, design_audit: Path, work: Path) -> dict[str, Any]:
    required_sources = [CONTRACT, BUILDER, EVALUATOR, SEALER, AUDITOR, Path(__file__).resolve()]
    if any(not path.is_file() for path in required_sources):
        raise RuntimeError("one or more production sources are missing")
    design = load_json(design_dir / "resolved_design.json")
    design_audit_json = load_json(design_audit)
    if design.get("passed") is not True or design_audit_json.get("passed", design_audit_json.get("pass")) is not True:
        raise RuntimeError("Stage33D parent design/audit did not pass")
    if any(item.get("populated") is not False for item in design["future_required_inputs"].values()):
        raise RuntimeError("synthetic qualification requires every empirical future input to remain empty")
    inputs = make_fixture_inputs(work, design_dir)
    success = work / "successful_release"; success.mkdir()
    initial = success / "initial_release"
    run(builder_command(design_dir, design_audit, inputs, initial))
    completed = success / "completed"; completed.mkdir()
    capture, linearity = make_completed_captures(initial, completed)
    prepared = success / "prepared_release"
    run([sys.executable, str(SEALER), "--phase", "prepare", "--source-release", str(initial),
         "--capture", str(capture), "--linearity", str(linearity), "--output-dir", str(prepared)])
    pre_eval = success / "pre_reveal_evaluation"
    run(evaluator_pre_command(prepared, pre_eval))
    final_release = success / "release"
    run([sys.executable, str(SEALER), "--phase", "freeze", "--source-release", str(prepared),
         "--pre-reveal-dir", str(pre_eval), "--output-dir", str(final_release)])
    evaluation = success / "evaluation"
    run(evaluator_post_command(final_release, pre_eval, evaluation))

    _, specimen_rows = read_csv(evaluation / "specimen_results.csv")
    _, batch_rows = read_csv(evaluation / "batch_endpoints.csv")
    _, condition_rows = read_csv(evaluation / "condition_summary.csv")
    if len(specimen_rows) != 54 or len(batch_rows) != 15 or len(condition_rows) != 5:
        raise RuntimeError("positive evaluation count closure failed")
    role_counts = {role: sum(row["specimen_role"] == role for row in specimen_rows)
                   for role in ("pet_mixture", "clean_lbs_control")}
    if role_counts != {"pet_mixture": 45, "clean_lbs_control": 9}:
        raise RuntimeError("positive specimen role counts failed")
    challenges = run_negative_challenges(
        work, design_dir, design_audit, inputs, initial, prepared, final_release,
        pre_eval, capture, linearity,
    )
    production = {
        "stage33do_contract": binding(CONTRACT),
        "stage33do_release_builder": binding(BUILDER),
        "stage33do_evaluator": binding(EVALUATOR),
        "stage33do_primary_freeze_sealer": binding(SEALER),
        "stage33do_verifier": binding(Path(__file__).resolve()),
        "stage33do_release_auditor": binding(AUDITOR),
    }
    hash_bindings = {
        "test_only_secret_fixture": internal_binding(inputs["secret"], work),
        "initial_release_manifest": internal_binding(initial / "release_manifest.json", work),
        "prepared_release_state": internal_binding(prepared / "prepared_release_state.json", work),
        "final_release_manifest": internal_binding(final_release / "release_manifest.json", work),
        "primary_freeze_commitment": internal_binding(final_release / "restricted" / "primary_freeze_commitment.json", work),
        "reveal_declaration": internal_binding(final_release / "restricted" / "reveal_declaration.json", work),
        "pre_reveal_evaluation": internal_binding(pre_eval / "pre_reveal_evaluation.json", work),
        "final_evaluation": internal_binding(evaluation / "evaluation.json", work),
    }
    return {
        "schema": SCHEMA, "stage": STAGE,
        "verification_id": "STAGE33DO-OPERATIONAL-WORKFLOW-SYNTHETIC-QUALIFICATION-01",
        "created_utc": utc_now(), "status": STATUS, "pass": True,
        "test_only": True, "no_empirical_data": True, "no_real_key": True,
        "design": {
            "stage33d_design": binding(design_dir / "resolved_design.json"),
            "stage33d_design_audit": binding(design_audit),
        },
        "production_scripts": production, "hash_bindings": hash_bindings,
        "release": {
            "release_manifest": internal_binding(final_release / "release_manifest.json", work),
            "primary_freeze_commitment": internal_binding(final_release / "restricted" / "primary_freeze_commitment.json", work),
            "reveal_declaration": internal_binding(final_release / "restricted" / "reveal_declaration.json", work),
        },
        "positive_release": {
            "passed": True, "release_dir": final_release.relative_to(work).as_posix(),
            "pre_reveal_evaluation_dir": pre_eval.relative_to(work).as_posix(),
            "evaluation_dir": evaluation.relative_to(work).as_posix(),
            "specimen_n": 54, "pet_n": 45, "clean_n": 9, "batch_n": 15,
            "operator_package_blinded": True, "test_only_key_isolated": True,
            "capture_hash_bound": True, "linearity_hash_bound": True,
            "K20_exact_recomputation": True, "matched_ratio_exact_recomputation": True,
            "evaluator_checks_passed": True, "package_hashes_exact": True,
            "primary_endpoints_frozen_before_reveal": True,
            "public_design_nonjoinable": True, "sentinel_identity_isolated": True,
        },
        "negative_challenges": challenges,
        "claim_boundary": (
            "synthetic software/release qualification only; no empirical PET morphology, "
            "hydraulic, temperature, molecular-degradation, length-proxy, numerical-validation, "
            "migration, clogging, deformation or coupling claim"
        ),
        "stop_boundary": (
            "stop before real keys/data, laboratory or numerical execution, empirical unblinding, "
            "physical validation, degradation/permeability claims, migration, clogging or coupling"
        ),
        "authority": AUTHORITY,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design-dir", type=Path, default=DESIGN_DEFAULT)
    parser.add_argument("--design-audit", type=Path, default=DESIGN_AUDIT_DEFAULT)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    design_dir = args.design_dir.resolve(); design_audit = args.design_audit.resolve()
    output = args.output_dir.absolute()
    if output.exists():
        print(f"Refusing to overwrite immutable output: {output}", file=sys.stderr); return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=str(output.parent)))
    work = temporary / "verification"
    work.mkdir()
    try:
        verification = verify(design_dir, design_audit, work)
        json_dump(work / "verification.json", verification)
        completion = {
            "schema": "pet.stage33do-operational-workflow-synthetic-verification-completion.v1",
            "stage": STAGE, "status": "complete", "completed_utc": utc_now(),
            "passed": True, "verification_sha256": sha256(work / "verification.json"),
            "no_empirical_data": True, "no_real_key": True,
            "no_laboratory_execution": True, "no_simulation": True,
            "authority_closed": True,
        }
        json_dump(work / "completion.json", completion)
        os.replace(work, output)
        print(json.dumps(completion, indent=2, sort_keys=True)); return 0
    except Exception as exc:
        failure = {
            "schema": "pet.stage33do-operational-workflow-synthetic-verification-failure.v1",
            "stage": STAGE, "status": "failed_closed", "passed": False,
            "created_utc": utc_now(), "error_type": type(exc).__name__, "error": str(exc),
            "no_empirical_data": True, "authority": AUTHORITY,
        }
        json_dump(work / "failure.json", failure)
        failed_output = output.with_name(output.name + "_failed")
        if not failed_output.exists(): os.replace(work, failed_output)
        print(json.dumps(failure, indent=2, sort_keys=True), file=sys.stderr); return 2
    finally:
        if temporary.exists(): shutil.rmtree(temporary, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
