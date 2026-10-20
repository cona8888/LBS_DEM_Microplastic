#!/usr/bin/env python3
"""Build redesign 04 with a gravity-bed-appropriate transition gate."""
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
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    cfg, result, completion, evaluation = (load(args.prior_config), load(args.prior_result), load(args.prior_completion), load(args.prior_evaluation))
    assert completion["result_sha256"] == sha(args.prior_result)
    assert result["source_hashes"]["config"] == sha(args.prior_config)
    assert evaluation["source_hashes"]["result"] == sha(args.prior_result)
    assert evaluation["passed"] is True and evaluation["control_qualified"] is False
    terminal = result["terminal"]
    assert terminal["normalized_kinetic_energy_pV"] <= cfg["acceptance"]["maximum_normalized_kinetic_energy_pV"]
    assert terminal["sand_sand_real_contact_count"] >= 250
    assert terminal["sand_coordination_excluding_degree_lt2_rattlers"] >= 3.0
    original_acceptance = json.loads(json.dumps(cfg["acceptance"]))
    cfg["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    cfg["redesign"]["gravity_transition_gate_correction"] = {
        "basis": "The unconfined bed had KE/pV below the final energy limit and an established network, while global UB was dominated by surface/rattler grains.",
        "maximum_unbalanced_force": 0.30,
        "maximum_normalized_kinetic_energy_weight_D50": 1e-4,
        "minimum_sand_contact_count": 250,
        "final_acceptance_changed": False,
    }
    cfg["settling"].update({
        "maximum_unbalanced_force": 0.30,
        "maximum_normalized_kinetic_energy_weight_D50": 1e-4,
        "minimum_sand_contact_count": 250,
    })
    cfg["sources"].update({
        "prior_transition_config": str(args.prior_config.resolve()).replace("\\", "/"), "prior_transition_config_sha256": sha(args.prior_config),
        "prior_transition_result": str(args.prior_result.resolve()).replace("\\", "/"), "prior_transition_result_sha256": sha(args.prior_result),
        "prior_transition_completion": str(args.prior_completion.resolve()).replace("\\", "/"), "prior_transition_completion_sha256": sha(args.prior_completion),
        "prior_transition_evaluation": str(args.prior_evaluation.resolve()).replace("\\", "/"), "prior_transition_evaluation_sha256": sha(args.prior_evaluation),
    })
    assert cfg["acceptance"] == original_acceptance
    args.output_dir.mkdir(parents=True, exist_ok=False)
    target = args.output_dir / "control_config.json"
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(cfg, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"config": str(target), "config_sha256": sha(target)}, sort_keys=True))


if __name__ == "__main__":
    main()
