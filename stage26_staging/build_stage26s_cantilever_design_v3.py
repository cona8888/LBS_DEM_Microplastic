#!/usr/bin/env python3
"""Freeze the Stage26s three-mesh cantilever design."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
OUT = ROOT / "stage26_designs" / "stage26s_flexible_fibre_cantilever_20260819" / "clean_design_03"
CONTRACT = ROOT / "stage26_staging" / "STAGE26S_FLEXIBLE_FIBRE_CANTILEVER_RESEARCH_CONTRACT.md"
RUNNER = ROOT / "stage26_staging" / "run_stage26s_flexible_fibre_cantilever_v3.py"
PROBE = ROOT / "stage26_runs" / "stage26s_flexible_fibre_cantilever_20260819" / "grid_connection_probe_01" / "probe.json"
STAGE26R = ROOT / "stage26_evaluations" / "stage26r_periodic_radius_restoration_20260819" / "clean_radius_restoration_evaluation_05" / "checkpoint_manifest.json"
ATTEMPT01_FAILURE = ROOT / "stage26_evaluations" / "stage26s_flexible_fibre_cantilever_20260819" / "cantilever_01_failure" / "failure.json"
ATTEMPT02_FAILURE = ROOT / "stage26_evaluations" / "stage26s_flexible_fibre_cantilever_20260819" / "cantilever_02_failure" / "failure.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    if OUT.exists():
        raise RuntimeError(f"refusing to overwrite {OUT}")
    for path in (CONTRACT, RUNNER, PROBE, STAGE26R, ATTEMPT01_FAILURE, ATTEMPT02_FAILURE):
        if not path.is_file():
            raise RuntimeError(f"missing source {path}")
    probe = json.loads(PROBE.read_text(encoding="utf-8"))
    if not probe.get("passed"):
        raise RuntimeError("grid-connection stiffness probe did not pass")
    p = probe["physics"]
    ref = probe["reference_stiffness"]
    if abs(p["kn"] / ref["EA_over_L_n_per_m"] - 1.0) > 1.0e-12:
        raise RuntimeError("YADE kn does not bind to EA/L")
    if abs(p["kr"] / ref["EI_over_L_n_m_per_rad"] - 1.0) > 1.0e-12:
        raise RuntimeError("YADE kr does not bind to EI/L")

    config = {
        "schema": "lbs.stage26s-flexible-fibre-cantilever-design.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "case_id": "stage26s_clean_cantilever_03",
        "geometry": {"length_m": 0.9e-3, "diameter_m": 100.0e-6},
        "material": {
            "young_pa": 53.0e6,
            "poisson": 0.30,
            "density_kg_m3": 940.0,
            "status": "nominal_numerical_reference_not_polymer_calibration",
        },
        "loading": {
            "target_tip_deflection_over_length": 0.01,
            "ramp_duration_s": 7.5e-4,
            "settle_block_duration_s": 1.0e-4,
            "maximum_duration_s": 4.0e-3,
            "gravity_m_s2": [0.0, 0.0, 0.0],
        },
        "meshes": [{"node_count": n} for n in (19, 37, 73)],
        "numerics": {
            "newton_damping": 0.70,
            "time_step_safety_factor": 0.10,
            "required_consecutive_equilibrium_blocks": 4,
        },
        "gates": {
            "maximum_tip_speed_m_s": 5.0e-6,
            "maximum_tip_force_residual_over_applied": 2.0e-3,
            "maximum_clamp_displacement_m": 1.0e-15,
            "maximum_terminal_deflection_over_length": 0.05,
            "maximum_37_to_73_relative_change": 0.05,
            "maximum_73_node_analytical_relative_error": 0.10,
        },
        "authority": {
            "standalone_cantilever_execution_authorized": True,
            "sand_fibre_mixture_authorized": False,
            "periodic_grid_connection_authorized": False,
            "polymer_calibration_authorized": False,
            "flow_authorized": False,
        },
        "source_hashes": {
            "contract": sha256(CONTRACT),
            "runner": sha256(RUNNER),
            "grid_connection_probe": sha256(PROBE),
            "stage26r_checkpoint": sha256(STAGE26R),
            "attempt01_failure": sha256(ATTEMPT01_FAILURE),
            "attempt02_failure": sha256(ATTEMPT02_FAILURE),
        },
        "claim_boundary": "Standalone nonperiodic small-deflection code verification only; no sand, calibrated polymer, contact, flow, or permeability claim.",
    }
    OUT.mkdir(parents=True)
    path = OUT / "config.json"
    path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"config": str(path), "sha256": sha256(path)}, indent=2))


if __name__ == "__main__":
    main()
