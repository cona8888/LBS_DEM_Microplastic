from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
OUT = (
    ROOT
    / "stage26_checkpoints"
    / "stage26p_single_fibre_mechanism_20260818"
    / "mechanism_checkpoint_01"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def binding(path: Path) -> dict:
    return {"path": str(path), "sha256": sha256(path)}


def main() -> None:
    layered_config_path = (
        ROOT
        / "stage26_designs"
        / "stage26o_gravity_joint_deposition_20260818"
        / "two_fibre_layered_design_03"
        / "mixture_config.json"
    )
    layered_config = load(layered_config_path)
    placement_path = Path(layered_config["sources"]["placement"])
    placement = load(placement_path)

    d50 = float(layered_config["sand"]["D50_m"])
    fibre_diameter = 2.0 * float(layered_config["fibre"]["member_radius_m"])
    ideal_three_sphere_throat = (2.0 / math.sqrt(3.0) - 1.0) * d50
    ideal_tetrahedral_void_diameter = (math.sqrt(6.0) / 2.0 - 1.0) * d50

    fibre_geometry = []
    for fibre in placement["fibres"]:
        points = fibre["member_centres_m"]
        segment_lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
        length = sum(segment_lengths)
        fibre_geometry.append(
            {
                "fibre_index": int(fibre["fibre_index"]),
                "member_count": len(points),
                "minimum_member_spacing_m": min(segment_lengths),
                "maximum_member_spacing_m": max(segment_lengths),
                "centreline_length_m": length,
                "centreline_length_over_D50": length / d50,
                "centreline_length_over_diameter": length / fibre_diameter,
            }
        )

    stage26n = (
        ROOT
        / "stage26_evaluations"
        / "stage26n_safe_release_20260818"
        / "pilot_evaluation_01"
        / "evaluation.json"
    )
    uniform = (
        ROOT
        / "stage26_evaluations"
        / "stage26o_gravity_joint_deposition_20260818"
        / "two_fibre_mixture_evaluation_01"
        / "evaluation.json"
    )
    layered = (
        ROOT
        / "stage26_evaluations"
        / "stage26o_gravity_joint_deposition_20260818"
        / "two_fibre_layered_evaluation_03"
        / "evaluation.json"
    )
    analytical = (
        ROOT
        / "stage26_evaluations"
        / "stage26p_single_fibre_mechanism_20260818"
        / "analytical_buoyancy_check_01"
        / "analytical_check.json"
    )
    force_smoke = (
        ROOT
        / "stage26_runs"
        / "stage26p_single_fibre_mechanism_20260818"
        / "force_sign_smoke_01"
        / "result.json"
    )

    evidence_paths = {
        "stage26n_safe_release_evaluation": stage26n,
        "stage26o_uniform_mixture_evaluation": uniform,
        "stage26o_layered_mixture_evaluation": layered,
        "stage26p_analytical_buoyancy_check": analytical,
        "stage26p_yade_force_sign_smoke": force_smoke,
        "layered_config": layered_config_path,
        "fibre_placement": placement_path,
    }
    for path in evidence_paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)

    status_checks = {
        "stage26n_release_numerically_stable_but_caging_failed": (
            load(stage26n).get("status")
            == "numerically_stable_release_but_mobile_caging_failed"
        ),
        "uniform_joint_deposition_nonqualification_preserved": (
            load(uniform).get("status") == "preserved_nonqualification_classified"
        ),
        "layered_joint_deposition_nonqualification_preserved": (
            load(layered).get("status")
            == "layered_preparation_nonqualification_preserved"
        ),
        "analytical_buoyancy_check_passed": load(analytical).get("passed") is True,
        "yade_force_sign_smoke_passed": load(force_smoke).get("passed") is True,
        "fibre_diameter_smaller_than_ideal_D50_three_sphere_throat": (
            fibre_diameter < ideal_three_sphere_throat
        ),
        "all_fibre_geometries_exact_37_members": all(
            row["member_count"] == 37 for row in fibre_geometry
        ),
    }

    manifest = {
        "schema": "lbs.stage26p-single-fibre-mechanism-checkpoint.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "mechanism_checkpoint_passed_full_mixture_remains_blocked",
        "passed": all(status_checks.values()),
        "research_question": (
            "Why do exact rigid F37 fibres fail to remain embedded in the current "
            "216-sphere LBS reconstruction?"
        ),
        "claim_boundary": (
            "Mechanism classification for the existing wall-bounded 216-sphere, "
            "rigid-F37 development model only. The ideal three-equal-sphere throat "
            "is a reference geometry, not a measured throat distribution. No "
            "flexible-fibre calibration, representative-volume, flow, permeability, "
            "migration, deformation, or production-parametric claim."
        ),
        "status_checks": status_checks,
        "geometry": {
            "sand_D50_m": d50,
            "fibre_diameter_m": fibre_diameter,
            "fibre_diameter_over_D50": fibre_diameter / d50,
            "ideal_three_equal_D50_sphere_throat_diameter_m": ideal_three_sphere_throat,
            "fibre_diameter_over_ideal_throat": fibre_diameter / ideal_three_sphere_throat,
            "ideal_tetrahedral_void_diameter_m": ideal_tetrahedral_void_diameter,
            "fibre_geometry": fibre_geometry,
            "interpretation": (
                "The 100 um rigid fibre cross-section is smaller than the ideal "
                "three-D50-sphere aperture (about 127.3 um). Together with the "
                "observed zero terminal contacts, this provides a physically "
                "consistent route for pore threading in this spherical packing."
            ),
        },
        "mechanism_conclusion": {
            "primary_current_model_limitation": (
                "The fibre-to-pore-throat size ratio and spherical-sand pore geometry "
                "do not create persistent cages for both fibres."
            ),
            "secondary_missing_physics": (
                "Whole-fibre bending stiffness is not represented: the configured "
                "Young parameter controls contact stiffness only because F37 is a "
                "rigid clump."
            ),
            "submerged_force_direction": (
                "A 940 kg/m3 polyethylene fibre in 1000 kg/m3 water has net upward "
                "buoyancy; the analytical and YADE one-clump checks agree."
            ),
            "why_another_rigid_full_mixture_is_not_justified": (
                "Stable release, uniform co-deposition, and layered pluviation have "
                "already failed to form persistent simultaneous cages."
            ),
        },
        "recommended_next_stage": {
            "stage": "flexural_and_pore_geometry_model_form_screen_design",
            "required_inputs": [
                "polymer-specific flexural rigidity EI or bending-test calibration",
                "measured or image-derived LBS particle angularity/pore-throat distribution",
                "fibre diameter and length distribution for the target microplastic",
            ],
            "first_executable_benchmark": (
                "Single flexible or bonded-chain fibre in a frozen, measured throat "
                "geometry, calibrated against force-deflection before any mixture run."
            ),
        },
        "authority": {
            "flexural_parameter_screen_design_authorized": True,
            "single_fibre_force_deflection_benchmark_execution_authorized": False,
            "another_rigid_full_mixture_run_authorized": False,
            "flow_execution_authorized": False,
            "permeability_claim_authorized": False,
            "production_parametric_study_authorized": False,
        },
        "evidence": {name: binding(path) for name, path in evidence_paths.items()},
        "builder": binding(Path(__file__).resolve()),
    }

    if not manifest["passed"]:
        raise RuntimeError(json.dumps(status_checks, indent=2))

    OUT.mkdir(parents=True, exist_ok=False)
    out_path = OUT / "checkpoint_manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(out_path)
    print(sha256(out_path))


if __name__ == "__main__":
    main()
