"""Preserve attempt-3 pre-load configuration-status failure."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = PROJECT / "stage26_staging" / "stage26b_revision2_network_export_execution_v3.json"
PRERUN = PROJECT / "stage26_checkpoints" / "stage26b_tier1_placement_stability_revision2_20260816" / "network_export_prerun_checkpoint_03" / "checkpoint_manifest.json"
EXPORTER = PROJECT / "stage26_staging" / "export_stage26b_revision2_stage25_network_v1.py"
TARGET = PROJECT / "stage26_network_exports" / "stage26b_revision2_stage25_network_20260816" / "export_03"
OUTPUT = PROJECT / "stage26_failures" / "stage26b_revision2_stage25_network_20260816" / "attempt_03"


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
        raise RuntimeError("immutable attempt-3 failure record already exists")
    if TARGET.exists():
        raise RuntimeError("attempt-3 output unexpectedly exists")
    cfg = load_json(CONFIG)
    expected_status = "authorized_stage26b_revision2_network_export"
    observed_status = cfg.get("status")
    classification_confirmed = observed_status != expected_status and cfg["authority"]["network_export_execution_authorized"] is True
    failure = {
        "schema": "lbs.stage26b-revision2-network-export-attempt-failure.v3",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": False,
        "status": "failed_before_checkpoint_load",
        "attempt": 3,
        "failure_classification": "configuration_status_schema_mismatch",
        "observed_error_type": "RuntimeError",
        "observed_error": "configuration is not network-export authorized",
        "status_comparison": {
            "observed": observed_status,
            "exporter_required": expected_status,
            "classification_confirmed": classification_confirmed,
        },
        "side_effects": {
            "yade_started": True,
            "checkpoint_loaded": False,
            "dem_steps_or_runs": 0,
            "target_output_created": False,
            "exporter_child_remaining_after_exit": False,
        },
        "source_hashes": {
            "config": digest(CONFIG),
            "prerun_checkpoint": digest(PRERUN),
            "exporter": digest(EXPORTER),
            "recorder": digest(Path(__file__)),
        },
        "adaptive_decision": "Use the exporter-required status literal in a new immutable configuration; keep the corrected 175 core gate, checkpoint, graph logic, and exporter source unchanged.",
        "authority": {
            "attempt4_design_authorized": classification_confirmed,
            "network_export_execution_authorized": False,
            "placement_generation_authorized": False,
            "prefilter_yade_execution_authorized": False,
            "two_fibre_free_release_authorized": False,
            "four_fibre_execution_authorized": False,
            "flow_execution_authorized": False
        },
        "claim_boundary": "Pre-load configuration-schema failure only; no checkpoint load, DEM evolution, or physical result.",
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "failure.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(failure, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": False, "classification_confirmed": classification_confirmed, "failure_sha256": digest(path)}, sort_keys=True))
    if not classification_confirmed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
