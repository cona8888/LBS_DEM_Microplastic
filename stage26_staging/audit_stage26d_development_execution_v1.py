"""Fail-closed audit for exact Stage26d candidate01 development run."""

import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
CONFIG = ROOT / "stage26_staging/stage26d_adaptive_development_candidate01_execution_v1.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    cfg = json.loads(CONFIG.read_text())
    assert cfg["prefilter"]["blocks"] == 300 and cfg["prefilter"]["free_release"] is False
    assert len(cfg["trials"]) == 1
    trial = cfg["trials"][0]
    assert trial["trial_id"] == "revision3_candidate01_development"
    assert trial["record_type"] == "candidate" and trial["stage26d_role"] == "development"
    controls = json.loads(Path(cfg["sources"]["control_checkpoint"]).read_text())
    assert controls["passed"] is True and controls["both_controls_reproduced"] is True
    for key, value in cfg["sources"].items():
        expected = cfg["sources"].get(key + "_sha256")
        if expected is not None:
            assert digest(value) == expected, key
    assert digest(trial["placement"]) == trial["placement_sha256"]
    text = Path(cfg["sources"]["runner"]).read_text()
    assert "O.save" not in text and "saveTmp" not in text
    assert cfg["authority"]["two_fibre_free_release_authorized"] is False
    assert cfg["authority"]["flow_execution_authorized"] is False
    print("stage26d development execution audit passed")


if __name__ == "__main__":
    main()
