#!/usr/bin/env python3
"""Freeze the Stage26x paired periodic fixed-sand flexible-fibre pilot."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
OUT = ROOT / "stage26_designs" / "stage26x_periodic_pore_geometry_20260823" / "fixed_sand_design_01"
SEARCH = ROOT / "stage26_designs" / "stage26x_periodic_pore_geometry_20260823" / "path_search_01" / "path_candidates.json"
CONTRACT = ROOT / "stage26_staging" / "STAGE26X_PERIODIC_PORE_GEOMETRY_CONTRACT.md"
RUNNER = ROOT / "stage26_staging" / "run_stage26x_periodic_fixed_sand_fibre_v1.py"
STATE = ROOT / "stage25_runs" / "stage25a_pure_sand_mechanics_20260813" / "qualification_04" / "mu_0.60" / "load_bearing_state.yade.gz"
NETWORK = ROOT / "stage26_network_exports" / "stage26b_revision2_stage25_network_20260816" / "export_04" / "network.json"
STAGE26S = ROOT / "stage26_evaluations" / "stage26s_flexible_fibre_cantilever_20260819" / "cantilever_evaluation_03" / "checkpoint_manifest.json"
STAGE26T = ROOT / "stage26_evaluations" / "stage26t_sand_fibre_contact_20260820" / "contact_evaluation_01" / "checkpoint_manifest.json"
STAGE26U = ROOT / "stage26_evaluations" / "stage26u_three_grain_throat_20260820" / "throat_evaluation_01" / "checkpoint_manifest.json"
STAGE26W = ROOT / "stage26_evaluations" / "stage26w_dense_wall_shrink_regrow_20260823" / "evaluation_01" / "checkpoint_manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path):
    if not path.is_file():
        raise RuntimeError(f"missing source: {path}")
    return {"path": str(path).replace("C:\\", "/mnt/c/").replace("\\", "/"), "sha256": sha(path)}


if OUT.exists():
    raise RuntimeError(f"refusing to overwrite immutable Stage26x design: {OUT}")
search = json.loads(SEARCH.read_text(encoding="utf-8"))
lookup = {(int(item["face_index"]), float(item["orientation_sign"])): item for item in search["candidates"]}
constricted_source = lookup[(37527, 1.0)]
open_source = lookup[(37641, 1.0)]


def make_case(source, case_id, translation, plane_advance):
    direction = np.asarray(source["pull_direction"], dtype=float)
    rear = np.asarray(source["rear_m"], dtype=float) + direction * translation
    tip = np.asarray(source["tip_m"], dtype=float) + direction * translation
    plane = tip + direction * plane_advance
    return {
        "case_id": case_id,
        "source_face_index": int(source["face_index"]),
        "source_orientation_sign": float(source["orientation_sign"]),
        "source_face_body_ids": source["face_body_ids"],
        "rear_m": rear.tolist(),
        "tip_m": tip.tolist(),
        "pull_direction": direction.tolist(),
        "classification_plane_point_m": plane.tolist(),
        "analytical_local_throat_radius_m": float(source["throat_radius_m"]),
        "analytical_local_throat_to_fibre_radius_ratio": float(source["throat_to_fibre_radius_ratio"]),
        "source_first_contact_translation_m": source["first_sampled_contact_translation_m"],
        "source_distinct_near_grain_count": int(source["distinct_near_grain_count"]),
        "placement_forward_shift_m": translation,
        "predicted_contact_translation_after_placement_m": None if source["first_sampled_contact_translation_m"] is None else float(source["first_sampled_contact_translation_m"]) - translation,
        "role": "two_near_grain_downstream_obstacle" if case_id == "constricted" else "open_periodic_throat_control",
    }


target_contact = 80.0e-6
shift = float(constricted_source["first_sampled_contact_translation_m"]) - target_contact
cases = [make_case(constricted_source, "constricted", shift, target_contact), make_case(open_source, "open", 0.0, 0.25e-3)]
config = {
    "schema": "lbs.stage26x-periodic-fixed-sand-fibre-design.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "status": "authorized_stage26x_periodic_fixed_sand_fibre_pilot",
    "fibre": {"length_m": 0.9e-3, "diameter_m": 0.1e-3, "node_count": 37, "young_pa": 53e6, "poisson": 0.30, "density_kg_m3": 940.0, "property_status": "nominal_numerical_reference_not_polymer_calibration"},
    "contact": {"young_pa": 53e6, "poisson": 0.25, "friction_coefficient": 0.0},
    "loading": {"zero_load_hold_duration_s": 0.25e-3, "axial_pull_force_n": 1.0e-6, "force_ramp_duration_s": 0.5e-3, "pull_duration_s": 5.0e-3},
    "numerics": {"time_step_safety_factor": 0.20, "newton_damping": 0.70, "basis": "Stage26s/t/u verified flexible-fibre mechanics"},
    "outputs": {"sample_duration_s": 0.05e-3, "terminal_record_count": 5},
    "gates": {"maximum_hold_drift_m": 1.0e-6, "maximum_penetration_over_fibre_radius": 0.01, "minimum_open_nodes_beyond_plane": 4, "minimum_open_advance_m": 0.25e-3, "maximum_caged_advance_m": 0.12e-3, "minimum_response_contrast_m": 0.05e-3},
    "cases": cases,
    "sources": {
        "source_state": bind(STATE),
        "network": bind(NETWORK),
        "path_search": bind(SEARCH),
        "contract": bind(CONTRACT),
        "runner": bind(RUNNER),
        "stage26s_checkpoint": bind(STAGE26S),
        "stage26t_checkpoint": bind(STAGE26T),
        "stage26u_checkpoint": bind(STAGE26U),
        "stage26w_checkpoint": bind(STAGE26W),
        "expected_yade_version": "2022.01a",
    },
    "authority": {"periodic_fixed_sand_fibre_pilot_authorized": True, "mobile_sand_execution_authorized": False, "flow_authorized": False, "permeability_claim_authorized": False},
    "claim_boundary": "One paired fixed-sand flexible-fibre pilot in the accepted periodic 216-grain LBS geometry; no mobile sand, polymer calibration, flow, permeability, deformation, or production claim.",
}
OUT.mkdir(parents=True, exist_ok=False)
path = OUT / "config.json"
path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(path)
print(sha(path))
print(json.dumps(cases, indent=2))
