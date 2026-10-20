#!/usr/bin/env python3
"""Independently release or reject the Stage27b CPD4 execution design."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
STUDY = "stage27b_stage26x_mechanics_hydraulic_cpd4_20260824"
CONFIG = ROOT / "stage27_designs" / STUDY / "geometry_01/resolved_config.json"
COMPLETION = CONFIG.parent / "completion.json"
OUTPUT = ROOT / "stage27_evaluations" / STUDY / "design_audit_01"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUTPUT}")
    config, completion = load(CONFIG), load(COMPLETION)
    case_by_id = {row["case_id"]: row for row in config["geometry"]["cases"]}
    cpd2_config = load(Path(config["lineage"]["cpd2_config"]["path"]))
    cpd2 = {row["case_id"]: row for row in cpd2_config["geometry"]["cases"]}
    artifacts_ok, phase_counts = True, {}
    for case_id, binding in config["geometry"]["artifacts"].items():
        path = Path(binding["geometry"])
        artifacts_ok &= digest(path) == binding["geometry_sha256"]
        with np.load(path, allow_pickle=False) as archive:
            phase = np.asarray(archive["phase"], dtype=np.uint8)
            phase_counts[case_id] = int(np.count_nonzero(phase == 2))
            artifacts_ok &= phase.shape == (186, 186, 186) and set(np.unique(phase).tolist()) <= {0, 2}
    warm_ok = all(digest(Path(row["path"])) == row["sha256"] for row in config["cpd2_reference"]["warm_starts"].values())
    open_scale = case_by_id["open"]["fibre_only_voxel_count"] / cpd2["open"]["fibre_only_voxel_count"]
    constricted_scale = case_by_id["constricted"]["fibre_only_voxel_count"] / cpd2["constricted"]["fibre_only_voxel_count"]
    cells = 186**3
    initial_state_bytes = 19 * cells * 4
    estimated_device_bytes = 2 * initial_state_bytes + cells + 4
    checks = {
        "config_completion_binding": digest(CONFIG) == completion["config_sha256"],
        "completion_passed": bool(completion.get("passed") and all(completion.get("checks", {}).values())),
        "upstream_authority_is_design_only": bool(config["authority"]["independent_design_audit"] and not config["authority"]["gpu_cpd4_execution"]),
        "artifacts_and_phase_valid": bool(artifacts_ok),
        "warm_start_hashes": bool(warm_ok),
        "resolution_exact": config["geometry"]["resolution"] == [186, 186, 186],
        "fibre_resolution": float(config["geometry"]["fibre_diameter_cells"]) >= 3.9,
        "fibre_voxel_scaling": 7.5 <= open_scale <= 8.5 and 7.5 <= constricted_scale <= 8.5,
        "device_memory_below_4gb": estimated_device_bytes < 4 * 1024**3,
        "acceptance_frozen": float(config["acceptance"]["maximum_absolute_single_fibre_ratio_shift"]) == 0.002 and float(config["acceptance"]["maximum_absolute_placement_contrast_shift"]) == 0.001,
        "no_new_physics": not any(config["authority"][key] for key in ("concentration_campaign", "mobile_sand", "two_way_coupling")),
    }
    passed = all(checks.values())
    OUTPUT.mkdir(parents=True)
    audit = {"schema": "lbs.stage27b-stage26x-mechanics-hydraulic-cpd4-design-audit.v1", "status": "passed_gpu_execution_release" if passed else "failed_closed", "passed": passed, "timestamp_utc": datetime.now(timezone.utc).isoformat(), "checks": checks, "metrics": {"open_fibre_voxel_scale_cpd4_over_cpd2": open_scale, "constricted_fibre_voxel_scale_cpd4_over_cpd2": constricted_scale, "estimated_device_bytes": estimated_device_bytes, "estimated_device_gib": estimated_device_bytes / 1024**3, "phase_solid_counts": phase_counts}, "source_bindings": {"config": {"path": str(CONFIG), "sha256": digest(CONFIG)}, "completion": {"path": str(COMPLETION), "sha256": digest(COMPLETION)}, "auditor": {"path": str(Path(__file__).resolve()), "sha256": digest(Path(__file__).resolve())}}, "authority": {"gpu_cpd4_execution": passed, "independent_result_evaluation": passed, "render": False, "concentration_campaign": False, "mobile_sand": False, "two_way_coupling": False}}
    audit_path = OUTPUT / "design_audit.json"
    write(audit_path, audit)
    handoff = {"schema": audit["schema"] + ".handoff", "status": "gpu_cpd4_execution_authorized" if passed else "fail_closed", "passed": passed, "design_audit": {"path": str(audit_path), "sha256": digest(audit_path)}, "next_handoff": {"authorized": "one immutable three-case CPD4 GPU run followed by independent evaluation", "not_authorized": "rerun, CPD2 overwrite, concentration campaign, mobile mechanics or two-way coupling"}}
    handoff_path = OUTPUT / "execution_handoff.json"
    write(handoff_path, handoff)
    print(json.dumps({"passed": passed, "audit": str(audit_path), "audit_sha256": digest(audit_path), "handoff": str(handoff_path), "handoff_sha256": digest(handoff_path), "metrics": audit["metrics"]}, indent=2))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
