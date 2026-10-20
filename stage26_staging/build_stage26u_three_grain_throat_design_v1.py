#!/usr/bin/env python3
"""Freeze Stage26u geometry and run design."""

import hashlib, json, math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
OUT = ROOT / "stage26_designs" / "stage26u_three_grain_throat_20260820" / "throat_design_01"
CONTRACT = ROOT / "stage26_staging" / "STAGE26U_THREE_GRAIN_THROAT_RESEARCH_CONTRACT.md"
RUNNER = ROOT / "stage26_staging" / "run_stage26u_three_grain_throat_v1.py"
STAGE26T = ROOT / "stage26_evaluations" / "stage26t_sand_fibre_contact_20260820" / "contact_evaluation_01" / "checkpoint_manifest.json"
STAGE26S = ROOT / "stage26_evaluations" / "stage26s_flexible_fibre_cantilever_20260819" / "cantilever_evaluation_03" / "checkpoint_manifest.json"
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
if OUT.exists(): raise RuntimeError(f"refusing to overwrite {OUT}")
for p in (CONTRACT, RUNNER, STAGE26T, STAGE26S):
    if not p.is_file(): raise RuntimeError(f"missing {p}")
df = 100e-6; factor = 2.0 / math.sqrt(3.0) - 1.0
ratios = [0.8, 1.0, 0.00012725458139095392 / df]
cases = []
for ratio in ratios:
    throat = ratio * df; sand_diameter = throat / factor
    cases.append({"case_id": "ratio_%s" % str(round(ratio, 6)).replace(".", "p"),
                  "throat_to_fibre_diameter_ratio": ratio, "throat_diameter_m": throat,
                  "sand_diameter_m": sand_diameter})
config = {
 "schema": "lbs.stage26u-three-grain-throat-design.v1", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
 "case_id": "stage26u_throat_screen_01",
 "fibre": {"length_m": 0.9e-3, "diameter_m": df, "node_count": 37, "young_pa": 53e6, "poisson": 0.30,
           "density_kg_m3": 940.0, "property_status": "nominal_numerical_reference_not_polymer_calibration"},
 "sand": {"density_kg_m3": 2650.0, "shape": "three_fixed_mutually_tangent_equal_spheres"},
 "geometry": {"initial_tip_x_m": -0.15e-3, "transverse_imperfection_m": 2e-6,
              "throat_plane_x_m": 0.0, "analytical_tangent_throat_factor": factor},
 "contact": {"young_pa": 53e6, "poisson": 0.25, "friction_coefficient": 0.0},
 "loading": {"axial_pull_force_n": 1e-6, "force_ramp_duration_s": 0.5e-3, "total_duration_s": 5e-3},
 "numerics": {"time_step_safety_factor": 0.20, "newton_damping": 0.70,
              "basis": "Stage26t three-level convergence accepted this factor"},
 "outputs": {"sample_duration_s": 0.05e-3}, "analysis": {"terminal_record_count": 5},
 "cases": cases,
 "gates": {"maximum_penetration_over_fibre_radius": 0.01, "maximum_blocked_leading_advance_m": 0.12e-3,
           "minimum_passable_nodes_beyond_throat": 4, "minimum_passable_leading_advance_m": 0.25e-3,
           "minimum_passage_contrast_m": 0.15e-3},
 "authority": {"three_grain_throat_execution_authorized": True, "full_216_grain_integration_authorized": False,
               "periodic_grid_connection_authorized": False, "flow_authorized": False,
               "permeability_claim_authorized": False},
 "source_hashes": {"contract": sha(CONTRACT), "runner": sha(RUNNER), "stage26t_checkpoint": sha(STAGE26T),
                   "stage26s_checkpoint": sha(STAGE26S)},
 "claim_boundary": "Deterministic nonperiodic frictionless three-tangent-sphere throat mechanism screen only; no measured LBS pore distribution, calibrated material/contact, bulk mixture, flow, or permeability claim."
}
OUT.mkdir(parents=True); path = OUT / "config.json"
path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"config": str(path), "sha256": sha(path), "cases": cases}, indent=2))
