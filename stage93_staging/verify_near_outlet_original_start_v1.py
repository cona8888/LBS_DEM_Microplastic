"""Original-start transfer to the archived Stage86 cutoff, with frozen budget.

Stage92 physical error criteria are carried forward unchanged. The source is
a valid accepted state of a censored run; only its state at the known time is
used as the numerical comparator. This is not a new release observation.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage68_staging"), str(ROOT / "stage89_staging"),
                str(ROOT / "stage92_staging")]
import verify_short_fibre_crossing_v1 as runner
import verify_short_seed_local_v1 as harness
import verify_physical_error_budget_v1 as comparison

OUT = ROOT / "stage93_evaluations/near_outlet_original_start_01"
PRIOR = ROOT / "stage92_evaluations/physical_error_budget_01/results.json"
STAGE86 = ROOT / "stage86_runs/near_outlet_conditional_20260913/seed2_pair_01/results.json"


def main():
    previous = json.loads(PRIOR.read_text())
    completion = json.loads((PRIOR.parent / "completion.json").read_text())
    if completion["status"] != "complete_passed" or completion["results_sha256"] != harness.sha(PRIOR):
        raise RuntimeError("Stage92 verification prerequisite failed")
    prior86 = json.loads(STAGE86.read_text())
    for record in (previous, prior86):
        for section in ("input_hashes", "source_hashes", "artifact_hashes", "case_hashes"):
            for path, digest in record.get(section, {}).items():
                if harness.sha(path) != digest:
                    raise RuntimeError(f"source evidence drift: {path}")
    protocol92 = json.loads((PRIOR.parent / "protocol.json").read_text())
    reference = json.loads(harness.CASE.read_text())["result"]
    cfg = json.loads(harness.DESIGN.read_text())
    target = reference["time_s"]
    OUT.mkdir(parents=True, exist_ok=False)
    protocol = {"target_s": target, "budget_s": 180.,
                "surface_displacement_budget_m": protocol92["surface_displacement_budget_m"],
                "generalized_velocity_budget_m_s": protocol92["generalized_velocity_budget_m_s"],
                "source_status": reference["status"], "candidate_pgs_seed_sweeps": 64,
                "input_hashes": {str(p): harness.sha(p) for p in (PRIOR, STAGE86, harness.CASE, harness.DESIGN)},
                "source_hashes": {str(p): harness.sha(p) for p in (
                    Path(__file__), Path(runner.__file__), Path(harness.candidate.__file__),
                    Path(comparison.__file__))},
                "claim_boundary": "Original-start numerical transfer to a censored run's saved time; no release fraction."}
    harness.dump(OUT / "protocol.json", protocol)
    original = runner.DESIGN, runner.trajectory
    runner.DESIGN, runner.trajectory = harness.DESIGN, harness.candidate
    try:
        result, _ = runner.run(2, "prolate_ar4", target, 180.)
    finally:
        runner.DESIGN, runner.trajectory = original
    harness.dump(OUT / "candidate.json", result)
    m = comparison.metrics(reference, result, cfg["prolate_semiaxes_m"][0])
    checks = {
        "target_completed": result["status"] == "present_at_horizon" and abs(result["time_s"]-target) <= 1e-12,
        "health": comparison.health(result),
        "surface_error_budget": m["surface_displacement_bound_m"] <= protocol["surface_displacement_budget_m"],
        "velocity_error_budget": m["generalized_velocity_difference_m_s"] <= protocol["generalized_velocity_budget_m_s"],
        "same_steps": result["steps"] == reference["steps"],
        "same_rejections": result["rejected"] == reference["rejected"],
        "within_budget": result["runtime_seconds"] <= 180.,
        "candidate_exercised": result["short_pgs_seed_stats"]["accepted"] > 0,
    }
    record = {"passed": all(checks.values()), "checks": checks, "metrics": m,
              "runtime_s": result["runtime_seconds"], "time_s": result["time_s"],
              "candidate_counts": result["short_pgs_seed_stats"],
              "input_hashes": protocol["input_hashes"], "source_hashes": protocol["source_hashes"],
              "artifact_hashes": {str(p): harness.sha(p) for p in OUT.glob("*.json")}}
    harness.dump(OUT / "results.json", record)
    harness.dump(OUT / "completion.json", {"status": "complete_passed" if record["passed"] else "complete_failed",
                                           "results_sha256": harness.sha(OUT / "results.json")})
    print(json.dumps(record, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
