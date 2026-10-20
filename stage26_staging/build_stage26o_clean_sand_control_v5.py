#!/usr/bin/env python3
"""Build design 05 with a phase-specific confinement transition gate."""
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
    assert evaluation["passed"] is True and result["status"] == "confinement_not_qualified"
    terminal = result["terminal"]
    assert terminal["sand_coordination_excluding_degree_lt2_rattlers"] >= cfg["acceptance"]["minimum_sand_coordination_excluding_rattlers"]
    assert terminal["sand_rattler_fraction_degree_lt2_iterative"] <= cfg["acceptance"]["maximum_sand_rattler_fraction"]
    original_acceptance = json.loads(json.dumps(cfg["acceptance"]))
    old_runner, old_runner_sha = cfg["sources"]["runner"], cfg["sources"]["runner_sha256"]
    cfg["schema"] = "lbs.stage26o-clean-sand-wall-preparation-control-config.v3"
    cfg["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    cfg["confinement_transition"] = {
        "maximum_relative_mean_wall_stress_error": 0.05,
        "maximum_principal_wall_stress_error": 0.12,
        "maximum_unbalanced_force": 0.08,
        "maximum_normalized_kinetic_energy_pV": 1e-4,
        "required_consecutive_pass_blocks": 5,
        "purpose": "Authorize gravity-removal ramp only; not final qualification.",
    }
    cfg["redesign"]["confinement_transition_gate_correction"] = {
        "basis": "Control 04 formed a healthy near-target network, but the v1 runner reused final zero-g equilibrium gates before gravity removal.",
        "final_acceptance_changed": False,
    }
    cfg["sources"].update({
        "core_runner": old_runner, "core_runner_sha256": old_runner_sha,
        "runner": str(args.runner.resolve()).replace("\\", "/"), "runner_sha256": sha(args.runner),
        "prior_confinement_config": str(args.prior_config.resolve()).replace("\\", "/"), "prior_confinement_config_sha256": sha(args.prior_config),
        "prior_confinement_result": str(args.prior_result.resolve()).replace("\\", "/"), "prior_confinement_result_sha256": sha(args.prior_result),
        "prior_confinement_completion": str(args.prior_completion.resolve()).replace("\\", "/"), "prior_confinement_completion_sha256": sha(args.prior_completion),
        "prior_confinement_evaluation": str(args.prior_evaluation.resolve()).replace("\\", "/"), "prior_confinement_evaluation_sha256": sha(args.prior_evaluation),
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
