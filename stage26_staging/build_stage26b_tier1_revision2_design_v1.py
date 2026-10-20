"""Build the immutable, design-only Stage26b Tier-1 Revision-2 schedule."""

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


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
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("immutable design output already exists")
    cfg = load_json(config_path)
    if cfg["status"] != "frozen_design_only":
        raise RuntimeError("configuration is not design-only")
    authority = cfg["authority"]
    if not authority["design_builder_execution_authorized"]:
        raise RuntimeError("design builder is not authorized")
    forbidden = [
        "network_export_execution_authorized",
        "placement_generation_authorized",
        "prefilter_yade_execution_authorized",
        "two_fibre_free_release_authorized",
        "four_fibre_execution_authorized",
        "eight_or_more_fibre_execution_authorized",
        "flow_execution_authorized",
        "deformation_coupled_flow_authorized",
        "transient_two_way_coupling_authorized",
        "production_parametric_study_authorized",
    ]
    if any(authority[name] for name in forbidden):
        raise RuntimeError("design configuration improperly authorizes execution")
    for key, text in cfg["sources"].items():
        if key.endswith("_sha256"):
            continue
        expected = cfg["sources"].get(key + "_sha256")
        if expected is None or digest(Path(text)) != expected:
            raise RuntimeError("source hash mismatch: " + key)
    failure = load_json(Path(cfg["sources"]["failure_checkpoint"]))
    if failure.get("passed") is not True or failure.get("scientific_outcome_passed") is not False:
        raise RuntimeError("frozen failure state is not verified")
    if failure["terminal_metrics"]["distinct_sand_contacts_by_fibre"] != [0, 2]:
        raise RuntimeError("unexpected failure signature")

    generation = cfg["candidate_generation"]
    rows = [
        {
            "run_order": 1,
            "record_type": "control",
            "trial_id": "positive_stage26a",
            "candidate_index": "",
            "seed": "",
            "fibre_count": 1,
            "expected_outcome": "retain_at_least_two_contacts_all_blocks",
            "selection_eligible": False,
        },
        {
            "run_order": 2,
            "record_type": "control",
            "trial_id": "negative_stage26b_failure",
            "candidate_index": "",
            "seed": "",
            "fibre_count": 2,
            "expected_outcome": "fibre_zero_loses_engagement_by_block_one",
            "selection_eligible": False,
        },
    ]
    for index in range(1, generation["candidate_count"] + 1):
        rows.append({
            "run_order": index + 2,
            "record_type": "candidate",
            "trial_id": "stage26b_f002_revision2_candidate_%02d" % index,
            "candidate_index": index,
            "seed": generation["candidate_seed_base"] + (index - 1) * generation["candidate_seed_stride"],
            "fibre_count": generation["fibre_count"],
            "expected_outcome": "unknown_predeclared",
            "selection_eligible": True,
        })
    resolved = {
        "schema": "lbs.stage26b-tier1-placement-stability-revision2-resolved-design.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "resolved_design_only_no_physics_execution",
        "research_question": cfg["research_question"],
        "trial_count": len(rows),
        "control_count": 2,
        "candidate_count": generation["candidate_count"],
        "trials": rows,
        "network_export": cfg["network_export"],
        "candidate_generation": generation,
        "prefilter": cfg["prefilter"],
        "sequential_decision": cfg["sequential_decision"],
        "frozen_physics": cfg["frozen_physics"],
        "source_hashes": {
            "config": digest(config_path),
            "builder": digest(Path(__file__)),
            "failure_checkpoint": cfg["sources"]["failure_checkpoint_sha256"],
            "stage25_checkpoint": cfg["sources"]["stage25_checkpoint_sha256"],
            "positive_control_placement": cfg["sources"]["positive_control_placement_sha256"],
            "negative_control_placement": cfg["sources"]["negative_control_placement_sha256"],
        },
        "authority": cfg["authority"],
        "claim_boundary": cfg["claim_boundary"],
    }
    output.mkdir(parents=True)
    resolved_path = output / "resolved_design.json"
    with resolved_path.open("x", encoding="utf-8") as stream:
        json.dump(resolved, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    csv_path = output / "trial_schedule.csv"
    with csv_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "schema": "lbs.stage26b-tier1-placement-stability-revision2-design-manifest.v1",
        "passed": True,
        "resolved_design_path": str(resolved_path),
        "resolved_design_sha256": digest(resolved_path),
        "trial_schedule_path": str(csv_path),
        "trial_schedule_sha256": digest(csv_path),
        "config_path": str(config_path),
        "config_sha256": digest(config_path),
        "builder_sha256": digest(Path(__file__)),
    }
    manifest_path = output / "design_manifest.json"
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": True, "manifest_sha256": digest(manifest_path), "trial_count": len(rows)}, sort_keys=True))


if __name__ == "__main__":
    main()
