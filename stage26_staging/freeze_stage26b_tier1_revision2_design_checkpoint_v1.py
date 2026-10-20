"""Freeze the independently audited Stage26b Tier-1 Revision-2 design checkpoint."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
EVALUATION = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260814" / "design_evaluation_02" / "evaluation.json"
OUTPUT = PROJECT / "stage26_checkpoints" / "stage26b_tier1_placement_stability_revision2_20260814" / "design_checkpoint_01"


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
        raise RuntimeError("immutable design checkpoint already exists")
    evaluation = load_json(EVALUATION)
    if evaluation.get("passed") is not True or evaluation.get("status") != "passed_design_audit_no_physics_execution":
        raise RuntimeError("design evaluation is not accepted")
    for name in ("config", "design_manifest", "resolved_design", "trial_schedule"):
        path = Path(evaluation["evidence"][name + "_path"])
        if digest(path) != evaluation["evidence"][name + "_sha256"]:
            raise RuntimeError(name + " evidence hash mismatch")
    checkpoint = {
        "schema": "lbs.stage26b-tier1-placement-stability-revision2-design-checkpoint.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "frozen_revision2_design_no_physics_execution",
        "design_summary": evaluation["design_summary"],
        "evidence": {
            "evaluation_path": str(EVALUATION),
            "evaluation_sha256": digest(EVALUATION),
            "config_path": evaluation["evidence"]["config_path"],
            "config_sha256": evaluation["evidence"]["config_sha256"],
            "resolved_design_path": evaluation["evidence"]["resolved_design_path"],
            "resolved_design_sha256": evaluation["evidence"]["resolved_design_sha256"],
            "trial_schedule_path": evaluation["evidence"]["trial_schedule_path"],
            "trial_schedule_sha256": evaluation["evidence"]["trial_schedule_sha256"],
            "freezer_sha256": digest(Path(__file__)),
        },
        "authority": evaluation["authority"],
        "claim_boundary": evaluation["claim_boundary"],
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "checkpoint_manifest.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(checkpoint, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": True, "checkpoint_sha256": digest(path)}, sort_keys=True))


if __name__ == "__main__":
    main()
