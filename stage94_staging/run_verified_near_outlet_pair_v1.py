"""Resolve the Stage86 conditional pair after prospective solution verification.

Uses the frozen Stage89 64-sweep candidate and unchanged Stage86 physics,
start, 0.1-PV observation window and per-case 600 s cap. This is a new run;
all original evidence stays immutable. No population release claim is made.
"""
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage68_staging"), str(ROOT / "stage89_staging")]
import verify_short_fibre_crossing_v1 as runner
import verify_short_seed_local_v1 as harness

PREREQ = ROOT / "stage93_evaluations/near_outlet_original_start_01/results.json"
PILOT = ROOT / "stage86_runs/near_outlet_conditional_20260913/seed2_pair_01"
OUT = ROOT / "stage94_runs/verified_near_outlet_pair_20260913/pair_01"


def verify_bindings(record):
    count = 0
    for key in ("input_hashes", "source_hashes", "artifact_hashes", "case_hashes"):
        for path, digest in record.get(key, {}).items():
            if harness.sha(path) != digest:
                raise RuntimeError(f"evidence hash drift: {path}")
            count += 1
    return count


def verify_transfer():
    result = json.loads(PREREQ.read_text())
    completion = json.loads((PREREQ.parent / "completion.json").read_text())
    if completion["status"] != "complete_passed" or completion["results_sha256"] != harness.sha(PREREQ):
        raise RuntimeError("original-start transfer prerequisite failed")
    count = verify_bindings(result)
    prior = json.loads(harness.CASE.read_text())["result"]
    new = json.loads((PREREQ.parent / "candidate.json").read_text())
    protocol = json.loads((PREREQ.parent / "protocol.json").read_text())
    a = json.loads(harness.DESIGN.read_text())["prolate_semiaxes_m"][0]
    dx = np.linalg.norm(np.asarray(prior["position_m"])-new["position_m"])
    dp = np.linalg.norm(np.asarray(prior["orientation"])-new["orientation"])
    dq = np.linalg.norm(np.asarray(prior["velocity_generalized"])-new["velocity_generalized"])
    checks = [new["status"] == "present_at_horizon", abs(new["time_s"]-prior["time_s"]) <= 1e-12,
              dx+a*dp <= protocol["surface_displacement_budget_m"],
              dq <= protocol["generalized_velocity_budget_m_s"],
              new["steps"] == prior["steps"], new["rejected"] == prior["rejected"],
              new["minimum_gap_m"] >= -5e-10, new["max_contact_residual"] <= 1e-8,
              new["max_force_residual"] <= 1e-8, new["max_momentum_residual"] <= 1e-8,
              new["max_reynolds"] <= 3]
    if not all(checks):
        raise RuntimeError("independent original-start transfer audit failed")
    return {"passed": True, "hash_bindings_verified": count,
            "surface_displacement_bound_m": float(dx+a*dp),
            "generalized_velocity_difference_m_s": float(dq),
            "execution_note": "Stage93 simulation and durable result/completion were complete. Driver exited 1 only when printing a NumPy boolean in the already-written record. Raw results and acceptance are independently verified here; Stage93 source and artifacts are preserved."}


def checks(r, horizon, budget):
    resolved = ((r["status"] == "present_at_horizon" and abs(r["time_s"]-horizon) <= 1e-12)
                or (r["status"] == "full_window_exit" and 0 < r["time_s"] <= horizon))
    return {"resolved": bool(resolved), "clearance": bool(r["minimum_gap_m"] >= -5e-10),
            "contact": bool(r["max_contact_residual"] <= 1e-8),
            "force": bool(r["max_force_residual"] <= 1e-8),
            "momentum": bool(r["max_momentum_residual"] <= 1e-8),
            "reynolds": bool(r["max_reynolds"] <= 3),
            "within_budget": bool(r["runtime_seconds"] <= budget),
            "nonabsorbing_dwell": r["dwell_is_absorbing"] is False}


def main():
    audit = verify_transfer()
    prior = json.loads((PILOT / "results.json").read_text())
    verify_bindings(prior)
    cfg = json.loads(harness.DESIGN.read_text())
    _, _, length, _, field_inputs = harness.matrix_case_v1.load(2)
    horizon = cfg["horizon_pore_volumes"]*length/cfg["target_mean_interstitial_velocity_m_s"]
    budget = cfg["numerics"]["wall_budget_s_per_case"]
    if budget != 600. or cfg["horizon_pore_volumes"] != .1:
        raise RuntimeError("conditional observation design drift")
    sources = {Path(__file__).resolve()}
    for module in list(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if name:
            path = Path(name).resolve()
            if path.suffix == ".py" and ROOT in path.parents:
                sources.add(path)
    starts = ROOT / "stage37_runs/stage4_farfield_bound_20260912/pilot_01/starts_s2.json"
    protocol = {"packing_seed": 2, "start_id": 47, "horizon_s": horizon,
                "horizon_pore_volumes": .1, "wall_budget_s_per_case": budget,
                "candidate_pgs_seed_sweeps": 64,
                "input_hashes": {str(p): harness.sha(p) for p in (
                    harness.DESIGN, PREREQ, PILOT / "results.json", starts, *field_inputs)},
                "source_hashes": {str(p): harness.sha(p) for p in sorted(sources)},
                "claim_boundary": "One geometry-selected near-outlet conditional pair. Finite-window first passage and dwell only; not probability-weighted matrix release, permanent retention, or experimental validation."}
    OUT.mkdir(parents=True, exist_ok=False)
    harness.dump(OUT / "protocol.json", protocol)
    harness.dump(OUT / "prerequisite_audit.json", audit)
    original = runner.DESIGN, runner.trajectory
    runner.DESIGN, runner.trajectory = harness.DESIGN, harness.candidate
    rows = []
    try:
        for shape in cfg["shapes"]:
            started = datetime.now(timezone.utc).isoformat()
            result, _ = runner.run(2, shape, horizon, budget)
            gates = checks(result, horizon, budget)
            row = {"shape": shape, "packing_seed": 2, "start_id": 47,
                   "started_utc": started, "ended_utc": datetime.now(timezone.utc).isoformat(),
                   "passed": all(gates.values()), "checks": gates,
                   "first_passage_observed": result["status"] == "full_window_exit",
                   "result": result}
            rows.append(row)
            harness.dump(OUT / f"s2_{shape}.json", row)
            print(json.dumps({"shape": shape, "status": result["status"],
                              "time_s": result["time_s"], "runtime_s": result["runtime_seconds"],
                              "passed": row["passed"]}), flush=True)
            if not row["passed"]:
                break
    finally:
        runner.DESIGN, runner.trajectory = original
    verify_bindings(protocol)
    record = {"passed": len(rows) == 2 and all(r["passed"] for r in rows),
              "completed_case_count": len(rows), "rows": rows,
              "horizon_s": horizon, "horizon_pore_volumes": .1,
              "input_hashes": protocol["input_hashes"], "source_hashes": protocol["source_hashes"],
              "artifact_hashes": {str(p): harness.sha(p) for p in OUT.glob("*.json")},
              "environment": {"python": platform.python_version(), "numpy": np.__version__},
              "claim_boundary": protocol["claim_boundary"]}
    harness.dump(OUT / "results.json", record)
    harness.dump(OUT / "completion.json", {"status": "complete_passed" if record["passed"] else "complete_failed",
                                           "results_sha256": harness.sha(OUT / "results.json")})
    print(json.dumps({"passed": record["passed"], "completed_case_count": len(rows)}), flush=True)
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
