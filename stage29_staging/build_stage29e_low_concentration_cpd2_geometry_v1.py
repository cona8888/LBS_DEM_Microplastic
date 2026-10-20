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

STUDY = "stage29e_low_concentration_hydraulic_design_20260826"
DESIGN = ROOT / "stage29_designs" / STUDY / "design_01" / "design_manifest.json"
DESIGN_AUDIT = ROOT / "stage29_evaluations" / STUDY / "design_audit_01" / "design_audit.json"
S28_RESULT = ROOT / "stage28_runs" / "stage28a_two_fibre_mechanics_hydraulics_20260824" / "mechanics_02" / "result.json"
S29_RESULT = ROOT / "stage29_runs" / "stage29d_shared_pair_context_qualification_20260825" / "mechanics_01" / "result.json"
STAGE27_CONFIG = ROOT / "stage27_designs" / "stage27a_stage26x_mechanics_hydraulic_bridge_20260823" / "geometry_01" / "resolved_config.json"
CLEAN = ROOT / "stage27_designs" / "stage27a_stage26x_mechanics_hydraulic_bridge_20260823" / "geometry_01" / "clean" / "geometry_cpd2.npz"
GEOMETRY_API = ROOT / "stage27_staging" / "build_stage27a_mechanics_hydraulic_masks_v1.py"
OUT = ROOT / "stage29_designs" / STUDY / "geometry_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": sha(path)}


def face_adjacency(a: np.ndarray, b: np.ndarray) -> int:
    return sum(int(np.count_nonzero(np.roll(a, s, axis=axis) & b)) for axis in range(3) for s in (-1, 1))


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    design = json.loads(DESIGN.read_text())
    audit = json.loads(DESIGN_AUDIT.read_text())
    r28, r29 = json.loads(S28_RESULT.read_text()), json.loads(S29_RESULT.read_text())
    stage27 = json.loads(STAGE27_CONFIG.read_text())
    if not (audit.get("passed") and "hydraulic geometries" in audit["next_handoff"]["authorized"] and r28.get("passed") and r29.get("passed")):
        raise RuntimeError("design or mechanics handoff absent")
    by_study = {"stage28a": {x["case_id"]: x for x in r28["cases"]}, "stage29d": {x["case_id"]: x for x in r29["cases"]}}
    with np.load(CLEAN) as data:
        clean_phase = np.asarray(data["phase"], dtype=np.uint8)
        clean_material = np.asarray(data["material"], dtype=np.uint8)
        spacing = float(data["spacing_m"][0]); length = float(data["cell_length_m"][0])
        affine = np.asarray(data["affine_scale_xyz"], dtype=float)
        sand_centres = np.asarray(data["sand_centres_m"], dtype=float); sand_radii = np.asarray(data["sand_radii_m"], dtype=float)
        original_cell = np.asarray(data["original_cell_lengths_m"], dtype=float)
    sand = clean_material == 1
    radius = 0.5 * float(stage27["geometry"]["fibre_diameter_cells"]) * spacing
    OUT.mkdir(parents=True)
    artifacts, rows = {}, []
    for case in sorted(design["cases"], key=lambda x: x["frozen_cpd2_run_order"]):
        source = by_study[case["mechanics_source_study"]][case["mechanics_source_case_id"]]
        source_file = (ROOT / "stage28_runs" / "stage28a_two_fibre_mechanics_hydraulics_20260824" / "mechanics_02" / source["result_artifact"]["path"]) if case["mechanics_source_study"] == "stage28a" else (ROOT / "stage29_runs" / "stage29d_shared_pair_context_qualification_20260825" / "mechanics_01" / source["result_artifact"]["path"])
        if sha(source_file) != case["mechanics_source_case_result_sha256"]:
            raise RuntimeError("mechanics case hash mismatch: " + case["case_id"])
        centrelines, masks = [], []
        for fibre in source["terminal_fibres"]:
            points = np.asarray(fibre["terminal_node_positions_m"], dtype=float) * affine
            mask = np.zeros_like(sand)
            api.mark_capsule(mask, points, radius, length)
            centrelines.append(points); masks.append(mask)
        union = np.logical_or.reduce(masks)
        fibre_only = union & ~sand
        solid = sand | fibre_only
        material = np.zeros_like(clean_material); material[sand] = 1; material[fibre_only] = 2
        phase = np.where(solid, 2, 0).astype(np.uint8)
        conn = api.connectivity(solid)
        overlaps, adjacencies = [], []
        for i in range(len(masks)):
            for j in range(i + 1, len(masks)):
                overlaps.append(int(np.count_nonzero(masks[i] & masks[j])))
                adjacencies.append(face_adjacency(masks[i], masks[j]))
        contact_voxel_resolved = any(v > 0 for v in overlaps + adjacencies)
        expects_contact = case["topology"] in ("crossing", "one_contact")
        checks = {
            "mechanics_case_hash_bound": True,
            "fibre_count_exact": len(masks) == case["fibre_count"],
            "all_37_node_centrelines": all(x.shape == (37, 3) for x in centrelines),
            "all_fibres_positive_voxels": all(np.count_nonzero(mask & ~sand) > 0 for mask in masks),
            "sand_exact": np.array_equal(sand, clean_material == 1),
            "fluid_connected_99pct": conn["largest_fluid_component_fraction"] >= 0.99,
            "fluid_spans_xyz": all(conn["largest_component_spans_xyz_nonperiodic"]),
            "contact_topology_resolved_at_cpd2": contact_voxel_resolved == expects_contact,
        }
        case_dir = OUT / case["case_id"]; case_dir.mkdir()
        geometry = case_dir / "geometry_cpd2.npz"
        np.savez_compressed(geometry, phase=phase, material=material, spacing_m=np.asarray([spacing]), cell_length_m=np.asarray([length]), original_cell_lengths_m=original_cell, affine_scale_xyz=affine, sand_centres_m=sand_centres, sand_radii_m=sand_radii, fibre_centrelines_m=np.asarray(centrelines), fibre_radius_m=np.asarray([radius]))
        vtk = case_dir / "material.vtk"; api.write_vtk(vtk, material, spacing)
        artifacts[case["case_id"]] = {"geometry": str(geometry.resolve()), "geometry_sha256": sha(geometry), "material_vtk": str(vtk.resolve()), "material_vtk_sha256": sha(vtk), "mechanics_case_result": str(source_file.resolve()), "mechanics_case_result_sha256": sha(source_file)}
        rows.append({"case_id": case["case_id"], "run_order": case["frozen_cpd2_run_order"], "fibre_count": case["fibre_count"], "achieved_dry_mass_percent": case["achieved_dry_mass_percent"], "topology": case["topology"], "block": case["block"], "fibre_individual_voxel_counts": [int(np.count_nonzero(mask & ~sand)) for mask in masks], "fibre_union_only_voxel_count": int(np.count_nonzero(fibre_only)), "pair_raw_overlap_voxels": overlaps, "pair_face_adjacency_counts": adjacencies, "contact_voxel_resolved": contact_voxel_resolved, "sand_voxel_count": int(np.count_nonzero(sand)), "voxel_porosity": float(np.mean(~solid)), "connectivity": conn, "checks": checks})
    checks = {
        "exact_eleven_cases": len(rows) == 11,
        "case_order_is_frozen_permutation": [x["run_order"] for x in rows] == list(range(1, 12)),
        "sand_identity_all_cases": len({x["sand_voxel_count"] for x in rows}) == 1,
        "all_case_checks": all(all(x["checks"].values()) for x in rows),
        "fibre_resolution_at_least_1p9_cells": 2 * radius / spacing >= 1.9,
        "all_mixture_porosity_below_clean": all(float(np.mean(clean_phase == 0)) > x["voxel_porosity"] for x in rows),
    }
    if not all(checks.values()):
        raise RuntimeError("Stage29e geometry checks failed")
    config = {
        "schema": "lbs.stage29e-low-concentration-cpd2-hydraulic.v1",
        "status": "geometry_built_independent_gpu_release_required",
        "research_question": "How do mechanics-qualified F37 counts and contact topology change paired CPD2 permeability in fixed periodic LBS?",
        "claim_boundary": design["claim_boundary"],
        "solver": stage27["solver"], "acceptance": stage27["acceptance"], "execution": stage27["execution"], "fluid": stage27["fluid"],
        "clean_control": {"geometry": str(CLEAN.resolve()), "geometry_sha256": sha(CLEAN), "reused": True},
        "geometry": {"resolution": list(clean_phase.shape[::-1]), "spacing_m": spacing, "equivalent_cell_length_m": length, "fibre_radius_m": radius, "fibre_diameter_cells": 2 * radius / spacing, "cases": rows, "artifacts": artifacts},
        "analysis_plan": design["analysis_plan"],
        "lineage": {**{k: v for k, v in stage27["lineage"].items()}, "stage29e_design": bind(DESIGN), "stage29e_design_audit": bind(DESIGN_AUDIT), "stage28_mechanics_result": bind(S28_RESULT), "stage29d_mechanics_result": bind(S29_RESULT), "stage27_config": bind(STAGE27_CONFIG), "stage27_clean_geometry": bind(CLEAN), "geometry_api": bind(GEOMETRY_API), "builder": bind(Path(__file__).resolve())},
        "checks": checks,
        "authority": {"independent_gpu_audit": True, "gpu_execution": False, "cpd4": False, "permeability_claim": False, "mechanics_rerun": False, "mobile_sand": False, "two_way_coupling": False},
    }
    config_path = OUT / "resolved_config.json"; config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    completion = {"schema": config["schema"] + ".geometry-completion", "timestamp_utc": datetime.now(timezone.utc).isoformat(), "passed": True, "status": config["status"], "config_sha256": sha(config_path), "checks": checks, "cases": rows, "artifacts": artifacts, "next_handoff": {"authorized": "independent CPD2 geometry/topology audit", "not_authorized": "GPU execution, CPD4, or permeability claims"}}
    completion_path = OUT / "completion.json"; completion_path.write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"config": str(config_path), "config_sha256": sha(config_path), "completion_sha256": sha(completion_path), "checks": checks, "case_count": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
