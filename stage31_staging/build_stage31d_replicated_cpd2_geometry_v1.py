#!/usr/bin/env python3
"""Build 21 immutable CPD2 masks from accepted Stage31c terminal paths."""
from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
sys.path.insert(0, str(ROOT / "stage27_staging"))
import build_stage27a_mechanics_hydraulic_masks_v1 as api  # noqa: E402

STUDY = "stage31d_replicated_nested_cpd2_geometry_20260826"
OUTPUT = ROOT / "stage31_designs" / STUDY / "geometry_01"
DESIGN = ROOT / "stage31_designs/stage31b_nested_concentration_replication_20260826/design_01/design_manifest.json"
DESIGN_AUDIT = ROOT / "stage31_evaluations/stage31b_nested_concentration_replication_20260826/design_audit_01/design_audit.json"
MECHANICS_RESULT = ROOT / "stage31_runs/stage31c_replicated_nested_mechanics_20260826/mechanics_01/result.json"
MECHANICS_EVALUATION = ROOT / "stage31_evaluations/stage31c_replicated_nested_mechanics_20260826/mechanics_evaluation_01/evaluation.json"
STAGE27_CONFIG = ROOT / "stage27_designs/stage27a_stage26x_mechanics_hydraulic_bridge_20260823/geometry_01/resolved_config.json"
GEOMETRY_API = ROOT / "stage27_staging/build_stage27a_mechanics_hydraulic_masks_v1.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": sha(path)}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable geometry: {OUTPUT}")
    required = [DESIGN, DESIGN_AUDIT, MECHANICS_RESULT, MECHANICS_EVALUATION, STAGE27_CONFIG, GEOMETRY_API]
    if any(not path.is_file() for path in required):
        raise RuntimeError("required Stage31d source is missing")
    design, design_audit = load(DESIGN), load(DESIGN_AUDIT)
    mechanics_result, mechanics_evaluation, stage27 = load(MECHANICS_RESULT), load(MECHANICS_EVALUATION), load(STAGE27_CONFIG)
    if not (design_audit.get("passed") and mechanics_result.get("passed") and mechanics_evaluation.get("passed")):
        raise RuntimeError("upstream design or mechanics handoff did not pass")
    mechanics_by_block = {}
    mechanics_case_bindings = {}
    for record in mechanics_result["case_records"]:
        path = MECHANICS_RESULT.parent / record["path"]
        if sha(path) != record["sha256"]:
            raise RuntimeError("mechanics case record hash mismatch")
        case = load(path)
        mechanics_by_block[(case["packing_id"], case["placement_block"])] = case
        mechanics_case_bindings[case["case_id"]] = bind(path)
    if len(mechanics_by_block) != 6:
        raise RuntimeError("six mechanics blocks are required")
    n = 93
    fibre_radius = float(design["fibre"]["radius_m"])
    packing_data = {}
    for packing_id in ("n216_s1", "n216_s2", "n216_s3"):
        network_path = Path(design["source_bindings"][packing_id]["network"]["path"])
        if sha(network_path) != design["source_bindings"][packing_id]["network"]["sha256"]:
            raise RuntimeError("network hash mismatch: " + packing_id)
        network = load(network_path)
        cell = np.diag(np.asarray(network["cell_hsize_m"], dtype=float))
        equivalent_length = float(np.prod(cell) ** (1.0 / 3.0))
        affine = equivalent_length / cell
        centres = np.asarray([particle["position_m"] for particle in network["particles"]], dtype=float) * affine
        radii = np.asarray([particle["radius_m"] for particle in network["particles"]], dtype=float)
        sand = np.zeros((n, n, n), dtype=bool)
        api.mark_spheres(sand, centres, radii, equivalent_length)
        packing_data[packing_id] = {
            "network_path": network_path,
            "cell": cell,
            "equivalent_length": equivalent_length,
            "spacing": equivalent_length / n,
            "affine": affine,
            "centres": centres,
            "radii": radii,
            "sand": sand,
            "maximum_affine_distortion": float(np.max(np.abs(affine - 1.0))),
        }
    ordered_cases = sorted(
        design["cases"],
        key=lambda case: (
            0 if case["role"] == "packing_clean_control" else 1,
            ("n216_s1", "n216_s2", "n216_s3").index(case["packing_id"]) if case["role"] == "packing_clean_control" else int(case["frozen_randomized_nonclean_run_order"]),
        ),
    )
    OUTPUT.mkdir(parents=True)
    artifacts, rows = {}, []
    for flow_order, design_case in enumerate(ordered_cases, start=1):
        packing_id = design_case["packing_id"]
        data = packing_data[packing_id]
        sand = data["sand"]
        centrelines, masks = [], []
        mechanics_binding = None
        if design_case["role"] != "packing_clean_control":
            source = mechanics_by_block[(packing_id, design_case["placement_block"])]
            mechanics_binding = mechanics_case_bindings[source["case_id"]]
            for terminal in source["terminal_fibres"][: int(design_case["fibre_count"])]:
                points = np.asarray(terminal["terminal_node_positions_m"], dtype=float) * data["affine"]
                mask = np.zeros_like(sand)
                api.mark_capsule(mask, points, fibre_radius, data["equivalent_length"])
                centrelines.append(points)
                masks.append(mask)
        fibre_union = np.logical_or.reduce(masks) if masks else np.zeros_like(sand)
        fibre_only = fibre_union & ~sand
        solid = sand | fibre_only
        material = np.zeros_like(sand, dtype=np.uint8)
        material[sand] = 1
        material[fibre_only] = 2
        phase = np.where(solid, 2, 0).astype(np.uint8)
        connectivity = api.connectivity(solid)
        checks = {
            "fibre_count_exact": len(centrelines) == int(design_case["fibre_count"]),
            "all_terminal_centrelines_37_nodes": all(points.shape == (37, 3) for points in centrelines),
            "all_fibres_positive_voxels": not masks or all(np.count_nonzero(mask & ~sand) > 0 for mask in masks),
            "fluid_connected_99pct": connectivity["largest_fluid_component_fraction"] >= 0.99,
            "fluid_spans_xyz": all(connectivity["largest_component_spans_xyz_nonperiodic"]),
            "material_phase_consistent": np.array_equal(material != 0, phase != 0),
        }
        case_dir = OUTPUT / design_case["case_id"]
        case_dir.mkdir()
        geometry_path = case_dir / "geometry_cpd2.npz"
        np.savez_compressed(
            geometry_path,
            phase=phase,
            material=material,
            spacing_m=np.asarray([data["spacing"]]),
            cell_length_m=np.asarray([data["equivalent_length"]]),
            original_cell_lengths_m=data["cell"],
            affine_scale_xyz=data["affine"],
            sand_centres_m=data["centres"],
            sand_radii_m=data["radii"],
            fibre_centrelines_m=np.asarray(centrelines, dtype=float).reshape((len(centrelines), 37, 3)),
            fibre_radius_m=np.asarray([fibre_radius]),
        )
        vtk_path = case_dir / "material.vtk"
        api.write_vtk(vtk_path, material, data["spacing"])
        artifacts[design_case["case_id"]] = {
            "geometry": str(geometry_path.resolve()),
            "geometry_sha256": sha(geometry_path),
            "material_vtk": str(vtk_path.resolve()),
            "material_vtk_sha256": sha(vtk_path),
            "mechanics_case": mechanics_binding,
        }
        rows.append(
            {
                "case_id": design_case["case_id"],
                "flow_order": flow_order,
                "packing_id": packing_id,
                "placement_block": design_case["placement_block"],
                "fibre_count": int(design_case["fibre_count"]),
                "achieved_dry_mass_percent": float(design_case["achieved_dry_mass_percent"]),
                "role": design_case["role"],
                "sand_voxel_count": int(np.count_nonzero(sand)),
                "fibre_only_voxel_count": int(np.count_nonzero(fibre_only)),
                "voxel_porosity": float(np.mean(~solid)),
                "equivalent_cell_length_m": data["equivalent_length"],
                "spacing_m": data["spacing"],
                "affine_scale_xyz": data["affine"].tolist(),
                "maximum_affine_distortion": data["maximum_affine_distortion"],
                "connectivity": connectivity,
                "checks": checks,
            }
        )
    clean_by_packing = {row["packing_id"]: row for row in rows if row["fibre_count"] == 0}
    checks = {
        "exact_twenty_one_cases": len(rows) == 21,
        "exact_three_clean_controls": len(clean_by_packing) == 3,
        "exact_eighteen_fibre_cases": sum(row["fibre_count"] > 0 for row in rows) == 18,
        "flow_order_exact": [row["flow_order"] for row in rows] == list(range(1, 22)),
        "all_case_checks": all(all(row["checks"].values()) for row in rows),
        "cpd2_resolution_at_least_1p9_cells": all(2.0 * fibre_radius / packing_data[packing]["spacing"] >= 1.9 for packing in packing_data),
        "maximum_affine_distortion_below_0p02": all(data["maximum_affine_distortion"] < 0.02 for data in packing_data.values()),
        "mixture_porosity_below_matched_clean": all(row["fibre_count"] == 0 or row["voxel_porosity"] < clean_by_packing[row["packing_id"]]["voxel_porosity"] for row in rows),
        "sand_identity_within_packing": all(len({row["sand_voxel_count"] for row in rows if row["packing_id"] == packing}) == 1 for packing in packing_data),
    }
    if not all(checks.values()):
        raise RuntimeError("Stage31d geometry construction failed: " + json.dumps(checks, sort_keys=True))
    config = {
        "schema": "lbs.stage31d-replicated-nested-cpd2-geometry.v1",
        "status": "geometry_built_independent_audit_required",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "research_question": "How do 1/2/4 mechanics-qualified open-path F37 prefixes change CPD2 conductance across three sand packings and two placement blocks?",
        "solver": stage27["solver"],
        "acceptance": stage27["acceptance"],
        "execution": stage27["execution"],
        "fluid": stage27["fluid"],
        "geometry": {"resolution": [n, n, n], "fibre_radius_m": fibre_radius, "cases": rows, "artifacts": artifacts},
        "analysis_plan": {
            "primary_response": "paired conductance ratio to the matched packing clean control",
            "fixed_effect": "fibre_count treated categorically without imposed monotonicity",
            "blocking": ["packing_id", "placement_block nested within packing_id"],
            "replicates_per_nonzero_count": 6,
            "uncertainty": "report raw six ratios, mean, standard deviation, coefficient of variation, and packing/block ranges",
        },
        "lineage": {
            "stage31b_design": bind(DESIGN),
            "stage31b_design_audit": bind(DESIGN_AUDIT),
            "stage31c_mechanics_result": bind(MECHANICS_RESULT),
            "stage31c_mechanics_evaluation": bind(MECHANICS_EVALUATION),
            "stage27_solver_config": bind(STAGE27_CONFIG),
            "geometry_api": bind(GEOMETRY_API),
            "builder": bind(Path(__file__).resolve()),
            **{f"{packing}_network": bind(data["network_path"]) for packing, data in packing_data.items()},
            **{f"{case_id}_mechanics": value for case_id, value in mechanics_case_bindings.items()},
        },
        "checks": checks,
        "authority": {"geometry_audit": True, "gpu_execution": False, "cpd4": False, "permeability_claim": False, "mobile_sand": False, "coupling": False},
        "claim_boundary": "Fixed-solid CPD2 geometry only. No flow result, permeability claim, mobile sand, migration, clogging, deformation, or coupling.",
    }
    config_path = OUTPUT / "resolved_config.json"
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    completion = {
        "schema": config["schema"] + ".completion",
        "status": config["status"],
        "passed": True,
        "config_sha256": sha(config_path),
        "checks": checks,
        "case_count": len(rows),
        "next_handoff": {"authorized": "independent geometry and visual audit", "not_authorized": "GPU flow or hydraulic claims"},
    }
    (OUTPUT / "completion.json").write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "config_sha256": sha(config_path), "checks": checks}, indent=2))


if __name__ == "__main__":
    main()
