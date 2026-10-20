"""Independently evaluate the one-shot Stage26e held-out capture outcome."""

import argparse
import json
from pathlib import Path

from evaluate_stage26d_adaptive_prefilter_v1 import load_history
from stage26b_revision2_prefilter_common_v1 import load_json, sha256, write_json_exclusive
from stage26d_adaptive_common_v1 import continuous_engagement_pass, earliest_consecutive_window, row_equilibrium_pass


def longest_streak(rows, minimum_block, gates):
    current, best = [], []
    for row in rows:
        if row["block"] < minimum_block:
            continue
        current = current + [row["block"]] if row_equilibrium_pass(row, gates) else []
        if len(current) > len(best):
            best = list(current)
    return None if not best else [best[0], best[-1], len(best)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cfg = load_json(str(args.config))
    result_path = args.run_dir / "result.json"
    completion_path = args.run_dir / "completion.json"
    history_path = args.run_dir / "fixed_capture_history.csv"
    result = load_json(str(result_path))
    completion = load_json(str(completion_path))
    rows = load_history(history_path)
    assert result["passed"] is True and completion["passed"] is True
    assert result["trial"]["stage26e_role"] == "heldout_capture"
    assert result["source_hashes"]["config"] == sha256(str(args.config))
    assert result["artifacts"]["history_sha256"] == sha256(str(history_path))
    assert completion["result_sha256"] == sha256(str(result_path))
    assert len(rows) == 300 and [row["block"] for row in rows] == list(range(1, 301))
    assert not (args.run_dir / "qualified_fixed_state.yade.gz").exists()
    adaptive = cfg["adaptive_equilibration"]
    gates = cfg["equilibrium_window_gates"]
    engagement = continuous_engagement_pass(rows, cfg["continuous_engagement_gates"])
    window = earliest_consecutive_window(
        rows,
        adaptive["minimum_blocks_before_equilibrium_window"],
        adaptive["required_consecutive_passing_blocks"],
        gates,
    )
    evaluation = {
        "schema": "lbs.stage26e-heldout-capture-evaluation.v1",
        "passed": True,
        "status": "evaluated_one_shot_heldout_capture_failure",
        "heldout_capture_qualified": False,
        "checks": {
            "exact_two_contact_insertion": all(
                value == 2 for value in result["insertion"]["distinct_sand_contacts_by_fibre"]
            ),
            "full_resource_ceiling_reached": len(rows) == adaptive["maximum_blocks"],
            "continuous_engagement": engagement,
            "qualifying_window_absent": window is None,
            "state_file_absent": not (args.run_dir / "qualified_fixed_state.yade.gz").exists(),
            "free_release_false": result["protocol"]["free_release"] is False,
        },
        "metrics": {
            "earliest_qualifying_window": window,
            "longest_passing_streak_after_minimum_block": longest_streak(
                rows, adaptive["minimum_blocks_before_equilibrium_window"], gates
            ),
            "passing_equilibrium_row_count": sum(row_equilibrium_pass(row, gates) for row in rows),
            "minimum_contacts_over_all_blocks": min(
                min(row["distinct_sand_contacts_by_fibre"]) for row in rows
            ),
            "minimum_anchors_over_all_blocks": min(
                min(row["declared_anchor_contacts_by_fibre"]) for row in rows
            ),
            "terminal_mean_stress_pa": rows[-1]["mean_effective_stress_pa_compression_positive"],
            "terminal_unbalanced_force": rows[-1]["unbalanced_force"],
            "terminal_contact_retention": rows[-1]["sand_sand_contact_retention_fraction"],
            "maximum_sand_displacement_over_D50": max(
                row["maximum_nonaffine_sand_displacement_over_D50"] for row in rows
            ),
        },
        "failure_classification": (
            "predeclared held-out non-equilibration at the 300-block resource ceiling; "
            "no rerun, retuning, saved state, reload, or release is authorized"
        ),
        "bindings": {
            "config_sha256": sha256(str(args.config)),
            "result_sha256": sha256(str(result_path)),
            "completion_sha256": sha256(str(completion_path)),
            "history_sha256": sha256(str(history_path)),
        },
        "authority": {
            "stage26e_failure_freeze_authorized": True,
            "candidate07_rerun_authorized": False,
            "candidate08_execution_authorized": False,
            "rehydration_execution_authorized": False,
            "free_release_authorized": False,
            "flow_execution_authorized": False,
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    assert all(evaluation["checks"].values())
    write_json_exclusive(str(args.output), evaluation)
    print(json.dumps(evaluation, sort_keys=True))


if __name__ == "__main__":
    main()
