#!/usr/bin/env python3
"""Build fail-closed CPD2 masks for accepted Stage28a two-fibre mechanics."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
sys.path.insert(0, str(ROOT / "stage27_staging"))
import build_stage27a_mechanics_hydraulic_masks_v1 as geometry_api  # noqa: E402

RESULT = ROOT / "stage28_runs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_02/result.json"
EVALUATION = ROOT / "stage28_evaluations/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_evaluation_02/evaluation.json"
CHECKPOINT = ROOT / "stage28_evaluations/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_evaluation_02/checkpoint_manifest.json"
CONTRACT = ROOT / "stage28_staging/STAGE28B_TWO_FIBRE_CPD2_HYDRAULIC_CONTRACT.md"
STAGE27_CONFIG = ROOT / "stage27_designs/stage27a_stage26x_mechanics_hydraulic_bridge_20260823/geometry_01/resolved_config.json"
CLEAN_GEOMETRY = ROOT / "stage27_designs/stage27a_stage26x_mechanics_hydraulic_bridge_20260823/geometry_01/clean/geometry_cpd2.npz"
GEOMETRY_API = ROOT / "stage27_staging/build_stage27a_mechanics_hydraulic_masks_v1.py"
OUTPUT = ROOT / "stage28_designs/stage28b_two_fibre_cpd2_hydraulic_20260824/geometry_01"
EXPECTED = {
    RESULT: "af5d50d906bfcc681f0970a0150e9c8a0b0f9dd291e99a681ec69ff689f87852",
    EVALUATION: "d9559faf168bbd17956688d33308e2b53949b70f647337077b1cd8576e037169",
    CHECKPOINT: "df1d881d009ae1c53ca0740fbf83a7d84dd06b6149e39a77edde54612c1b5eda",
    STAGE27_CONFIG: "3712873b744d0565b795f9c6c6ab2e2bf821f5239c6d95f928ea38cd43506482",
    CLEAN_GEOMETRY: "c7d2914d5351b1dc2178e5ca1679f092183cb1b11c163c7840d62b66af278d56",
    GEOMETRY_API: "92163d42d54960208ea5ac9efd132e23413cb7f08a1c8ca934ff6e18cc2bd6f1",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def bind(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": sha(path)}


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUTPUT}")
    mismatches = [str(path) for path, expected in EXPECTED.items() if sha(path) != expected]
    if mismatches:
        raise RuntimeError("source hash mismatch: " + ", ".join(mismatches))
    result, evaluation, stage27 = map(load, (RESULT, EVALUATION, STAGE27_CONFIG))
    if not (result["passed"] and evaluation["passed"] and all(evaluation["checks"].values())):
        raise RuntimeError("accepted Stage28a mechanics checkpoint is absent")
    with np.load(CLEAN_GEOMETRY) as data:
        clean_phase = np.asarray(data["phase"], dtype=np.uint8)
        clean_material = np.asarray(data["material"], dtype=np.uint8)
        spacing = float(data["spacing_m"][0])
        length = float(data["cell_length_m"][0])
        affine = np.asarray(data["affine_scale_xyz"], dtype=float)
        sand_centres = np.asarray(data["sand_centres_m"], dtype=float)
        sand_radii = np.asarray(data["sand_radii_m"], dtype=float)
        original_cell = np.asarray(data["original_cell_lengths_m"], dtype=float)
    sand = clean_material == 1
    by_id = {case["case_id"]: case for case in result["cases"]}
    case_ids = ["clean", "separated_open_open", "separated_open_constricted", "crossing_interaction"]
    radius = 0.5 * float(stage27["geometry"]["fibre_diameter_cells"]) * spacing
    OUTPUT.mkdir(parents=True)
    artifacts, rows = {}, []
    for case_id in case_ids:
        fibre_masks, centrelines = [], []
        if case_id != "clean":
            for fibre in by_id[case_id]["terminal_fibres"]:
                points = np.asarray(fibre["terminal_node_positions_m"], dtype=float) * affine
                mask = np.zeros_like(sand)
                geometry_api.mark_capsule(mask, points, radius, length)
                fibre_masks.append(mask)
                centrelines.append(points)
        union = np.zeros_like(sand)
        for mask in fibre_masks:
            union |= mask
        fibre_only = union & ~sand
        solid = sand | fibre_only
        material = np.zeros_like(clean_material)
        material[sand] = 1
        material[fibre_only] = 2
        phase = np.where(solid, 2, 0).astype(np.uint8)
        conn = geometry_api.connectivity(solid)
        individual = [int(np.count_nonzero(mask & ~sand)) for mask in fibre_masks]
        overlap = int(np.count_nonzero(fibre_masks[0] & fibre_masks[1] & ~sand)) if len(fibre_masks) == 2 else 0
        checks = {
            "clean_sand_exact": np.array_equal(sand, clean_material == 1),
            "clean_phase_exact_or_two_fibres": np.array_equal(phase, clean_phase) if case_id == "clean" else len(fibre_masks) == 2,
            "two_37_node_centrelines_or_clean": case_id == "clean" or all(array.shape == (37, 3) for array in centrelines),
            "each_fibre_positive_voxels_or_clean": case_id == "clean" or all(value > 0 for value in individual),
            "fluid_connected_99pct": conn["largest_fluid_component_fraction"] >= 0.99,
            "fluid_spans_xyz": all(conn["largest_component_spans_xyz_nonperiodic"]),
        }
        case_dir = OUTPUT / case_id
        case_dir.mkdir()
        geometry = case_dir / "geometry_cpd2.npz"
        np.savez_compressed(geometry, phase=phase, material=material, spacing_m=np.asarray([spacing]),
            cell_length_m=np.asarray([length]), original_cell_lengths_m=original_cell,
            affine_scale_xyz=affine, sand_centres_m=sand_centres, sand_radii_m=sand_radii,
            fibre_centrelines_m=np.asarray(centrelines, dtype=float).reshape((-1, 37, 3)),
            fibre_radius_m=np.asarray([radius]))
        vtk = case_dir / "material.vtk"
        geometry_api.write_vtk(vtk, material, spacing)
        artifacts[case_id] = {"geometry": str(geometry.resolve()), "geometry_sha256": sha(geometry),
                              "material_vtk": str(vtk.resolve()), "material_vtk_sha256": sha(vtk)}
        rows.append({"case_id": case_id, "fibre_count": len(fibre_masks),
                     "fibre_individual_voxel_counts": individual, "fibre_union_only_voxel_count": int(np.count_nonzero(fibre_only)),
                     "fibre_overlap_only_voxel_count": overlap, "sand_voxel_count": int(np.count_nonzero(sand)),
                     "voxel_porosity": float(np.mean(~solid)), "connectivity": conn, "checks": checks})
    checks = {
        "source_hashes_match": not mismatches,
        "exact_four_cases": [row["case_id"] for row in rows] == case_ids,
        "clean_array_identity": np.array_equal(np.load(artifacts["clean"]["geometry"])["phase"], clean_phase),
        "sand_identity_all_cases": len({row["sand_voxel_count"] for row in rows}) == 1,
        "all_case_checks": all(all(row["checks"].values()) for row in rows),
        "fibre_resolution_at_least_1p9_cells": 2 * radius / spacing >= 1.9,
        "mixture_porosity_below_clean": all(rows[0]["voxel_porosity"] > row["voxel_porosity"] for row in rows[1:]),
    }
    if not all(checks.values()):
        raise RuntimeError("Stage28b geometry checks failed")
    config = {
        "schema": "lbs.stage28b-two-fibre-cpd2-hydraulic.v1",
        "status": "geometry_built_independent_gpu_release_required",
        "research_question": "How do accepted separated and crossing two-fibre mechanics states change paired CPD2 permeability relative to identical clean LBS sand?",
        "claim_boundary": "Fixed-solid periodic CPD2 mechanism pilot at approximately 0.0093815 dry-mass percent; no production concentration law, mobile sand, migration, clogging evolution, transient response or two-way coupling.",
        "solver": stage27["solver"], "acceptance": stage27["acceptance"], "execution": stage27["execution"], "fluid": stage27["fluid"],
        "geometry": {"resolution": list(clean_phase.shape[::-1]), "spacing_m": spacing,
                     "equivalent_cell_length_m": length, "fibre_radius_m": radius,
                     "fibre_diameter_cells": 2 * radius / spacing, "cases": rows, "artifacts": artifacts},
        "lineage": {**{key: value for key, value in stage27["lineage"].items()},
                    "stage28_mechanics_result": bind(RESULT),
                    "stage28_mechanics_evaluation": bind(EVALUATION),
                    "stage28_mechanics_checkpoint": bind(CHECKPOINT), "stage28_contract": bind(CONTRACT),
                    "stage27_config": bind(STAGE27_CONFIG), "stage27_clean_geometry": bind(CLEAN_GEOMETRY),
                    "stage27_geometry_api": bind(GEOMETRY_API), "stage28_builder": bind(Path(__file__).resolve())},
        "checks": checks,
        "authority": {"independent_gpu_audit": True, "gpu_cpd2_pilot": False, "cpd4": False,
                      "production_concentration_campaign": False, "mobile_sand": False, "two_way_coupling": False},
    }
    config_path = OUTPUT / "resolved_config.json"
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    completion = {"schema": config["schema"] + ".geometry-completion", "status": config["status"],
                  "passed": True, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                  "config_sha256": sha(config_path), "checks": checks, "cases": rows, "artifacts": artifacts,
                  "next_handoff": {"authorized": "independent GPU preflight audit", "not_authorized": "GPU execution"}}
    completion_path = OUTPUT / "completion.json"
    completion_path.write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"config": str(config_path), "config_sha256": sha(config_path),
                      "completion": str(completion_path), "completion_sha256": sha(completion_path),
                      "checks": checks, "cases": rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
