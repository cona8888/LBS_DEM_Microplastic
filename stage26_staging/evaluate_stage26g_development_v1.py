#!/usr/bin/env python3
"""Fail-closed evaluation of the Stage26g fresh-cage development runs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def write_exclusive_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")


def parse_rows(path: Path):
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        for key in (
            "block",
            "isolated_fibre_count",
            "fibre_fibre_real_interaction_count",
            "intraclump_real_interaction_count",
        ):
            row[key] = int(row[key])
        for key in (
            "cell_volume_relative_drift",
            "maximum_principal_stress_error",
            "relative_mean_stress_error",
            "maximum_interobject_penetration_over_smaller_radius",
            "maximum_nonaffine_sand_displacement_over_D50",
            "sand_rattler_fraction_degree_lt2_iterative",
            "unbalanced_force",
            "sand_sand_contact_retention_fraction",
            "sand_coordination_excluding_degree_lt2_rattlers",
            "mean_effective_stress_pa_compression_positive",
        ):
            row[key] = float(row[key])
        for key in (
            "distinct_sand_contacts_by_fibre",
            "declared_support_contacts_by_fibre",
        ):
            row[key] = json.loads(row[key])
    return rows


def window_pass(row, gates) -> bool:
    checks = (
        row["cell_volume_relative_drift"] <= gates["maximum_cell_volume_relative_drift"],
        row["fibre_fibre_real_interaction_count"] <= gates["maximum_fibre_fibre_real_interaction_count"],
        row["maximum_interobject_penetration_over_smaller_radius"] <= gates["maximum_interobject_penetration_over_smaller_radius"],
        row["intraclump_real_interaction_count"] <= gates["maximum_intraclump_real_interaction_count"],
        row["maximum_principal_stress_error"] <= gates["maximum_principal_stress_error"],
        row["relative_mean_stress_error"] <= gates["maximum_relative_mean_stress_error"],
        row["maximum_nonaffine_sand_displacement_over_D50"] <= gates["maximum_sand_displacement_over_D50"],
        row["sand_rattler_fraction_degree_lt2_iterative"] <= gates["maximum_sand_rattler_fraction"],
        row["unbalanced_force"] <= gates["maximum_unbalanced_force"],
        min(row["declared_support_contacts_by_fibre"]) >= gates["minimum_declared_support_contacts_per_fibre"],
        min(row["distinct_sand_contacts_by_fibre"]) >= gates["minimum_distinct_sand_contacts_per_fibre"],
        row["sand_sand_contact_retention_fraction"] >= gates["minimum_sand_contact_retention_fraction"],
        row["sand_coordination_excluding_degree_lt2_rattlers"] >= gates["minimum_sand_coordination_excluding_rattlers"],
    )
    return all(checks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design-dir", type=Path, required=True)
    parser.add_argument("--runs-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    resolved_path = args.design_dir / "resolved_design.json"
    execution_path = args.design_dir / "development_execution.json"
    manifest_path = args.design_dir / "design_manifest.json"
    resolved = load_json(resolved_path)
    execution = load_json(execution_path)
    manifest = load_json(manifest_path)

    assert resolved["schema"] == "lbs.stage26g-fresh-cage-fixed-fibre-qualification-design.v2"
    assert execution["schema"] == "lbs.stage26g-development-fixed-cage-capture-execution.v2"
    assert execution["authority"]["heldout_execution_authorized"] is False
    assert execution["authority"]["two_fibre_free_release_authorized"] is False
    assert execution["authority"]["flow_execution_authorized"] is False
    assert resolved["allocation"]["development"] == [6, 7, 8]
    assert resolved["development_acceptance"]["required_qualified_cases"] == 2

    gates = resolved["equilibrium_window_gates"]
    engagement = resolved["engagement_gates"]
    minimum_block = resolved["temporal_protocol"]["minimum_blocks_before_window"]
    required_consecutive = resolved["temporal_protocol"]["required_consecutive_passing_blocks"]
    expected_config_hash = sha256(execution_path)
    expected_runner_hash = execution["sources"]["capture_runner_sha256"]

    case_evaluations = []
    qualified_count = 0
    for trial in execution["trials"]:
        case_dir = args.runs_dir / f"stage26f_cage_candidate_{trial['candidate_index']:02d}"
        completion_path = case_dir / "completion.json"
        result_path = case_dir / "result.json"
        history_path = case_dir / "fixed_capture_history.csv"
        assert case_dir.is_dir()
        assert not (case_dir / "failure.json").exists()
        for path in (completion_path, result_path, history_path):
            assert path.is_file(), path

        completion = load_json(completion_path)
        result = load_json(result_path)
        rows = parse_rows(history_path)
        assert completion["passed"] is True
        assert result["passed"] is True
        assert completion["result_sha256"] == sha256(result_path)
        assert result["artifacts"]["history_sha256"] == sha256(history_path)
        assert result["source_hashes"]["config"] == expected_config_hash
        assert result["source_hashes"]["runner"] == expected_runner_hash
        assert result["trial"]["trial_id"] == trial["trial_id"]
        assert result["trial"]["placement_sha256"] == trial["placement_sha256"]
        assert result["protocol"]["all_fibres_fixed"] is True
        assert result["protocol"]["free_release"] is False
        assert result["protocol"]["blocks_executed"] == len(rows)
        assert result["insertion"]["distinct_sand_contacts_by_fibre"] == [4, 4]
        assert result["insertion"]["declared_support_contacts_by_fibre"] == [4, 4]
        assert result["insertion"]["isolated_fibre_count"] == 0
        assert result["insertion"]["fibre_fibre_real_interaction_count"] == 0
        assert result["insertion"]["intraclump_real_interaction_count"] == 0
        assert result["artifacts"]["state_sha256"] is None
        assert completion["state_sha256"] is None

        violations = []
        streak = 0
        max_streak = 0
        for row in rows:
            engaged = (
                min(row["distinct_sand_contacts_by_fibre"]) >= engagement["minimum_distinct_sand_contacts_per_fibre_at_every_block"]
                and min(row["declared_support_contacts_by_fibre"]) >= engagement["minimum_declared_support_contacts_per_fibre_at_every_block"]
                and row["isolated_fibre_count"] <= engagement["maximum_isolated_fibre_count_at_every_block"]
            )
            if not engaged:
                violations.append(row["block"])
            if row["block"] >= minimum_block and engaged and window_pass(row, gates):
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0

        qualified = bool(result["qualified_fixed_state_captured"])
        qualified_count += int(qualified)
        assert qualified == (max_streak >= required_consecutive)
        assert completion["qualified_fixed_state_captured"] == qualified
        assert result["status"] == "no_qualifying_state_captured"
        assert violations and violations[0] == rows[-1]["block"]

        case_evaluations.append(
            {
                "candidate_index": trial["candidate_index"],
                "trial_id": trial["trial_id"],
                "blocks_executed": len(rows),
                "eligible_minimum_block_reached": rows[-1]["block"] >= minimum_block,
                "first_continuous_engagement_violation_block": violations[0],
                "terminal_distinct_contacts_by_fibre": rows[-1]["distinct_sand_contacts_by_fibre"],
                "terminal_declared_supports_by_fibre": rows[-1]["declared_support_contacts_by_fibre"],
                "minimum_contacts_observed": min(min(r["distinct_sand_contacts_by_fibre"]) for r in rows),
                "minimum_declared_supports_observed": min(min(r["declared_support_contacts_by_fibre"]) for r in rows),
                "maximum_eligible_window_streak": max_streak,
                "qualified_fixed_state_captured": qualified,
                "completion_sha256": sha256(completion_path),
                "result_sha256": sha256(result_path),
                "history_sha256": sha256(history_path),
                "failure_absent": True,
            }
        )

    required = resolved["development_acceptance"]["required_qualified_cases"]
    development_passed = qualified_count >= required
    assert development_passed is False
    heldout_root = args.runs_dir.parent / "heldout_01"
    assert not heldout_root.exists()

    evaluation = {
        "schema": "lbs.stage26g-development-fixed-cage-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "development_gate_failed_heldout_locked",
        "development_acceptance_passed": False,
        "qualified_cases": qualified_count,
        "required_qualified_cases": required,
        "heldout_execution_authorized": False,
        "heldout_execution_absent": True,
        "case_evaluations": case_evaluations,
        "finding": (
            "All three fresh four-support cages had exact [4,4] insertion contact/support counts, "
            "but every case lost the continuous two-support-per-fibre engagement gate before block 60. "
            "Static cage rank and conditioning therefore did not provide persistent fixed-fibre support "
            "during sand stress equilibration."
        ),
        "failure_classification": "physical_qualification_failure_not_software_failure",
        "authority": {
            "heldout_execution_authorized": False,
            "free_release_authorized": False,
            "flow_execution_authorized": False,
            "deformation_authorized": False,
            "production_parametric_study_authorized": False,
        },
        "source_hashes": {
            "resolved_design": sha256(resolved_path),
            "development_execution": sha256(execution_path),
            "design_manifest": sha256(manifest_path),
            "evaluator": sha256(Path(__file__)),
        },
        "claim_boundary": resolved["claim_boundary"],
    }
    write_exclusive_json(args.output_dir / "evaluation.json", evaluation)
    print(json.dumps({"output": str(args.output_dir / 'evaluation.json'), "status": evaluation["status"]}, sort_keys=True))


if __name__ == "__main__":
    main()
