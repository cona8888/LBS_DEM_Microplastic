#!/usr/bin/env python3
"""Independently audit the immutable Stage31f CPD4 design."""

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

STUDY = "stage31f_selected_replicated_cpd4_20260827"
CONFIG = ROOT / "stage31_designs" / STUDY / "geometry_01/resolved_config.json"
COMPLETION = CONFIG.parent / "completion.json"
OUTPUT = ROOT / "stage31_evaluations" / STUDY / "design_audit_01"
ORDER = (
    "s31b_n216_s2_clean", "s31b_n216_s1_A_f001_open", "s31b_n216_s1_A_f002_open",
    "s31b_n216_s1_A_f004_open", "s31b_n216_s1_B_f004_open",
    "s31b_n216_s2_A_f004_open", "s31b_n216_s2_B_f004_open",
)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def face_adjacency(first: np.ndarray, second: np.ndarray) -> int:
    return sum(int(np.count_nonzero(np.roll(first, shift, axis=axis) & second))
               for axis in range(3) for shift in (-1, 1))


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable audit: {OUTPUT}")
    config, completion = load(CONFIG), load(COMPLETION)
    source_checks = {}
    for key, binding in config["lineage"].items():
        if isinstance(binding, dict) and "path" in binding and "sha256" in binding:
            path = Path(binding["path"])
            source_checks[key] = path.is_file() and sha(path) == binding["sha256"]

    rows = {row["case_id"]: row for row in config["geometry"]["cases"]}
    case_checks, topology, voxel_scales = {}, {}, {}
    sand_by_packing = {}
    radius = float(config["geometry"]["fibre_radius_m"])
    for case_id in ORDER:
        row = rows[case_id]
        artifact = config["geometry"]["artifacts"][case_id]
        path, vtk = Path(artifact["geometry"]), Path(artifact["material_vtk"])
        source = Path(artifact["source_cpd2_geometry"])
        with np.load(path, allow_pickle=False) as data:
            phase = np.asarray(data["phase"], dtype=np.uint8)
            material = np.asarray(data["material"], dtype=np.uint8)
            centres = np.asarray(data["sand_centres_m"], dtype=float)
            radii = np.asarray(data["sand_radii_m"], dtype=float)
            centrelines = np.asarray(data["fibre_centrelines_m"], dtype=float)
            length = float(data["cell_length_m"][0])
            spacing = float(data["spacing_m"][0])
        sand_expected = np.zeros((186, 186, 186), dtype=bool)
        api.mark_spheres(sand_expected, centres, radii, length)
        sand = material == 1
        if row["packing_id"] in sand_by_packing:
            same_packing_sand = np.array_equal(sand, sand_by_packing[row["packing_id"]])
        else:
            sand_by_packing[row["packing_id"]] = sand.copy()
            same_packing_sand = True
        checks = {
            "geometry_hash": path.is_file() and sha(path) == artifact["geometry_sha256"],
            "vtk_hash": vtk.is_file() and sha(vtk) == artifact["material_vtk_sha256"],
            "cpd2_source_hash": source.is_file() and sha(source) == artifact["source_cpd2_geometry_sha256"],
            "shape_186_cubed": phase.shape == material.shape == (186, 186, 186),
            "spacing_exact": math.isclose(spacing, length / 186.0, rel_tol=0.0, abs_tol=1e-18),
            "phase_material_consistent": np.array_equal(phase != 0, material != 0),
            "sand_raster_reproduced": np.array_equal(sand, sand_expected),
            "same_packing_sand_exact": same_packing_sand,
            "fibre_count_exact": centrelines.shape == (row["fibre_count"], 37, 3),
            "fluid_connected_and_spanning": api.connectivity(phase != 0)["largest_fluid_component_fraction"] >= 0.99
                and all(api.connectivity(phase != 0)["largest_component_spans_xyz_nonperiodic"]),
        }
        masks = []
        for points in centrelines:
            mask = np.zeros_like(sand)
            api.mark_capsule(mask, points, radius, length)
            masks.append(mask)
        if masks:
            expected_fibre = np.logical_or.reduce(masks) & ~sand
            checks["fibre_raster_reproduced"] = np.array_equal(expected_fibre, material == 2)
            overlaps, adjacencies = [], []
            for i in range(len(masks)):
                for j in range(i + 1, len(masks)):
                    overlaps.append(int(np.count_nonzero(masks[i] & masks[j])))
                    adjacencies.append(face_adjacency(masks[i], masks[j]))
            checks["zero_interfibre_contact"] = all(value == 0 for value in overlaps + adjacencies)
            voxel_scales[case_id] = int(np.count_nonzero(material == 2)) / row["cpd2_fibre_only_voxel_count"]
            checks["fibre_voxel_scale_7_to_9"] = 7.0 <= voxel_scales[case_id] <= 9.0
            topology[case_id] = {"raw_overlap_voxels": overlaps, "periodic_face_adjacency_counts": adjacencies}
        else:
            checks["clean_has_no_fibre_voxels"] = not np.any(material == 2)
        case_checks[case_id] = checks

    cpd2 = {row["case_id"]: row for row in config["cpd2_reference"]["paired_results"]}
    s1_sequence = [cpd2[f"s31b_n216_s1_A_f{count:03d}_open"]["paired_permeability_ratio"] for count in (1, 2, 4)]
    s1_contrast = cpd2["s31b_n216_s1_B_f004_open"]["paired_permeability_ratio"] - cpd2["s31b_n216_s1_A_f004_open"]["paired_permeability_ratio"]
    s2_contrast = cpd2["s31b_n216_s2_B_f004_open"]["paired_permeability_ratio"] - cpd2["s31b_n216_s2_A_f004_open"]["paired_permeability_ratio"]
    reused = config["reused_s1_clean_cpd4"]
    reused_checks = {
        key: Path(binding["path"]).is_file() and sha(Path(binding["path"])) == binding["sha256"]
        for key, binding in reused.items() if isinstance(binding, dict) and "path" in binding
    }
    cells = 186 ** 3
    estimated_device_bytes = 2 * (19 * cells * 4) + cells + 4
    acceptance = config["acceptance"]
    checks = {
        "config_completion_binding": completion.get("passed") is True and completion["config_sha256"] == sha(CONFIG),
        "config_fail_closed": config["status"] == "cpd4_geometry_built_independent_gpu_release_required" and config["authority"]["gpu_cpd4_execution"] is False,
        "all_lineage_hashes": all(source_checks.values()),
        "all_builder_checks": all(config["checks"].values()),
        "all_case_checks": all(all(values.values()) for values in case_checks.values()),
        "exact_selected_order": [row["case_id"] for row in config["geometry"]["cases"]] == list(ORDER),
        "seven_new_cases": len(config["geometry"]["cases"]) == 7,
        "all_warm_starts_bound": all(Path(item["path"]).is_file() and sha(Path(item["path"])) == item["sha256"] for item in config["cpd2_reference"]["warm_starts"].values()),
        "reused_s1_clean_all_bound": all(reused_checks.values()) and len(reused_checks) == 4,
        "s1_sequence_strictly_decreasing_observed_not_imposed": s1_sequence[0] > s1_sequence[1] > s1_sequence[2],
        "opposite_block_contrast_signs_selected": s1_contrast > 0 and s2_contrast < 0,
        "acceptance_frozen": math.isclose(acceptance["maximum_absolute_selected_ratio_shift"], 0.002)
            and math.isclose(acceptance["maximum_absolute_block_contrast_shift"], 0.001),
        "device_memory_below_4gb": estimated_device_bytes < 4 * 1024 ** 3,
        "authority_narrow": not any(config["authority"].get(key, False) for key in
            ("absolute_permeability_validation_claim", "mechanics_rerun", "mobile_sand", "migration",
             "clogging", "deformation", "transient_coupling", "two_way_coupling")),
    }
    passed = all(checks.values())
    OUTPUT.mkdir(parents=True)
    audit = {
        "schema": "lbs.stage31f-selected-replicated-cpd4-design-audit.v1",
        "status": "passed_design_audit" if passed else "failed_closed", "passed": passed,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "checks": checks,
        "case_checks": case_checks, "source_checks": source_checks, "reused_s1_clean_checks": reused_checks,
        "metrics": {"voxel_scales_cpd4_over_cpd2": voxel_scales, "topology": topology,
                    "cpd2_s1_A_ratios_1_2_4": s1_sequence,
                    "cpd2_four_fibre_block_contrasts_B_minus_A": {"n216_s1": s1_contrast, "n216_s2": s2_contrast},
                    "estimated_device_bytes": estimated_device_bytes, "estimated_device_gib": estimated_device_bytes / 1024 ** 3},
        "bindings": {"config": {"path": str(CONFIG), "sha256": sha(CONFIG)},
                     "completion": {"path": str(COMPLETION), "sha256": sha(COMPLETION)},
                     "auditor": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).resolve())}},
        "authority": {"runner_audit": passed, "gpu_cpd4_execution": False, "render": False,
                      "absolute_permeability_validation_claim": False, "mobile_sand": False,
                      "migration": False, "clogging": False, "deformation": False,
                      "transient_coupling": False, "two_way_coupling": False},
    }
    audit_path = OUTPUT / "design_audit.json"
    write(audit_path, audit)
    handoff = {
        "schema": audit["schema"] + ".handoff", "status": "runner_audit_authorized" if passed else "fail_closed",
        "passed": passed, "design_audit": {"path": str(audit_path), "sha256": sha(audit_path)},
        "next_handoff": {"authorized": "independent frozen-runner audit", "not_authorized": "GPU execution before a runner-hash-bound release"},
    }
    write(OUTPUT / "runner_audit_handoff.json", handoff)
    print(json.dumps({"passed": passed, "audit": str(audit_path), "audit_sha256": sha(audit_path),
                      "checks": checks, "metrics": audit["metrics"]}, indent=2))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
