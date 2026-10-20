"""Fail-closed audit of the exact Stage26c Revision-3 candidate01 execution."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "stage26_staging/stage26c_fixed_prefilter_candidate01_execution_v2.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cfg = json.loads(CONFIG.read_text())
    assert cfg["prefilter"]["all_fibres_fixed"] is True
    assert cfg["prefilter"]["free_release"] is False
    assert cfg["prefilter"]["blocks"] == 60
    assert cfg["prefilter"]["steps_per_block"] == 500
    assert cfg["temporal_contact_gates"]["terminal_window_blocks_inclusive"] == [51, 60]
    assert len(cfg["trials"]) == 1
    trial = cfg["trials"][0]
    assert trial["trial_id"] == "revision3_candidate01"
    assert trial["record_type"] == "candidate" and trial["fibre_count"] == 2
    assert cfg["authority"]["prefilter_yade_execution_authorized"] is True
    assert cfg["authority"]["candidate01_fixed_prefilter_execution_authorized"] is True
    forbidden = [
        "two_fibre_free_release_authorized", "four_fibre_execution_authorized",
        "eight_or_more_fibre_execution_authorized", "flow_execution_authorized",
        "deformation_coupled_flow_authorized", "transient_two_way_coupling_authorized",
        "production_parametric_study_authorized",
    ]
    assert all(cfg["authority"][name] is False for name in forbidden)
    for key, value in cfg["sources"].items():
        expected = cfg["sources"].get(key + "_sha256")
        if expected is not None:
            assert digest(Path(value)) == expected, key
    assert digest(Path(trial["placement"])) == trial["placement_sha256"]
    controls = json.loads(Path(cfg["sources"]["control_checkpoint"]).read_text())
    assert controls["passed"] is True and controls["both_controls_reproduced"] is True
    runner_text = Path(cfg["sources"]["runner"]).read_text()
    assert "O.save" not in runner_text and "saveTmp" not in runner_text
    assert runner_text.count('blockedDOFs = "xyzXYZ"') == 1
    print("stage26c candidate01 execution audit passed")


if __name__ == "__main__":
    main()
