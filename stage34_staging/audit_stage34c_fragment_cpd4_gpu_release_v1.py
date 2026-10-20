#!/usr/bin/env python3
"""Independently audit and hash-release the Stage34C fragment CPD4 GPU campaign."""

from __future__ import annotations

import ast
import hashlib
import json
import py_compile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage34c_cpd4_first_fragmentation_geometry_20260902"
CONFIG = ROOT / "stage34_designs" / STUDY / "gpu_config_01/resolved_config.json"
CONFIG_COMPLETION = CONFIG.parent / "completion.json"
RUNNER = ROOT / "stage34_staging/run_stage34c_fragment_cpd4_gpu_v1.py"
SUPERVISOR = ROOT / "stage34_staging/supervise_stage34c_fragment_cpd4_gpu_v1.ps1"
OUTPUT = ROOT / "stage34_evaluations" / STUDY / "execution_release_01"
RUN_OUTPUT = ROOT / "stage34_runs" / STUDY / "gpu_confirmation_01"
SUPERVISOR_OUTPUT = RUN_OUTPUT.parent / "gpu_confirmation_01_supervisor"
ORDER = (
    "s34c_n216_s2_A_p4_frag2_cpd4",
    "s34c_n216_s1_A_p4_frag2_cpd4",
    "s34c_n216_s2_B_p4_frag2_cpd4",
    "s34c_n216_s2_A_p4_frag3_cpd4",
    "s34c_n216_s1_B_p4_frag2_cpd4",
    "s34c_n216_s1_B_p4_frag3_cpd4",
    "s34c_n216_s2_B_p4_frag3_cpd4",
    "s34c_n216_s1_A_p4_frag3_cpd4",
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


def binding_ok(item: dict) -> bool:
    path = Path(item["path"])
    return path.is_file() and sha(path) == item["sha256"]


def assigned_tuple(tree: ast.AST, name: str) -> tuple[str, ...] | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            try:
                return tuple(ast.literal_eval(node.value))
            except Exception:
                return None
    return None


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable release: {OUTPUT}")
    for path in (CONFIG, CONFIG_COMPLETION, RUNNER, SUPERVISOR):
        if not path.is_file():
            raise RuntimeError(f"required release input missing: {path}")
    config, completion = load(CONFIG), load(CONFIG_COMPLETION)
    runner_source = RUNNER.read_text(encoding="utf-8")
    supervisor_source = SUPERVISOR.read_text(encoding="utf-8")
    tree = ast.parse(runner_source)
    py_compile.compile(str(RUNNER), doraise=True)
    py_compile.compile(str(config["lineage"]["builder"]["path"]), doraise=True)

    lineage_checks = {
        key: binding_ok(item)
        for key, item in config["lineage"].items()
        if isinstance(item, dict) and "path" in item and "sha256" in item
    }
    geometry_checks = {}
    for case_id, item in config["geometry"]["artifacts"].items():
        path = Path(item["path"])
        valid = binding_ok(item)
        if valid:
            with np.load(path, allow_pickle=False) as archive:
                phase = np.asarray(archive["phase"], dtype=np.uint8)
            valid = (
                phase.shape == (186, 186, 186)
                and set(np.unique(phase).tolist()).issubset({0, 1, 2})
                and int(np.count_nonzero(phase == 2)) == int(item["fibre_only_voxel_count"])
                and int(np.count_nonzero(phase == 1)) == int(item["sand_voxel_count"])
            )
        geometry_checks[case_id] = bool(valid)

    warm_start_checks = {}
    case_meta = {row["case_id"]: row for row in config["geometry"]["cases"]}
    for case_id, item in config["warm_starts"].items():
        meta = case_meta[case_id]
        context = config["intact_contexts"][f"{meta['packing_id']}_{meta['placement_block']}"]
        warm_start_checks[case_id] = (
            binding_ok(item)
            and item["sha256"] == context["artifacts"]["final_fields.npz"]["sha256"]
            and item["source_intact_case_id"] == context["source_case_id"]
            and float(item["velocity_scale"]) == float(config["solver"]["warm_start_velocity_scale"])
            and float(item["density_deviation_scale"]) == float(config["solver"]["warm_start_density_deviation_scale"])
        )
    intact_checks = {
        context_id: binding_ok(item["geometry"])
        and all(binding_ok(artifact) for artifact in item["artifacts"].values())
        for context_id, item in config["intact_contexts"].items()
    }
    clean_checks = {
        context_id: all(binding_ok(item[name]) for name in ("record", "geometry", "completion", "evaluation"))
        and float(item["conductance_proxy_lu"]) > 0
        for context_id, item in config["matched_clean_controls"].items()
    }
    stage31_config = load(Path(config["lineage"]["stage31f_config"]["path"]))

    runner_checks = {
        "order_exact": assigned_tuple(tree, "ORDER") == ORDER,
        "refuses_existing_output": "refusing to overwrite immutable output" in runner_source,
        "requires_hash_bound_release": "handoff/config/runner hash mismatch" in runner_source,
        "validates_lineage_geometry_warm_starts": all(
            token in runner_source for token in ("lineage/", "geometry/", "warm_start/")
        ),
        "runs_only_cpd4": '"cpd": 4' in runner_source and "cpd6" not in assigned_tuple(tree, "ORDER")[0],
        "uses_context_matched_common_intact_warm_start": "source_intact_case_id" in runner_source
            and "resampled_local_field_warm_start" in runner_source,
        "does_not_chain_fragment_cases": "final_fields.npz" not in runner_source.split("for ordinal", 1)[1].split("finally:", 1)[0],
        "closes_gpu_driver": "finally:" in runner_source and "driver.close()" in runner_source,
        "preserves_structured_failure": "failure.json" in runner_source and "failed_preserved" in runner_source,
        "does_not_gate_monotonicity_or_sign": "monotonicity_or_sign_not_an_acceptance_gate" in runner_source
            and "monotonicity_not_gated" in runner_source,
        "writes_all_five_case_artifacts": "ARTIFACT_NAMES" in runner_source and "artifact_sha256" in runner_source,
    }
    supervisor_checks = {
        "refuses_existing_targets": "immutable Stage34C run or supervisor target already exists" in supervisor_source,
        "requires_release_status": "stage34c_fragment_cpd4_gpu_execution_authorized" in supervisor_source,
        "checks_runner_config_supervisor_hashes": all(
            token in supervisor_source for token in ("runner_sha256", "config_sha256", "supervisor_sha256")
        ),
        "refuses_competing_python_or_yade": "Get-Process -Name python,python3,yade" in supervisor_source,
        "hidden_noninteractive_launch": "-WindowStyle Hidden" in supervisor_source,
        "single_bound_command": "Start-Process" in supervisor_source and "--config" in supervisor_source
            and "--handoff" in supervisor_source and "--output" in supervisor_source,
        "writes_launch_manifest": "launch_manifest.json" in supervisor_source,
        "authority_narrow": "$false" in supervisor_source and "cpd6_flow" in supervisor_source
            and "mechanics_or_coupling" in supervisor_source,
    }
    prohibited = (
        "absolute_permeability_validation_claim", "chemical_degradation_claim", "cpd6_flow_execution",
        "mechanics_rerun", "mobile_sand", "migration", "clogging", "deformation",
        "transient_coupling", "two_way_coupling",
    )
    configured_order = tuple(row["case_id"] for row in sorted(config["geometry"]["cases"], key=lambda row: row["run_order"]))
    config_checks = {
        "schema_and_status_exact": config.get("schema") == "lbs.stage34c-fragment-cpd4-gpu.v1"
            and config.get("status") == "fragment_cpd4_configuration_frozen_independent_gpu_release_required",
        "config_completion_passed_and_bound": completion.get("passed") is True
            and completion.get("status") == "passed_fragment_cpd4_configuration_freeze"
            and completion.get("config_sha256") == sha(CONFIG),
        "all_config_self_checks": all(config["checks"].values()),
        "exact_eight_new_cases": len(config["geometry"]["cases"]) == 8
            and all(int(row["fragments_per_parent"]) in (2, 3) for row in config["geometry"]["cases"]),
        "frozen_order_exact": configured_order == ORDER and tuple(completion["run_order"]) == ORDER,
        "exact_four_intact_contexts": len(config["intact_contexts"]) == 4,
        "exact_four_matched_clean_mappings": len(config["matched_clean_controls"]) == 4,
        "two_unique_clean_records": len({item["record"]["sha256"] for item in config["matched_clean_controls"].values()}) == 2,
        "exact_eight_context_matched_warm_starts": len(config["warm_starts"]) == 8,
        "solver_exact_stage31f": config["solver"] == stage31_config["solver"],
        "fluid_and_execution_exact_stage31f": config["fluid"] == stage31_config["fluid"]
            and config["execution"] == stage31_config["execution"],
        "acceptance_exact_stage31f": config["acceptance"] == stage31_config["acceptance"],
        "config_fail_closed_before_release": config["authority"]["gpu_cpd4_execution"] is False
            and config["authority"]["independent_gpu_release"] is False,
        "authority_boundary_narrow": not any(config["authority"].get(key, False) for key in prohibited),
    }
    checks = {
        "all_lineage_hashes_verified": all(lineage_checks.values()),
        "all_eight_geometry_artifacts_verified": len(geometry_checks) == 8 and all(geometry_checks.values()),
        "all_eight_warm_starts_verified": len(warm_start_checks) == 8 and all(warm_start_checks.values()),
        "all_four_intact_contexts_verified": len(intact_checks) == 4 and all(intact_checks.values()),
        "all_four_clean_context_mappings_verified": len(clean_checks) == 4 and all(clean_checks.values()),
        "all_runner_checks": all(runner_checks.values()),
        "all_supervisor_checks": all(supervisor_checks.values()),
        "all_configuration_checks": all(config_checks.values()),
        "immutable_run_targets_absent": not RUN_OUTPUT.exists() and not SUPERVISOR_OUTPUT.exists(),
    }
    passed = all(checks.values())
    OUTPUT.mkdir(parents=True)
    audit = {
        "schema": "lbs.stage34c-fragment-cpd4-gpu-release-audit.v1",
        "status": "stage34c_fragment_cpd4_gpu_execution_authorized" if passed else "failed_closed",
        "passed": passed, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks, "config_checks": config_checks, "runner_checks": runner_checks,
        "supervisor_checks": supervisor_checks, "lineage_checks": lineage_checks,
        "geometry_checks": geometry_checks, "warm_start_checks": warm_start_checks,
        "intact_checks": intact_checks, "clean_checks": clean_checks,
        "bindings": {
            "config_sha256": sha(CONFIG), "config_completion_sha256": sha(CONFIG_COMPLETION),
            "runner_sha256": sha(RUNNER), "supervisor_sha256": sha(SUPERVISOR),
            "release_auditor_sha256": sha(Path(__file__).resolve()),
        },
        "authority": {
            "gpu_cpd4_execution": passed, "one_eight_case_campaign_only": passed,
            "independent_evaluation": passed, "render": False, "cpd6_flow_execution": False,
            "absolute_permeability_validation_claim": False, "chemical_degradation_claim": False,
            "mechanics_rerun": False, "mobile_sand": False, "migration": False,
            "clogging": False, "deformation": False, "transient_coupling": False,
            "two_way_coupling": False,
        },
        "claim_boundary": "Authorizes one immutable eight-case Stage34C CPD4 GPU run only; no execution occurred during this audit.",
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
                      "checks": checks}, indent=2))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
