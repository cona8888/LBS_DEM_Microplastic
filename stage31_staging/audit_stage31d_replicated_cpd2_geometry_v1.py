#!/usr/bin/env python3
"""Independently audit the Stage31d 21-case CPD2 geometry bundle."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
SOURCE = ROOT / "stage31_designs/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_01"
CONFIG = SOURCE / "resolved_config.json"
COMPLETION = SOURCE / "completion.json"
OUTPUT = ROOT / "stage31_evaluations/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_audit_03"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_default(value):
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"unsupported JSON value: {type(value)!r}")


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable geometry audit: {OUTPUT}")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    completion = json.loads(COMPLETION.read_text(encoding="utf-8"))
    source_checks = {
        name: Path(binding["path"]).is_file() and sha(Path(binding["path"])) == binding["sha256"]
        for name, binding in config["lineage"].items()
        if isinstance(binding, dict) and "path" in binding and "sha256" in binding
    }
    case_checks, materials = {}, {}
    for row in config["geometry"]["cases"]:
        case_id = row["case_id"]
        artifact = config["geometry"]["artifacts"][case_id]
        geometry_path = Path(artifact["geometry"])
        vtk_path = Path(artifact["material_vtk"])
        with np.load(geometry_path) as data:
            phase = np.asarray(data["phase"], dtype=np.uint8)
            material = np.asarray(data["material"], dtype=np.uint8)
            centrelines = np.asarray(data["fibre_centrelines_m"], dtype=float)
            spacing = float(data["spacing_m"][0])
            length = float(data["cell_length_m"][0])
            affine = np.asarray(data["affine_scale_xyz"], dtype=float)
        materials[case_id] = material
        mechanics_binding = artifact.get("mechanics_case")
        mechanics_ok = mechanics_binding is None if row["fibre_count"] == 0 else Path(mechanics_binding["path"]).is_file() and sha(Path(mechanics_binding["path"])) == mechanics_binding["sha256"]
        checks = {
            "geometry_hash": sha(geometry_path) == artifact["geometry_sha256"],
            "vtk_hash": sha(vtk_path) == artifact["material_vtk_sha256"],
            "mechanics_hash_or_clean": mechanics_ok,
            "shape_93_cubed": phase.shape == material.shape == (93, 93, 93),
            "phase_material_consistent": np.array_equal(phase != 0, material != 0),
            "material_labels_exact": set(np.unique(material)).issubset({0, 1, 2}),
            "centrelines_exact": centrelines.shape == (int(row["fibre_count"]), 37, 3),
            "spacing_consistent": abs(spacing * 93 - length) <= 1.0e-15,
            "affine_finite": affine.shape == (3,) and bool(np.all(np.isfinite(affine))),
            "voxel_counts_match": int(np.count_nonzero(material == 1)) == int(row["sand_voxel_count"]) and int(np.count_nonzero(material == 2)) == int(row["fibre_only_voxel_count"]),
            "builder_checks": all(row["checks"].values()),
        }
        case_checks[case_id] = checks
    nested_checks = {}
    for packing in ("n216_s1", "n216_s2", "n216_s3"):
        clean_id = f"s31b_{packing}_clean"
        clean_sand = materials[clean_id] == 1
        for block in ("A", "B"):
            ids = [f"s31b_{packing}_{block}_f{count:03d}_open" for count in (1, 2, 4)]
            fibre_masks = [materials[case_id] == 2 for case_id in ids]
            nested_checks[f"{packing}_{block}"] = {
                "sand_exact_across_prefixes": all(np.array_equal(materials[case_id] == 1, clean_sand) for case_id in ids),
                "one_subset_two": not np.any(fibre_masks[0] & ~fibre_masks[1]),
                "two_subset_four": not np.any(fibre_masks[1] & ~fibre_masks[2]),
                "strict_voxel_growth": np.count_nonzero(fibre_masks[0]) < np.count_nonzero(fibre_masks[1]) < np.count_nonzero(fibre_masks[2]),
            }
    checks = {
        "config_fail_closed": config["status"] == "geometry_built_independent_audit_required" and config["authority"]["gpu_execution"] is False,
        "completion_passed_bound": completion.get("passed") is True and completion.get("config_sha256") == sha(CONFIG),
        "all_lineage_hashes": bool(source_checks) and all(source_checks.values()),
        "exact_twenty_one_cases": len(case_checks) == 21,
        "all_case_checks": all(all(item.values()) for item in case_checks.values()),
        "all_nested_prefix_checks": all(all(item.values()) for item in nested_checks.values()),
        "builder_global_checks": all(config["checks"].values()),
        "flow_order_exact": [row["flow_order"] for row in config["geometry"]["cases"]] == list(range(1, 22)),
    }
    passed = all(checks.values())
    audit = {
        "schema": "lbs.stage31d-replicated-nested-cpd2-geometry-audit.v1",
        "status": "passed_geometry_audit_visual_review_required" if passed else "failed_geometry_audit",
        "passed": passed,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "case_checks": case_checks,
        "nested_checks": nested_checks,
        "source_checks": source_checks,
        "bindings": {"config_sha256": sha(CONFIG), "completion_sha256": sha(COMPLETION)},
        "authority": {"visual_review": passed, "gpu_execution": False, "cpd4": False, "permeability_claim": False, "mobile_sand": False, "coupling": False},
        "decision": "Render and visually inspect the terminal CPD2 geometry; flow remains unauthorized.",
    }
    OUTPUT.mkdir(parents=True)
    audit_path = OUTPUT / "geometry_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True, default=json_default) + "\n", encoding="utf-8")
    (OUTPUT / "checkpoint_manifest.json").write_text(json.dumps({"schema": audit["schema"] + ".checkpoint", "passed": passed, "audit_sha256": sha(audit_path), "config_sha256": sha(CONFIG), "authority": audit["authority"]}, indent=2, sort_keys=True, default=json_default) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "status": audit["status"], "passed": passed, "checks": checks, "nested_checks": nested_checks}, indent=2, default=json_default))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
