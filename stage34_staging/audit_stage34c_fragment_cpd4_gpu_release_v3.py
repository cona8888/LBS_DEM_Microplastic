#!/usr/bin/env python3
"""Audit config_02 and issue the executable Stage34C release_03 handoff."""

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
CONFIG = ROOT / "stage34_designs" / STUDY / "gpu_config_02/resolved_config.json"
CONFIG_COMPLETION = CONFIG.parent / "completion.json"
RUNNER = ROOT / "stage34_staging/run_stage34c_fragment_cpd4_gpu_v1.py"
SUPERVISOR = ROOT / "stage34_staging/supervise_stage34c_fragment_cpd4_gpu_v2.ps1"
OUTPUT = ROOT / "stage34_evaluations" / STUDY / "execution_release_03"
RUN_OUTPUT = ROOT / "stage34_runs" / STUDY / "gpu_confirmation_01"
SUPERVISOR_OUTPUT = RUN_OUTPUT.parent / "gpu_confirmation_01_supervisor"
ORDER = (
    "s34c_n216_s2_A_p4_frag2_cpd4", "s34c_n216_s1_A_p4_frag2_cpd4",
    "s34c_n216_s2_B_p4_frag2_cpd4", "s34c_n216_s2_A_p4_frag3_cpd4",
    "s34c_n216_s1_B_p4_frag2_cpd4", "s34c_n216_s1_B_p4_frag3_cpd4",
    "s34c_n216_s2_B_p4_frag3_cpd4", "s34c_n216_s1_A_p4_frag3_cpd4",
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
            raise RuntimeError(f"required release evidence missing: {path}")
    config, completion = load(CONFIG), load(CONFIG_COMPLETION)
    runner_source = RUNNER.read_text(encoding="utf-8")
    supervisor_source = SUPERVISOR.read_text(encoding="utf-8")
    tree = ast.parse(runner_source)
    py_compile.compile(str(RUNNER), doraise=True)
    py_compile.compile(config["lineage"]["builder"]["path"], doraise=True)

    lineage_checks = {key: binding_ok(item) for key, item in config["lineage"].items()
                      if isinstance(item, dict) and "path" in item and "sha256" in item}
    geometry_checks = {}
    for case_id, item in config["geometry"]["artifacts"].items():
        valid = binding_ok(item)
        if valid:
            with np.load(Path(item["path"]), allow_pickle=False) as archive:
                phase = np.asarray(archive["phase"], dtype=np.uint8)
                material = np.asarray(archive["material"], dtype=np.uint8)
            valid = (
                phase.shape == material.shape == (186, 186, 186)
                and set(np.unique(phase).tolist()).issubset({0, 2})
                and set(np.unique(material).tolist()).issubset({0, 1, 2})
                and np.array_equal(phase == 0, material == 0)
                and int(np.count_nonzero(material == 1)) == int(item["sand_voxel_count"])
                and int(np.count_nonzero(material == 2)) == int(item["fibre_only_voxel_count"])
                and int(np.count_nonzero(phase == 2)) == int(item["sand_voxel_count"]) + int(item["fibre_only_voxel_count"])
            )
        geometry_checks[case_id] = bool(valid)

    case_meta = {row["case_id"]: row for row in config["geometry"]["cases"]}
    warm_checks = {}
    for case_id, item in config["warm_starts"].items():
        meta = case_meta[case_id]
        intact = config["intact_contexts"][f"{meta['packing_id']}_{meta['placement_block']}"]
        warm_checks[case_id] = binding_ok(item) and item["sha256"] == intact["artifacts"]["final_fields.npz"]["sha256"] \
            and item["source_intact_case_id"] == intact["source_case_id"]
    intact_checks = {key: binding_ok(item["geometry"]) and all(binding_ok(value) for value in item["artifacts"].values())
                     for key, item in config["intact_contexts"].items()}
    clean_checks = {key: all(binding_ok(item[name]) for name in ("record", "geometry", "completion", "evaluation"))
                    and float(item["conductance_proxy_lu"]) > 0 for key, item in config["matched_clean_controls"].items()}
    stage31 = load(Path(config["lineage"]["stage31f_config"]["path"]))
    order = tuple(row["case_id"] for row in sorted(config["geometry"]["cases"], key=lambda row: row["run_order"]))
    predecessor = config["supersedes"]
    predecessor_checks = {
        "all_predecessor_bindings_valid": all(binding_ok(predecessor[name]) for name in ("configuration", "completion", "release_audit", "handoff")),
        "predecessor_supervisor_defect_reproduced": "execution_release_01" in Path(
            load(Path(predecessor["configuration"]["path"]))["lineage"]["supervisor"]["path"]
        ).read_text(encoding="utf-8"),
        "new_supervisor_targets_release_03": "execution_release_03" in supervisor_source
            and "gpu_config_02" in supervisor_source,
        "physics_and_order_declared_unchanged": config["checks"]["physics_geometry_solver_and_order_unchanged_from_config_01"] is True,
    }
    prohibited = ("absolute_permeability_validation_claim", "chemical_degradation_claim", "cpd6_flow_execution",
                  "mechanics_rerun", "mobile_sand", "migration", "clogging", "deformation",
                  "transient_coupling", "two_way_coupling")
    config_checks = {
        "schema_status_exact": config.get("schema") == "lbs.stage34c-fragment-cpd4-gpu.v1"
            and config.get("status") == "fragment_cpd4_configuration_frozen_independent_gpu_release_required",
        "completion_passed_bound": completion.get("passed") is True
            and completion.get("status") == "passed_fragment_cpd4_configuration_supervisor_correction"
            and completion.get("config_sha256") == sha(CONFIG),
        "self_checks_true": all(config["checks"].values()),
        "eight_new_cases_frozen_order": len(case_meta) == 8 and order == ORDER and tuple(completion["run_order"]) == ORDER,
        "four_intact_four_context_controls_two_unique_clean": len(config["intact_contexts"]) == 4
            and len(config["matched_clean_controls"]) == 4
            and len({item["record"]["sha256"] for item in config["matched_clean_controls"].values()}) == 2,
        "solver_fluid_execution_acceptance_exact_stage31f": config["solver"] == stage31["solver"]
            and config["fluid"] == stage31["fluid"] and config["execution"] == stage31["execution"]
            and config["acceptance"] == stage31["acceptance"],
        "fail_closed_before_release": config["authority"]["gpu_cpd4_execution"] is False
            and config["authority"]["independent_gpu_release"] is False,
        "authority_narrow": not any(config["authority"].get(key, False) for key in prohibited),
    }
    runner_checks = {
        "order_exact": assigned_tuple(tree, "ORDER") == ORDER,
        "refuses_overwrite": "refusing to overwrite immutable output" in runner_source,
        "requires_hash_handoff": "handoff/config/runner hash mismatch" in runner_source,
        "checks_lineage_geometry_warm_intact_clean": all(token in runner_source for token in ("lineage/", "geometry/", "warm_start/", "intact/", "clean/")),
        "cpd4_only_no_case_chaining": '"cpd": 4' in runner_source and "resampled_local_field_warm_start" in runner_source
            and "final_fields.npz" not in runner_source.split("for ordinal", 1)[1].split("finally:", 1)[0],
        "driver_close_failure_preservation": "driver.close()" in runner_source and "failed_preserved" in runner_source,
        "no_monotonicity_gate": "monotonicity_not_gated" in runner_source,
    }
    supervisor_checks = {
        "exact_config_and_release_targets": "gpu_config_02" in supervisor_source and "execution_release_03" in supervisor_source,
        "refuses_existing_targets": "immutable Stage34C run or supervisor target already exists" in supervisor_source,
        "requires_exact_release_and_hashes": "stage34c_fragment_cpd4_gpu_execution_authorized" in supervisor_source
            and all(token in supervisor_source for token in ("config_sha256", "runner_sha256", "supervisor_sha256")),
        "refuses_competing_python_yade": "Get-Process -Name python,python3,yade" in supervisor_source,
        "one_hidden_launch_and_manifest": supervisor_source.count("Start-Process") == 1
            and "-WindowStyle Hidden" in supervisor_source and "launch_manifest.json" in supervisor_source,
    }
    checks = {
        "predecessor_preserved_and_defect_corrected": all(predecessor_checks.values()),
        "all_lineage_hashes_verified": all(lineage_checks.values()),
        "all_eight_geometries_verified": len(geometry_checks) == 8 and all(geometry_checks.values()),
        "all_eight_context_warm_starts_verified": len(warm_checks) == 8 and all(warm_checks.values()),
        "all_four_intact_contexts_verified": len(intact_checks) == 4 and all(intact_checks.values()),
        "all_four_clean_context_mappings_verified": len(clean_checks) == 4 and all(clean_checks.values()),
        "configuration_exact": all(config_checks.values()), "runner_exact": all(runner_checks.values()),
        "supervisor_exact": all(supervisor_checks.values()),
        "run_and_supervisor_targets_absent": not RUN_OUTPUT.exists() and not SUPERVISOR_OUTPUT.exists(),
    }
    passed = all(checks.values())
    OUTPUT.mkdir(parents=True)
    audit = {
        "schema": "lbs.stage34c-fragment-cpd4-gpu-release-audit.v3",
        "status": "stage34c_fragment_cpd4_gpu_execution_authorized" if passed else "failed_closed",
        "passed": passed, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks, "predecessor_checks": predecessor_checks, "config_checks": config_checks,
        "runner_checks": runner_checks, "supervisor_checks": supervisor_checks,
        "lineage_checks": lineage_checks, "geometry_checks": geometry_checks,
        "warm_start_checks": warm_checks, "intact_checks": intact_checks, "clean_checks": clean_checks,
        "bindings": {"config_sha256": sha(CONFIG), "config_completion_sha256": sha(CONFIG_COMPLETION),
                     "runner_sha256": sha(RUNNER), "supervisor_sha256": sha(SUPERVISOR),
                     "release_auditor_sha256": sha(Path(__file__).resolve())},
        "authority": {"gpu_cpd4_execution": passed, "one_eight_case_campaign_only": passed,
                      "independent_evaluation": passed, "render": False, "cpd6_flow_execution": False,
                      "absolute_permeability_validation_claim": False, "chemical_degradation_claim": False,
                      "mechanics_rerun": False, "mobile_sand": False, "migration": False,
                      "clogging": False, "deformation": False, "transient_coupling": False,
                      "two_way_coupling": False},
        "claim_boundary": "Authorizes one immutable eight-case Stage34C CPD4 GPU run only.",
    }
    audit_path = OUTPUT / "release_audit.json"
    write(audit_path, audit)
    handoff = {"schema": audit["schema"] + ".handoff", "status": audit["status"], "passed": passed,
               "bindings": dict(audit["bindings"], release_audit_sha256=sha(audit_path)),
               "authority": audit["authority"], "claim_boundary": audit["claim_boundary"]}
    handoff_path = OUTPUT / "handoff.json"
    write(handoff_path, handoff)
    print(json.dumps({"passed": passed, "audit": str(audit_path), "audit_sha256": sha(audit_path),
                      "handoff": str(handoff_path), "handoff_sha256": sha(handoff_path), "checks": checks}, indent=2))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
