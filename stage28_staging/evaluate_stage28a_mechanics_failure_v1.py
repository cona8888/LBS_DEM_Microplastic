#!/usr/bin/env python3
"""Independently verify and diagnose the immutable Stage28a mechanics failure."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
RUN = ROOT / "stage28_runs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_01"
RESULT = RUN / "result.json"
COMPLETION = RUN / "completion.json"
CONFIG = ROOT / "stage28_designs/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_preflight_01/config.json"
RUNNER = ROOT / "stage28_staging/run_stage28a_two_fibre_mechanics_v1.py"
STAGE26 = ROOT / "stage26_runs/stage26x_periodic_pore_geometry_20260823/fixed_sand_pilot_02/result.json"
OUTPUT = ROOT / "stage28_evaluations/stage28a_two_fibre_mechanics_hydraulics_20260824/mechanics_evaluation_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite immutable output: {OUTPUT}")
    result = load(RESULT)
    completion = load(COMPLETION)
    config = load(CONFIG)
    stage26 = load(STAGE26)

    artifact_checks = {}
    first_hold = {}
    for case in result["cases"]:
        case_id = case["case_id"]
        record_path = RUN / case["result_artifact"]["path"]
        history_path = RUN / case["history"]["path"]
        artifact_checks[case_id + "_record"] = (
            record_path.is_file() and sha(record_path) == case["result_artifact"]["sha256"]
        )
        artifact_checks[case_id + "_history"] = (
            history_path.is_file() and sha(history_path) == case["history"]["sha256"]
        )
        with history_path.open(newline="", encoding="utf-8") as stream:
            row = next(csv.DictReader(stream))
        first_hold[case_id] = {
            "time_s": float(row["time_s"]),
            "applied_force_n": float(row["applied_pull_force_per_fibre_n"]),
            "maximum_node_displacement_m": float(row["maximum_node_displacement_m"]),
            "maximum_node_speed_m_s": float(row["maximum_node_speed_m_s"]),
            "intrafibre_contact_count": int(row["intrafibre_contact_count"]),
        }

    by_id = {case["case_id"]: case for case in result["cases"]}
    isolated_ids = ["isolated_face_14848", "isolated_face_30311", "isolated_face_30924"]
    paired_ids = ["separated_open_open", "separated_open_constricted", "crossing_interaction"]
    stage26_holds = [case["maximum_hold_drift_m"] for case in stage26["cases"]]
    path_by_face = {
        (row["case_id"], int(row["source_face_index"])): row[
            "aligned_terminal_rms_over_fibre_diameter"
        ]
        for row in result["path_match"]
    }
    checks = {
        "completion_bound_to_result": completion["result"]["sha256"] == sha(RESULT),
        "source_config_bound": result["source_hashes"]["config"] == sha(CONFIG),
        "source_runner_bound": result["source_hashes"]["runner"] == sha(RUNNER),
        "all_case_artifacts_bound": all(artifact_checks.values()),
        "expected_fail_closed_status": result["passed"] is False
        and result["status"] == "two_fibre_mechanics_not_qualified"
        and completion["passed"] is False,
        "only_two_global_gates_failed": sorted(
            name for name, passed in result["checks"].items() if not passed
        )
        == ["separated_path_match", "zero_load_hold_stable"],
        "no_force_during_first_hold_sample": all(
            row["applied_force_n"] == 0.0 for row in first_hold.values()
        ),
        "exact_67_intrafibre_contacts_per_isolated_fibre": all(
            by_id[name]["maximum_intrafibre_contact_count"] == 67 for name in isolated_ids
        ),
        "exact_additive_134_intrafibre_contacts_per_pair": all(
            by_id[name]["maximum_intrafibre_contact_count"] == 134 for name in paired_ids
        ),
        "self_contacts_present_in_first_zero_load_sample": all(
            first_hold[name]["intrafibre_contact_count"] == (67 if name in isolated_ids else 134)
            for name in isolated_ids + paired_ids
        ),
        "legacy_stage26_hold_was_exactly_stable": max(stage26_holds) == 0.0,
        "new_isolated_path_reproduces_when_same_runner_used": path_by_face[
            ("separated_open_open", 14848)
        ]
        <= 0.05,
        "legacy_controls_are_contaminated": path_by_face[("separated_open_open", 37641)]
        > 1.0
        and path_by_face[("separated_open_constricted", 37641)] > 1.0
        and path_by_face[("separated_open_constricted", 37527)] > 1.0,
        "desired_cross_fibre_contact_was_resolved": result["checks"][
            "crossing_contact_resolved"
        ]
        and by_id["crossing_interaction"]["maximum_fibre_fibre_contact_count"] >= 1,
        "no_cross_node_bond": result["checks"]["no_cross_fibre_node_bond"],
        "sand_cell_bonds_penetration_remained_healthy": all(
            result["checks"][name]
            for name in (
                "finite_bond_complete",
                "fixed_periodic_cell_exact",
                "fixed_sand_exact",
                "penetration_guard",
            )
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(
            "independent failure diagnosis did not verify: "
            + ", ".join(name for name, value in checks.items() if not value)
        )

    evaluation = {
        "schema": "lbs.stage28a-two-fibre-mechanics-failure-evaluation.v1",
        "status": "verified_implementation_artifact_revision_required",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "checks": checks,
        "artifact_checks": artifact_checks,
        "first_hold_samples": first_hold,
        "diagnosis": {
            "plain_language": (
                "The new segment-to-segment contact law also made neighbouring segments "
                "within each single fibre repel one another. Each isolated fibre therefore "
                "started with 67 false self-contacts before any pull force was applied."
            ),
            "mechanical_consequence": (
                "The false self-contact forces displaced the fibre by roughly 0.27-0.33 mm "
                "during the nominal hold, corrupting comparisons with the accepted Stage26 "
                "single-fibre controls."
            ),
            "not_a_yade_fundamental_limit": True,
            "required_revision": (
                "Erase or suppress same-fibre GridConnection-GridConnection interactions "
                "before the contact law is evaluated while preserving cross-fibre contacts."
            ),
        },
        "bindings": {
            "result_sha256": sha(RESULT),
            "completion_sha256": sha(COMPLETION),
            "config_sha256": sha(CONFIG),
            "runner_sha256": sha(RUNNER),
            "stage26_result_sha256": sha(STAGE26),
        },
        "authority": {
            "implementation_revision_and_unit_test": True,
            "mechanics_rerun": False,
            "gpu_execution": False,
            "hydraulic_geometry_design": False,
        },
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "evaluation.json"
    path.write_text(json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"evaluation": str(path), "sha256": sha(path), "checks": checks}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
