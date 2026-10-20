#!/usr/bin/env python3
"""Build the immutable Stage34C CPD4/CPD6 fixed-volume geometry sentinel."""

from __future__ import annotations

import csv
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
sys.path.insert(0, str(ROOT / "stage27_staging"))
import build_stage27a_mechanics_hydraulic_masks_v1 as api  # noqa: E402

STUDY_ROOT = ROOT / "stage34_designs/stage34c_cpd4_first_fragmentation_geometry_20260902"
OUTPUT = STUDY_ROOT / "raster_geometry_01"
DESIGN = STUDY_ROOT / "design_01/design_manifest.json"
DESIGN_COMPLETION = STUDY_ROOT / "design_01/completion.json"
PLACEMENT = STUDY_ROOT / "placement_search_01/placement_manifest.json"
PLACEMENT_COMPLETION = STUDY_ROOT / "placement_search_01/completion.json"
DESIGN_AUDIT = ROOT / "stage34_evaluations/stage34c_cpd4_first_fragmentation_geometry_20260902/design_audit_01/design_audit.json"
PLACEMENT_AUDIT = ROOT / "stage34_evaluations/stage34c_cpd4_first_fragmentation_geometry_20260902/placement_audit_01/placement_audit.json"
STAGE31F_CONFIG = ROOT / "stage31_designs/stage31f_selected_replicated_cpd4_20260827/geometry_01/resolved_config.json"
STAGE31F_RUN = ROOT / "stage31_runs/stage31f_selected_replicated_cpd4_20260827/gpu_confirmation_01"
GEOMETRY_API = ROOT / "stage27_staging/build_stage27a_mechanics_hydraulic_masks_v1.py"
CONTRACT = ROOT / "stage34_staging/STAGE34C_CPD4_FIRST_FRAGMENTATION_GEOMETRY_CONTRACT.md"

PACKINGS = ("n216_s1", "n216_s2")
BLOCKS = ("A", "B")
RESOLUTIONS = (186, 279)
RADIUS_M = 50.0e-6
MULTIPLIER_LOWER = 0.90
MULTIPLIER_UPPER = 1.10
VOLUME_REL_TOL = 0.005
MAX_VOLUME_RATIO_SHIFT = 0.02


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


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def source_arrays(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as data:
        return {key: np.asarray(data[key]) for key in data.files}


def contour_length(points: np.ndarray) -> float:
    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())


def point_at_arclength(points: np.ndarray, target: float) -> np.ndarray:
    segment_lengths = np.linalg.norm(np.diff(points, axis=0), axis=1)
    cumulative = np.concatenate(([0.0], np.cumsum(segment_lengths)))
    target = min(max(float(target), 0.0), float(cumulative[-1]))
    index = int(np.searchsorted(cumulative, target, side="right") - 1)
    index = min(max(index, 0), len(points) - 2)
    local = target - cumulative[index]
    fraction = 0.0 if segment_lengths[index] <= 1.0e-30 else local / segment_lengths[index]
    return points[index] + fraction * (points[index + 1] - points[index])


def rotation_matrix(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    source = source / np.linalg.norm(source)
    target = target / np.linalg.norm(target)
    cross = np.cross(source, target)
    sine = float(np.linalg.norm(cross))
    cosine = float(np.dot(source, target))
    if sine <= 1.0e-14:
        if cosine > 0.0:
            return np.eye(3)
        trial = np.array([1.0, 0.0, 0.0]) if abs(source[0]) < 0.8 else np.array([0.0, 1.0, 0.0])
        axis = np.cross(source, trial)
        axis /= np.linalg.norm(axis)
        return -np.eye(3) + 2.0 * np.outer(axis, axis)
    axis = cross / sine
    skew = np.array([[0.0, -axis[2], axis[1]], [axis[2], 0.0, -axis[0]], [-axis[1], axis[0], 0.0]])
    return np.eye(3) + sine * skew + (1.0 - cosine) * (skew @ skew)


def fragment_geometry(
    parents: np.ndarray, anchors: list[dict], fragments_per_parent: int, multiplier: float
) -> tuple[np.ndarray, list[dict]]:
    lines, records = [], []
    for anchor in sorted(anchors, key=lambda row: (int(row["child_rank"]), int(row["parent_rank"]))):
        child_rank = int(anchor["child_rank"])
        if child_rank > fragments_per_parent:
            continue
        parent_rank = int(anchor["parent_rank"])
        parent = np.asarray(parents[parent_rank - 1], dtype=float)
        parent_length = contour_length(parent)
        base_length = (parent_length - 4.0 * RADIUS_M * (fragments_per_parent - 1) / 3.0) / fragments_per_parent
        selected_length = base_length * multiplier
        crop_centre_s = (child_rank - 0.5) * parent_length / fragments_per_parent
        crop_start_s = crop_centre_s - 0.5 * selected_length
        crop_end_s = crop_centre_s + 0.5 * selected_length
        if crop_start_s < -1.0e-14 or crop_end_s > parent_length + 1.0e-14:
            raise RuntimeError("selected crop extends outside its source parent")
        sample_s = np.linspace(crop_start_s, crop_end_s, 37)
        source_piece = np.stack([point_at_arclength(parent, value) for value in sample_s])
        source_direction = source_piece[-1] - source_piece[0]
        target_direction = np.asarray(anchor["pull_direction"], dtype=float)
        target_direction /= np.linalg.norm(target_direction)
        transform = rotation_matrix(source_direction, target_direction)
        source_centre = 0.5 * (source_piece[0] + source_piece[-1])
        target_centre = 0.5 * (np.asarray(anchor["rear_m"], dtype=float) + np.asarray(anchor["tip_m"], dtype=float))
        translation = target_centre - transform @ source_centre
        target_piece = (transform @ source_piece.T).T + translation
        lines.append(target_piece)
        records.append({
            "parent_rank": parent_rank,
            "child_rank": child_rank,
            "target_face_index": int(anchor["face_index"]),
            "target_face_body_ids": [int(value) for value in anchor["face_body_ids"]],
            "source_parent_contour_length_m": parent_length,
            "base_equal_volume_piece_length_m": base_length,
            "selected_piece_contour_length_m": contour_length(target_piece),
            "source_crop_start_arclength_m": crop_start_s,
            "source_crop_end_arclength_m": crop_end_s,
            "source_crop_centre_m": source_centre.tolist(),
            "target_centre_m": target_centre.tolist(),
            "source_direction": (source_direction / np.linalg.norm(source_direction)).tolist(),
            "target_direction": target_direction.tolist(),
            "rotation_matrix": transform.tolist(),
            "translation_m": translation.tolist(),
            "throat_to_fibre_radius_ratio": float(anchor["throat_to_fibre_radius_ratio"]),
            "minimum_sampled_swept_clearance_m": float(anchor["minimum_sampled_swept_clearance_m"]),
            "target_anchor_chord_m": float(np.linalg.norm(np.asarray(anchor["tip_m"]) - np.asarray(anchor["rear_m"]))),
        })
    return np.asarray(lines, dtype=float), records


def raster_union(lines: np.ndarray, resolution: int, length: float) -> np.ndarray:
    union = np.zeros((resolution, resolution, resolution), dtype=bool)
    for points in lines:
        # All accepted Stage31f parents are straight to floating-point precision;
        # endpoints therefore give the same capsule union without repeatedly
        # rasterizing 36 collinear subsegments.
        api.mark_capsule(union, points[[0, -1]], RADIUS_M, length)
    return union


def detailed_masks(lines: np.ndarray, resolution: int, length: float) -> tuple[np.ndarray, list[np.ndarray]]:
    masks = []
    for points in lines:
        mask = np.zeros((resolution, resolution, resolution), dtype=bool)
        api.mark_capsule(mask, points[[0, -1]], RADIUS_M, length)
        masks.append(mask)
    return np.logical_or.reduce(masks), masks


def face_adjacency(first: np.ndarray, second: np.ndarray) -> int:
    return sum(
        int(np.count_nonzero(np.roll(first, shift, axis=axis) & second))
        for axis in range(3) for shift in (-1, 1)
    )


def mask_sha(mask: np.ndarray) -> str:
    return hashlib.sha256(np.packbits(mask, axis=None).tobytes()).hexdigest()


def projected_footprints(fibre: np.ndarray) -> dict[str, float]:
    resolution = fibre.shape[0]
    return {
        "normal_x": float(np.count_nonzero(np.any(fibre, axis=2)) / resolution**2),
        "normal_y": float(np.count_nonzero(np.any(fibre, axis=1)) / resolution**2),
        "normal_z": float(np.count_nonzero(np.any(fibre, axis=0)) / resolution**2),
    }


def orientation_order(values: dict[str, float]) -> list[str]:
    return [key for key, _ in sorted(values.items(), key=lambda item: (-item[1], item[0]))]


def raster_metrics(
    lines: np.ndarray, sand: np.ndarray, resolution: int, length: float, source_sand_intersection: int
) -> tuple[np.ndarray, dict]:
    union, masks = detailed_masks(lines, resolution, length)
    material = np.zeros(sand.shape, dtype=np.uint8)
    material[sand] = 1
    material[union & ~sand] = 2
    phase = np.where(material != 0, 2, 0).astype(np.uint8)
    overlaps, adjacency = [], []
    for first, second in itertools.combinations(masks, 2):
        overlaps.append(int(np.count_nonzero(first & second)))
        adjacency.append(face_adjacency(first, second))
    fragment_hashes = [mask_sha(mask) for mask in masks]
    fibre = material == 2
    footprints = projected_footprints(fibre)
    connectivity = api.connectivity(material != 0)
    metrics = {
        "resolution": resolution,
        "spacing_m": length / resolution,
        "sand_voxel_count": int(np.count_nonzero(sand)),
        "raw_fragment_union_voxel_count": int(np.count_nonzero(union)),
        "fibre_only_voxel_count": int(np.count_nonzero(fibre)),
        "sand_intersection_voxel_count": int(np.count_nonzero(union & sand)),
        "source_intact_sand_intersection_voxel_count": int(source_sand_intersection),
        "pair_raw_overlap_voxel_counts": overlaps,
        "pair_face_adjacency_counts": adjacency,
        "fragment_mask_sha256": fragment_hashes,
        "distinct_fragment_masks": len(fragment_hashes) == len(set(fragment_hashes)),
        "projected_fibre_footprint_fraction": footprints,
        "orientation_order": orientation_order(footprints),
        "voxel_porosity": float(np.mean(phase == 0)),
        "connectivity": connectivity,
    }
    return material, metrics


def tune_multiplier(
    parents: np.ndarray, anchors: list[dict], fragments: int,
    sand_186: np.ndarray, sand_279: np.ndarray, length: float,
    target_186: int, target_279: int,
) -> tuple[float, int, list[dict], float, dict]:
    cache_186: dict[float, tuple[int, list[dict]]] = {}
    cache_279: dict[float, int] = {}

    def evaluate(multiplier: float) -> tuple[int, list[dict]]:
        key = float(multiplier)
        if key not in cache_186:
            lines, records = fragment_geometry(parents, anchors, fragments, key)
            union = raster_union(lines, 186, length)
            cache_186[key] = (int(np.count_nonzero(union & ~sand_186)), records)
        return cache_186[key]

    def evaluate_279(multiplier: float) -> int:
        key = float(multiplier)
        if key not in cache_279:
            lines, _ = fragment_geometry(parents, anchors, fragments, key)
            union = raster_union(lines, 279, length)
            cache_279[key] = int(np.count_nonzero(union & ~sand_279))
        return cache_279[key]

    crop_upper = min(
        (contour_length(parent) / fragments)
        / ((contour_length(parent) - 4.0 * RADIUS_M * (fragments - 1) / 3.0) / fragments)
        for parent in parents
    )
    effective_upper = min(MULTIPLIER_UPPER, crop_upper)
    tolerance = max(1.0, VOLUME_REL_TOL * target_186)
    minimum_count = math.ceil(target_186 - tolerance)
    maximum_count = math.floor(target_186 + tolerance)

    def first_at_least(threshold: int) -> float:
        low, high = MULTIPLIER_LOWER, effective_upper
        if evaluate(high)[0] < threshold:
            raise RuntimeError("CPD4 target volume cannot be reached within the non-overlapping crop bound")
        for _ in range(36):
            middle = 0.5 * (low + high)
            if evaluate(middle)[0] < threshold:
                low = middle
            else:
                high = middle
        return high

    def last_at_most(threshold: int) -> float:
        low, high = MULTIPLIER_LOWER, effective_upper
        if evaluate(low)[0] > threshold:
            raise RuntimeError("CPD4 target volume lies below the frozen multiplier range")
        for _ in range(36):
            middle = 0.5 * (low + high)
            if evaluate(middle)[0] <= threshold:
                low = middle
            else:
                high = middle
        return low

    admissible_low = first_at_least(minimum_count)
    admissible_high = last_at_most(maximum_count)
    if admissible_low > admissible_high + 1.0e-12:
        raise RuntimeError("no CPD4 volume-admissible multiplier interval")
    candidates = set(float(value) for value in np.linspace(admissible_low, admissible_high, 65))
    candidates.update((admissible_low, admissible_high, min(max(1.0, admissible_low), admissible_high)))
    scored = []
    for multiplier in sorted(candidates):
        count_186, records = evaluate(multiplier)
        if not (minimum_count <= count_186 <= maximum_count):
            continue
        count_279 = evaluate_279(multiplier)
        ratio_186 = count_186 / target_186
        ratio_279 = count_279 / target_279
        scored.append((
            abs(ratio_279 - ratio_186),
            abs(count_186 - target_186),
            abs(multiplier - 1.0),
            multiplier,
            count_186,
            count_279,
            records,
        ))
    if not scored:
        raise RuntimeError("no sampled multiplier satisfies the CPD4 volume tolerance")
    scored.sort(key=lambda row: row[:4])
    shift, _, _, best_multiplier, best_count_186, best_count_279, best_records = scored[0]
    diagnostics = {
        "selection_rule": "CPD4 volume gate; minimize CPD4-to-CPD6 volume-ratio shift; then CPD4 count error; then distance from 1.0",
        "admissible_multiplier_interval": [admissible_low, admissible_high],
        "sampled_admissible_candidate_count": len(scored),
        "selected_cpd6_fibre_only_voxel_count": best_count_279,
        "selected_absolute_cpd4_to_cpd6_volume_ratio_shift": shift,
    }
    return best_multiplier, best_count_186, best_records, effective_upper, diagnostics


def save_geometry(
    path: Path, material: np.ndarray, length: float, source: dict[str, np.ndarray],
    lines: np.ndarray, fragments: int, multiplier: float,
) -> None:
    resolution = material.shape[0]
    phase = np.where(material != 0, 2, 0).astype(np.uint8)
    np.savez_compressed(
        path,
        phase=phase,
        material=material,
        spacing_m=np.asarray([length / resolution]),
        cell_length_m=np.asarray([length]),
        original_cell_lengths_m=source["original_cell_lengths_m"],
        affine_scale_xyz=source["affine_scale_xyz"],
        sand_centres_m=source["sand_centres_m"],
        sand_radii_m=source["sand_radii_m"],
        fibre_centrelines_m=lines,
        fibre_radius_m=np.asarray([RADIUS_M]),
        fragments_per_parent=np.asarray([fragments], dtype=np.int16),
        uniform_length_multiplier=np.asarray([multiplier]),
    )


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable raster geometry: {OUTPUT}")
    design, placement, design_audit, placement_audit, stage31f = map(
        load, (DESIGN, PLACEMENT, DESIGN_AUDIT, PLACEMENT_AUDIT, STAGE31F_CONFIG)
    )
    design_done, placement_done = load(DESIGN_COMPLETION), load(PLACEMENT_COMPLETION)
    if not all(item.get("passed") is True for item in (design_done, placement_done, design_audit, placement_audit)):
        raise RuntimeError("upstream Stage34C gate did not pass")
    if placement_audit["authority"].get("geometry_rasterization") is not True:
        raise RuntimeError("geometry rasterization is not authorized")
    if placement_audit["authority"].get("gpu_flow_execution") is not False:
        raise RuntimeError("unexpected GPU authority in placement audit")
    if sha(STAGE31F_CONFIG) != design["source_bindings"]["stage31f_config"]["sha256"]:
        raise RuntimeError("Stage31f configuration hash mismatch")

    design_cases = {(row["packing_id"], row["placement_block"], int(row["fragments_per_parent"])): row for row in design["cases"]}
    source_artifacts = stage31f["geometry"]["artifacts"]
    parent_cache: dict[tuple[str, str], dict] = {}
    sand_cache_279: dict[str, np.ndarray] = {}
    source_rows = []

    for packing in PACKINGS:
        for block in BLOCKS:
            row = design_cases[(packing, block, 1)]
            source_case = row["source_intact_case_id"]
            source_path = Path(source_artifacts[source_case]["geometry"])
            record_path = STAGE31F_RUN / f"stage31f_{source_case}_cpd4/record.json"
            if sha(source_path) != row["source_intact_geometry_sha256"] or sha(record_path) != row["source_intact_record_sha256"]:
                raise RuntimeError(f"accepted intact binding mismatch: {packing}/{block}")
            source = source_arrays(source_path)
            parents = np.asarray(source["fibre_centrelines_m"], dtype=float)
            if parents.shape != (4, 37, 3):
                raise RuntimeError(f"source parent shape mismatch: {packing}/{block}")
            line_deviations = []
            for line in parents:
                chord = line[-1] - line[0]
                unit = chord / np.linalg.norm(chord)
                residual = line - (line[0] + ((line - line[0]) @ unit)[:, None] * unit)
                line_deviations.append(float(np.max(np.linalg.norm(residual, axis=1))))
            if max(line_deviations) > 1.0e-12:
                raise RuntimeError("endpoint rasterization is not equivalent for a non-straight accepted parent")
            material = np.asarray(source["material"], dtype=np.uint8)
            sand_186 = material == 1
            intact_fibre_186 = material == 2
            length = float(source["cell_length_m"][0])
            reconstructed = raster_union(parents, 186, length)
            if not np.array_equal(reconstructed & ~sand_186, intact_fibre_186):
                raise RuntimeError(f"accepted intact CPD4 mask does not reproduce from stored parents: {packing}/{block}")
            source_intersection_186 = int(np.count_nonzero(reconstructed & sand_186))
            if packing not in sand_cache_279:
                sand_279 = np.zeros((279, 279, 279), dtype=bool)
                api.mark_spheres(sand_279, source["sand_centres_m"], source["sand_radii_m"], length)
                sand_cache_279[packing] = sand_279
            else:
                sand_279 = sand_cache_279[packing]
            intact_union_279 = raster_union(parents, 279, length)
            source_intersection_279 = int(np.count_nonzero(intact_union_279 & sand_279))
            parent_cache[(packing, block)] = {
                "source_case": source_case,
                "source_path": source_path,
                "record_path": record_path,
                "source": source,
                "parents": parents,
                "length": length,
                "sand_186": sand_186,
                "sand_279": sand_279,
                "intact_fibre_count_186": int(np.count_nonzero(intact_fibre_186)),
                "intact_fibre_count_279": int(np.count_nonzero(intact_union_279 & ~sand_279)),
                "source_intersection_186": source_intersection_186,
                "source_intersection_279": source_intersection_279,
                "intact_material_186": material,
                "intact_material_279": np.where(sand_279, 1, np.where(intact_union_279, 2, 0)).astype(np.uint8),
                "maximum_parent_line_deviation_m": max(line_deviations),
            }
            source_rows.append({
                "packing_id": packing,
                "placement_block": block,
                "source_case_id": source_case,
                "source_geometry": bind(source_path),
                "source_record": bind(record_path),
                "intact_fibre_only_voxel_count_cpd4": int(np.count_nonzero(intact_fibre_186)),
                "rebuilt_intact_fibre_only_voxel_count_cpd6": int(np.count_nonzero(intact_union_279 & ~sand_279)),
                "maximum_parent_line_deviation_m": max(line_deviations),
            })

    rows, artifacts, transforms = [], {}, {}
    parent_dir = OUTPUT.parent
    parent_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".raster_geometry_01_building_", dir=parent_dir) as temporary:
        temporary_path = Path(temporary)
        for packing in PACKINGS:
            for block in BLOCKS:
                context = parent_cache[(packing, block)]
                anchors = placement["packings"][packing]["blocks"][block]["anchors"]
                for fragments in (1, 2, 3):
                    case = design_cases[(packing, block, fragments)]
                    case_id = case["case_id"]
                    case_dir = temporary_path / case_id
                    case_dir.mkdir()
                    if fragments == 1:
                        multiplier = 1.0
                        tuning_diagnostics = None
                        lines = context["parents"]
                        fragment_records = []
                        material_186 = context["intact_material_186"]
                        material_279 = context["intact_material_279"]
                        _, metrics_186 = raster_metrics(
                            lines, context["sand_186"], 186, context["length"], context["source_intersection_186"]
                        )
                        _, metrics_279 = raster_metrics(
                            lines, context["sand_279"], 279, context["length"], context["source_intersection_279"]
                        )
                        cpd4_path = context["source_path"]
                        cpd4_reused = True
                    else:
                        target = context["intact_fibre_count_186"]
                        multiplier, tuned_count, _, effective_crop_upper, tuning_diagnostics = tune_multiplier(
                            context["parents"], anchors, fragments,
                            context["sand_186"], context["sand_279"], context["length"],
                            target, context["intact_fibre_count_279"],
                        )
                        lines, fragment_records = fragment_geometry(context["parents"], anchors, fragments, multiplier)
                        material_186, metrics_186 = raster_metrics(
                            lines, context["sand_186"], 186, context["length"], context["source_intersection_186"]
                        )
                        if metrics_186["fibre_only_voxel_count"] != tuned_count:
                            raise RuntimeError("tuning/final CPD4 count mismatch")
                        material_279, metrics_279 = raster_metrics(
                            lines, context["sand_279"], 279, context["length"], context["source_intersection_279"]
                        )
                        if metrics_279["fibre_only_voxel_count"] != tuning_diagnostics["selected_cpd6_fibre_only_voxel_count"]:
                            raise RuntimeError("tuning/final CPD6 count mismatch")
                        cpd4_path = case_dir / "geometry_cpd4.npz"
                        save_geometry(cpd4_path, material_186, context["length"], context["source"], lines, fragments, multiplier)
                        cpd4_reused = False
                    if fragments == 1:
                        effective_crop_upper = 1.0
                    cpd6_path = case_dir / "geometry_cpd6.npz"
                    save_geometry(cpd6_path, material_279, context["length"], context["source"], lines, fragments, multiplier)

                    target = context["intact_fibre_count_186"]
                    tolerance_voxels = max(1.0, VOLUME_REL_TOL * target)
                    volume_error_voxels = metrics_186["fibre_only_voxel_count"] - target
                    ratio_186 = metrics_186["fibre_only_voxel_count"] / target
                    ratio_279 = metrics_279["fibre_only_voxel_count"] / context["intact_fibre_count_279"]
                    ratio_shift = abs(ratio_279 - ratio_186)
                    case_checks = {
                        "cpd4_solver_pet_volume_within_tolerance": abs(volume_error_voxels) <= tolerance_voxels,
                        "uniform_length_multiplier_within_frozen_bounds": MULTIPLIER_LOWER <= multiplier <= MULTIPLIER_UPPER,
                        "uniform_length_multiplier_within_nonoverlapping_crop_bound": multiplier <= effective_crop_upper + 1.0e-12,
                        "radius_unchanged": float(case["fibre_radius_m"]) == RADIUS_M,
                        "fragment_count_exact": int(metrics_186["distinct_fragment_masks"]) == 1 and lines.shape[0] == 4 * fragments,
                        "distinct_fragment_masks_both_resolutions": metrics_186["distinct_fragment_masks"] and metrics_279["distinct_fragment_masks"],
                        "zero_pair_overlap_both_resolutions": all(value == 0 for value in metrics_186["pair_raw_overlap_voxel_counts"] + metrics_279["pair_raw_overlap_voxel_counts"]),
                        "at_least_one_voxel_interfragment_gap_both_resolutions": all(value == 0 for value in metrics_186["pair_face_adjacency_counts"] + metrics_279["pair_face_adjacency_counts"]),
                        "sand_intersection_not_greater_than_intact_both_resolutions": (
                            metrics_186["sand_intersection_voxel_count"] <= context["source_intersection_186"]
                            and metrics_279["sand_intersection_voxel_count"] <= context["source_intersection_279"]
                        ),
                        "fluid_connected_99pct_both_resolutions": (
                            metrics_186["connectivity"]["largest_fluid_component_fraction"] >= 0.99
                            and metrics_279["connectivity"]["largest_fluid_component_fraction"] >= 0.99
                        ),
                        "fluid_spans_xyz_both_resolutions": (
                            all(metrics_186["connectivity"]["largest_component_spans_xyz_nonperiodic"])
                            and all(metrics_279["connectivity"]["largest_component_spans_xyz_nonperiodic"])
                        ),
                        "cpd4_cpd6_volume_ratio_shift_le_0p02": ratio_shift <= MAX_VOLUME_RATIO_SHIFT,
                        "orientation_order_stable": metrics_186["orientation_order"] == metrics_279["orientation_order"],
                    }
                    if not all(case_checks.values()):
                        raise RuntimeError(json.dumps({
                            "message": "raster geometry checks failed",
                            "case_id": case_id,
                            "checks": case_checks,
                            "cpd4_volume_ratio": ratio_186,
                            "cpd6_volume_ratio": ratio_279,
                            "absolute_ratio_shift": ratio_shift,
                            "uniform_length_multiplier": multiplier,
                            "tuning_diagnostics": tuning_diagnostics,
                        }, sort_keys=True))

                    cpd4_actual = context["source_path"] if cpd4_reused else cpd4_path
                    cpd4_final = context["source_path"] if cpd4_reused else OUTPUT / case_id / "geometry_cpd4.npz"
                    cpd6_final = OUTPUT / case_id / "geometry_cpd6.npz"
                    artifacts[case_id] = {
                        "cpd4_geometry": str(cpd4_final.resolve()),
                        "cpd4_geometry_sha256": sha(cpd4_actual),
                        "cpd4_reused_accepted_intact": cpd4_reused,
                        "cpd6_geometry": str(cpd6_final.resolve()),
                        "cpd6_geometry_sha256": sha(cpd6_path),
                    }
                    transforms[case_id] = fragment_records
                    rows.append({
                        "case_id": case_id,
                        "packing_id": packing,
                        "placement_block": block,
                        "fragments_per_parent": fragments,
                        "total_fragment_count": int(lines.shape[0]),
                        "uniform_length_multiplier": multiplier,
                        "effective_nonoverlapping_crop_multiplier_upper": effective_crop_upper,
                        "geometry_only_multiplier_selection": tuning_diagnostics,
                        "target_intact_fibre_only_voxel_count_cpd4": target,
                        "cpd4_volume_tolerance_voxels": tolerance_voxels,
                        "cpd4_volume_error_voxels": volume_error_voxels,
                        "cpd4_fibre_volume_ratio_to_intact": ratio_186,
                        "cpd6_fibre_volume_ratio_to_intact": ratio_279,
                        "absolute_cpd4_to_cpd6_volume_ratio_shift": ratio_shift,
                        "cpd4_metrics": metrics_186,
                        "cpd6_metrics": metrics_279,
                        "checks": case_checks,
                    })

        csv_path = temporary_path / "raster_metrics.csv"
        flat_rows = []
        for row in rows:
            flat_rows.append({
                "case_id": row["case_id"],
                "packing_id": row["packing_id"],
                "placement_block": row["placement_block"],
                "fragments_per_parent": row["fragments_per_parent"],
                "total_fragment_count": row["total_fragment_count"],
                "uniform_length_multiplier": row["uniform_length_multiplier"],
                "effective_crop_multiplier_upper": row["effective_nonoverlapping_crop_multiplier_upper"],
                "target_cpd4_fibre_voxels": row["target_intact_fibre_only_voxel_count_cpd4"],
                "cpd4_fibre_voxels": row["cpd4_metrics"]["fibre_only_voxel_count"],
                "cpd6_fibre_voxels": row["cpd6_metrics"]["fibre_only_voxel_count"],
                "cpd4_volume_ratio": row["cpd4_fibre_volume_ratio_to_intact"],
                "cpd6_volume_ratio": row["cpd6_fibre_volume_ratio_to_intact"],
                "absolute_ratio_shift": row["absolute_cpd4_to_cpd6_volume_ratio_shift"],
                "cpd4_orientation_order": ">".join(row["cpd4_metrics"]["orientation_order"]),
                "cpd6_orientation_order": ">".join(row["cpd6_metrics"]["orientation_order"]),
            })
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(flat_rows[0]))
            writer.writeheader()
            writer.writerows(flat_rows)

        checks = {
            "exact_twelve_conditions": len(rows) == 12,
            "exact_four_reused_intact_cpd4": sum(int(value["cpd4_reused_accepted_intact"]) for value in artifacts.values()) == 4,
            "exact_eight_new_cpd4": sum(int(not value["cpd4_reused_accepted_intact"]) for value in artifacts.values()) == 8,
            "exact_twelve_new_cpd6_geometry_sentinels": len(artifacts) == 12,
            "all_case_checks_passed": all(all(row["checks"].values()) for row in rows),
            "all_source_parents_straight_within_1e_12_m": all(row["maximum_parent_line_deviation_m"] <= 1.0e-12 for row in source_rows),
            "maximum_volume_ratio_shift_le_0p02": max(row["absolute_cpd4_to_cpd6_volume_ratio_shift"] for row in rows) <= MAX_VOLUME_RATIO_SHIFT,
            "all_orientation_orders_stable": all(row["checks"]["orientation_order_stable"] for row in rows),
            "no_topology_reversal": all(
                row["checks"]["fluid_connected_99pct_both_resolutions"]
                and row["checks"]["fluid_spans_xyz_both_resolutions"]
                and row["checks"]["zero_pair_overlap_both_resolutions"]
                and row["checks"]["at_least_one_voxel_interfragment_gap_both_resolutions"]
                for row in rows
            ),
        }
        if not all(checks.values()):
            raise RuntimeError(f"global raster checks failed: {checks}")

        manifest = {
            "schema": "lbs.stage34c-cpd4-cpd6-fragment-raster-geometry.v1",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "status": "raster_geometry_complete_independent_audit_required",
            "research_question": design["research_question"],
            "claim_boundary": design["claim_boundary"],
            "method": {
                "parent_geometry": "accepted Stage31f straight 37-point centrelines, cropped by parent arclength",
                "transform": "rigid rotation and translation to frozen Stage34C anchors",
                "volume_control": "uniform per-case centreline-length multiplier constrained by CPD4 fibre-only voxel count and selected by the CPD4/CPD6 geometry sentinel",
                "multiplier_selection": "CPD4 volume gate followed by minimum CPD4-to-CPD6 volume-ratio shift; no flow observable",
                "radius_retuned": False,
                "flow_results_used": False,
                "orientation_order_definition": "descending projected fibre-footprint fractions normal to x, y, and z",
                "topology_definition": "fluid spans x/y/z with >=0.99 largest-component fraction and fragment masks neither overlap nor face-touch",
            },
            "resolutions": {"cpd4": [186, 186, 186], "cpd6": [279, 279, 279]},
            "source_contexts": source_rows,
            "cases": rows,
            "transforms": transforms,
            "artifacts": artifacts,
            "checks": checks,
            "source_bindings": {
                "contract": bind(CONTRACT),
                "design": bind(DESIGN),
                "design_completion": bind(DESIGN_COMPLETION),
                "design_audit": bind(DESIGN_AUDIT),
                "placement": bind(PLACEMENT),
                "placement_completion": bind(PLACEMENT_COMPLETION),
                "placement_audit": bind(PLACEMENT_AUDIT),
                "stage31f_config": bind(STAGE31F_CONFIG),
                "geometry_api": bind(GEOMETRY_API),
                "builder": bind(Path(__file__).resolve()),
            },
            "raster_metrics_csv": {"path": str((OUTPUT / "raster_metrics.csv").resolve()), "sha256": sha(csv_path)},
            "authority": {
                "independent_raster_audit": True,
                "gpu_flow_execution": False,
                "cpd6_flow_execution": False,
                "mechanics_or_coupling": False,
            },
        }
        manifest_path = temporary_path / "raster_manifest.json"
        write_json(manifest_path, manifest)
        completion = {
            "schema": manifest["schema"] + ".completion",
            "passed": True,
            "status": manifest["status"],
            "raster_manifest_sha256": sha(manifest_path),
            "raster_metrics_csv_sha256": sha(csv_path),
            "checks": checks,
            "authority": manifest["authority"],
        }
        write_json(temporary_path / "completion.json", completion)
        os.replace(temporary_path, OUTPUT)

    print(json.dumps({
        "passed": True,
        "status": "raster_geometry_complete_independent_audit_required",
        "manifest": str(OUTPUT / "raster_manifest.json"),
        "manifest_sha256": sha(OUTPUT / "raster_manifest.json"),
        "maximum_volume_ratio_shift": max(row["absolute_cpd4_to_cpd6_volume_ratio_shift"] for row in rows),
        "multipliers": {row["case_id"]: row["uniform_length_multiplier"] for row in rows if row["fragments_per_parent"] > 1},
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
