#!/usr/bin/env python3
"""Independently release or reject the Stage28c CPD4 design."""

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
CONFIG = ROOT / "stage28_designs" / STUDY / "geometry_01/resolved_config.json"
COMPLETION = CONFIG.parent / "completion.json"
OUTPUT = ROOT / "stage28_evaluations" / STUDY / "design_audit_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def periodic_face_adjacency(first: np.ndarray, second: np.ndarray) -> int:
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
    case_checks, topology, phase_counts = {}, {}, {}
    clean_path = Path(config["geometry"]["artifacts"]["clean"]["geometry"])
    with np.load(clean_path, allow_pickle=False) as data:
        clean_phase = np.asarray(data["phase"], dtype=np.uint8)
        clean_material = np.asarray(data["material"], dtype=np.uint8)
        sand = clean_material == 1
        length = float(data["cell_length_m"][0])
    radius = float(config["geometry"]["fibre_radius_m"])
    cpd2_config = load(Path(config["lineage"]["stage28b_cpd2_config"]["path"]))
    cpd2_rows = {row["case_id"]: row for row in cpd2_config["geometry"]["cases"]}
    cpd4_rows = {row["case_id"]: row for row in config["geometry"]["cases"]}
    voxel_scales = {}
    for case_id in ("clean", "separated_open_open", "crossing_interaction"):
        artifact = config["geometry"]["artifacts"][case_id]
        path = Path(artifact["geometry"])
        with np.load(path, allow_pickle=False) as data:
            phase = np.asarray(data["phase"], dtype=np.uint8)
            material = np.asarray(data["material"], dtype=np.uint8)
            centrelines = np.asarray(data["fibre_centrelines_m"], dtype=float)
        phase_counts[case_id] = int(np.count_nonzero(phase != 0))
        checks = {
            "artifact_hash": sha(path) == artifact["geometry_sha256"],
            "shape_186_cubed": phase.shape == (186, 186, 186),
            "sand_exact": np.array_equal(material == 1, sand),
            "phase_material_consistent": np.array_equal(phase != 0, material != 0),
            "clean_exact_or_two_centrelines": np.array_equal(phase, clean_phase) if case_id == "clean" else centrelines.shape == (2, 37, 3),
        }
        if case_id != "clean":
            raw = []
            for points in centrelines:
                mask = np.zeros_like(sand)
                api.mark_capsule(mask, points, radius, length)
                raw.append(mask)
            overlap = int(np.count_nonzero(raw[0] & raw[1]))
            adjacency = periodic_face_adjacency(raw[0], raw[1])
            union_only = (raw[0] | raw[1]) & ~sand
            checks["rasterisation_reproduces_material"] = np.array_equal(union_only, material == 2)
            if case_id == "separated_open_open":
                checks["separated_masks_noncontacting"] = overlap == 0 and adjacency == 0
            else:
                checks["crossing_contact_resolved"] = overlap > 0 or adjacency > 0
            topology[case_id] = {"raw_overlap_voxels": overlap, "periodic_face_adjacency_count": adjacency}
            voxel_scales[case_id] = cpd4_rows[case_id]["fibre_union_only_voxel_count"] / cpd2_rows[case_id]["fibre_union_only_voxel_count"]
        case_checks[case_id] = checks
    warm_ok = all(Path(row["path"]).is_file() and sha(Path(row["path"])) == row["sha256"]
                  for row in config["cpd2_reference"]["warm_starts"].values())
    cells = 186 ** 3
    estimated_device_bytes = 2 * (19 * cells * 4) + cells + 4
    a = config["acceptance"]
    checks = {
        "config_completion_binding": completion.get("passed") and completion["config_sha256"] == sha(CONFIG),
        "config_fail_closed": config["status"] == "cpd4_geometry_built_independent_gpu_release_required" and not config["authority"]["gpu_cpd4_execution"],
        "all_sources_bound": all(source_checks.values()),
        "all_builder_checks_passed": all(config["checks"].values()),
        "all_case_checks_passed": all(all(values.values()) for values in case_checks.values()),
        "exact_selected_case_order": [row["case_id"] for row in config["geometry"]["cases"]] == ["clean", "separated_open_open", "crossing_interaction"],
        "clean_geometry_exact_stage27b": sha(clean_path) == config["lineage"]["stage27b_clean_cpd4_geometry"]["sha256"],
        "warm_start_hashes": warm_ok,
        "fibre_voxel_scaling": all(7.0 <= value <= 9.0 for value in voxel_scales.values()),
        "device_memory_below_4gb": estimated_device_bytes < 4 * 1024 ** 3,
        "acceptance_frozen": float(a["maximum_absolute_two_fibre_ratio_shift"]) == 0.002
        and float(a["maximum_absolute_crossing_minus_separated_contrast_shift"]) == 0.001
        and float(a["maximum_relative_clean_reproduction_error"]) == 1e-12,
        "no_new_physics": not any(config["authority"][key] for key in ("production_concentration_campaign", "mobile_sand", "two_way_coupling")),
    }
    passed = all(checks.values())
    OUTPUT.mkdir(parents=True)
    audit = {
        "schema": "lbs.stage28c-selected-two-fibre-cpd4-design-audit.v1",
        "status": "passed_gpu_execution_release" if passed else "failed_closed", "passed": passed,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "checks": checks,
        "case_checks": case_checks, "source_checks": source_checks,
        "metrics": {"topology": topology, "fibre_voxel_scales_cpd4_over_cpd2": voxel_scales,
                    "phase_solid_counts": phase_counts, "estimated_device_bytes": estimated_device_bytes,
                    "estimated_device_gib": estimated_device_bytes / 1024 ** 3},
        "source_bindings": {"config": {"path": str(CONFIG), "sha256": sha(CONFIG)},
                            "completion": {"path": str(COMPLETION), "sha256": sha(COMPLETION)},
                            "auditor": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).resolve())}},
        "authority": {"gpu_cpd4_execution": passed, "independent_result_evaluation": passed,
                      "render": False, "production_concentration_campaign": False,
                      "mobile_sand": False, "two_way_coupling": False},
    }
    audit_path = OUTPUT / "design_audit.json"
    write(audit_path, audit)
    handoff = {
        "schema": audit["schema"] + ".handoff", "status": "gpu_cpd4_execution_authorized" if passed else "fail_closed",
        "passed": passed, "design_audit": {"path": str(audit_path), "sha256": sha(audit_path)},
        "next_handoff": {"authorized": "one immutable three-case CPD4 GPU run followed by independent evaluation",
                         "not_authorized": "rerun, production concentration, mechanics, deformation or two-way coupling"},
    }
    handoff_path = OUTPUT / "execution_handoff.json"
    write(handoff_path, handoff)
    print(json.dumps({"passed": passed, "audit": str(audit_path), "audit_sha256": sha(audit_path),
                      "handoff": str(handoff_path), "handoff_sha256": sha(handoff_path),
                      "checks": checks, "metrics": audit["metrics"]}, indent=2))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
