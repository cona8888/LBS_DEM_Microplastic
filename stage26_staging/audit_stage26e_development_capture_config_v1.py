"""Fail-closed audit of the Stage26e candidate05 development capture config."""

import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
CONFIG = ROOT / "stage26_staging/stage26e_candidate05_development_capture_execution_v2.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert cfg["status"] == "authorized_stage26e_fixed_capture"
    assert cfg["capture_protocol"]["all_fibres_fixed"] is True
    assert cfg["capture_protocol"]["free_release"] is False
    assert cfg["capture_protocol"]["save_on_first_qualifying_window_only"] is True
    assert cfg["adaptive_equilibration"] == {
        "maximum_blocks": 300,
        "minimum_blocks_before_equilibrium_window": 60,
        "required_consecutive_passing_blocks": 10,
    }
    assert cfg["authority"]["capture_yade_execution_authorized"] is True
    assert all(value is False for key, value in cfg["authority"].items() if key != "capture_yade_execution_authorized")
    trial, = cfg["trials"]
    assert trial["candidate_index"] == 5 and trial["stage26e_role"] == "development_capture"
    assert digest(Path(trial["placement"])) == trial["placement_sha256"]
    for key, value in cfg["sources"].items():
        if key.endswith("_sha256") or key == "expected_yade_version":
            continue
        expected = cfg["sources"].get(key + "_sha256")
        if expected is not None:
            assert digest(Path(value)) == expected, key
    assert cfg["sources"]["capture_runner_sha256"] == "5fb877785649b22bd402abfd40af69c8df04969a4490cf71676f2988bf7ab5f6"
    assert cfg["sources"]["capture_common_sha256"] == "212145df33b037c31f02c5401c3c2cf80e821f55df32951db10e6c3d62faa768"
    print(json.dumps({"passed": True, "config_sha256": digest(CONFIG)}, sort_keys=True))


if __name__ == "__main__":
    main()
