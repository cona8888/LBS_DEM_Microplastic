#!/usr/bin/env python3
"""Fail-closed evaluation of the Stage26j joint sand-growth screen."""

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


def load(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--runs-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    config = load(args.config)
    assert config["schema"] == "lbs.stage26j-joint-sand-growth-development-screen-config.v1"
    assert config["research_role"] == "specimen_preparation_development_screen_not_validation"
    assert config["authority"]["heldout_execution_authorized"] is False
    assert config["authority"]["reserve_execution_authorized"] is False
    assert config["authority"]["flow_execution_authorized"] is False
    assert config["authority"]["temporary_fibre_radius_authorized"] is False
    config_hash = sha256(args.config)
    cases = []
    for trial in sorted(config["trials"], key=lambda row: row["execution_order"]):
        case_dir = args.runs_dir / trial["trial_id"]
        result_path = case_dir / "result.json"
        completion_path = case_dir / "completion.json"
        history_path = case_dir / "joint_growth_history.csv"
        assert case_dir.is_dir() and not (case_dir / "failure.json").exists()
        result = load(result_path)
        completion = load(completion_path)
        assert result["passed"] is True and completion["passed"] is True
        assert result["trial"] == trial
        assert result["source_hashes"]["config"] == config_hash
        assert result["source_hashes"]["runner"] == config["sources"]["runner_sha256"]
        assert result["source_hashes"]["placement"] == trial["placement_sha256"]
        assert completion["result_sha256"] == sha256(result_path)
        assert result["artifacts"]["history_sha256"] == sha256(history_path)
        assert result["final_sand_radii_restored_exactly"] is True
        assert result["exact_geometry_fixed_hold_qualified"] is False
        assert result["qualified_state_captured"] is False
        assert result["artifacts"]["state_sha256"] is None
        assert completion["state_sha256"] is None
        with history_path.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == result["blocks_executed"] == 160
        terminal = result["terminal_row"]
        assert json.loads(rows[-1]["distinct_sand_contacts_by_fibre"]) == terminal["distinct_sand_contacts_by_fibre"]
        assert abs(float(rows[-1]["temporary_sand_radius_scale"]) - 1.0) <= 1e-15
        cases.append({
            "trial_id": trial["trial_id"],
            "initial_sand_radius_shrink_percent": trial["initial_sand_radius_shrink_percent"],
            "status": result["status"],
            "qualified": False,
            "final_sand_radii_restored_exactly": True,
            "terminal_mean_effective_stress_pa": terminal["mean_effective_stress_pa_compression_positive"],
            "terminal_sand_contact_count": terminal["sand_sand_real_contact_count"],
            "terminal_contact_retention_fraction": terminal["sand_sand_contact_retention_fraction"],
            "terminal_coordination_excluding_rattlers": terminal["sand_coordination_excluding_degree_lt2_rattlers"],
            "terminal_rattler_fraction": terminal["sand_rattler_fraction_degree_lt2_iterative"],
            "terminal_fibre_contacts": terminal["distinct_sand_contacts_by_fibre"],
            "terminal_declared_supports": terminal["declared_support_contacts_by_fibre"],
            "terminal_unbalanced_force": terminal["unbalanced_force"],
            "terminal_maximum_sand_displacement_over_D50": terminal["maximum_nonaffine_sand_displacement_over_D50"],
            "result_sha256": sha256(result_path),
            "completion_sha256": sha256(completion_path),
            "history_sha256": sha256(history_path),
            "failure_absent": True,
        })
    assert [round(row["initial_sand_radius_shrink_percent"], 8) for row in cases] == [1.0, 2.0]
    assert [row["terminal_sand_contact_count"] for row in cases] == [134, 237]
    assert [row["terminal_fibre_contacts"] for row in cases] == [[2, 2], [1, 1]]

    args.output_dir.mkdir(parents=True, exist_ok=False)
    evaluation = {
        "schema": "lbs.stage26j-joint-sand-growth-development-screen-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "development_screen_completed_no_exact_geometry_success",
        "screen_success": False,
        "case_evaluations": cases,
        "finding": (
            "Both predeclared sand-shrink levels restored exact particle radii but failed to recover the "
            "100 Pa load-bearing fabric or at least three contacts per fibre."
        ),
        "mechanical_interpretation": (
            "Uniformly shrinking the already equilibrated sand deletes most of its contact network. Slow "
            "radius restoration alone does not preserve the original force-chain topology around the exact fibre."
        ),
        "next_mechanics_hypothesis": (
            "Generate and consolidate the sand-fibre mixture together from an initially loose state, with exact "
            "final fibre geometry present throughout, rather than editing an equilibrated pure-sand packing."
        ),
        "authority": {
            "heldout_execution_authorized": False,
            "reserve_execution_authorized": False,
            "flow_execution_authorized": False,
            "deformation_authorized": False,
        },
        "source_hashes": {"config": config_hash, "evaluator": sha256(Path(__file__))},
        "claim_boundary": config["claim_boundary"],
    }
    output = args.output_dir / "evaluation.json"
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"evaluation": str(output), "evaluation_sha256": sha256(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
