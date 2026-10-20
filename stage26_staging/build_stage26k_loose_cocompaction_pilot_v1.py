#!/usr/bin/env python3
"""Build the immutable Stage26k exact-fibre loose-state co-compaction pilot."""

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
    parser.add_argument("--stage25-result", type=Path, required=True)
    parser.add_argument("--stage25-checkpoint", type=Path, required=True)
    parser.add_argument("--placement", type=Path, required=True)
    parser.add_argument("--stage26j-evaluation", type=Path, required=True)
    parser.add_argument("--stage26j-checkpoint", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--helper", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    stage25 = load(args.stage25_result)
    placement = load(args.placement)
    stage26j = load(args.stage26j_evaluation)
    checkpoint = load(args.stage26j_checkpoint)
    assert stage25["passed"] is True and stage25["case_id"] == "mu_0.60"
    assert len(stage25["particles"]) == 216
    assert placement["record_type"] == "development_capture" and placement["candidate_index"] == 7
    assert len(placement["fibres"]) == 2 and all(len(row["member_centres_m"]) == 37 for row in placement["fibres"])
    assert stage26j["passed"] is True and stage26j["screen_success"] is False
    assert checkpoint["passed"] is True and checkpoint["screen_success"] is False
    assert checkpoint["next_action"] == "generate_and_consolidate_exact_geometry_sand_fibre_mixture_from_loose_state"
    assert checkpoint["source_hashes"]["evaluation"] == sha256(args.stage26j_evaluation)

    config = {
        "schema": "lbs.stage26k-loose-state-exact-fibre-cocompaction-pilot-config.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "authorized_stage26k_spent_development_loose_cocompaction_pilot",
        "research_role": "specimen_preparation_development_pilot_not_validation",
        "physical_question": (
            "Can the 216-sand load-bearing network and persistent exact-geometry fibre support form together "
            "when the mixture is consolidated from a contact-free loose state to 100 Pa?"
        ),
        "claim_boundary": (
            "Stage26k fixed-fibre loose-state co-compaction pilot on one spent development geometry. Sand "
            "radii and exact 50 um fibre geometry are never modified. No free release, held-out inference, "
            "flow, permeability, deformation, migration, or production result."
        ),
        "sources": {
            "expected_yade_version": "2022.01a",
            "stage25_result": str(args.stage25_result.resolve()).replace("\\", "/"),
            "stage25_result_sha256": sha256(args.stage25_result),
            "stage25_checkpoint": str(args.stage25_checkpoint.resolve()).replace("\\", "/"),
            "stage25_checkpoint_sha256": sha256(args.stage25_checkpoint),
            "placement": str(args.placement.resolve()).replace("\\", "/"),
            "placement_sha256": sha256(args.placement),
            "stage26j_evaluation": str(args.stage26j_evaluation.resolve()).replace("\\", "/"),
            "stage26j_evaluation_sha256": sha256(args.stage26j_evaluation),
            "stage26j_checkpoint": str(args.stage26j_checkpoint.resolve()).replace("\\", "/"),
            "stage26j_checkpoint_sha256": sha256(args.stage26j_checkpoint),
            "runner": str(args.runner.resolve()).replace("\\", "/"),
            "runner_sha256": sha256(args.runner),
            "helper": str(args.helper.resolve()).replace("\\", "/"),
            "helper_sha256": sha256(args.helper),
        },
        "sand": {
            "particle_count": 216,
            "reference_contact_count": int(stage25["terminal"]["real_contact_count"]),
            "reference_void_ratio": float(stage25["terminal"]["void_ratio"]),
            "D50_m": float(stage25["psd"]["D50_m"]),
        },
        "candidate_generation": {"D50_m": float(stage25["psd"]["D50_m"])},
        "network_export": {"required_sand_contact_count": int(stage25["terminal"]["real_contact_count"])},
        "frozen_physics": {"target_mean_effective_stress_pa": 100.0},
        "fibre": {
            "count": 2,
            "members_per_fibre": 37,
            "member_radius_m": 5e-05,
            "density_kg_m3": 940.0,
            "target_mass_kg": 6.997520680643619e-09,
            "young_pa": 53000000.0,
            "poisson": 0.25,
            "friction_coefficient": 0.45,
            "fixed_during_pilot": True,
        },
        "preparation": {
            "initial_sand_skeleton_void_ratio": 4.0,
            "target_mean_effective_stress_pa": 100.0,
            "maximum_strain_rate_s_inv": 0.2,
            "steps_per_check_block": 1000,
            "minimum_check_blocks": 50,
            "maximum_check_blocks": 1400,
            "required_consecutive_pass_blocks": 5,
            "newton_damping": 0.35,
            "timestep_safety_coefficient": 0.4,
            "gravity_m_s2": [0.0, 0.0, 0.0],
        },
        "acceptance": {
            "maximum_relative_mean_stress_error": 0.02,
            "maximum_principal_stress_error": 0.03,
            "maximum_unbalanced_force": 0.02,
            "maximum_normalized_kinetic_energy_pV": 1e-05,
            "minimum_sand_coordination_excluding_rattlers": 3.0,
            "maximum_sand_rattler_fraction": 0.35,
            "maximum_interobject_penetration_over_smaller_radius": 0.02,
            "maximum_absolute_sand_skeleton_void_ratio_difference": 0.05,
            "minimum_distinct_sand_contacts_per_fibre": 3,
            "maximum_fibre_fibre_real_interaction_count": 0,
            "maximum_intraclump_real_interaction_count": 0,
        },
        "trial": {
            "trial_id": "candidate07_loose_e4_exact_fibre_fixed_pilot",
            "candidate_index": 7,
            "record_type": "spent_development_loose_cocompaction_pilot",
        },
        "authority": {
            "loose_state_cocompaction_authorized": True,
            "free_release_authorized": False,
            "heldout_execution_authorized": False,
            "reserve_execution_authorized": False,
            "flow_execution_authorized": False,
            "deformation_authorized": False,
            "production_parametric_study_authorized": False,
        },
    }
    assert config["sand"]["reference_contact_count"] == 361
    assert abs(config["sand"]["reference_void_ratio"] - 0.738579856519565) < 1e-12
    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir / "pilot_config.json"
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(config, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"config": str(output), "config_sha256": sha256(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
