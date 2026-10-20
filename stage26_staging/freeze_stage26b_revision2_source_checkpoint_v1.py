"""Freeze the independently audited Stage26b Revision-2 source bundle."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
EVALUATION = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260816" / "source_audit_02" / "evaluation.json"
OUTPUT = PROJECT / "stage26_checkpoints" / "stage26b_tier1_placement_stability_revision2_20260816" / "source_checkpoint_02"


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
        raise RuntimeError("immutable source checkpoint already exists")
    evaluation = load_json(EVALUATION)
    if evaluation.get("passed") is not True or evaluation.get("status") != "passed_source_audit_without_yade_execution":
        raise RuntimeError("source audit is not accepted")
    for name, expected in evaluation["source_hashes"].items():
        if name == "auditor":
            path = PROJECT / "stage26_staging" / "audit_stage26b_revision2_prefilter_sources_v1.py"
        elif name == "interface":
            path = PROJECT / "stage26_staging" / "stage26b_tier1_revision2_source_interface_v1.json"
        elif name == "common":
            path = PROJECT / "stage26_staging" / "stage26b_revision2_prefilter_common_v1.py"
        elif name == "network_exporter":
            path = PROJECT / "stage26_staging" / "export_stage26b_revision2_stage25_network_v1.py"
        elif name == "fixed_prefilter_runner":
            path = PROJECT / "stage26_staging" / "run_stage26b_revision2_fixed_prefilter_v1.py"
        elif name == "selector":
            path = PROJECT / "stage26_staging" / "select_stage26b_revision2_prefilter_candidate_v1.py"
        elif name == "unit_tests":
            path = PROJECT / "stage26_staging" / "test_stage26b_revision2_prefilter_common_v1.py"
        else:
            raise RuntimeError("unknown audited source: " + name)
        if digest(path) != expected:
            raise RuntimeError(name + " source hash mismatch")
    checkpoint = {
        "schema": "lbs.stage26b-tier1-revision2-source-checkpoint.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "frozen_audited_sources_no_yade_execution",
        "evidence": {
            "evaluation_path": str(EVALUATION),
            "evaluation_sha256": digest(EVALUATION),
            "source_hashes": evaluation["source_hashes"],
            "freezer_sha256": digest(Path(__file__)),
        },
        "interfaces": evaluation["interfaces"],
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
