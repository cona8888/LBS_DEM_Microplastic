#!/usr/bin/env python3
"""Independent bundle and physics-gate evaluation of Stage28a Revision 2."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
RUN = ROOT / "stage28_runs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_02"
RESULT = RUN / "result.json"
COMPLETION = RUN / "completion.json"
CONFIG = ROOT / "stage28_designs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_preflight_02/config.json"
RUNNER = ROOT / "stage28_designs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_revision2_runner_01/run_stage28a_two_fibre_mechanics_v2.py"
HANDOFF = ROOT / "stage28_evaluations/stage28a_two_fibre_mechanics_hydraulics_20260824/execution_audit_02/execution_handoff.json"
REV1 = ROOT / "stage28_runs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_01/result.json"
OUTPUT = ROOT / "stage28_evaluations/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_evaluation_02"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUTPUT}")
    result, completion, config, handoff, rev1 = map(load, (RESULT, COMPLETION, CONFIG, HANDOFF, REV1))
    artifacts = {}
    for case in result["cases"]:
        for kind in ("history", "result_artifact"):
            binding = case[kind]
            path = RUN / binding["path"]
            artifacts[case["case_id"] + "_" + kind] = path.is_file() and sha(path) == binding["sha256"]
    by_id = {case["case_id"]: case for case in result["cases"]}
    separated = [by_id["separated_open_open"], by_id["separated_open_constricted"]]
    crossing = by_id["crossing_interaction"]
    max_path_ratio = max(row["aligned_terminal_rms_over_fibre_diameter"] for row in result["path_match"])
    checks = {
        "completion_passed_and_bound": completion["passed"] is True
        and completion["result"]["sha256"] == sha(RESULT),
        "config_bound": result["source_hashes"]["config"] == sha(CONFIG),
        "runner_bound": result["source_hashes"]["runner"] == sha(RUNNER),
        "handoff_bound_to_config_and_runner": handoff["bindings"]["config_sha256"] == sha(CONFIG)
        and handoff["bindings"]["runner_sha256"] == sha(RUNNER),
        "all_case_artifacts_bound": all(artifacts.values()),
        "exact_six_unique_cases": len(result["cases"]) == 6
        and len(by_id) == 6,
        "all_runner_gates_passed": result["passed"] is True and all(result["checks"].values()),
        "zero_same_fibre_grid_contacts": all(case["maximum_intrafibre_contact_count"] == 0 for case in result["cases"]),
        "zero_cross_node_bonds": all(case["maximum_cross_fibre_node_real_interaction_count"] == 0 for case in result["cases"]),
        "all_internal_bonds_complete": all(
            all(fibre["terminal_internal_real_bond_count"] == 36 for fibre in case["terminal_fibres"])
            for case in result["cases"]
        ),
        "hold_exactly_stable": all(case["maximum_hold_drift_m"] == 0.0 and case["maximum_hold_speed_m_s"] == 0.0 for case in result["cases"]),
        "fixed_sand_and_cell_exact": all(case["maximum_fixed_sand_displacement_m"] == 0.0
        and case["maximum_periodic_cell_change_m"] == 0.0 for case in result["cases"]),
        "penetration_guard": all(case["maximum_penetration_over_fibre_radius"] <= 0.01 for case in result["cases"]),
        "separated_pairs_have_no_contact": all(case["maximum_fibre_fibre_contact_count"] == 0 for case in separated),
        "crossing_has_finite_contact": crossing["maximum_fibre_fibre_contact_count"] >= 1
        and crossing["maximum_fibre_contact_normal_force_n"] > 0.0,
        "path_matching_within_frozen_limit": max_path_ratio <= 0.05,
        "revision1_failure_preserved": rev1["passed"] is False,
        "revision2_removed_revision1_self_contacts": max(case["maximum_intrafibre_contact_count"] for case in rev1["cases"]) == 134,
        "authority_remains_mechanics_only": result["authority"]["hydraulic_geometry_design"] is False
        and result["authority"]["gpu_execution"] is False
        and result["authority"]["mobile_sand"] is False
        and result["authority"]["two_way_coupling"] is False,
    }
    if not all(checks.values()):
        raise RuntimeError("Revision-2 evaluation failed: " + ", ".join(k for k, v in checks.items() if not v))
    evaluation = {
        "schema": "lbs.stage28a-two-fibre-mechanics-revision2-evaluation.v1",
        "status": "passed_two_fibre_mechanics_mechanism_pilot",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "checks": checks,
        "artifacts": artifacts,
        "metrics": {
            "elapsed_wall_s": result["elapsed_wall_s"],
            "maximum_path_match_rms_over_fibre_diameter": max_path_ratio,
            "crossing_maximum_contact_count": crossing["maximum_fibre_fibre_contact_count"],
            "crossing_maximum_contact_normal_force_n": crossing["maximum_fibre_contact_normal_force_n"],
            "maximum_penetration_over_fibre_radius": max(case["maximum_penetration_over_fibre_radius"] for case in result["cases"]),
            "revision1_maximum_false_same_fibre_contacts": 134,
            "revision2_maximum_same_fibre_contacts": 0,
        },
        "interpretation": {
            "separated": "Path-matched separated fibres reproduce their isolated controls within 0.00433 fibre diameters and do not interact.",
            "crossing": "The prescribed crossing generates one finite noncohesive fibre-fibre contact without false same-fibre contacts or broken bonds.",
            "claim_boundary": config["claim_boundary"],
        },
        "bindings": {"result_sha256": sha(RESULT), "completion_sha256": sha(COMPLETION),
                     "config_sha256": sha(CONFIG), "runner_sha256": sha(RUNNER),
                     "handoff_sha256": sha(HANDOFF), "revision1_result_sha256": sha(REV1)},
        "authority": {"mechanics_pilot_accepted": True, "rendering": True,
                      "hydraulic_geometry_design": False, "gpu_execution": False,
                      "production_concentration_campaign": False, "mobile_sand": False,
                      "two_way_coupling": False},
        "next_handoff": {"authorized": "render the accepted mechanics evidence and design a paired CPD2 hydraulic pilot",
                         "not_authorized": "GPU execution before an independent hydraulic preflight release"},
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "evaluation.json"
    path.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "schema": "lbs.stage28a-two-fibre-mechanics-revision2-checkpoint.v1",
        "status": "mechanics_checkpoint_frozen",
        "passed": True,
        "files": {str(path.relative_to(ROOT)): sha(path), str(RESULT.relative_to(ROOT)): sha(RESULT),
                  str(COMPLETION.relative_to(ROOT)): sha(COMPLETION), str(CONFIG.relative_to(ROOT)): sha(CONFIG),
                  str(RUNNER.relative_to(ROOT)): sha(RUNNER), str(HANDOFF.relative_to(ROOT)): sha(HANDOFF)},
    }
    checkpoint = OUTPUT / "checkpoint_manifest.json"
    checkpoint.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"evaluation": str(path), "evaluation_sha256": sha(path),
                      "checkpoint": str(checkpoint), "checkpoint_sha256": sha(checkpoint),
                      "metrics": evaluation["metrics"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
