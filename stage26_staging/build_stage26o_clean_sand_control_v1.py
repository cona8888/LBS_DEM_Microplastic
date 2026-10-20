#!/usr/bin/env python3
"""Build the immutable Stage26o clean-sand wall preparation control."""
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
    parser.add_argument("--design", type=Path, required=True)
    parser.add_argument("--api-evaluation", type=Path, required=True)
    parser.add_argument("--stage25-design", type=Path, required=True)
    parser.add_argument("--stage25-checkpoint", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    design, api, stage25 = load(args.design), load(args.api_evaluation), load(args.stage25_design)
    assert design["status"] == "design_frozen_execution_not_yet_authorized"
    assert api["passed"] is True and api["authority"]["clean_sand_control_authorized"] is True
    assert api["source_hashes"]["design"] == sha(args.design)
    assert api["next_action"] == "build_and_run_stage26o_clean_sand_wall_preparation_control"
    assert stage25["sand"]["particle_count"] == 216
    cfg = {
        "schema": "lbs.stage26o-clean-sand-wall-preparation-control-config.v1",
        "status": "authorized_stage26o_clean_sand_wall_preparation_control",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "physical_question": "Can the wall-bounded gravity and confinement path form a stable 100 Pa LBS sand skeleton without fibres?",
        "research_role": "small_assembly_preparation_control_not_validation",
        "claim_boundary": design["claim_boundary"],
        "sand": {
            "particle_count": 216,
            "density_kg_m3": float(stage25["sand"]["density_kg_m3"]),
            "friction_coefficient": 0.60,
            "young_pa": float(stage25["contacts"]["young_pa"]),
            "poisson": float(stage25["contacts"]["poisson"]),
            "D50_m": 0.0008225865451029433,
            "reference_void_ratio": 0.7385798565195647,
        },
        "walls": {"friction_coefficient": 0.0, "thickness_m": 0.0},
        "initialization": {
            "initial_void_ratio": 4.0,
            "deterministic_rsa_seed": 2026081801,
            "maximum_trials_per_particle": 200000,
            "minimum_initial_clearance_m": 0.0,
        },
        "settling": {
            "gravity_m_s2": [0.0, 0.0, -9.81],
            "timestep_safety_coefficient": 0.10,
            "newton_damping": 0.70,
            "steps_per_block": 500,
            "maximum_blocks": 600,
            "minimum_blocks": 20,
            "required_consecutive_pass_blocks": 5,
            "maximum_unbalanced_force": 0.05,
            "maximum_normalized_kinetic_energy_weight_D50": 1e-5,
            "minimum_sand_contact_count": 150,
        },
        "confinement": {
            "target_mean_wall_stress_pa_compression_positive": 100.0,
            "controller_maximum_wall_velocity_m_s": 0.0015,
            "timestep_safety_coefficient": 0.10,
            "newton_damping": 0.60,
            "steps_per_block": 500,
            "maximum_blocks": 1200,
            "minimum_blocks": 20,
            "required_consecutive_pass_blocks": 5,
        },
        "gravity_removal": {
            "blocks": 100,
            "steps_per_block": 500,
            "terminal_gravity_m_s2": [0.0, 0.0, 0.0],
        },
        "final_hold": {
            "timestep_safety_coefficient": 0.30,
            "newton_damping": 0.35,
            "steps_per_block": 500,
            "maximum_blocks": 400,
            "minimum_blocks": 20,
            "required_consecutive_pass_blocks": 5,
        },
        "acceptance": {
            "maximum_relative_mean_wall_stress_error": 0.05,
            "maximum_principal_wall_stress_error": 0.10,
            "maximum_unbalanced_force": 0.03,
            "maximum_normalized_kinetic_energy_pV": 1e-5,
            "minimum_sand_coordination_excluding_rattlers": 3.0,
            "maximum_sand_rattler_fraction": 0.35,
            "maximum_penetration_over_smaller_radius": 0.02,
            "hard_guard_penetration_over_smaller_radius": 0.05,
            "required_particle_count": 216,
        },
        "sources": {
            "design": str(args.design.resolve()).replace("\\", "/"), "design_sha256": sha(args.design),
            "api_evaluation": str(args.api_evaluation.resolve()).replace("\\", "/"), "api_evaluation_sha256": sha(args.api_evaluation),
            "stage25_design": str(args.stage25_design.resolve()).replace("\\", "/"), "stage25_design_sha256": sha(args.stage25_design),
            "stage25_checkpoint": str(args.stage25_checkpoint.resolve()).replace("\\", "/"), "stage25_checkpoint_sha256": sha(args.stage25_checkpoint),
            "runner": str(args.runner.resolve()).replace("\\", "/"), "runner_sha256": sha(args.runner),
            "expected_yade_version": "2022.01a",
        },
        "authority": {
            "clean_sand_control_authorized": True, "spent_development_mixture_authorized": False,
            "heldout_execution_authorized": False, "flow_execution_authorized": False,
            "deformation_authorized": False, "production_parametric_study_authorized": False,
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir / "control_config.json"
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(cfg, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"config": str(output), "config_sha256": sha(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
