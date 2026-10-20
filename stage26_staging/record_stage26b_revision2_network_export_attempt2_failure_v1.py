"""Preserve attempt-2 graph-gate failure and its independent comparator."""

import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
sys.path.insert(0, str(PROJECT / "stage26_staging"))
from stage26b_revision2_prefilter_common_v1 import iterative_core

CONFIG = PROJECT / "stage26_staging" / "stage26b_revision2_network_export_execution_v2.json"
PRERUN = PROJECT / "stage26_checkpoints" / "stage26b_tier1_placement_stability_revision2_20260816" / "network_export_prerun_checkpoint_02" / "checkpoint_manifest.json"
STAGE25_RESULT = PROJECT / "stage25_runs" / "stage25a_pure_sand_mechanics_20260813" / "qualification_04" / "mu_0.60" / "result.json"
PRIOR_CONTACTS = PROJECT / "stage25_exports" / "stage25a_pure_sand_mechanics_20260813" / "contact_export_01" / "contacts.csv"
PRIOR_COMPLETION = PROJECT / "stage25_exports" / "stage25a_pure_sand_mechanics_20260813" / "contact_export_01" / "completion.json"
TARGET = PROJECT / "stage26_network_exports" / "stage26b_revision2_stage25_network_20260816" / "export_02"
OUTPUT = PROJECT / "stage26_failures" / "stage26b_revision2_stage25_network_20260816" / "attempt_02"


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
        raise RuntimeError("immutable attempt-2 failure record already exists")
    if TARGET.exists():
        raise RuntimeError("attempt-2 target output unexpectedly exists")
    stage25 = load_json(STAGE25_RESULT)
    prior = load_json(PRIOR_COMPLETION)
    with PRIOR_CONTACTS.open("r", newline="", encoding="utf-8") as stream:
        contacts = list(csv.DictReader(stream))
    edges = [(int(row["id1"]), int(row["id2"])) for row in contacts]
    particle_ids = [int(row["body_id"]) for row in stage25["particles"]]
    _, _, active = iterative_core(particle_ids, edges, 2)
    observed_core = len(active)
    comparator_passed = (
        observed_core == 175
        and stage25["terminal"]["load_bearing_particle_count_after_degree_lt2_pruning"] == 175
        and stage25["terminal"]["real_contact_count"] == 361
        and prior.get("passed") is True
        and prior["real_contact_count"] == 361
        and prior["particle_count"] == 216
        and prior["source"]["checkpoint_sha256"] == "598107294f82d3a5f317f02fc87599d324fc614bb02bfd5048f6a932cced4aad"
    )
    failure = {
        "schema": "lbs.stage26b-revision2-network-export-attempt-failure.v2",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": False,
        "status": "failed_after_checkpoint_load_before_output",
        "attempt": 2,
        "failure_classification": "incorrect_predeclared_stage25_core_count_gate",
        "observed_error_type": "RuntimeError",
        "observed_error": "Stage25 load-bearing-core count mismatch",
        "side_effects": {
            "yade_started": True,
            "checkpoint_loaded": True,
            "dem_steps_or_runs": 0,
            "target_output_created": False,
            "yade_process_remaining_after_exit": False,
        },
        "gate_comparison": {
            "attempt2_required_core_count": 180,
            "exact_stage25_result_core_count": stage25["terminal"]["load_bearing_particle_count_after_degree_lt2_pruning"],
            "independent_prior_contact_export_recomputed_core_count": observed_core,
            "contact_count": len(edges),
            "particle_count": len(particle_ids),
            "comparator_passed": comparator_passed,
        },
        "source_hashes": {
            "config": digest(CONFIG),
            "prerun_checkpoint": digest(PRERUN),
            "stage25_result": digest(STAGE25_RESULT),
            "prior_contacts": digest(PRIOR_CONTACTS),
            "prior_completion": digest(PRIOR_COMPLETION),
            "recorder": digest(Path(__file__)),
        },
        "adaptive_decision": "Correct the Stage25 checkpoint core gate from 180 to 175 through a separately audited erratum; do not change graph logic, checkpoint, contact physics, or exporter source.",
        "authority": {
            "core_count_erratum_design_authorized": comparator_passed,
            "network_export_retry_authorized": False,
            "placement_generation_authorized": False,
            "prefilter_yade_execution_authorized": False,
            "two_fibre_free_release_authorized": False,
            "four_fibre_execution_authorized": False,
            "flow_execution_authorized": False,
        },
        "claim_boundary": "Graph-gate failure and offline evidence comparison only; no DEM evolution or physical result.",
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "failure.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(failure, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": False, "comparator_passed": comparator_passed, "failure_sha256": digest(path)}, sort_keys=True))
    if not comparator_passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
