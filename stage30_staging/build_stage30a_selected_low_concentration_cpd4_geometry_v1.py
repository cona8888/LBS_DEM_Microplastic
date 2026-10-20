#!/usr/bin/env python3
"""Build the fail-closed Stage30a four-case CPD4 geometry checkpoint."""

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

STUDY = "stage30a_selected_low_concentration_cpd4_20260826"
OUTPUT = ROOT / "stage30_designs" / STUDY / "geometry_01"
STAGE29_CONFIG = ROOT / "stage29_designs/stage29e_low_concentration_hydraulic_design_20260826/geometry_01/resolved_config.json"
STAGE29_COMPLETION = ROOT / "stage29_runs/stage29e_low_concentration_hydraulic_design_20260826/gpu_screen_01/completion.json"
STAGE29_EVALUATION = ROOT / "stage29_evaluations/stage29e_low_concentration_hydraulic_design_20260826/hydraulic_evaluation_01/evaluation.json"
STAGE29_CHECKPOINT = STAGE29_EVALUATION.parent / "checkpoint_manifest.json"
STAGE28C_COMPLETION = ROOT / "stage28_runs/stage28c_selected_two_fibre_cpd4_20260825/gpu_confirmation_01/completion.json"
STAGE28C_EVALUATION = ROOT / "stage28_evaluations/stage28c_selected_two_fibre_cpd4_20260825/gpu_evaluation_01/evaluation.json"
STAGE28C_CHECKPOINT = STAGE28C_EVALUATION.parent / "checkpoint_manifest.json"
CPD4_CONFIG = ROOT / "stage27_designs/stage27b_stage26x_mechanics_hydraulic_cpd4_20260824/geometry_01/resolved_config.json"
CPD4_CLEAN = ROOT / "stage27_designs/stage27b_stage26x_mechanics_hydraulic_cpd4_20260824/geometry_01/clean/geometry_cpd4.npz"
CPD4_COMPLETION = ROOT / "stage27_runs/stage27b_stage26x_mechanics_hydraulic_cpd4_20260824/gpu_confirmation_01/completion.json"
CPD4_EVALUATION = ROOT / "stage27_evaluations/stage27b_stage26x_mechanics_hydraulic_cpd4_20260824/evaluation_01/evaluation.json"
CPD4_CHECKPOINT = CPD4_EVALUATION.parent / "checkpoint_manifest.json"
GEOMETRY_API = ROOT / "stage27_staging/build_stage27a_mechanics_hydraulic_masks_v1.py"
CONTRACT = ROOT / "stage30_staging/STAGE30A_SELECTED_LOW_CONCENTRATION_CPD4_CONTRACT.md"

EXPECTED = {
    STAGE29_CONFIG: "43b9a2f810c010f23d8f090af4067f399c7cd52f6907ff47503b5e502bb8dd64",
    STAGE29_COMPLETION: "7bf42821d67da91b5b56f724b186a8cd55ae9f6f5a71ed6b9c7b5149e6eec2a4",
    STAGE29_EVALUATION: "5b4f4d6168f2d20814522bb6b570a1a695585cbcf16bc81b025b8f63de3f518c",
    STAGE29_CHECKPOINT: "4e2b82b858369c8b78ddb59a67dd32896dafd65b95601d81cc0facc06c4c3247",
    STAGE28C_COMPLETION: "90d612d5d16e9905935ed1d237a982ea77bb57594f2581c48a66cca9600e7dab",
    STAGE28C_EVALUATION: "ade8f541cd2d9194ac5ce8b75a3f9dbc1ddd326bf7e0b174117aceac22e2271d",
    STAGE28C_CHECKPOINT: "70a1fa079d8ae10fa1de598ba0461d9770199e32cd269b52743de8272165df4c",
    CPD4_CONFIG: "218433a39143c19c3451967e839b25d29cd7360726c3c9662d497480b499821e",
    CPD4_CLEAN: "e0d780f54b433480bb92ef86252d56d9a1066e4542c26b736e71229f3a1c251c",
    CPD4_COMPLETION: "152592f30eacd89f29f312b5ff88594c5b319dfbe7487534a5fe2e27a7df8886",
    CPD4_EVALUATION: "9716701710a31b22608ccabee3686374dff69d50ecbdd78d0e3639670417c380",
    CPD4_CHECKPOINT: "be1ad72c1d6f83a92621693b62bf7145cfab75cef770016834dcc4fa0fa6ba7f",
    GEOMETRY_API: "92163d42d54960208ea5ac9efd132e23413cb7f08a1c8ca934ff6e18cc2bd6f1",
}

CASES = (
    ("clean", 0, "clean", "clean"),
    ("s29e_f001_isolated_B", 1, "single_isolated", "B"),
    ("s29e_f004_zero_contact_context_B", 4, "zero_contact", "B"),
    ("s29e_f004_one_contact_context_B", 4, "one_contact", "B"),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def bind(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": sha(path)}


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def face_adjacency(first: np.ndarray, second: np.ndarray) -> int:
    return sum(int(np.count_nonzero(np.roll(first, shift, axis=axis) & second)) for axis in range(3) for shift in (-1, 1))


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUTPUT}")
    mismatch = [str(path) for path, expected in EXPECTED.items() if not path.is_file() or sha(path) != expected]
    if mismatch:
        raise RuntimeError("immutable source mismatch: " + ", ".join(mismatch))
    stage29, stage29_done, stage29_eval, stage29_checkpoint = map(load, (STAGE29_CONFIG, STAGE29_COMPLETION, STAGE29_EVALUATION, STAGE29_CHECKPOINT))
    stage28_done, stage28_eval, stage28_checkpoint = map(load, (STAGE28C_COMPLETION, STAGE28C_EVALUATION, STAGE28C_CHECKPOINT))
    cpd4, cpd4_done, cpd4_eval, cpd4_checkpoint = map(load, (CPD4_CONFIG, CPD4_COMPLETION, CPD4_EVALUATION, CPD4_CHECKPOINT))
    if not all(x.get("passed") for x in (stage29_done, stage29_eval, stage29_checkpoint, stage28_done, stage28_eval, stage28_checkpoint, cpd4_done, cpd4_eval, cpd4_checkpoint)):
        raise RuntimeError("accepted CPD2/CPD4 lineage is absent")

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
    radius = float(stage29["geometry"]["fibre_radius_m"])
    cpd2_rows = {row["case_id"]: row for row in stage29_done["paired_results"]}
    source_rows = {row["case_id"]: row for row in stage29["geometry"]["cases"]}
    OUTPUT.mkdir(parents=True)
    rows, artifacts, warm_starts = [], {}, {}
    for run_order, (case_id, fibre_count, topology, block) in enumerate(CASES):
        if case_id == "clean":
            material, phase = clean_material, clean_phase
            centrelines = np.empty((0, 37, 3), dtype=float)
            masks = []
            artifacts[case_id] = {
                "geometry": str(CPD4_CLEAN.resolve()), "geometry_sha256": sha(CPD4_CLEAN),
                "material_vtk": cpd4["geometry"]["artifacts"]["clean"]["material_vtk"],
                "material_vtk_sha256": cpd4["geometry"]["artifacts"]["clean"]["material_vtk_sha256"],
            }
        else:
            source_path = Path(stage29["geometry"]["artifacts"][case_id]["geometry"])
            with np.load(source_path, allow_pickle=False) as source:
                centrelines = np.asarray(source["fibre_centrelines_m"], dtype=float)
            if centrelines.shape != (fibre_count, 37, 3):
                raise RuntimeError(f"unexpected centreline shape for {case_id}: {centrelines.shape}")
            masks = []
            for points in centrelines:
                mask = np.zeros_like(sand)
                api.mark_capsule(mask, points, radius, length)
                masks.append(mask)
            union = np.logical_or.reduce(masks)
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
        individual = [int(np.count_nonzero(mask & ~sand)) for mask in masks]
        pair_overlap = []
        pair_adjacency = []
        for i in range(len(masks)):
            for j in range(i + 1, len(masks)):
                pair_overlap.append(int(np.count_nonzero(masks[i] & masks[j])))
                pair_adjacency.append(face_adjacency(masks[i], masks[j]))
        conn = api.connectivity(phase != 0)
        checks = {
            "sand_exact": np.array_equal(material == 1, sand),
            "fibre_count_exact": centrelines.shape == (fibre_count, 37, 3),
            "all_fibres_positive_or_clean": fibre_count == 0 or all(value > 0 for value in individual),
            "fluid_connected_99pct": conn["largest_fluid_component_fraction"] >= 0.99,
            "fluid_spans_xyz": all(conn["largest_component_spans_xyz_nonperiodic"]),
            "zero_contact_resolved_or_other": topology != "zero_contact" or (all(v == 0 for v in pair_overlap) and all(v == 0 for v in pair_adjacency)),
            "one_contact_resolved_or_other": topology != "one_contact" or sum(v > 0 for v in pair_overlap) + sum(v > 0 for v in pair_adjacency) >= 1,
        }
        source_voxels = 0 if case_id == "clean" else source_rows[case_id]["fibre_union_only_voxel_count"]
        rows.append({
            "case_id": case_id, "run_order": run_order, "fibre_count": fibre_count, "topology": topology, "block": block,
            "achieved_dry_mass_percent": 0.0 if case_id == "clean" else source_rows[case_id]["achieved_dry_mass_percent"],
            "fibre_individual_voxel_counts": individual, "fibre_union_only_voxel_count": int(np.count_nonzero(material == 2)),
            "cpd2_fibre_union_only_voxel_count": source_voxels,
            "pair_raw_overlap_voxels": pair_overlap, "pair_face_adjacency_counts": pair_adjacency,
            "sand_voxel_count": int(np.count_nonzero(sand)), "voxel_porosity": float(np.mean(phase == 0)),
            "connectivity": conn, "checks": checks,
        })
        warm_path = ROOT / "stage29_runs" / "stage29e_low_concentration_hydraulic_design_20260826" / "gpu_screen_01" / cpd2_rows[case_id]["solver_case_id"] / "final_fields.npz"
        warm_starts[case_id] = {
            "path": str(warm_path.resolve()), "sha256": sha(warm_path),
            "velocity_scale": float(cpd4["solver"]["warm_start_velocity_scale"]),
            "density_deviation_scale": float(cpd4["solver"]["warm_start_density_deviation_scale"]),
        }

    selected_nonclean = [row for row in rows if row["case_id"] != "clean"]
    voxel_scales = {row["case_id"]: row["fibre_union_only_voxel_count"] / row["cpd2_fibre_union_only_voxel_count"] for row in selected_nonclean}
    checks = {
        "exact_selected_order": [row["case_id"] for row in rows] == [x[0] for x in CASES],
        "resolution_exact_double": list(clean_phase.shape) == [2 * x for x in stage29["geometry"]["resolution"]],
        "fibre_diameter_cells_at_least_3p9": 2 * radius / spacing >= 3.9,
        "clean_geometry_byte_identical": sha(CPD4_CLEAN) == EXPECTED[CPD4_CLEAN],
        "sand_identity_all_cases": len({row["sand_voxel_count"] for row in rows}) == 1,
        "all_case_checks": all(all(row["checks"].values()) for row in rows),
        "all_warm_starts_bound": all(Path(v["path"]).is_file() and sha(Path(v["path"])) == v["sha256"] for v in warm_starts.values()),
        "fibre_voxel_scaling_7_to_9": all(7.0 <= value <= 9.0 for value in voxel_scales.values()),
        "reused_stage28c_cpd4_passed": stage28_done.get("passed") is True and stage28_eval.get("passed") is True and stage28_checkpoint.get("passed") is True,
    }
    if not all(checks.values()):
        raise RuntimeError(f"Stage30a CPD4 geometry checks failed: {checks}")
    acceptance = dict(cpd4["acceptance"])
    acceptance.update({
        "maximum_absolute_selected_ratio_shift": 0.002,
        "maximum_absolute_four_fibre_contrast_shift": 0.001,
        "maximum_relative_clean_reproduction_error": 1e-12,
        "require_all_selected_obstructive": True,
        "require_zero_contact_more_obstructive": True,
    })
    lineage = {
        "stage29e_cpd2_config": bind(STAGE29_CONFIG), "stage29e_cpd2_completion": bind(STAGE29_COMPLETION),
        "stage29e_cpd2_evaluation": bind(STAGE29_EVALUATION), "stage29e_cpd2_checkpoint": bind(STAGE29_CHECKPOINT),
        "stage28c_cpd4_completion": bind(STAGE28C_COMPLETION), "stage28c_cpd4_evaluation": bind(STAGE28C_EVALUATION),
        "stage28c_cpd4_checkpoint": bind(STAGE28C_CHECKPOINT), "stage27b_cpd4_config": bind(CPD4_CONFIG),
        "stage27b_clean_cpd4_geometry": bind(CPD4_CLEAN), "stage27b_cpd4_completion": bind(CPD4_COMPLETION),
        "stage27b_cpd4_evaluation": bind(CPD4_EVALUATION), "stage27b_cpd4_checkpoint": bind(CPD4_CHECKPOINT),
        "geometry_api": bind(GEOMETRY_API), "contract": bind(CONTRACT), "builder": bind(Path(__file__).resolve()),
        "cuda_source": cpd4["lineage"]["cuda_source"], "stage13_qualification": cpd4["lineage"]["stage13_qualification"],
        "stage13_execution_manifest": cpd4["lineage"]["stage13_execution_manifest"], "stage13_runner": cpd4["lineage"]["stage13_runner"],
        "qualified_ptx_sha256": cpd4["lineage"]["qualified_ptx_sha256"],
    }
    config = {
        "schema": "lbs.stage30a-selected-low-concentration-cpd4.v1", "status": "cpd4_geometry_built_independent_gpu_release_required",
        "research_question": "Are selected Stage29e one- and four-fibre CPD2 effects stable at CPD4?",
        "claim_boundary": "Four-case selected fixed-solid solution verification in one 216-grain periodic LBS packing; no monotonic concentration law, laboratory validation, population inference, mobile sand, migration, clogging, deformation or coupling.",
        "selection_rationale": "Block B is near the CPD2 block means for both the isolated-single response and paired four-fibre topology contrast; accepted Stage28c CPD4 two-fibre results are reused without rerun.",
        "solver": cpd4["solver"], "acceptance": acceptance, "execution": cpd4["execution"], "fluid": cpd4["fluid"],
        "geometry": {"resolution": [186, 186, 186], "spacing_m": spacing, "equivalent_cell_length_m": length,
                     "fibre_radius_m": radius, "fibre_diameter_cells": 2 * radius / spacing, "cases": rows, "artifacts": artifacts},
        "cpd2_reference": {"paired_results": [cpd2_rows[x[0]] for x in CASES], "warm_starts": warm_starts},
        "accepted_clean_cpd4": {"conductance_proxy_lu": float(cpd4_done["paired_results"][0]["conductance_proxy_lu"]),
                                "intrinsic_permeability_m2": float(cpd4_done["paired_results"][0]["intrinsic_permeability_m2"])},
        "reused_stage28c_cpd4": {"paired_results": stage28_done["paired_results"], "completion_sha256": sha(STAGE28C_COMPLETION),
                                  "evaluation_sha256": sha(STAGE28C_EVALUATION), "checkpoint_sha256": sha(STAGE28C_CHECKPOINT)},
        "lineage": lineage, "checks": checks,
        "authority": {"independent_design_audit": True, "gpu_cpd4_execution": False, "render": False,
                      "permeability_validation_claim": False, "mechanics_rerun": False, "mobile_sand": False,
                      "migration": False, "clogging": False, "two_way_coupling": False},
    }
    config_path = OUTPUT / "resolved_config.json"
    write(config_path, config)
    completion = {
        "schema": config["schema"] + ".geometry-completion", "status": config["status"], "passed": True,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "config_sha256": sha(config_path),
        "builder_sha256": sha(Path(__file__).resolve()), "checks": checks, "cases": rows, "artifacts": artifacts,
        "next_handoff": {"authorized": "independent design audit", "not_authorized": "GPU execution before hash-bound audit release"},
    }
    completion_path = OUTPUT / "completion.json"
    write(completion_path, completion)
    print(json.dumps({"passed": True, "config": str(config_path), "config_sha256": sha(config_path),
                      "completion": str(completion_path), "completion_sha256": sha(completion_path),
                      "checks": checks, "voxel_scales": voxel_scales}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
