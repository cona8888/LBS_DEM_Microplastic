#!/usr/bin/env python3
"""Independently audit and release the six-case Stage34C recovery."""

from __future__ import annotations

import ast
import hashlib
import json
import py_compile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage34c_cpd4_first_fragmentation_geometry_20260902"
CONFIG = ROOT / "stage34_designs" / STUDY / "gpu_config_02/resolved_config.json"
ORIGINAL_HANDOFF = ROOT / "stage34_evaluations" / STUDY / "execution_release_03/handoff.json"
ORIGINAL_RUNNER = ROOT / "stage34_staging/run_stage34c_fragment_cpd4_gpu_v1.py"
ORIGINAL_SUPERVISOR = ROOT / "stage34_staging/supervise_stage34c_fragment_cpd4_gpu_v2.ps1"
ORIGINAL_OUTPUT = ROOT / "stage34_runs" / STUDY / "gpu_confirmation_01"
INTERRUPTION_AUDITOR = ROOT / "stage34_staging/audit_stage34c_fragment_cpd4_interruption_v1.py"
INTERRUPTION_AUDIT = ROOT / "stage34_evaluations" / STUDY / "interruption_audit_01/interruption_audit.json"
INTERRUPTION_COMPLETION = INTERRUPTION_AUDIT.parent / "completion.json"
CONTRACT = ROOT / "stage34_staging/STAGE34C_FRAGMENT_CPD4_RECOVERY_CONTRACT.md"
RUNNER = ROOT / "stage34_staging/run_stage34c_fragment_cpd4_recovery_gpu_v1.py"
SUPERVISOR = ROOT / "stage34_staging/supervise_stage34c_fragment_cpd4_recovery_gpu_v1.ps1"
OUTPUT = ROOT / "stage34_evaluations" / STUDY / "recovery_release_01"
RUN_OUTPUT = ROOT / "stage34_runs" / STUDY / "gpu_confirmation_02_recovery"
SUPERVISOR_OUTPUT = RUN_OUTPUT.parent / "gpu_confirmation_02_recovery_supervisor"
FULL_ORDER = (
    "s34c_n216_s2_A_p4_frag2_cpd4", "s34c_n216_s1_A_p4_frag2_cpd4",
    "s34c_n216_s2_B_p4_frag2_cpd4", "s34c_n216_s2_A_p4_frag3_cpd4",
    "s34c_n216_s1_B_p4_frag2_cpd4", "s34c_n216_s1_B_p4_frag3_cpd4",
    "s34c_n216_s2_B_p4_frag3_cpd4", "s34c_n216_s1_A_p4_frag3_cpd4",
)
REUSED_ORDER = FULL_ORDER[:2]
RECOVERY_ORDER = FULL_ORDER[2:]
ARTIFACT_NAMES = ("record.json", "audit.npz", "final_fields.npz", "final_shifted_state.npz", "final_flow.vtk")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
        raise FileExistsError(f"refusing to overwrite immutable recovery release: {OUTPUT}")
    required = (
        CONFIG, ORIGINAL_HANDOFF, ORIGINAL_RUNNER, ORIGINAL_SUPERVISOR, ORIGINAL_OUTPUT,
        INTERRUPTION_AUDITOR, INTERRUPTION_AUDIT, INTERRUPTION_COMPLETION, CONTRACT, RUNNER, SUPERVISOR,
    )
    if not all(path.exists() for path in required):
        raise RuntimeError("required recovery evidence is missing")
    config, original_handoff = load(CONFIG), load(ORIGINAL_HANDOFF)
    interruption, interruption_completion = load(INTERRUPTION_AUDIT), load(INTERRUPTION_COMPLETION)
    runner_source = RUNNER.read_text(encoding="utf-8")
    supervisor_source = SUPERVISOR.read_text(encoding="utf-8")
    tree = ast.parse(runner_source)
    py_compile.compile(str(RUNNER), doraise=True)
    py_compile.compile(str(INTERRUPTION_AUDITOR), doraise=True)

    original_config_hash = "33f110cb29b73389ce74f1464000d4e4b51e6b418024f6282a3554cffeb0004d"
    original_handoff_hash = "94e9e861b410a086d5a689bde04bfa347c313ab133b652166cfcbdbad5590744"
    original_runner_hash = "44c7d6fab8cef09ce0147746e30efa4a489177050733fde2cf2a06fa7b0ce274"
    original_supervisor_hash = "53c414c1ae1d704ae82533f46431baac2faa873b1264de01ceabf6dcdefce4a7"
    original_checks = {
        "original_config_hash_exact": sha(CONFIG) == original_config_hash,
        "original_handoff_hash_exact": sha(ORIGINAL_HANDOFF) == original_handoff_hash,
        "original_runner_hash_exact": sha(ORIGINAL_RUNNER) == original_runner_hash,
        "original_supervisor_hash_exact": sha(ORIGINAL_SUPERVISOR) == original_supervisor_hash,
        "original_release_passed": original_handoff.get("passed") is True
            and original_handoff.get("status") == "stage34c_fragment_cpd4_gpu_execution_authorized",
        "original_output_preserved_incomplete": not (ORIGINAL_OUTPUT / "completion.json").exists()
            and not (ORIGINAL_OUTPUT / "failure.json").exists(),
    }
    lineage_checks = {key: binding_ok(item) for key, item in config["lineage"].items()
                      if isinstance(item, dict) and "path" in item and "sha256" in item}
    geometry_checks = {case_id: binding_ok(item) for case_id, item in config["geometry"]["artifacts"].items()}
    warm_checks = {case_id: binding_ok(item) for case_id, item in config["warm_starts"].items()}
    intact_checks = {key: binding_ok(item["geometry"]) and all(binding_ok(value) for value in item["artifacts"].values())
                     for key, item in config["intact_contexts"].items()}
    clean_checks = {key: all(binding_ok(item[name]) for name in ("record", "geometry", "completion", "evaluation"))
                    for key, item in config["matched_clean_controls"].items()}
    configured_order = tuple(row["case_id"] for row in sorted(config["geometry"]["cases"], key=lambda row: row["run_order"]))
    interruption_checks = {
        "interruption_audit_passed": interruption.get("passed") is True
            and interruption.get("status") == "passed_recoverable_external_interruption"
            and all(interruption.get("checks", {}).values()),
        "interruption_completion_bound": interruption_completion.get("passed") is True
            and interruption_completion.get("interruption_audit_sha256") == sha(INTERRUPTION_AUDIT)
            and interruption_completion.get("auditor_sha256") == sha(INTERRUPTION_AUDITOR),
        "exact_two_completed_bundles": tuple(interruption["completed_order"]) == REUSED_ORDER
            and set(interruption["completed_case_bundles"]) == set(REUSED_ORDER),
    }
    completed_case_checks = {}
    completed_case_bundles = {}
    for case_id in REUSED_ORDER:
        bundle = interruption["completed_case_bundles"][case_id]
        case_dir = Path(bundle["path"])
        artifact_hashes = {name: sha(case_dir / name) for name in ARTIFACT_NAMES}
        record = load(case_dir / "record.json")
        completed_case_checks[case_id] = artifact_hashes == bundle["artifact_sha256"] \
            and record.get("passed") is True and all(value is True for value in record.get("checks", {}).values())
        completed_case_bundles[case_id] = {"path": str(case_dir), "artifact_sha256": artifact_hashes}

    runner_checks = {
        "full_order_exact": assigned_tuple(tree, "FULL_ORDER") == FULL_ORDER,
        "reused_order_derived": "REUSED_ORDER = FULL_ORDER[:2]" in runner_source,
        "recovery_order_derived": "RECOVERY_ORDER = FULL_ORDER[2:]" in runner_source,
        "refuses_overwrite": "refusing to overwrite immutable recovery output" in runner_source,
        "requires_hash_handoff": "recovery handoff/config/runner hash mismatch" in runner_source,
        "verifies_reused_artifacts": "reused artifact hash mismatch" in runner_source,
        "runs_only_recovery_order": "for recovery_ordinal, case_id in enumerate(RECOVERY_ORDER" in runner_source,
        "cpd4_only": '"cpd": 4' in runner_source,
        "preserves_failure": "failed_preserved" in runner_source,
        "no_monotonicity_gate": "monotonicity_not_gated" in runner_source,
    }
    supervisor_checks = {
        "targets_new_recovery_paths": "gpu_confirmation_02_recovery" in supervisor_source
            and "recovery_release_01" in supervisor_source,
        "refuses_existing_targets": "immutable Stage34C recovery run or supervisor target already exists" in supervisor_source,
        "requires_release_and_hashes": "stage34c_fragment_cpd4_recovery_gpu_execution_authorized" in supervisor_source
            and all(token in supervisor_source for token in ("config_sha256", "runner_sha256", "supervisor_sha256")),
        "refuses_competing_python_yade": "Get-Process -Name python,python3,yade" in supervisor_source,
        "one_hidden_launch": supervisor_source.count("Start-Process") == 1 and "-WindowStyle Hidden" in supervisor_source,
    }
    authority_prohibited = (
        "absolute_permeability_validation_claim", "chemical_degradation_claim", "cpd6_flow_execution",
        "mechanics_rerun", "mobile_sand", "migration", "clogging", "deformation",
        "transient_coupling", "two_way_coupling",
    )
    config_checks = {
        "config_schema_status_exact": config.get("schema") == "lbs.stage34c-fragment-cpd4-gpu.v1"
            and config.get("status") == "fragment_cpd4_configuration_frozen_independent_gpu_release_required",
        "full_order_unchanged": configured_order == FULL_ORDER,
        "all_config_self_checks_true": all(config["checks"].values()),
        "all_prohibited_config_authority_false": not any(config["authority"].get(key, False) for key in authority_prohibited),
    }
    checks = {
        "original_chain_exact_and_preserved": all(original_checks.values()),
        "interruption_independently_audited": all(interruption_checks.values()),
        "two_completed_bundles_verified": len(completed_case_checks) == 2 and all(completed_case_checks.values()),
        "all_original_config_lineage_verified": all(lineage_checks.values()),
        "all_eight_geometry_bindings_verified": len(geometry_checks) == 8 and all(geometry_checks.values()),
        "all_eight_warm_starts_verified": len(warm_checks) == 8 and all(warm_checks.values()),
        "all_four_intact_contexts_verified": len(intact_checks) == 4 and all(intact_checks.values()),
        "all_four_clean_contexts_verified": len(clean_checks) == 4 and all(clean_checks.values()),
        "configuration_exact": all(config_checks.values()),
        "recovery_runner_exact": all(runner_checks.values()),
        "recovery_supervisor_exact": all(supervisor_checks.values()),
        "new_recovery_targets_absent": not RUN_OUTPUT.exists() and not SUPERVISOR_OUTPUT.exists(),
    }
    passed = all(checks.values())
    OUTPUT.mkdir(parents=True)
    bindings = {
        "config_sha256": sha(CONFIG), "original_handoff_sha256": sha(ORIGINAL_HANDOFF),
        "original_runner_sha256": sha(ORIGINAL_RUNNER), "original_supervisor_sha256": sha(ORIGINAL_SUPERVISOR),
        "interruption_auditor_sha256": sha(INTERRUPTION_AUDITOR),
        "interruption_audit_sha256": sha(INTERRUPTION_AUDIT),
        "interruption_completion_sha256": sha(INTERRUPTION_COMPLETION),
        "contract_sha256": sha(CONTRACT), "runner_sha256": sha(RUNNER),
        "supervisor_sha256": sha(SUPERVISOR), "release_auditor_sha256": sha(Path(__file__).resolve()),
    }
    authority = {
        "gpu_cpd4_execution": passed, "one_six_case_recovery_only": passed,
        "independent_evaluation": passed, "render": False, "cpd6_flow_execution": False,
        "absolute_permeability_validation_claim": False, "chemical_degradation_claim": False,
        "mechanics_rerun": False, "mobile_sand": False, "migration": False,
        "clogging": False, "deformation": False, "transient_coupling": False,
        "two_way_coupling": False,
    }
    audit = {
        "schema": "lbs.stage34c-fragment-cpd4-recovery-release-audit.v1",
        "status": "stage34c_fragment_cpd4_recovery_gpu_execution_authorized" if passed else "failed_closed",
        "passed": passed, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks, "original_checks": original_checks,
        "interruption_checks": interruption_checks, "completed_case_checks": completed_case_checks,
        "lineage_checks": lineage_checks, "geometry_checks": geometry_checks, "warm_start_checks": warm_checks,
        "intact_checks": intact_checks, "clean_checks": clean_checks,
        "config_checks": config_checks, "runner_checks": runner_checks, "supervisor_checks": supervisor_checks,
        "bindings": bindings, "completed_case_bundles": completed_case_bundles,
        "full_order": list(FULL_ORDER), "reused_order": list(REUSED_ORDER), "recovery_order": list(RECOVERY_ORDER),
        "authority": authority,
        "claim_boundary": "Authorizes one immutable six-case recovery of the interrupted Stage34C CPD4 campaign only.",
    }
    audit_path = OUTPUT / "release_audit.json"
    write(audit_path, audit)
    handoff = {
        "schema": audit["schema"] + ".handoff", "status": audit["status"], "passed": passed,
        "bindings": dict(bindings, release_audit_sha256=sha(audit_path)),
        "completed_case_bundles": completed_case_bundles,
        "full_order": list(FULL_ORDER), "reused_order": list(REUSED_ORDER), "recovery_order": list(RECOVERY_ORDER),
        "authority": authority, "claim_boundary": audit["claim_boundary"],
    }
    handoff_path = OUTPUT / "handoff.json"
    write(handoff_path, handoff)
    print(json.dumps({"passed": passed, "checks": checks, "audit": str(audit_path),
                      "audit_sha256": sha(audit_path), "handoff": str(handoff_path),
                      "handoff_sha256": sha(handoff_path)}, indent=2))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
