"""Fail-closed one-shot held-out execution audit."""

import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
CONFIG = ROOT / "stage26_staging/stage26d_adaptive_holdout_candidate04_execution_v1.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    cfg = json.loads(CONFIG.read_text())
    trial = cfg["trials"][0]
    assert len(cfg["trials"]) == 1 and trial["candidate_index"] == 4
    assert trial["record_type"] == "candidate" and trial["stage26d_role"] == "heldout_confirmation"
    assert cfg["prefilter"]["blocks"] == 300 and cfg["prefilter"]["free_release"] is False
    assert cfg["authority"]["heldout_candidate04_execution_authorized"] is True
    assert cfg["authority"]["candidate01_development_execution_authorized"] is False
    for key, value in cfg["sources"].items():
        expected = cfg["sources"].get(key + "_sha256")
        if expected is not None:
            assert digest(value) == expected, key
    assert digest(trial["placement"]) == trial["placement_sha256"]
    handoff = json.loads(Path(cfg["sources"]["development_handoff"]).read_text())
    assert handoff["scientific_outcome_passed"] is True
    assert cfg["authority"]["two_fibre_free_release_authorized"] is False
    assert cfg["authority"]["flow_execution_authorized"] is False
    print("stage26d heldout execution audit passed")


if __name__ == "__main__":
    main()
