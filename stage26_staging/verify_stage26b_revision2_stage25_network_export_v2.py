"""Correct the first verifier's over-strict floating-point equality and reverify."""

import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
STAGING = PROJECT / "stage26_staging"
sys.path.insert(0, str(STAGING))
from stage26b_revision2_prefilter_common_v1 import iterative_core

BUNDLE = PROJECT / "stage26_network_exports" / "stage26b_revision2_stage25_network_20260816" / "export_04"
CONFIG = STAGING / "stage26b_revision2_network_export_execution_v4.json"
FIRST_EVALUATION = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260816" / "network_export_evaluation_01" / "evaluation.json"
FIRST_FAILURE = PROJECT / "stage26_failures" / "stage26b_revision2_stage25_network_20260816" / "verification_01" / "failure.json"
OUTPUT = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260816" / "network_export_evaluation_02"
REL_TOL = 5e-15
ABS_TOL = 1e-18


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
        raise RuntimeError("immutable corrected network-export evaluation already exists")
    first = load_json(FIRST_EVALUATION)
    failure = load_json(FIRST_FAILURE)
    network = load_json(BUNDLE / "network.json")
    completion = load_json(BUNDLE / "completion.json")
    cfg = load_json(CONFIG)
    ids = [int(row["sand_body_id"]) for row in network["particles"]]
    edges = [(int(row["id1"]), int(row["id2"])) for row in network["contacts"]]
    degree, core_degree, core = iterative_core(ids, edges, 2)
    incident = {body_id: [] for body_id in ids}
    for row in network["contacts"]:
        normal = float(row["normal_force_n"])
        incident[int(row["id1"])].append(normal)
        incident[int(row["id2"])].append(normal)
    max_abs_delta = 0.0
    max_relative_delta = 0.0
    fields_within_tolerance = True
    for row in network["particles"]:
        body_id = int(row["sand_body_id"])
        values = incident[body_id]
        expected_sum = sum(values)
        expected_min = min(values) if values else 0.0
        expected_mean = expected_sum / len(values) if values else 0.0
        pairs = (
            (float(row["incident_normal_force_sum_n"]), expected_sum),
            (float(row["minimum_incident_normal_force_n"]), expected_min),
            (float(row["mean_incident_normal_force_n"]), expected_mean),
        )
        for observed, expected in pairs:
            delta = abs(observed - expected)
            scale = max(abs(observed), abs(expected), ABS_TOL)
            max_abs_delta = max(max_abs_delta, delta)
            max_relative_delta = max(max_relative_delta, delta / scale)
            fields_within_tolerance = fields_within_tolerance and math.isclose(observed, expected, rel_tol=REL_TOL, abs_tol=ABS_TOL)
        fields_within_tolerance = fields_within_tolerance and (
            int(row["sand_network_degree"]) == degree[body_id]
            and bool(row["load_bearing_core_member"]) == (body_id in core)
            and int(row["load_bearing_core_degree"]) == core_degree[body_id]
        )
    expected_names = {"network.json", "particles.csv", "contacts.csv", "completion.json"}
    checks = {
        "first_failure_preserved_and_narrow": (
            first.get("passed") is False
            and [name for name, passed in first["checks"].items() if not passed] == ["derived_particle_fields_exact"]
            and failure.get("failure_classification") == "verifier_tolerance_defect_not_export_defect"
            and failure["authority"]["network_export_rerun_authorized"] is False
        ),
        "all_other_first_verification_checks_passed": all(value for name, value in first["checks"].items() if name != "derived_particle_fields_exact"),
        "bundle_unchanged_since_first_verification": all(
            digest(Path(first["evidence"][name + "_path"])) == first["evidence"][name + "_sha256"]
            for name in ("network", "particles_csv", "contacts_csv", "completion", "config", "prerun_checkpoint")
        ),
        "corrected_derived_fields_within_declared_tolerance": fields_within_tolerance,
        "tolerance_is_numerically_tight": REL_TOL <= 5e-15 and ABS_TOL <= 1e-18 and max_relative_delta < REL_TOL,
        "topology_independently_reproduced": len(ids) == len(set(ids)) == 216 and len(edges) == 361 and len(core) == 175,
        "completion_hashes_still_exact": (
            completion["network_sha256"] == digest(BUNDLE / "network.json")
            and completion["particles_csv_sha256"] == digest(BUNDLE / "particles.csv")
            and completion["contacts_csv_sha256"] == digest(BUNDLE / "contacts.csv")
        ),
        "source_bindings_still_exact": (
            completion["source_hashes"]["config"] == digest(CONFIG)
            and completion["source_hashes"]["stage25_checkpoint"] == digest(Path(cfg["sources"]["stage25_checkpoint"]))
            and completion["source_hashes"]["exporter"] == digest(Path(cfg["sources"]["network_exporter"]))
            and completion["source_hashes"]["common"] == digest(Path(cfg["sources"]["common"]))
        ),
        "bundle_contains_no_extra_files": {path.name for path in BUNDLE.iterdir() if path.is_file()} == expected_names,
    }
    passed = all(checks.values())
    evaluation = {
        "schema": "lbs.stage26b-revision2-stage25-network-export-evaluation.v2",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_tolerance_corrected_exact_network_export_verification" if passed else "failed_tolerance_corrected_network_export_verification",
        "checks": checks,
        "tolerance_audit": {
            "relative_tolerance": REL_TOL,
            "absolute_tolerance_n": ABS_TOL,
            "maximum_observed_absolute_delta_n": max_abs_delta,
            "maximum_observed_relative_delta": max_relative_delta,
        },
        "independent_summary": dict(first["independent_summary"], degree2_load_bearing_core_count=len(core)),
        "evidence": dict(first["evidence"],
            first_evaluation_path=str(FIRST_EVALUATION), first_evaluation_sha256=digest(FIRST_EVALUATION),
            first_failure_path=str(FIRST_FAILURE), first_failure_sha256=digest(FIRST_FAILURE),
            verifier_v2_sha256=digest(Path(__file__))),
        "authority": {
            "authorized_next_activity": "Freeze this verified read-only network bundle and prepare an independently audited deterministic two-fibre placement-generation configuration; do not generate placements or execute YADE yet.",
            "placement_generation_preparation_authorized": passed,
            "placement_generation_authorized": False,
            "prefilter_yade_execution_authorized": False,
            "two_fibre_free_release_authorized": False,
            "four_fibre_execution_authorized": False,
            "flow_execution_authorized": False,
        },
        "claim_boundary": completion["claim_boundary"],
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "evaluation.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": passed, "evaluation_sha256": digest(path), "max_relative_delta": max_relative_delta}, sort_keys=True))
    if not passed:
        print(json.dumps({"failed_checks": [name for name, value in checks.items() if not value]}, sort_keys=True))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
