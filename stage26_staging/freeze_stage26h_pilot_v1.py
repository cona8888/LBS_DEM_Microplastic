#!/usr/bin/env python3
"""Freeze Stage26h pilot evaluation and render with a closed authority boundary."""

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


def load(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--render-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    evaluation = load(args.evaluation)
    render = load(args.render_manifest)
    assert evaluation["passed"] is True
    assert evaluation["mobile_conditioning_qualified"] is False
    assert evaluation["fixed_validation_qualified"] is False
    assert render["source_hashes"]["evaluation"] == sha256(args.evaluation)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    checkpoint = {
        "schema": "lbs.stage26h-bounded-conditioning-pilot-checkpoint.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "pilot_failed_evidence_frozen",
        "mechanics_conclusion": "Bounded fibre mobility alone does not stabilize shallow insertion contacts.",
        "next_action": "design_controlled_preload_or_joint_cocompaction_on_spent_development_geometry_only",
        "authority": {
            "heldout_execution_authorized": False,
            "reserve_execution_authorized": False,
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
        json.dump(checkpoint, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"checkpoint": str(output), "checkpoint_sha256": sha256(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
