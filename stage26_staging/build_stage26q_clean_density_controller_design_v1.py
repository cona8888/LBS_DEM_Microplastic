from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
OUT = (
    ROOT
    / "stage26_designs"
    / "stage26q_density_geometry_flexure_20260818"
    / "clean_density_controller_design_01"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": str(path), "sha256": sha256(path)}


def main() -> None:
    stage25 = (
        ROOT
        / "stage25_checkpoints"
        / "stage25a_pure_sand_mechanics_20260813"
        / "checkpoint_01"
        / "checkpoint_manifest.json"
    )
    clean = (
        ROOT
        / "stage26_checkpoints"
        / "stage26o_gravity_joint_deposition_20260818"
        / "clean_control_acceptance_13"
        / "checkpoint_manifest.json"
    )
    mechanism = (
        ROOT
        / "stage26_checkpoints"
        / "stage26p_single_fibre_mechanism_20260818"
        / "mechanism_checkpoint_01"
        / "checkpoint_manifest.json"
    )
    contract = ROOT / "stage26_staging" / "STAGE26Q_DENSITY_AND_FLEXURE_RESEARCH_CONTRACT.md"
    runner = ROOT / "stage26_staging" / "run_stage26q_clean_density_controller_v1.py"

    stage25_data = json.loads(stage25.read_text(encoding="utf-8"))
    clean_data = json.loads(clean.read_text(encoding="utf-8"))
    mechanism_data = json.loads(mechanism.read_text(encoding="utf-8"))
    if not (
        stage25_data.get("passed") is True
        and clean_data.get("passed") is True
        and mechanism_data.get("passed") is True
    ):
        raise RuntimeError("required accepted checkpoints are not passed")

    config = {
        "schema": "lbs.stage26q-clean-density-controller-config.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "authorized_stage26q_clean_density_controller_pilot",
        "research_role": "clean_controller_qualification_not_material_calibration",
        "claim_boundary": (
            "One wall-bounded 216-sphere clean-sand density-controller benchmark. "
            "No fibre, angular-grain, representative-volume, flow, permeability, "
            "deformation, migration, or production-parametric claim."
        ),
        "sand": {
            "particle_count": 216,
            "D50_m": 0.0008225865451029433,
            "density_kg_m3": 2650.0,
        },
        "density_ramp": {
            "reference_void_ratio": 0.744,
            "handoff_void_ratio_tolerance": 0.002,
            "isotropic_compressive_strain_rate_per_s": 0.10,
            "steps_per_block": 500,
            "maximum_blocks": 2000,
            "newton_damping": 0.90,
            "timestep_safety_coefficient": 0.30,
        },
        "fixed_volume_hold": {
            "minimum_blocks": 20,
            "maximum_blocks": 1200,
            "steps_per_block": 500,
            "required_consecutive_pass_blocks": 5,
            "maximum_unbalanced_force": 0.05,
            "maximum_normalized_kinetic_energy_pV": 1.0e-4,
            "newton_damping": 0.90,
        },
        "stress_restoration": {
            "target_isotropic_stress_pa_compression_positive": 100.0,
            "controller_maximum_wall_velocity_m_s": 0.02,
            "minimum_blocks": 20,
            "maximum_blocks": 2400,
            "steps_per_block": 500,
            "required_consecutive_pass_blocks": 5,
            "newton_damping": 0.85,
            "timestep_safety_coefficient": 0.30,
        },
        "acceptance": {
            "required_particle_count": 216,
            "maximum_terminal_void_ratio_error": 0.02,
            "maximum_relative_mean_wall_stress_error": 0.05,
            "maximum_principal_wall_stress_error": 0.10,
            "maximum_unbalanced_force": 0.03,
            "maximum_normalized_kinetic_energy_pV": 1.0e-5,
            "maximum_penetration_over_smaller_radius": 0.02,
            "hard_guard_penetration_over_smaller_radius": 0.05,
            "minimum_sand_coordination_excluding_rattlers": 3.0,
            "maximum_sand_rattler_fraction": 0.35,
            "maximum_leaked_particle_count": 0,
        },
        "sources": {
            "stage25_reference": bind(stage25),
            "stage26o_clean_control": bind(clean),
            "stage26p_mechanism_checkpoint": bind(mechanism),
            "research_contract": bind(contract),
            "runner": bind(runner),
            "input_state": clean_data["sources"]["state"],
            "expected_yade_version": "2022.01a",
        },
        "authority": {
            "clean_density_controller_pilot_authorized": True,
            "pore_throat_extraction_authorized_after_clean_pass": True,
            "single_fibre_execution_authorized": False,
            "full_mixture_execution_authorized": False,
            "flexible_fibre_execution_authorized": False,
            "flow_execution_authorized": False,
            "permeability_claim_authorized": False,
            "production_parametric_study_authorized": False,
        },
    }

    OUT.mkdir(parents=True, exist_ok=False)
    output_path = OUT / "config.json"
    output_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    print(sha256(output_path))


if __name__ == "__main__":
    main()
