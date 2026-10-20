"""Freeze revised attempt-2 read-only network-export authority."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
EVALUATION = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260816" / "network_export_prerun_audit_03" / "evaluation.json"
OUTPUT = PROJECT / "stage26_checkpoints" / "stage26b_tier1_placement_stability_revision2_20260816" / "network_export_prerun_checkpoint_02"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable revised pre-run checkpoint already exists")
    evaluation = load_json(EVALUATION)
    if evaluation.get("passed") is not True or evaluation.get("status") != "passed_revised_exact_read_only_export_prerun_audit":
        raise RuntimeError("revised pre-run audit is not accepted")
    for name in ("config", "launcher", "exporter", "source_checkpoint", "attempt1_failure"):
        path = Path(evaluation["evidence"][name + "_path"])
        if digest(path) != evaluation["evidence"][name + "_sha256"]:
            raise RuntimeError(name + " evidence hash mismatch")
    checkpoint = {
        "schema": "lbs.stage26b-revision2-network-export-prerun-checkpoint.v2",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "frozen_revised_exact_read_only_network_export_authority",
        "evidence": {
            "evaluation_path": str(EVALUATION), "evaluation_sha256": digest(EVALUATION),
            "config_path": evaluation["evidence"]["config_path"], "config_sha256": evaluation["evidence"]["config_sha256"],
            "launcher_path": evaluation["evidence"]["launcher_path"], "launcher_sha256": evaluation["evidence"]["launcher_sha256"],
            "exporter_path": evaluation["evidence"]["exporter_path"], "exporter_sha256": evaluation["evidence"]["exporter_sha256"],
            "attempt1_failure_path": evaluation["evidence"]["attempt1_failure_path"],
            "attempt1_failure_sha256": evaluation["evidence"]["attempt1_failure_sha256"],
            "freezer_sha256": digest(Path(__file__)),
        },
        "frozen_execution": evaluation["frozen_execution"],
        "authority": evaluation["authority"],
        "claim_boundary": evaluation["claim_boundary"],
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "checkpoint_manifest.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(checkpoint, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": True, "checkpoint_sha256": digest(path)}, sort_keys=True))


if __name__ == "__main__":
    main()
