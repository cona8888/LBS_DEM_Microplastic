#!/usr/bin/env python3
"""Independently audit the superseding Stage34C raster-stable placements."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
PLACEMENT = ROOT / "stage34_designs/stage34c_cpd4_first_fragmentation_geometry_20260902/placement_search_02/placement_manifest.json"
PLACEMENT_COMPLETION = PLACEMENT.parent / "completion.json"
ORIGINAL = ROOT / "stage34_designs/stage34c_cpd4_first_fragmentation_geometry_20260902/placement_search_01/placement_manifest.json"
DESIGN = ROOT / "stage34_designs/stage34c_cpd4_first_fragmentation_geometry_20260902/design_01/design_manifest.json"
OUTPUT = ROOT / "stage34_evaluations/stage34c_cpd4_first_fragmentation_geometry_20260902/placement_audit_02"
PATHS = {
    "n216_s1": ROOT / "stage26_designs/stage26x_periodic_pore_geometry_20260823/path_search_01/path_candidates.json",
    "n216_s2": ROOT / "stage31_designs/stage31b_pore_network_exports_20260826/path_search_n216_s2_01/path_candidates.json",
}
PACKINGS = ("n216_s1", "n216_s2")
BLOCKS = ("A", "B")
RADIUS_M = 50.0e-6


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_binding(binding: dict) -> bool:
    path = Path(binding["path"])
    return path.is_file() and sha(path) == binding["sha256"]


def segment_distance(p1: np.ndarray, q1: np.ndarray, p2: np.ndarray, q2: np.ndarray) -> float:
    # Independent finite-segment closest-distance implementation.
    u, v, w = q1 - p1, q2 - p2, p1 - p2
    a, b, c = float(u @ u), float(u @ v), float(v @ v)
    d, e = float(u @ w), float(v @ w)
    denominator = a * c - b * b
    s = 0.0 if denominator <= 1.0e-30 else min(max((b * e - c * d) / denominator, 0.0), 1.0)
    t = 0.0 if c <= 1.0e-30 else min(max((b * s + e) / c, 0.0), 1.0)
    s = 0.0 if a <= 1.0e-30 else min(max((b * t - d) / a, 0.0), 1.0)
    return float(np.linalg.norm(w + s * u - t * v))


def endpoints(row: dict, length: float) -> tuple[np.ndarray, np.ndarray]:
    rear, tip = np.asarray(row["rear_m"], dtype=float), np.asarray(row["tip_m"], dtype=float)
    direction = tip - rear
    direction /= np.linalg.norm(direction)
    centre = 0.5 * (rear + tip)
    return centre - 0.5 * length * direction, centre + 0.5 * length * direction


def periodic_distance(first: dict, second: dict, length: float, cell: np.ndarray) -> float:
    p1, q1 = endpoints(first, length)
    p2, q2 = endpoints(second, length)
    return min(
        segment_distance(p1, q1, p2 + np.asarray(shift) * cell, q2 + np.asarray(shift) * cell)
        for shift in itertools.product((-1, 0, 1), repeat=3)
    )


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable placement audit: {OUTPUT}")
    placement, completion, original, design = map(load, (PLACEMENT, PLACEMENT_COMPLETION, ORIGINAL, DESIGN))
    contexts = {(row["packing_id"], row["placement_block"]): row for row in design["contexts"]}
    checks = {
        "schema_exact": placement.get("schema") == "lbs.stage34c-raster-stable-fragment-placement.v2",
        "completion_passed": completion.get("passed") is True,
        "completion_binds_manifest": completion.get("placement_manifest_sha256") == sha(PLACEMENT),
        "all_source_bindings_verified": all(check_binding(binding) for binding in placement["source_bindings"].values()),
        "original_binding_exact": placement["source_bindings"]["placement_01"]["sha256"] == sha(ORIGINAL),
        "design_binding_exact": placement["source_bindings"]["design"]["sha256"] == sha(DESIGN),
        "exact_packings": set(placement["packings"]) == set(PACKINGS),
        "claim_boundary_unchanged": placement.get("claim_boundary") == design.get("claim_boundary"),
        "no_gpu_authority": placement.get("authority", {}).get("gpu_flow_execution") is False,
        "no_raster_build_before_audit": placement.get("authority", {}).get("raster_geometry_build") is False,
        "hydraulic_results_not_used": placement.get("method", {}).get("hydraulic_results_used") is False,
        "radius_not_retuned": placement.get("method", {}).get("radius_retuned") is False,
    }

    ranks_exact = True
    anchors_match = True
    seed_match = True
    unique_faces = True
    disjoint_blocks = True
    spacing_pass = True
    selected_raster_pass = True
    selected_thresholds_pass = True
    replacement_scope_exact = True
    min_gap = math.inf

    for packing in PACKINGS:
        catalogue = load(PATHS[packing])
        cell = np.asarray(catalogue["cell_dimensions_m"], dtype=float)
        spacing = float(np.prod(cell) ** (1.0 / 3.0)) / 186.0
        threshold = 2.0 * RADIUS_M + spacing
        eligible = {
            int(row["face_index"]): row for row in catalogue["candidates"]
            if float(row["throat_to_fibre_radius_ratio"]) >= 1.25
            and float(row["minimum_sampled_swept_clearance_m"]) >= 2.0e-6
        }
        observed = placement["packings"][packing]
        selected_faces = {}
        for block in BLOCKS:
            state = observed["blocks"][block]
            rows = state["anchors"]
            selected_faces[block] = {int(row["face_index"]) for row in rows}
            ranks_exact &= (
                len(rows) == 12
                and sorted((int(row["child_rank"]), int(row["parent_rank"])) for row in rows)
                == [(child, parent) for child in (1, 2, 3) for parent in (1, 2, 3, 4)]
            )
            unique_faces &= len(selected_faces[block]) == 12
            original_seeds = [
                int(row["face_index"]) for row in original["packings"][packing]["blocks"][block]["anchors"]
                if int(row["child_rank"]) == 1
            ]
            observed_seeds = [int(row["face_index"]) for row in rows if int(row["child_rank"]) == 1]
            seed_match &= observed_seeds == original_seeds
            for row in rows:
                face = int(row["face_index"])
                if face not in eligible:
                    anchors_match = False
                    continue
                source = eligible[face]
                anchors_match &= (
                    row["face_body_ids"] == source["face_body_ids"]
                    and np.allclose(row["rear_m"], source["rear_m"], rtol=0.0, atol=1.0e-12)
                    and np.allclose(row["tip_m"], source["tip_m"], rtol=0.0, atol=1.0e-12)
                    and np.allclose(row["pull_direction"], source["pull_direction"], rtol=0.0, atol=1.0e-12)
                )
            context = contexts[(packing, block)]
            parent_length = float(context["mean_parent_contour_length_m"])
            for fragments in (2, 3):
                active = [row for row in rows if int(row["child_rank"]) <= fragments]
                piece_length = (parent_length - 4.0 * RADIUS_M * (fragments - 1) / 3.0) / fragments
                distances = [periodic_distance(a, b, piece_length, cell) for a, b in itertools.combinations(active, 2)]
                minimum = min(distances)
                min_gap = min(min_gap, minimum - 2.0 * RADIUS_M)
                spacing_pass &= minimum + 1.0e-12 >= threshold
                screen = state["raster_screen"][f"frag{fragments}"]
                selected_raster_pass &= screen.get("passed") is True and all(screen.get("checks", {}).values())
                selected_thresholds_pass &= (
                    abs(float(screen["cpd4_volume_ratio"]) - 1.0) <= 0.005 + 1.0 / max(1, int(screen["cpd4_fibre_only_voxel_count"]))
                    and float(screen["absolute_ratio_shift"]) <= 0.02
                    and 0.90 <= float(screen["uniform_length_multiplier"]) <= 1.10
                    and screen["cpd4_orientation_order"] == screen["cpd6_orientation_order"]
                )
            original_block = original["packings"][packing]["blocks"][block]["anchors"]
            original_round2 = {int(row["face_index"]) for row in original_block if int(row["child_rank"]) == 2}
            original_round3 = {int(row["face_index"]) for row in original_block if int(row["child_rank"]) == 3}
            observed_round2 = {int(row["face_index"]) for row in rows if int(row["child_rank"]) == 2}
            observed_round3 = {int(row["face_index"]) for row in rows if int(row["child_rank"]) == 3}
            should_replace_round2 = packing == "n216_s1" and block == "B"
            replacement_scope_exact &= (
                (observed_round2 != original_round2) == should_replace_round2
                and observed_round3 == original_round3
                and int(state["round2_rank"]) == (2 if should_replace_round2 else 1)
                and int(state["round3_rank"]) == 1
            )
        disjoint_blocks &= not (selected_faces["A"] & selected_faces["B"])
        disjoint_blocks &= observed["cross_block_shared_face_indices"] == []

    rejected = placement.get("rejected_geometry_only_candidates", [])
    rejected_original = [
        row for row in rejected
        if row.get("packing_id") == "n216_s1" and row.get("placement_block") == "B"
        and int(row.get("fragments_per_parent", 0)) == 2 and int(row.get("round2_rank", 0)) == 1
    ]
    checks.update({
        "exact_child_parent_rank_grid": ranks_exact,
        "all_anchors_match_eligible_catalogues": anchors_match,
        "accepted_seed_faces_unchanged": seed_match,
        "unique_faces_within_blocks": unique_faces,
        "blocks_use_disjoint_faces": disjoint_blocks,
        "pairwise_spacing_independently_passed": spacing_pass,
        "all_selected_raster_screens_passed": selected_raster_pass,
        "all_selected_raster_thresholds_passed": selected_thresholds_pass,
        "only_failed_s1B_round2_was_replaced": replacement_scope_exact,
        "exact_one_rejected_original_candidate": len(rejected) == 1 and len(rejected_original) == 1,
        "rejected_original_shift_reproduced_in_record": (
            len(rejected_original) == 1
            and abs(float(rejected_original[0]["screen"]["absolute_ratio_shift"]) - 0.022697730591089926) <= 1.0e-12
            and rejected_original[0]["screen"]["checks"]["cpd4_cpd6_ratio_shift"] is False
        ),
        "global_checks_all_true": all(placement.get("checks", {}).values()),
    })
    search_text = Path(placement["source_bindings"]["searcher"]["path"]).read_text(encoding="utf-8").lower()
    checks["search_code_has_no_hydraulic_observable"] = not any(
        token in search_text for token in ("paired_permeability_ratio", "conductance_proxy_lu", "intrinsic_permeability", "pressure_drop", "flow_rate")
    )

    passed = all(checks.values())
    status = "passed_superseding_placement_audit_raster_build_authorized" if passed else "failed_superseding_placement_audit_fail_closed"
    authority = {
        "raster_geometry_build": passed,
        "independent_raster_audit": False,
        "gpu_flow_execution": False,
        "mechanics_or_coupling": False,
    }
    audit = {
        "schema": "lbs.stage34c-raster-stable-fragment-placement-audit.v2",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": status,
        "checks": checks,
        "metrics": {
            "anchor_count": sum(len(block["anchors"]) for row in placement["packings"].values() for block in row["blocks"].values()),
            "minimum_independently_recomputed_surface_gap_m": min_gap,
            "rejected_candidate_count": len(rejected),
            "replacement_count": 1 if replacement_scope_exact else None,
        },
        "source_bindings": {
            "placement": {"path": str(PLACEMENT.resolve()), "sha256": sha(PLACEMENT)},
            "placement_completion": {"path": str(PLACEMENT_COMPLETION.resolve()), "sha256": sha(PLACEMENT_COMPLETION)},
            "original_placement": {"path": str(ORIGINAL.resolve()), "sha256": sha(ORIGINAL)},
            "design": {"path": str(DESIGN.resolve()), "sha256": sha(DESIGN)},
            "auditor": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).resolve())},
        },
        "authority": authority,
        "claim_boundary": placement["claim_boundary"],
    }
    OUTPUT.mkdir(parents=True)
    audit_path = OUTPUT / "placement_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    completion_out = {
        "schema": audit["schema"] + ".completion",
        "passed": passed,
        "status": status,
        "placement_audit_sha256": sha(audit_path),
        "checks": checks,
        "authority": authority,
    }
    (OUTPUT / "completion.json").write_text(json.dumps(completion_out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "passed": passed,
        "status": status,
        "failed_checks": [name for name, value in checks.items() if not value],
        "metrics": audit["metrics"],
    }, indent=2, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
