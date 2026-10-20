#!/usr/bin/env python3
"""Independent execution release for the Stage28c selected CPD4 run."""

from __future__ import annotations

import hashlib
import json
import py_compile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage28c_selected_two_fibre_cpd4_20260825"
CONFIG = ROOT / "stage28_designs" / STUDY / "geometry_01/resolved_config.json"
COMPLETION = CONFIG.parent / "completion.json"
DESIGN_AUDIT = ROOT / "stage28_evaluations" / STUDY / "design_audit_01/design_audit.json"
RUNNER = ROOT / "stage28_staging/run_stage28c_selected_two_fibre_cpd4_gpu_v1.py"
OUTPUT_RUN = ROOT / "stage28_runs" / STUDY / "gpu_confirmation_01"
OUTPUT = ROOT / "stage28_evaluations" / STUDY / "gpu_release_audit_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable audit: {OUTPUT}")
    config, completion, design = map(load, (CONFIG, COMPLETION, DESIGN_AUDIT))
    py_compile.compile(str(RUNNER), doraise=True)
    text = RUNNER.read_text(encoding="utf-8")
    artifact_checks = {case: sha(Path(binding["geometry"])) == binding["geometry_sha256"]
                       for case, binding in config["geometry"]["artifacts"].items()}
    lineage_checks = {key: Path(binding["path"]).is_file() and sha(Path(binding["path"])) == binding["sha256"]
                      for key, binding in config["lineage"].items()
                      if isinstance(binding, dict) and "path" in binding and "sha256" in binding}
    required = ("--handoff", "stage28c_cpd4_gpu_execution_authorized", "gpu_cpd4_execution\") is not False",
                "clean\", \"separated_open_open\", \"crossing_interaction", "two_fibre_ratio_shifts",
                "clean_reproduced", "crossing_more_obstructive", "failure.json")
    checks = {
        "config_fail_closed": config["status"] == "cpd4_geometry_built_independent_gpu_release_required" and config["authority"]["gpu_cpd4_execution"] is False,
        "geometry_completion_bound": completion["passed"] and completion["config_sha256"] == sha(CONFIG),
        "design_audit_passed_and_bound": design["passed"] and design["source_bindings"]["config"]["sha256"] == sha(CONFIG),
        "topology_separated_noncontacting": design["metrics"]["topology"]["separated_open_open"] == {"periodic_face_adjacency_count": 0, "raw_overlap_voxels": 0},
        "topology_crossing_resolved": design["metrics"]["topology"]["crossing_interaction"]["periodic_face_adjacency_count"] > 0,
        "all_geometry_artifacts_bound": all(artifact_checks.values()), "all_lineage_bound": all(lineage_checks.values()),
        "runner_compiles": True, "runner_fail_closed_and_complete": all(token in text for token in required),
        "solver_is_qualified_cpd4": config["geometry"]["resolution"] == [186, 186, 186]
        and config["solver"]["maximum_steps"] == 160000 and config["solver"]["acceleration_lu"] == 2.5e-09,
        "output_absent": not OUTPUT_RUN.exists(),
        "no_widened_authority": all(config["authority"][key] is False for key in ("production_concentration_campaign", "mobile_sand", "two_way_coupling")),
    }
    if not all(checks.values()):
        raise RuntimeError("GPU release audit failed: " + ", ".join(key for key, value in checks.items() if not value))
    OUTPUT.mkdir(parents=True)
    audit = {
        "schema": "lbs.stage28c-selected-two-fibre-cpd4-gpu-release-audit.v1",
        "status": "passed_stage28c_cpd4_gpu_release", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True, "checks": checks, "artifact_checks": artifact_checks, "lineage_checks": lineage_checks,
        "bindings": {"config_sha256": sha(CONFIG), "completion_sha256": sha(COMPLETION),
                     "design_audit_sha256": sha(DESIGN_AUDIT), "runner_sha256": sha(RUNNER)},
        "next_handoff": {"authorized": "one three-case Stage28c CPD4 GPU execution",
                         "not_authorized": "rerun, production concentration, mechanics, deformation or coupling"},
    }
    audit_path = OUTPUT / "audit.json"
    write(audit_path, audit)
    handoff = {
        "schema": "lbs.stage28c-selected-two-fibre-cpd4-gpu-handoff.v1",
        "status": "stage28c_cpd4_gpu_execution_authorized", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True, "authority": {"gpu_cpd4_execution": True, "production_concentration_campaign": False,
                                      "mobile_sand": False, "two_way_coupling": False},
        "bindings": {"config_sha256": sha(CONFIG), "runner_sha256": sha(RUNNER), "audit_sha256": sha(audit_path)},
        "output": str(OUTPUT_RUN),
    }
    handoff_path = OUTPUT / "execution_handoff.json"
    write(handoff_path, handoff)
    print(json.dumps({"audit": str(audit_path), "audit_sha256": sha(audit_path),
                      "handoff": str(handoff_path), "handoff_sha256": sha(handoff_path), "checks": checks}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
