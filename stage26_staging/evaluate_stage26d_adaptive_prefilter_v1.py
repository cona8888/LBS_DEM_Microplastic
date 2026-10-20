"""Evaluate a full-ceiling fixed-fibre history with Stage26d adaptive semantics."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from stage26b_revision2_prefilter_common_v1 import load_json, sha256, write_json_exclusive
from stage26d_adaptive_common_v1 import (
    continuous_engagement_pass,
    earliest_consecutive_window,
    row_equilibrium_pass,
)


JSON_FIELDS = {
    "cell_dimensions_m", "principal_effective_stress_pa_compression_positive",
    "distinct_sand_contacts_by_fibre", "contacted_sand_body_ids_by_fibre",
    "declared_anchor_contacts_by_fibre",
}
INT_FIELDS = {
    "block", "iteration", "sand_sand_real_contact_count",
    "sand_load_bearing_particle_count_after_degree_lt2_pruning",
    "minimum_distinct_sand_contacts_per_fibre", "minimum_declared_anchor_contacts_per_fibre",
    "isolated_fibre_count", "fibre_fibre_real_interaction_count", "intraclump_real_interaction_count",
}
BOOL_FIELDS = {"unbalanced_force_defined"}


def load_history(path):
    rows = []
    with Path(path).open(newline="") as stream:
        for raw in csv.DictReader(stream):
            row = dict(raw)
            for name in JSON_FIELDS:
                row[name] = json.loads(row[name])
            for name in INT_FIELDS:
                row[name] = int(row[name])
            for name in BOOL_FIELDS:
                row[name] = row[name].lower() == "true"
            for name in set(row) - JSON_FIELDS - INT_FIELDS - BOOL_FIELDS:
                row[name] = float(row[name])
            rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--trial", required=True)
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    cfg = load_json(str(args.config))
    trial = next(row for row in cfg["trials"] if row["trial_id"] == args.trial)
    result_path = args.raw_dir / "result.json"
    completion_path = args.raw_dir / "completion.json"
    history_path = args.raw_dir / "fixed_conditioning_history.csv"
    result = load_json(str(result_path))
    completion = load_json(str(completion_path))
    if result.get("passed") is not True or completion.get("passed") is not True:
        raise RuntimeError("raw runner did not complete")
    if result["source_hashes"]["config"] != sha256(str(args.config)):
        raise RuntimeError("raw result/config binding mismatch")
    if completion["result_sha256"] != sha256(str(result_path)):
        raise RuntimeError("completion/result binding mismatch")
    if result["artifacts"]["fixed_conditioning_history_csv_sha256"] != sha256(str(history_path)):
        raise RuntimeError("history binding mismatch")
    history = load_history(history_path)
    adaptive = cfg["adaptive_equilibration"]
    if len(history) != adaptive["maximum_blocks"]:
        raise RuntimeError("history did not reach frozen resource ceiling")
    if [row["block"] for row in history] != list(range(1, adaptive["maximum_blocks"] + 1)):
        raise RuntimeError("history block sequence is incomplete")
    insertion_exact = all(value == 2 for value in result["insertion"]["distinct_sand_contacts_by_fibre"])
    engagement = continuous_engagement_pass(history, cfg["continuous_engagement_gates"])
    window = earliest_consecutive_window(
        history,
        adaptive["minimum_blocks_before_equilibrium_window"],
        adaptive["required_consecutive_passing_blocks"],
        cfg["equilibrium_window_gates"],
    )
    if trial["record_type"] == "positive_control":
        control_reproduced = insertion_exact and engagement and window is not None
        qualified = None
    elif trial["record_type"] == "negative_control":
        control_reproduced = insertion_exact and not engagement and any(row["isolated_fibre_count"] > 0 for row in history)
        qualified = None
    elif trial["record_type"] in ("development", "heldout_confirmation"):
        control_reproduced = None
        qualified = insertion_exact and engagement and window is not None
    else:
        raise RuntimeError("unexpected trial role")
    window_terminal = None if window is None else history[window[1] - 1]
    payload = {
        "schema": "lbs.stage26d-adaptive-fixed-prefilter-evaluation.v1",
        "passed": True,
        "status": "evaluated_full_ceiling_with_frozen_adaptive_gate",
        "trial": trial,
        "checks": {
            "insertion_exact": insertion_exact,
            "continuous_engagement": engagement,
            "qualifying_window_exists": window is not None,
            "known_isolation_observed": any(row["isolated_fibre_count"] > 0 for row in history),
            "all_rows_finite_and_evaluable": all(
                isinstance(row_equilibrium_pass(row, cfg["equilibrium_window_gates"]), bool)
                for row in history
            ),
        },
        "control_reproduced": control_reproduced,
        "qualified_fixed_prefilter": qualified,
        "earliest_qualifying_window_blocks": window,
        "metrics": {
            "minimum_contacts_over_all_blocks": min(min(row["distinct_sand_contacts_by_fibre"]) for row in history),
            "minimum_anchors_over_all_blocks": min(min(row["declared_anchor_contacts_by_fibre"]) for row in history),
            "passing_equilibrium_row_count": sum(row_equilibrium_pass(row, cfg["equilibrium_window_gates"]) for row in history),
            "window_terminal_mean_stress_pa": None if window_terminal is None else window_terminal["mean_effective_stress_pa_compression_positive"],
            "window_terminal_unbalanced_force": None if window_terminal is None else window_terminal["unbalanced_force"],
            "window_terminal_contact_retention": None if window_terminal is None else window_terminal["sand_sand_contact_retention_fraction"],
            "maximum_sand_displacement_over_D50": max(row["maximum_nonaffine_sand_displacement_over_D50"] for row in history),
        },
        "bindings": {
            "config_sha256": sha256(str(args.config)),
            "raw_result_sha256": sha256(str(result_path)),
            "raw_completion_sha256": sha256(str(completion_path)),
            "raw_history_sha256": sha256(str(history_path)),
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    write_json_exclusive(str(args.output), payload)
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
