#!/usr/bin/env python3
"""Refine the immutable Stage27a masks from CPD2 to CPD4."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import build_stage27a_mechanics_hydraulic_masks_v1 as base


ROOT = Path(__file__).resolve().parents[1]
STUDY_A = "stage27a_stage26x_mechanics_hydraulic_bridge_20260823"
STUDY_B = "stage27b_stage26x_mechanics_hydraulic_cpd4_20260824"
SOURCE_CONFIG = ROOT / "stage27_designs" / STUDY_A / "geometry_01/resolved_config.json"
SOURCE_EVALUATION = ROOT / "stage27_evaluations" / STUDY_A / "evaluation_01/evaluation.json"
SOURCE_CHECKPOINT = SOURCE_EVALUATION.parent / "checkpoint_manifest.json"
SOURCE_COMPLETION = ROOT / "stage27_runs" / STUDY_A / "gpu_pilot_01/completion.json"
OUTPUT = ROOT / "stage27_designs" / STUDY_B / "geometry_01"
EXTERNAL_CONFIG = Path(r"C:\Users\wonjuncha-admin\Documents\Codex\2026-07-19\skill-creator-c-users-wonjuncha-admin\yade_benchmark\lbs_calibration\configs\lbs_stage24e_lbs_f37_selected_cpd4_gpu_v1.json")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUTPUT}")
    sources = {"cpd2_config": SOURCE_CONFIG, "cpd2_evaluation": SOURCE_EVALUATION, "cpd2_checkpoint": SOURCE_CHECKPOINT, "cpd2_completion": SOURCE_COMPLETION, "stage24e_config": EXTERNAL_CONFIG}
    observed = {key: digest(path) for key, path in sources.items()}
    expected = {
        "cpd2_evaluation": "436eeb64970b460823c779bfac6211dc1623430d955f79b81c19299f4cfcfc74",
        "cpd2_checkpoint": "4f37339083aa23b705b55c0d8648b0a86e2aeca5039880b0052936dbde0ed43c",
        "stage24e_config": "24251fcc945853013a83670258f5a8243937a1a68169b7116ab7e4e49068d22b",
    }
    mismatch = [key for key, value in expected.items() if observed[key] != value]
    if mismatch:
        raise RuntimeError(f"immutable source mismatch: {mismatch}")
    source, evaluation, checkpoint, cpd2 = load(SOURCE_CONFIG), load(SOURCE_EVALUATION), load(SOURCE_CHECKPOINT), load(SOURCE_COMPLETION)
    stage24e = load(EXTERNAL_CONFIG)
    if not (evaluation.get("passed") and checkpoint.get("passed") and evaluation["authority"]["cpd4_confirmation_design"]):
        raise RuntimeError("Stage27a does not authorize the CPD4 design")
    if evaluation["authority"]["cpd4_execution"]:
        raise RuntimeError("unexpected Stage27a execution authority")
    clean_cpd2 = Path(source["geometry"]["artifacts"]["clean"]["geometry"])
    with np.load(clean_cpd2, allow_pickle=False) as archive:
        length = float(archive["cell_length_m"][0])
        original_cell = np.asarray(archive["original_cell_lengths_m"], dtype=float)
        affine = np.asarray(archive["affine_scale_xyz"], dtype=float)
        centres = np.asarray(archive["sand_centres_m"], dtype=float)
        radii = np.asarray(archive["sand_radii_m"], dtype=float)
        fibre_radius = float(archive["fibre_radius_m"][0])
    n = 186
    spacing = length / n
    sand = np.zeros((n, n, n), dtype=bool)
    base.mark_spheres(sand, centres, radii, length)
    OUTPUT.mkdir(parents=True)
    rows, artifacts = [], {}
    sand_count = int(np.count_nonzero(sand))
    for case_id in ("clean", "open", "constricted"):
        with np.load(Path(source["geometry"]["artifacts"][case_id]["geometry"]), allow_pickle=False) as old:
            fibre_points = np.asarray(old["fibre_centrelines_m"], dtype=float)
        fibre = np.zeros_like(sand)
        if fibre_points.size:
            base.mark_capsule(fibre, fibre_points, fibre_radius, length)
        fibre_only = fibre & ~sand
        solid = sand | fibre_only
        phase = np.where(solid, 2, 0).astype(np.uint8)
        material = np.zeros_like(phase)
        material[sand] = 1
        material[fibre_only] = 2
        connectivity = base.connectivity(solid)
        case_dir = OUTPUT / case_id
        case_dir.mkdir()
        geometry_path = case_dir / "geometry_cpd4.npz"
        np.savez_compressed(geometry_path, phase=phase, material=material, spacing_m=np.asarray([spacing]), cell_length_m=np.asarray([length]), original_cell_lengths_m=original_cell, affine_scale_xyz=affine, sand_centres_m=centres, sand_radii_m=radii, fibre_centrelines_m=fibre_points, fibre_radius_m=np.asarray([fibre_radius]))
        vtk_path = case_dir / "material.vtk"
        base.write_vtk(vtk_path, material, spacing)
        checks = {"sand_identity": int(np.count_nonzero(material == 1)) == sand_count, "fibre_positive_or_clean": case_id == "clean" or int(np.count_nonzero(fibre_only)) > 0, "fluid_connected_99pct": connectivity["largest_fluid_component_fraction"] >= 0.99, "fluid_spans_xyz": all(connectivity["largest_component_spans_xyz_nonperiodic"])}
        artifacts[case_id] = {"geometry": str(geometry_path.resolve()), "geometry_sha256": digest(geometry_path), "material_vtk": str(vtk_path.resolve()), "material_vtk_sha256": digest(vtk_path)}
        rows.append({"case_id": case_id, "sand_voxel_count": sand_count, "fibre_only_voxel_count": int(np.count_nonzero(fibre_only)), "voxel_porosity": float(np.mean(~solid)), "connectivity": connectivity, "checks": checks})
    cpd2_rows = {row["case_id"]: row for row in source["geometry"]["cases"]}
    global_checks = {"case_count_three": len(rows) == 3, "sand_particle_count_216": centres.shape == (216, 3), "resolution_exact_double": n == 2 * int(source["geometry"]["resolution"][0]), "fibre_diameter_cells_at_least_3p9": 2 * fibre_radius / spacing >= 3.9, "all_case_checks": all(all(row["checks"].values()) for row in rows), "sand_voxel_identity": len({row["sand_voxel_count"] for row in rows}) == 1, "cpd2_warm_starts_present": all((ROOT / "stage27_runs" / STUDY_A / "gpu_pilot_01" / cpd2["paired_results"][i]["solver_case_id"] / "final_fields.npz").is_file() for i in range(3))}
    if not all(global_checks.values()):
        raise RuntimeError(f"CPD4 geometry checks failed: {global_checks}")
    warm = {}
    for row in cpd2["paired_results"]:
        path = ROOT / "stage27_runs" / STUDY_A / "gpu_pilot_01" / row["solver_case_id"] / "final_fields.npz"
        warm[row["case_id"]] = {"path": str(path.resolve()), "sha256": digest(path), "velocity_scale": float(stage24e["solver"]["warm_start_velocity_scale"]), "density_deviation_scale": float(stage24e["solver"]["warm_start_density_deviation_scale"])}
    config = {"schema": "lbs.stage27b-stage26x-mechanics-hydraulic-cpd4.v1", "status": "cpd4_geometry_preflight_passed_independent_release_required", "research_question": "Does CPD4 preserve the Stage27a CPD2 single-fibre obstruction signs and the deflected-minus-open placement contrast within frozen numerical bounds?", "claim_boundary": "Three-case CPD4 fixed-solid solution verification only; no physical concentration law, absolute-permeability validation, mobile sand, clogging evolution or two-way coupling.", "solver": stage24e["solver"], "acceptance": {**stage24e["acceptance"], "maximum_absolute_single_fibre_ratio_shift": 0.002, "maximum_absolute_placement_contrast_shift": 0.001, "require_both_obstruction_signs": True, "require_deflected_more_obstructive": True}, "execution": stage24e["execution"], "fluid": source["fluid"], "geometry": {"resolution": [n, n, n], "spacing_m": spacing, "equivalent_cell_length_m": length, "fibre_diameter_cells": 2 * fibre_radius / spacing, "cases": rows, "artifacts": artifacts}, "cpd2_reference": {"paired_results": cpd2["paired_results"], "warm_starts": warm}, "lineage": {**{key: {"path": str(path.resolve()), "sha256": observed[key]} for key, path in sources.items()}, **{key: source["lineage"][key] for key in ("stage13_qualification", "stage13_execution_manifest", "stage13_runner", "cuda_source")}, "qualified_ptx_sha256": source["lineage"]["qualified_ptx_sha256"]}, "authority": {"independent_design_audit": True, "gpu_cpd4_execution": False, "render": False, "concentration_campaign": False, "mobile_sand": False, "two_way_coupling": False}}
    config_path = OUTPUT / "resolved_config.json"
    write(config_path, config)
    completion = {"schema": config["schema"] + ".geometry-completion", "status": "passed_cpd4_geometry_preflight_independent_release_required", "passed": True, "timestamp_utc": datetime.now(timezone.utc).isoformat(), "config_sha256": digest(config_path), "builder_sha256": digest(Path(__file__).resolve()), "checks": global_checks, "cases": rows, "artifacts": artifacts, "next_handoff": {"authorized": "independent design audit", "not_authorized": "GPU execution before audit release, concentration campaign, mobile mechanics or two-way coupling"}}
    completion_path = OUTPUT / "completion.json"
    write(completion_path, completion)
    print(json.dumps({"passed": True, "config": str(config_path), "config_sha256": digest(config_path), "completion": str(completion_path), "completion_sha256": digest(completion_path), "cases": rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

