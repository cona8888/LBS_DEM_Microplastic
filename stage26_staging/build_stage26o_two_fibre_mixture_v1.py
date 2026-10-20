"""Build the bounded Stage26o two-F37 spent-development mixture config."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def win(path):
    return str(Path(path).resolve()).replace("\\", "/")


def main():
    output = ROOT / "stage26_designs" / "stage26o_gravity_joint_deposition_20260818" / "two_fibre_mixture_design_01"
    if output.exists():
        raise RuntimeError("immutable mixture design exists")
    runner = ROOT / "stage26_staging" / "run_stage26o_two_fibre_mixture_v1.py"
    control_v9 = ROOT / "stage26_staging" / "run_stage26o_clean_sand_control_v9.py"
    core = ROOT / "stage26_staging" / "run_stage26o_clean_sand_control_v1.py"
    placement = ROOT / "stage26_designs" / "stage26g_fresh_cage_fixed_qualification_20260817" / "design_02" / "normalized_placements" / "stage26f_cage_candidate_07_development.json"
    stage25 = ROOT / "stage25_runs" / "stage25a_pure_sand_mechanics_20260813" / "qualification_04" / "mu_0.60" / "load_bearing_state.yade.gz"
    acceptance = ROOT / "stage26_checkpoints" / "stage26o_gravity_joint_deposition_20260818" / "clean_control_acceptance_13" / "checkpoint_manifest.json"
    with acceptance.open("r", encoding="utf-8") as stream:
        handoff = json.load(stream)
    if not handoff.get("passed") or not handoff["authority"].get("spent_development_mixture_authorized"):
        raise RuntimeError("clean-control handoff does not authorize mixture")
    config = {
        "schema": "lbs.stage26o-two-fibre-joint-deposition-config.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "authorized_stage26o_spent_development_two_fibre_mixture",
        "research_role": "spent_development_small_assembly_preparation_benchmark_not_validation",
        "physical_question": "Can two exact mobile F37 fibres acquire persistent multi-sand-contact cages during the qualified gravity-assisted wall preparation path?",
        "claim_boundary": "One wall-bounded 216-sand, two-F37 spent-development preparation case only. No representative-volume, held-out, flow, permeability, deformation, migration, polymer-calibration, or production-parametric claim.",
        "authority": {"spent_development_mixture_authorized": True, "heldout_execution_authorized": False, "flow_execution_authorized": False, "deformation_authorized": False, "production_parametric_study_authorized": False},
        "acceptance": {"hard_guard_penetration_over_smaller_radius": 0.05, "maximum_normalized_kinetic_energy_pV": 1.0e-5, "maximum_penetration_over_smaller_radius": 0.02, "maximum_principal_wall_stress_error": 0.10, "maximum_relative_mean_wall_stress_error": 0.05, "maximum_sand_rattler_fraction": 0.35, "maximum_unbalanced_force": 0.03, "minimum_sand_coordination_excluding_rattlers": 3.0, "required_particle_count": 216, "minimum_distinct_sand_contacts_per_fibre": 3, "maximum_fibre_wall_contacts": 0},
        "initialization": {"deterministic_rsa_seed": 2026081801, "initial_void_ratio": 4.0, "maximum_trials_per_particle": 200000, "minimum_initial_clearance_m": 0.0, "fibre_pivot_fractions": [[0.34, 0.38, 0.78], [0.66, 0.62, 0.72]]},
        "sand": {"D50_m": 0.0008225865451029433, "density_kg_m3": 2650.0, "friction_coefficient": 0.6, "particle_count": 216, "poisson": 0.25, "young_pa": 53000000.0},
        "fibre": {"count": 2, "shape": "rigid_37_member_sphere_clump", "member_radius_m": 5.0e-5, "members_per_fibre": 37, "density_kg_m3": 940.0, "friction_coefficient": 0.45, "poisson": 0.25, "young_pa": 53000000.0, "target_mass_kg": 6.997520680643619e-9, "mobile_during_all_dynamic_phases": True},
        "walls": {"friction_coefficient": 0.0, "thickness_m": 0.0},
        "settling": {"gravity_m_s2": [0.0, 0.0, -9.81], "maximum_blocks": 1200, "maximum_normalized_kinetic_energy_weight_D50": 0.0001, "maximum_unbalanced_force": 0.3, "minimum_blocks": 20, "minimum_sand_contact_count": 250, "newton_damping": 0.9, "required_consecutive_pass_blocks": 5, "steps_per_block": 500, "timestep_safety_coefficient": 0.3},
        "confinement": {"controller_internal_target_pa": 100.0, "physical_reaction_target_pa": 100.0, "target_mean_wall_stress_pa_compression_positive": 100.0, "controller_maximum_wall_velocity_m_s": 0.02, "maximum_blocks": 1800, "minimum_blocks": 20, "newton_damping": 0.85, "required_consecutive_pass_blocks": 5, "steps_per_block": 500, "timestep_safety_coefficient": 0.3, "stress_observable": "absolute_right_top_front_wall_reaction_component_divided_by_current_wall_area"},
        "confinement_transition": {"maximum_normalized_kinetic_energy_pV": 0.0001, "maximum_principal_wall_stress_error": 0.12, "maximum_relative_mean_wall_stress_error": 0.05, "maximum_unbalanced_force": 0.08, "required_consecutive_pass_blocks": 5},
        "gravity_removal": {"blocks": 100, "steps_per_block": 500, "terminal_gravity_m_s2": [0.0, 0.0, 0.0]},
        "final_hold": {"boundary_condition_after_first_block": "active_stress_servo", "controller_maximum_wall_velocity_m_s": 0.02, "maximum_blocks": 2000, "minimum_blocks": 20, "newton_damping": 0.85, "required_consecutive_pass_blocks": 5, "steps_per_block": 500, "timestep_safety_coefficient": 0.3},
        "sources": {"expected_yade_version": "2022.01a", "runner": win(runner), "runner_sha256": sha256(runner), "control_v9": win(control_v9), "control_v9_sha256": sha256(control_v9), "core_runner": win(core), "core_runner_sha256": sha256(core), "placement": win(placement), "placement_sha256": sha256(placement), "stage25_checkpoint": win(stage25), "stage25_checkpoint_sha256": sha256(stage25), "clean_control_acceptance": win(acceptance), "clean_control_acceptance_sha256": sha256(acceptance)},
    }
    output.mkdir(parents=True)
    path = output / "mixture_config.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(config, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"config": str(path), "sha256": sha256(path), "runner_sha256": sha256(runner)}, sort_keys=True))


if __name__ == "__main__":
    main()
