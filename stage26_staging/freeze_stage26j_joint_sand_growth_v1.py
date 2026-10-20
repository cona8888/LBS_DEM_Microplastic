#!/usr/bin/env python3
"""Freeze the Stage26j failed-screen evidence and authority boundary."""

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
    assert evaluation["passed"] is True and evaluation["screen_success"] is False
    assert render["passed"] is True
    assert render["source_hashes"]["evaluation"] == sha256(args.evaluation)
    assert evaluation["authority"] == {
        "deformation_authorized": False,
        "flow_execution_authorized": False,
        "heldout_execution_authorized": False,
        "reserve_execution_authorized": False,
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    checkpoint = {
        "schema": "lbs.stage26j-joint-sand-growth-screen-checkpoint.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "failed_joint_sand_growth_screen_evidence_frozen",
        "screen_success": False,
        "mechanics_conclusion": (
            "Uniform shrink-regrow editing of the equilibrated pure-sand packing does not preserve a "
            "100 Pa load-bearing network around exact-geometry fibres."
        ),
        "next_action": "generate_and_consolidate_exact_geometry_sand_fibre_mixture_from_loose_state",
        "authority": evaluation["authority"],
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
