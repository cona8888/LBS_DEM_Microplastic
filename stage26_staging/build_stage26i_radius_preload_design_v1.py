#!/usr/bin/env python3
"""Freeze a three-level temporary-radius-preload screen on spent candidate 07."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path):
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage26h-config", type=Path, required=True)
    parser.add_argument("--stage26h-evaluation", type=Path, required=True)
    parser.add_argument("--stage26h-checkpoint", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--helper", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    h_config = load(args.stage26h_config)
    h_eval = load(args.stage26h_evaluation)
    design01_failure = args.runner.with_name("stage26i_design01_csv_schema_failure.json")
    assert design01_failure.is_file()
    assert h_eval["passed"] is True and h_eval["mobile_conditioning_qualified"] is False
    assert h_config["trial"]["candidate_index"] == 7
    args.output_dir.mkdir(parents=True, exist_ok=False)

    final_gates = dict(h_config["equilibrium_gates"])
    final_gates["minimum_declared_support_contacts_per_fibre"] = 3
    final_gates["minimum_distinct_sand_contacts_per_fibre"] = 3
    final_gates["maximum_interobject_penetration_over_smaller_radius"] = 0.02
    inflated_gates = dict(final_gates)
    inflated_gates["maximum_interobject_penetration_over_smaller_radius"] = 0.025
    scales = [1.010, 1.005, 1.015]
    trials = []
    for order, scale in enumerate(scales, start=1):
        trials.append({
            "trial_id": f"candidate07_preload_{(scale - 1.0) * 100:.1f}pct",
            "execution_order": order,
            "record_type": "spent_development_preload_screen",
            "candidate_index": 7,
            "temporary_radius_scale": scale,
            "temporary_radius_increase_percent": (scale - 1.0) * 100.0,
            "placement": h_config["trial"]["placement"],
            "placement_sha256": h_config["trial"]["placement_sha256"],
        })
    config = {
        "schema": "lbs.stage26i-radius-preload-development-screen-config.v1",
        "status": "authorized_stage26i_spent_development_preload_screen",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "physical_question": (
            "Can temporary 0.5%, 1.0%, or 1.5% fibre-member radius expansion create persistent "
            "fibre-sand cages that remain qualified after exact restoration to the 50 micrometre radius?"
        ),
        "research_role": "preparation_parameter_development_screen_not_validation",
        "screen_order_predeclared": True,
        "trials": trials,
        "screen_acceptance": {
            "select_smallest_successful_radius_increase": True,
            "success_requires_inflated_hold_and_final_geometry_fixed_validation": True,
            "no_heldout_or_reserve_inference": True,
        },
        "authority": {
            "temporary_radius_preload_authorized": True,
            "heldout_execution_authorized": False,
            "reserve_execution_authorized": False,
            "free_release_authorized": False,
            "flow_execution_authorized": False,
            "deformation_authorized": False,
            "production_parametric_study_authorized": False,
        },
        "preload_protocol": {
            "steps_per_block": 500,
            "inflation_ramp_blocks": 10,
            "inflated_hold_minimum_blocks": 20,
            "inflated_hold_maximum_blocks": 100,
            "deflation_ramp_blocks": 10,
            "final_validation_maximum_blocks": 40,
            "required_consecutive_passing_blocks": 10,
            "maximum_strain_rate_s_inv": 0.02,
        },
        "preparation_guards": {
            "maximum_isolated_fibre_count": 0,
            "minimum_distinct_contacts_per_fibre": 2,
            "maximum_temporary_interobject_penetration_over_smaller_radius": 0.025,
        },
        "inflated_equilibrium_gates": inflated_gates,
        "final_equilibrium_gates": final_gates,
        "candidate_generation": h_config["candidate_generation"],
        "network_export": h_config["network_export"],
        "frozen_physics": dict(h_config["frozen_physics"]),
        "sources": {
            "runner": str(args.runner).replace("\\", "/"),
            "runner_sha256": sha256(args.runner),
            "helper": str(args.helper).replace("\\", "/"),
            "helper_sha256": sha256(args.helper),
            "stage25_checkpoint": h_config["sources"]["stage25_checkpoint"],
            "stage25_checkpoint_sha256": h_config["sources"]["stage25_checkpoint_sha256"],
            "stage26h_config": str(args.stage26h_config).replace("\\", "/"),
            "stage26h_config_sha256": sha256(args.stage26h_config),
            "stage26h_evaluation": str(args.stage26h_evaluation).replace("\\", "/"),
            "stage26h_evaluation_sha256": sha256(args.stage26h_evaluation),
            "stage26h_checkpoint": str(args.stage26h_checkpoint).replace("\\", "/"),
            "stage26h_checkpoint_sha256": sha256(args.stage26h_checkpoint),
            "design01_csv_schema_failure": str(design01_failure).replace("\\", "/"),
            "design01_csv_schema_failure_sha256": sha256(design01_failure),
            "expected_yade_version": "2022.01a",
        },
        "claim_boundary": (
            "Stage26i temporary-radius-preload preparation screen on one spent development geometry only; "
            "temporary radius is a numerical preparation control and is restored before acceptance. No "
            "held-out inference, free release, flow, permeability, deformation, migration, or production result."
        ),
    }
    config["frozen_physics"]["newton_damping"] = 0.35
    config["frozen_physics"]["timestep_safety_coefficient"] = 0.10
    config_path = args.output_dir / "screen_config.json"
    with config_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(config, stream, indent=2, sort_keys=True)
        stream.write("\n")
    manifest = {
        "schema": "lbs.stage26i-radius-preload-development-screen-manifest.v1",
        "passed": True,
        "status": "frozen_before_execution",
        "config_sha256": sha256(config_path),
        "trial_order": [row["trial_id"] for row in trials],
        "heldout_and_reserve_untouched": True,
        "source_hashes": {
            "builder": sha256(Path(__file__)), "runner": sha256(args.runner),
            "helper": sha256(args.helper), "stage26h_evaluation": sha256(args.stage26h_evaluation),
            "stage26h_checkpoint": sha256(args.stage26h_checkpoint),
            "design01_csv_schema_failure": sha256(design01_failure),
        },
    }
    manifest_path = args.output_dir / "design_manifest.json"
    with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"config": str(config_path), "config_sha256": sha256(config_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
