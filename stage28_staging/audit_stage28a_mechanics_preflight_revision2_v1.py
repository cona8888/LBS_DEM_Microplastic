#!/usr/bin/env python3
"""Independent release audit for the Stage28a Revision-2 mechanics rerun."""

from __future__ import annotations

import hashlib
import json
import py_compile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
PREFLIGHT = ROOT / "stage28_designs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_preflight_02"
CONFIG = PREFLIGHT / "config.json"
COMPLETION = PREFLIGHT / "completion.json"
V1_CONFIG = ROOT / "stage28_designs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_preflight_01/config.json"
RUNNER = ROOT / "stage28_designs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_revision2_runner_01/run_stage28a_two_fibre_mechanics_v2.py"
FAILURE = ROOT / "stage28_evaluations/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_evaluation_01/evaluation.json"
UNIT = ROOT / "stage28_tests/stage28a_yade_groupmask_self_filter_20260824/unit_03/result.json"
MECHANICS_OUTPUT = ROOT / "stage28_runs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_02"
OUTPUT = ROOT / "stage28_evaluations/stage28a_two_fibre_mechanics_hydraulics_20260824/execution_audit_02"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def host(value: str) -> Path:
    return Path("C:\\" + value[7:].replace("/", "\\")) if value.startswith("/mnt/c/") else Path(value)


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUTPUT}")
    config = load(CONFIG)
    completion = load(COMPLETION)
    v1 = load(V1_CONFIG)
    failure = load(FAILURE)
    unit = load(UNIT)
    py_compile.compile(str(RUNNER), doraise=True)
    runner_text = RUNNER.read_text(encoding="utf-8")
    source_checks = {
        name: host(binding["path"]).is_file() and sha(host(binding["path"])) == binding["sha256"]
        for name, binding in config["sources"].items()
        if name != "expected_yade_version"
    }
    unchanged_keys = ("execution_cases", "accepted_isolated_controls", "mechanics", "acceptance", "cell_dimensions_m")
    checks = {
        "revision2_status_fail_closed": config["status"]
        == "stage28a_two_fibre_mechanics_revision2_preflight_independent_release_required",
        "all_preflight_checks_passed": all(config["checks"].values()),
        "completion_passed_and_bound": completion["passed"] and completion["config"]["sha256"] == sha(CONFIG),
        "all_sources_bound": all(source_checks.values()),
        "runner_compiles": True,
        "structural_filter_exact": "avoidSelfInteractionMask=6" in runner_text
        and "fibre_group_mask = 1 | (2 << fibre_index)" in runner_text,
        "explicit_zero_intrafibre_gate": '"no_intrafibre_grid_contact"' in runner_text,
        "unit_passed_and_bound": unit["passed"] and all(unit["checks"].values())
        and config["sources"]["structural_groupmask_unit"]["sha256"] == sha(UNIT),
        "failure_diagnosis_passed_and_bound": failure["passed"]
        and config["sources"]["revision1_failure_evaluation"]["sha256"] == sha(FAILURE),
        "science_and_numerics_unchanged_from_revision1": all(
            canonical(config[key]) == canonical(v1[key]) for key in unchanged_keys
        ),
        "exact_six_cases": len(config["execution_cases"]) == 6,
        "only_mechanics_rerun_authorizable": config["authority"]["mechanics_execution_authorized"] is False
        and config["authority"]["gpu_execution_authorized"] is False
        and config["authority"]["mobile_sand_authorized"] is False
        and config["authority"]["two_way_coupling_authorized"] is False,
        "revision1_output_preserved": (ROOT / "stage28_runs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_01/result.json").is_file(),
        "revision2_output_absent": not MECHANICS_OUTPUT.exists(),
    }
    if not all(checks.values()):
        raise RuntimeError("Revision-2 audit failed: " + ", ".join(k for k, v in checks.items() if not v))
    OUTPUT.mkdir(parents=True)
    audit = {
        "schema": "lbs.stage28a-two-fibre-mechanics-revision2-execution-audit.v1",
        "status": "passed_stage28a_revision2_mechanics_execution_release",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "checks": checks,
        "source_checks": source_checks,
        "bindings": {"config_sha256": sha(CONFIG), "completion_sha256": sha(COMPLETION),
                     "runner_sha256": sha(RUNNER), "failure_evaluation_sha256": sha(FAILURE),
                     "unit_sha256": sha(UNIT)},
        "next_handoff": {"authorized": "one immutable Stage28a Revision-2 CPU YADE mechanics execution",
                         "not_authorized": "GPU-LBM, mechanics model changes, mobile sand, concentration campaign, or coupling"},
    }
    audit_path = OUTPUT / "audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    handoff = {
        "schema": "lbs.stage28a-two-fibre-mechanics-revision2-execution-handoff.v1",
        "status": "stage28a_revision2_mechanics_execution_authorized",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "authority": {"mechanics_execution": True, "gpu_execution": False, "mobile_sand": False,
                      "production_concentration_campaign": False, "two_way_coupling": False},
        "bindings": {"config_sha256": sha(CONFIG), "runner_sha256": sha(RUNNER),
                     "audit_sha256": sha(audit_path)},
        "output": str(MECHANICS_OUTPUT),
    }
    handoff_path = OUTPUT / "execution_handoff.json"
    handoff_path.write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"audit": str(audit_path), "audit_sha256": sha(audit_path),
                      "handoff": str(handoff_path), "handoff_sha256": sha(handoff_path),
                      "checks": checks}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
