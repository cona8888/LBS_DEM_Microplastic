#!/usr/bin/env python3
"""Generate the immutable Stage28a Revision-2 runner from the frozen v1 runner."""

from __future__ import annotations

import hashlib
import json
import py_compile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
V1 = ROOT / "stage28_staging/run_stage28a_two_fibre_mechanics_v1.py"
FAILURE = ROOT / "stage28_evaluations/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_evaluation_01/evaluation.json"
UNIT = ROOT / "stage28_tests/stage28a_yade_groupmask_self_filter_20260824/unit_03/result.json"
OUTPUT = ROOT / "stage28_designs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_revision2_runner_01"
RUNNER_NAME = "run_stage28a_two_fibre_mechanics_v2.py"
EXPECTED_V1_SHA = "856ee61a922611911971ec73f947418ceaf507659ce92108fcf2e584b249edbc"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one replacement target, found {count}")
    return source.replace(old, new, 1)


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUTPUT}")
    failure = json.loads(FAILURE.read_text(encoding="utf-8"))
    unit = json.loads(UNIT.read_text(encoding="utf-8"))
    if sha(V1) != EXPECTED_V1_SHA:
        raise RuntimeError("frozen v1 runner hash changed")
    if not (failure.get("passed") and failure["status"] == "verified_implementation_artifact_revision_required"):
        raise RuntimeError("failure diagnosis is not accepted")
    if not (unit.get("passed") and all(unit["checks"].values())):
        raise RuntimeError("structural group-mask unit evidence is not accepted")

    source = V1.read_text(encoding="utf-8")
    replacements = []
    def revise(old: str, new: str, label: str) -> None:
        nonlocal source
        source = replace_once(source, old, new, label)
        replacements.append(label)

    revise(
        '"""YADE runner for isolated and paired Stage28a flexible-fibre mechanics."""',
        '"""YADE Stage28a Revision-2 runner with structural same-fibre contact filtering."""',
        "docstring",
    )
    revise(
        'RUNNER = "/mnt/c/MATDEM_MICROPLASTIC/stage28_staging/run_stage28a_two_fibre_mechanics_v1.py"',
        'RUNNER = "/mnt/c/MATDEM_MICROPLASTIC/stage28_designs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_revision2_runner_01/run_stage28a_two_fibre_mechanics_v2.py"',
        "runner_path",
    )
    revise(
        '"stage28a_two_fibre_mechanics_preflight_independent_release_required"',
        '"stage28a_two_fibre_mechanics_revision2_preflight_independent_release_required"',
        "config_status",
    )
    revise(
        '"stage28a_mechanics_execution_authorized"',
        '"stage28a_revision2_mechanics_execution_authorized"',
        "handoff_status",
    )
    revise(
        "InsertionSortCollider([Bo1_Sphere_Aabb(), Bo1_GridConnection_Aabb()]),",
        "InsertionSortCollider(\n            [Bo1_Sphere_Aabb(), Bo1_GridConnection_Aabb()],\n            avoidSelfInteractionMask=6,\n        ),",
        "collider_structural_filter",
    )
    revise(
        "        for body_id in nodes:\n            node_owner[body_id] = fibre_index",
        "        fibre_group_mask = 1 | (2 << fibre_index)\n"
        "        for body_id in nodes + connections:\n"
        "            O.bodies[body_id].groupMask = fibre_group_mask\n"
        "        for body_id in nodes:\n"
        "            node_owner[body_id] = fibre_index",
        "per_fibre_group_masks",
    )
    revise(
        '    "no_cross_fibre_node_bond": all(\n        case["maximum_cross_fibre_node_real_interaction_count"] == 0 for case in cases\n    ),',
        '    "no_cross_fibre_node_bond": all(\n'
        '        case["maximum_cross_fibre_node_real_interaction_count"] == 0 for case in cases\n'
        '    ),\n'
        '    "no_intrafibre_grid_contact": all(\n'
        '        case["maximum_intrafibre_contact_count"] == 0 for case in cases\n'
        '    ),',
        "intrafibre_zero_gate",
    )
    revise(
        '"schema": "lbs.stage28a-two-fibre-mechanics-result.v1"',
        '"schema": "lbs.stage28a-two-fibre-mechanics-result.v2"',
        "result_schema",
    )
    revise(
        '"status": "two_fibre_mechanics_verified" if passed else "two_fibre_mechanics_not_qualified"',
        '"status": "two_fibre_mechanics_revision2_verified" if passed else "two_fibre_mechanics_revision2_not_qualified"',
        "result_status",
    )

    OUTPUT.mkdir(parents=True)
    runner = OUTPUT / RUNNER_NAME
    runner.write_text(source, encoding="utf-8")
    py_compile.compile(str(runner), doraise=True)
    checks = {
        "frozen_v1_hash": sha(V1) == EXPECTED_V1_SHA,
        "failure_diagnosis_bound": sha(FAILURE) == "a6f21bc029e94357ae264c9707cc45524d3c324f270c2f8b0167d76da3533dda",
        "structural_unit_passed": unit["passed"] and all(unit["checks"].values()),
        "all_nine_revisions_applied_once": len(replacements) == 9,
        "runner_compiles": True,
        "structural_filter_present": "avoidSelfInteractionMask=6" in source,
        "fibre_masks_present": "fibre_group_mask = 1 | (2 << fibre_index)" in source,
        "intrafibre_zero_gate_present": '"no_intrafibre_grid_contact"' in source,
    }
    if not all(checks.values()):
        raise RuntimeError("generated runner verification failed")
    completion = {
        "schema": "lbs.stage28a-two-fibre-mechanics-runner-revision2.v1",
        "status": "revision2_runner_built_independent_execution_audit_required",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "checks": checks,
        "replacements": replacements,
        "bindings": {
            "runner_v1": {"path": str(V1), "sha256": sha(V1)},
            "failure_evaluation": {"path": str(FAILURE), "sha256": sha(FAILURE)},
            "structural_unit": {"path": str(UNIT), "sha256": sha(UNIT)},
            "runner_v2": {"path": str(runner), "sha256": sha(runner)},
            "builder": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).resolve())},
        },
        "authority": {"preflight_revision": True, "mechanics_execution": False, "gpu_execution": False},
    }
    completion_path = OUTPUT / "completion.json"
    completion_path.write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"runner": str(runner), "runner_sha256": sha(runner),
                      "completion": str(completion_path), "completion_sha256": sha(completion_path),
                      "checks": checks}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
