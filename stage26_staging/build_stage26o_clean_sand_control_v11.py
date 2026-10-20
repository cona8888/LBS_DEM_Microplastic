#!/usr/bin/env python3
"""Build design 11 with direct reaction stress measurement and calibrated servo goal."""
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
    parser.add_argument("--direct-audit", type=Path, required=True)
    parser.add_argument("--reaction-probe", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    cfg, result, completion, audit, probe = (load(args.prior_config), load(args.prior_result), load(args.prior_completion), load(args.direct_audit), load(args.reaction_probe))
    assert completion["result_sha256"] == sha(args.prior_result)
    assert result["source_hashes"]["config"] == sha(args.prior_config)
    assert audit["source_hashes"]["reaction_probe"] == sha(args.reaction_probe)
    assert audit["control_qualified"] is False and audit["authority"]["direct_reaction_stress_redesign_authorized"] is True
    measured_factor = float(probe["direct_mean_stress_pa"]) / 100.0
    internal_target = 100.0 / measured_factor
    original_acceptance = json.loads(json.dumps(cfg["acceptance"]))
    previous_runner, previous_runner_sha = cfg["sources"]["runner"], cfg["sources"]["runner_sha256"]
    cfg["schema"] = "lbs.stage26o-clean-sand-wall-preparation-control-config.v4"
    cfg["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    cfg["confinement"].update({
        "physical_reaction_target_pa": 100.0,
        "controller_internal_target_pa": internal_target,
        "stress_observable": "absolute_right_top_front_wall_reaction_component_divided_by_current_wall_area",
        "controller_calibration_factor_direct_over_internal": measured_factor,
    })
    cfg["redesign"]["direct_reaction_stress_correction"] = {
        "basis": "One-step force rebuild on the qualified checkpoint measured 444.274 Pa mean direct reaction rather than the reported 99.748 Pa.",
        "controller_internal_target_pa": internal_target,
        "physical_target_pa": 100.0,
        "all_stress_gates_use_direct_reactions": True,
        "final_acceptance_changed": False,
    }
    cfg["sources"].update({
        "prior_cached_stress_runner": previous_runner, "prior_cached_stress_runner_sha256": previous_runner_sha,
        "runner": str(args.runner.resolve()).replace("\\", "/"), "runner_sha256": sha(args.runner),
        "prior_cached_stress_config": str(args.prior_config.resolve()).replace("\\", "/"), "prior_cached_stress_config_sha256": sha(args.prior_config),
        "prior_cached_stress_result": str(args.prior_result.resolve()).replace("\\", "/"), "prior_cached_stress_result_sha256": sha(args.prior_result),
        "prior_cached_stress_completion": str(args.prior_completion.resolve()).replace("\\", "/"), "prior_cached_stress_completion_sha256": sha(args.prior_completion),
        "direct_stress_audit": str(args.direct_audit.resolve()).replace("\\", "/"), "direct_stress_audit_sha256": sha(args.direct_audit),
        "direct_reaction_probe": str(args.reaction_probe.resolve()).replace("\\", "/"), "direct_reaction_probe_sha256": sha(args.reaction_probe),
    })
    assert cfg["acceptance"] == original_acceptance
    args.output_dir.mkdir(parents=True, exist_ok=False)
    target = args.output_dir / "control_config.json"
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(cfg, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"config": str(target), "config_sha256": sha(target), "internal_target_pa": internal_target}, sort_keys=True))


if __name__ == "__main__":
    main()
