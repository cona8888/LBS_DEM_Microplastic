#!/usr/bin/env python3
"""Independently audit and release the Stage31c six-block mechanics run."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
CONFIG = ROOT / "stage31_designs/stage31c_replicated_nested_mechanics_20260826/mechanics_preflight_01/config.json"
COMPLETION = CONFIG.parent / "completion.json"
OUTPUT = ROOT / "stage31_evaluations/stage31c_replicated_nested_mechanics_20260826/mechanics_release_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def host_path(wsl_path: str) -> Path:
    prefix = "/mnt/c/"
    if not wsl_path.startswith(prefix):
        raise ValueError(f"unsupported source path: {wsl_path}")
    return Path("C:/" + wsl_path[len(prefix):])


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable audit: {OUTPUT}")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    completion = json.loads(COMPLETION.read_text(encoding="utf-8"))
    cases = config["execution_cases"]
    source_checks = {}
    for name, binding in config["sources"].items():
        if isinstance(binding, dict) and "path" in binding and "sha256" in binding:
            path = host_path(binding["path"])
            source_checks[name] = path.is_file() and sha(path) == binding["sha256"]
    case_state_checks = {
        case["case_id"]: (
            host_path(case["source_state"]["path"]).is_file()
            and sha(host_path(case["source_state"]["path"])) == case["source_state"]["sha256"]
        )
        for case in cases
    }
    pairs = [(case["packing_id"], case["placement_block"]) for case in cases]
    checks = {
        "config_status": config.get("status") == "stage31c_replicated_nested_mechanics_preflight_release_required",
        "config_fail_closed": config["authority"] == {"mechanics_execution": False, "gpu_flow": False, "permeability_claim": False, "mobile_sand": False, "coupling": False},
        "completion_passed": completion.get("passed") is True,
        "completion_config_hash": completion.get("config_sha256") == sha(CONFIG),
        "completion_runner_hash": completion.get("runner_sha256") == config["sources"]["runner"]["sha256"],
        "all_source_hashes": bool(source_checks) and all(source_checks.values()),
        "all_case_state_hashes": all(case_state_checks.values()),
        "six_unique_cases": len(cases) == 6 and len({case["case_id"] for case in cases}) == 6,
        "complete_factorial_blocks": set(pairs) == {(packing, block) for packing in ("n216_s1", "n216_s2", "n216_s3") for block in ("A", "B")},
        "four_fibres_each": all(len(case["fibres"]) == 4 for case in cases),
        "nested_ranks_exact": all([fibre["nested_rank"] for fibre in case["fibres"]] == [1, 2, 3, 4] for case in cases),
        "unique_faces_within_blocks": all(len({fibre["source_face_index"] for fibre in case["fibres"]}) == 4 for case in cases),
        "mechanics_protocol_unchanged": config["mechanics"] == json.loads(host_path(config["sources"]["accepted_stage29d_config"]["path"]).read_text(encoding="utf-8"))["mechanics"],
        "hard_zero_cross_contact_gates": config["acceptance"]["maximum_fibre_fibre_contacts"] == 0 and config["acceptance"]["maximum_cross_fibre_node_interactions"] == 0 and config["acceptance"]["maximum_intrafibre_grid_contacts"] == 0,
        "positive_initial_separation": config["acceptance"]["minimum_initial_interfibre_surface_clearance_m"] > 0.0,
    }
    passed = all(checks.values())
    handoff = {
        "schema": "lbs.stage31c-replicated-nested-mechanics-release.v1",
        "status": "stage31c_replicated_nested_mechanics_execution_authorized" if passed else "stage31c_replicated_nested_mechanics_execution_not_authorized",
        "passed": passed,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "source_checks": source_checks,
        "case_state_checks": case_state_checks,
        "bindings": {"config_sha256": sha(CONFIG), "runner_sha256": config["sources"]["runner"]["sha256"], "completion_sha256": sha(COMPLETION)},
        "authority": {"mechanics_execution": passed, "gpu_flow": False, "permeability_claim": False, "mobile_sand": False, "coupling": False},
        "claim_boundary": "Authorizes only the six frozen Stage31c fixed-sand CPU YADE mechanics cases. It does not authorize flow or any hydraulic claim.",
    }
    OUTPUT.mkdir(parents=True)
    (OUTPUT / "handoff.json").write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "status": handoff["status"], "passed": passed, "checks": checks}, indent=2))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
