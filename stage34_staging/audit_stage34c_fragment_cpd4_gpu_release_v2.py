#!/usr/bin/env python3
"""Supersede the failed Stage34C release audit with the correct phase/material schema."""

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
PRIOR_FAILED_AUDIT = ROOT / "stage34_evaluations" / STUDY / "execution_release_01/release_audit.json"
PRIOR_FAILED_HANDOFF = PRIOR_FAILED_AUDIT.parent / "handoff.json"
OUTPUT = ROOT / "stage34_evaluations" / STUDY / "execution_release_02"
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
        raise FileExistsError(f"refusing to overwrite immutable superseding release: {OUTPUT}")
    for path in (CONFIG, CONFIG_COMPLETION, RUNNER, SUPERVISOR, PRIOR_FAILED_AUDIT, PRIOR_FAILED_HANDOFF):
        if not path.is_file():
            raise RuntimeError(f"required release evidence missing: {path}")
    config, completion, prior, prior_handoff = map(load, (CONFIG, CONFIG_COMPLETION, PRIOR_FAILED_AUDIT, PRIOR_FAILED_HANDOFF))
    runner_source = RUNNER.read_text(encoding="utf-8")
    supervisor_source = SUPERVISOR.read_text(encoding="utf-8")
    runner_tree = ast.parse(runner_source)
    py_compile.compile(str(RUNNER), doraise=True)
    py_compile.compile(config["lineage"]["builder"]["path"], doraise=True)

    lineage_checks = {key: binding_ok(item) for key, item in config["lineage"].items()
                      if isinstance(item, dict) and "path" in item and "sha256" in item}
    geometry_checks = {}
    geometry_observations = {}
    for case_id, item in config["geometry"]["artifacts"].items():
        valid = binding_ok(item)
        if valid:
            with np.load(Path(item["path"]), allow_pickle=False) as archive:
                phase = np.asarray(archive["phase"], dtype=np.uint8)
                material = np.asarray(archive["material"], dtype=np.uint8)
                spacing = float(np.asarray(archive["spacing_m"]).reshape(-1)[0])
                fragments = int(np.asarray(archive["fragments_per_parent"]).reshape(-1)[0])
            sand_count = int(np.count_nonzero(material == 1))
            fibre_count = int(np.count_nonzero(material == 2))
            solid_count = int(np.count_nonzero(phase == 2))
            valid = (
                phase.shape == material.shape == (186, 186, 186)
                and set(np.unique(phase).tolist()).issubset({0, 2})
                and set(np.unique(material).tolist()).issubset({0, 1, 2})
                and np.array_equal(phase == 0, material == 0)
                and solid_count == sand_count + fibre_count
                and sand_count == int(item["sand_voxel_count"])
                and fibre_count == int(item["fibre_only_voxel_count"])
                and spacing == float(item["spacing_m"])
                and fragments == int(next(row["fragments_per_parent"] for row in config["geometry"]["cases"] if row["case_id"] == case_id))
            )
            geometry_observations[case_id] = {
                "shape": list(phase.shape), "phase_values": np.unique(phase).tolist(),
                "material_values": np.unique(material).tolist(), "sand_voxel_count": sand_count,
                "fibre_only_voxel_count": fibre_count, "total_solid_voxel_count": solid_count,
            }
        geometry_checks[case_id] = bool(valid)

    case_meta = {row["case_id"]: row for row in config["geometry"]["cases"]}
    warm_start_checks = {}
    for case_id, item in config["warm_starts"].items():
        meta = case_meta[case_id]
        intact = config["intact_contexts"][f"{meta['packing_id']}_{meta['placement_block']}"]
        warm_start_checks[case_id] = (
            binding_ok(item) and item["sha256"] == intact["artifacts"]["final_fields.npz"]["sha256"]
            and item["source_intact_case_id"] == intact["source_case_id"]
            and float(item["velocity_scale"]) == float(config["solver"]["warm_start_velocity_scale"])
            and float(item["density_deviation_scale"]) == float(config["solver"]["warm_start_density_deviation_scale"])
        )
    intact_checks = {key: binding_ok(item["geometry"]) and all(binding_ok(value) for value in item["artifacts"].values())
                     for key, item in config["intact_contexts"].items()}
    clean_checks = {key: all(binding_ok(item[name]) for name in ("record", "geometry", "completion", "evaluation"))
                    and float(item["conductance_proxy_lu"]) > 0 for key, item in config["matched_clean_controls"].items()}

    stage31 = load(Path(config["lineage"]["stage31f_config"]["path"]))
    configured_order = tuple(row["case_id"] for row in sorted(config["geometry"]["cases"], key=lambda row: row["run_order"]))
    prohibited = ("absolute_permeability_validation_claim", "chemical_degradation_claim", "cpd6_flow_execution",
                  "mechanics_rerun", "mobile_sand", "migration", "clogging", "deformation",
                  "transient_coupling", "two_way_coupling")
    prior_failure_checks = {
        "prior_audit_failed_closed": prior.get("passed") is False and prior.get("status") == "failed_closed"
            and prior_handoff.get("passed") is False and prior_handoff.get("status") == "failed_closed",
        "only_aggregate_geometry_gate_failed": prior["checks"]["all_eight_geometry_artifacts_verified"] is False
            and all(value is True for key, value in prior["checks"].items() if key != "all_eight_geometry_artifacts_verified"),
        "all_old_per_case_geometry_checks_failed": len(prior["geometry_checks"]) == 8
            and not any(prior["geometry_checks"].values()),
        "failure_explained_by_phase_material_schema": all(
            obs["phase_values"] == [0, 2] and obs["material_values"] == [0, 1, 2]
            and obs["total_solid_voxel_count"] == obs["sand_voxel_count"] + obs["fibre_only_voxel_count"]
            for obs in geometry_observations.values()
        ),
    }
    config_checks = {
        "schema_status_exact": config.get("schema") == "lbs.stage34c-fragment-cpd4-gpu.v1"
            and config.get("status") == "fragment_cpd4_configuration_frozen_independent_gpu_release_required",
        "completion_passed_and_bound": completion.get("passed") is True
            and completion.get("config_sha256") == sha(CONFIG),
        "all_config_checks_true": all(config["checks"].values()),
        "exact_eight_new_cases_and_order": len(case_meta) == 8 and configured_order == ORDER
            and tuple(completion["run_order"]) == ORDER,
        "four_intact_and_four_context_controls": len(config["intact_contexts"]) == 4
            and len(config["matched_clean_controls"]) == 4,
        "two_unique_clean_records": len({item["record"]["sha256"] for item in config["matched_clean_controls"].values()}) == 2,
        "solver_fluid_execution_acceptance_exact_stage31f": config["solver"] == stage31["solver"]
            and config["fluid"] == stage31["fluid"] and config["execution"] == stage31["execution"]
            and config["acceptance"] == stage31["acceptance"],
        "config_fail_closed_before_release": config["authority"]["gpu_cpd4_execution"] is False
            and config["authority"]["independent_gpu_release"] is False,
        "authority_narrow": not any(config["authority"].get(key, False) for key in prohibited),
    }
    runner_checks = {
        "order_exact": assigned_tuple(runner_tree, "ORDER") == ORDER,
        "refuses_overwrite": "refusing to overwrite immutable output" in runner_source,
        "requires_hash_bound_handoff": "handoff/config/runner hash mismatch" in runner_source,
        "validates_all_bindings": all(token in runner_source for token in ("lineage/", "geometry/", "warm_start/", "intact/", "clean/")),
        "only_cpd4_cases": '"cpd": 4' in runner_source and all(case_id.endswith("_cpd4") for case_id in ORDER),
        "common_intact_warm_starts_not_chained": "resampled_local_field_warm_start" in runner_source
            and "source_intact_case_id" in runner_source
            and "final_fields.npz" not in runner_source.split("for ordinal", 1)[1].split("finally:", 1)[0],
        "closes_driver_and_preserves_failure": "driver.close()" in runner_source
            and "failure.json" in runner_source and "failed_preserved" in runner_source,
        "no_monotonicity_or_sign_gate": "monotonicity_or_sign_not_an_acceptance_gate" in runner_source
            and "monotonicity_not_gated" in runner_source,
    }
    supervisor_checks = {
        "refuses_existing_targets": "immutable Stage34C run or supervisor target already exists" in supervisor_source,
        "requires_exact_release": "stage34c_fragment_cpd4_gpu_execution_authorized" in supervisor_source,
        "checks_config_runner_supervisor_hashes": all(token in supervisor_source for token in ("config_sha256", "runner_sha256", "supervisor_sha256")),
        "refuses_competing_process": "Get-Process -Name python,python3,yade" in supervisor_source,
        "hidden_single_launch": "-WindowStyle Hidden" in supervisor_source and supervisor_source.count("Start-Process") == 1,
        "writes_bound_manifest": "launch_manifest.json" in supervisor_source,
    }
    checks = {
        "prior_failed_audit_preserved_and_explained": all(prior_failure_checks.values()),
        "all_lineage_hashes_verified": all(lineage_checks.values()),
        "all_eight_geometry_phase_material_schemas_verified": len(geometry_checks) == 8 and all(geometry_checks.values()),
        "all_eight_context_warm_starts_verified": len(warm_start_checks) == 8 and all(warm_start_checks.values()),
        "all_four_intact_contexts_verified": len(intact_checks) == 4 and all(intact_checks.values()),
        "all_four_context_clean_mappings_verified": len(clean_checks) == 4 and all(clean_checks.values()),
        "configuration_exact": all(config_checks.values()),
        "runner_exact": all(runner_checks.values()),
        "supervisor_exact": all(supervisor_checks.values()),
        "run_and_supervisor_targets_absent": not RUN_OUTPUT.exists() and not SUPERVISOR_OUTPUT.exists(),
    }
    passed = all(checks.values())
    OUTPUT.mkdir(parents=True)
    audit = {
        "schema": "lbs.stage34c-fragment-cpd4-gpu-release-audit.v2",
        "status": "stage34c_fragment_cpd4_gpu_execution_authorized" if passed else "failed_closed",
        "passed": passed, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "supersedes": {"reason": "v1 incorrectly treated phase=2 as fibre-only; material distinguishes sand=1 and fibre=2",
                       "prior_failed_audit": {"path": str(PRIOR_FAILED_AUDIT), "sha256": sha(PRIOR_FAILED_AUDIT)},
                       "prior_failed_handoff": {"path": str(PRIOR_FAILED_HANDOFF), "sha256": sha(PRIOR_FAILED_HANDOFF)}},
        "checks": checks, "prior_failure_checks": prior_failure_checks, "config_checks": config_checks,
        "runner_checks": runner_checks, "supervisor_checks": supervisor_checks,
        "lineage_checks": lineage_checks, "geometry_checks": geometry_checks,
        "geometry_observations": geometry_observations, "warm_start_checks": warm_start_checks,
        "intact_checks": intact_checks, "clean_checks": clean_checks,
        "bindings": {"config_sha256": sha(CONFIG), "config_completion_sha256": sha(CONFIG_COMPLETION),
                     "runner_sha256": sha(RUNNER), "supervisor_sha256": sha(SUPERVISOR),
                     "release_auditor_sha256": sha(Path(__file__).resolve())},
        "authority": {"gpu_cpd4_execution": passed, "one_eight_case_campaign_only": passed,
                      "independent_evaluation": passed, "render": False, "cpd6_flow_execution": False,
                      "absolute_permeability_validation_claim": False, "chemical_degradation_claim": False,
                      "mechanics_rerun": False, "mobile_sand": False, "migration": False,
                      "clogging": False, "deformation": False, "transient_coupling": False,
                      "two_way_coupling": False},
        "claim_boundary": "Authorizes one immutable eight-case Stage34C CPD4 GPU run only; no execution occurred during this audit.",
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
