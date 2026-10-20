#!/usr/bin/env python3
"""Freeze the Stage26n evaluated evidence and next-action boundary."""
from __future__ import annotations

import argparse
import hashlib
import json
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
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--render-manifest", type=Path, required=True)
    parser.add_argument("--freezer", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    evaluation, render = load(args.evaluation), load(args.render_manifest)
    assert evaluation["passed"] is True and evaluation["numerical_release_stability_pass"] is True
    assert evaluation["mobile_caging_qualified"] is False and evaluation["physical_result_accepted"] is False
    assert render["passed"] is True and render["source_hashes"]["evaluation"] == sha(args.evaluation)
    checkpoint = {
        "schema": "lbs.stage26n-safe-release-pilot-checkpoint.v1", "passed": True,
        "status": "stable_release_verified_but_exact_fibres_not_embedded",
        "numerical_release_stability_pass": True, "mobile_caging_qualified": False,
        "physical_result_accepted": False,
        "mechanics_conclusion": (
            "Safe integration is no longer the blocker. The current loose isotropic reconstruction "
            "forms a sound sand skeleton but leaves both exact fibres uncaged in pore space."
        ),
        "next_action": evaluation["next_action"],
        "source_hashes": {"evaluation": sha(args.evaluation), "render_manifest": sha(args.render_manifest), "freezer": sha(args.freezer)},
        "authority": evaluation["authority"], "claim_boundary": evaluation["claim_boundary"],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir / "checkpoint_manifest.json"
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(checkpoint, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"checkpoint": str(output), "checkpoint_sha256": sha(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
