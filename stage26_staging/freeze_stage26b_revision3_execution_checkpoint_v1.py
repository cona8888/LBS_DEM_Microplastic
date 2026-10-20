"""Freeze the audited exact Revision-3 execution handoff."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
CONFIG = ROOT / "stage26_staging/stage26b_revision3_joint_placement_execution_v1.json"
AUDITOR = ROOT / "stage26_staging/audit_stage26b_revision3_execution_v1.py"
EVALUATION = ROOT / "stage26_evaluations/stage26b_revision3_joint_placement_20260816/execution_evaluation_01/evaluation.json"
OUTPUT = ROOT / "stage26_checkpoints/stage26b_revision3_joint_placement_20260816/execution_checkpoint_01/checkpoint_manifest.json"


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


evaluation = json.loads(EVALUATION.read_text(encoding="utf-8"))
if evaluation.get("passed") is not True:
    raise RuntimeError("execution audit did not pass")
if evaluation["evidence"]["config_sha256"] != digest(CONFIG):
    raise RuntimeError("execution config changed after audit")
cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
manifest = {
    "schema": "lbs.stage26b-revision3-joint-placement-execution-checkpoint.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": True,
    "status": "frozen_authorized_revision3_joint_placement_execution",
    "evidence": {
        "config_path": str(CONFIG), "config_sha256": digest(CONFIG),
        "auditor_path": str(AUDITOR), "auditor_sha256": digest(AUDITOR),
        "evaluation_path": str(EVALUATION), "evaluation_sha256": digest(EVALUATION),
        "generator_path": cfg["sources"]["generator"], "generator_sha256": cfg["sources"]["generator_sha256"],
        "generator_source_checkpoint": cfg["sources"]["generator_source_checkpoint"],
        "generator_source_checkpoint_sha256": cfg["sources"]["generator_source_checkpoint_sha256"]
    },
    "execution": cfg["execution"],
    "authority": {"placement_generation_authorized": True, "prefilter_yade_execution_authorized": False},
    "claim_boundary": cfg["claim_boundary"]
}
OUTPUT.parent.mkdir(parents=True, exist_ok=False)
OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"passed": True, "checkpoint_sha256": digest(OUTPUT)}, sort_keys=True))
