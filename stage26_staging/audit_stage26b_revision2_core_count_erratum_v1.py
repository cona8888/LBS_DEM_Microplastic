"""Independently audit the Stage25 degree-2 core-count erratum."""

import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
STAGING = PROJECT / "stage26_staging"
sys.path.insert(0, str(STAGING))
from stage26b_revision2_prefilter_common_v1 import iterative_core

ERRATUM = STAGING / "stage26b_revision2_stage25_core_count_erratum_v1.json"
OUTPUT = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260816" / "core_count_erratum_evaluation_01"


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
        raise RuntimeError("immutable erratum evaluation already exists")
    erratum = load_json(ERRATUM)
    evidence = erratum["evidence"]
    paths = {name: Path(evidence[name]) for name in ("attempt2_failure", "stage25_result", "prior_contacts", "prior_completion")}
    hashes_match = all(digest(path) == evidence[name + "_sha256"] for name, path in paths.items())
    failure = load_json(paths["attempt2_failure"])
    stage25 = load_json(paths["stage25_result"])
    completion = load_json(paths["prior_completion"])
    with paths["prior_contacts"].open("r", newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    particle_ids = [int(row["body_id"]) for row in stage25["particles"]]
    edges = [(int(row["id1"]), int(row["id2"])) for row in rows]
    _, _, core = iterative_core(particle_ids, edges, 2)
    exporter = STAGING / "export_stage26b_revision2_stage25_network_v1.py"
    common = STAGING / "stage26b_revision2_prefilter_common_v1.py"
    checks = {
        "all_declared_evidence_hashes_match": hashes_match,
        "attempt2_is_preserved_zero_step_gate_failure": (
            failure.get("passed") is False
            and failure.get("status") == "failed_after_checkpoint_load_before_output"
            and failure.get("failure_classification") == "incorrect_predeclared_stage25_core_count_gate"
            and failure["side_effects"]["dem_steps_or_runs"] == 0
            and failure["side_effects"]["target_output_created"] is False
            and failure["gate_comparison"]["comparator_passed"] is True
        ),
        "independent_degree2_core_is_175": len(core) == 175,
        "stage25_result_reports_175": stage25["terminal"]["load_bearing_particle_count_after_degree_lt2_pruning"] == 175,
        "particle_and_contact_counts_unchanged": len(set(particle_ids)) == 216 and len(rows) == 361,
        "prior_export_binds_exact_checkpoint": (
            completion.get("passed") is True
            and completion["source"]["checkpoint_sha256"] == erratum["unchanged_evidence"]["stage25_checkpoint_sha256"]
            and completion["particle_count"] == 216
            and completion["real_contact_count"] == 361
        ),
        "only_declared_gate_changes": erratum["superseded_gate"] == {
            "field": "network_export.required_load_bearing_particle_count",
            "incorrect_value": 180,
            "corrected_value": 175,
            "core_degree_threshold": 2,
        },
        "export_sources_unchanged": (
            digest(exporter) == erratum["unchanged_evidence"]["network_exporter_sha256"]
            and digest(common) == erratum["unchanged_evidence"]["common_sha256"]
        ),
        "no_execution_authority": all(
            value is False for name, value in erratum["authority"].items()
            if name != "erratum_audit_authorized"
        ),
    }
    passed = all(checks.values())
    evaluation = {
        "schema": "lbs.stage26b-revision2-stage25-core-count-erratum-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_evidence_bound_core_count_erratum" if passed else "failed_core_count_erratum",
        "checks": checks,
        "independent_result": {
            "particle_count": len(set(particle_ids)),
            "real_contact_count": len(rows),
            "degree_threshold": 2,
            "load_bearing_core_count": len(core),
        },
        "evidence": {
            "erratum_path": str(ERRATUM), "erratum_sha256": digest(ERRATUM),
            "attempt2_failure_path": str(paths["attempt2_failure"]), "attempt2_failure_sha256": digest(paths["attempt2_failure"]),
            "stage25_result_path": str(paths["stage25_result"]), "stage25_result_sha256": digest(paths["stage25_result"]),
            "prior_contacts_path": str(paths["prior_contacts"]), "prior_contacts_sha256": digest(paths["prior_contacts"]),
            "prior_completion_path": str(paths["prior_completion"]), "prior_completion_sha256": digest(paths["prior_completion"]),
            "exporter_path": str(exporter), "exporter_sha256": digest(exporter),
            "common_path": str(common), "common_sha256": digest(common),
            "auditor_sha256": digest(Path(__file__)),
        },
        "authority": {
            "authorized_next_activity": "Freeze the audited erratum and prepare a new exact read-only network-export attempt; do not execute YADE yet.",
            "network_export_execution_authorized": False,
            "placement_generation_authorized": False,
            "prefilter_yade_execution_authorized": False,
            "two_fibre_free_release_authorized": False,
            "four_fibre_execution_authorized": False,
            "flow_execution_authorized": False,
        },
        "claim_boundary": erratum["claim_boundary"],
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "evaluation.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": passed, "evaluation_sha256": digest(path), "core_count": len(core)}, sort_keys=True))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
