#!/usr/bin/env python3
"""Independently audit the frozen Stage30a selected CPD4 geometry."""

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

STUDY = "stage30a_selected_low_concentration_cpd4_20260826"
CONFIG = ROOT / "stage30_designs" / STUDY / "geometry_01/resolved_config.json"
COMPLETION = CONFIG.parent / "completion.json"
OUTPUT = ROOT / "stage30_evaluations" / STUDY / "design_audit_02"
ORDER = ("clean", "s29e_f001_isolated_B", "s29e_f004_zero_contact_context_B", "s29e_f004_one_contact_context_B")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def face_adjacency(first: np.ndarray, second: np.ndarray) -> int:
    return sum(int(np.count_nonzero(np.roll(first, shift, axis=axis) & second)) for axis in range(3) for shift in (-1, 1))


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable audit: {OUTPUT}")
    config, completion = load(CONFIG), load(COMPLETION)
    source_checks = {}
    for key, binding in config["lineage"].items():
        if isinstance(binding, dict) and "path" in binding and "sha256" in binding:
            path = Path(binding["path"])
            source_checks[key] = path.is_file() and sha(path) == binding["sha256"]
    clean_path = Path(config["geometry"]["artifacts"]["clean"]["geometry"])
    with np.load(clean_path, allow_pickle=False) as data:
        clean_phase = np.asarray(data["phase"], dtype=np.uint8)
        clean_material = np.asarray(data["material"], dtype=np.uint8)
        sand = clean_material == 1
        length = float(data["cell_length_m"][0])
    radius = float(config["geometry"]["fibre_radius_m"])
    config_rows = {row["case_id"]: row for row in config["geometry"]["cases"]}
    case_checks, topology, voxel_scales = {}, {}, {}
    for case_id in ORDER:
        artifact = config["geometry"]["artifacts"][case_id]
        path = Path(artifact["geometry"])
        with np.load(path, allow_pickle=False) as data:
            phase = np.asarray(data["phase"], dtype=np.uint8)
            material = np.asarray(data["material"], dtype=np.uint8)
            centrelines = np.asarray(data["fibre_centrelines_m"], dtype=float)
        row = config_rows[case_id]
        checks = {
            "artifact_hash": path.is_file() and sha(path) == artifact["geometry_sha256"],
            "shape_186_cubed": phase.shape == (186, 186, 186),
            "sand_exact": np.array_equal(material == 1, sand),
            "phase_material_consistent": np.array_equal(phase != 0, material != 0),
            "fibre_count_exact": centrelines.size == 0 if row["fibre_count"] == 0 else centrelines.shape == (row["fibre_count"], 37, 3),
            "connectivity_recomputed": api.connectivity(phase != 0)["largest_fluid_component_fraction"] >= 0.99,
        }
        if case_id == "clean":
            checks["clean_phase_exact"] = np.array_equal(phase, clean_phase)
        else:
            masks = []
            for points in centrelines:
                mask = np.zeros_like(sand)
                api.mark_capsule(mask, points, radius, length)
                masks.append(mask)
            union_only = np.logical_or.reduce(masks) & ~sand
            checks["rasterisation_reproduces_material"] = np.array_equal(union_only, material == 2)
            overlaps, adjacencies = [], []
            for i in range(len(masks)):
                for j in range(i + 1, len(masks)):
                    overlaps.append(int(np.count_nonzero(masks[i] & masks[j])))
                    adjacencies.append(face_adjacency(masks[i], masks[j]))
            topology[case_id] = {"raw_overlap_voxels": overlaps, "periodic_face_adjacency_counts": adjacencies}
            if row["topology"] == "zero_contact":
                checks["zero_contact_exact"] = all(v == 0 for v in overlaps + adjacencies)
            if row["topology"] == "one_contact":
                checks["one_contact_resolved"] = sum(v > 0 for v in overlaps) + sum(v > 0 for v in adjacencies) >= 1
            voxel_scales[case_id] = row["fibre_union_only_voxel_count"] / row["cpd2_fibre_union_only_voxel_count"]
        case_checks[case_id] = checks
    cells = 186 ** 3
    estimated_device_bytes = 2 * (19 * cells * 4) + cells + 4
    a = config["acceptance"]
    cpd2 = {row["case_id"]: row for row in config["cpd2_reference"]["paired_results"]}
    single_b = cpd2["s29e_f001_isolated_B"]["paired_permeability_ratio"]
    stage29_eval = load(Path(config["lineage"]["stage29e_cpd2_evaluation"]["path"]))
    single_mean = stage29_eval["branch_summary"]["single_isolated"]["mean"]
    contrast_b = cpd2["s29e_f004_one_contact_context_B"]["paired_permeability_ratio"] - cpd2["s29e_f004_zero_contact_context_B"]["paired_permeability_ratio"]
    contrast_mean = stage29_eval["effects_k_over_k0"]["four_one_minus_zero_paired"]["summary"]["mean"]
    checks = {
        "config_completion_binding": completion.get("passed") and completion["config_sha256"] == sha(CONFIG),
        "config_fail_closed": config["status"] == "cpd4_geometry_built_independent_gpu_release_required" and config["authority"]["gpu_cpd4_execution"] is False,
        "all_sources_bound": all(source_checks.values()),
        "all_builder_checks_passed": all(config["checks"].values()),
        "all_case_checks_passed": all(all(values.values()) for values in case_checks.values()),
        "exact_selected_case_order": [row["case_id"] for row in config["geometry"]["cases"]] == list(ORDER),
        "clean_geometry_exact_stage27b": sha(clean_path) == config["lineage"]["stage27b_clean_cpd4_geometry"]["sha256"],
        "warm_start_hashes": all(Path(v["path"]).is_file() and sha(Path(v["path"])) == v["sha256"] for v in config["cpd2_reference"]["warm_starts"].values()),
        "fibre_voxel_scaling": all(7.0 <= value <= 9.0 for value in voxel_scales.values()),
        "representative_block_b": abs(single_b - single_mean) <= 1e-4 and abs(contrast_b - contrast_mean) <= 1e-4,
        "device_memory_below_4gb": estimated_device_bytes < 4 * 1024 ** 3,
        "acceptance_frozen": math.isclose(float(a["maximum_absolute_selected_ratio_shift"]), 0.002)
        and math.isclose(float(a["maximum_absolute_four_fibre_contrast_shift"]), 0.001)
        and math.isclose(float(a["maximum_relative_clean_reproduction_error"]), 1e-12),
        "no_new_physics": all(config["authority"][k] is False for k in ("permeability_validation_claim", "mechanics_rerun", "mobile_sand", "migration", "clogging", "two_way_coupling")),
    }
    passed = all(checks.values())
    OUTPUT.mkdir(parents=True)
    audit = {
        "schema": "lbs.stage30a-selected-low-concentration-cpd4-design-audit.v1",
        "status": "passed_gpu_execution_release" if passed else "failed_closed", "passed": passed,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "checks": checks, "case_checks": case_checks,
        "source_checks": source_checks, "metrics": {"topology": topology, "fibre_voxel_scales_cpd4_over_cpd2": voxel_scales,
        "selected_single_b_minus_mean": single_b - single_mean, "selected_contrast_b_minus_mean": contrast_b - contrast_mean,
        "estimated_device_bytes": estimated_device_bytes, "estimated_device_gib": estimated_device_bytes / 1024 ** 3},
        "source_bindings": {"config": {"path": str(CONFIG), "sha256": sha(CONFIG)},
        "completion": {"path": str(COMPLETION), "sha256": sha(COMPLETION)},
        "auditor": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).resolve())}},
        "authority": {"gpu_cpd4_execution": passed, "independent_result_evaluation": passed, "render": False,
        "permeability_validation_claim": False, "mechanics_rerun": False, "mobile_sand": False,
        "migration": False, "clogging": False, "two_way_coupling": False},
    }
    audit_path = OUTPUT / "design_audit.json"
    write(audit_path, audit)
    handoff = {"schema": audit["schema"] + ".handoff", "status": "gpu_cpd4_execution_design_authorized" if passed else "fail_closed",
    "passed": passed, "design_audit": {"path": str(audit_path), "sha256": sha(audit_path)},
    "next_handoff": {"authorized": "execution-release audit for one immutable four-case CPD4 run", "not_authorized": "GPU execution before runner audit"}}
    handoff_path = OUTPUT / "execution_handoff.json"
    write(handoff_path, handoff)
    print(json.dumps({"passed": passed, "audit": str(audit_path), "audit_sha256": sha(audit_path),
                      "handoff": str(handoff_path), "checks": checks, "metrics": audit["metrics"]}, indent=2))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
