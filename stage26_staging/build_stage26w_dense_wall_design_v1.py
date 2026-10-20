from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
OUT = ROOT / "stage26_designs" / "stage26w_dense_wall_shrink_regrow_20260823" / "design_01"
RUNNER = ROOT / "stage26_staging" / "run_stage26w_dense_wall_shrink_regrow_v1.py"
CONTRACT = ROOT / "stage26_staging" / "STAGE26W_DENSE_WALL_SHRINK_REGROW_CONTRACT.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise RuntimeError(f"missing source: {path}")
    return {"path": str(path), "sha256": sha256(path)}


def main() -> None:
    if OUT.exists():
        raise RuntimeError("immutable Stage26w Design01 exists")
    input_state = ROOT / "stage26_runs" / "stage26o_gravity_joint_deposition_20260818" / "clean_control_13" / "qualified_clean_sand_wall_state.yade.gz"
    stage26o_checkpoint = ROOT / "stage26_checkpoints" / "stage26o_gravity_joint_deposition_20260818" / "clean_control_acceptance_13" / "checkpoint_manifest.json"
    stage26q = ROOT / "stage26_evaluations" / "stage26q_density_geometry_flexure_20260818" / "clean_density_controller_evaluation_04" / "evaluation.json"
    stage26r = ROOT / "stage26_evaluations" / "stage26r_periodic_radius_restoration_20260819" / "clean_radius_restoration_evaluation_05" / "evaluation.json"
    stage26v = ROOT / "stage26_evaluations" / "stage26v_216_flexible_fibre_integration_20260823" / "fixed_sand_evaluation_01" / "checkpoint_manifest.json"
    q = json.loads(stage26q.read_text(encoding="utf-8"))
    r = json.loads(stage26r.read_text(encoding="utf-8"))
    if q.get("passed") is not False or q.get("status") != "clean_density_controller_not_accepted":
        raise RuntimeError("Stage26q nonacceptance is not preserved")
    if r.get("passed") is not True or r.get("classification") != "verified_physical_protocol_nonacceptance":
        raise RuntimeError("Stage26r protocol nonacceptance is not verified")
    cfg = {
        "schema": "lbs.stage26w-dense-wall-shrink-regrow-config.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "authorized_stage26w_dense_wall_shrink_regrow_pilot",
        "research_role": "clean_specimen_preparation_verification_not_material_calibration",
        "claim_boundary": "One 216-sphere, six-wall clean-LBS preparation pilot. No fibre, representative-volume, flow, permeability, deformation, migration, or production-parametric claim.",
        "target_state": {
            "particle_count": 216,
            "void_ratio": 0.744,
            "isotropic_stress_pa_compression_positive": 100.0,
        },
        "preparation": {
            "initial_radius_scale": 0.78,
            "growth_blocks": 300,
            "steps_per_growth_block": 500,
            "preparation_friction_coefficient": 0.0,
            "newton_damping": 0.9,
            "timestep_safety_coefficient": 0.3,
        },
        "frictionless_hold": {
            "minimum_blocks": 20,
            "maximum_blocks": 400,
            "steps_per_block": 500,
            "maximum_unbalanced_force": 0.10,
            "maximum_normalized_kinetic_energy_pV": 1.0e-4,
        },
        "stress_restoration": {
            "restored_friction_coefficient": 0.60,
            "controller_maximum_wall_velocity_m_s": 1.0e-3,
            "minimum_blocks": 20,
            "maximum_blocks": 2400,
            "steps_per_block": 500,
            "required_consecutive_pass_blocks": 5,
            "newton_damping": 0.85,
            "timestep_safety_coefficient": 0.3,
        },
        "acceptance": {
            "required_particle_count": 216,
            "maximum_relative_radius_error": 1.0e-12,
            "maximum_void_ratio_error": 0.02,
            "maximum_relative_mean_wall_stress_error": 0.05,
            "maximum_principal_wall_stress_error": 0.10,
            "maximum_unbalanced_force": 0.06,
            "maximum_normalized_kinetic_energy_pV": 1.0e-6,
            "maximum_penetration_over_smaller_radius": 0.02,
            "hard_guard_penetration_over_smaller_radius": 0.05,
            "minimum_sand_coordination_excluding_rattlers": 3.0,
            "maximum_sand_rattler_fraction": 0.35,
        },
        "sources": {
            "input_state": binding(input_state),
            "stage26o_checkpoint": binding(stage26o_checkpoint),
            "stage26q_nonacceptance": binding(stage26q),
            "stage26r_nonacceptance": binding(stage26r),
            "stage26v_checkpoint": binding(stage26v),
            "research_contract": binding(CONTRACT),
            "runner": binding(RUNNER),
            "expected_yade_version": "2022.01a",
        },
        "authority": {
            "clean_dense_preparation_pilot_authorized": True,
            "pore_throat_extraction_authorized_after_acceptance": True,
            "pore_throat_extraction_authorized": False,
            "fibre_execution_authorized": False,
            "mobile_sand_execution_authorized": False,
            "flow_execution_authorized": False,
            "permeability_claim_authorized": False,
            "production_parametric_study_authorized": False,
        },
    }
    OUT.mkdir(parents=True, exist_ok=False)
    path = OUT / "config.json"
    path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(path)
    print(sha256(path))


if __name__ == "__main__":
    main()
