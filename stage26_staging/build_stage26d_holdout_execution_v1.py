"""Build the one-shot Stage26d held-out candidate04 execution config."""

import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
BASE = ROOT / "stage26_staging/stage26d_adaptive_development_candidate01_execution_v1.json"
HANDOFF = ROOT / "stage26_checkpoints/stage26d_adaptive_equilibration_20260816/development_outcome_checkpoint_01/checkpoint_manifest.json"
PLACEMENT = ROOT / "stage26_placements/stage26d_adaptive_equilibration_20260816/holdout_01/revision3_candidate04_holdout.json"
OUTPUT = ROOT / "stage26_staging/stage26d_adaptive_holdout_candidate04_execution_v1.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    cfg = json.loads(BASE.read_text())
    handoff = json.loads(HANDOFF.read_text())
    assert handoff["passed"] is True and handoff["scientific_outcome_passed"] is True
    assert handoff["authority"]["heldout_candidate04_execution_authorized"] is True
    cfg["schema"] = "lbs.stage26d-adaptive-heldout-confirmation-execution.v1"
    cfg["claim_boundary"] = "One-shot held-out candidate04 confirmation of the frozen fixed-fibre adaptive protocol; no retuning, release, state promotion, or flow."
    cfg["sources"]["development_handoff"] = HANDOFF.as_posix()
    cfg["sources"]["development_handoff_sha256"] = digest(HANDOFF)
    placement = json.loads(PLACEMENT.read_text())
    assert placement["candidate"]["candidate_index"] == 4
    cfg["trials"] = [{
        "trial_id": "revision3_candidate04_heldout",
        "record_type": "candidate",
        "stage26d_role": "heldout_confirmation",
        "candidate_index": 4,
        "fibre_count": 2,
        "minimum_anchor_degree": 3,
        "placement": PLACEMENT.as_posix(),
        "placement_sha256": digest(PLACEMENT),
    }]
    cfg["authority"]["candidate01_development_execution_authorized"] = False
    cfg["authority"]["heldout_candidate04_execution_authorized"] = True
    OUTPUT.open("x").write(json.dumps(cfg, indent=2, sort_keys=True) + "\n")
    print(digest(OUTPUT))


if __name__ == "__main__":
    main()
