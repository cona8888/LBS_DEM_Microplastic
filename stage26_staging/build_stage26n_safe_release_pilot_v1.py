#!/usr/bin/env python3
"""Build the immutable Stage26n equilibrated, timestep-ramped fibre-release pilot."""
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
    parser.add_argument("--stage26m-config", type=Path, required=True)
    parser.add_argument("--stage26m-evaluation", type=Path, required=True)
    parser.add_argument("--stage26m-checkpoint", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--helper", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    parent = load(args.stage26m_config)
    evaluation = load(args.stage26m_evaluation)
    checkpoint = load(args.stage26m_checkpoint)
    assert evaluation["passed"] is True
    assert evaluation["physical_result_accepted"] is False
    assert evaluation["next_action"] == "equilibrate_fixed_state_then_reduce_timestep_and_increase_damping_before_release"
    assert checkpoint["passed"] is True
    assert checkpoint["physical_result_accepted"] is False
    assert checkpoint["next_action"] == evaluation["next_action"]
    assert checkpoint["source_hashes"]["evaluation"] == sha(args.stage26m_evaluation)

    cfg = dict(parent)
    cfg.update({
        "schema": "lbs.stage26n-equilibrated-safe-release-pilot-config.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "authorized_stage26n_spent_development_equilibrated_safe_release_pilot",
        "physical_question": (
            "After the exact-fibre loose mixture reaches a stable 100 Pa sand skeleton, can a "
            "small-timestep high-damping release avoid the Stage26m integration impulse and reach "
            "a bounded mobile equilibrium?"
        ),
        "claim_boundary": (
            "Stage26n numerical release-stability and mobile-caging pilot on one spent development "
            "geometry. Fixed positioning is initialization only. Exact sand radii and rigid 50 um "
            "fibre geometry are retained. No held-out, reserve, flow, permeability, deformation, "
            "migration, or production-parametric result."
        ),
        "trial": {
            "trial_id": "candidate07_equilibrated_safe_release_mobile_pilot",
            "candidate_index": 7,
            "record_type": "spent_development_numerical_release_stability_pilot",
        },
        "fixed_equilibration": {
            "maximum_blocks": 1800,
            "minimum_blocks": 1300,
            "steps_per_block": 1000,
            "required_consecutive_pass_blocks": 5,
            "minimum_sand_contact_count": 330,
            "minimum_distinct_sand_contacts_per_fibre": 1,
            "maximum_relative_mean_stress_error": 0.02,
            "maximum_principal_stress_error": 0.03,
            "maximum_unbalanced_force": 0.03,
            "maximum_normalized_kinetic_energy_pV": 1e-5,
            "minimum_sand_coordination_excluding_rattlers": 3.0,
            "maximum_sand_rattler_fraction": 0.35,
            "maximum_interobject_penetration_over_smaller_radius": 0.02,
            "maximum_absolute_sand_skeleton_void_ratio_difference": 0.05,
        },
        "release_protocol": {
            "forced_pre_release_dt_multiplier": 0.01,
            "time_step_update_interval": 1,
            "ramp_stages": [
                {"name": "micro_02", "timestep_safety_coefficient": 0.02, "newton_damping": 0.95, "subblocks": 20, "steps_per_subblock": 10},
                {"name": "micro_05", "timestep_safety_coefficient": 0.05, "newton_damping": 0.90, "subblocks": 20, "steps_per_subblock": 25},
                {"name": "micro_10", "timestep_safety_coefficient": 0.10, "newton_damping": 0.85, "subblocks": 20, "steps_per_subblock": 50},
                {"name": "micro_20", "timestep_safety_coefficient": 0.20, "newton_damping": 0.75, "subblocks": 20, "steps_per_subblock": 100},
            ],
            "mobile_timestep_safety_coefficient": 0.30,
            "mobile_newton_damping": 0.60,
            "mobile_steps_per_block": 500,
            "mobile_minimum_blocks": 20,
            "mobile_maximum_blocks": 800,
            "required_consecutive_pass_blocks": 5,
        },
        "hard_guards": {
            "maximum_interobject_penetration_over_smaller_radius": 0.05,
            "maximum_nonaffine_translation_over_D50": 1.0,
            "maximum_absolute_principal_stress_pa": 500.0,
        },
        "authority": {
            "equilibrated_safe_release_pilot_authorized": True,
            "heldout_execution_authorized": False,
            "reserve_execution_authorized": False,
            "flow_execution_authorized": False,
            "deformation_authorized": False,
            "production_parametric_study_authorized": False,
        },
    })
    cfg["fibre"] = dict(parent["fibre"])
    cfg["fibre"]["fixed_during_initialization_only"] = True
    cfg["sources"] = dict(parent["sources"])
    cfg["sources"].update({
        "stage26m_config": str(args.stage26m_config.resolve()).replace("\\", "/"),
        "stage26m_config_sha256": sha(args.stage26m_config),
        "stage26m_evaluation": str(args.stage26m_evaluation.resolve()).replace("\\", "/"),
        "stage26m_evaluation_sha256": sha(args.stage26m_evaluation),
        "stage26m_checkpoint": str(args.stage26m_checkpoint.resolve()).replace("\\", "/"),
        "stage26m_checkpoint_sha256": sha(args.stage26m_checkpoint),
        "runner": str(args.runner.resolve()).replace("\\", "/"),
        "runner_sha256": sha(args.runner),
        "helper": str(args.helper.resolve()).replace("\\", "/"),
        "helper_sha256": sha(args.helper),
    })
    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir / "pilot_config.json"
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(cfg, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"config": str(output), "config_sha256": sha(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
