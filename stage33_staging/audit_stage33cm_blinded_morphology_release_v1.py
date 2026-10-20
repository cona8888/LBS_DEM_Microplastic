"""Fail-closed audit of the immutable Stage33C-M software release."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_empty(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise RuntimeError(f"fail-closed: audit directory is not empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def json_dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def audit(design_path: Path, output: Path) -> dict[str, Any]:
    ensure_empty(output)
    design = json.loads(design_path.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    def check(check_id: str, passed: bool, observed: Any, requirement: str) -> None:
        checks.append({"check_id": check_id, "pass": bool(passed), "observed": observed, "requirement": requirement})

    check("stage_name", design.get("stage") == "Stage33C-M", design.get("stage"), "Stage33C-M")
    check("release_status", design.get("status") == "software_verified_empirically_unvalidated", design.get("status"), "software_verified_empirically_unvalidated")
    for section in ("release_files", "lineage"):
        for item in design.get(section, []):
            path = Path(item["path"])
            exists = path.is_file()
            check(f"{section}_exists_{path.name}", exists, str(path), "file exists")
            if exists:
                actual = sha256(path)
                check(f"{section}_hash_{path.name}", actual == item["sha256"].lower(), actual, item["sha256"].lower())

    verification_dir = Path(design["synthetic_verification"]["directory"])
    verification_path = verification_dir / "verification.json"
    completion_path = verification_dir / "completion.json"
    failure_path = verification_dir / "failure.json"
    check("synthetic_verification_exists", verification_path.is_file(), str(verification_path), "exists")
    check("synthetic_completion_exists", completion_path.is_file(), str(completion_path), "exists")
    check("synthetic_no_failure", not failure_path.exists(), failure_path.exists(), "False")
    if verification_path.is_file():
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
        check("synthetic_pass", verification.get("pass") is True, verification.get("pass"), "True")
        check("synthetic_54_of_54", verification.get("passed_n") == 54 and verification.get("failed_n") == 0, {"passed": verification.get("passed_n"), "failed": verification.get("failed_n")}, "54 passed, 0 failed")
        check("synthetic_claim_boundary", "software geometry verification only" in verification.get("claim_boundary", ""), verification.get("claim_boundary"), "software-only boundary present")
        actual = sha256(verification_path)
        check("verification_hash", actual == design["synthetic_verification"]["verification_sha256"], actual, design["synthetic_verification"]["verification_sha256"])
    if completion_path.is_file():
        completion = json.loads(completion_path.read_text(encoding="utf-8"))
        check("synthetic_completion_status", completion.get("status") == "complete", completion.get("status"), "complete")
        check("synthetic_no_empirical_data", completion.get("no_empirical_data_analyzed") is True, completion.get("no_empirical_data_analyzed"), "True")
        check("synthetic_no_dem_lbm", completion.get("no_dem_lbm_job_launched") is True, completion.get("no_dem_lbm_job_launched"), "True")
        actual = sha256(completion_path)
        check("completion_hash", actual == design["synthetic_verification"]["completion_sha256"], actual, design["synthetic_verification"]["completion_sha256"])

    bound_artifacts = {
        "objects_sha256": verification_dir / "analysis_01" / "objects.csv",
        "metrics_comparison_sha256": verification_dir / "metrics_comparison.csv",
        "montage_sha256": verification_dir / "synthetic_overlay_montage.png",
    }
    for key, path in bound_artifacts.items():
        actual = sha256(path) if path.is_file() else None
        check(f"bound_{key}", actual == design["synthetic_verification"][key], actual, design["synthetic_verification"][key])

    objects_path = verification_dir / "analysis_01" / "objects.csv"
    if objects_path.is_file():
        with objects_path.open(newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        ids = [row["object_id"] for row in rows]
        check("object_ids_unique", len(ids) == len(set(ids)), {"rows": len(ids), "unique": len(set(ids))}, "equal")
        candidate_ok = all(row["primary_analysis_included"] == "False" for row in rows if row["segmentation_status"] == "candidate_unadjudicated")
        check("candidate_never_publication", candidate_ok, candidate_ok, "True")
        exclusions = {row["image_id"]: row for row in rows}
        check("border_excluded", exclusions["border_clip"]["primary_analysis_included"] == "False", exclusions["border_clip"]["primary_analysis_included"], "False")
        check("underresolved_excluded", exclusions["underresolved"]["primary_analysis_included"] == "False", exclusions["underresolved"]["primary_analysis_included"], "False")
        check("branch_excluded", exclusions["branch_y"]["primary_analysis_included"] == "False", exclusions["branch_y"]["primary_analysis_included"], "False")
        numeric_columns = [
            "max_feret_um", "min_feret_um", "projected_area_um2", "perimeter_um", "solidity", "circularity"
        ]
        finite = all(
            (row[column] == "" or math.isfinite(float(row[column])))
            for row in rows for column in numeric_columns
        )
        check("finite_core_metrics", finite, finite, "True")

    template_path = next(Path(v["path"]) for v in design["release_files"] if Path(v["path"]).name == "blinded_manifest_template.csv")
    with template_path.open(newline="", encoding="utf-8-sig") as f:
        headers = next(csv.reader(f))
    forbidden = {"condition_id", "challenge_arm", "target_temperature_c", "temperature_c", "source_batch_id", "source_aliquot_id", "randomization_block"}
    check("template_no_treatment_key_columns", not (set(map(str.lower, headers)) & forbidden), sorted(set(map(str.lower, headers)) & forbidden), "empty")
    check("template_has_blind_binding", {"blind_release_id", "blind_key_manifest_sha256"}.issubset(headers), headers, "both binding columns")
    check("empirical_gate_closed", design.get("empirical_publication_gates", {}).get("status") == "closed", design.get("empirical_publication_gates", {}).get("status"), "closed")
    check("stop_boundary_no_simulation", any("no DEM or LBM" in item for item in design.get("stop_boundary", [])), design.get("stop_boundary"), "explicit no DEM/LBM")

    passed = all(item["pass"] for item in checks)
    result = {
        "stage": "Stage33C-M",
        "audit_id": "stage33cm_release_audit_01",
        "created_utc": utc_now(),
        "pass": passed,
        "check_n": len(checks),
        "passed_n": sum(item["pass"] for item in checks),
        "failed_n": sum(not item["pass"] for item in checks),
        "checks": checks,
        "resolved_design_path": str(design_path),
        "resolved_design_sha256": sha256(design_path),
        "conclusion": "software release accepted; empirical publication and degradation-calibration gates remain closed" if passed else "release rejected",
    }
    json_dump(output / "release_audit.json", result)
    completion = {
        "stage": "Stage33C-M",
        "status": "complete" if passed else "failed",
        "completed_utc": utc_now(),
        "release_audit_sha256": sha256(output / "release_audit.json"),
        "empirical_publication_gate": "closed",
        "no_empirical_data_analyzed": True,
        "no_dem_lbm_job_launched": True,
    }
    json_dump(output / ("completion.json" if passed else "failure.json"), completion)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.design.resolve(), args.output.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
