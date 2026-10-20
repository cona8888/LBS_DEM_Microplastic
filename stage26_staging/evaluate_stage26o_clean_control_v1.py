#!/usr/bin/env python3
"""Independently bind and evaluate a Stage26o clean-sand control attempt."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--completion", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    cfg, result, completion = load(args.config), load(args.result), load(args.completion)
    assert result["source_hashes"]["config"] == sha(args.config)
    assert completion["result_sha256"] == sha(args.result)
    assert result["artifacts"]["history_sha256"] == sha(args.history)
    assert result["source_hashes"]["runner"] == cfg["sources"]["runner_sha256"]
    assert completion["passed"] is True and result["passed"] is True
    with args.history.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == int(result["records_written"])
    tail = rows[-min(200, len(rows)):]
    def series(name):
        return [float(row[name]) for row in tail]
    ke, ub, contacts = series("normalized_kinetic_energy_weight_D50"), series("unbalanced_force"), series("sand_sand_real_contact_count")
    terminal = result["terminal"]
    numerical_health = {
        "particle_count_exact": int(terminal["particle_count"]) == int(cfg["acceptance"]["required_particle_count"]),
        "no_leakage": int(terminal["leaked_particle_count"]) == 0,
        "penetration_below_hard_guard": float(terminal["maximum_interobject_penetration_over_smaller_radius"]) <= float(cfg["acceptance"]["hard_guard_penetration_over_smaller_radius"]),
    }
    qualified = bool(result["qualified"] and completion["qualified"])
    status_matches = result["status"] == completion["status"]
    passed = all(numerical_health.values()) and status_matches
    evaluation = {
        "schema": "lbs.stage26o-clean-sand-control-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "control_qualified": qualified,
        "status": result["status"],
        "numerical_health": numerical_health,
        "terminal": terminal,
        "tail_200_block_diagnostics": {
            "kinetic_energy_weight_D50_first": ke[0], "kinetic_energy_weight_D50_last": ke[-1],
            "kinetic_energy_weight_D50_minimum": min(ke), "kinetic_energy_weight_D50_median": statistics.median(ke),
            "unbalanced_force_first": ub[0], "unbalanced_force_last": ub[-1],
            "unbalanced_force_minimum": min(ub), "unbalanced_force_median": statistics.median(ub),
            "sand_contacts_first": contacts[0], "sand_contacts_last": contacts[-1],
            "sand_contacts_median": statistics.median(contacts),
        },
        "interpretation": (
            "The attempt is a numerically healthy but scientifically unqualified gravity-settling result. "
            "It reached the frozen physical-time ceiling before the unchanged equilibrium gates passed."
            if not qualified else
            "The clean-sand wall preparation control passed all frozen qualification gates."
        ),
        "authority": {
            "redesign_clean_control_authorized": passed and not qualified,
            "spent_development_mixture_authorized": passed and qualified,
            "heldout_execution_authorized": False,
            "flow_execution_authorized": False,
            "deformation_authorized": False,
        },
        "source_hashes": {
            "config": sha(args.config), "result": sha(args.result),
            "completion": sha(args.completion), "history": sha(args.history),
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    target = args.output_dir / "evaluation.json"
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"evaluation": str(target), "sha256": sha(target), "passed": passed, "control_qualified": qualified}, sort_keys=True))


if __name__ == "__main__":
    main()
