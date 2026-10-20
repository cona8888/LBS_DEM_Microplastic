"""Fail-closed source and configuration audit for Stage26c temporal controls."""

import ast
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "stage26_staging/stage26c_fixed_prefilter_controls_execution_v2.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cfg = json.loads(CONFIG.read_text())
    runner = Path(cfg["sources"]["runner"])
    text = runner.read_text()
    ast.parse(text)
    assert cfg["prefilter"] == {
        "all_fibres_fixed": True,
        "free_release": False,
        "steps_per_block": 500,
        "blocks": 60,
        "maximum_strain_rate_s_inv": 0.02,
    }
    assert cfg["temporal_contact_gates"]["terminal_window_blocks_inclusive"] == [51, 60]
    assert "O.load(" in text and "O.run(" in text
    assert "O.save" not in text and "saveTmp" not in text
    assert text.count('blockedDOFs = "xyzXYZ"') == 1
    assert cfg["authority"]["prefilter_yade_execution_authorized"] is True
    assert all(
        not cfg["authority"][key]
        for key in cfg["authority"]
        if key != "prefilter_yade_execution_authorized"
    )
    for key, value in cfg["sources"].items():
        expected = cfg["sources"].get(key + "_sha256")
        if expected is not None:
            assert digest(Path(value)) == expected, key
    for trial in cfg["trials"]:
        assert digest(Path(trial["placement"])) == trial["placement_sha256"]
    print("stage26c v2 source/config audit passed")


if __name__ == "__main__":
    main()
