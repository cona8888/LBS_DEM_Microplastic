"""Original-start 0.3 s comparison with hash-bound Stage80 reference."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage68_staging"), str(ROOT / "stage81_staging")]
import verify_short_fibre_crossing_v1 as source
import trajectory_combined_scalar_v1 as candidate

FROZEN = ROOT / "stage80_evaluations" / "combined_short_01" / "results.json"
FROZEN_COMPLETION = FROZEN.parent / "completion.json"
OUT = ROOT / "stage81_evaluations" / "early_scalar_ab_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    completion = json.loads(FROZEN_COMPLETION.read_text())
    if completion["status"] != "complete_passed" or completion["results_sha256"] != sha(FROZEN):
        raise RuntimeError("frozen Stage80 early reference binding failed")
    baseline = json.loads(FROZEN.read_text())["combined_candidate"]
    source.trajectory = candidate
    revised, _ = source.run(2, "prolate_ar4", .3, 60.)
    deltas = {key: float(np.linalg.norm(
        np.asarray(revised[key], dtype=float) - np.asarray(baseline[key], dtype=float)))
        for key in ("position_m", "orientation", "velocity_generalized")}
    checks = {
        "both_complete": baseline["status"] == revised["status"] == "present_at_horizon",
        "same_time": baseline["time_s"] == revised["time_s"] == .3,
        "same_steps": baseline["steps"] == revised["steps"],
        "same_rejects": baseline["rejected"] == revised["rejected"],
        "position_agreement_m": deltas["position_m"] <= 1e-9,
        "orientation_agreement": deltas["orientation"] <= 1e-9,
        "velocity_agreement": deltas["velocity_generalized"] <= 1e-9,
        "candidate_clearance": revised["minimum_gap_m"] >= -5e-10,
        "candidate_contact": revised["max_contact_residual"] <= 1e-8,
        "candidate_force": revised["max_force_residual"] <= 1e-8,
        "candidate_momentum": revised["max_momentum_residual"] <= 1e-8,
        "candidate_reynolds": revised["max_reynolds"] <= 3,
    }
    checks = {key: bool(value) for key, value in checks.items()}
    record = {"passed": all(checks.values()), "checks": checks,
              "baseline": baseline, "candidate": revised, "state_deltas": deltas,
              "input_hashes": {str(p): sha(p) for p in (FROZEN, FROZEN_COMPLETION)},
              "source_hashes": {str(p): sha(p) for p in (
                  Path(__file__), Path(candidate.__file__), Path(source.__file__))},
              "claim_boundary": "Original-start 0.3 s numerical A/B only; no release evidence."}
    path = OUT / "results.json"
    path.write_text(json.dumps(record, indent=2))
    (OUT / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if record["passed"] else "complete_failed",
        "results_sha256": sha(path)}, indent=2))
    print(json.dumps({"passed": record["passed"], "checks": checks,
                      "state_deltas": deltas,
                      "reference_runtime_s": baseline["runtime_seconds"],
                      "candidate_runtime_s": revised["runtime_seconds"],
                      "reuse": revised["within_pose_reuse_stats"]}, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
