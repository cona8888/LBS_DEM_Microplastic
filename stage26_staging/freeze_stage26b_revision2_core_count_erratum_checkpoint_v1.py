"""Freeze the audited Stage25 core-count erratum."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
EVALUATION = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260816" / "core_count_erratum_evaluation_01" / "evaluation.json"
OUTPUT = PROJECT / "stage26_checkpoints" / "stage26b_tier1_placement_stability_revision2_20260816" / "core_count_erratum_checkpoint_01"


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
        raise RuntimeError("immutable erratum checkpoint already exists")
    evaluation = load_json(EVALUATION)
    if evaluation.get("passed") is not True or evaluation.get("status") != "passed_evidence_bound_core_count_erratum":
        raise RuntimeError("erratum evaluation is not accepted")
    for name in ("erratum", "attempt2_failure", "stage25_result", "prior_contacts", "prior_completion", "exporter", "common"):
        path = Path(evaluation["evidence"][name + "_path"])
        if digest(path) != evaluation["evidence"][name + "_sha256"]:
            raise RuntimeError(name + " evidence hash mismatch")
    checkpoint = {
        "schema": "lbs.stage26b-revision2-stage25-core-count-erratum-checkpoint.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "frozen_evidence_bound_stage25_core_count_175",
        "corrected_gate": {
            "required_load_bearing_particle_count": 175,
            "core_degree_threshold": 2,
            "particle_count": 216,
            "real_contact_count": 361,
        },
        "evidence": {
            "evaluation_path": str(EVALUATION), "evaluation_sha256": digest(EVALUATION),
            "erratum_path": evaluation["evidence"]["erratum_path"], "erratum_sha256": evaluation["evidence"]["erratum_sha256"],
            "attempt2_failure_path": evaluation["evidence"]["attempt2_failure_path"], "attempt2_failure_sha256": evaluation["evidence"]["attempt2_failure_sha256"],
            "stage25_result_path": evaluation["evidence"]["stage25_result_path"], "stage25_result_sha256": evaluation["evidence"]["stage25_result_sha256"],
            "prior_contacts_path": evaluation["evidence"]["prior_contacts_path"], "prior_contacts_sha256": evaluation["evidence"]["prior_contacts_sha256"],
            "freezer_sha256": digest(Path(__file__)),
        },
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
