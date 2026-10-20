"""Freeze the verified Stage26f static-cage handoff."""

import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load(path):
    with Path(path).open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--audit", required=True)
    parser.add_argument("--render", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    campaign = Path(args.campaign).resolve()
    audit_path = Path(args.audit).resolve()
    render_path = Path(args.render).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("immutable Stage26f handoff already exists")
    config, completion, audit, render = (
        load(config_path),
        load(campaign / "completion.json"),
        load(audit_path),
        load(render_path),
    )
    if not all(value.get("passed") is True for value in (completion, audit, render)):
        raise RuntimeError("one or more Stage26f handoff sources failed")
    if completion["passing_candidate_count"] != 8 or audit["verified_passing_candidate_count"] != 8:
        raise RuntimeError("Stage26f did not verify all eight geometries")
    if audit["distinct_joint_support_topology_count"] != 8:
        raise RuntimeError("Stage26f topology diversity mismatch")
    if render.get("physical_axis_limits_verified_for_every_panel") is not True:
        raise RuntimeError("Stage26f corrected visual limits are not verified")
    if any(value.get("candidate08_read_or_used") is not False for value in (completion, audit, render)):
        raise RuntimeError("legacy Revision3 candidate08 reserve boundary is not intact")
    output.mkdir(parents=True)
    checkpoint = {
        "schema": "lbs.stage26f-static-robust-cage-handoff.v1",
        "passed": True,
        "status": "static_geometry_campaign_verified_and_visually_reviewed",
        "verified_candidate_count": 8,
        "distinct_joint_support_topology_count": 8,
        "legacy_stage26b_revision3_candidate08_read_evaluated_or_executed": False,
        "naming_erratum": "Fields named candidate08_read_or_used in Stage26f evidence refer only to the reserved legacy Stage26b Revision3 candidate08. Stage26f cage candidate_08 is a new geometry and is unrelated.",
        "accepted_render": render["image"],
        "accepted_render_sha256": render["image_sha256"],
        "rejected_diagnostic_render": "stage26_renders/stage26f_robust_cage_placement_20260817/candidate_render_01",
        "rejected_render_reason": "After panel 1 the renderer allowed Matplotlib to mutate the shared box-aspect array, clipping panels 2-8; no numerical geometry was affected.",
        "next_stage": {
            "stage26g_fixed_fibre_design_preparation_authorized": True,
            "stage26g_yade_execution_authorized": False,
            "free_release_authorized": False,
            "rehydration_authorized": False,
            "deformation_authorized": False,
            "flow_authorized": False,
        },
        "source_hashes": {
            "config": digest(config_path),
            "campaign_completion": digest(campaign / "completion.json"),
            "candidate_index": digest(campaign / "candidate_index.csv"),
            "audit": digest(audit_path),
            "render_manifest": digest(render_path),
            "freezer": digest(Path(__file__)),
        },
        "claim_boundary": config["claim_boundary"],
    }
    with (output / "checkpoint_manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(checkpoint, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": True, "checkpoint_sha256": digest(output / "checkpoint_manifest.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
