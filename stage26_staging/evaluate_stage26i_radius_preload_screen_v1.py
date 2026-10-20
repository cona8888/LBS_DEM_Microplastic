#!/usr/bin/env python3
"""Fail-closed evaluation of the Stage26i three-level preload screen."""

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
    assert config["research_role"] == "preparation_parameter_development_screen_not_validation"
    assert config["authority"]["heldout_execution_authorized"] is False
    assert config["authority"]["reserve_execution_authorized"] is False
    evaluations = []
    successful = []
    for trial in sorted(config["trials"], key=lambda row: row["execution_order"]):
        case_dir = args.runs_dir / trial["trial_id"]
        completion_path = case_dir / "completion.json"
        result_path = case_dir / "result.json"
        history_path = case_dir / "preload_history.csv"
        assert case_dir.is_dir() and not (case_dir / "failure.json").exists()
        completion = load(completion_path)
        result = load(result_path)
        assert completion["passed"] is True and result["passed"] is True
        assert completion["result_sha256"] == sha256(result_path)
        assert result["artifacts"]["history_sha256"] == sha256(history_path)
        assert result["source_hashes"]["config"] == sha256(args.config)
        assert result["source_hashes"]["runner"] == config["sources"]["runner_sha256"]
        assert result["source_hashes"]["placement"] == trial["placement_sha256"]
        assert result["trial"] == trial
        assert result["insertion"]["distinct_sand_contacts_by_fibre"] == [4, 4]
        assert result["insertion"]["declared_support_contacts_by_fibre"] == [4, 4]
        assert result["final_geometry_fixed_validation_qualified"] is False
        assert result["qualified_state_captured"] is False
        assert result["artifacts"]["state_sha256"] is None
        assert completion["state_sha256"] is None
        with history_path.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == result["blocks_executed"]
        terminal_contacts = json.loads(rows[-1]["distinct_sand_contacts_by_fibre"])
        assert terminal_contacts == result["terminal_row"]["distinct_sand_contacts_by_fibre"]
        success = bool(result["final_geometry_fixed_validation_qualified"])
        if success:
            successful.append(trial["temporary_radius_increase_percent"])
        evaluations.append({
            "trial_id": trial["trial_id"],
            "temporary_radius_increase_percent": trial["temporary_radius_increase_percent"],
            "blocks_executed": result["blocks_executed"],
            "status": result["status"],
            "inflated_hold_qualified": result["inflated_hold_qualified"],
            "final_radius_restored_exactly": result["final_radius_restored_exactly"],
            "final_geometry_fixed_validation_qualified": success,
            "terminal_phase": result["terminal_row"]["phase"],
            "terminal_contacts_by_fibre": terminal_contacts,
            "terminal_radius_scale": result["terminal_row"]["temporary_fibre_radius_scale"],
            "result_sha256": sha256(result_path),
            "completion_sha256": sha256(completion_path),
            "history_sha256": sha256(history_path),
            "failure_absent": True,
        })
    assert successful == []
    expected = {
        "candidate07_preload_1.0pct": (False, "inflated_hold_guard_failed", [1, 4]),
        "candidate07_preload_0.5pct": (True, "deflation_ramp_guard_failed", [1, 1]),
        "candidate07_preload_1.5pct": (True, "deflation_ramp_guard_failed", [1, 3]),
    }
    for row in evaluations:
        inflated, status, contacts = expected[row["trial_id"]]
        assert row["inflated_hold_qualified"] is inflated
        assert row["status"] == status
        assert row["terminal_contacts_by_fibre"] == contacts

    args.output_dir.mkdir(parents=True, exist_ok=False)
    evaluation = {
        "schema": "lbs.stage26i-radius-preload-development-screen-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "development_screen_completed_no_final_geometry_success",
        "screen_success": False,
        "successful_radius_increase_percent": [],
        "case_evaluations": evaluations,
        "finding": (
            "Temporary radius expansion can support an inflated equilibrium state at 0.5% and 1.5%, "
            "but contacts collapse during radius restoration. The 1.0% case loses support even before "
            "restoration. No tested amplitude yields a qualified exact-final-geometry state."
        ),
        "mechanical_interpretation": (
            "The stable cage depends on the artificial expanded contact geometry rather than a self-sustaining "
            "sand fabric. Radius expansion is therefore unsuitable as the final preparation mechanism here."
        ),
        "next_mechanics_hypothesis": (
            "Generate the sand and fibres jointly during compaction so the load-bearing sand fabric forms around "
            "the exact final fibre surface instead of removing a temporary geometric support."
        ),
        "authority": {
            "heldout_execution_authorized": False,
            "reserve_execution_authorized": False,
            "flow_execution_authorized": False,
            "deformation_authorized": False,
        },
        "source_hashes": {
            "config": sha256(args.config),
            "evaluator": sha256(Path(__file__)),
        },
        "claim_boundary": config["claim_boundary"],
    }
    output = args.output_dir / "evaluation.json"
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"evaluation": str(output), "evaluation_sha256": sha256(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
