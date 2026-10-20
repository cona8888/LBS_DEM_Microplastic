#!/usr/bin/env python3
"""Independent execution release for the Stage30a selected CPD4 run."""

from __future__ import annotations

import hashlib
import json
import py_compile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage30a_selected_low_concentration_cpd4_20260826"
CONFIG = ROOT / "stage30_designs" / STUDY / "geometry_01/resolved_config.json"
COMPLETION = CONFIG.parent / "completion.json"
DESIGN_AUDIT = ROOT / "stage30_evaluations" / STUDY / "design_audit_02/design_audit.json"
RUNNER = ROOT / "stage30_staging/run_stage30a_selected_low_concentration_cpd4_gpu_v1.py"
OUTPUT_RUN = ROOT / "stage30_runs" / STUDY / "gpu_confirmation_01"
OUTPUT = ROOT / "stage30_evaluations" / STUDY / "gpu_release_audit_01"


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
    artifacts = {case: sha(Path(v["geometry"])) == v["geometry_sha256"] for case, v in config["geometry"]["artifacts"].items()}
    lineage = {key: Path(v["path"]).is_file() and sha(Path(v["path"])) == v["sha256"] for key, v in config["lineage"].items() if isinstance(v, dict) and "path" in v and "sha256" in v}
    required = ("--handoff", "stage30a_cpd4_gpu_execution_authorized", "selected_ratio_shifts", "clean_reproduced",
                "zero_contact_more_obstructive", "four_fibre_contrast_shift_within_bound", "failure.json")
    checks = {
        "config_fail_closed": config["status"] == "cpd4_geometry_built_independent_gpu_release_required" and config["authority"]["gpu_cpd4_execution"] is False,
        "geometry_completion_bound": completion["passed"] and completion["config_sha256"] == sha(CONFIG),
        "design_audit_passed_and_bound": design["passed"] and design["source_bindings"]["config"]["sha256"] == sha(CONFIG),
        "all_geometry_artifacts_bound": all(artifacts.values()), "all_lineage_bound": all(lineage.values()),
        "runner_compiles": True, "runner_fail_closed_and_complete": all(token in text for token in required),
        "solver_is_qualified_cpd4": config["geometry"]["resolution"] == [186, 186, 186]
        and config["solver"]["maximum_steps"] == 160000 and config["solver"]["acceleration_lu"] == 2.5e-09,
        "output_absent": not OUTPUT_RUN.exists(),
        "no_widened_authority": all(config["authority"][k] is False for k in ("permeability_validation_claim", "mechanics_rerun", "mobile_sand", "migration", "clogging", "two_way_coupling")),
    }
    if not all(checks.values()):
        raise RuntimeError("GPU release audit failed: " + ", ".join(k for k, v in checks.items() if not v))
    OUTPUT.mkdir(parents=True)
    audit = {"schema": "lbs.stage30a-selected-low-concentration-cpd4-gpu-release-audit.v1",
    "status": "passed_stage30a_cpd4_gpu_release", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": True, "checks": checks, "artifact_checks": artifacts, "lineage_checks": lineage,
    "bindings": {"config_sha256": sha(CONFIG), "completion_sha256": sha(COMPLETION),
    "design_audit_sha256": sha(DESIGN_AUDIT), "runner_sha256": sha(RUNNER)},
    "next_handoff": {"authorized": "one four-case Stage30a CPD4 GPU execution", "not_authorized": "rerun or further physics"}}
    audit_path = OUTPUT / "audit.json"
    write(audit_path, audit)
    handoff = {"schema": "lbs.stage30a-selected-low-concentration-cpd4-gpu-handoff.v1",
    "status": "stage30a_cpd4_gpu_execution_authorized", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": True, "authority": {"gpu_cpd4_execution": True, "permeability_validation_claim": False,
    "mechanics_rerun": False, "mobile_sand": False, "migration": False, "clogging": False, "two_way_coupling": False},
    "bindings": {"config_sha256": sha(CONFIG), "runner_sha256": sha(RUNNER), "audit_sha256": sha(audit_path)},
    "output": str(OUTPUT_RUN)}
    handoff_path = OUTPUT / "execution_handoff.json"
    write(handoff_path, handoff)
    print(json.dumps({"audit": str(audit_path), "handoff": str(handoff_path), "checks": checks,
                      "runner_sha256": sha(RUNNER), "handoff_sha256": sha(handoff_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
