#!/usr/bin/env python3
"""Rasterize the frozen Stage24c six-case selection at CPD4."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
from build_sphere_fibre_voxel_geometry import write_binary_structured_points  # noqa: E402
from build_stage23d_clean_lbs_cpd4_selected_geometry_v1 import connectivity  # noqa: E402
from build_stage24b_lbs_f37_nested_geometry_v1 import mark_periodic_fibres  # noqa: E402


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config_path, output = args.config.resolve(), args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable Stage24d output: {output}")
    config = load(config_path)
    lineage = config["lineage"]
    shared_keys = ("stage24b_completion", "stage24c_completion", "stage24c_evaluation",
                   "stage23d_completion", "stage23e_evaluation")
    observed = {key: digest(ROOT / lineage[key]) for key in shared_keys}
    if any(observed[key] != lineage[key + "_sha256"] for key in shared_keys):
        raise RuntimeError("Stage24d immutable lineage mismatch")
    stage24b = load(ROOT / lineage["stage24b_completion"])
    stage24c = load(ROOT / lineage["stage24c_completion"])
    evaluation = load(ROOT / lineage["stage24c_evaluation"])
    stage23d = load(ROOT / lineage["stage23d_completion"])
    stage23e = load(ROOT / lineage["stage23e_evaluation"])
    if not all(item.get("passed") is True for item in (stage24b, stage24c, evaluation, stage23d, stage23e)):
        raise RuntimeError("Stage24d requires all frozen source handoffs to pass")
    frozen = evaluation["frozen_bounded_cpd4_confirmation_subset_not_executed"]
    configured_ids = [case["case_id"] for case in config["cases"]]
    if configured_ids != frozen["case_ids"] or len(configured_ids) != 6:
        raise RuntimeError("Stage24d case selection differs from the frozen Stage24c subset")

    output.mkdir(parents=True)
    case_rows = []
    artifacts = {}
    for case in config["cases"]:
        case_id = case["case_id"]
        source_path = ROOT / case["source_cpd2_geometry"]
        clean_path = ROOT / case["clean_cpd4_geometry"]
        if digest(source_path) != case["source_cpd2_geometry_sha256"]:
            raise RuntimeError(f"CPD2 source geometry hash mismatch: {case_id}")
        if digest(clean_path) != case["clean_cpd4_geometry_sha256"]:
            raise RuntimeError(f"clean CPD4 geometry hash mismatch: {case_id}")
        with np.load(source_path, allow_pickle=False) as source:
            source_phase = np.asarray(source["phase"], dtype=np.uint8)
            source_material = np.asarray(source["material"], dtype=np.uint8)
            length = float(source["cell_length_m"][0])
            sand = np.asarray(source["sand_centres_m"], dtype=np.float64)
            radii = np.asarray(source["sand_radii_m"], dtype=np.float64)
            centrelines = np.asarray(source["fibre_centrelines_m"], dtype=np.float64)
            fibre_radius = float(source["fibre_radius_m"][0])
        with np.load(clean_path, allow_pickle=False) as clean:
            clean_phase = np.asarray(clean["phase"], dtype=np.uint8)
            spacing = float(clean["spacing_m"][0])
            clean_length = float(clean["cell_length_m"][0])
            clean_sand = np.asarray(clean["sand_centres_m"], dtype=np.float64)
            clean_radii = np.asarray(clean["sand_radii_m"], dtype=np.float64)
        if not (np.array_equal(sand, clean_sand) and np.array_equal(radii, clean_radii)
                and abs(length - clean_length) <= 1e-15):
            raise RuntimeError(f"continuous sand identity mismatch: {case_id}")
        sand_mask = clean_phase != 0
        fibre_mask = np.zeros_like(sand_mask)
        mark_periodic_fibres(fibre_mask, list(centrelines), fibre_radius, spacing, length)
        fibre_only = fibre_mask & ~sand_mask
        solid = sand_mask | fibre_only
        material = np.zeros_like(clean_phase, dtype=np.uint8)
        material[sand_mask] = 1
        material[fibre_only] = 2
        phase = np.where(solid, 2, 0).astype(np.uint8)
        connected = connectivity(solid)
        source_increment = float(np.count_nonzero(source_material == 2) / source_material.size)
        increment = float(np.count_nonzero(fibre_only) / material.size)
        allocation = int(2 * 19 * phase.size * 4 + phase.size + 4)
        checks = {
            "frozen_selection_identity": case_id in configured_ids,
            "continuous_sand_identity": True,
            "cpd4_sand_exactly_reuses_accepted_clean_mask": np.array_equal(material == 1, sand_mask),
            "fibre_count": len(centrelines) == int(case["fibre_count"]),
            "positive_fibre_voxels": int(np.count_nonzero(fibre_only)) >= int(case["fibre_count"]) * int(config["voxel"]["minimum_fibre_voxels_per_fibre"]),
            "fluid_connected": connected["largest_fluid_component_fraction"] >= float(config["voxel"]["minimum_largest_fluid_component_fraction"]) and all(connected["largest_component_spans_xyz_nonperiodic"]),
            "solid_increment_close_to_cpd2": abs(increment - source_increment) <= float(config["voxel"]["maximum_absolute_cpd4_minus_cpd2_solid_increment"]),
            "gpu_memory_estimate": allocation <= int(config["voxel"]["maximum_allocation_bytes"]),
            "phase_values": set(np.unique(phase).tolist()) <= {0, 2},
            "material_values": set(np.unique(material).tolist()) <= {0, 1, 2},
        }
        if not all(checks.values()):
            raise RuntimeError(f"Stage24d geometry checks failed: {case_id}: {checks}")
        case_output = output / case_id
        case_output.mkdir()
        geometry_path = case_output / "mixed_cpd4_geometry.npz"
        np.savez_compressed(
            geometry_path,
            phase=phase,
            material=material,
            spacing_m=np.asarray([spacing]),
            cell_length_m=np.asarray([length]),
            sand_centres_m=sand,
            sand_radii_m=radii,
            fibre_centrelines_m=centrelines,
            fibre_radius_m=np.asarray([fibre_radius]),
        )
        vtk_path = case_output / "mixed_cpd4_material.vtk"
        write_binary_structured_points(vtk_path, material, np.zeros(3), spacing)
        audit = {
            "schema": "lbs.stage24d-lbs-f37-selected-cpd4-geometry.v1.case-audit",
            "status": "passed_selected_cpd4_geometry_preflight",
            "passed": True,
            "case_id": case_id,
            "packing": case["packing"],
            "orientation_regime": case["orientation_regime"],
            "placement_block": case["placement_block"],
            "fibre_count": int(case["fibre_count"]),
            "target_dry_mass_percent": float(case["target_dry_mass_percent"]),
            "achieved_dry_mass_percent": float(case["achieved_dry_mass_percent"]),
            "dimensions_xyz": list(map(int, phase.shape[::-1])),
            "spacing_m": spacing,
            "cell_length_m": length,
            "fibre_voxel_count": int(np.count_nonzero(fibre_only)),
            "source_cpd2_fibre_voxel_count": int(np.count_nonzero(source_material == 2)),
            "solid_fraction_increment": increment,
            "source_cpd2_solid_fraction_increment": source_increment,
            "voxel_porosity": float(np.count_nonzero(~solid) / solid.size),
            "estimated_gpu_allocation_bytes": allocation,
            "connectivity": connected,
            "checks": checks,
            "source_hashes": {
                "cpd2_geometry": digest(source_path),
                "clean_cpd4_geometry": digest(clean_path),
            },
        }
        write_json(case_output / "geometry_audit.json", audit)
        artifacts[case_id] = {
            "geometry": str(geometry_path.relative_to(ROOT)).replace("\\", "/"),
            "geometry_sha256": digest(geometry_path),
            "material_vtk": str(vtk_path.relative_to(ROOT)).replace("\\", "/"),
            "material_vtk_sha256": digest(vtk_path),
            "audit": str((case_output / "geometry_audit.json").relative_to(ROOT)).replace("\\", "/"),
            "audit_sha256": digest(case_output / "geometry_audit.json"),
            "phase_sha256": hashlib.sha256(phase.tobytes(order="C")).hexdigest(),
            "material_sha256": hashlib.sha256(material.tobytes(order="C")).hexdigest(),
        }
        case_rows.append(audit)
        print(json.dumps({"case_id": case_id, "dimensions": audit["dimensions_xyz"],
                          "fibre_voxels": audit["fibre_voxel_count"],
                          "connected_fraction": connected["largest_fluid_component_fraction"]}), flush=True)

    completion = {
        "schema": "lbs.stage24d-lbs-f37-selected-cpd4-geometry.v1.completion",
        "status": "passed_all_six_selected_cpd4_geometry_preflights",
        "passed": True,
        "claim_boundary": config["claim_boundary"],
        "config_sha256": digest(config_path),
        "builder_sha256": digest(Path(__file__).resolve()),
        "source_hashes": observed,
        "case_count": len(case_rows),
        "cases": case_rows,
        "artifacts": artifacts,
        "checks": {
            "exact_six_cases": len(case_rows) == 6,
            "all_case_checks": all(all(row["checks"].values()) for row in case_rows),
            "all_artifacts_present": all((ROOT / value["geometry"]).is_file() and (ROOT / value["material_vtk"]).is_file() for value in artifacts.values()),
        },
        "next_handoff": {
            "authorized": "render and visually inspect the selected CPD4 phase assignments",
            "not_authorized": "GPU execution until the render and independent evidence audit pass",
        },
    }
    write_json(output / "completion.json", completion)
    print(json.dumps({"status": completion["status"], "completion_sha256": digest(output / "completion.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
