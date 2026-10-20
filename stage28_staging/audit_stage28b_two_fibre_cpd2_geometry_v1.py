#!/usr/bin/env python3
"""Independent topology and lineage audit for Stage28b CPD2 geometry."""

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

GEOMETRY = ROOT / "stage28_designs/stage28b_two_fibre_cpd2_hydraulic_20260824/geometry_01"
CONFIG = GEOMETRY / "resolved_config.json"
COMPLETION = GEOMETRY / "completion.json"
RESULT = ROOT / "stage28_runs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_02/result.json"
OUTPUT = ROOT / "stage28_evaluations/stage28b_two_fibre_cpd2_hydraulic_20260824/geometry_audit_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def periodic_face_adjacency(first: np.ndarray, second: np.ndarray) -> int:
    total = 0
    for axis in range(3):
        total += int(np.count_nonzero(np.roll(first, 1, axis=axis) & second))
        total += int(np.count_nonzero(np.roll(first, -1, axis=axis) & second))
    return total


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable audit: {OUTPUT}")
    config, completion, result = map(load, (CONFIG, COMPLETION, RESULT))
    source_checks = {}
    for key, binding in config["lineage"].items():
        if isinstance(binding, dict) and "path" in binding and "sha256" in binding:
            path = Path(binding["path"])
            source_checks[key] = path.is_file() and sha(path) == binding["sha256"]
    case_checks, topology = {}, {}
    by_id = {case["case_id"]: case for case in result["cases"]}
    clean_artifact = Path(config["geometry"]["artifacts"]["clean"]["geometry"])
    with np.load(clean_artifact) as clean_data:
        clean_phase = np.asarray(clean_data["phase"], dtype=np.uint8)
        sand = np.asarray(clean_data["material"] == 1)
        length = float(clean_data["cell_length_m"][0])
        affine = np.asarray(clean_data["affine_scale_xyz"], dtype=float)
    radius = float(config["geometry"]["fibre_radius_m"])
    for row in config["geometry"]["cases"]:
        case_id = row["case_id"]
        artifact = config["geometry"]["artifacts"][case_id]
        path = Path(artifact["geometry"])
        with np.load(path) as data:
            phase = np.asarray(data["phase"], dtype=np.uint8)
            material = np.asarray(data["material"], dtype=np.uint8)
            centrelines = np.asarray(data["fibre_centrelines_m"], dtype=float)
        checks = {
            "artifact_hash": sha(path) == artifact["geometry_sha256"],
            "shape_matches_clean": phase.shape == clean_phase.shape,
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
            raw_overlap = int(np.count_nonzero(raw[0] & raw[1]))
            face_adjacency = periodic_face_adjacency(raw[0], raw[1])
            union_only = (raw[0] | raw[1]) & ~sand
            checks["rasterisation_reproduces_material"] = np.array_equal(union_only, material == 2)
            if case_id.startswith("separated_"):
                checks["separated_masks_noncontacting"] = raw_overlap == 0 and face_adjacency == 0
            else:
                checks["crossing_contact_resolved_at_cpd2"] = raw_overlap > 0 or face_adjacency > 0
            topology[case_id] = {"raw_overlap_voxels": raw_overlap, "periodic_face_adjacency_count": face_adjacency}
        case_checks[case_id] = checks
    global_checks = {
        "config_fail_closed": config["status"] == "geometry_built_independent_gpu_release_required"
        and config["authority"]["gpu_cpd2_pilot"] is False,
        "completion_bound": completion["passed"] and completion["config_sha256"] == sha(CONFIG),
        "all_sources_bound": all(source_checks.values()),
        "all_builder_checks_passed": all(config["checks"].values()),
        "all_case_checks_passed": all(all(checks.values()) for checks in case_checks.values()),
        "exact_case_order": [row["case_id"] for row in config["geometry"]["cases"]]
        == ["clean", "separated_open_open", "separated_open_constricted", "crossing_interaction"],
        "clean_geometry_matches_stage27": sha(clean_artifact) == config["geometry"]["artifacts"]["clean"]["geometry_sha256"],
    }
    passed = all(global_checks.values())
    status = "cpd2_geometry_topology_verified_runner_audit_required" if passed else "cpd2_geometry_not_qualified"
    audit = {"schema": "lbs.stage28b-two-fibre-cpd2-geometry-audit.v1", "status": status,
             "timestamp_utc": datetime.now(timezone.utc).isoformat(), "passed": passed,
             "checks": global_checks, "case_checks": case_checks, "topology": topology,
             "source_checks": source_checks,
             "bindings": {"config_sha256": sha(CONFIG), "completion_sha256": sha(COMPLETION),
                          "mechanics_result_sha256": sha(RESULT)},
             "authority": {"runner_implementation_and_audit": passed, "gpu_execution": False,
                           "cpd4": False, "production_concentration_campaign": False}}
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "audit.json"
    path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"audit": str(path), "sha256": sha(path), "passed": passed,
                      "checks": global_checks, "topology": topology}, indent=2))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
