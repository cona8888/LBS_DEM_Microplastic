"""Freeze the audited Stage26c control execution handoff."""

import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
CONFIG = ROOT / "stage26_staging/stage26c_fixed_prefilter_controls_execution_v1.json"
EVALUATION = ROOT / "stage26_evaluations/stage26c_revision3_fixed_prefilter_20260816/controls_execution_evaluation_01/evaluation.json"
AUDITOR = ROOT / "stage26_staging/audit_stage26c_controls_execution_v1.py"
OUTPUT = ROOT / "stage26_checkpoints/stage26c_revision3_fixed_prefilter_20260816/controls_execution_checkpoint_01/checkpoint_manifest.json"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


evaluation = json.loads(EVALUATION.read_text(encoding="utf-8"))
if evaluation.get("passed") is not True or evaluation["config_sha256"] != digest(CONFIG):
    raise RuntimeError("control execution audit binding failed")
manifest = {"schema": "lbs.stage26c-controls-execution-checkpoint.v1", "passed": True, "status": "frozen_authorized_two_control_fixed_prefilter", "evidence": {"config_path": str(CONFIG), "config_sha256": digest(CONFIG), "evaluation_path": str(EVALUATION), "evaluation_sha256": digest(EVALUATION), "auditor_path": str(AUDITOR), "auditor_sha256": digest(AUDITOR)}, "authority": {"controls_yade_execution_authorized": True, "candidate_yade_execution_authorized": False, "two_fibre_free_release_authorized": False, "flow_execution_authorized": False}}
OUTPUT.parent.mkdir(parents=True, exist_ok=False)
OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"passed": True, "checkpoint_sha256": digest(OUTPUT)}, sort_keys=True))
