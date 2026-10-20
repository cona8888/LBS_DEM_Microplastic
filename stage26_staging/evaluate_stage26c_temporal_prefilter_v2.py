"""Evaluate one immutable Stage26c raw fixed-fibre history under temporal gate v2."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from stage26c_prefilter_common_v2 import (
    known_negative_reproduced,
    load_json,
    sand_terminal_pass,
    sha256,
    temporal_contact_pass,
    write_json_exclusive,
)


JSON_FIELDS = {
    "distinct_sand_contacts_by_fibre",
    "declared_anchor_contacts_by_fibre",
}


def load_history(path: Path):
    rows = []
    with path.open("r", newline="") as stream:
        for raw in csv.DictReader(stream):
            row = dict(raw)
            for name in JSON_FIELDS:
                row[name] = json.loads(row[name])
            row["block"] = int(row["block"])
            row["isolated_fibre_count"] = int(row["isolated_fibre_count"])
            rows.append(row)
    return rows


def evaluate(config_path: Path, trial_id: str, raw_dir: Path, output: Path):
    cfg = load_json(str(config_path))
    trial = next(row for row in cfg["trials"] if row["trial_id"] == trial_id)
    result_path = raw_dir / "result.json"
    completion_path = raw_dir / "completion.json"
    history_path = raw_dir / "fixed_conditioning_history.csv"
    result = load_json(str(result_path))
    completion = load_json(str(completion_path))
    if result.get("passed") is not True or completion.get("passed") is not True:
        raise RuntimeError("raw fixed-prefilter run did not complete")
    if result["source_hashes"]["config"] != sha256(str(config_path)):
        raise RuntimeError("raw result is not bound to supplied execution config")
    if result["artifacts"]["fixed_conditioning_history_csv_sha256"] != sha256(str(history_path)):
        raise RuntimeError("raw history hash mismatch")
    if completion["result_sha256"] != sha256(str(result_path)):
        raise RuntimeError("raw completion-to-result binding mismatch")
    history = load_history(history_path)
    if len(history) != int(cfg["temporal_contact_gates"]["required_blocks"]):
        raise RuntimeError("raw history has wrong block count")
    insertion_exact = all(
        int(value) == int(cfg["insertion_gate"]["required_exact_contacts_per_fibre"])
        for value in result["insertion"]["distinct_sand_contacts_by_fibre"]
    )
    temporal_pass = temporal_contact_pass(history, cfg["temporal_contact_gates"])
    sand_pass = sand_terminal_pass(result["terminal"], cfg["sand_health_gates_at_terminal_block"])
    no_forbidden_contacts = (
        int(result["terminal"]["fibre_fibre_real_interaction_count"]) == 0
        and int(result["terminal"]["intraclump_real_interaction_count"]) == 0
    )
    if trial["record_type"] == "control" and trial_id == "positive_stage26a":
        control_reproduced = insertion_exact and temporal_pass and sand_pass and no_forbidden_contacts
        candidate_passed = None
    elif trial["record_type"] == "control" and trial_id == "negative_stage26b_failure":
        control_reproduced = insertion_exact and known_negative_reproduced(history)
        candidate_passed = None
    elif trial["record_type"] == "candidate":
        control_reproduced = None
        candidate_passed = insertion_exact and temporal_pass and sand_pass and no_forbidden_contacts
    else:
        raise RuntimeError("unexpected trial role")
    payload = {
        "schema": "lbs.stage26c-temporal-prefilter-evaluation.v2",
        "passed": True,
        "status": "evaluated_fixed_prefilter_temporal_gate_v2",
        "trial": trial,
        "checks": {
            "insertion_exact": insertion_exact,
            "temporal_contact_gate": temporal_pass,
            "terminal_sand_health": sand_pass,
            "no_fibre_fibre_or_intraclump_contacts": no_forbidden_contacts,
            "known_negative_isolation_observed": known_negative_reproduced(history),
        },
        "control_reproduced": control_reproduced,
        "candidate_passed_prefilter": candidate_passed,
        "metrics": {
            "minimum_contacts_all_blocks": min(min(row["distinct_sand_contacts_by_fibre"]) for row in history),
            "minimum_contacts_terminal_window": min(
                min(row["distinct_sand_contacts_by_fibre"])
                for row in history
                if int(row["block"]) >= int(cfg["temporal_contact_gates"]["terminal_window_blocks_inclusive"][0])
            ),
            "minimum_anchors_terminal_window": min(
                min(row["declared_anchor_contacts_by_fibre"])
                for row in history
                if int(row["block"]) >= int(cfg["temporal_contact_gates"]["terminal_window_blocks_inclusive"][0])
            ),
            "terminal_mean_stress_pa": result["terminal"]["mean_effective_stress_pa_compression_positive"],
            "terminal_unbalanced_force": result["terminal"]["unbalanced_force"],
            "maximum_sand_displacement_over_D50": result["prefilter_summary"]["maximum_sand_displacement_over_D50"],
        },
        "bindings": {
            "config_sha256": sha256(str(config_path)),
            "raw_result_sha256": sha256(str(result_path)),
            "raw_completion_sha256": sha256(str(completion_path)),
            "raw_history_sha256": sha256(str(history_path)),
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    write_json_exclusive(str(output), payload)
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--trial", required=True)
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = evaluate(args.config.resolve(), args.trial, args.raw_dir.resolve(), args.output.resolve())
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
