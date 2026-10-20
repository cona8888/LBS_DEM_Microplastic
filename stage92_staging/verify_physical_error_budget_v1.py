"""Prospective physical error budget and timestep audit for the frozen 64 seed.

The legacy 1e-9 component comparison remains a separate, failed criterion.
This protocol derives a displacement budget from the existing clearance
tolerance and a velocity budget from imposed mean flow. It is frozen before
the new timestep and withheld-packing runs. No release inference is allowed.
"""
import copy
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage89_staging")]
import verify_short_seed_local_v1 as harness

OUT = ROOT / "stage92_evaluations/physical_error_budget_01"
PARENT_DESIGN = ROOT / "stage55_designs/paired_three_packing_pilot_v1.json"
OLD = ROOT / "stage55_runs/paired_three_packing_pilot_20260912/pilot_01"
PRIOR = ROOT / "stage89_evaluations/short_seed_local_01/results.json"


def metrics(old, new, a):
    dx = float(np.linalg.norm(np.asarray(old["position_m"])-np.asarray(new["position_m"])))
    dp = float(np.linalg.norm(np.asarray(old["orientation"])-np.asarray(new["orientation"])))
    dq = float(np.linalg.norm(np.asarray(old["velocity_generalized"])-np.asarray(new["velocity_generalized"])))
    # Axis directions are oriented continuously from a common start. Rotating
    # the prolate by angle theta displaces any surface point by <=a*||dp||.
    return {"translation_difference_m": dx, "axis_difference": dp,
            "surface_displacement_bound_m": dx+a*dp,
            "generalized_velocity_difference_m_s": dq,
            "legacy_max_component_difference": max(float(np.max(np.abs(
                np.asarray(old[k])-np.asarray(new[k])))) for k in (
                    "position_m", "orientation", "velocity_generalized"))}


def health(r):
    return bool(r["status"] == "present_at_horizon"
                and r["minimum_gap_m"] >= -5e-10
                and r["max_contact_residual"] <= 1e-8
                and r["max_force_residual"] <= 1e-8
                and r["max_momentum_residual"] <= 1e-8
                and r["max_reynolds"] <= 3)


def main():
    prior = json.loads(PRIOR.read_text())
    completion = json.loads((PRIOR.parent / "completion.json").read_text())
    if completion["status"] != "complete_failed" or completion["results_sha256"] != harness.sha(PRIOR):
        raise RuntimeError("legacy failure record changed")
    for section in ("input_hashes", "source_hashes", "artifact_hashes"):
        for path, digest in prior[section].items():
            if harness.sha(path) != digest:
                raise RuntimeError(f"Stage89 evidence drift: {path}")
    cfg = json.loads(harness.DESIGN.read_text())
    a, b, _ = cfg["prolate_semiaxes_m"]
    clearance = 1e-5*b
    budget_x = 0.01*clearance
    budget_q = 1e-4*cfg["target_mean_interstitial_velocity_m_s"]
    cases = [{"name": f"near_s2_dt{level}", "seed": 2, "state": str(harness.CASE),
              "refinement": level} for level in (1, 2, 4)]
    cases += [{"name": f"withheld_s{seed}", "seed": seed,
               "state": str(OLD / f"s{seed}_prolate_ar4.json"), "refinement": 1}
              for seed in (1, 3)]
    sources = [Path(__file__), Path(harness.__file__), Path(harness.candidate.__file__),
               Path(harness.baseline.__file__), Path(harness.candidate.stage50.__file__),
               Path(harness.candidate.stage53.__file__), Path(harness.candidate.portfolio.__file__)]
    protocol = {"cases": cases, "horizon_s": .01, "wall_budget_s_per_arm": 60.,
                "surface_displacement_budget_m": budget_x,
                "generalized_velocity_budget_m_s": budget_q,
                "rationale": "Algorithm error <=1% of existing geometric clearance tolerance, velocity error <=0.01% of imposed mean flow; all original physical acceptance gates retained.",
                "legacy_component_gate": 1e-9,
                "refinement_controls": ["max_dt_s", "relaxation_fraction", "displacement_fraction", "angle_limit_rad"],
                "candidate_frozen_pgs_sweeps": 64,
                "input_hashes": {str(p): harness.sha(p) for p in (
                    harness.DESIGN, PRIOR, *[Path(c["state"]) for c in cases])},
                "source_hashes": {str(p): harness.sha(p) for p in sources},
                "claim_boundary": "Prospective local solution verification; strict Stage89 equivalence remains failed. No material validation or release outcome."}
    OUT.mkdir(parents=True, exist_ok=False)
    harness.dump(OUT / "protocol.json", protocol)
    rows = []
    all_results = {}
    for case in cases:
        config = copy.deepcopy(cfg)
        for key in protocol["refinement_controls"]:
            config["numerics"][key] /= case["refinement"]
        previous = json.loads(Path(case["state"]).read_text())["result"]
        pair = {}
        for arm, module in (("baseline", harness.baseline), ("candidate", harness.candidate)):
            result = harness.run_local(module, config, previous, case["seed"], .01, 60.)
            pair[arm] = result
            harness.dump(OUT / f'{case["name"]}_{arm}.json', result)
            print(json.dumps({"case": case["name"], "arm": arm, "status": result["status"],
                              "time_s": result["time_s"], "runtime_s": result["runtime_seconds"]}), flush=True)
        m = metrics(pair["baseline"], pair["candidate"], a)
        checks = {"same_completed_horizon": all(abs(r["time_s"]-.01) <= 1e-12 for r in pair.values()),
                  "both_health": all(health(r) for r in pair.values()),
                  "surface_error_budget": m["surface_displacement_bound_m"] <= budget_x,
                  "velocity_error_budget": m["generalized_velocity_difference_m_s"] <= budget_q,
                  "same_steps": pair["baseline"]["steps"] == pair["candidate"]["steps"],
                  "same_rejections": pair["baseline"]["rejected"] == pair["candidate"]["rejected"]}
        row = {**case, "metrics": m, "checks": checks, "passed": all(checks.values()),
               "legacy_component_gate_passed": m["legacy_max_component_difference"] <= 1e-9,
               "candidate_counts": pair["candidate"]["short_pgs_seed_stats"]}
        rows.append(row)
        all_results[case["name"]] = pair
        harness.dump(OUT / f'{case["name"]}_comparison.json', row)
    refinements = {}
    for arm in ("baseline", "candidate"):
        refinements[arm] = {"level1_to_2": metrics(all_results["near_s2_dt1"][arm], all_results["near_s2_dt2"][arm], a),
                            "level2_to_4": metrics(all_results["near_s2_dt2"][arm], all_results["near_s2_dt4"][arm], a)}
    passed = all(row["passed"] for row in rows)
    record = {"passed": passed, "rows": rows, "timestep_differences": refinements,
              "scope": protocol["claim_boundary"],
              "input_hashes": protocol["input_hashes"], "source_hashes": protocol["source_hashes"],
              "artifact_hashes": {str(p): harness.sha(p) for p in OUT.glob("*.json")}}
    harness.dump(OUT / "results.json", record)
    harness.dump(OUT / "completion.json", {"status": "complete_passed" if passed else "complete_failed",
                                           "results_sha256": harness.sha(OUT / "results.json")})
    print(json.dumps({"passed": passed, "row_passes": [r["passed"] for r in rows],
                      "timestep_differences": refinements}, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
