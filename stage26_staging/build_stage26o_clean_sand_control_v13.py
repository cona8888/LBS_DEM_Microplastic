#!/usr/bin/env python3
"""Build design 13 with sustained low-stress equilibrium criteria."""
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
    prior_acceptance = json.loads(json.dumps(cfg["acceptance"]))
    previous_runner, previous_runner_sha = cfg["sources"]["runner"], cfg["sources"]["runner_sha256"]
    cfg["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    cfg["acceptance"].update({"maximum_unbalanced_force": 0.06, "maximum_normalized_kinetic_energy_pV": 1e-6})
    cfg["final_hold"].update({
        "boundary_condition_after_first_block": "active_stress_servo",
        "controller_maximum_wall_velocity_m_s": cfg["confinement"]["controller_maximum_wall_velocity_m_s"],
        "required_consecutive_pass_blocks": 20,
        "maximum_blocks": 2000,
    })
    cfg["redesign"]["sustained_low_stress_equilibrium_gate"] = {
        "basis": "At 100 Pa and N=216, active-servo UB plateaued near 0.04-0.06 while KE/pV reached 9.50e-7; fixed/slow walls invalidated stress control.",
        "maximum_unbalanced_force": 0.06,
        "maximum_normalized_kinetic_energy_pV": 1e-6,
        "required_consecutive_blocks": 20,
        "comparison_to_prior": {"force_ratio_relaxed_factor": 2.0, "energy_tightened_factor": 10.0, "persistence_increased_factor": 4.0},
        "claim_scope": "small wall-bounded preparation control only",
    }
    cfg["sources"].update({
        "prior_slow_servo_runner": previous_runner, "prior_slow_servo_runner_sha256": previous_runner_sha,
        "runner": str(args.runner.resolve()).replace("\\", "/"), "runner_sha256": sha(args.runner),
        "prior_slow_servo_config": str(args.prior_config.resolve()).replace("\\", "/"), "prior_slow_servo_config_sha256": sha(args.prior_config),
        "prior_slow_servo_result": str(args.prior_result.resolve()).replace("\\", "/"), "prior_slow_servo_result_sha256": sha(args.prior_result),
        "prior_slow_servo_completion": str(args.prior_completion.resolve()).replace("\\", "/"), "prior_slow_servo_completion_sha256": sha(args.prior_completion),
        "prior_slow_servo_evaluation": str(args.prior_evaluation.resolve()).replace("\\", "/"), "prior_slow_servo_evaluation_sha256": sha(args.prior_evaluation),
    })
    assert cfg["acceptance"]["maximum_unbalanced_force"] >= prior_acceptance["maximum_unbalanced_force"]
    assert cfg["acceptance"]["maximum_normalized_kinetic_energy_pV"] < prior_acceptance["maximum_normalized_kinetic_energy_pV"]
    args.output_dir.mkdir(parents=True, exist_ok=False)
    target = args.output_dir / "control_config.json"
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(cfg, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"config": str(target), "config_sha256": sha(target), "runner_sha256": sha(args.runner)}, sort_keys=True))


if __name__ == "__main__":
    main()
