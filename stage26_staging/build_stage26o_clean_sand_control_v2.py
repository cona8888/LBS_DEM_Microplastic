#!/usr/bin/env python3
"""Build the immutable Stage26o clean-control redesign from attempt-01 evidence."""
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
    assert evaluation["authority"]["redesign_clean_control_authorized"] is True
    cfg["schema"] = "lbs.stage26o-clean-sand-wall-preparation-control-config.v2"
    cfg["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    cfg["status"] = "authorized_stage26o_clean_sand_wall_preparation_control_redesign_02"
    cfg["redesign"] = {
        "basis": "Attempt 01 was numerically healthy but reached only 0.128 s before its settling ceiling.",
        "acceptance_gates_changed": False,
        "initial_geometry_seed_changed": False,
        "changes": [
            "settling timestep safety 0.10 to 0.30",
            "settling damping 0.70 to 0.90",
            "settling ceiling 600 to 1200 blocks",
            "wall maximum speed 0.0015 to 0.020 m/s",
            "confinement timestep safety 0.10 to 0.30",
            "confinement damping 0.60 to 0.85",
            "confinement ceiling 1200 to 1800 blocks",
        ],
    }
    cfg["settling"].update({"timestep_safety_coefficient": 0.30, "newton_damping": 0.90, "maximum_blocks": 1200})
    cfg["confinement"].update({
        "controller_maximum_wall_velocity_m_s": 0.020,
        "timestep_safety_coefficient": 0.30,
        "newton_damping": 0.85,
        "maximum_blocks": 1800,
    })
    cfg["sources"].update({
        "prior_config": str(args.prior_config.resolve()).replace("\\", "/"), "prior_config_sha256": sha(args.prior_config),
        "prior_result": str(args.prior_result.resolve()).replace("\\", "/"), "prior_result_sha256": sha(args.prior_result),
        "prior_completion": str(args.prior_completion.resolve()).replace("\\", "/"), "prior_completion_sha256": sha(args.prior_completion),
        "prior_evaluation": str(args.prior_evaluation.resolve()).replace("\\", "/"), "prior_evaluation_sha256": sha(args.prior_evaluation),
    })
    args.output_dir.mkdir(parents=True, exist_ok=False)
    target = args.output_dir / "control_config.json"
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(cfg, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"config": str(target), "config_sha256": sha(target)}, sort_keys=True))


if __name__ == "__main__":
    main()
