"""Freeze the verified Stage26c control-gate failure."""

import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
EVALUATION = ROOT / "stage26_evaluations/stage26c_revision3_fixed_prefilter_20260816/controls_outcome_evaluation_01/evaluation.json"
AUDITOR = ROOT / "stage26_staging/evaluate_stage26c_controls_v1.py"
OUTPUT = ROOT / "stage26_checkpoints/stage26c_revision3_fixed_prefilter_20260816/control_failure_checkpoint_01/checkpoint_manifest.json"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


evaluation = json.loads(EVALUATION.read_text(encoding="utf-8"))
if evaluation.get("passed") is not True or evaluation.get("scientific_outcome_passed") is not False:
    raise RuntimeError("control failure evaluation is not verified")
manifest = {"schema": "lbs.stage26c-fixed-prefilter-control-failure-checkpoint.v1", "passed": True, "scientific_outcome_passed": False, "status": "frozen_verified_positive_control_persistence_failure", "diagnosis": evaluation["diagnosis"], "records": evaluation["records"], "evidence": {"evaluation_path": str(EVALUATION), "evaluation_sha256": digest(EVALUATION), "auditor_path": str(AUDITOR), "auditor_sha256": digest(AUDITOR)}, "authority": {"prefilter_redesign_authorized": True, "candidate_yade_execution_authorized": False, "two_fibre_free_release_authorized": False, "flow_execution_authorized": False}, "claim_boundary": evaluation["claim_boundary"]}
OUTPUT.parent.mkdir(parents=True, exist_ok=False)
OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"passed": True, "checkpoint_sha256": digest(OUTPUT)}, sort_keys=True))
