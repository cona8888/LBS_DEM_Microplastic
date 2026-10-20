"""Build exact Stage26d candidate01 development execution config."""

import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
BASE = ROOT / "stage26_staging/stage26d_adaptive_controls_execution_v1.json"
CONTROL = ROOT / "stage26_checkpoints/stage26d_adaptive_equilibration_20260816/control_requalification_checkpoint_01/checkpoint_manifest.json"
PLACEMENT = ROOT / "stage26_placements/stage26c_revision3_fixed_prefilter_20260816/normalized_01/revision3_candidate01.json"
OUTPUT = ROOT / "stage26_staging/stage26d_adaptive_development_candidate01_execution_v1.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    cfg = json.loads(BASE.read_text())
    controls = json.loads(CONTROL.read_text())
    assert controls["passed"] is True and controls["both_controls_reproduced"] is True
    cfg["schema"] = "lbs.stage26d-adaptive-development-execution.v1"
    cfg["claim_boundary"] = "Candidate01 development evaluation of the frozen fixed-fibre adaptive protocol only; no independent confirmation, release, state promotion, or flow."
    cfg["sources"]["control_checkpoint"] = CONTROL.as_posix()
    cfg["sources"]["control_checkpoint_sha256"] = digest(CONTROL)
    placement = json.loads(PLACEMENT.read_text())
    cfg["trials"] = [{
        "trial_id": "revision3_candidate01_development",
        "record_type": "candidate",
        "stage26d_role": "development",
        "candidate_index": 1,
        "fibre_count": 2,
        "minimum_anchor_degree": 3,
        "placement": PLACEMENT.as_posix(),
        "placement_sha256": digest(PLACEMENT),
    }]
    cfg["authority"]["candidate01_development_execution_authorized"] = True
    OUTPUT.open("x").write(json.dumps(cfg, indent=2, sort_keys=True) + "\n")
    print(digest(OUTPUT))


if __name__ == "__main__":
    main()
