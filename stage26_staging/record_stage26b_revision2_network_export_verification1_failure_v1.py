"""Preserve the over-strict first independent verification failure."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
EVALUATION = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260816" / "network_export_evaluation_01" / "evaluation.json"
VERIFIER = PROJECT / "stage26_staging" / "verify_stage26b_revision2_stage25_network_export_v1.py"
OUTPUT = PROJECT / "stage26_failures" / "stage26b_revision2_stage25_network_20260816" / "verification_01"


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
        raise RuntimeError("immutable verification-failure record already exists")
    evaluation = load_json(EVALUATION)
    failed = [name for name, passed in evaluation["checks"].items() if not passed]
    confirmed = (
        evaluation.get("passed") is False
        and failed == ["derived_particle_fields_exact"]
        and evaluation["independent_summary"]["degree2_load_bearing_core_count"] == 175
        and evaluation["evidence"]["verifier_sha256"] == digest(VERIFIER)
    )
    failure = {
        "schema": "lbs.stage26b-revision2-network-export-verification-failure.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": False,
        "status": "failed_over_strict_binary_float_equality",
        "failure_classification": "verifier_tolerance_defect_not_export_defect",
        "failed_checks": failed,
        "diagnosis": "Re-summing JSON-decoded contact forces differs from YADE-Python exporter sums by at most a few binary floating-point ulps; topology, artifact hashes, CSV-to-JSON rows, source bindings, force validity, and core count passed.",
        "evidence": {
            "evaluation_path": str(EVALUATION), "evaluation_sha256": digest(EVALUATION),
            "verifier_path": str(VERIFIER), "verifier_sha256": digest(VERIFIER),
        },
        "authority": {
            "tolerance_corrected_reverification_authorized": confirmed,
            "network_export_rerun_authorized": False,
            "placement_generation_authorized": False,
            "prefilter_yade_execution_authorized": False,
            "flow_execution_authorized": False,
        },
        "claim_boundary": "Verification-method failure only; the immutable YADE export is not rerun or modified.",
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "failure.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(failure, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": False, "confirmed": confirmed, "failure_sha256": digest(path)}, sort_keys=True))
    if not confirmed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
