#!/usr/bin/env python3
"""Verify and freeze the Stage26h bounded-conditioning pilot result."""

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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    config = load_json(args.config)
    result_path = args.run_dir / "result.json"
    completion_path = args.run_dir / "completion.json"
    history_path = args.run_dir / "conditioning_history.csv"
    result = load_json(result_path)
    completion = load_json(completion_path)
    assert not (args.run_dir / "failure.json").exists()
    assert completion["passed"] is True and result["passed"] is True
    assert completion["result_sha256"] == sha256(result_path)
    assert result["artifacts"]["history_sha256"] == sha256(history_path)
    assert result["source_hashes"]["config"] == sha256(args.config)
    assert result["source_hashes"]["runner"] == config["sources"]["runner_sha256"]
    assert result["source_hashes"]["placement"] == config["trial"]["placement_sha256"]
    assert result["insertion"]["distinct_sand_contacts_by_fibre"] == [4, 4]
    assert result["insertion"]["declared_support_contacts_by_fibre"] == [4, 4]
    assert result["protocol"]["unbounded_free_release"] is False
    assert result["mobile_conditioning_qualified"] is False
    assert result["fixed_validation_qualified"] is False
    assert result["qualified_conditioned_fixed_state_captured"] is False
    assert result["artifacts"]["state_sha256"] is None
    assert result["status"] == "bounded_conditioning_guard_failed"
    terminal = result["terminal_row"]
    assert terminal["block"] == 20
    assert terminal["distinct_sand_contacts_by_fibre"] == [4, 0]
    assert terminal["isolated_fibre_count"] == 1
    assert terminal["maximum_fibre_translation_over_D50"] < 0.001
    assert terminal["maximum_fibre_rotation_deg"] < 1.0
    with history_path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == result["protocol"]["blocks_executed"] == 20

    args.output_dir.mkdir(parents=True, exist_ok=False)
    evaluation = {
        "schema": "lbs.stage26h-bounded-conditioning-pilot-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "physical_feasibility_pilot_failed_contacts_too_shallow",
        "software_or_geometry_failure": False,
        "mobile_conditioning_qualified": False,
        "fixed_validation_qualified": False,
        "terminal_isolated_fibre_count": terminal["isolated_fibre_count"],
        "terminal_contacts_by_fibre": terminal["distinct_sand_contacts_by_fibre"],
        "terminal_maximum_translation_over_D50": terminal["maximum_fibre_translation_over_D50"],
        "terminal_maximum_rotation_deg": terminal["maximum_fibre_rotation_deg"],
        "finding": (
            "Bounded fibre motion did not preserve the initially exact four-contact cages. One fibre became "
            "isolated by block 20 despite sub-0.001 D50 translation and sub-1 degree rotation; the dominant "
            "problem is shallow near-tangent insertion contacts, not over-constraint by fixing the fibres."
        ),
        "next_mechanics_hypothesis": (
            "Prepare the mixture by controlled contact preload/co-compaction so finite normal forces develop "
            "before the 100 Pa equilibrium hold, then restore and verify the exact final fibre geometry."
        ),
        "authority": {
            "heldout_execution_authorized": False,
            "reserve_execution_authorized": False,
            "flow_execution_authorized": False,
            "deformation_authorized": False,
        },
        "source_hashes": {
            "config": sha256(args.config),
            "result": sha256(result_path),
            "completion": sha256(completion_path),
            "history": sha256(history_path),
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
