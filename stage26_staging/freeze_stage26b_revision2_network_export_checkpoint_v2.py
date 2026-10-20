"""Freeze the tolerance-corrected verified Stage25 network export."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
EVALUATION = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260816" / "network_export_evaluation_02" / "evaluation.json"
OUTPUT = PROJECT / "stage26_checkpoints" / "stage26b_tier1_placement_stability_revision2_20260816" / "network_export_checkpoint_01"


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
        raise RuntimeError("immutable verified network-export checkpoint already exists")
    evaluation = load_json(EVALUATION)
    if evaluation.get("passed") is not True or evaluation.get("status") != "passed_tolerance_corrected_exact_network_export_verification":
        raise RuntimeError("corrected network-export evaluation is not accepted")
    for name in ("network", "particles_csv", "contacts_csv", "completion", "config", "prerun_checkpoint", "first_evaluation", "first_failure"):
        path = Path(evaluation["evidence"][name + "_path"])
        if digest(path) != evaluation["evidence"][name + "_sha256"]:
            raise RuntimeError(name + " evidence hash mismatch")
    checkpoint = {
        "schema": "lbs.stage26b-revision2-stage25-network-export-checkpoint.v2",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "frozen_verified_exact_stage25_network_export",
        "verified_summary": evaluation["independent_summary"],
        "tolerance_audit": evaluation["tolerance_audit"],
        "evidence": dict(evaluation["evidence"], evaluation_path=str(EVALUATION), evaluation_sha256=digest(EVALUATION), freezer_sha256=digest(Path(__file__))),
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
