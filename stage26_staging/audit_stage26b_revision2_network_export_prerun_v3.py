"""Independent pre-run audit for corrected network-export attempt 3."""

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = PROJECT / "stage26_staging" / "stage26b_revision2_network_export_execution_v3.json"
OUTPUT = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260816" / "network_export_prerun_audit_04"


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
        raise RuntimeError("immutable attempt-3 pre-run audit already exists")
    cfg = load_json(CONFIG)
    paths = {name: Path(value) for name, value in cfg["sources"].items() if not name.endswith("_sha256") and name != "expected_yade_version"}
    all_hashes_match = all(digest(path) == cfg["sources"][name + "_sha256"] for name, path in paths.items())
    source_checkpoint = load_json(paths["source_checkpoint"])
    source_audit = load_json(paths["source_audit"])
    erratum = load_json(paths["core_count_erratum_checkpoint"])
    failure1 = load_json(paths["attempt1_failure"])
    failure2 = load_json(paths["attempt2_failure"])
    probe = load_json(paths["environment_probe"])
    exporter = paths["network_exporter"]
    launcher = paths["launcher"]
    calls = o_calls(exporter)
    launcher_text = launcher.read_text(encoding="utf-8")
    network = cfg["network_export"]
    execution = cfg["execution"]
    output = PROJECT / "stage26_network_exports" / "stage26b_revision2_stage25_network_20260816" / "export_03"
    checks = {
        "all_declared_source_hashes_match": all_hashes_match,
        "source_checkpoint_and_audit_passed": (
            source_checkpoint.get("passed") is True and source_audit.get("passed") is True
            and source_checkpoint["evidence"]["source_hashes"]["network_exporter"] == digest(exporter)
            and source_audit["checks"]["exporter_is_read_only"] is True
        ),
        "both_prior_failures_preserved": (
            failure1.get("passed") is False and failure1["side_effects"]["dem_steps_or_runs"] == 0
            and failure2.get("passed") is False and failure2["side_effects"]["dem_steps_or_runs"] == 0
            and failure2["gate_comparison"]["comparator_passed"] is True
        ),
        "erratum_checkpoint_passed_and_exact": (
            erratum.get("passed") is True
            and erratum.get("status") == "frozen_evidence_bound_stage25_core_count_175"
            and erratum["corrected_gate"] == {
                "required_load_bearing_particle_count": 175,
                "core_degree_threshold": 2,
                "particle_count": 216,
                "real_contact_count": 361,
            }
        ),
        "attempt3_environment_probe_passed_without_yade": (
            probe.get("passed") is True and probe.get("yade_invoked") is False
            and probe.get("wsl_distribution") == "Ubuntu"
            and len(probe.get("checks", [])) == 5
            and all(row.get("passed") is True for row in probe["checks"])
        ),
        "exporter_is_still_read_only": calls.count("load") == 1 and not any(name in calls for name in ("run", "step", "save", "saveTmp", "reset")),
        "corrected_exact_network_targets": (
            network["required_sand_particle_count"] == 216
            and network["required_sand_contact_count"] == 361
            and network["required_load_bearing_particle_count"] == 175
            and network["core_degree_threshold"] == 2
            and network["dem_state_operations"] == {
                "load_checkpoint": True, "step": False, "run": False,
                "save_checkpoint": False, "modify_body_state": False, "modify_cell_state": False,
            }
        ),
        "attempt3_output_is_new": Path(execution["output_windows"]) == output and not output.exists() and execution["immutable_output"] is True and execution["one_shot"] is True,
        "exact_commands": (
            execution["host_launcher_argv"] == ["wsl.exe", "-d", "Ubuntu", "--", "bash", "/mnt/c/MATDEM_MICROPLASTIC/stage26_staging/run_stage26b_revision2_network_export_v3.sh"]
            and execution["engine_argv"] == ["/usr/bin/yade", "-n", "-x", "/mnt/c/MATDEM_MICROPLASTIC/stage26_staging/export_stage26b_revision2_stage25_network_v1.py"]
        ),
        "launcher_fail_closed": all(marker in launcher_text for marker in ("set -euo pipefail", "export_03", "execution_v3.json", "exit 73", "exec env", "/usr/bin/yade -n -x \"$script\"")) and not any(token in launcher_text for token in ("rm -", "--force")),
        "expected_four_file_bundle": execution["expected_artifacts"] == ["network.json", "particles.csv", "contacts.csv", "completion.json"],
        "authority_is_export_only": cfg["authority"]["network_export_execution_authorized"] is True and all(value is False for name, value in cfg["authority"].items() if name != "network_export_execution_authorized"),
    }
    passed = all(checks.values())
    evaluation = {
        "schema": "lbs.stage26b-revision2-network-export-prerun-audit.v3",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_corrected_exact_read_only_export_prerun_audit" if passed else "failed_attempt3_export_prerun_audit",
        "checks": checks,
        "evidence": {
            "config_path": str(CONFIG), "config_sha256": digest(CONFIG),
            "launcher_path": str(launcher), "launcher_sha256": digest(launcher),
            "exporter_path": str(exporter), "exporter_sha256": digest(exporter),
            "common_path": str(paths["common"]), "common_sha256": digest(paths["common"]),
            "source_checkpoint_path": str(paths["source_checkpoint"]), "source_checkpoint_sha256": digest(paths["source_checkpoint"]),
            "erratum_checkpoint_path": str(paths["core_count_erratum_checkpoint"]), "erratum_checkpoint_sha256": digest(paths["core_count_erratum_checkpoint"]),
            "attempt1_failure_path": str(paths["attempt1_failure"]), "attempt1_failure_sha256": digest(paths["attempt1_failure"]),
            "attempt2_failure_path": str(paths["attempt2_failure"]), "attempt2_failure_sha256": digest(paths["attempt2_failure"]),
            "environment_probe_path": str(paths["environment_probe"]), "environment_probe_sha256": digest(paths["environment_probe"]),
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
            "authorized_next_activity": "Execute corrected attempt 3 exactly once, then independently verify its four-file read-only network bundle.",
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
