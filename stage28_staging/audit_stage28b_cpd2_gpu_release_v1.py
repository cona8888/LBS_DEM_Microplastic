#!/usr/bin/env python3
"""Independent execution release for the Stage28b four-case CPD2 GPU pilot."""

from __future__ import annotations

import hashlib
import json
import py_compile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
GEOMETRY = ROOT / "stage28_designs/stage28b_two_fibre_cpd2_hydraulic_20260824/geometry_01"
CONFIG = GEOMETRY / "resolved_config.json"
COMPLETION = GEOMETRY / "completion.json"
GEOMETRY_AUDIT = ROOT / "stage28_evaluations/stage28b_two_fibre_cpd2_hydraulic_20260824/geometry_audit_01/audit.json"
RUNNER = ROOT / "stage28_staging/run_stage28b_two_fibre_cpd2_gpu_v1.py"
OUTPUT_RUN = ROOT / "stage28_runs/stage28b_two_fibre_cpd2_hydraulic_20260825/gpu_pilot_01"
OUTPUT = ROOT / "stage28_evaluations/stage28b_two_fibre_cpd2_hydraulic_20260824/gpu_release_audit_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable audit: {OUTPUT}")
    config, completion, geometry_audit = map(load, (CONFIG, COMPLETION, GEOMETRY_AUDIT))
    py_compile.compile(str(RUNNER), doraise=True)
    text = RUNNER.read_text(encoding="utf-8")
    artifact_checks = {}
    for case_id, binding in config["geometry"]["artifacts"].items():
        artifact_checks[case_id] = sha(Path(binding["geometry"])) == binding["geometry_sha256"]
    lineage_checks = {}
    for key, binding in config["lineage"].items():
        if isinstance(binding, dict) and "path" in binding and "sha256" in binding:
            path = Path(binding["path"])
            lineage_checks[key] = path.is_file() and sha(path) == binding["sha256"]
    required = ("--handoff", "stage28b_cpd2_gpu_execution_authorized", "gpu_cpd2_pilot\") is not False",
                "clean\", \"separated_open_open\", \"separated_open_constricted\", \"crossing_interaction",
                "all_records_passed", "clean_ratio_exact", "failure.json")
    checks = {
        "config_fail_closed": config["status"] == "geometry_built_independent_gpu_release_required"
        and config["authority"]["gpu_cpd2_pilot"] is False,
        "geometry_completion_bound": completion["passed"] and completion["config_sha256"] == sha(CONFIG),
        "geometry_audit_passed_and_bound": geometry_audit["passed"] and geometry_audit["bindings"]["config_sha256"] == sha(CONFIG),
        "crossing_topology_resolved": geometry_audit["topology"]["crossing_interaction"]["periodic_face_adjacency_count"] > 0,
        "all_geometry_artifacts_bound": all(artifact_checks.values()),
        "all_lineage_bound": all(lineage_checks.values()),
        "runner_compiles": True,
        "runner_fail_closed_and_complete": all(token in text for token in required),
        "solver_is_cpd2": config["geometry"]["fibre_diameter_cells"] >= 1.9
        and config["solver"]["maximum_steps"] == 80000,
        "output_absent": not OUTPUT_RUN.exists(),
        "no_widened_authority": all(config["authority"][key] is False for key in
                                     ("cpd4", "production_concentration_campaign", "mobile_sand", "two_way_coupling")),
    }
    if not all(checks.values()):
        raise RuntimeError("GPU release audit failed: " + ", ".join(k for k, v in checks.items() if not v))
    OUTPUT.mkdir(parents=True)
    audit = {"schema": "lbs.stage28b-two-fibre-cpd2-gpu-release-audit.v1",
             "status": "passed_stage28b_cpd2_gpu_release", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
             "passed": True, "checks": checks, "artifact_checks": artifact_checks, "lineage_checks": lineage_checks,
             "bindings": {"config_sha256": sha(CONFIG), "completion_sha256": sha(COMPLETION),
                          "geometry_audit_sha256": sha(GEOMETRY_AUDIT), "runner_sha256": sha(RUNNER)},
             "next_handoff": {"authorized": "one four-case Stage28b CPD2 GPU execution",
                              "not_authorized": "CPD4, production concentration campaign, mobile sand or coupling"}}
    audit_path = OUTPUT / "audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    handoff = {"schema": "lbs.stage28b-two-fibre-cpd2-gpu-handoff.v1",
               "status": "stage28b_cpd2_gpu_execution_authorized", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
               "passed": True, "authority": {"gpu_cpd2_execution": True, "cpd4": False,
                                             "production_concentration_campaign": False, "mobile_sand": False, "two_way_coupling": False},
               "bindings": {"config_sha256": sha(CONFIG), "runner_sha256": sha(RUNNER), "audit_sha256": sha(audit_path)},
               "output": str(OUTPUT_RUN)}
    handoff_path = OUTPUT / "execution_handoff.json"
    handoff_path.write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"audit": str(audit_path), "audit_sha256": sha(audit_path),
                      "handoff": str(handoff_path), "handoff_sha256": sha(handoff_path), "checks": checks}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
