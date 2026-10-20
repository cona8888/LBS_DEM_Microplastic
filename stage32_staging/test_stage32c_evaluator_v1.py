#!/usr/bin/env python3
"""Synthetic dry-run tests for Stage32C. Synthetic values are never evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
EVALUATOR = ROOT / "stage32_staging" / "evaluate_stage32c_matched_validation_v1.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def density(temp_c: float) -> float:
    return 1000.0 * (1.0 - ((temp_c + 288.9414) / (508929.2 * (temp_c + 68.12963))) * (temp_c - 3.9863) ** 2)


def water_mass_g(k_m_s: float, diameter_mm: float, length_mm: float, head_m: float, time_s: float, temp_c: float = 20.0) -> float:
    area = math.pi * (diameter_mm / 2000.0) ** 2
    q = k_m_s * area * head_m / (length_mm / 1000.0)
    return q * time_s * density(temp_c) * 1000.0


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_rows(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    release = args.release_dir.resolve()
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite: {output}")

    design_fields, design = read_rows(release / "preparation_schedule.csv")
    capture_fields, capture = read_rows(release / "operator_capture.csv")
    linearity_fields, _ = read_rows(release / "darcy_linearity_capture.csv")
    design_by_id = {row["specimen_id"]: row for row in design}
    clean_base = 0.00786
    clean_offsets = {1: -0.0025, 2: -0.0015, 3: -0.0005, 4: 0.0005, 5: 0.0015, 6: 0.0025}
    for row in capture:
        d = design_by_id[row["specimen_id"]]
        target = float(d["target_dry_mass_percent"])
        ratio = float(d["numerical_mean_ratio"])
        replicate = int(d["replicate"])
        if d["group_id"] == "clean":
            k20 = clean_base * (1.0 + clean_offsets[replicate])
        else:
            k20 = clean_base * ratio
        row.update({
            "batch_id": "SYNTHETIC-B001", "dry_sand_mass_g": "1000", "fibre_mass_g": f"{10.0 * target:.12g}",
            "initial_void_ratio": "0.744", "final_void_ratio": "0.744", "water_temperature_c": "20.0",
            "specimen_diameter_mm": "50.0", "specimen_length_mm": "100.0", "head_difference_m": "0.100",
            "collection_time_s": "60.0", "collected_water_mass_g": f"{water_mass_g(k20, 50, 100, 0.1, 60):.15g}",
            "K_raw_m_s": "", "K20_m_s": "", "valid": "yes", "rejection_reason": "",
            "operator_notes": "SYNTHETIC DRY-RUN ONLY; NOT EXPERIMENTAL EVIDENCE",
        })

    clean_sid = next(row["specimen_id"] for row in design if row["group_id"] == "clean")
    high_sid = next(row["specimen_id"] for row in design if row["group_id"] == "iso_0p401820")
    high_ratio = float(design_by_id[high_sid]["numerical_mean_ratio"])
    linearity = []
    for sid, k20 in [(clean_sid, clean_base), (high_sid, clean_base * high_ratio)]:
        for index, head in enumerate([0.05, 0.10, 0.15], 1):
            linearity.append({
                "specimen_id": sid, "determination_id": f"SYN-{index}", "water_temperature_c": "20.0",
                "specimen_diameter_mm": "50.0", "specimen_length_mm": "100.0", "head_difference_m": f"{head:.3f}",
                "collection_time_s": "60.0", "collected_water_mass_g": f"{water_mass_g(k20, 50, 100, head, 60):.15g}",
                "K_raw_m_s": "", "K20_m_s": "", "valid": "yes", "rejection_reason": "",
                "operator_notes": "SYNTHETIC LINEARITY DRY-RUN ONLY",
            })

    with tempfile.TemporaryDirectory(prefix="stage32c_synthetic_") as temp_name:
        temp = Path(temp_name)
        capture_path = temp / "synthetic_capture.csv"
        linearity_path = temp / "synthetic_linearity.csv"
        write_rows(capture_path, capture_fields, capture)
        write_rows(linearity_path, linearity_fields, linearity)
        pass_output = temp / "pass_evaluation"
        command = [sys.executable, str(EVALUATOR), "--release-dir", str(release), "--capture", str(capture_path),
                   "--linearity", str(linearity_path), "--phase", "all", "--output-dir", str(pass_output)]
        passed_run = subprocess.run(command, text=True, capture_output=True, check=False)
        pass_evaluation = json.loads((pass_output / "evaluation.json").read_text(encoding="utf-8")) if (pass_output / "evaluation.json").is_file() else None

        tampered = [dict(row) for row in capture]
        tampered[0]["run_order"] = "999"
        tampered_path = temp / "tampered_capture.csv"
        write_rows(tampered_path, capture_fields, tampered)
        fail_output = temp / "fail_evaluation"
        fail_command = [sys.executable, str(EVALUATOR), "--release-dir", str(release), "--capture", str(tampered_path),
                        "--linearity", str(linearity_path), "--phase", "phase1", "--output-dir", str(fail_output)]
        failed_run = subprocess.run(fail_command, text=True, capture_output=True, check=False)
        failure = json.loads((fail_output / "failure.json").read_text(encoding="utf-8")) if (fail_output / "failure.json").is_file() else None

        checks = {
            "synthetic_pass_exit_zero": passed_run.returncode == 0,
            "synthetic_pass_evaluation_created": pass_evaluation is not None,
            "synthetic_phase1_model_support": bool(pass_evaluation and pass_evaluation["gates"]["phase1_model_support"]),
            "synthetic_orientation_support": bool(pass_evaluation and pass_evaluation["gates"]["orientation"]["supported"]),
            "synthetic_overall_support": bool(pass_evaluation and pass_evaluation["gates"]["overall_preregistered_support"]),
            "identity_tamper_exit_nonzero": failed_run.returncode != 0,
            "identity_tamper_failure_recorded": bool(failure and failure.get("status") == "failed_closed"),
        }
        result = {
            "schema": "lbs.stage32c-evaluator-synthetic-test.v1", "evidence_role": "software dry-run only; never experimental evidence",
            "release_manifest_sha256": sha256(release / "release_manifest.json"), "evaluator_sha256": sha256(EVALUATOR),
            "checks": checks, "pass_stdout": passed_run.stdout.strip(), "pass_stderr": passed_run.stderr.strip(),
            "tamper_stdout": failed_run.stdout.strip(), "tamper_stderr": failed_run.stderr.strip(),
            "passed": all(checks.values()),
        }
    output.mkdir(parents=True)
    (output / "synthetic_test.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output_dir": str(output), "checks": checks, "passed": result["passed"]}, indent=2))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
