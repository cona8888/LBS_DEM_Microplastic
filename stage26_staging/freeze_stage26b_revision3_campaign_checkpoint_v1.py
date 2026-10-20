"""Freeze the independently verified Revision-3 campaign and selected geometry."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
EVALUATION = ROOT / "stage26_evaluations/stage26b_revision3_joint_placement_20260816/campaign_evaluation_01/evaluation.json"
AUDITOR = ROOT / "stage26_staging/audit_stage26b_revision3_campaign_v1.py"
CAMPAIGN_COMPLETION = ROOT / "stage26_placements/stage26b_revision3_joint_placement_20260816/candidate_generation_01/completion.json"
SELECTED_PLACEMENT = ROOT / "stage26_placements/stage26b_revision3_joint_placement_20260816/candidate_generation_01/stage26b_f002_revision3_candidate_01/placement.json"
OUTPUT = ROOT / "stage26_checkpoints/stage26b_revision3_joint_placement_20260816/campaign_checkpoint_01/checkpoint_manifest.json"


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


evaluation = json.loads(EVALUATION.read_text(encoding="utf-8"))
if evaluation.get("passed") is not True:
    raise RuntimeError("campaign evaluation did not pass")
if evaluation["evidence"]["campaign_completion_sha256"] != digest(CAMPAIGN_COMPLETION):
    raise RuntimeError("campaign completion changed after audit")
if evaluation["summary"]["selected_candidate_id"] != "stage26b_f002_revision3_candidate_01":
    raise RuntimeError("selected candidate changed")
manifest = {
    "schema": "lbs.stage26b-revision3-joint-placement-campaign-checkpoint.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": True,
    "status": "frozen_verified_campaign_and_selected_geometry",
    "summary": evaluation["summary"],
    "evidence": {
        "evaluation_path": str(EVALUATION), "evaluation_sha256": digest(EVALUATION),
        "auditor_path": str(AUDITOR), "auditor_sha256": digest(AUDITOR),
        "campaign_completion_path": str(CAMPAIGN_COMPLETION), "campaign_completion_sha256": digest(CAMPAIGN_COMPLETION),
        "selected_placement_path": str(SELECTED_PLACEMENT), "selected_placement_sha256": digest(SELECTED_PLACEMENT)
    },
    "authority": {
        "selection_and_render_authorized": True,
        "prefilter_yade_execution_authorized": False,
        "two_fibre_free_release_authorized": False,
        "flow_execution_authorized": False
    },
    "claim_boundary": evaluation["claim_boundary"]
}
OUTPUT.parent.mkdir(parents=True, exist_ok=False)
OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"passed": True, "checkpoint_sha256": digest(OUTPUT)}, sort_keys=True))
