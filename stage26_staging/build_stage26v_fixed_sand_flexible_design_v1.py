#!/usr/bin/env python3
"""Freeze the paired Stage26v fixed-sand flexible-fibre pilot design."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
OUT = ROOT / "stage26_designs" / "stage26v_216_flexible_fibre_integration_20260823" / "fixed_sand_design_01"
GEOMETRY = ROOT / "stage26_runs" / "stage26v_216_flexible_fibre_integration_20260823" / "geometry_export_02" / "geometry.json"
SEARCH = ROOT / "stage26_designs" / "stage26v_216_flexible_fibre_integration_20260823" / "path_search_02" / "path_candidates.json"
CONTRACT = ROOT / "stage26_staging" / "STAGE26V_216_GRAIN_FLEXIBLE_FIBRE_RESEARCH_CONTRACT.md"
ADDENDUM = ROOT / "stage26_staging" / "STAGE26V_PATH_SELECTION_ADDENDUM.md"
RUNNER = ROOT / "stage26_staging" / "run_stage26v_fixed_sand_flexible_pilot_v1.py"
STAGE26S = ROOT / "stage26_evaluations" / "stage26s_flexible_fibre_cantilever_20260819" / "cantilever_evaluation_03" / "checkpoint_manifest.json"
STAGE26T = ROOT / "stage26_evaluations" / "stage26t_sand_fibre_contact_20260820" / "contact_evaluation_01" / "checkpoint_manifest.json"
STAGE26U = ROOT / "stage26_evaluations" / "stage26u_three_grain_throat_20260820" / "throat_evaluation_01" / "checkpoint_manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


if OUT.exists():
    raise RuntimeError(f"refusing to overwrite immutable design {OUT}")
for path in (GEOMETRY, SEARCH, CONTRACT, ADDENDUM, RUNNER, STAGE26S, STAGE26T, STAGE26U):
    if not path.is_file():
        raise RuntimeError(f"missing source {path}")
search = load(SEARCH)
lookup = {int(item["face_index"]): item for item in search["candidates"]}
constricted_source = lookup[603]
open_source = lookup[1219]
target_contact = 80e-6
shift = float(constricted_source["first_sampled_contact_translation_m"]) - target_contact


def case_from(source, case_id, translation, plane_advance):
    direction = np.asarray(source["pull_direction"], dtype=float)
    rear = np.asarray(source["rear_m"], dtype=float) + direction * translation
    tip = np.asarray(source["tip_m"], dtype=float) + direction * translation
    plane = tip + direction * plane_advance
    return {
        "case_id": case_id,
        "source_face_index": int(source["face_index"]),
        "source_orientation_sign": float(source["orientation_sign"]),
        "rear_m": rear.tolist(),
        "tip_m": tip.tolist(),
        "pull_direction": direction.tolist(),
        "classification_plane_point_m": plane.tolist(),
        "analytical_local_throat_radius_m": float(source["throat_radius_m"]),
        "analytical_local_throat_to_fibre_radius_ratio": float(source["throat_to_fibre_radius_ratio"]),
        "source_initial_clearance_m": float(source["initial_minimum_surface_clearance_m"]),
        "source_minimum_swept_clearance_m": float(source["minimum_sampled_swept_clearance_m"]),
        "source_first_contact_translation_m": source["first_sampled_contact_translation_m"],
        "placement_forward_shift_m": translation,
        "predicted_contact_translation_after_placement_m": None if source["first_sampled_contact_translation_m"] is None else float(source["first_sampled_contact_translation_m"]) - translation,
        "role": "constricted_downstream_path" if case_id == "constricted" else "open_path_control",
    }


cases = [case_from(constricted_source, "constricted", shift, target_contact),
         case_from(open_source, "open", 0.0, 0.25e-3)]
config = {
    "schema": "lbs.stage26v-fixed-sand-flexible-pilot-design.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "status": "authorized_stage26v_fixed_sand_flexible_pilot",
    "source_state": "/mnt/c/MATDEM_MICROPLASTIC/stage26_runs/stage26o_gravity_joint_deposition_20260818/clean_control_13/qualified_clean_sand_wall_state.yade.gz",
    "fibre": {"length_m": 0.9e-3, "diameter_m": 0.1e-3, "node_count": 37,
              "young_pa": 53e6, "poisson": 0.30, "density_kg_m3": 940.0,
              "property_status": "nominal_numerical_reference_not_polymer_calibration"},
    "contact": {"young_pa": 53e6, "poisson": 0.25, "friction_coefficient": 0.0},
    "loading": {"zero_load_hold_duration_s": 0.25e-3, "axial_pull_force_n": 1e-6,
                "force_ramp_duration_s": 0.5e-3, "pull_duration_s": 5e-3},
    "numerics": {"time_step_safety_factor": 0.20, "newton_damping": 0.70,
                 "basis": "Stage26t convergence and Stage26u pull-through acceptance"},
    "outputs": {"sample_duration_s": 0.05e-3, "terminal_record_count": 5},
    "gates": {"maximum_hold_drift_m": 1e-6, "maximum_penetration_over_fibre_radius": 0.01,
              "minimum_open_nodes_beyond_plane": 4, "minimum_open_advance_m": 0.25e-3,
              "maximum_caged_advance_m": 0.12e-3, "minimum_response_contrast_m": 0.05e-3},
    "cases": cases,
    "source_hashes": {"geometry": sha(GEOMETRY), "path_search": sha(SEARCH), "contract": sha(CONTRACT),
                      "path_addendum": sha(ADDENDUM), "runner": sha(RUNNER),
                      "stage26s_checkpoint": sha(STAGE26S), "stage26t_checkpoint": sha(STAGE26T),
                      "stage26u_checkpoint": sha(STAGE26U),
                      "source_state": "809632150c383fc9deca2dfa76e012e05be12cb7415112c848663b5def49867f"},
    "authority": {"fixed_sand_flexible_pilot_authorized": True, "mobile_sand_execution_authorized": False,
                  "flow_authorized": False, "permeability_claim_authorized": False},
    "claim_boundary": "One paired fixed-sand flexible-fibre integration pilot in the accepted wall-bounded 216-grain geometry; no mobile-sand, polymer calibration, flow, permeability, deformation, or production claim.",
}
OUT.mkdir(parents=True)
path = OUT / "config.json"
path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"config": str(path), "sha256": sha(path), "cases": cases}, indent=2))
