#!/usr/bin/env python3
"""Build immutable Stage31f selected replicated CPD4 geometries."""

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

STUDY = "stage31f_selected_replicated_cpd4_20260827"
OUTPUT = ROOT / "stage31_designs" / STUDY / "geometry_01"
S31D_CONFIG = ROOT / "stage31_designs/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_01/resolved_config.json"
S31D_COMPLETION = S31D_CONFIG.parent / "completion.json"
S31E_COMPLETION = ROOT / "stage31_runs/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_screen_01/completion.json"
S31E_EVALUATION = ROOT / "stage31_evaluations/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_evaluation_01/evaluation.json"
S31E_VISUAL = ROOT / "stage31_evaluations/stage31e_replicated_nested_cpd2_gpu_20260826/visual_audit_01/visual_audit.json"
S30_COMPLETION = ROOT / "stage30_runs/stage30a_selected_low_concentration_cpd4_20260826/gpu_confirmation_01/completion.json"
S30_EVALUATION = ROOT / "stage30_evaluations/stage30a_selected_low_concentration_cpd4_20260826/gpu_evaluation_01/evaluation.json"
CPD4_CONFIG = ROOT / "stage27_designs/stage27b_stage26x_mechanics_hydraulic_cpd4_20260824/geometry_01/resolved_config.json"
CPD4_S1_CLEAN = ROOT / "stage27_designs/stage27b_stage26x_mechanics_hydraulic_cpd4_20260824/geometry_01/clean/geometry_cpd4.npz"
S30_CLEAN_RECORD = ROOT / "stage30_runs/stage30a_selected_low_concentration_cpd4_20260826/gpu_confirmation_01/stage30a_clean_cpd4/record.json"
GEOMETRY_API = ROOT / "stage27_staging/build_stage27a_mechanics_hydraulic_masks_v1.py"
CONTRACT = ROOT / "stage31_staging/STAGE31F_SELECTED_REPLICATED_CPD4_CONTRACT.md"

EXPECTED = {
    S31D_CONFIG: "d44be2dd626be6d0053e9402d52b3c3051efb7948210cd039daff06d6e91a2c5",
    S31D_COMPLETION: "9ee9899ba4fce4106b2962f36c7328da5548d23f91958b471a2e46f0c18acf27",
    S31E_COMPLETION: "abfa274bebf3d2e8d8e0a32d406ead4e0d6027fa8c9a2aa1a1f9c0dc65caae5c",
    S31E_EVALUATION: "a279e49f0c3d0033588065472f4a394d8e5aa5563007afb33a74ec75848e990d",
    S31E_VISUAL: "1f5ce4f53f89ce1beddedc86f1647f6a5ad75c20a82f207817d9b2732bbb1528",
    S30_COMPLETION: "2adeb8e3ed1d450e235c63101c36ad002ee742d5d5213eb807a9da6d5c971795",
    S30_EVALUATION: "3036a2960fbdeb1527146666f9b2abdb05522747f9863a3c7be6ab6ce218f893",
    CPD4_CONFIG: "218433a39143c19c3451967e839b25d29cd7360726c3c9662d497480b499821e",
    CPD4_S1_CLEAN: "e0d780f54b433480bb92ef86252d56d9a1066e4542c26b736e71229f3a1c251c",
    GEOMETRY_API: "92163d42d54960208ea5ac9efd132e23413cb7f08a1c8ca934ff6e18cc2bd6f1",
    CONTRACT: "cf4f5aa3d2b58cc675e483c679ed5f352eeab166a0fa65e7dd29b21ed785f9ce",
}

ORDER = (
    "s31b_n216_s2_clean",
    "s31b_n216_s1_A_f001_open",
    "s31b_n216_s1_A_f002_open",
    "s31b_n216_s1_A_f004_open",
    "s31b_n216_s1_B_f004_open",
    "s31b_n216_s2_A_f004_open",
    "s31b_n216_s2_B_f004_open",
)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def bind(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": sha(path)}


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def face_adjacency(first: np.ndarray, second: np.ndarray) -> int:
    return sum(int(np.count_nonzero(np.roll(first, shift, axis=axis) & second))
               for axis in range(3) for shift in (-1, 1))


def source_arrays(path: Path) -> dict:
    with np.load(path, allow_pickle=False) as data:
        return {key: np.asarray(data[key]) for key in data.files}


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUTPUT}")
    mismatches = [str(path) for path, expected in EXPECTED.items()
                  if not path.is_file() or sha(path) != expected]
    if mismatches:
        raise RuntimeError("immutable source mismatch: " + ", ".join(mismatches))
    if not S30_CLEAN_RECORD.is_file():
        raise RuntimeError("accepted Stage30a clean record missing")

    s31d, s31d_done, s31e_done, s31e_eval, s31e_visual, s30_done, s30_eval, base = map(
        load, (S31D_CONFIG, S31D_COMPLETION, S31E_COMPLETION, S31E_EVALUATION,
               S31E_VISUAL, S30_COMPLETION, S30_EVALUATION, CPD4_CONFIG))
    if not all(item.get("passed") is True for item in
               (s31d_done, s31e_done, s31e_eval, s31e_visual, s30_done, s30_eval)):
        raise RuntimeError("accepted lineage did not pass")
    cp2_rows = {row["case_id"]: row for row in s31e_done["paired_results"]}
    geom_rows = {row["case_id"]: row for row in s31d["geometry"]["cases"]}
    if any(case_id not in cp2_rows or case_id not in geom_rows for case_id in ORDER):
        raise RuntimeError("selected case is absent from Stage31 evidence")

    with np.load(CPD4_S1_CLEAN, allow_pickle=False) as data:
        s1_clean = {key: np.asarray(data[key]) for key in data.files}
    if tuple(s1_clean["phase"].shape) != (186, 186, 186):
        raise RuntimeError("accepted s1 CPD4 clean shape mismatch")

    OUTPUT.mkdir(parents=True)
    clean_cache: dict[str, dict] = {"n216_s1": s1_clean}
    artifacts, rows, warm_starts = {}, [], {}
    radius = float(s31d["geometry"]["fibre_radius_m"])

    for run_order, case_id in enumerate(ORDER, start=1):
        source_path = Path(s31d["geometry"]["artifacts"][case_id]["geometry"])
        source = source_arrays(source_path)
        row = geom_rows[case_id]
        packing = row["packing_id"]
        length = float(source["cell_length_m"][0])
        spacing = length / 186.0
        if packing not in clean_cache:
            sand = np.zeros((186, 186, 186), dtype=bool)
            api.mark_spheres(sand, source["sand_centres_m"], source["sand_radii_m"], length)
            material = np.zeros(sand.shape, dtype=np.uint8)
            material[sand] = 1
            phase = np.where(sand, 2, 0).astype(np.uint8)
            clean_cache[packing] = {
                "phase": phase, "material": material, "spacing_m": np.asarray([spacing]),
                "cell_length_m": np.asarray([length]),
                "original_cell_lengths_m": source["original_cell_lengths_m"],
                "affine_scale_xyz": source["affine_scale_xyz"],
                "sand_centres_m": source["sand_centres_m"], "sand_radii_m": source["sand_radii_m"],
                "fibre_centrelines_m": np.empty((0, 37, 3), dtype=float),
                "fibre_radius_m": np.asarray([radius]),
            }
        clean = clean_cache[packing]
        if not (np.array_equal(source["sand_centres_m"], clean["sand_centres_m"])
                and np.array_equal(source["sand_radii_m"], clean["sand_radii_m"])):
            raise RuntimeError(f"sand identity mismatch for {case_id}")
        sand = clean["material"] == 1
        count = int(row["fibre_count"])
        centrelines = np.asarray(source["fibre_centrelines_m"], dtype=float)
        if count == 0:
            centrelines = np.empty((0, 37, 3), dtype=float)
            masks = []
            material = np.asarray(clean["material"], dtype=np.uint8).copy()
        else:
            if centrelines.shape != (count, 37, 3):
                raise RuntimeError(f"fibre centreline shape mismatch: {case_id}")
            masks = []
            for points in centrelines:
                mask = np.zeros_like(sand)
                api.mark_capsule(mask, points, radius, length)
                masks.append(mask)
            union = np.logical_or.reduce(masks)
            material = np.zeros(sand.shape, dtype=np.uint8)
            material[sand] = 1
            material[union & ~sand] = 2
        phase = np.where(material != 0, 2, 0).astype(np.uint8)
        case_dir = OUTPUT / case_id
        case_dir.mkdir()
        geometry_path = case_dir / "geometry_cpd4.npz"
        np.savez_compressed(
            geometry_path, phase=phase, material=material, spacing_m=np.asarray([spacing]),
            cell_length_m=np.asarray([length]), original_cell_lengths_m=source["original_cell_lengths_m"],
            affine_scale_xyz=source["affine_scale_xyz"], sand_centres_m=source["sand_centres_m"],
            sand_radii_m=source["sand_radii_m"], fibre_centrelines_m=centrelines,
            fibre_radius_m=np.asarray([radius]),
        )
        vtk_path = case_dir / "material.vtk"
        api.write_vtk(vtk_path, material, spacing)
        artifacts[case_id] = {
            "geometry": str(geometry_path.resolve()), "geometry_sha256": sha(geometry_path),
            "material_vtk": str(vtk_path.resolve()), "material_vtk_sha256": sha(vtk_path),
            "source_cpd2_geometry": str(source_path.resolve()), "source_cpd2_geometry_sha256": sha(source_path),
        }
        overlap, adjacency = [], []
        for i in range(len(masks)):
            for j in range(i + 1, len(masks)):
                overlap.append(int(np.count_nonzero(masks[i] & masks[j])))
                adjacency.append(face_adjacency(masks[i], masks[j]))
        connectivity = api.connectivity(phase != 0)
        fibre_voxels = int(np.count_nonzero(material == 2))
        source_fibre_voxels = int(row["fibre_only_voxel_count"])
        voxel_scale = None if count == 0 else fibre_voxels / source_fibre_voxels
        checks = {
            "shape_186_cubed": phase.shape == (186, 186, 186),
            "sand_exact": np.array_equal(material == 1, sand),
            "fibre_count_exact": centrelines.shape == (count, 37, 3),
            "fluid_connected_99pct": connectivity["largest_fluid_component_fraction"] >= 0.99,
            "fluid_spans_xyz": all(connectivity["largest_component_spans_xyz_nonperiodic"]),
            "zero_interfibre_contact": all(value == 0 for value in overlap + adjacency),
            "voxel_scale_7_to_9_or_clean": count == 0 or 7.0 <= voxel_scale <= 9.0,
        }
        if not all(checks.values()):
            raise RuntimeError(f"geometry checks failed for {case_id}: {checks}")
        rows.append({
            "case_id": case_id, "run_order": run_order, "packing_id": packing,
            "placement_block": row["placement_block"], "fibre_count": count,
            "achieved_dry_mass_percent": row["achieved_dry_mass_percent"],
            "spacing_m": spacing, "equivalent_cell_length_m": length,
            "sand_voxel_count": int(np.count_nonzero(sand)), "fibre_only_voxel_count": fibre_voxels,
            "cpd2_fibre_only_voxel_count": source_fibre_voxels,
            "cpd4_over_cpd2_fibre_voxel_scale": voxel_scale,
            "pair_raw_overlap_voxels": overlap, "pair_face_adjacency_counts": adjacency,
            "voxel_porosity": float(np.mean(phase == 0)), "connectivity": connectivity, "checks": checks,
        })
        warm = ROOT / "stage31_runs/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_screen_01" / cp2_rows[case_id]["solver_case_id"] / "final_fields.npz"
        warm_starts[case_id] = {
            "path": str(warm.resolve()), "sha256": sha(warm),
            "velocity_scale": float(base["solver"]["warm_start_velocity_scale"]),
            "density_deviation_scale": float(base["solver"]["warm_start_density_deviation_scale"]),
        }

    s30_rows = {row["case_id"]: row for row in s30_done["paired_results"]}
    reused_s1_clean = {
        "geometry": bind(CPD4_S1_CLEAN), "record": bind(S30_CLEAN_RECORD),
        "completion": bind(S30_COMPLETION), "evaluation": bind(S30_EVALUATION),
        "conductance_proxy_lu": float(s30_rows["clean"]["conductance_proxy_lu"]),
        "intrinsic_permeability_m2": float(s30_rows["clean"]["intrinsic_permeability_m2"]),
    }
    acceptance = dict(base["acceptance"])
    acceptance.update({
        "maximum_absolute_selected_ratio_shift": 0.002,
        "maximum_absolute_block_contrast_shift": 0.001,
        "require_all_selected_obstructive": True,
    })
    lineage = {
        "stage31d_config": bind(S31D_CONFIG), "stage31d_completion": bind(S31D_COMPLETION),
        "stage31e_completion": bind(S31E_COMPLETION), "stage31e_evaluation": bind(S31E_EVALUATION),
        "stage31e_visual_audit": bind(S31E_VISUAL), "stage30a_completion": bind(S30_COMPLETION),
        "stage30a_evaluation": bind(S30_EVALUATION), "stage27b_cpd4_config": bind(CPD4_CONFIG),
        "stage27b_s1_clean_cpd4": bind(CPD4_S1_CLEAN), "geometry_api": bind(GEOMETRY_API),
        "contract": bind(CONTRACT), "builder": bind(Path(__file__).resolve()),
        "cuda_source": base["lineage"]["cuda_source"],
        "stage13_qualification": base["lineage"]["stage13_qualification"],
        "stage13_execution_manifest": base["lineage"]["stage13_execution_manifest"],
        "stage13_runner": base["lineage"]["stage13_runner"],
        "qualified_ptx_sha256": base["lineage"]["qualified_ptx_sha256"],
    }
    checks = {
        "exact_selected_order": [row["case_id"] for row in rows] == list(ORDER),
        "exact_seven_new_cases": len(rows) == 7,
        "all_case_checks": all(all(row["checks"].values()) for row in rows),
        "all_warm_starts_bound": all(Path(item["path"]).is_file() and sha(Path(item["path"])) == item["sha256"] for item in warm_starts.values()),
        "s1_clean_exact_accepted_geometry": sha(CPD4_S1_CLEAN) == EXPECTED[CPD4_S1_CLEAN],
        "s1_source_particle_state_exact_accepted": np.array_equal(
            source_arrays(Path(s31d["geometry"]["artifacts"]["s31b_n216_s1_A_f001_open"]["geometry"]))["sand_centres_m"],
            s1_clean["sand_centres_m"]),
        "two_packings_only": sorted({row["packing_id"] for row in rows}) == ["n216_s1", "n216_s2"],
    }
    if not all(checks.values()):
        raise RuntimeError(f"Stage31f build checks failed: {checks}")

    config = {
        "schema": "lbs.stage31f-selected-replicated-cpd4.v1",
        "status": "cpd4_geometry_built_independent_gpu_release_required",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "research_question": "Are the selected replicated Stage31e count and placement-block effects stable from CPD2 to CPD4?",
        "claim_boundary": "Selected fixed-solid CPD2-to-CPD4 solution verification only; no absolute permeability validation, population inference, or new physics.",
        "selection_rationale": "Full strongest s1/A count trajectory plus opposite-sign four-fibre A/B contrasts in s1 and s2; s3 withheld because it adds replication but no new numerical mechanism.",
        "solver": base["solver"], "acceptance": acceptance, "execution": base["execution"], "fluid": base["fluid"],
        "geometry": {"resolution": [186, 186, 186], "fibre_radius_m": radius, "cases": rows, "artifacts": artifacts},
        "cpd2_reference": {"paired_results": [cp2_rows[case_id] for case_id in ORDER], "warm_starts": warm_starts},
        "reused_s1_clean_cpd4": reused_s1_clean, "lineage": lineage, "checks": checks,
        "authority": {"independent_design_audit": True, "gpu_cpd4_execution": False, "render": False,
                      "absolute_permeability_validation_claim": False, "mechanics_rerun": False,
                      "mobile_sand": False, "migration": False, "clogging": False,
                      "deformation": False, "transient_coupling": False, "two_way_coupling": False},
    }
    config_path = OUTPUT / "resolved_config.json"
    write(config_path, config)
    completion = {
        "schema": config["schema"] + ".geometry-completion", "status": config["status"], "passed": True,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "config_sha256": sha(config_path),
        "builder_sha256": sha(Path(__file__).resolve()), "checks": checks, "cases": rows, "artifacts": artifacts,
        "next_handoff": {"authorized": "independent design audit", "not_authorized": "GPU execution before hash-bound runner release"},
    }
    completion_path = OUTPUT / "completion.json"
    write(completion_path, completion)
    print(json.dumps({"passed": True, "config": str(config_path), "config_sha256": sha(config_path),
                      "completion": str(completion_path), "completion_sha256": sha(completion_path),
                      "checks": checks}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
