"""Freeze the accepted Stage26b Tier-1 placement checkpoint and bounded handoff."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = PROJECT / "stage26_staging" / "stage26b_tier1_placement_preflight_v1.json"
EVALUATION = PROJECT / "stage26_evaluations" / "stage26b_dry_multifibre_20260814" / "tier1_placement_evaluation_01" / "evaluation.json"
RENDER = PROJECT / "stage26_renders" / "stage26b_dry_multifibre_20260814" / "tier1_placement_render_02"
OUTPUT = PROJECT / "stage26_checkpoints" / "stage26b_dry_multifibre_20260814" / "tier1_placement_checkpoint_01"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable Tier-1 placement checkpoint already exists")
    cfg = load_json(CONFIG)
    evaluation = load_json(EVALUATION)
    render_manifest_path = RENDER / "render_manifest.json"
    render = load_json(render_manifest_path)
    if not evaluation.get("passed") or not render.get("passed"):
        raise RuntimeError("evaluation or visual preflight did not pass")
    if evaluation["config_sha256"] != digest(CONFIG) or render["source_hashes"]["evaluation"] != digest(EVALUATION):
        raise RuntimeError("evaluation/render source binding failed")
    image_path = Path(render["image_path"])
    if digest(image_path) != render["image_sha256"]:
        raise RuntimeError("render image hash mismatch")
    cases = []
    for case in evaluation["cases"]:
        placement_path = Path(case["placement_path"])
        if digest(placement_path) != case["placement_sha256"]:
            raise RuntimeError("placement hash mismatch: " + case["case_id"])
        placement = load_json(placement_path)
        cases.append({
            "case_id": case["case_id"],
            "fibre_count": placement["fibre_count"],
            "dry_mass_percent": placement["case"]["dry_mass_percent"],
            "placement_path": str(placement_path),
            "placement_sha256": case["placement_sha256"],
            "minimum_fibre_fibre_clearance_m": case["minimum_fibre_fibre_clearance_m"],
            "maximum_anchor_multiplicity": case["maximum_anchor_multiplicity"],
            "all_geometry_checks_passed": all(case["checks"].values()),
        })
    checkpoint = {
        "schema": "lbs.stage26b-tier1-placement-checkpoint.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "frozen_tier1_geometry_preflight",
        "cases": cases,
        "evidence": {
            "config_path": str(CONFIG), "config_sha256": digest(CONFIG),
            "evaluation_path": str(EVALUATION), "evaluation_sha256": digest(EVALUATION),
            "render_manifest_path": str(render_manifest_path), "render_manifest_sha256": digest(render_manifest_path),
            "accepted_visual_path": str(image_path), "accepted_visual_sha256": digest(image_path),
            "freezer_sha256": digest(Path(__file__)),
        },
        "authority": {
            "authorized_next_activity": "Bounded dry YADE relaxation of the exact stage26b_f002_A and stage26b_f004_A placements only.",
            "tier1_two_and_four_fibre_yade_execution_authorized": True,
            "eight_or_more_fibre_execution_authorized": False,
            "flow_execution_authorized": False,
            "transient_two_way_coupling_authorized": False,
            "deformation_coupled_flow_authorized": False,
            "production_parametric_study_authorized": False,
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "checkpoint_manifest.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(checkpoint, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": True, "checkpoint_manifest_sha256": digest(path)}, sort_keys=True))


if __name__ == "__main__":
    main()
