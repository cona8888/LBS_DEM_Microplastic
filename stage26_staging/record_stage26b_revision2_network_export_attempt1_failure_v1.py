"""Preserve the observed attempt-1 import failure before source repair."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = PROJECT / "stage26_staging" / "stage26b_revision2_network_export_execution_v1.json"
LAUNCHER = PROJECT / "stage26_staging" / "run_stage26b_revision2_network_export_v1.sh"
EXPORTER = PROJECT / "stage26_staging" / "export_stage26b_revision2_stage25_network_v1.py"
COMMON = PROJECT / "stage26_staging" / "stage26b_revision2_prefilter_common_v1.py"
PRERUN = PROJECT / "stage26_checkpoints" / "stage26b_tier1_placement_stability_revision2_20260815" / "network_export_prerun_checkpoint_01" / "checkpoint_manifest.json"
TARGET = PROJECT / "stage26_network_exports" / "stage26b_revision2_stage25_network_20260815" / "export_01"
OUTPUT = PROJECT / "stage26_failures" / "stage26b_revision2_stage25_network_20260816" / "attempt_01"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable failure record already exists")
    if TARGET.exists():
        raise RuntimeError("target output unexpectedly exists")
    failure = {
        "schema": "lbs.stage26b-revision2-network-export-attempt-failure.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": False,
        "status": "failed_before_checkpoint_load",
        "attempt": 1,
        "failure_classification": "software_import_path_defect",
        "command": [
            "wsl.exe", "-d", "Ubuntu", "--", "bash",
            "/mnt/c/MATDEM_MICROPLASTIC/stage26_staging/run_stage26b_revision2_network_export_v1.sh",
        ],
        "exit_code": 1,
        "observed_error_type": "ModuleNotFoundError",
        "observed_error": "No module named 'stage26b_revision2_prefilter_common_v1'",
        "side_effects": {
            "yade_started": True,
            "checkpoint_loaded": False,
            "dem_steps_or_runs": 0,
            "target_output_created": False,
            "yade_process_remaining_after_exit": False,
        },
        "reason_checkpoint_not_loaded": "The failing sibling-module import occurs at module top level before main(), while O.load is inside main().",
        "source_hashes": {
            "config": digest(CONFIG),
            "launcher": digest(LAUNCHER),
            "exporter": digest(EXPORTER),
            "common": digest(COMMON),
            "prerun_checkpoint": digest(PRERUN),
            "recorder": digest(Path(__file__)),
        },
        "adaptive_decision": "Do not retry attempt 1. Repair explicit script-directory import resolution, re-audit all bound sources, and issue a new immutable pre-run checkpoint.",
        "authority": {
            "source_repair_and_audit_authorized": True,
            "network_export_retry_authorized": False,
            "placement_generation_authorized": False,
            "prefilter_yade_execution_authorized": False,
            "two_fibre_free_release_authorized": False,
            "four_fibre_execution_authorized": False,
            "flow_execution_authorized": False,
        },
        "claim_boundary": "Observed software import failure only; no DEM state or physical result was produced.",
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "failure.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(failure, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": False, "failure_sha256": digest(path)}, sort_keys=True))


if __name__ == "__main__":
    main()
