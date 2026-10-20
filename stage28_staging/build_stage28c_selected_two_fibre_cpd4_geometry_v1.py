#!/usr/bin/env python3
"""Build fail-closed selected Stage28c two-fibre CPD4 masks."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
sys.path.insert(0, str(ROOT / "stage27_staging"))
import build_stage27a_mechanics_hydraulic_masks_v1 as api  # noqa: E402

STUDY = "stage28c_selected_two_fibre_cpd4_20260825"
OUTPUT = ROOT / "stage28_designs" / STUDY / "geometry_01"
CPD2_CONFIG = ROOT / "stage28_designs/stage28b_two_fibre_cpd2_hydraulic_20260824/geometry_01/resolved_config.json"
CPD2_COMPLETION = ROOT / "stage28_runs/stage28b_two_fibre_cpd2_hydraulic_20260825/gpu_pilot_01/completion.json"
CPD2_EVALUATION = ROOT / "stage28_evaluations/stage28b_two_fibre_cpd2_hydraulic_20260825/gpu_evaluation_01/evaluation.json"
CPD2_CHECKPOINT = CPD2_EVALUATION.parent / "checkpoint_manifest.json"
CPD4_CONFIG = ROOT / "stage27_designs/stage27b_stage26x_mechanics_hydraulic_cpd4_20260824/geometry_01/resolved_config.json"
CPD4_CLEAN = ROOT / "stage27_designs/stage27b_stage26x_mechanics_hydraulic_cpd4_20260824/geometry_01/clean/geometry_cpd4.npz"
CPD4_COMPLETION = ROOT / "stage27_runs/stage27b_stage26x_mechanics_hydraulic_cpd4_20260824/gpu_confirmation_01/completion.json"
CPD4_EVALUATION = ROOT / "stage27_evaluations/stage27b_stage26x_mechanics_hydraulic_cpd4_20260824/evaluation_01/evaluation.json"
CPD4_CHECKPOINT = CPD4_EVALUATION.parent / "checkpoint_manifest.json"
GEOMETRY_API = ROOT / "stage27_staging/build_stage27a_mechanics_hydraulic_masks_v1.py"
CONTRACT = ROOT / "stage28_staging/STAGE28C_SELECTED_TWO_FIBRE_CPD4_CONTRACT.md"

EXPECTED = {
    CPD2_CONFIG: "5ab84987cde4eb627dabf53ce63b2054872b62f76e51bf3bae85737462ff0135",
    CPD2_COMPLETION: "5edaed57e97744bf58ad6d95c0029f4fbfe29517a843c5f65449ba12992eb9c8",
    CPD2_EVALUATION: "3e9fd130f8a133fbeeb392e826025c9f465a6d35cadc4c5e1bf83873c99cc251",
    CPD2_CHECKPOINT: "c5fe5c29d205b76a8ac50b49039e7b6715aa642d2ac92b4c6ad8e8d78a76c9a1",
    CPD4_CONFIG: "218433a39143c19c3451967e839b25d29cd7360726c3c9662d497480b499821e",
    CPD4_CLEAN: "e0d780f54b433480bb92ef86252d56d9a1066e4542c26b736e71229f3a1c251c",
    CPD4_COMPLETION: "152592f30eacd89f29f312b5ff88594c5b319dfbe7487534a5fe2e27a7df8886",
    CPD4_EVALUATION: "9716701710a31b22608ccabee3686374dff69d50ecbdd78d0e3639670417c380",
    CPD4_CHECKPOINT: "be1ad72c1d6f83a92621693b62bf7145cfab75cef770016834dcc4fa0fa6ba7f",
    GEOMETRY_API: "92163d42d54960208ea5ac9efd132e23413cb7f08a1c8ca934ff6e18cc2bd6f1",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def bind(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": sha(path)}


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def periodic_face_adjacency(first: np.ndarray, second: np.ndarray) -> int:
    return sum(
        int(np.count_nonzero(np.roll(first, shift, axis=axis) & second))
        for axis in range(3) for shift in (-1, 1)
    )


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUTPUT}")
    mismatch = [str(path) for path, expected in EXPECTED.items() if not path.is_file() or sha(path) != expected]
    if mismatch:
        raise RuntimeError("immutable source mismatch: " + ", ".join(mismatch))
    cpd2, cpd2_done, cpd2_eval, cpd2_checkpoint = map(load, (CPD2_CONFIG, CPD2_COMPLETION, CPD2_EVALUATION, CPD2_CHECKPOINT))
    cpd4, cpd4_done, cpd4_eval, cpd4_checkpoint = map(load, (CPD4_CONFIG, CPD4_COMPLETION, CPD4_EVALUATION, CPD4_CHECKPOINT))
    if not all(item.get("passed") for item in (cpd2_done, cpd2_eval, cpd2_checkpoint, cpd4_done, cpd4_eval, cpd4_checkpoint)):
        raise RuntimeError("accepted CPD2 or qualified CPD4 lineage is absent")
    with np.load(CPD4_CLEAN, allow_pickle=False) as data:
        clean_phase = np.asarray(data["phase"], dtype=np.uint8)
        clean_material = np.asarray(data["material"], dtype=np.uint8)
        spacing = float(data["spacing_m"][0])
        length = float(data["cell_length_m"][0])
        original_cell = np.asarray(data["original_cell_lengths_m"], dtype=float)
        affine = np.asarray(data["affine_scale_xyz"], dtype=float)
        sand_centres = np.asarray(data["sand_centres_m"], dtype=float)
        sand_radii = np.asarray(data["sand_radii_m"], dtype=float)
    if clean_phase.shape != (186, 186, 186) or sand_centres.shape != (216, 3):
        raise RuntimeError("unexpected accepted CPD4 clean geometry")
    sand = clean_material == 1
    radius = float(cpd2["geometry"]["fibre_radius_m"])
    cpd2_rows = {row["case_id"]: row for row in cpd2_done["paired_results"]}
    case_ids = ["clean", "separated_open_open", "crossing_interaction"]
    OUTPUT.mkdir(parents=True)
    rows, artifacts, warm_starts = [], {}, {}
    for case_id in case_ids:
        if case_id == "clean":
            artifacts[case_id] = {
                "geometry": str(CPD4_CLEAN.resolve()), "geometry_sha256": sha(CPD4_CLEAN),
                "material_vtk": cpd4["geometry"]["artifacts"]["clean"]["material_vtk"],
                "material_vtk_sha256": cpd4["geometry"]["artifacts"]["clean"]["material_vtk_sha256"],
            }
            centrelines = np.empty((0, 37, 3), dtype=float)
            individual, overlap, adjacency = [], 0, 0
            material, phase = clean_material, clean_phase
        else:
            source_path = Path(cpd2["geometry"]["artifacts"][case_id]["geometry"])
            with np.load(source_path, allow_pickle=False) as source:
                centrelines = np.asarray(source["fibre_centrelines_m"], dtype=float)
            masks = []
            for points in centrelines:
                mask = np.zeros_like(sand)
                api.mark_capsule(mask, points, radius, length)
                masks.append(mask)
            individual = [int(np.count_nonzero(mask & ~sand)) for mask in masks]
            overlap = int(np.count_nonzero(masks[0] & masks[1]))
            adjacency = periodic_face_adjacency(masks[0], masks[1])
            union = masks[0] | masks[1]
            fibre_only = union & ~sand
            material = np.zeros_like(clean_material)
            material[sand] = 1
            material[fibre_only] = 2
            phase = np.where(material != 0, 2, 0).astype(np.uint8)
            case_dir = OUTPUT / case_id
            case_dir.mkdir()
            geometry_path = case_dir / "geometry_cpd4.npz"
            np.savez_compressed(
                geometry_path, phase=phase, material=material, spacing_m=np.asarray([spacing]),
                cell_length_m=np.asarray([length]), original_cell_lengths_m=original_cell,
                affine_scale_xyz=affine, sand_centres_m=sand_centres, sand_radii_m=sand_radii,
                fibre_centrelines_m=centrelines, fibre_radius_m=np.asarray([radius]),
            )
            vtk_path = case_dir / "material.vtk"
            api.write_vtk(vtk_path, material, spacing)
            artifacts[case_id] = {
                "geometry": str(geometry_path.resolve()), "geometry_sha256": sha(geometry_path),
                "material_vtk": str(vtk_path.resolve()), "material_vtk_sha256": sha(vtk_path),
            }
        solid = phase != 0
        conn = api.connectivity(solid)
        checks = {
            "sand_exact": np.array_equal(material == 1, sand),
            "clean_exact_or_two_centrelines": np.array_equal(phase, clean_phase) if case_id == "clean" else centrelines.shape == (2, 37, 3),
            "each_fibre_positive_or_clean": case_id == "clean" or all(value > 0 for value in individual),
            "fluid_connected_99pct": conn["largest_fluid_component_fraction"] >= 0.99,
            "fluid_spans_xyz": all(conn["largest_component_spans_xyz_nonperiodic"]),
            "separated_noncontacting_or_other": case_id != "separated_open_open" or (overlap == 0 and adjacency == 0),
            "crossing_contact_resolved_or_other": case_id != "crossing_interaction" or (overlap > 0 or adjacency > 0),
        }
        rows.append({
            "case_id": case_id, "fibre_count": 0 if case_id == "clean" else 2,
            "fibre_individual_voxel_counts": individual,
            "fibre_union_only_voxel_count": int(np.count_nonzero(material == 2)),
            "fibre_raw_overlap_voxel_count": overlap, "periodic_face_adjacency_count": adjacency,
            "sand_voxel_count": int(np.count_nonzero(sand)), "voxel_porosity": float(np.mean(~solid)),
            "connectivity": conn, "checks": checks,
        })
        warm_path = ROOT / "stage28_runs/stage28b_two_fibre_cpd2_hydraulic_20260825/gpu_pilot_01" / cpd2_rows[case_id]["solver_case_id"] / "final_fields.npz"
        warm_starts[case_id] = {
            "path": str(warm_path.resolve()), "sha256": sha(warm_path),
            "velocity_scale": float(cpd4["solver"]["warm_start_velocity_scale"]),
            "density_deviation_scale": float(cpd4["solver"]["warm_start_density_deviation_scale"]),
        }
    global_checks = {
        "exact_selected_cases": [row["case_id"] for row in rows] == case_ids,
        "resolution_exact_double": list(clean_phase.shape) == [2 * x for x in cpd2["geometry"]["resolution"]],
        "fibre_diameter_cells_at_least_3p9": 2 * radius / spacing >= 3.9,
        "clean_geometry_byte_identical_stage27b": sha(Path(artifacts["clean"]["geometry"])) == EXPECTED[CPD4_CLEAN],
        "sand_identity_all_cases": len({row["sand_voxel_count"] for row in rows}) == 1,
        "all_case_checks": all(all(row["checks"].values()) for row in rows),
        "all_warm_starts_bound": all(Path(value["path"]).is_file() and sha(Path(value["path"])) == value["sha256"] for value in warm_starts.values()),
    }
    if not all(global_checks.values()):
        raise RuntimeError(f"Stage28c CPD4 geometry checks failed: {global_checks}")
    acceptance = dict(cpd4["acceptance"])
    acceptance.update({
        "maximum_absolute_two_fibre_ratio_shift": 0.002,
        "maximum_absolute_crossing_minus_separated_contrast_shift": 0.001,
        "maximum_relative_clean_reproduction_error": 1e-12,
        "require_both_obstruction_signs": True,
        "require_crossing_more_obstructive": True,
    })
    lineage = {
        "stage28b_cpd2_config": bind(CPD2_CONFIG), "stage28b_cpd2_completion": bind(CPD2_COMPLETION),
        "stage28b_cpd2_evaluation": bind(CPD2_EVALUATION), "stage28b_cpd2_checkpoint": bind(CPD2_CHECKPOINT),
        "stage27b_cpd4_config": bind(CPD4_CONFIG), "stage27b_clean_cpd4_geometry": bind(CPD4_CLEAN),
        "stage27b_cpd4_completion": bind(CPD4_COMPLETION), "stage27b_cpd4_evaluation": bind(CPD4_EVALUATION),
        "stage27b_cpd4_checkpoint": bind(CPD4_CHECKPOINT), "geometry_api": bind(GEOMETRY_API),
        "contract": bind(CONTRACT), "builder": bind(Path(__file__).resolve()),
        "cuda_source": cpd4["lineage"]["cuda_source"],
        "stage13_qualification": cpd4["lineage"]["stage13_qualification"],
        "stage13_execution_manifest": cpd4["lineage"]["stage13_execution_manifest"],
        "stage13_runner": cpd4["lineage"]["stage13_runner"],
        "qualified_ptx_sha256": cpd4["lineage"]["qualified_ptx_sha256"],
    }
    config = {
        "schema": "lbs.stage28c-selected-two-fibre-cpd4.v1",
        "status": "cpd4_geometry_built_independent_gpu_release_required",
        "research_question": "Are the accepted separated and crossing two-fibre CPD2 permeability effects stable at CPD4?",
        "claim_boundary": "Three-case fixed-solid solution verification only; no concentration law, mobile sand, migration, clogging, transient response or two-way coupling.",
        "solver": cpd4["solver"], "acceptance": acceptance, "execution": cpd4["execution"], "fluid": cpd4["fluid"],
        "geometry": {"resolution": [186, 186, 186], "spacing_m": spacing, "equivalent_cell_length_m": length,
                     "fibre_radius_m": radius, "fibre_diameter_cells": 2 * radius / spacing,
                     "cases": rows, "artifacts": artifacts},
        "cpd2_reference": {"paired_results": [cpd2_rows[case] for case in case_ids], "warm_starts": warm_starts},
        "accepted_clean_cpd4": {"conductance_proxy_lu": float(cpd4_done["paired_results"][0]["conductance_proxy_lu"]),
                                "intrinsic_permeability_m2": float(cpd4_done["paired_results"][0]["intrinsic_permeability_m2"])},
        "lineage": lineage, "checks": global_checks,
        "authority": {"independent_design_audit": True, "gpu_cpd4_execution": False, "render": False,
                      "production_concentration_campaign": False, "mobile_sand": False, "two_way_coupling": False},
    }
    config_path = OUTPUT / "resolved_config.json"
    write(config_path, config)
    completion = {
        "schema": config["schema"] + ".geometry-completion", "status": config["status"], "passed": True,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "config_sha256": sha(config_path),
        "builder_sha256": sha(Path(__file__).resolve()), "checks": global_checks, "cases": rows, "artifacts": artifacts,
        "next_handoff": {"authorized": "independent design audit", "not_authorized": "GPU execution before audit release"},
    }
    completion_path = OUTPUT / "completion.json"
    write(completion_path, completion)
    print(json.dumps({"passed": True, "config": str(config_path), "config_sha256": sha(config_path),
                      "completion": str(completion_path), "completion_sha256": sha(completion_path),
                      "checks": global_checks, "cases": rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
