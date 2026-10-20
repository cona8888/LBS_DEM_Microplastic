#!/usr/bin/env python3
"""Freeze nested CPD4 fragment anchors for Stage34C without flow results."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
OUTPUT = ROOT / "stage34_designs/stage34c_cpd4_first_fragmentation_geometry_20260902/placement_search_01"
DESIGN = ROOT / "stage34_designs/stage34c_cpd4_first_fragmentation_geometry_20260902/design_01/design_manifest.json"
DESIGN_AUDIT = ROOT / "stage34_evaluations/stage34c_cpd4_first_fragmentation_geometry_20260902/design_audit_01/design_audit.json"
STAGE31B = ROOT / "stage31_designs/stage31b_nested_concentration_replication_20260826/design_01/design_manifest.json"
PATHS = {
    "n216_s1": ROOT / "stage26_designs/stage26x_periodic_pore_geometry_20260823/path_search_01/path_candidates.json",
    "n216_s2": ROOT / "stage31_designs/stage31b_pore_network_exports_20260826/path_search_n216_s2_01/path_candidates.json",
}
PACKINGS = ("n216_s1", "n216_s2")
BLOCKS = ("A", "B")
RADIUS_M = 50.0e-6


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": sha(path)}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def segment_distance(p1: np.ndarray, q1: np.ndarray, p2: np.ndarray, q2: np.ndarray) -> float:
    u, v, w = q1 - p1, q2 - p2, p1 - p2
    a, b, c = float(u @ u), float(u @ v), float(v @ v)
    d, e = float(u @ w), float(v @ w)
    denominator = a * c - b * b
    if denominator < 1.0e-30:
        s = 0.0
        t = 0.0 if c < 1.0e-30 else min(max(e / c, 0.0), 1.0)
    else:
        s = min(max((b * e - c * d) / denominator, 0.0), 1.0)
        t = min(max((a * e - b * d) / denominator, 0.0), 1.0)
        s = min(max((b * t - d) / a, 0.0), 1.0) if a > 1.0e-30 else 0.0
        t = min(max((b * s + e) / c, 0.0), 1.0) if c > 1.0e-30 else 0.0
    return float(np.linalg.norm(w + s * u - t * v))


def candidate_segment(row: dict, piece_length: float) -> tuple[np.ndarray, np.ndarray]:
    rear, tip = np.asarray(row["rear_m"], dtype=float), np.asarray(row["tip_m"], dtype=float)
    direction = tip - rear
    direction /= np.linalg.norm(direction)
    centre = 0.5 * (rear + tip)
    return centre - 0.5 * piece_length * direction, centre + 0.5 * piece_length * direction


def periodic_segment_distance(first: dict, second: dict, piece_length: float, cell: np.ndarray) -> float:
    p1, q1 = candidate_segment(first, piece_length)
    p2, q2 = candidate_segment(second, piece_length)
    best = math.inf
    for shift in itertools.product((-1, 0, 1), repeat=3):
        vector = np.asarray(shift, dtype=float) * cell
        best = min(best, segment_distance(p1, q1, p2 + vector, q2 + vector))
    return best


def periodic_point_distance(a: np.ndarray, b: np.ndarray, cell: np.ndarray) -> float:
    delta = np.abs(a - b)
    delta = np.minimum(delta, np.maximum(cell - delta, 0.0))
    return float(np.linalg.norm(delta))


def assignment_score(seeds: list[dict], selected: tuple[dict, ...], cell: np.ndarray) -> tuple[float, tuple[int, ...]]:
    best = None
    for order in itertools.permutations(range(4)):
        score = 0.0
        for parent_index, selected_index in enumerate(order):
            parent, child = seeds[parent_index], selected[selected_index]
            pd = np.asarray(parent["pull_direction"], dtype=float)
            cd = np.asarray(child["pull_direction"], dtype=float)
            orientation = 1.0 - abs(float(pd @ cd) / (np.linalg.norm(pd) * np.linalg.norm(cd)))
            parent_mid = 0.5 * (np.asarray(parent["rear_m"], dtype=float) + np.asarray(parent["tip_m"], dtype=float))
            child_mid = 0.5 * (np.asarray(child["rear_m"], dtype=float) + np.asarray(child["tip_m"], dtype=float))
            displacement = periodic_point_distance(parent_mid, child_mid, cell) / float(np.mean(cell))
            throat = abs(float(parent["throat_to_fibre_radius_ratio"]) - float(child["throat_to_fibre_radius_ratio"]))
            shared = len(set(parent["face_body_ids"]) & set(child["face_body_ids"]))
            score += 3.0 * orientation + displacement + 0.05 * throat + 2.0 * shared
        if best is None or score < best[0]:
            best = (score, order)
    assert best is not None
    return float(best[0]), best[1]


def compatible(rows: list[dict], piece_length: float, cell: np.ndarray, threshold: float) -> tuple[bool, float]:
    distances = [periodic_segment_distance(a, b, piece_length, cell) for a, b in itertools.combinations(rows, 2)]
    minimum = min(distances) if distances else math.inf
    return minimum >= threshold, minimum


def best_extension(
    seeds: list[dict], current: list[dict], pool: list[dict], piece_length: float,
    cell: np.ndarray, threshold: float, excluded_faces: set[int], limit: int = 4,
) -> tuple[list[dict], tuple[int, ...], float, float]:
    candidates = [row for row in pool if int(row["face_index"]) not in excluded_faces and int(row["face_index"]) not in {int(x["face_index"]) for x in current}]
    # Build the exact compatibility graph once.  The earlier implementation
    # recomputed every periodic pair distance inside every four-anchor
    # combination; this is mathematically identical but needlessly expensive.
    current_distances = [
        periodic_segment_distance(a, b, piece_length, cell)
        for a, b in itertools.combinations(current, 2)
    ]
    if current_distances and min(current_distances) < threshold:
        raise RuntimeError("accepted current anchors violate the requested fragment-level spacing")
    current_minimum = min(current_distances) if current_distances else math.inf
    distance_to_current = {}
    compatible_candidates = []
    for row in candidates:
        distances = [periodic_segment_distance(row, fixed, piece_length, cell) for fixed in current]
        minimum = min(distances) if distances else math.inf
        distance_to_current[int(row["face_index"])] = minimum
        if minimum >= threshold:
            compatible_candidates.append(row)
    pair_distances = {}
    for first, second in itertools.combinations(compatible_candidates, 2):
        key = tuple(sorted((int(first["face_index"]), int(second["face_index"]))))
        pair_distances[key] = periodic_segment_distance(first, second, piece_length, cell)
    scored = []
    for combo in itertools.combinations(compatible_candidates, limit):
        keys = [tuple(sorted((int(a["face_index"]), int(b["face_index"])))) for a, b in itertools.combinations(combo, 2)]
        combo_distances = [pair_distances[key] for key in keys]
        if any(distance < threshold for distance in combo_distances):
            continue
        minimum = min(
            current_minimum,
            *(distance_to_current[int(row["face_index"])] for row in combo),
            *combo_distances,
        )
        score, order = assignment_score(seeds, combo, cell)
        face_grain_overlap = sum(len(set(a["face_body_ids"]) & set(b["face_body_ids"])) for a, b in itertools.combinations(current + list(combo), 2))
        score += 0.5 * face_grain_overlap
        scored.append((score, tuple(int(row["face_index"]) for row in combo), list(combo), order, minimum))
    if not scored:
        raise RuntimeError("no admissible four-anchor extension")
    scored.sort(key=lambda item: (item[0], item[1]))
    score, _, selected, order, minimum = scored[0]
    return selected, order, float(score), float(minimum)


def anchor_record(row: dict, parent_rank: int, child_rank: int, selection_score: float) -> dict:
    return {
        "parent_rank": parent_rank,
        "child_rank": child_rank,
        "is_seed_parent_face": child_rank == 1,
        "face_index": int(row["face_index"]),
        "face_body_ids": row["face_body_ids"],
        "rear_m": row["rear_m"],
        "tip_m": row["tip_m"],
        "pull_direction": row["pull_direction"],
        "throat_centre_m": row["throat_centre_m"],
        "throat_to_fibre_radius_ratio": float(row["throat_to_fibre_radius_ratio"]),
        "minimum_sampled_swept_clearance_m": float(row["minimum_sampled_swept_clearance_m"]),
        "selection_score_contribution_group": selection_score,
    }


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable placement search: {OUTPUT}")
    design, audit, stage31b = load(DESIGN), load(DESIGN_AUDIT), load(STAGE31B)
    if audit.get("passed") is not True or audit["authority"]["placement_search"] is not True:
        raise RuntimeError("placement search is not authorized")
    context_map = {(row["packing_id"], row["placement_block"]): row for row in design["contexts"]}
    packing_results = {}
    for packing in PACKINGS:
        payload = load(PATHS[packing])
        cell = np.asarray(payload["cell_dimensions_m"], dtype=float)
        spacing = float(np.prod(cell) ** (1.0 / 3.0)) / 186.0
        threshold = 2.0 * RADIUS_M + spacing
        pool = [
            row for row in payload["candidates"]
            if float(row["throat_to_fibre_radius_ratio"]) >= 1.25
            and float(row["minimum_sampled_swept_clearance_m"]) >= 2.0e-6
        ]
        by_face = {int(row["face_index"]): row for row in pool}
        blocks = {}
        seed_faces_by_block = {
            block: [int(row["face_index"]) for row in stage31b["blocks"][packing][block]]
            for block in BLOCKS
        }
        if not all(face in by_face for faces in seed_faces_by_block.values() for face in faces):
            raise RuntimeError(f"accepted seed face absent from eligible pool: {packing}")
        # Reserve both blocks' accepted parents before either block selects a
        # child.  Otherwise block A can consume a face that is already frozen
        # as a block-B parent and only the final disjointness gate catches it.
        globally_used = {face for faces in seed_faces_by_block.values() for face in faces}
        # Select round 2 for both blocks first, then round 3. This keeps each
        # four-anchor addition independent of the other block's hydraulic data.
        for child_rank in (2, 3):
            for block in BLOCKS:
                seed_faces = seed_faces_by_block[block]
                seeds = [by_face[face] for face in seed_faces]
                if block not in blocks:
                    blocks[block] = {"seeds": seeds, "round2": [], "round3": [], "records": []}
                current = seeds + blocks[block]["round2"] + blocks[block]["round3"]
                context = context_map[(packing, block)]
                parent_length = float(context["mean_parent_contour_length_m"])
                fragments = child_rank
                piece_length = (parent_length - 4.0 * RADIUS_M * (fragments - 1) / 3.0) / fragments
                selected, order, score, minimum = best_extension(
                    seeds, current, pool, piece_length, cell, threshold, globally_used
                )
                assigned = [selected[index] for index in order]
                blocks[block][f"round{child_rank}"] = assigned
                blocks[block][f"round{child_rank}_score"] = score
                blocks[block][f"round{child_rank}_minimum_centreline_distance_m"] = minimum
                globally_used.update(int(row["face_index"]) for row in assigned)

        block_outputs = {}
        for block in BLOCKS:
            state = blocks[block]
            records = []
            for parent_rank, row in enumerate(state["seeds"], start=1):
                records.append(anchor_record(row, parent_rank, 1, 0.0))
            for child_rank in (2, 3):
                score = state[f"round{child_rank}_score"]
                for parent_rank, row in enumerate(state[f"round{child_rank}"], start=1):
                    records.append(anchor_record(row, parent_rank, child_rank, score))
            context = context_map[(packing, block)]
            level_metrics = {}
            for fragments in (2, 3):
                parent_length = float(context["mean_parent_contour_length_m"])
                piece_length = (parent_length - 4.0 * RADIUS_M * (fragments - 1) / 3.0) / fragments
                active = [by_face[int(row["face_index"])] for row in records if int(row["child_rank"]) <= fragments]
                okay, minimum = compatible(active, piece_length, cell, threshold)
                level_metrics[f"frag{fragments}"] = {
                    "active_anchor_count": len(active),
                    "piece_length_m": piece_length,
                    "minimum_periodic_centreline_distance_m": minimum,
                    "minimum_surface_gap_m": minimum - 2.0 * RADIUS_M,
                    "minimum_required_surface_gap_m": spacing,
                    "pairwise_spacing_passed": okay,
                    "face_indices": [int(row["face_index"]) for row in active],
                }
            block_outputs[block] = {"anchors": records, "level_metrics": level_metrics}
        faces_a = {row["face_index"] for row in block_outputs["A"]["anchors"]}
        faces_b = {row["face_index"] for row in block_outputs["B"]["anchors"]}
        packing_results[packing] = {
            "cell_dimensions_m": cell.tolist(),
            "cpd4_spacing_m": spacing,
            "required_centreline_distance_m": threshold,
            "eligible_candidate_count": len(pool),
            "blocks": block_outputs,
            "cross_block_shared_face_indices": sorted(faces_a & faces_b),
        }

    manifest = {
        "schema": "lbs.stage34c-cpd4-fragment-placement.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "placement_search_complete_independent_audit_required",
        "method": "deterministic nested four-parent anchor extension blind to hydraulic outcomes",
        "packings": packing_results,
        "checks": {
            "exact_two_packings": len(packing_results) == 2,
            "exact_two_blocks_each": all(set(row["blocks"]) == {"A", "B"} for row in packing_results.values()),
            "exact_twelve_anchors_per_block": all(len(block["anchors"]) == 12 for row in packing_results.values() for block in row["blocks"].values()),
            "no_cross_block_shared_faces": all(not row["cross_block_shared_face_indices"] for row in packing_results.values()),
            "all_pairwise_spacing_passed": all(level["pairwise_spacing_passed"] for row in packing_results.values() for block in row["blocks"].values() for level in block["level_metrics"].values()),
        },
        "source_bindings": {
            "stage34c_design": bind(DESIGN),
            "stage34c_design_audit": bind(DESIGN_AUDIT),
            "stage31b_seed_design": bind(STAGE31B),
            "n216_s1_path_catalogue": bind(PATHS["n216_s1"]),
            "n216_s2_path_catalogue": bind(PATHS["n216_s2"]),
            "searcher": bind(Path(__file__).resolve()),
        },
        "authority": {"independent_placement_audit": True, "geometry_rasterization": False, "gpu_flow_execution": False},
        "claim_boundary": design["claim_boundary"],
    }
    if not all(manifest["checks"].values()):
        print(json.dumps({"passed": False, "checks": manifest["checks"]}, sort_keys=True))
        raise RuntimeError("placement search produced an invalid manifest")
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "placement_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    completion = {
        "schema": "lbs.stage34c-cpd4-fragment-placement.v1.completion",
        "passed": True,
        "status": manifest["status"],
        "placement_manifest_sha256": sha(path),
        "authority": manifest["authority"],
    }
    (OUTPUT / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "status": manifest["status"], "summary": {p: {b: packing_results[p]["blocks"][b]["level_metrics"] for b in BLOCKS} for p in PACKINGS}}, sort_keys=True))


if __name__ == "__main__":
    main()
