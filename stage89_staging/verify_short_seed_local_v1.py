"""Predeclared Stage88 failed local A/B retest with a 64-sweep PGS seed.

Preserves the failed zero-LM evidence and the existing 1e-9 component gate.
All cases are local numerical restarts, with no release interpretation.
"""
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage41_staging"),
                str(ROOT / "stage81_staging"), str(ROOT / "stage89_staging")]
import matrix_case_v1
import geometry_exact_v1
import trajectory_combined_scalar_v1 as baseline
import trajectory_short_pgs_seed_v1 as candidate

DESIGN = ROOT / "stage86_designs/near_outlet_conditional_pilot_v1.json"
CASE = ROOT / "stage86_runs/near_outlet_conditional_20260913/seed2_pair_01/s2_prolate_ar4.json"
PRIOR = ROOT / "stage88_evaluations/local_direct_lm_transfer_03/results.json"
OUT = ROOT / "stage89_evaluations/short_seed_local_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_value(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(type(value).__name__)


def dump(path, record):
    Path(path).write_text(json.dumps(record, indent=2, default=json_value))


def run_local(module, config, previous, seed, horizon, budget):
    field, old_geometry, length, _, _ = matrix_case_v1.load(seed)
    geometry = geometry_exact_v1.GrainGeometry.from_geometry(old_geometry)
    a, b, _ = config["prolate_semiaxes_m"]
    return module.integrate(
        field, geometry, previous["position_m"], previous["orientation"],
        previous["velocity_generalized"], a, b,
        config["dynamic_viscosity_Pa_s"], config["particle_density_kg_m3"],
        config["fluid_density_kg_m3"], config["gravity_m_s2"],
        config["friction_coefficient"], length, horizon,
        added_mass_fraction=config["added_mass_fraction"],
        cutoff_ratio=0.2, roughness_ratio=0.01,
        displacement_fraction=config["numerics"]["displacement_fraction"],
        relaxation_fraction=config["numerics"]["relaxation_fraction"],
        angle_limit=config["numerics"]["angle_limit_rad"],
        max_dt=config["numerics"]["max_dt_s"], wall_budget=budget,
        trap_reference_speed=config["target_mean_interstitial_velocity_m_s"],
        trap_dwell_time=config["trap"]["dwell_time_s"],
        trap_speed_ratio=config["trap"]["speed_ratio"],
        trap_drift_over_minor_radius=config["trap"]["drift_over_minor_radius"],
        stop_on_trap=config["trap"]["absorbing"],
        reynolds_limit=config["numerics"]["reynolds_limit"])


def compare(old, new, horizon):
    differences = {key: float(np.max(np.abs(np.asarray(old[key])-np.asarray(new[key]))))
                   for key in ("position_m", "orientation", "velocity_generalized")}
    checks = {
        "same_completed_horizon": bool(old["status"] == new["status"] == "present_at_horizon"
                                        and abs(old["time_s"]-horizon) <= 1e-12
                                        and abs(new["time_s"]-horizon) <= 1e-12),
        "existing_component_tolerance": max(differences.values()) <= 1e-9,
        "same_steps": old["steps"] == new["steps"],
        "candidate_health": bool(new["minimum_gap_m"] >= -5e-10
                                 and new["max_contact_residual"] <= 1e-8
                                 and new["max_force_residual"] <= 1e-8
                                 and new["max_momentum_residual"] <= 1e-8
                                 and new["max_reynolds"] <= 3),
    }
    return checks, differences


def main():
    prior = json.loads(PRIOR.read_text())
    completion = json.loads((PRIOR.parent / "completion.json").read_text())
    if completion["status"] != "complete_failed" or completion["results_sha256"] != sha(PRIOR):
        raise RuntimeError("Stage88 failed diagnostic lineage changed")
    for path, digest in {**prior["input_hashes"], **prior["source_hashes"]}.items():
        if sha(path) != digest:
            raise RuntimeError(f"Stage88 lineage drift: {path}")
    OUT.mkdir(parents=True, exist_ok=False)
    config = json.loads(DESIGN.read_text())
    previous = json.loads(CASE.read_text())["result"]
    sources = [Path(__file__), Path(candidate.__file__), Path(baseline.__file__),
               Path(candidate.stage50.__file__), Path(candidate.stage53.__file__),
               Path(candidate.portfolio.__file__), Path(matrix_case_v1.__file__),
               Path(geometry_exact_v1.__file__)]
    protocol = {"horizon_s": 0.01, "wall_budget_s_per_arm": 30.,
                "component_tolerance": 1e-9, "pgs_seed_sweeps": 64,
                "input_hashes": {str(p): sha(p) for p in (DESIGN, CASE, PRIOR)},
                "source_hashes": {str(p): sha(p) for p in sources},
                "claim_boundary": "Local numerical restart only; no release observation."}
    dump(OUT / "protocol.json", protocol)
    old = run_local(baseline, config, previous, 2, .01, 30.)
    dump(OUT / "baseline.json", old)
    new = run_local(candidate, config, previous, 2, .01, 30.)
    dump(OUT / "candidate.json", new)
    checks, differences = compare(old, new, .01)
    checks["candidate_exercised"] = new["short_pgs_seed_stats"]["accepted"] > 0
    record = {"passed": all(checks.values()), "checks": checks, "differences": differences,
              "baseline_runtime_s": old["runtime_seconds"],
              "candidate_runtime_s": new["runtime_seconds"],
              "candidate_counts": new["short_pgs_seed_stats"],
              "artifact_hashes": {str(OUT / name): sha(OUT / name)
                                  for name in ("protocol.json", "baseline.json", "candidate.json")},
              "input_hashes": protocol["input_hashes"],
              "source_hashes": protocol["source_hashes"],
              "environment": {"python": platform.python_version(), "numpy": np.__version__}}
    dump(OUT / "results.json", record)
    dump(OUT / "completion.json", {"status": "complete_passed" if record["passed"] else "complete_failed",
                                   "results_sha256": sha(OUT / "results.json")})
    print(json.dumps(record, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
