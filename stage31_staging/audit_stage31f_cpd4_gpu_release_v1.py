#!/usr/bin/env python3
"""Audit the frozen Stage31f runner and issue one hash-bound GPU release."""

from __future__ import annotations

import ast
import hashlib
import json
import py_compile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage31f_selected_replicated_cpd4_20260827"
CONFIG = ROOT / "stage31_designs" / STUDY / "geometry_01/resolved_config.json"
GEOMETRY_COMPLETION = CONFIG.parent / "completion.json"
DESIGN_AUDIT = ROOT / "stage31_evaluations" / STUDY / "design_audit_01/design_audit.json"
DESIGN_HANDOFF = DESIGN_AUDIT.parent / "runner_audit_handoff.json"
RUNNER = ROOT / "stage31_staging/run_stage31f_selected_replicated_cpd4_gpu_v1.py"
OUTPUT = ROOT / "stage31_evaluations" / STUDY / "execution_release_01"
RUN_OUTPUT = ROOT / "stage31_runs" / STUDY / "gpu_confirmation_01"
SUPERVISOR = RUN_OUTPUT.parent / "gpu_confirmation_01_supervisor"
ORDER = (
    "s31b_n216_s2_clean", "s31b_n216_s1_A_f001_open", "s31b_n216_s1_A_f002_open",
    "s31b_n216_s1_A_f004_open", "s31b_n216_s1_B_f004_open",
    "s31b_n216_s2_A_f004_open", "s31b_n216_s2_B_f004_open",
)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def assigned_tuple(tree: ast.AST, name: str) -> tuple[str, ...] | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            try:
                value = ast.literal_eval(node.value)
                return tuple(value)
            except Exception:
                return None
    return None


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable release: {OUTPUT}")
    for path in (CONFIG, GEOMETRY_COMPLETION, DESIGN_AUDIT, DESIGN_HANDOFF, RUNNER):
        if not path.is_file():
            raise RuntimeError(f"required evidence missing: {path}")
    config, completion, design, design_handoff = map(load, (CONFIG, GEOMETRY_COMPLETION, DESIGN_AUDIT, DESIGN_HANDOFF))
    source = RUNNER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    py_compile.compile(str(RUNNER), doraise=True)

    lineage_checks = {}
    for key, binding in config["lineage"].items():
        if isinstance(binding, dict) and "path" in binding and "sha256" in binding:
            path = Path(binding["path"])
            lineage_checks[key] = path.is_file() and sha(path) == binding["sha256"]
    artifact_checks = {
        case_id: Path(binding["geometry"]).is_file() and sha(Path(binding["geometry"])) == binding["geometry_sha256"]
        and Path(binding["material_vtk"]).is_file() and sha(Path(binding["material_vtk"])) == binding["material_vtk_sha256"]
        for case_id, binding in config["geometry"]["artifacts"].items()
    }
    prohibited = ("absolute_permeability_validation_claim", "mechanics_rerun", "mobile_sand", "migration",
                  "clogging", "deformation", "transient_coupling", "two_way_coupling")
    runner_checks = {
        "order_exact": assigned_tuple(tree, "ORDER") == ORDER,
        "refuses_overwrite": "if output.exists()" in source and "refusing to overwrite immutable output" in source,
        "requires_hash_bound_handoff": "handoff/config/runner hash mismatch" in source,
        "checks_lineage_and_geometry": "immutable lineage mismatch" in source and "geometry hash mismatch" in source,
        "preserves_failure": "failure.json" in source and "failed_preserved" in source,
        "closes_driver": "finally:" in source and "driver.close()" in source,
        "uses_cpd4": '"cpd": 4' in source,
        "does_not_gate_monotonicity": "strictly_decreasing_observed" in source and "monotonicity_was_not_an_acceptance_gate" in source,
        "checks_ratio_and_contrast_shifts": "selected_ratio_shifts_within_bound" in source and "both_block_contrast_shifts_within_bound" in source,
    }
    checks = {
        "config_completion_bound": completion.get("passed") is True and completion["config_sha256"] == sha(CONFIG),
        "design_audit_passed": design.get("passed") is True and design["status"] == "passed_design_audit",
        "design_handoff_bound": design_handoff.get("passed") is True
            and design_handoff["design_audit"]["sha256"] == sha(DESIGN_AUDIT)
            and design_handoff["status"] == "runner_audit_authorized",
        "config_fail_closed_before_release": config["authority"]["gpu_cpd4_execution"] is False,
        "all_lineage_hashes": all(lineage_checks.values()),
        "all_geometry_artifacts": len(artifact_checks) == 7 and all(artifact_checks.values()),
        "all_warm_starts_bound": all(Path(item["path"]).is_file() and sha(Path(item["path"])) == item["sha256"] for item in config["cpd2_reference"]["warm_starts"].values()),
        "runner_checks": all(runner_checks.values()),
        "run_targets_absent": not RUN_OUTPUT.exists() and not SUPERVISOR.exists(),
        "authority_narrow": not any(config["authority"].get(key, False) for key in prohibited),
    }
    passed = all(checks.values())
    OUTPUT.mkdir(parents=True)
    audit = {
        "schema": "lbs.stage31f-selected-replicated-cpd4-gpu-release-audit.v1",
        "status": "stage31f_cpd4_gpu_execution_authorized" if passed else "failed_closed",
        "passed": passed, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks, "runner_checks": runner_checks, "lineage_checks": lineage_checks,
        "artifact_checks": artifact_checks,
        "bindings": {"config_sha256": sha(CONFIG), "geometry_completion_sha256": sha(GEOMETRY_COMPLETION),
                     "design_audit_sha256": sha(DESIGN_AUDIT), "design_handoff_sha256": sha(DESIGN_HANDOFF),
                     "runner_sha256": sha(RUNNER), "release_auditor_sha256": sha(Path(__file__).resolve())},
        "authority": {"gpu_cpd4_execution": passed, "independent_evaluation": passed, "render": False,
                      "absolute_permeability_validation_claim": False, "mechanics_rerun": False,
                      "mobile_sand": False, "migration": False, "clogging": False,
                      "deformation": False, "transient_coupling": False, "two_way_coupling": False},
        "claim_boundary": "Authorizes one immutable seven-case Stage31f CPD4 GPU run only.",
    }
    audit_path = OUTPUT / "release_audit.json"
    write(audit_path, audit)
    handoff = {
        "schema": audit["schema"] + ".handoff", "status": audit["status"], "passed": passed,
        "bindings": dict(audit["bindings"], release_audit_sha256=sha(audit_path)),
        "authority": audit["authority"], "claim_boundary": audit["claim_boundary"],
    }
    handoff_path = OUTPUT / "handoff.json"
    write(handoff_path, handoff)
    print(json.dumps({"passed": passed, "audit": str(audit_path), "audit_sha256": sha(audit_path),
                      "handoff": str(handoff_path), "handoff_sha256": sha(handoff_path),
                      "checks": checks, "runner_checks": runner_checks}, indent=2))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
