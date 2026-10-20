"""Freeze the audited Revision-3 render-02 source."""

import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
SOURCE = ROOT / "stage26_staging/render_stage26b_revision3_selected_geometry_v2.py"
AUDITOR = ROOT / "stage26_staging/audit_stage26b_revision3_renderer_v2.py"
EVALUATION = ROOT / "stage26_evaluations/stage26b_revision3_joint_placement_20260816/renderer_source_evaluation_02/evaluation.json"
OUTPUT = ROOT / "stage26_checkpoints/stage26b_revision3_joint_placement_20260816/renderer_source_checkpoint_02/checkpoint_manifest.json"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


evaluation = json.loads(EVALUATION.read_text(encoding="utf-8"))
if evaluation.get("passed") is not True or evaluation["evidence"]["source_sha256"] != digest(SOURCE):
    raise RuntimeError("render-02 source audit binding failed")
manifest = {"schema": "lbs.stage26b-revision3-render02-source-checkpoint.v1", "passed": True, "status": "frozen_audited_unambiguous_renderer_source", "evidence": {"source_path": str(SOURCE), "source_sha256": digest(SOURCE), "auditor_path": str(AUDITOR), "auditor_sha256": digest(AUDITOR), "evaluation_path": str(EVALUATION), "evaluation_sha256": digest(EVALUATION), "base_renderer_path": evaluation["evidence"]["base_renderer_path"], "base_renderer_sha256": evaluation["evidence"]["base_renderer_sha256"]}, "authority": {"render_execution_authorized": True, "prefilter_yade_execution_authorized": False}, "claim_boundary": evaluation["claim_boundary"]}
OUTPUT.parent.mkdir(parents=True, exist_ok=False)
OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"passed": True, "checkpoint_sha256": digest(OUTPUT)}, sort_keys=True))
