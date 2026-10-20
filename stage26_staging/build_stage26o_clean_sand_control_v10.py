#!/usr/bin/env python3
"""Build design 10 with fixed-volume zero-gravity final relaxation."""
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
    parser.add_argument("--prior-config", type=Path, required=True)
    parser.add_argument("--prior-result", type=Path, required=True)
    parser.add_argument("--prior-completion", type=Path, required=True)
    parser.add_argument("--prior-evaluation", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    cfg, result, completion, evaluation = (load(args.prior_config), load(args.prior_result), load(args.prior_completion), load(args.prior_evaluation))
    assert completion["result_sha256"] == sha(args.prior_result)
    assert result["source_hashes"]["config"] == sha(args.prior_config)
    assert evaluation["source_hashes"]["result"] == sha(args.prior_result)
    assert result["status"] == "zero_gravity_hold_not_qualified"
    assert result["terminal_checks"]["unbalanced_force"] is False
    assert all(value for key, value in result["terminal_checks"].items() if key != "unbalanced_force")
    original_acceptance = json.loads(json.dumps(cfg["acceptance"]))
    previous_runner, previous_runner_sha = cfg["sources"]["runner"], cfg["sources"]["runner_sha256"]
    cfg["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    cfg["final_hold"]["boundary_condition_after_first_block"] = "fixed_wall_positions_zero_gravity"
    cfg["redesign"]["fixed_volume_final_relaxation"] = {
        "basis": "Active stress-servo corrections maintained UB chatter despite KE/pV=9.50e-7 and stable stresses.",
        "controller_action": "Set TriaxialStressController.dead=True after the first zero-gravity hold block.",
        "final_stress_gates_retained": True,
        "final_acceptance_changed": False,
    }
    cfg["sources"].update({
        "prior_servo_runner": previous_runner, "prior_servo_runner_sha256": previous_runner_sha,
        "runner": str(args.runner.resolve()).replace("\\", "/"), "runner_sha256": sha(args.runner),
        "prior_servo_config": str(args.prior_config.resolve()).replace("\\", "/"), "prior_servo_config_sha256": sha(args.prior_config),
        "prior_servo_result": str(args.prior_result.resolve()).replace("\\", "/"), "prior_servo_result_sha256": sha(args.prior_result),
        "prior_servo_completion": str(args.prior_completion.resolve()).replace("\\", "/"), "prior_servo_completion_sha256": sha(args.prior_completion),
        "prior_servo_evaluation": str(args.prior_evaluation.resolve()).replace("\\", "/"), "prior_servo_evaluation_sha256": sha(args.prior_evaluation),
    })
    assert cfg["acceptance"] == original_acceptance
    args.output_dir.mkdir(parents=True, exist_ok=False)
    target = args.output_dir / "control_config.json"
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(cfg, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"config": str(target), "config_sha256": sha(target), "runner_sha256": sha(args.runner)}, sort_keys=True))


if __name__ == "__main__":
    main()
