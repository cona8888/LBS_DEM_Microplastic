#!/usr/bin/env python3
"""Independent structural and lineage audit of a Stage32C release."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


FORBIDDEN_OPERATOR_FIELDS = {
    "group_id", "orientation", "target_dry_mass_percent", "fibre_mass_g_per_1000g_dry_sand",
    "numerical_mean_ratio", "numerical_minimum_ratio", "numerical_maximum_ratio",
}
MEASUREMENT_FIELDS = {
    "batch_id", "dry_sand_mass_g", "fibre_mass_g", "initial_void_ratio", "final_void_ratio",
    "water_temperature_c", "specimen_diameter_mm", "specimen_length_mm", "head_difference_m",
    "collection_time_s", "collected_water_mass_g", "K_raw_m_s", "K20_m_s", "valid",
    "rejection_reason", "operator_notes",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    release = args.release_dir.resolve()
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite immutable audit: {output}")

    manifest_path = release / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks: dict[str, bool] = {}
    checks["schema"] = manifest.get("schema") == "lbs.stage32c-blinded-validation-release.v1"
    checks["release_status"] = manifest.get("status") == "frozen_predata_release" and manifest.get("passed") is True
    checks["all_source_bindings_match"] = all(
        Path(item["path"]).is_file() and sha256(Path(item["path"])).lower() == item["sha256"].lower()
        for item in manifest.get("source_bindings", {}).values()
    )
    checks["all_artifact_bindings_match"] = all(
        (release / name).is_file() and sha256(release / name).lower() == item["sha256"].lower()
        for name, item in manifest.get("artifacts", {}).items()
    )
    design_fields, design = read_csv(release / "preparation_schedule.csv")
    operator_fields, operator = read_csv(release / "operator_capture.csv")
    linearity_fields, linearity = read_csv(release / "darcy_linearity_capture.csv")
    checks["design_38_unique"] = len(design) == 38 and len({r["specimen_id"] for r in design}) == 38
    checks["operator_38_unique"] = len(operator) == 38 and len({r["specimen_id"] for r in operator}) == 38
    checks["operator_identity_matches_design"] = [r["specimen_id"] for r in operator] == [r["specimen_id"] for r in design]
    checks["operator_order_matches_design"] = all(
        o["run_order"] == d["run_order"] and o["phase"] == d["phase"] and o["preparation_block"] == d["preparation_block"]
        for o, d in zip(operator, design)
    )
    checks["operator_predictions_blinded"] = not (set(operator_fields) & FORBIDDEN_OPERATOR_FIELDS)
    checks["operator_measurements_empty"] = all(not row[field].strip() for row in operator for field in MEASUREMENT_FIELDS)
    checks["linearity_template_empty"] = len(linearity) == 0
    checks["linearity_template_has_raw_fields"] = {
        "specimen_id", "determination_id", "head_difference_m", "collection_time_s", "collected_water_mass_g", "valid"
    }.issubset(linearity_fields)
    checks["preparation_retains_predictions"] = {
        "group_id", "orientation", "target_dry_mass_percent", "numerical_mean_ratio", "numerical_minimum_ratio", "numerical_maximum_ratio"
    }.issubset(design_fields)
    authority = manifest.get("authority", {})
    checks["authority_remains_closed"] = all(authority.get(key) is False for key in [
        "laboratory_execution", "physical_validation_claim", "numerical_rerun", "migration", "clogging",
        "deformation", "transient_coupling", "two_way_coupling",
    ])
    checks["completion_manifest_binding"] = False
    completion_path = release / "completion.json"
    if completion_path.is_file():
        completion = json.loads(completion_path.read_text(encoding="utf-8"))
        checks["completion_manifest_binding"] = completion.get("status") == "complete" and completion.get("release_manifest_sha256", "").lower() == sha256(manifest_path).lower()

    result = {
        "schema": "lbs.stage32c-blinded-validation-release-audit.v1",
        "release_dir": str(release), "release_manifest_sha256": sha256(manifest_path),
        "checks": checks, "passed": all(checks.values()),
        "conclusion": "Release is structurally frozen, prediction-blinded, lineage-bound, and contains no observations." if all(checks.values()) else "Release audit failed closed.",
    }
    output.mkdir(parents=True)
    (output / "release_audit.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output_dir": str(output), "checks": checks, "passed": result["passed"]}, indent=2))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
