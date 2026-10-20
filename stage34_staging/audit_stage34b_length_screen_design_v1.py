#!/usr/bin/env python3
"""Independently audit the frozen Stage34B length-screen design."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
DESIGN_DIR = ROOT / "stage34_designs/stage34b_literature_informed_length_screen_20260902/design_01"
MANIFEST = DESIGN_DIR / "design_manifest.json"
COMPLETION = DESIGN_DIR / "completion.json"
MATRIX = DESIGN_DIR / "design_matrix.csv"
OUTPUT = ROOT / "stage34_evaluations/stage34b_literature_informed_length_screen_20260902/design_audit_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable audit: {OUTPUT}")
    manifest, completion = load(MANIFEST), load(COMPLETION)
    bindings = manifest["source_bindings"]
    lineage = {}
    for name, binding in bindings.items():
        if name == "mechanics_case_records":
            for subname, subbinding in binding.items():
                path = Path(subbinding["path"])
                lineage[f"mechanics:{subname}"] = path.is_file() and sha(path) == subbinding["sha256"]
        else:
            path = Path(binding["path"])
            lineage[name] = path.is_file() and sha(path) == binding["sha256"]

    cases = manifest["cases"]
    by_context = defaultdict(list)
    for case in cases:
        by_context[(case["packing_id"], case["placement_block"])].append(case)
    new_orders = sorted(case["new_randomized_run_order"] for case in cases if case["role"] == "new_cpd2_fragment_solve")
    fragment_counts = Counter(case["fragments_per_parent"] for case in cases)
    role_counts = Counter(case["role"] for case in cases)
    checks = {
        "design_completion_passed": completion.get("passed") is True,
        "manifest_hash_bound": sha(MANIFEST) == completion["design_manifest_sha256"],
        "matrix_hash_bound": sha(MATRIX) == completion["design_matrix_sha256"],
        "all_source_lineage_hashes": all(lineage.values()),
        "exact_six_matched_contexts": len(by_context) == 6,
        "three_levels_in_every_context": all(sorted(row["fragments_per_parent"] for row in rows) == [1, 2, 3] for rows in by_context.values()),
        "exact_eighteen_condition_rows": len(cases) == 18,
        "exact_six_reused_intact_rows": role_counts["reused_stage31e_intact"] == 6,
        "exact_twelve_new_cpd2_rows": role_counts["new_cpd2_fragment_solve"] == 12,
        "new_run_order_is_exact_permutation": new_orders == list(range(1, 13)),
        "fragment_counts_are_4_8_12": all(case["total_fragment_count"] == 4 * case["fragments_per_parent"] for case in cases),
        "fragment_levels_balanced": fragment_counts == Counter({1: 6, 2: 6, 3: 6}),
        "radius_frozen": all(case["fibre_radius_m"] == 50.0e-6 for case in cases),
        "dose_frozen_within_context": all(len({round(row["legacy_dry_mass_percent"], 15) for row in rows}) == 1 for rows in by_context.values()),
        "total_parent_length_frozen_within_context": all(len({round(row["total_parent_contour_length_m"], 15) for row in rows}) == 1 for rows in by_context.values()),
        "intact_records_hash_bound": all(case["source_intact_record_sha256"] for case in cases),
        "no_monotonicity_imposed": manifest["analysis"]["monotonicity_imposed"] is False,
        "volume_matching_required": "0.5 percent" in manifest["geometry_rules"]["maximum_fibre_only_voxel_deviation"],
        "radius_retuning_prohibited": manifest["geometry_rules"]["radius_retuning"] is False,
        "physical_experiment_not_authorized": manifest["authority"]["physical_experiment"] is False,
        "gpu_execution_not_authorized": manifest["authority"]["gpu_execution"] is False,
        "chemical_degradation_claim_not_authorized": manifest["authority"]["chemical_degradation_claim"] is False,
    }
    passed = all(checks.values())
    audit = {
        "schema": "lbs.stage34b-literature-informed-length-screen.v1.independent-design-audit",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed_design_audit_geometry_not_authorized" if passed else "failed_design_audit",
        "passed": passed,
        "checks": checks,
        "lineage_checks": lineage,
        "summary": {
            "matched_contexts": len(by_context),
            "condition_rows": len(cases),
            "reused_intact_rows": role_counts["reused_stage31e_intact"],
            "new_cpd2_rows": role_counts["new_cpd2_fragment_solve"],
            "fragmentation_levels": sorted(fragment_counts),
        },
        "authority": {
            "geometry_construction": passed,
            "gpu_execution": False,
            "cpd4_execution": False,
            "physical_experiment": False,
            "chemical_degradation_claim": False,
        },
        "claim_boundary": manifest["claim_boundary"],
        "bindings": {
            "design_manifest_sha256": sha(MANIFEST),
            "design_completion_sha256": sha(COMPLETION),
            "design_matrix_sha256": sha(MATRIX),
            "auditor_sha256": sha(Path(__file__).resolve()),
        },
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "design_audit.json"
    path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUTPUT / "completion.json").write_text(
        json.dumps({"passed": passed, "status": audit["status"], "design_audit_sha256": sha(path)}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"passed": passed, "status": audit["status"], "checks": checks}, sort_keys=True))
    if not passed:
        raise SystemExit(5)


if __name__ == "__main__":
    main()

