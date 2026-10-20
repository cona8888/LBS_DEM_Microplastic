#!/usr/bin/env python3
"""Freeze the Stage26o wall-bounded gravity-deposition benchmark design."""
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
    parser.add_argument("--stage26n-evaluation", type=Path, required=True)
    parser.add_argument("--stage26n-checkpoint", type=Path, required=True)
    parser.add_argument("--stage25-design", type=Path, required=True)
    parser.add_argument("--stage25-checkpoint", type=Path, required=True)
    parser.add_argument("--placement", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--builder", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    evaluation, checkpoint, stage25 = load(args.stage26n_evaluation), load(args.stage26n_checkpoint), load(args.stage25_design)
    assert evaluation["passed"] is True and evaluation["numerical_release_stability_pass"] is True
    assert evaluation["mobile_caging_qualified"] is False
    assert checkpoint["passed"] is True and checkpoint["source_hashes"]["evaluation"] == sha(args.stage26n_evaluation)
    assert checkpoint["next_action"] == "design_gravity_assisted_joint_mixture_deposition_benchmark_before_another_caging_attempt"
    assert stage25["sand"]["particle_count"] == 216
    design = {
        "schema": "lbs.stage26o-gravity-assisted-joint-deposition-benchmark-design.v1",
        "status": "design_frozen_execution_not_yet_authorized",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "physical_question": "Can gravity-assisted joint sand-fibre deposition create a persistent exact-fibre cage that the periodic isotropic reconstruction did not?",
        "research_role": "specimen_preparation_model_form_benchmark_not_validation",
        "claim_boundary": "Wall-bounded 216-sand preparation benchmark only. No representative-volume, held-out, flow, permeability, deformation, migration, polymer-calibration, or production-parametric claim.",
        "cases": [
            {"case_id": "clean_sand_wall_control", "fibre_count": 0, "role": "preparation_control"},
            {"case_id": "candidate07_two_fibre_mixture", "fibre_count": 2, "role": "spent_development_mixture"},
        ],
        "geometry": {
            "sand_particle_count": 216, "sand_shape": "sphere", "initial_sand_skeleton_void_ratio": 4.0,
            "boundary": "six_rigid_axis_aligned_walls", "wall_friction_coefficient": 0.0,
            "finite_size_warning": "approximately 5-8 D50 across; wall effects are intentionally diagnostic and not bulk representative",
        },
        "fibre": {
            "shape": "rigid_37_member_sphere_clump", "member_radius_m": 5e-5,
            "density_kg_m3": 940.0, "count_in_mixture": 2, "mobile_during_all_dynamic_phases": True,
        },
        "protocol": {
            "phase_1": "reconstruct loose sand and exact fibres inside static walls with no overlap",
            "phase_2": "settle jointly under gravity [0,0,-9.81] with timestep safety 0.10 and damping 0.70",
            "phase_3": "confine through six moving walls to 100 Pa while retaining gravity, timestep safety 0.10 and damping 0.60",
            "phase_4": "ramp gravity to zero, timestep safety to 0.30 and damping to 0.35",
            "phase_5": "mobile zero-gravity hold for five consecutive acceptance checks",
            "steps_per_check_block": 500,
            "maximum_blocks_by_phase": {"settling": 600, "confinement": 1200, "gravity_removal": 100, "final_hold": 400},
        },
        "acceptance": {
            "required_consecutive_final_hold_passes": 5,
            "minimum_distinct_sand_contacts_per_fibre": 3,
            "maximum_fibre_wall_contacts": 0,
            "maximum_relative_mean_wall_stress_error": 0.05,
            "maximum_unbalanced_force": 0.03,
            "maximum_normalized_kinetic_energy": 1e-5,
            "minimum_sand_coordination_excluding_rattlers": 3.0,
            "maximum_sand_rattler_fraction": 0.35,
            "maximum_penetration_over_smaller_radius": 0.02,
            "hard_guard_penetration_over_smaller_radius": 0.05,
            "exact_geometry_required": True,
        },
        "verification_before_execution": {
            "installed_yade_version": "2022.01a", "wall_api_smoke_required": True,
            "box_sphere_contact_smoke_required": True, "clump_gravity_smoke_required": True,
            "clean_sand_control_must_pass_before_mixture": True,
        },
        "authority": {
            "api_smoke_authorized": True, "clean_sand_control_authorized": False,
            "spent_development_mixture_authorized": False, "heldout_execution_authorized": False,
            "flow_execution_authorized": False, "deformation_authorized": False,
            "production_parametric_study_authorized": False,
        },
        "sources": {
            "stage26n_evaluation": str(args.stage26n_evaluation.resolve()).replace("\\", "/"), "stage26n_evaluation_sha256": sha(args.stage26n_evaluation),
            "stage26n_checkpoint": str(args.stage26n_checkpoint.resolve()).replace("\\", "/"), "stage26n_checkpoint_sha256": sha(args.stage26n_checkpoint),
            "stage25_design": str(args.stage25_design.resolve()).replace("\\", "/"), "stage25_design_sha256": sha(args.stage25_design),
            "stage25_checkpoint": str(args.stage25_checkpoint.resolve()).replace("\\", "/"), "stage25_checkpoint_sha256": sha(args.stage25_checkpoint),
            "placement": str(args.placement.resolve()).replace("\\", "/"), "placement_sha256": sha(args.placement),
            "research_contract": str(args.contract.resolve()).replace("\\", "/"), "research_contract_sha256": sha(args.contract),
            "builder": str(args.builder.resolve()).replace("\\", "/"), "builder_sha256": sha(args.builder),
            "local_yade_example": "/usr/share/doc/yade/examples/triax-tutorial/script-session1.py",
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir / "stage26o_design.json"
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(design, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"design": str(output), "design_sha256": sha(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
