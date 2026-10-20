from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
OUT = ROOT / "stage26_designs" / "stage26r_periodic_radius_restoration_20260819" / "clean_design_01"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": str(path), "sha256": sha256(path)}


def main() -> None:
    checkpoint = ROOT / "stage25_checkpoints" / "stage25a_pure_sand_mechanics_20260813" / "checkpoint_01" / "checkpoint_manifest.json"
    probe = ROOT / "stage26_runs" / "stage26r_periodic_radius_restoration_20260819" / "stage25_state_probe_01" / "probe.json"
    nonacceptance = ROOT / "stage26_evaluations" / "stage26q_density_geometry_flexure_20260818" / "clean_density_controller_evaluation_04" / "evaluation.json"
    contract = ROOT / "stage26_staging" / "STAGE26R_PERIODIC_RADIUS_RESTORATION_CONTRACT.md"
    runner = ROOT / "stage26_staging" / "run_stage26r_periodic_radius_restoration_v1.py"
    checkpoint_data = json.loads(checkpoint.read_text(encoding="utf-8"))
    probe_data = json.loads(probe.read_text(encoding="utf-8"))
    failure_data = json.loads(nonacceptance.read_text(encoding="utf-8"))
    if checkpoint_data.get("passed") is not True or probe_data.get("passed") is not True or failure_data.get("passed") is not False:
        raise RuntimeError("required Stage26r evidence state is invalid")
    input_state = Path(checkpoint_data["evidence"]["checkpoint_path"])
    input_state_hash = checkpoint_data["evidence"]["checkpoint_sha256"]
    if sha256(input_state) != input_state_hash:
        raise RuntimeError("Stage25 state hash mismatch")
    cfg = {
        "schema": "lbs.stage26r-periodic-radius-restoration-config.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "authorized_stage26r_clean_periodic_radius_restoration",
        "research_role": "clean_periodic_preparation_algorithm_qualification_not_physical_pluviation",
        "claim_boundary": "One clean 216-sphere periodic shrink-and-radius-restoration benchmark. No fibre, representative-volume, flow, permeability, deformation, migration, or production-parametric claim.",
        "target_state": {
            "void_ratio": float(checkpoint_data["metrics"]["void_ratio"]),
            "isotropic_stress_pa_compression_positive": 100.0,
            "particle_count": 216,
        },
        "restoration": {
            "initial_radius_scale": 0.80,
            "growth_blocks": 200,
            "steps_per_growth_block": 500,
            "preparation_friction_coefficient": 0.30,
            "restored_friction_coefficient": 0.60,
            "newton_damping": 0.90,
            "timestep_safety_coefficient": 0.30,
        },
        "hold": {
            "minimum_blocks": 20,
            "maximum_blocks": 1600,
            "steps_per_block": 500,
            "required_consecutive_pass_blocks": 5,
        },
        "acceptance": {
            "required_particle_count": 216,
            "maximum_relative_radius_error": 1.0e-12,
            "maximum_relative_cell_dimension_change": 1.0e-12,
            "maximum_void_ratio_error": 0.002,
            "maximum_relative_mean_stress_error": 0.05,
            "maximum_principal_stress_error": 0.10,
            "maximum_unbalanced_force": 0.03,
            "maximum_normalized_kinetic_energy_pV": 1.0e-5,
            "maximum_overlap_over_smaller_radius": 0.02,
            "hard_guard_overlap_over_smaller_radius": 0.05,
            "minimum_coordination_excluding_rattlers": 3.0,
            "maximum_rattler_fraction": 0.35,
        },
        "sources": {
            "stage25_checkpoint": bind(checkpoint),
            "stage25_state_probe": bind(probe),
            "stage26q_nonacceptance": bind(nonacceptance),
            "research_contract": bind(contract),
            "runner": bind(runner),
            "input_state": {"path": str(input_state), "sha256": input_state_hash},
            "expected_yade_version": "2022.01a",
        },
        "authority": {
            "clean_radius_restoration_authorized": True,
            "single_fibre_design_authorized_after_clean_pass": True,
            "fibre_execution_authorized": False,
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
