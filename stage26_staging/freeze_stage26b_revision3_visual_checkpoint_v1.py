"""Freeze the hash-verified visual prefilter handoff."""

import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
REVIEW = ROOT / "stage26_evaluations/stage26b_revision3_joint_placement_20260816/visual_review_01/evaluation.json"
OUTPUT = ROOT / "stage26_checkpoints/stage26b_revision3_joint_placement_20260816/visual_checkpoint_01/checkpoint_manifest.json"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


review = json.loads(REVIEW.read_text(encoding="utf-8"))
if review.get("passed") is not True:
    raise RuntimeError("visual review did not pass")
for name in ("image", "render_manifest", "renderer_source_checkpoint", "campaign_checkpoint"):
    if digest(review["evidence"][name + "_path"]) != review["evidence"][name + "_sha256"]:
        raise RuntimeError("visual evidence hash mismatch: " + name)
manifest = {"schema": "lbs.stage26b-revision3-visual-prefilter-checkpoint.v1", "passed": True, "status": "frozen_visual_prefilter_handoff", "selected_candidate_id": review["selected_candidate_id"], "visual_findings": review["visual_findings"], "evidence": {**review["evidence"], "visual_review_path": str(REVIEW), "visual_review_sha256": digest(REVIEW)}, "authority": {"prefilter_design_authorized": True, "prefilter_yade_execution_authorized": False, "two_fibre_free_release_authorized": False, "flow_execution_authorized": False}, "claim_boundary": review["claim_boundary"]}
OUTPUT.parent.mkdir(parents=True, exist_ok=False)
OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"passed": True, "checkpoint_sha256": digest(OUTPUT)}, sort_keys=True))
