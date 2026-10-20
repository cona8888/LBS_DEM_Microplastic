#!/usr/bin/env python3
"""Build design 12: direct 100 Pa reactions and slow active final servo."""
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
    terminal_stresses = result["terminal"]["principal_wall_stress_pa_compression_positive"]
    assert max(terminal_stresses) < 30.0
    original_acceptance = json.loads(json.dumps(cfg["acceptance"]))
    previous_runner, previous_runner_sha = cfg["sources"]["runner"], cfg["sources"]["runner_sha256"]
    cfg["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    cfg["confinement"]["controller_internal_target_pa"] = 100.0
    cfg["confinement"]["controller_calibration_factor_direct_over_internal"] = 1.0
    cfg["final_hold"].update({
        "boundary_condition_after_first_block": "active_stress_servo_reduced_maximum_velocity",
        "controller_maximum_wall_velocity_m_s": 1e-5,
    })
    cfg["redesign"]["direct_target_and_slow_servo_correction"] = {
        "basis": "Design 11 proved active direct reactions track the internal target nearly one-to-one; the prior 4.4x factor was caused by fixed-wall relaxation.",
        "controller_internal_target_pa": 100.0,
        "physical_target_pa": 100.0,
        "final_servo_maximum_velocity_m_s": 1e-5,
        "final_acceptance_changed": False,
    }
    cfg["sources"].update({
        "prior_calibrated_runner": previous_runner, "prior_calibrated_runner_sha256": previous_runner_sha,
        "runner": str(args.runner.resolve()).replace("\\", "/"), "runner_sha256": sha(args.runner),
        "prior_calibrated_config": str(args.prior_config.resolve()).replace("\\", "/"), "prior_calibrated_config_sha256": sha(args.prior_config),
        "prior_calibrated_result": str(args.prior_result.resolve()).replace("\\", "/"), "prior_calibrated_result_sha256": sha(args.prior_result),
        "prior_calibrated_completion": str(args.prior_completion.resolve()).replace("\\", "/"), "prior_calibrated_completion_sha256": sha(args.prior_completion),
        "prior_calibrated_evaluation": str(args.prior_evaluation.resolve()).replace("\\", "/"), "prior_calibrated_evaluation_sha256": sha(args.prior_evaluation),
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
