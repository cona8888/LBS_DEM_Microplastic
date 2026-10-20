#!/usr/bin/env python3
"""Verify Stage26o API smoke evidence and freeze the clean-control handoff."""
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
    parser.add_argument("--design", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--completion", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--evaluator", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    design, result, completion = load(args.design), load(args.result), load(args.completion)
    assert design["authority"]["api_smoke_authorized"] is True
    assert result["passed"] is True and completion["passed"] is True
    assert completion["result_sha256"] == sha(args.result)
    assert result["source_hashes"]["design"] == sha(args.design)
    assert result["source_hashes"]["smoke_runner"] == sha(args.runner)
    required = (
        "six_walls_created", "sand_fell", "clump_fell", "wall_contact_detected",
        "finite_time_step", "finite_kinetic_energy", "controller_api_present", "clump_membership_preserved",
    )
    assert all(result["checks"][name] for name in required)
    evaluation = {
        "schema": "lbs.stage26o-wall-gravity-api-smoke-evaluation.v1", "passed": True,
        "status": "local_yade_wall_gravity_clump_controller_api_verified",
        "verified_capabilities": list(required),
        "finding": "YADE 2022.01a supports the wall-bounded gravity/deposition mechanisms required by the frozen Stage26o benchmark design.",
        "next_action": "build_and_run_stage26o_clean_sand_wall_preparation_control",
        "authority": {
            "clean_sand_control_authorized": True, "spent_development_mixture_authorized": False,
            "heldout_execution_authorized": False, "flow_execution_authorized": False,
            "deformation_authorized": False, "production_parametric_study_authorized": False,
        },
        "source_hashes": {
            "design": sha(args.design), "smoke_result": sha(args.result), "smoke_completion": sha(args.completion),
            "smoke_runner": sha(args.runner), "evaluator": sha(args.evaluator),
        },
        "claim_boundary": design["claim_boundary"], "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir / "evaluation.json"
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"evaluation": str(output), "evaluation_sha256": sha(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
