"""Independent pre-run audit for the exact Revision-2 Stage25 network export."""

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = PROJECT / "stage26_staging" / "stage26b_revision2_network_export_execution_v1.json"
OUTPUT = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260815" / "network_export_prerun_audit_02"


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
        raise RuntimeError("immutable pre-run audit output already exists")
    cfg = load_json(CONFIG)
    source_checkpoint = load_json(Path(cfg["sources"]["source_checkpoint"]))
    source_audit = load_json(Path(cfg["sources"]["source_audit"]))
    environment_probe = load_json(Path(cfg["sources"]["environment_probe"]))
    exporter = Path(cfg["sources"]["network_exporter"])
    common = Path(cfg["sources"]["common"])
    launcher = Path(cfg["sources"]["launcher"])
    launcher_text = launcher.read_text(encoding="utf-8")
    calls = o_calls(exporter)
    checks = {}
    checks["all_source_hashes_match"] = all(
        digest(Path(value)) == cfg["sources"][key + "_sha256"]
        for key, value in cfg["sources"].items()
        if not key.endswith("_sha256") and key != "expected_yade_version"
    )
    checks["source_checkpoint_allows_only_config_preparation"] = (
        source_checkpoint.get("passed") is True
        and source_checkpoint.get("status") == "frozen_audited_sources_no_yade_execution"
        and source_checkpoint["authority"]["network_export_execution_authorized"] is False
        and source_checkpoint["authority"]["prefilter_yade_execution_authorized"] is False
        and "Prepare and independently audit" in source_checkpoint["authority"]["authorized_next_activity"]
    )
    checks["source_audit_passed"] = (
        source_audit.get("passed") is True
        and source_audit.get("status") == "passed_source_audit_without_yade_execution"
        and source_audit["source_hashes"]["network_exporter"] == digest(exporter)
        and source_audit["source_hashes"]["common"] == digest(common)
    )
    checks["wsl_environment_probe_passed_without_yade"] = (
        environment_probe.get("passed") is True
        and environment_probe.get("status") == "passed_read_only_wsl_path_probe"
        and environment_probe.get("wsl_distribution") == "Ubuntu"
        and environment_probe.get("yade_invoked") is False
        and len(environment_probe.get("checks", [])) == 4
        and all(row.get("passed") is True for row in environment_probe["checks"])
    )
    checks["configuration_status"] = cfg.get("status") == "authorized_stage26b_revision2_network_export"
    authority = cfg["authority"]
    checks["authority_is_network_export_only"] = (
        authority.get("network_export_execution_authorized") is True
        and all(
            authority.get(name) is False for name in (
                "placement_generation_authorized", "prefilter_yade_execution_authorized",
                "two_fibre_free_release_authorized", "four_fibre_execution_authorized",
                "eight_or_more_fibre_execution_authorized", "flow_execution_authorized",
                "deformation_coupled_flow_authorized", "transient_two_way_coupling_authorized",
                "production_parametric_study_authorized",
            )
        )
    )
    network = cfg["network_export"]
    checks["exact_stage25_network_targets"] = (
        network["required_sand_particle_count"] == 216
        and network["required_sand_contact_count"] == 361
        and network["required_load_bearing_particle_count"] == 180
        and network["core_degree_threshold"] == 2
        and network["real_sand_sand_contacts_only"] is True
    )
    operations = network["dem_state_operations"]
    checks["declared_read_only_operations"] = (
        operations == {
            "load_checkpoint": True,
            "step": False,
            "run": False,
            "save_checkpoint": False,
            "modify_body_state": False,
            "modify_cell_state": False,
        }
    )
    checks["exporter_static_read_only"] = (
        calls.count("load") == 1
        and not any(name in calls for name in ("run", "step", "save", "saveTmp", "reset"))
    )
    execution = cfg["execution"]
    expected_output = PROJECT / "stage26_network_exports" / "stage26b_revision2_stage25_network_20260815" / "export_01"
    checks["output_target_is_new_and_exact"] = (
        Path(execution["output_windows"]) == expected_output
        and not expected_output.exists()
        and execution["immutable_output"] is True
        and execution["one_shot"] is True
        and execution["gpu_required"] is False
    )
    checks["exact_engine_argv"] = execution["engine_argv"] == [
        "/usr/bin/yade", "-n", "-x",
        "/mnt/c/MATDEM_MICROPLASTIC/stage26_staging/export_stage26b_revision2_stage25_network_v1.py",
    ]
    checks["exact_wsl_distribution_and_host_launcher"] = (
        execution["wsl_distribution"] == "Ubuntu"
        and execution["host_launcher_argv"] == [
            "wsl.exe", "-d", "Ubuntu", "--", "bash",
            "/mnt/c/MATDEM_MICROPLASTIC/stage26_staging/run_stage26b_revision2_network_export_v1.sh",
        ]
    )
    env = execution["environment"]
    checks["exact_environment"] = (
        env["STAGE26B_R2_NETWORK_CONFIG"].endswith("/stage26b_revision2_network_export_execution_v1.json")
        and env["STAGE26B_R2_NETWORK_OUTPUT"] == execution["output_wsl"]
        and env["STAGE26B_R2_NETWORK_SCRIPT"] == execution["engine_argv"][-1]
    )
    checks["launcher_is_fail_closed"] = all(marker in launcher_text for marker in (
        "set -euo pipefail",
        "if [[ -e \"$output\" ]]",
        "exit 73",
        "exec env",
        "/usr/bin/yade -n -x \"$script\"",
    )) and not any(token in launcher_text for token in ("rm -", "--force", "> completion.json"))
    checks["expected_four_file_bundle"] = execution["expected_artifacts"] == [
        "network.json", "particles.csv", "contacts.csv", "completion.json"
    ]
    checks["engine_version_is_frozen"] = cfg["sources"]["expected_yade_version"] == "2022.01a"
    passed = all(checks.values())
    evaluation = {
        "schema": "lbs.stage26b-revision2-network-export-prerun-audit.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_exact_read_only_export_prerun_audit" if passed else "failed_export_prerun_audit",
        "checks": checks,
        "evidence": {
            "config_path": str(CONFIG),
            "config_sha256": digest(CONFIG),
            "launcher_path": str(launcher),
            "launcher_sha256": digest(launcher),
            "exporter_path": str(exporter),
            "exporter_sha256": digest(exporter),
            "common_path": str(common),
            "common_sha256": digest(common),
            "source_checkpoint_path": cfg["sources"]["source_checkpoint"],
            "source_checkpoint_sha256": cfg["sources"]["source_checkpoint_sha256"],
            "auditor_sha256": digest(Path(__file__)),
        },
        "frozen_execution": {
            "wsl_distribution": execution["wsl_distribution"],
            "host_launcher_argv": execution["host_launcher_argv"],
            "launcher_wsl": execution["launcher_wsl"],
            "output_windows": execution["output_windows"],
            "output_wsl": execution["output_wsl"],
            "expected_artifacts": execution["expected_artifacts"],
            "expected_yade_version": cfg["sources"]["expected_yade_version"],
        },
        "authority": {
            "authorized_next_activity": "Execute exactly one read-only Stage25 contact-network export using the frozen launcher, then independently verify the four-file bundle.",
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
