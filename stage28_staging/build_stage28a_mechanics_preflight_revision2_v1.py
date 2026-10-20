#!/usr/bin/env python3
"""Build the fail-closed Stage28a Revision-2 mechanics preflight."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
V1_CONFIG = ROOT / "stage28_designs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_preflight_01/config.json"
RUNNER_DIR = ROOT / "stage28_designs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_revision2_runner_01"
RUNNER = RUNNER_DIR / "run_stage28a_two_fibre_mechanics_v2.py"
RUNNER_COMPLETION = RUNNER_DIR / "completion.json"
FAILURE = ROOT / "stage28_evaluations/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_evaluation_01/evaluation.json"
UNIT = ROOT / "stage28_tests/stage28a_yade_groupmask_self_filter_20260824/unit_03/result.json"
OUTPUT = ROOT / "stage28_designs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_preflight_02"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def wsl(path: Path) -> str:
    return str(path).replace("C:\\", "/mnt/c/").replace("\\", "/")


def bind(path: Path) -> dict:
    return {"path": wsl(path), "sha256": sha(path)}


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUTPUT}")
    config = load(V1_CONFIG)
    runner_completion = load(RUNNER_COMPLETION)
    failure = load(FAILURE)
    unit = load(UNIT)
    if not (runner_completion["passed"] and all(runner_completion["checks"].values())):
        raise RuntimeError("Revision-2 runner evidence failed")
    if not (failure["passed"] and unit["passed"] and all(unit["checks"].values())):
        raise RuntimeError("failure or unit evidence failed")

    config["schema"] = "lbs.stage28a-two-fibre-mechanics-preflight.v2"
    config["status"] = "stage28a_two_fibre_mechanics_revision2_preflight_independent_release_required"
    config["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    config["checks"].update({
        "revision1_failure_independently_diagnosed": failure["status"]
        == "verified_implementation_artifact_revision_required",
        "revision2_runner_built_and_bound": runner_completion["passed"],
        "structural_groupmask_unit_passed": unit["passed"] and all(unit["checks"].values()),
        "same_fibre_contact_zero_gate_added": runner_completion["checks"]["intrafibre_zero_gate_present"],
    })
    config["sources"]["runner_v1"] = config["sources"].pop("runner")
    config["sources"]["runner"] = bind(RUNNER)
    config["sources"]["revision2_runner_completion"] = bind(RUNNER_COMPLETION)
    config["sources"]["revision1_failure_evaluation"] = bind(FAILURE)
    config["sources"]["structural_groupmask_unit"] = bind(UNIT)
    config["sources"]["revision2_preflight_builder"] = bind(Path(__file__).resolve())
    config["implementation_revision"] = {
        "cause": "same-fibre GridConnection contacts activated by the Revision-1 grid-grid law",
        "structural_filter": {
            "collider_avoid_self_interaction_mask": 6,
            "common_collision_bit": 1,
            "fibre_group_masks": [3, 5],
        },
        "unchanged": [
            "six case geometries",
            "sand source state",
            "fibre material and resolution",
            "loading history",
            "time-step and damping",
            "acceptance limits",
        ],
    }
    config["authority"] = {
        "independent_execution_audit": True,
        "mechanics_execution_authorized": False,
        "gpu_execution_authorized": False,
        "production_concentration_campaign_authorized": False,
        "mobile_sand_authorized": False,
        "two_way_coupling_authorized": False,
    }
    if not all(config["checks"].values()):
        raise RuntimeError("Revision-2 preflight checks failed")
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "config.json"
    path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    completion = {
        "schema": config["schema"] + ".completion",
        "status": config["status"],
        "passed": True,
        "checks": config["checks"],
        "config": {"path": str(path), "sha256": sha(path)},
        "next_handoff": {
            "authorized": "independent Revision-2 execution audit",
            "not_authorized": "YADE mechanics execution or GPU execution",
        },
    }
    completion_path = OUTPUT / "completion.json"
    completion_path.write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"config": str(path), "config_sha256": sha(path),
                      "completion": str(completion_path), "completion_sha256": sha(completion_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
