#!/usr/bin/env python3
"""Independent audit of the Stage34C CPD4-first fragmentation design."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
DESIGN_DIR = ROOT / "stage34_designs/stage34c_cpd4_first_fragmentation_geometry_20260902/design_01"
MANIFEST = DESIGN_DIR / "design_manifest.json"
COMPLETION = DESIGN_DIR / "completion.json"
MATRIX = DESIGN_DIR / "design_matrix.csv"
OUTPUT = ROOT / "stage34_evaluations/stage34c_cpd4_first_fragmentation_geometry_20260902/design_audit_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable audit: {OUTPUT}")
    manifest, completion = load(MANIFEST), load(COMPLETION)
    lineage = {}
    for name, binding in manifest["source_bindings"].items():
        if name == "mechanics_case_records":
            for child, child_binding in binding.items():
                path = Path(child_binding["path"])
                lineage[f"mechanics:{child}"] = path.is_file() and sha(path) == child_binding["sha256"]
        else:
            path = Path(binding["path"])
            lineage[name] = path.is_file() and sha(path) == binding["sha256"]

    cases = manifest["cases"]
    contexts = defaultdict(list)
    for row in cases:
        contexts[(row["packing_id"], row["placement_block"])].append(row)
    roles = Counter(row["role"] for row in cases)
    orders = sorted(row["new_randomized_run_order"] for row in cases if row["new_randomized_run_order"] is not None)
    checks = {
        "design_completion_passed": completion.get("passed") is True,
        "manifest_hash_bound": sha(MANIFEST) == completion["design_manifest_sha256"],
        "matrix_hash_bound": sha(MATRIX) == completion["design_matrix_sha256"],
        "all_source_hashes_verified": all(lineage.values()),
        "exact_four_contexts": len(contexts) == 4,
        "exact_three_levels_per_context": all(sorted(row["fragments_per_parent"] for row in values) == [1, 2, 3] for values in contexts.values()),
        "exact_twelve_rows": len(cases) == 12,
        "exact_four_reused_intact": roles["reused_stage31f_intact_cpd4"] == 4,
        "exact_eight_new_fragment_cases": roles["new_cpd4_fragment_geometry"] == 8,
        "new_order_exact_permutation": orders == list(range(1, 9)),
        "fragment_counts_4_8_12": all(row["total_fragment_count"] == 4 * row["fragments_per_parent"] for row in cases),
        "radius_fixed": all(row["fibre_radius_m"] == 50.0e-6 for row in cases),
        "all_initial_lengths_positive": all(row["initial_equal_volume_piece_centreline_length_m"] > 0 for row in cases),
        "candidate_counts_feasible_before_pairwise_search": all(row["count_feasible_before_pairwise_selection"] for row in manifest["candidate_summary"].values()),
        "candidate_selection_blind_to_hydraulics": manifest["placement_algorithm"]["hydraulic_results_used_for_selection"] is False,
        "nested_anchor_counts_exact": manifest["placement_algorithm"]["nested_anchor_counts"] == {"frag2": 8, "frag3": 12},
        "solver_volume_gate_frozen": "0.5 percent" in manifest["volume_control"]["tolerance"],
        "radius_and_postflow_retuning_prohibited": manifest["volume_control"]["radius_retuning"] is False and manifest["volume_control"]["post_flow_retuning"] is False,
        "cpd4_cpd6_geometry_sentinel_required": manifest["geometry_only_refinement_sentinel"]["resolutions"] == [[186, 186, 186], [279, 279, 279]],
        "no_monotonicity": manifest["analysis"]["monotonicity_imposed"] is False,
        "no_concentration_interaction_authority": manifest["analysis"]["concentration_interaction_authorized"] is False,
        "gpu_flow_not_authorized": manifest["authority"]["gpu_flow_execution"] is False,
        "no_physical_or_chemical_claim": manifest["authority"]["physical_experiment"] is False and manifest["authority"]["chemical_degradation_claim"] is False,
    }
    passed = all(checks.values())
    audit = {
        "schema": "lbs.stage34c-cpd4-first-fragmentation-geometry.v1.independent-design-audit",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed_design_audit_placement_search_authorized" if passed else "failed_design_audit",
        "passed": passed,
        "checks": checks,
        "lineage_checks": lineage,
        "summary": {
            "contexts": len(contexts),
            "condition_rows": len(cases),
            "reused_intact": roles["reused_stage31f_intact_cpd4"],
            "new_fragment_cases": roles["new_cpd4_fragment_geometry"],
            "eligible_candidates": {key: value["eligible_long_parent_scale_candidate_count"] for key, value in manifest["candidate_summary"].items()},
        },
        "authority": {
            "placement_search": passed,
            "geometry_rasterization": False,
            "gpu_flow_execution": False,
            "physical_experiment": False,
            "chemical_degradation_claim": False,
        },
        "claim_boundary": manifest["claim_boundary"],
        "bindings": {
            "manifest_sha256": sha(MANIFEST),
            "completion_sha256": sha(COMPLETION),
            "matrix_sha256": sha(MATRIX),
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
        raise SystemExit(8)


if __name__ == "__main__":
    main()

