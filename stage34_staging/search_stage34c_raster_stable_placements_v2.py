#!/usr/bin/env python3
"""Supersede Stage34C placements only where the frozen raster sentinel fails."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
sys.path.insert(0, str(ROOT / "stage34_staging"))
sys.path.insert(0, str(ROOT / "stage27_staging"))
import build_stage34c_cpd4_cpd6_fragment_geometry_v1 as raster_api  # noqa: E402
import search_stage34c_fragment_placements_v1 as placement_api  # noqa: E402
import build_stage27a_mechanics_hydraulic_masks_v1 as geometry_api  # noqa: E402

STUDY_ROOT = ROOT / "stage34_designs/stage34c_cpd4_first_fragmentation_geometry_20260902"
OUTPUT = STUDY_ROOT / "placement_search_02"
DESIGN = STUDY_ROOT / "design_01/design_manifest.json"
PLACEMENT_01 = STUDY_ROOT / "placement_search_01/placement_manifest.json"
PLACEMENT_01_AUDIT = ROOT / "stage34_evaluations/stage34c_cpd4_first_fragmentation_geometry_20260902/placement_audit_01/placement_audit.json"
STAGE31F_CONFIG = ROOT / "stage31_designs/stage31f_selected_replicated_cpd4_20260827/geometry_01/resolved_config.json"
PATHS = {
    "n216_s1": ROOT / "stage26_designs/stage26x_periodic_pore_geometry_20260823/path_search_01/path_candidates.json",
    "n216_s2": ROOT / "stage31_designs/stage31b_pore_network_exports_20260826/path_search_n216_s2_01/path_candidates.json",
}
PACKINGS = ("n216_s1", "n216_s2")
BLOCKS = ("A", "B")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def bind(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": sha(path)}


def anchor_record(row: dict, parent_rank: int, child_rank: int, score: float) -> dict:
    return {
        "parent_rank": parent_rank,
        "child_rank": child_rank,
        "is_seed_parent_face": child_rank == 1,
        "face_index": int(row["face_index"]),
        "face_body_ids": [int(value) for value in row["face_body_ids"]],
        "rear_m": row["rear_m"],
        "tip_m": row["tip_m"],
        "pull_direction": row["pull_direction"],
        "throat_centre_m": row["throat_centre_m"],
        "throat_to_fibre_radius_ratio": float(row["throat_to_fibre_radius_ratio"]),
        "minimum_sampled_swept_clearance_m": float(row["minimum_sampled_swept_clearance_m"]),
        "selection_score_contribution_group": score,
    }


def ranked_extensions(
    seeds: list[dict], current: list[dict], pool: list[dict], piece_length: float,
    cell: np.ndarray, threshold: float, excluded_faces: set[int], preferred_faces: tuple[int, ...] | None,
) -> list[dict]:
    current_faces = {int(row["face_index"]) for row in current}
    candidates = [
        row for row in pool
        if int(row["face_index"]) not in excluded_faces and int(row["face_index"]) not in current_faces
    ]
    current_distances = [
        placement_api.periodic_segment_distance(a, b, piece_length, cell)
        for a, b in itertools.combinations(current, 2)
    ]
    if current_distances and min(current_distances) < threshold:
        raise RuntimeError("current anchors violate fragment-level spacing")
    current_minimum = min(current_distances) if current_distances else math.inf
    distance_to_current = {}
    compatible = []
    for row in candidates:
        distances = [placement_api.periodic_segment_distance(row, fixed, piece_length, cell) for fixed in current]
        minimum = min(distances) if distances else math.inf
        distance_to_current[int(row["face_index"])] = minimum
        if minimum >= threshold:
            compatible.append(row)
    pair_distances = {}
    for first, second in itertools.combinations(compatible, 2):
        key = tuple(sorted((int(first["face_index"]), int(second["face_index"]))))
        pair_distances[key] = placement_api.periodic_segment_distance(first, second, piece_length, cell)
    ranked = []
    for combo in itertools.combinations(compatible, 4):
        keys = [tuple(sorted((int(a["face_index"]), int(b["face_index"])))) for a, b in itertools.combinations(combo, 2)]
        combo_distances = [pair_distances[key] for key in keys]
        if any(value < threshold for value in combo_distances):
            continue
        score, order = placement_api.assignment_score(seeds, combo, cell)
        overlap = sum(
            len(set(a["face_body_ids"]) & set(b["face_body_ids"]))
            for a, b in itertools.combinations(current + list(combo), 2)
        )
        score += 0.5 * overlap
        assigned = [combo[index] for index in order]
        faces = tuple(int(row["face_index"]) for row in assigned)
        minimum = min(
            current_minimum,
            *(distance_to_current[int(row["face_index"])] for row in combo),
            *combo_distances,
        )
        ranked.append({"score": float(score), "faces": faces, "rows": assigned, "minimum_distance_m": float(minimum)})
    ranked.sort(key=lambda row: (row["score"], tuple(sorted(row["faces"]))))
    if preferred_faces is not None:
        preferred_set = set(preferred_faces)
        for index, row in enumerate(ranked):
            if set(row["faces"]) == preferred_set:
                preferred = ranked.pop(index)
                ranked.insert(0, preferred)
                break
    return ranked


def prepare_contexts(design: dict, stage31f: dict) -> dict:
    cases = {(row["packing_id"], row["placement_block"], int(row["fragments_per_parent"])): row for row in design["cases"]}
    contexts = {}
    sand_279_cache = {}
    for packing in PACKINGS:
        for block in BLOCKS:
            row = cases[(packing, block, 1)]
            path = Path(stage31f["geometry"]["artifacts"][row["source_intact_case_id"]]["geometry"])
            source = raster_api.source_arrays(path)
            material = np.asarray(source["material"], dtype=np.uint8)
            sand_186 = material == 1
            parents = np.asarray(source["fibre_centrelines_m"], dtype=float)
            length = float(source["cell_length_m"][0])
            intact_union_186 = raster_api.raster_union(parents, 186, length)
            if not np.array_equal(intact_union_186 & ~sand_186, material == 2):
                raise RuntimeError(f"source intact reproduction failed: {packing}/{block}")
            if packing not in sand_279_cache:
                sand = np.zeros((279, 279, 279), dtype=bool)
                geometry_api.mark_spheres(sand, source["sand_centres_m"], source["sand_radii_m"], length)
                sand_279_cache[packing] = sand
            sand_279 = sand_279_cache[packing]
            intact_union_279 = raster_api.raster_union(parents, 279, length)
            contexts[(packing, block)] = {
                "parents": parents,
                "length": length,
                "sand_186": sand_186,
                "sand_279": sand_279,
                "target_186": int(np.count_nonzero(material == 2)),
                "target_279": int(np.count_nonzero(intact_union_279 & ~sand_279)),
                "intersection_186": int(np.count_nonzero(intact_union_186 & sand_186)),
                "intersection_279": int(np.count_nonzero(intact_union_279 & sand_279)),
            }
    return contexts


def screen_case(context: dict, anchors: list[dict], fragments: int) -> dict:
    try:
        multiplier, count_186, _, crop_upper, tuning = raster_api.tune_multiplier(
            context["parents"], anchors, fragments,
            context["sand_186"], context["sand_279"], context["length"],
            context["target_186"], context["target_279"],
        )
        lines, _ = raster_api.fragment_geometry(context["parents"], anchors, fragments, multiplier)
        _, metrics_186 = raster_api.raster_metrics(
            lines, context["sand_186"], 186, context["length"], context["intersection_186"]
        )
        _, metrics_279 = raster_api.raster_metrics(
            lines, context["sand_279"], 279, context["length"], context["intersection_279"]
        )
        ratio_186 = metrics_186["fibre_only_voxel_count"] / context["target_186"]
        ratio_279 = metrics_279["fibre_only_voxel_count"] / context["target_279"]
        shift = abs(ratio_279 - ratio_186)
        tolerance = max(1.0, raster_api.VOLUME_REL_TOL * context["target_186"])
        checks = {
            "cpd4_volume": abs(count_186 - context["target_186"]) <= tolerance,
            "cpd4_cpd6_ratio_shift": shift <= raster_api.MAX_VOLUME_RATIO_SHIFT,
            "multiplier_bounds": raster_api.MULTIPLIER_LOWER <= multiplier <= min(raster_api.MULTIPLIER_UPPER, crop_upper),
            "distinct_masks": metrics_186["distinct_fragment_masks"] and metrics_279["distinct_fragment_masks"],
            "zero_overlap": all(value == 0 for value in metrics_186["pair_raw_overlap_voxel_counts"] + metrics_279["pair_raw_overlap_voxel_counts"]),
            "zero_face_adjacency": all(value == 0 for value in metrics_186["pair_face_adjacency_counts"] + metrics_279["pair_face_adjacency_counts"]),
            "sand_intersection": (
                metrics_186["sand_intersection_voxel_count"] <= context["intersection_186"]
                and metrics_279["sand_intersection_voxel_count"] <= context["intersection_279"]
            ),
            "fluid_connected": (
                metrics_186["connectivity"]["largest_fluid_component_fraction"] >= 0.99
                and metrics_279["connectivity"]["largest_fluid_component_fraction"] >= 0.99
                and all(metrics_186["connectivity"]["largest_component_spans_xyz_nonperiodic"])
                and all(metrics_279["connectivity"]["largest_component_spans_xyz_nonperiodic"])
            ),
            "orientation_order": metrics_186["orientation_order"] == metrics_279["orientation_order"],
        }
        return {
            "passed": all(checks.values()),
            "checks": checks,
            "uniform_length_multiplier": multiplier,
            "effective_crop_multiplier_upper": crop_upper,
            "cpd4_fibre_only_voxel_count": metrics_186["fibre_only_voxel_count"],
            "cpd6_fibre_only_voxel_count": metrics_279["fibre_only_voxel_count"],
            "cpd4_volume_ratio": ratio_186,
            "cpd6_volume_ratio": ratio_279,
            "absolute_ratio_shift": shift,
            "cpd4_orientation_order": metrics_186["orientation_order"],
            "cpd6_orientation_order": metrics_279["orientation_order"],
            "tuning": tuning,
        }
    except Exception as exc:
        return {"passed": False, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable superseding placement: {OUTPUT}")
    design, original, original_audit, stage31f = map(load, (DESIGN, PLACEMENT_01, PLACEMENT_01_AUDIT, STAGE31F_CONFIG))
    if original_audit.get("passed") is not True:
        raise RuntimeError("original placement audit did not pass")
    contexts = prepare_contexts(design, stage31f)
    design_contexts = {(row["packing_id"], row["placement_block"]): row for row in design["contexts"]}
    packing_results, rejected = {}, []

    for packing in PACKINGS:
        catalogue = load(PATHS[packing])
        cell = np.asarray(catalogue["cell_dimensions_m"], dtype=float)
        spacing = float(np.prod(cell) ** (1.0 / 3.0)) / 186.0
        threshold = 2.0 * raster_api.RADIUS_M + spacing
        pool = [
            row for row in catalogue["candidates"]
            if float(row["throat_to_fibre_radius_ratio"]) >= 1.25
            and float(row["minimum_sampled_swept_clearance_m"]) >= 2.0e-6
        ]
        by_face = {int(row["face_index"]): row for row in pool}
        selected_blocks = {}
        globally_used = {
            int(row["face_index"])
            for block in BLOCKS
            for row in original["packings"][packing]["blocks"][block]["anchors"]
            if int(row["child_rank"]) == 1
        }

        for block in BLOCKS:
            original_rows = original["packings"][packing]["blocks"][block]["anchors"]
            seed_records = [row for row in original_rows if int(row["child_rank"]) == 1]
            seeds = [by_face[int(row["face_index"])] for row in seed_records]
            original_round2 = tuple(int(row["face_index"]) for row in original_rows if int(row["child_rank"]) == 2)
            original_round3 = tuple(int(row["face_index"]) for row in original_rows if int(row["child_rank"]) == 3)
            context_design = design_contexts[(packing, block)]
            parent_length = float(context_design["mean_parent_contour_length_m"])
            length2 = (parent_length - 4.0 * raster_api.RADIUS_M / 3.0) / 2.0
            round2_options = ranked_extensions(
                seeds, seeds, pool, length2, cell, threshold, globally_used, original_round2
            )
            chosen = None
            for round2_rank, option2 in enumerate(round2_options, start=1):
                round2_records = [anchor_record(row, rank, 2, option2["score"]) for rank, row in enumerate(option2["rows"], start=1)]
                anchors2 = seed_records + round2_records
                screen2 = screen_case(contexts[(packing, block)], anchors2, 2)
                if not screen2["passed"]:
                    rejected.append({
                        "packing_id": packing, "placement_block": block, "fragments_per_parent": 2,
                        "round2_rank": round2_rank, "round2_faces": list(option2["faces"]),
                        "screen": screen2,
                    })
                    continue
                used_for_round3 = globally_used | set(option2["faces"])
                current3 = seeds + option2["rows"]
                length3 = (parent_length - 8.0 * raster_api.RADIUS_M / 3.0) / 3.0
                round3_options = ranked_extensions(
                    seeds, current3, pool, length3, cell, threshold, used_for_round3, original_round3
                )
                for round3_rank, option3 in enumerate(round3_options, start=1):
                    round3_records = [anchor_record(row, rank, 3, option3["score"]) for rank, row in enumerate(option3["rows"], start=1)]
                    anchors3 = anchors2 + round3_records
                    screen3 = screen_case(contexts[(packing, block)], anchors3, 3)
                    if not screen3["passed"]:
                        rejected.append({
                            "packing_id": packing, "placement_block": block, "fragments_per_parent": 3,
                            "round2_rank": round2_rank, "round3_rank": round3_rank,
                            "round2_faces": list(option2["faces"]), "round3_faces": list(option3["faces"]),
                            "screen": screen3,
                        })
                        continue
                    chosen = {
                        "anchors": anchors3,
                        "round2_rank": round2_rank,
                        "round3_rank": round3_rank,
                        "round2_score": option2["score"],
                        "round3_score": option3["score"],
                        "round2_minimum_distance_m": option2["minimum_distance_m"],
                        "round3_minimum_distance_m": option3["minimum_distance_m"],
                        "raster_screen": {"frag2": screen2, "frag3": screen3},
                        "reused_original_round2": set(option2["faces"]) == set(original_round2),
                        "reused_original_round3": set(option3["faces"]) == set(original_round3),
                    }
                    break
                if chosen is not None:
                    break
            if chosen is None:
                raise RuntimeError(f"no raster-stable nested placement found for {packing}/{block}")
            selected_blocks[block] = chosen
            globally_used.update(int(row["face_index"]) for row in chosen["anchors"])

        faces_a = {int(row["face_index"]) for row in selected_blocks["A"]["anchors"]}
        faces_b = {int(row["face_index"]) for row in selected_blocks["B"]["anchors"]}
        packing_results[packing] = {
            "cell_dimensions_m": cell.tolist(),
            "cpd4_spacing_m": spacing,
            "required_centreline_distance_m": threshold,
            "eligible_candidate_count": len(pool),
            "blocks": selected_blocks,
            "cross_block_shared_face_indices": sorted(faces_a & faces_b),
        }

    checks = {
        "exact_two_packings": set(packing_results) == set(PACKINGS),
        "exact_two_blocks_each": all(set(row["blocks"]) == set(BLOCKS) for row in packing_results.values()),
        "exact_twelve_anchors_per_block": all(len(block["anchors"]) == 12 for row in packing_results.values() for block in row["blocks"].values()),
        "no_cross_block_shared_faces": all(not row["cross_block_shared_face_indices"] for row in packing_results.values()),
        "all_selected_fragment_levels_pass_raster_screen": all(
            block["raster_screen"][level]["passed"]
            for row in packing_results.values() for block in row["blocks"].values() for level in ("frag2", "frag3")
        ),
        "original_failed_candidate_preserved": any(
            row["packing_id"] == "n216_s1" and row["placement_block"] == "B"
            and row["fragments_per_parent"] == 2
            and abs(row["screen"].get("absolute_ratio_shift", 0.0) - 0.022697730591089926) <= 1.0e-12
            for row in rejected
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(f"superseding placement checks failed: {checks}")

    manifest = {
        "schema": "lbs.stage34c-raster-stable-fragment-placement.v2",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "superseding_raster_stable_placement_complete_independent_audit_required",
        "method": {
            "selection": "retain original nested anchors when both raster levels pass; otherwise select first passing pair in frozen geometric-cost order",
            "raster_gate": "CPD4 volume within max(1 voxel, 0.5%); CPD4-to-CPD6 volume-ratio shift <=0.02; orientation and topology stable",
            "hydraulic_results_used": False,
            "radius_retuned": False,
        },
        "packings": packing_results,
        "rejected_geometry_only_candidates": rejected,
        "checks": checks,
        "source_bindings": {
            "design": bind(DESIGN),
            "placement_01": bind(PLACEMENT_01),
            "placement_01_audit": bind(PLACEMENT_01_AUDIT),
            "stage31f_config": bind(STAGE31F_CONFIG),
            "n216_s1_path_catalogue": bind(PATHS["n216_s1"]),
            "n216_s2_path_catalogue": bind(PATHS["n216_s2"]),
            "raster_builder_api": bind(Path(raster_api.__file__).resolve()),
            "placement_search_api": bind(Path(placement_api.__file__).resolve()),
            "searcher": bind(Path(__file__).resolve()),
        },
        "authority": {
            "independent_placement_v2_audit": True,
            "raster_geometry_build": False,
            "gpu_flow_execution": False,
            "mechanics_or_coupling": False,
        },
        "claim_boundary": design["claim_boundary"],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".placement_search_02_building_", dir=OUTPUT.parent) as temporary:
        temporary_path = Path(temporary)
        manifest_path = temporary_path / "placement_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        completion = {
            "schema": manifest["schema"] + ".completion",
            "passed": True,
            "status": manifest["status"],
            "placement_manifest_sha256": sha(manifest_path),
            "checks": checks,
            "authority": manifest["authority"],
        }
        (temporary_path / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary_path, OUTPUT)
    print(json.dumps({
        "passed": True,
        "status": manifest["status"],
        "manifest_sha256": sha(OUTPUT / "placement_manifest.json"),
        "rejected_candidate_count": len(rejected),
        "selection": {
            packing: {
                block: {
                    "round2_rank": packing_results[packing]["blocks"][block]["round2_rank"],
                    "round3_rank": packing_results[packing]["blocks"][block]["round3_rank"],
                    "frag2_shift": packing_results[packing]["blocks"][block]["raster_screen"]["frag2"]["absolute_ratio_shift"],
                    "frag3_shift": packing_results[packing]["blocks"][block]["raster_screen"]["frag3"]["absolute_ratio_shift"],
                }
                for block in BLOCKS
            }
            for packing in PACKINGS
        },
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
