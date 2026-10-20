#!/usr/bin/env python3
"""Freeze the Stage26t contact verification design."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
OUT = ROOT / "stage26_designs" / "stage26t_sand_fibre_contact_20260820" / "contact_design_01"
CONTRACT = ROOT / "stage26_staging" / "STAGE26T_SAND_FIBRE_CONTACT_RESEARCH_CONTRACT.md"
RUNNER = ROOT / "stage26_staging" / "run_stage26t_sand_fibre_contact_v1.py"
PROBE = ROOT / "stage26_runs" / "stage26t_sand_fibre_contact_20260820" / "contact_probe_01" / "probe.json"
STAGE26S = ROOT / "stage26_evaluations" / "stage26s_flexible_fibre_cantilever_20260819" / "cantilever_evaluation_03" / "checkpoint_manifest.json"
STAGE26P = ROOT / "stage26_checkpoints" / "stage26p_single_fibre_mechanism_20260818" / "mechanism_checkpoint_01" / "checkpoint_manifest.json"


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


if OUT.exists(): raise RuntimeError(f"refusing to overwrite {OUT}")
for path in (CONTRACT, RUNNER, PROBE, STAGE26S, STAGE26P):
    if not path.is_file(): raise RuntimeError(f"missing {path}")
probe = json.loads(PROBE.read_text(encoding="utf-8"))
if not probe.get("passed"): raise RuntimeError("contact probe did not pass")
config = {
    "schema": "lbs.stage26t-sand-fibre-contact-design.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(), "case_id": "stage26t_contact_01",
    "fibre": {"length_m": 0.9e-3, "diameter_m": 100e-6, "node_count": 37,
              "young_pa": 53e6, "poisson": 0.30, "density_kg_m3": 940.0,
              "property_status": "nominal_numerical_reference_not_polymer_calibration"},
    "sand": {"diameter_m": 0.0008225865451029433, "density_kg_m3": 2650.0,
             "shape": "single_fixed_sphere"},
    "contact": {"young_pa": 53e6, "poisson": 0.25, "friction_coefficient": 0.0,
                "status": "frictionless_code_verification_not_contact_calibration"},
    "loading": {"initial_clearance_m": 0.2e-6, "peak_sphere_travel_m": 4.8e-6,
                "load_duration_s": 0.75e-3, "peak_hold_duration_s": 0.75e-3,
                "unload_duration_s": 0.75e-3, "final_hold_duration_s": 0.75e-3},
    "numerics": {"time_step_safety_factors": [0.20, 0.10, 0.05], "newton_damping": 0.70},
    "outputs": {"sample_duration_s": 0.05e-3},
    "analysis": {"hold_average_window_s": 0.20e-3},
    "gates": {"maximum_endpoint_displacement_m": 1e-15, "maximum_peak_deflection_over_length": 0.02,
              "maximum_peak_hold_node_speed_m_s": 5e-6, "maximum_fine_beam_theory_relative_error": 0.10,
              "maximum_medium_to_fine_relative_change": 0.02, "maximum_recovery_residual_over_peak": 0.01},
    "authority": {"contact_benchmark_execution_authorized": True, "multigrain_caging_authorized": False,
                  "sand_mixture_authorized": False, "periodic_grid_connection_authorized": False,
                  "flow_authorized": False, "permeability_claim_authorized": False},
    "source_hashes": {"contract": sha(CONTRACT), "runner": sha(RUNNER), "contact_probe": sha(PROBE),
                      "stage26s_checkpoint": sha(STAGE26S), "stage26p_checkpoint": sha(STAGE26P)},
    "claim_boundary": "Nonperiodic frictionless single-sphere/single-fibre contact and beam verification only; no calibrated polymer/contact, multigrain caging, mixture, flow, or permeability claim.",
}
OUT.mkdir(parents=True)
path = OUT / "config.json"
path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"config": str(path), "sha256": sha(path)}, indent=2))
