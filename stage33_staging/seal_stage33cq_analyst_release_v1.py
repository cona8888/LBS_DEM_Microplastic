"""Seal a sanitized Stage33C-Q analyst package after two visual leakage reviews."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REVIEW_COLUMNS = {
    "blind_release_id", "image_id", "reviewer_slot", "reviewer_id", "review_status",
    "burned_label_absent", "burned_scale_bar_absent", "other_visual_leakage_absent",
    "findings", "review_utc",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def bool_value(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def json_dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def seal(
    pending_dir: Path,
    review_path: Path,
    roles_path: Path,
    restricted_commitment_path: Path,
    output: Path,
) -> dict[str, Any]:
    if output.exists():
        raise RuntimeError(f"fail-closed: seal output already exists: {output}")
    analyst_manifest_path = pending_dir / "analyst_manifest.json"
    blinded_manifest_path = pending_dir / "blinded_image_manifest.csv"
    package_hashes_path = pending_dir / "package_hashes.json"
    leakage_scan_path = pending_dir / "leakage_scan.json"
    for required in (
        analyst_manifest_path, blinded_manifest_path, package_hashes_path,
        leakage_scan_path, pending_dir / "visual_leakage_montage.png",
    ):
        if not required.is_file():
            raise RuntimeError(f"fail-closed: pending package artifact missing: {required}")
    analyst_manifest = json.loads(analyst_manifest_path.read_text(encoding="utf-8"))
    if analyst_manifest.get("state") != "SANITIZED_PENDING_VISUAL_REVIEW":
        raise RuntimeError(f"fail-closed: invalid pending-package state: {analyst_manifest.get('state')}")
    if analyst_manifest.get("metadata_leak_scan") != "pass" or analyst_manifest.get("treatment_key_present") is not False:
        raise RuntimeError("fail-closed: machine leakage audit did not pass")
    leakage_scan = json.loads(leakage_scan_path.read_text(encoding="utf-8"))
    if (
        leakage_scan.get("status") != "pass"
        or leakage_scan.get("finding_n") != 0
        or leakage_scan.get("findings") != []
        or analyst_manifest.get("leakage_scan_sha256") != sha256(leakage_scan_path)
    ):
        raise RuntimeError("fail-closed: explicit machine leakage-scan evidence is missing or failed")
    payload_hashes = json.loads(package_hashes_path.read_text(encoding="utf-8"))
    for relative, expected in payload_hashes.items():
        path = pending_dir / Path(relative)
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"fail-closed: pending package mutation or missing payload: {relative}")

    roles = json.loads(roles_path.read_text(encoding="utf-8"))
    roles_sha256 = sha256(roles_path)
    if analyst_manifest.get("roles_and_key_custody_sha256") != roles_sha256:
        raise RuntimeError("fail-closed: roles file is not the one bound into the pending package")
    release_officers = set(map(str, roles.get("release_officer_ids", [])))
    if len(release_officers) < 2:
        raise RuntimeError("fail-closed: at least two release officers are required")
    with blinded_manifest_path.open(newline="", encoding="utf-8-sig") as f:
        image_rows = list(csv.DictReader(f))
    image_ids = {row["image_id"] for row in image_rows}
    release_ids = {row["blind_release_id"] for row in image_rows}
    if len(release_ids) != 1:
        raise RuntimeError("fail-closed: pending package must bind exactly one release ID")
    release_id = next(iter(release_ids))
    if not restricted_commitment_path.is_file():
        raise RuntimeError("fail-closed: restricted cross-release commitment is missing")
    commitment = json.loads(restricted_commitment_path.read_text(encoding="utf-8"))
    restricted_manifest_path = restricted_commitment_path.parent / "restricted_manifest.json"
    if not restricted_manifest_path.is_file():
        raise RuntimeError("fail-closed: restricted manifest bound by the commitment is missing")
    restricted_manifest = json.loads(restricted_manifest_path.read_text(encoding="utf-8"))
    commitment_gates = (
        commitment.get("stage") == "Stage33C-Q",
        commitment.get("release_id") == release_id,
        commitment.get("state") == "CUSTODIAN_COMMITTED_PENDING_VISUAL_REVIEW",
        commitment.get("restricted_manifest_sha256") == sha256(restricted_manifest_path),
        commitment.get("custodian_key_sha256") == analyst_manifest.get("custodian_key_sha256"),
        commitment.get("roles_and_key_custody_sha256") == analyst_manifest.get("roles_and_key_custody_sha256"),
        commitment.get("resolved_config_sha256") == analyst_manifest.get("resolved_config_sha256"),
        commitment.get("resolved_config_hash_basis") == analyst_manifest.get("resolved_config_hash_basis"),
        commitment.get("release_builder_sha256") == analyst_manifest.get("release_builder_sha256"),
        commitment.get("blinded_image_manifest_sha256") == sha256(blinded_manifest_path),
        commitment.get("analyst_manifest_sha256") == sha256(analyst_manifest_path),
        commitment.get("analyst_package_hashes_sha256") == sha256(package_hashes_path),
        commitment.get("treatment_key_present_in_analyst_package") is False,
    )
    if not all(commitment_gates):
        raise RuntimeError("fail-closed: restricted cross-release commitment does not bind the pending analyst package")
    restricted_manifest_gates = (
        restricted_manifest.get("stage") == "Stage33C-Q",
        restricted_manifest.get("release_id") == release_id,
        restricted_manifest.get("custodian_key_sha256") == commitment.get("custodian_key_sha256"),
        restricted_manifest.get("roles_and_key_custody_sha256") == roles_sha256,
        restricted_manifest.get("resolved_config_sha256") == commitment.get("resolved_config_sha256"),
        restricted_manifest.get("resolved_config_hash_basis") == commitment.get("resolved_config_hash_basis"),
        restricted_manifest.get("release_builder_sha256") == commitment.get("release_builder_sha256"),
    )
    if not all(restricted_manifest_gates):
        raise RuntimeError("fail-closed: restricted manifest lineage disagrees with the cross-release commitment")
    with review_path.open(newline="", encoding="utf-8-sig") as f:
        review_rows = list(csv.DictReader(f))
    if not review_rows or REVIEW_COLUMNS - set(review_rows[0]):
        raise RuntimeError(f"fail-closed: visual review file missing columns: {sorted(REVIEW_COLUMNS - set(review_rows[0]) if review_rows else REVIEW_COLUMNS)}")
    grouped: dict[str, list[dict[str, str]]] = {}
    for row_no, row in enumerate(review_rows, start=2):
        if row["blind_release_id"] != release_id or row["image_id"] not in image_ids:
            raise RuntimeError(f"fail-closed: review release/image binding mismatch at row {row_no}")
        grouped.setdefault(row["image_id"], []).append(row)
    if set(grouped) != image_ids:
        raise RuntimeError("fail-closed: visual review does not cover every image exactly")
    reviewers_used: set[str] = set()
    for image_id, rows in grouped.items():
        if len(rows) != 2 or {row["reviewer_slot"] for row in rows} != {"1", "2"}:
            raise RuntimeError(f"fail-closed: image {image_id} requires reviewer slots 1 and 2")
        reviewers = {row["reviewer_id"].strip() for row in rows}
        if len(reviewers) != 2 or not reviewers.issubset(release_officers):
            raise RuntimeError(f"fail-closed: image {image_id} lacks two distinct authorized release officers")
        reviewers_used.update(reviewers)
        for row in rows:
            gates = (
                row["review_status"].strip().lower() == "pass",
                bool_value(row["burned_label_absent"]),
                bool_value(row["burned_scale_bar_absent"]),
                bool_value(row["other_visual_leakage_absent"]),
                not row["findings"].strip(),
                bool(row["review_utc"].strip()),
            )
            if not all(gates):
                raise RuntimeError(f"fail-closed: visual leakage review did not pass for {image_id}")

    output.mkdir(parents=True)
    shutil.copy2(review_path, output / "visual_leakage_review.csv")
    declaration = {
        "stage": "Stage33C-Q",
        "release_id": release_id,
        "state": "ANALYST_RELEASED",
        "created_utc": utc_now(),
        "pending_package_path": str(pending_dir),
        "pending_package_hashes_sha256": sha256(package_hashes_path),
        "blinded_image_manifest_sha256": sha256(blinded_manifest_path),
        "analyst_manifest_sha256": sha256(analyst_manifest_path),
        "visual_leakage_montage_sha256": sha256(pending_dir / "visual_leakage_montage.png"),
        "visual_leakage_review_sha256": sha256(output / "visual_leakage_review.csv"),
        "roles_and_key_custody_sha256": roles_sha256,
        "restricted_cross_release_commitment_sha256": sha256(restricted_commitment_path),
        "restricted_manifest_sha256": sha256(restricted_manifest_path),
        "visual_sealer_sha256": sha256(Path(__file__).resolve()),
        "reviewer_ids": sorted(reviewers_used),
        "image_n": len(image_ids),
        "machine_leakage_scan": "pass",
        "leakage_scan_sha256": sha256(leakage_scan_path),
        "two_person_visual_review": "pass",
        "treatment_key_present": False,
        "claim_boundary": "blinded acquisition release only; no empirical analysis or degradation inference",
    }
    json_dump(output / "release_declaration.json", declaration)
    completion = {
        "stage": "Stage33C-Q",
        "release_id": release_id,
        "status": "complete",
        "state": "ANALYST_RELEASED",
        "completed_utc": utc_now(),
        "release_declaration_sha256": sha256(output / "release_declaration.json"),
        "no_empirical_analysis": True,
        "no_treatment_reveal": True,
        "no_simulation": True,
    }
    json_dump(output / "completion.json", completion)
    return declaration


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pending-package", type=Path, required=True)
    parser.add_argument("--visual-review", type=Path, required=True)
    parser.add_argument("--roles-file", type=Path, required=True)
    parser.add_argument("--restricted-commitment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = seal(
        args.pending_package.resolve(), args.visual_review.resolve(), args.roles_file.resolve(),
        args.restricted_commitment.resolve(), args.output.resolve(),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
