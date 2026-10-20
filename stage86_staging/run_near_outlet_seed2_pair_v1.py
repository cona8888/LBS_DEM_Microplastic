"""Frozen near-outlet conditional first-passage feasibility, seed 2 only.

Stage81 solver and Stage68 physics are unchanged. The new geometry-only start
selection is frozen in Stage86 design; a different wall budget is a resource
cap, not a material parameter. No matrix-wide release estimate is made.
"""
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage68_staging"),
                str(ROOT / "stage81_staging")]
import matrix_case_v1
import verify_short_fibre_crossing_v1 as source
import trajectory_combined_scalar_v1 as candidate

DESIGN = ROOT / "stage86_designs" / "near_outlet_conditional_pilot_v1.json"
PARENT = ROOT / "stage55_designs" / "paired_three_packing_pilot_v1.json"
PREFLIGHT = ROOT / "stage85_evaluations" / "near_outlet_preflight_01" / "results.json"
PREFLIGHT_COMPLETION = PREFLIGHT.parent / "completion.json"
STAGE83 = ROOT / "stage83_runs" / "s2_full_window_pair_20260913" / "pair_01"
START = ROOT / "stage37_runs" / "stage4_farfield_bound_20260912" / "pilot_01" / "starts_s2.json"
OUT = ROOT / "stage86_runs" / "near_outlet_conditional_20260913" / "seed2_pair_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_frozen_design(config, parent, preflight):
    if config["status"] != "frozen_near_outlet_conditional_pilot":
        raise RuntimeError("unfrozen conditional design")
    if config["parent_stage55_design_sha256"] != sha(PARENT):
        raise RuntimeError("parent design hash drift")
    if config["stage85_preflight_results_sha256"] != sha(PREFLIGHT):
        raise RuntimeError("preflight hash drift")
    immutable_fields = ("shapes", "prolate_semiaxes_m", "particle_density_kg_m3",
                        "fluid_density_kg_m3", "dynamic_viscosity_Pa_s",
                        "gravity_m_s2", "friction_coefficient", "added_mass_fraction",
                        "target_mean_interstitial_velocity_m_s", "horizon_pore_volumes", "trap")
    if any(config[key] != parent[key] for key in immutable_fields):
        raise RuntimeError("conditional pilot altered physical design")
    for key in ("displacement_fraction", "relaxation_fraction", "angle_limit_rad",
                "max_dt_s", "reynolds_limit"):
        if config["numerics"][key] != parent["numerics"][key]:
            raise RuntimeError("conditional pilot altered numerical control")
    for packing in config["packings"]:
        seed = packing["seed"]
        eligible = [r for r in preflight["rows"] if r["seed"] == seed
                    and r["eligible_for_0p1pv_mean_travel"]]
        chosen = min(eligible, key=lambda r: (abs(r["paired_gap_pv"] - .05), r["start_id"]))
        if chosen["start_id"] != packing["start_id"] or abs(
                chosen["paired_gap_pv"] - packing["paired_gap_pv"]) > 1e-15:
            raise RuntimeError("near-outlet selection rule mismatch")


def checks(result, horizon, budget):
    resolved = ((result["status"] == "present_at_horizon" and
                 abs(result["time_s"] - horizon) <= 1e-12) or
                (result["status"] == "full_window_exit" and
                 0 < result["time_s"] <= horizon))
    return {key: bool(value) for key, value in {
        "resolved_conditional_observation": resolved,
        "no_failure_or_censoring": result["status"] not in {
            "numerical_failure", "incomplete_budget", "unresolved_model", "unresolved_field"},
        "clearance": result["minimum_gap_m"] >= -5e-10,
        "contact_closure": result["max_contact_residual"] <= 1e-8,
        "force_closure": result["max_force_residual"] <= 1e-8,
        "momentum_closure": result["max_momentum_residual"] <= 1e-8,
        "reynolds_envelope": result["max_reynolds"] <= 3,
        "within_budget": result["runtime_seconds"] <= budget,
        "nonabsorbing_dwell": result["dwell_is_absorbing"] is False,
    }.items()}


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    config = json.loads(DESIGN.read_text())
    parent = json.loads(PARENT.read_text())
    c = json.loads(PREFLIGHT_COMPLETION.read_text())
    if c["status"] != "complete_passed" or c["results_sha256"] != sha(PREFLIGHT):
        raise RuntimeError("Stage85 preflight completion binding failed")
    preflight = json.loads(PREFLIGHT.read_text())
    verify_frozen_design(config, parent, preflight)
    stage83_result = STAGE83 / "results.json"
    stage83_completion = STAGE83 / "completion.json"
    c83 = json.loads(stage83_completion.read_text())
    if c83["status"] != "complete_passed" or c83["results_sha256"] != sha(stage83_result):
        raise RuntimeError("Stage83 full-window solver prerequisite failed")
    prior = json.loads(stage83_result.read_text())
    if not prior["passed"]:
        raise RuntimeError("Stage83 paired result did not pass")
    for path, digest in {**prior["input_hashes"], **prior["source_hashes"],
                         **prior["case_hashes"]}.items():
        if sha(path) != digest:
            raise RuntimeError(f"Stage83 lineage drift: {path}")
    length = matrix_case_v1.load(2)[2]
    horizon = config["horizon_pore_volumes"] * length / config["target_mean_interstitial_velocity_m_s"]
    budget = config["numerics"]["wall_budget_s_per_case"]
    if budget != 600.:
        raise RuntimeError("conditional resource cap drift")
    input_paths = [DESIGN, PARENT, PREFLIGHT, PREFLIGHT_COMPLETION,
                   stage83_result, stage83_completion, START]
    source.trajectory = candidate
    original_design = source.DESIGN
    source.DESIGN = DESIGN
    rows = []
    try:
        for shape in config["shapes"]:
            started = datetime.now(timezone.utc).isoformat()
            result, _ = source.run(2, shape, horizon, budget)
            case_checks = checks(result, horizon, budget)
            row = {"packing_seed": 2, "start_id": 47, "shape": shape,
                   "horizon_s": horizon, "wall_budget_s": budget,
                   "start_utc": started,
                   "end_utc": datetime.now(timezone.utc).isoformat(),
                   "passed": all(case_checks.values()), "checks": case_checks,
                   "first_passage_observed": result["status"] == "full_window_exit",
                   "result": result}
            rows.append(row)
            case_path = OUT / f"s2_{shape}.json"
            case_path.write_text(json.dumps(row, indent=2))
            print(json.dumps({"shape": shape, "passed": row["passed"],
                              "status": result["status"],
                              "first_passage_observed": row["first_passage_observed"],
                              "time_s": result["time_s"],
                              "runtime_s": result["runtime_seconds"]}), flush=True)
            if not row["passed"]:
                break
    finally:
        source.DESIGN = original_design
    source_paths = [Path(__file__), Path(source.__file__), Path(candidate.__file__),
                    ROOT / "stage80_staging" / "trajectory_combined_pruning_v1.py",
                    ROOT / "stage79_staging" / "inertial_contact_within_pose_reuse_v1.py",
                    ROOT / "stage76_staging" / "geometry_fail_fast_sweep_v1.py",
                    ROOT / "stage74_staging" / "scalar_contact_kernels_v1.py",
                    ROOT / "stage68_staging" / "trajectory_extended_recovery_v1.py",
                    Path(matrix_case_v1.__file__)]
    record = {"completed": len(rows) == 2,
              "passed": len(rows) == 2 and all(row["passed"] for row in rows),
              "rows": rows, "horizon_s": horizon,
              "input_hashes": {str(p): sha(p) for p in input_paths},
              "case_hashes": {str(p): sha(p) for p in OUT.glob("s2_*.json")},
              "source_hashes": {str(p): sha(p) for p in source_paths},
              "environment": {"python": platform.python_version(),
                              "numpy": np.__version__},
              "claim_boundary": config["claim_boundary"]}
    path = OUT / "results.json"
    path.write_text(json.dumps(record, indent=2))
    (OUT / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if record["passed"] else "complete_failed",
        "results_sha256": sha(path)}, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
