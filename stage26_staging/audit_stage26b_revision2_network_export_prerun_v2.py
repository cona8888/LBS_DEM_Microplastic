"""Independent pre-run audit for revised network-export attempt 2."""

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = PROJECT / "stage26_staging" / "stage26b_revision2_network_export_execution_v2.json"
OUTPUT = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260816" / "network_export_prerun_audit_03"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def o_calls(path):
    parsed = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result = []
    for node in ast.walk(parsed):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "O":
                result.append(node.func.attr)
    return result


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable revised pre-run audit already exists")
    cfg = load_json(CONFIG)
    source_checkpoint = load_json(Path(cfg["sources"]["source_checkpoint"]))
    source_audit = load_json(Path(cfg["sources"]["source_audit"]))
    failure = load_json(Path(cfg["sources"]["attempt1_failure"]))
    probe = load_json(Path(cfg["sources"]["environment_probe"]))
    exporter = Path(cfg["sources"]["network_exporter"])
    launcher = Path(cfg["sources"]["launcher"])
    exporter_text = exporter.read_text(encoding="utf-8")
    launcher_text = launcher.read_text(encoding="utf-8")
    calls = o_calls(exporter)
    checks = {}
    checks["all_source_hashes_match"] = all(
        digest(Path(value)) == cfg["sources"][key + "_sha256"]
        for key, value in cfg["sources"].items()
        if not key.endswith("_sha256") and key != "expected_yade_version"
    )
    checks["attempt1_failure_preserved"] = (
        failure.get("passed") is False
        and failure.get("status") == "failed_before_checkpoint_load"
        and failure.get("failure_classification") == "software_import_path_defect"
        and failure["side_effects"]["checkpoint_loaded"] is False
        and failure["side_effects"]["dem_steps_or_runs"] == 0
        and failure["authority"]["network_export_retry_authorized"] is False
    )
    checks["revised_source_checkpoint_passed"] = (
        source_checkpoint.get("passed") is True
        and source_checkpoint.get("status") == "frozen_audited_sources_no_yade_execution"
        and source_checkpoint["evidence"]["source_hashes"]["network_exporter"] == digest(exporter)
    )
    checks["revised_source_audit_closes_import_defect"] = (
        source_audit.get("passed") is True
        and source_audit["checks"].get("yade_entrypoints_resolve_sibling_module") is True
        and source_audit["checks"].get("exporter_is_read_only") is True
        and source_audit["source_hashes"]["network_exporter"] == digest(exporter)
    )
    checks["revised_environment_probe_passed_without_yade"] = (
        probe.get("passed") is True
        and probe.get("status") == "passed_revised_read_only_wsl_path_probe"
        and probe.get("wsl_distribution") == "Ubuntu"
        and probe.get("yade_invoked") is False
        and len(probe.get("checks", [])) == 5
        and all(row.get("passed") is True for row in probe["checks"])
    )
    checks["explicit_sibling_import_resolution_present"] = (
        "STAGE26B_R2_NETWORK_SCRIPT" in exporter_text
        and "sys.path.insert(0, SCRIPT_DIRECTORY)" in exporter_text
    )
    checks["exporter_remains_read_only"] = (
        calls.count("load") == 1
        and not any(name in calls for name in ("run", "step", "save", "saveTmp", "reset"))
    )
    authority = cfg["authority"]
    checks["authority_is_retry_export_only"] = (
        authority["network_export_execution_authorized"] is True
        and all(authority[name] is False for name in authority if name != "network_export_execution_authorized")
    )
    network = cfg["network_export"]
    checks["exact_network_targets"] = (
        network["required_sand_particle_count"] == 216
        and network["required_sand_contact_count"] == 361
        and network["required_load_bearing_particle_count"] == 180
        and network["core_degree_threshold"] == 2
        and network["dem_state_operations"] == {
            "load_checkpoint": True, "step": False, "run": False,
            "save_checkpoint": False, "modify_body_state": False, "modify_cell_state": False,
        }
    )
    execution = cfg["execution"]
    expected_output = PROJECT / "stage26_network_exports" / "stage26b_revision2_stage25_network_20260816" / "export_02"
    checks["new_attempt2_output"] = (
        Path(execution["output_windows"]) == expected_output
        and not expected_output.exists()
        and execution["immutable_output"] is True
        and execution["one_shot"] is True
        and execution["gpu_required"] is False
    )
    checks["exact_host_and_engine_commands"] = (
        execution["host_launcher_argv"] == [
            "wsl.exe", "-d", "Ubuntu", "--", "bash",
            "/mnt/c/MATDEM_MICROPLASTIC/stage26_staging/run_stage26b_revision2_network_export_v2.sh",
        ]
        and execution["engine_argv"] == [
            "/usr/bin/yade", "-n", "-x",
            "/mnt/c/MATDEM_MICROPLASTIC/stage26_staging/export_stage26b_revision2_stage25_network_v1.py",
        ]
    )
    checks["launcher_fail_closed_and_revised"] = all(marker in launcher_text for marker in (
        "set -euo pipefail", "export_02", "execution_v2.json", "if [[ -e \"$output\" ]]",
        "exit 73", "exec env", "/usr/bin/yade -n -x \"$script\"",
    )) and not any(token in launcher_text for token in ("rm -", "--force"))
    checks["expected_bundle"] = execution["expected_artifacts"] == [
        "network.json", "particles.csv", "contacts.csv", "completion.json"
    ]
    passed = all(checks.values())
    evaluation = {
        "schema": "lbs.stage26b-revision2-network-export-prerun-audit.v2",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_revised_exact_read_only_export_prerun_audit" if passed else "failed_revised_export_prerun_audit",
        "checks": checks,
        "evidence": {
            "config_path": str(CONFIG), "config_sha256": digest(CONFIG),
            "launcher_path": str(launcher), "launcher_sha256": digest(launcher),
            "exporter_path": str(exporter), "exporter_sha256": digest(exporter),
            "source_checkpoint_path": cfg["sources"]["source_checkpoint"],
            "source_checkpoint_sha256": cfg["sources"]["source_checkpoint_sha256"],
            "attempt1_failure_path": cfg["sources"]["attempt1_failure"],
            "attempt1_failure_sha256": cfg["sources"]["attempt1_failure_sha256"],
            "auditor_sha256": digest(Path(__file__)),
        },
        "frozen_execution": {
            "wsl_distribution": execution["wsl_distribution"],
            "host_launcher_argv": execution["host_launcher_argv"],
            "output_windows": execution["output_windows"],
            "output_wsl": execution["output_wsl"],
            "expected_artifacts": execution["expected_artifacts"],
            "expected_yade_version": cfg["sources"]["expected_yade_version"],
        },
        "authority": {
            "authorized_next_activity": "Execute revised attempt 2 exactly once, then independently verify its four-file read-only network bundle.",
            "network_export_execution_authorized": passed,
            "placement_generation_authorized": False,
            "prefilter_yade_execution_authorized": False,
            "two_fibre_free_release_authorized": False,
            "four_fibre_execution_authorized": False,
            "flow_execution_authorized": False,
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "evaluation.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": passed, "evaluation_sha256": digest(path)}, sort_keys=True))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
