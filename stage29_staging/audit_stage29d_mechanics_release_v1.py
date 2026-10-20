from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STUDY = "stage29d_shared_pair_context_qualification_20260825"
CONFIG = ROOT / "stage29_designs" / STUDY / "mechanics_preflight_01" / "config.json"
COMPLETION = ROOT / "stage29_designs" / STUDY / "mechanics_preflight_01" / "completion.json"
RUNNER = ROOT / "stage29_designs" / STUDY / "mechanics_runner_01" / "run_stage29d_four_fibre_mechanics_v1.py"
OUT = ROOT / "stage29_evaluations" / STUDY / "mechanics_release_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def windows_path(wsl_path: str) -> Path:
    if not wsl_path.startswith("/mnt/c/"):
        raise ValueError(wsl_path)
    return Path("C:/" + wsl_path[len("/mnt/c/"):])


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUT}")
    config = json.loads(CONFIG.read_text())
    completion = json.loads(COMPLETION.read_text())
    runner_text = RUNNER.read_text()
    ast.parse(runner_text)
    source_checks = {}
    for name, value in config["sources"].items():
        if name == "expected_yade_version":
            continue
        path = windows_path(value["path"])
        source_checks[name] = path.is_file() and sha(path) == value["sha256"]
    unit = json.loads(windows_path(config["sources"]["four_fibre_groupmask_unit"]["path"]).read_text())
    geometry_audit = json.loads(windows_path(config["sources"]["geometry_audit"]["path"]).read_text())
    prior_eval = json.loads(windows_path(config["sources"]["stage28_revision2_evaluation"]["path"]).read_text())
    cases = config["execution_cases"]
    checks = {
        "preflight_completion_passed": completion.get("passed") is True,
        "completion_binds_config": completion.get("config_sha256") == sha(CONFIG),
        "completion_binds_runner": completion.get("runner_sha256") == sha(RUNNER),
        "all_source_hashes_match": all(source_checks.values()),
        "runner_python_syntax": True,
        "runner_uses_four_fibre_self_mask": "sum(2 << i for i in range(4))" in runner_text,
        "runner_checks_exact_terminal_graph": "terminal_contact_graphs_exact" in runner_text,
        "runner_checks_no_unintended_edges": "no_unintended_contact_edges_ever" in runner_text,
        "runner_checks_context_paths": "paired_context_path_match" in runner_text,
        "four_fibre_unit_passed_and_version_bound": unit.get("passed") is True and unit["metrics"]["avoid_self_interaction_mask"] == 30 and unit["environment"]["yade_version"] == config["sources"]["expected_yade_version"],
        "geometry_audit_passed": geometry_audit.get("passed") is True,
        "stage28_revision2_mechanics_passed": prior_eval.get("passed") is True,
        "exact_six_four_fibre_cases": len(cases) == 6 and all(len(x["fibres"]) == 4 for x in cases),
        "paired_context_sources_exact": all(len({tuple(x["context_source_faces"]) for x in cases if x["context_block"] == block}) == 1 for block in "ABC"),
        "config_fail_closed": config["authority"]["mechanics_execution"] is False and config["authority"]["gpu_flow"] is False,
    }
    passed = all(checks.values())
    handoff = {
        "schema": "lbs.stage29d-four-fibre-mechanics-release.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "stage29d_four_fibre_mechanics_execution_authorized" if passed else "stage29d_four_fibre_mechanics_release_failed",
        "checks": checks,
        "source_checks": source_checks,
        "bindings": {"config_path": "/mnt/c/MATDEM_MICROPLASTIC/stage29_designs/stage29d_shared_pair_context_qualification_20260825/mechanics_preflight_01/config.json", "config_sha256": sha(CONFIG), "runner_path": "/mnt/c/MATDEM_MICROPLASTIC/stage29_designs/stage29d_shared_pair_context_qualification_20260825/mechanics_runner_01/run_stage29d_four_fibre_mechanics_v1.py", "runner_sha256": sha(RUNNER)},
        "authority": {"mechanics_execution": passed, "gpu_flow": False, "permeability_claim": False, "mobile_sand": False, "two_way_coupling": False},
        "next_handoff": {"authorized": "one immutable six-case YADE mechanics execution" if passed else "diagnosis only", "not_authorized": "rerun, GPU flow, permeability claims, mobile sand, or coupling"},
    }
    OUT.mkdir(parents=True)
    p = OUT / "handoff.json"
    p.write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "checkpoint_manifest.json").write_text(json.dumps({"schema": handoff["schema"] + ".checkpoint", "passed": passed, "handoff_sha256": sha(p), "config_sha256": sha(CONFIG), "runner_sha256": sha(RUNNER), "authority": handoff["next_handoff"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), **handoff}, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
