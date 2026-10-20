#!/usr/bin/env python3
"""Build the immutable Stage32C blinded laboratory-validation release."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
DESIGN_DIR = ROOT / "stage32_designs" / "stage32a_matched_constant_head_validation_20260828" / "design_01"
AUDIT = ROOT / "stage32_evaluations" / "stage32a_matched_constant_head_validation_20260828" / "design_audit_01" / "design_audit.json"
LITERATURE_DIR = ROOT / "stage32_literature" / "stage32b_literature_verification_20260829"
STAGING = ROOT / "stage32_staging"

CONTRACT = STAGING / "STAGE32C_BLINDED_VALIDATION_RELEASE_CONTRACT.md"
EVALUATOR = STAGING / "evaluate_stage32c_matched_validation_v1.py"
TESTER = STAGING / "test_stage32c_evaluator_v1.py"
AUDITOR = STAGING / "audit_stage32c_blinded_validation_release_v1.py"

DEFAULT_OUTPUT = ROOT / "stage32_releases" / "stage32c_blinded_validation_release_20260829" / "release_01"

OPERATOR_FIELDS = [
    "run_order", "specimen_id", "phase", "preparation_block", "batch_id",
    "dry_sand_mass_g", "fibre_mass_g", "initial_void_ratio", "final_void_ratio",
    "water_temperature_c", "specimen_diameter_mm", "specimen_length_mm",
    "head_difference_m", "collection_time_s", "collected_water_mass_g",
    "K_raw_m_s", "K20_m_s", "valid", "rejection_reason", "operator_notes",
]

LINEARITY_FIELDS = [
    "specimen_id", "determination_id", "water_temperature_c",
    "specimen_diameter_mm", "specimen_length_mm", "head_difference_m",
    "collection_time_s", "collected_water_mass_g", "K_raw_m_s", "K20_m_s",
    "valid", "rejection_reason", "operator_notes",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": str(path.resolve()), "sha256": sha256(path)}


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_dir.resolve()

    required = {
        "stage32a_protocol": DESIGN_DIR / "resolved_protocol.json",
        "stage32a_design": DESIGN_DIR / "design_matrix.csv",
        "stage32a_design_audit": AUDIT,
        "stage32b_literature_dataset": LITERATURE_DIR / "literature_dataset.json",
        "stage32b_literature_report": LITERATURE_DIR / "literature_verification_report.md",
        "stage32c_contract": CONTRACT,
        "release_builder": Path(__file__).resolve(),
        "evaluator": EVALUATOR,
        "synthetic_tester": TESTER,
        "release_auditor": AUDITOR,
    }
    source_bindings = {name: binding(path) for name, path in required.items()}

    protocol = json.loads(required["stage32a_protocol"].read_text(encoding="utf-8"))
    design_audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    if protocol.get("passed") is not True or design_audit.get("passed") is not True:
        raise RuntimeError("Stage32A protocol or independent audit is not accepted")

    with required["stage32a_design"].open("r", encoding="utf-8", newline="") as handle:
        design_rows = list(csv.DictReader(handle))
        design_fields = list(design_rows[0].keys()) if design_rows else []
    if len(design_rows) != 38 or len({row["specimen_id"] for row in design_rows}) != 38:
        raise RuntimeError("Stage32A design is not the frozen 38-specimen design")

    if output.exists():
        raise FileExistsError(f"Refusing to overwrite immutable release: {output}")
    output.mkdir(parents=True)

    shutil.copyfile(required["stage32a_design"], output / "preparation_schedule.csv")
    operator_rows = []
    for row in design_rows:
        operator_rows.append({
            "run_order": row["run_order"],
            "specimen_id": row["specimen_id"],
            "phase": row["phase"],
            "preparation_block": row["preparation_block"],
            **{field: "" for field in OPERATOR_FIELDS[4:]},
        })
    write_csv(output / "operator_capture.csv", OPERATOR_FIELDS, operator_rows)
    write_csv(output / "darcy_linearity_capture.csv", LINEARITY_FIELDS, [])

    readme = """# Stage32C blinded validation release\n\nThis directory is an immutable, pre-data release. It does not contain experimental observations and does not make a validation claim.\n\n- The preparation custodian uses `preparation_schedule.csv`.\n- The hydraulic operator records raw observations in a copy of `operator_capture.csv` without receiving predictions.\n- Three-gradient controls are recorded in a copy of `darcy_linearity_capture.csv`.\n- The independent analyst evaluates Phase 1 before Phase 2 using the hash-bound evaluator.\n\nExample (after independently freezing completed raw files):\n\n```powershell\npython C:\\MATDEM_MICROPLASTIC\\stage32_staging\\evaluate_stage32c_matched_validation_v1.py --release-dir <release> --capture <completed.csv> --linearity <linearity.csv> --phase phase1 --output-dir <new-output>\n```\n\nDo not edit this release in place.\n"""
    (output / "README.md").write_text(readme, encoding="utf-8", newline="\n")

    artifacts = {}
    for name in ["preparation_schedule.csv", "operator_capture.csv", "darcy_linearity_capture.csv", "README.md"]:
        artifacts[name] = binding(output / name)

    manifest = {
        "schema": "lbs.stage32c-blinded-validation-release.v1",
        "status": "frozen_predata_release",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_role": "pre-registered blinded evaluation release; no laboratory data or validation claim",
        "source_bindings": source_bindings,
        "artifacts": artifacts,
        "row_counts": {"preparation_schedule": 38, "operator_capture": 38, "darcy_linearity_capture": 0},
        "blinding": {
            "operator_capture_omits": ["group_id", "orientation", "target_dry_mass_percent", "numerical_mean_ratio", "numerical_minimum_ratio", "numerical_maximum_ratio"],
            "join_key": "specimen_id",
        },
        "authority": protocol["authority"],
        "passed": True,
    }
    manifest_path = output / "release_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    completion = {
        "schema": "lbs.stage32c-release-completion.v1",
        "status": "complete",
        "release_manifest_sha256": sha256(manifest_path),
        "next_handoff": "independent release audit and synthetic evaluator dry-run only; no laboratory execution",
        "passed": True,
    }
    (output / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output_dir": str(output), "manifest_sha256": sha256(manifest_path), "passed": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
