"""Original-start Stage70/76 A/B to 0.05 s with exact accepted-state check."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage68_staging"), str(ROOT / "stage70_staging"),
                str(ROOT / "stage76_staging")]
import verify_short_fibre_crossing_v1 as source
import trajectory_runtime_portfolio_v1 as baseline
import trajectory_fail_fast_sweep_v1 as candidate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    out = ROOT / "stage76_evaluations" / "original_start_ab_01"
    out.mkdir(parents=True, exist_ok=False)
    source.trajectory = baseline
    original, _ = source.run(2, "prolate_ar4", .05, 30.)
    source.trajectory = candidate
    revised, _ = source.run(2, "prolate_ar4", .05, 30.)
    excluded = {"runtime_seconds", "fail_fast_sweep_stats"}
    state_equal = {k: v for k, v in original.items() if k not in excluded} == {
        k: v for k, v in revised.items() if k not in excluded}
    checks = {
        "both_complete": original["status"] == revised["status"] == "present_at_horizon" and original["time_s"] == revised["time_s"] == .05,
        "all_nonruntime_fields_equal": state_equal,
        "early_rejects_used": revised["fail_fast_sweep_stats"]["endpoint_early_rejects"] + revised["fail_fast_sweep_stats"]["interior_early_rejects"] > 0,
        "clearance": revised["minimum_gap_m"] >= -5e-10,
        "contact_residual": revised["max_contact_residual"] <= 1e-8,
        "force_residual": revised["max_force_residual"] <= 1e-8,
        "momentum_residual": revised["max_momentum_residual"] <= 1e-8,
        "reynolds_envelope": revised["max_reynolds"] <= 3,
    }
    checks = {k: bool(v) for k, v in checks.items()}
    record = {"passed": all(checks.values()), "checks": checks,
              "baseline": original, "candidate": revised,
              "source_hashes": {str(Path(__file__).resolve()): sha(__file__),
                                str(Path(candidate.__file__).resolve()): sha(candidate.__file__),
                                str((ROOT / "stage76_staging/geometry_fail_fast_sweep_v1.py").resolve()): sha(ROOT / "stage76_staging/geometry_fail_fast_sweep_v1.py")},
              "claim_boundary": "0.05 s original-start numerical/cost check only; no release inference."}
    path = out / "results.json"
    path.write_text(json.dumps(record, indent=2))
    (out / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if record["passed"] else "complete_failed",
        "results_sha256": sha(path)}, indent=2))
    print(json.dumps({"passed": record["passed"], "checks": checks,
                      "baseline_runtime_s": original["runtime_seconds"],
                      "candidate_runtime_s": revised["runtime_seconds"],
                      "steps": revised["steps"], "rejected": revised["rejected"],
                      "fast_stats": revised["fail_fast_sweep_stats"]}, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
