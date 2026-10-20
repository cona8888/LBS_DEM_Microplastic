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
from stage28a_geometry_math_v1 import synchronous_distance_history  # noqa: E402


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage29c_four_fibre_single_contact_qualification_20260825"
SOURCE = ROOT / "stage29_designs" / STUDY / "candidate_geometry_01"
OUT = ROOT / "stage29_evaluations" / STUDY / "candidate_geometry_audit_01"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    p, cp = SOURCE / "candidate_geometry.json", SOURCE / "completion.json"
    data, completion = json.loads(p.read_text()), json.loads(cp.read_text())
    lengths = np.asarray(data["cell_dimensions_m"], dtype=float)
    translations = np.linspace(0.0, data["maximum_synchronous_translation_m"], data["translation_sample_count"])
    radius = float(data["fibre_radius_m"])
    recomputed, graphs_ok = {}, True
    for c in data["cases"]:
        observed, minima = [], {}
        for i, j in itertools.combinations(range(4), 2):
            values = synchronous_distance_history(c["fibres"][i], c["fibres"][j], lengths, translations)
            minimum = float(np.min(values))
            minima[f"{i + 1}-{j + 1}"] = minimum
            if minimum <= 2.0 * radius:
                observed.append([i + 1, j + 1])
        expected = sorted(c["intended_predicted_contact_edges"])
        observed.sort()
        ok = observed == expected
        graphs_ok &= ok
        recomputed[c["case_id"]] = {"expected": expected, "observed": observed, "minimum_centreline_distance_by_pair_m": minima, "passed": ok}
    source_ok = all(digest(Path(v["path"])) == v["sha256"] for v in data["source_bindings"].values())
    checks = {
        "completion_passed_and_bound": completion.get("passed") is True and completion.get("candidate_geometry_sha256") == digest(p),
        "all_source_hashes_match": source_ok,
        "stage29b_failure_bound": "stage29b_failure" in data["source_bindings"],
        "exact_six_cases": len(data["cases"]) == 6,
        "three_complete_blocks": all({c["topology_regime"] for c in data["cases"] if c["placement_block"] == b} == {"zero_contact", "one_contact"} for b in "ABC"),
        "recomputed_contact_graphs_exact": graphs_ok,
        "matching_metrics_finite": all(np.isfinite(v["orientation_feature_l2_mismatch"]) and np.isfinite(v["periodic_centroid_mismatch_m"]) for v in data["paired_matching"].values()),
        "authority_stops_before_acceptance": data["authority"]["geometry_acceptance"] is False and data["authority"]["yade_execution"] is False,
    }
    passed = all(checks.values())
    audit = {
        "schema": data["schema"] + ".audit",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_candidate_geometry_audit_runner_not_authorized" if passed else "failed_candidate_geometry_audit",
        "checks": checks,
        "recomputed_topology": recomputed,
        "paired_matching": data["paired_matching"],
        "candidate_geometry_sha256": digest(p),
        "completion_sha256": digest(cp),
        "next_handoff": {
            "authorized": "design and independently audit a Stage29c mechanics runner/preflight derived from accepted Stage28a revision 2",
            "not_authorized": "YADE execution, GPU flow, or permeability claims",
        },
    }
    OUT.mkdir(parents=True)
    ap = OUT / "geometry_audit.json"
    ap.write_text(json.dumps(audit, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    (OUT / "checkpoint_manifest.json").write_text(json.dumps({
        "schema": data["schema"] + ".checkpoint", "passed": passed,
        "geometry_audit_sha256": digest(ap), "candidate_geometry_sha256": digest(p), "authority": audit["next_handoff"]
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **audit}, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
