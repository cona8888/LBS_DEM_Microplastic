"""Evaluate all frozen Revision-2 prefilter outcomes and select by frozen rank."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from stage26b_revision2_prefilter_common_v1 import candidate_rank_key


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
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    run_root = Path(args.run_root).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("immutable selector output already exists")
    cfg = load_json(config_path)
    if cfg.get("status") != "authorized_stage26b_revision2_fixed_prefilter":
        raise RuntimeError("configuration is not the frozen prefilter execution config")
    if cfg["authority"].get("prefilter_yade_execution_authorized") is not True:
        raise RuntimeError("prefilter execution was not authorized")
    forbidden = (
        "two_fibre_free_release_authorized", "four_fibre_execution_authorized",
        "eight_or_more_fibre_execution_authorized", "flow_execution_authorized",
        "deformation_coupled_flow_authorized", "transient_two_way_coupling_authorized",
        "production_parametric_study_authorized",
    )
    if any(cfg["authority"].get(name, False) for name in forbidden):
        raise RuntimeError("execution configuration exceeds prefilter authority")
    trials = cfg["trials"]
    if len(trials) != 14 or [row["trial_id"] for row in trials[:2]] != ["positive_stage26a", "negative_stage26b_failure"]:
        raise RuntimeError("trial schedule does not contain the frozen 2-control plus 12-candidate design")

    outcomes = []
    for trial in trials:
        trial_root = run_root / trial["trial_id"]
        completion_path = trial_root / "completion.json"
        result_path = trial_root / "result.json"
        if not completion_path.is_file() or not result_path.is_file() or (trial_root / "failure.json").exists():
            raise RuntimeError("missing, incomplete, or failed prefilter trial: " + trial["trial_id"])
        completion = load_json(completion_path)
        result = load_json(result_path)
        if completion.get("passed") is not True or result.get("passed") is not True:
            raise RuntimeError("prefilter trial did not complete technically: " + trial["trial_id"])
        if completion["result_sha256"] != digest(result_path):
            raise RuntimeError("completion/result hash mismatch: " + trial["trial_id"])
        if result["trial"]["trial_id"] != trial["trial_id"] or result["trial"]["run_order"] != trial["run_order"]:
            raise RuntimeError("trial identity mismatch: " + trial["trial_id"])
        if result["protocol"] != {
            "all_fibres_fixed": True,
            "free_release": False,
            "steps_per_block": 500,
            "blocks": 10,
        }:
            raise RuntimeError("unexpected prefilter protocol: " + trial["trial_id"])
        outcomes.append({
            "trial": trial,
            "completion_path": str(completion_path),
            "completion_sha256": digest(completion_path),
            "result_path": str(result_path),
            "result_sha256": digest(result_path),
            "control_reproduced": result["control_reproduced"],
            "candidate_passed_prefilter": result["candidate_passed_prefilter"],
            "prefilter_summary": result["prefilter_summary"],
        })

    positive_ok = outcomes[0]["control_reproduced"] is True
    negative_ok = outcomes[1]["control_reproduced"] is True
    controls_ok = positive_ok and negative_ok
    candidates = [row for row in outcomes if row["trial"]["record_type"] == "candidate"]
    passing = [row for row in candidates if row["candidate_passed_prefilter"] is True]
    passing.sort(key=lambda row: candidate_rank_key(row["prefilter_summary"]))
    selected = passing[0] if controls_ok and passing else None
    evaluation = {
        "schema": "lbs.stage26b-revision2-prefilter-selection-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": controls_ok and selected is not None,
        "status": (
            "passed_controls_and_selected_prefilter_candidate" if controls_ok and selected is not None
            else "failed_controls_no_selection" if not controls_ok
            else "controls_passed_no_candidate_passed"
        ),
        "both_controls_reproduced": controls_ok,
        "positive_control_reproduced": positive_ok,
        "negative_control_reproduced": negative_ok,
        "trial_count": len(outcomes),
        "candidate_count": len(candidates),
        "passing_candidate_count": len(passing),
        "selected_trial": selected["trial"] if selected else None,
        "selected_prefilter_summary": selected["prefilter_summary"] if selected else None,
        "outcomes": outcomes,
        "source_hashes": {
            "config": digest(config_path),
            "selector": digest(Path(__file__)),
        },
        "authority": {
            "independent_source_and_visual_audit_authorized": selected is not None,
            "two_fibre_free_release_authorized": False,
            "four_fibre_execution_authorized": False,
            "eight_or_more_fibre_execution_authorized": False,
            "flow_execution_authorized": False,
            "deformation_coupled_flow_authorized": False,
            "transient_two_way_coupling_authorized": False,
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    output.mkdir(parents=True)
    path = output / "evaluation.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({
        "passed": evaluation["passed"],
        "status": evaluation["status"],
        "selected_trial_id": selected["trial"]["trial_id"] if selected else None,
        "evaluation_sha256": digest(path),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
