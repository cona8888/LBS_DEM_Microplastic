#!/usr/bin/env python3
"""Independently audit all Stage34C CPD4/CPD6 fragment geometry artifacts."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
sys.path.insert(0, str(ROOT / "stage27_staging"))
import build_stage27a_mechanics_hydraulic_masks_v1 as api  # noqa: E402

GEOMETRY_DIR = ROOT / "stage34_designs/stage34c_cpd4_first_fragmentation_geometry_20260902/raster_geometry_01"
MANIFEST = GEOMETRY_DIR / "raster_manifest.json"
COMPLETION = GEOMETRY_DIR / "completion.json"
PLACEMENT = ROOT / "stage34_designs/stage34c_cpd4_first_fragmentation_geometry_20260902/placement_search_02/placement_manifest.json"
RASTER_RELEASE = ROOT / "stage34_evaluations/stage34c_cpd4_first_fragmentation_geometry_20260902/placement_audit_04/placement_audit.json"
OUTPUT = ROOT / "stage34_evaluations/stage34c_cpd4_first_fragmentation_geometry_20260902/raster_audit_01"
RADIUS_M = 50.0e-6
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


def check_binding(binding: dict) -> bool:
    path = Path(binding["path"])
    return path.is_file() and sha(path) == binding["sha256"]


def arrays(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as data:
        return {key: np.asarray(data[key]) for key in data.files}


def contour_length(points: np.ndarray) -> float:
    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())


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


def rerasterize(lines: np.ndarray, sand: np.ndarray, radius: float, length: float) -> tuple[np.ndarray, dict]:
    union = np.zeros_like(sand)
    fragment_hashes = []
    overlap_counts = []
    adjacency_counts = []
    for line in lines:
        mask = np.zeros_like(sand)
        # Deliberately use all stored subsegments, unlike the endpoint-only
        # optimization used by the builder.
        api.mark_capsule(mask, line, radius, length)
        overlap_counts.append(int(np.count_nonzero(mask & union)))
        adjacency_counts.append(sum(
            int(np.count_nonzero(np.roll(mask, shift, axis=axis) & union))
            for axis in range(3) for shift in (-1, 1)
        ))
        fragment_hashes.append(mask_sha(mask))
        union |= mask
    fibre = union & ~sand
    material = np.zeros(sand.shape, dtype=np.uint8)
    material[sand] = 1
    material[fibre] = 2
    phase = np.where(material != 0, 2, 0).astype(np.uint8)
    footprints = projected_footprints(fibre)
    connectivity = api.connectivity(material != 0)
    return material, {
        "raw_union_voxel_count": int(np.count_nonzero(union)),
        "fibre_only_voxel_count": int(np.count_nonzero(fibre)),
        "sand_intersection_voxel_count": int(np.count_nonzero(union & sand)),
        "incremental_overlap_voxel_counts": overlap_counts,
        "incremental_face_adjacency_counts": adjacency_counts,
        "fragment_mask_sha256": fragment_hashes,
        "distinct_fragment_masks": len(fragment_hashes) == len(set(fragment_hashes)),
        "projected_fibre_footprint_fraction": footprints,
        "orientation_order": orientation_order(footprints),
        "connectivity": connectivity,
        "phase_sha256": hashlib.sha256(phase.tobytes()).hexdigest(),
    }


def capsule_volume(radius: float, centreline_length: float) -> float:
    return math.pi * radius**2 * centreline_length + 4.0 * math.pi * radius**3 / 3.0


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable raster audit: {OUTPUT}")
    manifest, completion, placement, release = map(load, (MANIFEST, COMPLETION, PLACEMENT, RASTER_RELEASE))
    checks = {
        "schema_exact": manifest.get("schema") == "lbs.stage34c-cpd4-cpd6-fragment-raster-geometry.v1",
        "completion_passed": completion.get("passed") is True,
        "completion_binds_manifest": completion.get("raster_manifest_sha256") == sha(MANIFEST),
        "completion_binds_metrics_csv": completion.get("raster_metrics_csv_sha256") == sha(GEOMETRY_DIR / "raster_metrics.csv"),
        "all_source_bindings_verified": all(check_binding(binding) for binding in manifest["source_bindings"].values()),
        "metrics_csv_binding_verified": check_binding(manifest["raster_metrics_csv"]),
        "raster_release_passed": release.get("passed") is True and release["authority"].get("geometry_rasterization") is True,
        "manifest_binds_superseding_placement": manifest["source_bindings"]["placement"]["sha256"] == sha(PLACEMENT),
        "exact_twelve_cases": len(manifest["cases"]) == 12,
        "gpu_flow_not_authorized": manifest["authority"].get("gpu_flow_execution") is False,
        "cpd6_flow_not_authorized": manifest["authority"].get("cpd6_flow_execution") is False,
        "claim_boundary_unchanged": manifest["claim_boundary"] == placement["claim_boundary"],
    }
    case_rows = {row["case_id"]: row for row in manifest["cases"]}
    source_contexts = {(row["packing_id"], row["placement_block"]): row for row in manifest["source_contexts"]}
    selected_anchors = {
        (packing, block): placement["packings"][packing]["blocks"][block]["anchors"]
        for packing in PACKINGS for block in BLOCKS
    }

    artifact_hashes = True
    array_schema = True
    sand_identity = True
    full_segment_reproduction = True
    counts_reproduced = True
    volume_gate = True
    resolution_gate = True
    orientation_gate = True
    topology_gate = True
    transform_gate = True
    radius_gate = True
    fragment_count_gate = True
    no_overlap_gate = True
    sand_intersection_gate = True
    case_checks_match = True
    audit_rows = []
    context_arrays = {}
    analytic_volume_deviations = []

    for packing in PACKINGS:
        for block in BLOCKS:
            intact_id = f"s34c_{packing}_{block}_p4_frag1_cpd4"
            source = source_contexts[(packing, block)]
            source_cpd4 = arrays(Path(source["source_geometry"]["path"]))
            context_arrays[(packing, block, 186)] = source_cpd4
            intact_cpd6_path = Path(manifest["artifacts"][intact_id]["cpd6_geometry"])
            context_arrays[(packing, block, 279)] = arrays(intact_cpd6_path)

    for case_id, row in case_rows.items():
        packing, block, fragments = row["packing_id"], row["placement_block"], int(row["fragments_per_parent"])
        artifact = manifest["artifacts"][case_id]
        cpd4_path, cpd6_path = Path(artifact["cpd4_geometry"]), Path(artifact["cpd6_geometry"])
        artifact_hashes &= (
            cpd4_path.is_file() and cpd6_path.is_file()
            and sha(cpd4_path) == artifact["cpd4_geometry_sha256"]
            and sha(cpd6_path) == artifact["cpd6_geometry_sha256"]
        )
        data_by_resolution = {186: arrays(cpd4_path), 279: arrays(cpd6_path)}
        independently = {}
        for resolution, data in data_by_resolution.items():
            material = np.asarray(data["material"], dtype=np.uint8)
            phase = np.asarray(data["phase"], dtype=np.uint8)
            lines = np.asarray(data["fibre_centrelines_m"], dtype=float)
            radius = float(data["fibre_radius_m"][0])
            length = float(data["cell_length_m"][0])
            reference_sand = np.asarray(context_arrays[(packing, block, resolution)]["material"], dtype=np.uint8) == 1
            stage34_metadata = (
                int(data["fragments_per_parent"][0]) == fragments
                and math.isclose(float(data["uniform_length_multiplier"][0]), float(row["uniform_length_multiplier"]), rel_tol=0.0, abs_tol=1.0e-14)
            ) if "fragments_per_parent" in data and "uniform_length_multiplier" in data else (
                fragments == 1 and resolution == 186 and bool(artifact["cpd4_reused_accepted_intact"])
            )
            array_schema &= (
                material.shape == (resolution, resolution, resolution)
                and phase.shape == material.shape
                and lines.shape == (4 * fragments, 37, 3)
                and set(np.unique(material)).issubset({0, 1, 2})
                and np.array_equal(phase, np.where(material != 0, 2, 0).astype(np.uint8))
                and math.isclose(float(data["spacing_m"][0]), length / resolution, rel_tol=0.0, abs_tol=1.0e-15)
                and stage34_metadata
            )
            sand_identity &= np.array_equal(material == 1, reference_sand)
            radius_gate &= math.isclose(radius, RADIUS_M, rel_tol=0.0, abs_tol=0.0)
            rerasterized_material, metrics = rerasterize(lines, reference_sand, radius, length)
            independently[resolution] = metrics
            full_segment_reproduction &= np.array_equal(rerasterized_material, material)
            recorded = row[f"cpd{4 if resolution == 186 else 6}_metrics"]
            counts_reproduced &= (
                metrics["fibre_only_voxel_count"] == int(recorded["fibre_only_voxel_count"])
                and metrics["sand_intersection_voxel_count"] == int(recorded["sand_intersection_voxel_count"])
                and metrics["orientation_order"] == recorded["orientation_order"]
                and all(value == 0 for value in metrics["incremental_overlap_voxel_counts"])
                and all(value == 0 for value in metrics["incremental_face_adjacency_counts"])
            )
            no_overlap_gate &= (
                all(value == 0 for value in metrics["incremental_overlap_voxel_counts"])
                and all(value == 0 for value in metrics["incremental_face_adjacency_counts"])
                and metrics["distinct_fragment_masks"]
            )
            topology_gate &= (
                metrics["connectivity"]["largest_fluid_component_fraction"] >= 0.99
                and all(metrics["connectivity"]["largest_component_spans_xyz_nonperiodic"])
            )
        target_186 = int(row["target_intact_fibre_only_voxel_count_cpd4"])
        count_186 = independently[186]["fibre_only_voxel_count"]
        count_279 = independently[279]["fibre_only_voxel_count"]
        intact_279 = int(source_contexts[(packing, block)]["rebuilt_intact_fibre_only_voxel_count_cpd6"])
        ratio_186 = count_186 / target_186
        ratio_279 = count_279 / intact_279
        ratio_shift = abs(ratio_279 - ratio_186)
        tolerance = max(1.0, 0.005 * target_186)
        volume_gate &= abs(count_186 - target_186) <= tolerance
        resolution_gate &= ratio_shift <= 0.02
        orientation_gate &= independently[186]["orientation_order"] == independently[279]["orientation_order"]
        source_int_186 = int(row["cpd4_metrics"]["source_intact_sand_intersection_voxel_count"])
        source_int_279 = int(row["cpd6_metrics"]["source_intact_sand_intersection_voxel_count"])
        sand_intersection_gate &= (
            independently[186]["sand_intersection_voxel_count"] <= source_int_186
            and independently[279]["sand_intersection_voxel_count"] <= source_int_279
        )
        fragment_count_gate &= independently[186]["distinct_fragment_masks"] and independently[279]["distinct_fragment_masks"]

        transforms = manifest["transforms"][case_id]
        if fragments == 1:
            transform_gate &= transforms == [] and bool(artifact["cpd4_reused_accepted_intact"])
            analytic_deviation = 0.0
        else:
            anchors = {
                (int(anchor["parent_rank"]), int(anchor["child_rank"])): anchor
                for anchor in selected_anchors[(packing, block)]
                if int(anchor["child_rank"]) <= fragments
            }
            transform_gate &= len(transforms) == 4 * fragments and not bool(artifact["cpd4_reused_accepted_intact"])
            source_lengths = {}
            fragment_volume = 0.0
            for record in transforms:
                key = (int(record["parent_rank"]), int(record["child_rank"]))
                anchor = anchors.get(key)
                rotation = np.asarray(record["rotation_matrix"], dtype=float)
                translation = np.asarray(record["translation_m"], dtype=float)
                source_centre = np.asarray(record["source_crop_centre_m"], dtype=float)
                target_centre = np.asarray(record["target_centre_m"], dtype=float)
                source_direction = np.asarray(record["source_direction"], dtype=float)
                target_direction = np.asarray(record["target_direction"], dtype=float)
                transform_gate &= (
                    anchor is not None
                    and int(record["target_face_index"]) == int(anchor["face_index"])
                    and np.allclose(rotation.T @ rotation, np.eye(3), rtol=0.0, atol=1.0e-12)
                    and math.isclose(float(np.linalg.det(rotation)), 1.0, rel_tol=0.0, abs_tol=1.0e-12)
                    and np.allclose(rotation @ source_direction, target_direction, rtol=0.0, atol=1.0e-12)
                    and np.allclose(rotation @ source_centre + translation, target_centre, rtol=0.0, atol=1.0e-12)
                    and math.isclose(
                        float(record["selected_piece_contour_length_m"]),
                        float(record["base_equal_volume_piece_length_m"]) * float(row["uniform_length_multiplier"]),
                        rel_tol=1.0e-10, abs_tol=1.0e-14,
                    )
                )
                source_lengths[int(record["parent_rank"])] = float(record["source_parent_contour_length_m"])
                fragment_volume += capsule_volume(RADIUS_M, float(record["selected_piece_contour_length_m"]))
            parent_volume = sum(capsule_volume(RADIUS_M, length) for length in source_lengths.values())
            analytic_deviation = fragment_volume / parent_volume - 1.0
        analytic_volume_deviations.append(abs(analytic_deviation))
        case_checks_match &= all(row["checks"].values())
        audit_rows.append({
            "case_id": case_id,
            "packing_id": packing,
            "placement_block": block,
            "fragments_per_parent": fragments,
            "uniform_length_multiplier": float(row["uniform_length_multiplier"]),
            "cpd4_fibre_only_voxel_count": count_186,
            "cpd6_fibre_only_voxel_count": count_279,
            "cpd4_volume_ratio": ratio_186,
            "cpd6_volume_ratio": ratio_279,
            "absolute_volume_ratio_shift": ratio_shift,
            "analytical_capsule_volume_deviation_from_intact": analytic_deviation,
            "orientation_order": independently[186]["orientation_order"],
            "fluid_component_fraction_cpd4": independently[186]["connectivity"]["largest_fluid_component_fraction"],
            "fluid_component_fraction_cpd6": independently[279]["connectivity"]["largest_fluid_component_fraction"],
        })

    checks.update({
        "all_artifact_hashes_verified": artifact_hashes,
        "all_npz_schemas_and_phase_maps_valid": array_schema,
        "sand_masks_exact_within_context": sand_identity,
        "all_masks_reproduced_with_full_37_point_rasterization": full_segment_reproduction,
        "recorded_counts_and_orders_reproduced": counts_reproduced,
        "all_cpd4_solver_volume_gates_passed": volume_gate,
        "all_cpd4_cpd6_ratio_shifts_le_0p02": resolution_gate,
        "all_orientation_orders_stable": orientation_gate,
        "all_fluid_topology_gates_passed": topology_gate,
        "all_rigid_transforms_reproduced": transform_gate,
        "radius_exactly_50_um_everywhere": radius_gate,
        "all_fragment_counts_and_masks_distinct": fragment_count_gate,
        "no_fragment_overlap_or_face_adjacency": no_overlap_gate,
        "sand_intersection_not_greater_than_intact": sand_intersection_gate,
        "all_builder_case_checks_true": case_checks_match,
        "exact_four_reused_and_eight_new_cpd4": (
            sum(int(value["cpd4_reused_accepted_intact"]) for value in manifest["artifacts"].values()) == 4
            and sum(int(not value["cpd4_reused_accepted_intact"]) for value in manifest["artifacts"].values()) == 8
        ),
    })
    passed = all(checks.values())
    status = "passed_raster_audit_gpu_configuration_authorized" if passed else "failed_raster_audit_fail_closed"
    authority = {
        "gpu_flow_configuration": passed,
        "independent_gpu_release": False,
        "gpu_flow_execution": False,
        "cpd6_flow_execution": False,
        "mechanics_or_coupling": False,
    }
    audit = {
        "schema": "lbs.stage34c-cpd4-cpd6-fragment-raster-audit.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": status,
        "checks": checks,
        "cases": audit_rows,
        "summary": {
            "case_count": len(audit_rows),
            "maximum_absolute_cpd4_volume_error_voxels": max(abs(row["cpd4_fibre_only_voxel_count"] - case_rows[row["case_id"]]["target_intact_fibre_only_voxel_count_cpd4"]) for row in audit_rows),
            "maximum_absolute_cpd4_to_cpd6_volume_ratio_shift": max(row["absolute_volume_ratio_shift"] for row in audit_rows),
            "maximum_absolute_analytical_capsule_volume_deviation": max(analytic_volume_deviations),
            "minimum_fluid_component_fraction": min(min(row["fluid_component_fraction_cpd4"], row["fluid_component_fraction_cpd6"]) for row in audit_rows),
        },
        "source_bindings": {
            "raster_manifest": {"path": str(MANIFEST.resolve()), "sha256": sha(MANIFEST)},
            "raster_completion": {"path": str(COMPLETION.resolve()), "sha256": sha(COMPLETION)},
            "superseding_placement": {"path": str(PLACEMENT.resolve()), "sha256": sha(PLACEMENT)},
            "raster_release": {"path": str(RASTER_RELEASE.resolve()), "sha256": sha(RASTER_RELEASE)},
            "geometry_api": {"path": str(Path(api.__file__).resolve()), "sha256": sha(Path(api.__file__).resolve())},
            "auditor": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).resolve())},
        },
        "authority": authority,
        "claim_boundary": manifest["claim_boundary"],
        "limitation": "Solver-resolved PET volume is fixed at CPD4. Geometry-only length multipliers introduce the separately reported analytical capsule-volume deviation; no flow or experimental claim follows from this audit.",
    }
    OUTPUT.mkdir(parents=True)
    audit_path = OUTPUT / "raster_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    completion_out = {
        "schema": audit["schema"] + ".completion",
        "passed": passed,
        "status": status,
        "raster_audit_sha256": sha(audit_path),
        "checks": checks,
        "authority": authority,
    }
    (OUTPUT / "completion.json").write_text(json.dumps(completion_out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "passed": passed,
        "status": status,
        "failed_checks": [name for name, value in checks.items() if not value],
        "summary": audit["summary"],
    }, indent=2, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
