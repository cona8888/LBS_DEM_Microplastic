#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(r"C:\MATDEM_MICROPLASTIC\stage28_staging")))
from stage28a_geometry_math_v1 import synchronous_distance_history


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage29b_four_fibre_mechanics_qualification_20260825"
SOURCE = ROOT / "stage29_designs" / STUDY / "candidate_geometry_01"
OUT = ROOT / "stage29_evaluations" / STUDY / "candidate_geometry_audit_01"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    p = SOURCE / "candidate_geometry.json"
    cp = SOURCE / "completion.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    completion = json.loads(cp.read_text(encoding="utf-8"))
    lengths = np.asarray(data["cell_dimensions_m"], dtype=float)
    translations = np.linspace(0.0, data["maximum_synchronous_translation_m"], data["translation_sample_count"])
    radius = float(data["fibre_radius_m"])
    recomputed = {}
    topology_ok = True
    for case in data["cases"]:
        observed = []
        all_pairs = {}
        for i, j in itertools.combinations(range(4), 2):
            values = synchronous_distance_history(case["fibres"][i], case["fibres"][j], lengths, translations)
            minimum = float(np.min(values))
            key = f"{i + 1}-{j + 1}"
            all_pairs[key] = minimum
            if minimum <= 2.0 * radius:
                observed.append([i + 1, j + 1])
        observed.sort()
        expected = sorted(case["intended_predicted_contact_edges"])
        case_ok = observed == expected
        topology_ok = topology_ok and case_ok
        recomputed[case["case_id"]] = {
            "expected_predicted_contact_edges": expected,
            "recomputed_predicted_contact_edges": observed,
            "minimum_centreline_distance_by_pair_m": all_pairs,
            "passed": case_ok,
        }
    source_hashes = all(digest(Path(v["path"])) == v["sha256"] for v in data["source_bindings"].values())
    matching = data["paired_matching"]
    checks = {
        "builder_completion_passed": completion.get("passed") is True,
        "completion_binds_geometry": completion.get("candidate_geometry_sha256") == digest(p),
        "source_hashes_match": source_hashes,
        "exact_six_cases": len(data["cases"]) == 6,
        "three_complete_blocks": all(
            len([c for c in data["cases"] if c["placement_block"] == b]) == 2 for b in "ABC"
        ),
        "recomputed_topology_matches_every_label": topology_ok,
        "orientation_mismatch_reported_finite": all(np.isfinite(v["orientation_feature_l2_mismatch"]) for v in matching.values()),
        "centroid_mismatch_reported_finite": all(np.isfinite(v["periodic_centroid_mismatch_m"]) for v in matching.values()),
        "authority_stops_before_acceptance": data["authority"]["geometry_acceptance"] is False and data["authority"]["yade_execution"] is False,
    }
    passed = all(checks.values())
    audit = {
        "schema": "lbs.stage29b-four-fibre-candidate-geometry.v1.audit",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_candidate_geometry_audit_runner_not_authorized" if passed else "failed_candidate_geometry_audit",
        "checks": checks,
        "recomputed_topology": recomputed,
        "paired_matching": matching,
        "candidate_geometry_sha256": digest(p),
        "completion_sha256": digest(cp),
        "next_handoff": {
            "authorized": "design and independently audit a Stage29b mechanics runner/preflight using the accepted Stage28a revision-2 suppression implementation",
            "not_authorized": "YADE execution, GPU flow, or permeability claims",
        },
    }
    OUT.mkdir(parents=True)
    ap = OUT / "geometry_audit.json"
    ap.write_text(json.dumps(audit, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    checkpoint = {
        "schema": "lbs.stage29b-four-fibre-candidate-geometry.v1.checkpoint",
        "passed": passed,
        "geometry_audit_sha256": digest(ap),
        "candidate_geometry_sha256": digest(p),
        "authority": audit["next_handoff"],
    }
    (OUT / "checkpoint_manifest.json").write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **audit}, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
