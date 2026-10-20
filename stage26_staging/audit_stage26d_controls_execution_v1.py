"""Fail-closed audit for Stage26d control execution."""

import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
CONFIG = ROOT / "stage26_staging/stage26d_adaptive_controls_execution_v1.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    cfg = json.loads(CONFIG.read_text())
    assert cfg["prefilter"]["blocks"] == 300 and cfg["prefilter"]["steps_per_block"] == 500
    assert cfg["prefilter"]["all_fibres_fixed"] is True and cfg["prefilter"]["free_release"] is False
    assert cfg["adaptive_equilibration"] == {
        "maximum_blocks": 300,
        "minimum_blocks_before_equilibrium_window": 60,
        "required_consecutive_passing_blocks": 10,
    }
    assert [row["stage26d_role"] for row in cfg["trials"]] == ["positive_control", "negative_control"]
    for key, value in cfg["sources"].items():
        expected = cfg["sources"].get(key + "_sha256")
        if expected is not None:
            assert digest(value) == expected, key
    for trial in cfg["trials"]:
        assert digest(trial["placement"]) == trial["placement_sha256"]
    text = Path(cfg["sources"]["runner"]).read_text()
    assert "O.save" not in text and "saveTmp" not in text
    assert text.count('blockedDOFs = "xyzXYZ"') == 1
    assert cfg["authority"]["prefilter_yade_execution_authorized"] is True
    assert cfg["authority"]["two_fibre_free_release_authorized"] is False
    assert cfg["authority"]["flow_execution_authorized"] is False
    print("stage26d controls execution audit passed")


if __name__ == "__main__":
    main()
