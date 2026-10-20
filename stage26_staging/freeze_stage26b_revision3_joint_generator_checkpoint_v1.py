"""Freeze the independently audited Revision-3 generator source."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
SOURCE = ROOT / "stage26_staging/generate_stage26b_revision3_joint_placements_v1.py"
AUDITOR = ROOT / "stage26_staging/audit_stage26b_revision3_joint_generator_v1.py"
EVALUATION = ROOT / "stage26_evaluations/stage26b_revision3_joint_placement_20260816/generator_source_evaluation_02/evaluation.json"
DESIGN_CHECKPOINT = ROOT / "stage26_checkpoints/stage26b_revision3_joint_placement_20260816/design_checkpoint_01/checkpoint_manifest.json"
OUTPUT = ROOT / "stage26_checkpoints/stage26b_revision3_joint_placement_20260816/generator_source_checkpoint_01/checkpoint_manifest.json"


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


evaluation = json.loads(EVALUATION.read_text(encoding="utf-8"))
if evaluation.get("passed") is not True:
    raise RuntimeError("generator source evaluation did not pass")
if evaluation["observed"]["source_sha256"] != digest(SOURCE):
    raise RuntimeError("generator source changed after audit")
manifest = {
    "schema": "lbs.stage26b-revision3-joint-generator-source-checkpoint.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": True,
    "status": "frozen_audited_revision3_generator_source",
    "evidence": {
        "source_path": str(SOURCE),
        "source_sha256": digest(SOURCE),
        "auditor_path": str(AUDITOR),
        "auditor_sha256": digest(AUDITOR),
        "evaluation_path": str(EVALUATION),
        "evaluation_sha256": digest(EVALUATION),
        "design_checkpoint_path": str(DESIGN_CHECKPOINT),
        "design_checkpoint_sha256": digest(DESIGN_CHECKPOINT),
    },
    "authority": {
        "execution_config_preparation_authorized": True,
        "placement_generation_authorized": False,
        "prefilter_yade_execution_authorized": False,
    },
    "claim_boundary": evaluation["claim_boundary"],
}
OUTPUT.parent.mkdir(parents=True, exist_ok=False)
OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"passed": True, "checkpoint_sha256": digest(OUTPUT)}, sort_keys=True))
