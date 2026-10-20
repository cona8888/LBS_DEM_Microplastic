"""Independent pre-run audit for authority-literal-corrected network export."""

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = PROJECT / "stage26_staging" / "stage26b_revision2_network_export_execution_v4.json"
OUTPUT = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260816" / "network_export_prerun_audit_05"


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
        raise RuntimeError("immutable attempt-4 pre-run audit already exists")
    cfg = load_json(CONFIG)
    paths = {name: Path(value) for name, value in cfg["sources"].items() if not name.endswith("_sha256") and name != "expected_yade_version"}
    erratum = load_json(paths["core_count_erratum_checkpoint"])
    failure3 = load_json(paths["attempt3_failure"])
    probe = load_json(paths["environment_probe"])
    exporter = paths["network_exporter"]
    launcher = paths["launcher"]
    calls = o_calls(exporter)
    launcher_text = launcher.read_text(encoding="utf-8")
    output = PROJECT / "stage26_network_exports" / "stage26b_revision2_stage25_network_20260816" / "export_04"
    checks = {
        "all_declared_source_hashes_match": all(digest(path) == cfg["sources"][name + "_sha256"] for name, path in paths.items()),
        "exporter_required_status_literal_exact": cfg.get("status") == "authorized_stage26b_revision2_network_export",
        "attempt3_preload_failure_preserved": (
            failure3.get("passed") is False
            and failure3.get("status") == "failed_before_checkpoint_load"
            and failure3.get("failure_classification") == "configuration_status_schema_mismatch"
            and failure3["side_effects"]["checkpoint_loaded"] is False
            and failure3["side_effects"]["dem_steps_or_runs"] == 0
            and failure3["status_comparison"]["classification_confirmed"] is True
        ),
        "erratum_checkpoint_requires_175": (
            erratum.get("passed") is True
            and erratum["corrected_gate"] == {
                "required_load_bearing_particle_count": 175,
                "core_degree_threshold": 2,
                "particle_count": 216,
                "real_contact_count": 361,
            }
        ),
        "network_targets_match_erratum": (
            cfg["network_export"]["required_sand_particle_count"] == 216
            and cfg["network_export"]["required_sand_contact_count"] == 361
            and cfg["network_export"]["required_load_bearing_particle_count"] == 175
            and cfg["network_export"]["core_degree_threshold"] == 2
        ),
        "exporter_remains_read_only": calls.count("load") == 1 and not any(name in calls for name in ("run", "step", "save", "saveTmp", "reset")),
        "environment_probe_passed_without_yade": probe.get("passed") is True and probe.get("yade_invoked") is False and all(row["passed"] for row in probe["checks"]),
        "attempt4_output_is_new": not output.exists() and Path(cfg["execution"]["output_windows"]) == output,
        "launcher_is_exact_and_fail_closed": all(marker in launcher_text for marker in ("set -euo pipefail", "execution_v4.json", "export_04", "exit 73", "/usr/bin/yade -n -x \"$script\"")) and not any(token in launcher_text for token in ("rm -", "--force")),
        "commands_and_bundle_exact": (
            cfg["execution"]["host_launcher_argv"] == ["wsl.exe", "-d", "Ubuntu", "--", "bash", "/mnt/c/MATDEM_MICROPLASTIC/stage26_staging/run_stage26b_revision2_network_export_v4.sh"]
            and cfg["execution"]["expected_artifacts"] == ["network.json", "particles.csv", "contacts.csv", "completion.json"]
        ),
        "authority_is_network_export_only": cfg["authority"]["network_export_execution_authorized"] is True and all(value is False for name, value in cfg["authority"].items() if name != "network_export_execution_authorized"),
    }
    passed = all(checks.values())
    evidence = {
        "config_path": str(CONFIG), "config_sha256": digest(CONFIG),
        "launcher_path": str(launcher), "launcher_sha256": digest(launcher),
        "exporter_path": str(exporter), "exporter_sha256": digest(exporter),
        "common_path": str(paths["common"]), "common_sha256": digest(paths["common"]),
        "erratum_checkpoint_path": str(paths["core_count_erratum_checkpoint"]), "erratum_checkpoint_sha256": digest(paths["core_count_erratum_checkpoint"]),
        "attempt3_failure_path": str(paths["attempt3_failure"]), "attempt3_failure_sha256": digest(paths["attempt3_failure"]),
        "environment_probe_path": str(paths["environment_probe"]), "environment_probe_sha256": digest(paths["environment_probe"]),
        "auditor_sha256": digest(Path(__file__)),
    }
    evaluation = {
        "schema": "lbs.stage26b-revision2-network-export-prerun-audit.v4",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_authority_literal_corrected_export_prerun_audit" if passed else "failed_attempt4_export_prerun_audit",
        "checks": checks,
        "evidence": evidence,
        "frozen_execution": {
            "wsl_distribution": cfg["execution"]["wsl_distribution"],
            "host_launcher_argv": cfg["execution"]["host_launcher_argv"],
            "output_windows": cfg["execution"]["output_windows"],
            "output_wsl": cfg["execution"]["output_wsl"],
            "expected_artifacts": cfg["execution"]["expected_artifacts"],
            "expected_yade_version": cfg["sources"]["expected_yade_version"],
        },
        "authority": {
            "authorized_next_activity": "Execute corrected attempt 4 exactly once, then independently verify its four-file read-only network bundle.",
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
