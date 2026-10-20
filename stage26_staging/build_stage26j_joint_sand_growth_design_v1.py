#!/usr/bin/env python3
"""Freeze Stage26j exact-fibre joint sand-growth development screen."""

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
    parser.add_argument("--stage26i-config", type=Path, required=True)
    parser.add_argument("--stage26i-evaluation", type=Path, required=True)
    parser.add_argument("--stage26i-checkpoint", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--helper", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    i_config = load(args.stage26i_config)
    i_eval = load(args.stage26i_evaluation)
    assert i_eval["screen_success"] is False
    placement_trial = next(row for row in i_config["trials"] if row["execution_order"] == 1)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    trials = []
    for order, scale in enumerate((0.99, 0.98), start=1):
        trials.append({
            "trial_id": f"candidate07_joint_growth_from_{(1.0-scale)*100:.0f}pct_shrink",
            "execution_order": order, "record_type": "spent_development_joint_growth_screen",
            "candidate_index": 7, "initial_sand_radius_scale": scale,
            "initial_sand_radius_shrink_percent": (1.0 - scale) * 100.0,
            "placement": placement_trial["placement"], "placement_sha256": placement_trial["placement_sha256"],
        })
    gates = dict(i_config["final_equilibrium_gates"])
    gates["minimum_distinct_sand_contacts_per_fibre"] = 3
    gates["minimum_declared_support_contacts_per_fibre"] = 2
    config = {
        "schema": "lbs.stage26j-joint-sand-growth-development-screen-config.v1",
        "status": "authorized_stage26j_spent_development_joint_growth_screen",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "physical_question": (
            "Can exact-final-geometry fibres acquire persistent support when temporarily shrunken sand is "
            "regrown and reconsolidated around them at 100 Pa?"
        ),
        "research_role": "specimen_preparation_development_screen_not_validation",
        "trials": trials,
        "screen_acceptance": {"select_smallest_successful_shrink": True,
                              "success_requires_exact_final_sand_and_fibre_geometry": True,
                              "no_heldout_or_reserve_inference": True},
        "authority": {"joint_sand_growth_authorized": True, "heldout_execution_authorized": False,
                      "reserve_execution_authorized": False, "free_release_authorized": False,
                      "temporary_fibre_radius_authorized": False, "flow_execution_authorized": False,
                      "deformation_authorized": False, "production_parametric_study_authorized": False},
        "growth_protocol": {"steps_per_block": 500, "sand_growth_blocks": 40,
                            "final_hold_minimum_blocks": 20, "final_hold_maximum_blocks": 120,
                            "required_consecutive_passing_blocks": 10, "maximum_strain_rate_s_inv": 0.02},
        "preparation_guards": {"maximum_interobject_penetration_over_smaller_radius": 0.025},
        "final_equilibrium_gates": gates,
        "candidate_generation": i_config["candidate_generation"],
        "network_export": i_config["network_export"],
        "frozen_physics": dict(i_config["frozen_physics"]),
        "sources": {"runner": str(args.runner).replace("\\", "/"), "runner_sha256": sha256(args.runner),
                    "helper": str(args.helper).replace("\\", "/"), "helper_sha256": sha256(args.helper),
                    "stage25_checkpoint": i_config["sources"]["stage25_checkpoint"],
                    "stage25_checkpoint_sha256": i_config["sources"]["stage25_checkpoint_sha256"],
                    "stage26i_config": str(args.stage26i_config).replace("\\", "/"),
                    "stage26i_config_sha256": sha256(args.stage26i_config),
                    "stage26i_evaluation": str(args.stage26i_evaluation).replace("\\", "/"),
                    "stage26i_evaluation_sha256": sha256(args.stage26i_evaluation),
                    "stage26i_checkpoint": str(args.stage26i_checkpoint).replace("\\", "/"),
                    "stage26i_checkpoint_sha256": sha256(args.stage26i_checkpoint),
                    "expected_yade_version": "2022.01a"},
        "claim_boundary": (
            "Stage26j joint sand-growth preparation screen on one spent development geometry only. Fibres remain "
            "fixed at exact final geometry; sand radii must be exactly restored before acceptance. No held-out "
            "inference, flow, permeability, deformation, migration, or production result."
        ),
    }
    config["frozen_physics"]["newton_damping"] = 0.35
    config["frozen_physics"]["timestep_safety_coefficient"] = 0.10
    config_path = args.output_dir / "screen_config.json"
    with config_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(config, stream, indent=2, sort_keys=True); stream.write("\n")
    manifest = {"schema": "lbs.stage26j-joint-sand-growth-design-manifest.v1", "passed": True,
                "status": "frozen_before_execution", "config_sha256": sha256(config_path),
                "trial_order": [row["trial_id"] for row in trials], "heldout_and_reserve_untouched": True,
                "source_hashes": {"builder": sha256(Path(__file__)), "runner": sha256(args.runner),
                                  "helper": sha256(args.helper), "stage26i_evaluation": sha256(args.stage26i_evaluation),
                                  "stage26i_checkpoint": sha256(args.stage26i_checkpoint)}}
    manifest_path = args.output_dir / "design_manifest.json"
    with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True); stream.write("\n")
    print(json.dumps({"config": str(config_path), "config_sha256": sha256(config_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
