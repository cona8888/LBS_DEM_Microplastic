"""Fail-closed audit of the Stage26e candidate07 held-out configuration."""

import hashlib
import json
from pathlib import Path


ROOT = Path("C:/MATDEM_MICROPLASTIC")
CONFIG = ROOT / "stage26_staging/stage26e_candidate07_heldout_capture_execution_v1.json"


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
    assert cfg["authority"]["candidate07_heldout_execution_authorized"] is True
    assert all(
        value is False for key, value in cfg["authority"].items()
        if key not in ("capture_yade_execution_authorized", "candidate07_heldout_execution_authorized")
    )
    trial, = cfg["trials"]
    assert trial["candidate_index"] == 7 and trial["stage26e_role"] == "heldout_capture"
    assert digest(Path(trial["placement"])) == trial["placement_sha256"]
    for key, value in cfg["sources"].items():
        if key.endswith("_sha256") or key == "expected_yade_version":
            continue
        expected = cfg["sources"].get(key + "_sha256")
        if expected is not None:
            assert digest(Path(value)) == expected, key
    assert cfg["sources"]["capture_runner_sha256"] == "b775ce1cacdab522ad83af83ab1043c9f16fca6b24ca3fb2d026548235ef33ed"
    assert cfg["sources"]["capture_common_sha256"] == "212145df33b037c31f02c5401c3c2cf80e821f55df32951db10e6c3d62faa768"
    assert cfg["sources"]["stage26e_development_outcome_sha256"] == "7158ebbe1f23faf5e81100cab5ebedc0dd961d58abcb4be7937d79d01a28854d"
    assert cfg["sources"]["reload_verifier_sha256"] == "e68fec49cf0c64dff1b0263f978f46292a4e5f5336826a9b9bf9dd59875941ef"
    assert cfg["sources"]["reload_semantics_erratum_sha256"] == "0f2d7df191dd10fba378acecc0263cfe7cb15416b034d5d24fe7af24d0b3bad6"
    print(json.dumps({"passed": True, "config_sha256": digest(CONFIG)}, sort_keys=True))


if __name__ == "__main__":
    main()
