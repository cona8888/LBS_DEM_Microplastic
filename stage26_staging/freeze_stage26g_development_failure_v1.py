#!/usr/bin/env python3
"""Freeze the verified Stage26g development-gate failure and authority boundary."""

from __future__ import annotations

import argparse
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
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--render-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    evaluation = load_json(args.evaluation)
    render = load_json(args.render_manifest)
    assert evaluation["passed"] is True
    assert evaluation["development_acceptance_passed"] is False
    assert evaluation["heldout_execution_authorized"] is False
    assert render["passed"] is True
    assert render["source_hashes"]["evaluation"] == sha256(args.evaluation)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    payload = {
        "schema": "lbs.stage26g-development-failure-checkpoint.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "development_gate_failed_evidence_frozen",
        "development_acceptance_passed": False,
        "heldout_execution_authorized": False,
        "next_action": "redesign_preparation_protocol_without_using_heldout_or_reserve_cases",
        "authority": {
            "heldout_execution_authorized": False,
            "reserve_execution_authorized": False,
            "free_release_authorized": False,
            "flow_execution_authorized": False,
            "deformation_authorized": False,
        },
        "source_hashes": {
            "evaluation": sha256(args.evaluation),
            "render_manifest": sha256(args.render_manifest),
            "freezer": sha256(Path(__file__)),
        },
        "claim_boundary": evaluation["claim_boundary"],
    }
    output = args.output_dir / "checkpoint_manifest.json"
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"checkpoint": str(output), "checkpoint_sha256": sha256(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
