#!/usr/bin/env python3
"""Independently release the bounded Stage31e 21-case CPD2 GPU screen."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = ROOT / "stage31_designs/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_01/resolved_config.json"
COMPLETION = CONFIG.parent / "completion.json"
GEOMETRY_AUDIT = ROOT / "stage31_evaluations/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_audit_03/geometry_audit.json"
GEOMETRY_CHECKPOINT = GEOMETRY_AUDIT.parent / "checkpoint_manifest.json"
VISUAL_AUDIT = ROOT / "stage31_evaluations/stage31d_replicated_nested_cpd2_geometry_20260826/visual_audit_01/visual_audit.json"
RUNNER = ROOT / "stage31_staging/run_stage31e_replicated_nested_cpd2_gpu_v1.py"
OUTPUT = ROOT / "stage31_evaluations/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_release_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable release: {OUTPUT}")
    required = [CONFIG, COMPLETION, GEOMETRY_AUDIT, GEOMETRY_CHECKPOINT, VISUAL_AUDIT, RUNNER]
    if any(not path.is_file() for path in required):
        raise RuntimeError("required Stage31e release source is missing")
    config, completion = json.loads(CONFIG.read_text(encoding="utf-8")), json.loads(COMPLETION.read_text(encoding="utf-8"))
    geometry_audit, checkpoint, visual = json.loads(GEOMETRY_AUDIT.read_text(encoding="utf-8")), json.loads(GEOMETRY_CHECKPOINT.read_text(encoding="utf-8")), json.loads(VISUAL_AUDIT.read_text(encoding="utf-8"))
    rows = config["geometry"]["cases"]
    artifact_checks = {
        case_id: Path(artifact["geometry"]).is_file() and sha(Path(artifact["geometry"])) == artifact["geometry_sha256"] and Path(artifact["material_vtk"]).is_file() and sha(Path(artifact["material_vtk"])) == artifact["material_vtk_sha256"]
        for case_id, artifact in config["geometry"]["artifacts"].items()
    }
    lineage_checks = {
        name: Path(binding["path"]).is_file() and sha(Path(binding["path"])) == binding["sha256"]
        for name, binding in config["lineage"].items()
        if isinstance(binding, dict) and "path" in binding and "sha256" in binding
    }
    checks = {
        "config_fail_closed": config.get("status") == "geometry_built_independent_audit_required" and config["authority"]["gpu_execution"] is False,
        "completion_passed_bound": completion.get("passed") is True and completion.get("config_sha256") == sha(CONFIG),
        "geometry_audit_passed_bound": geometry_audit.get("passed") is True and geometry_audit["bindings"]["config_sha256"] == sha(CONFIG),
        "geometry_checkpoint_bound": checkpoint.get("passed") is True and checkpoint["audit_sha256"] == sha(GEOMETRY_AUDIT),
        "visual_audit_passed": visual.get("passed") is True and visual["authority"]["gpu_release_design"] is True and visual["authority"]["gpu_execution"] is False,
        "all_artifact_hashes": len(artifact_checks) == 21 and all(artifact_checks.values()),
        "all_lineage_hashes": bool(lineage_checks) and all(lineage_checks.values()),
        "exact_complete_design": len(rows) == 21 and sum(row["fibre_count"] == 0 for row in rows) == 3 and sum(row["fibre_count"] > 0 for row in rows) == 18,
        "flow_order_exact": [row["flow_order"] for row in rows] == list(range(1, 22)),
        "clean_controls_first": [row["fibre_count"] for row in rows[:3]] == [0, 0, 0],
        "six_replicates_per_nonzero_count": all(sum(row["fibre_count"] == count for row in rows) == 6 for count in (1, 2, 4)),
        "matched_pairing_fields": all(row["packing_id"] in ("n216_s1", "n216_s2", "n216_s3") and (row["fibre_count"] == 0 or row["placement_block"] in ("A", "B")) for row in rows),
        "runner_compiles_and_bound": RUNNER.is_file(),
        "authority_narrow": not any(config["authority"].get(name, False) for name in ("cpd4", "permeability_claim", "mobile_sand", "coupling")),
    }
    passed = all(checks.values())
    handoff = {
        "schema": "lbs.stage31e-replicated-nested-cpd2-gpu-release.v1",
        "status": "stage31e_replicated_nested_cpd2_gpu_execution_authorized" if passed else "stage31e_replicated_nested_cpd2_gpu_execution_not_authorized",
        "passed": passed,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "artifact_checks": artifact_checks,
        "lineage_checks": lineage_checks,
        "bindings": {"config_sha256": sha(CONFIG), "runner_sha256": sha(RUNNER), "geometry_completion_sha256": sha(COMPLETION), "geometry_audit_sha256": sha(GEOMETRY_AUDIT), "visual_audit_sha256": sha(VISUAL_AUDIT)},
        "authority": {"gpu_execution": passed, "independent_evaluation": True, "render": False, "cpd4": False, "permeability_claim": False, "mobile_sand": False, "coupling": False},
        "claim_boundary": "Authorizes only the frozen 21-case fixed-solid CPD2 GPU screen. CPD4, absolute permeability validation, mechanics reruns, mobile sand, migration, clogging, deformation, and coupling remain prohibited.",
    }
    OUTPUT.mkdir(parents=True)
    (OUTPUT / "handoff.json").write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "status": handoff["status"], "passed": passed, "checks": checks}, indent=2))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
