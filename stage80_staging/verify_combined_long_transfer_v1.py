"""Bounded original-start s2 short crossing; no release inference."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage68_staging"), str(ROOT / "stage80_staging")]
import verify_short_fibre_crossing_v1 as source
import trajectory_combined_pruning_v1 as candidate

OLD = (ROOT / "stage55_runs" / "paired_three_packing_pilot_20260912" /
       "pilot_01" / "s2_prolate_ar4.json")
OUT = ROOT / "stage80_evaluations" / "combined_s2_long_transfer_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    old = json.loads(OLD.read_text())["result"]
    target = old["time_s"] + .05
    source.trajectory = candidate
    result, _ = source.run(2, "prolate_ar4", target, 300.)
    checks = {
        "old_numerical_failure": old["status"] == "numerical_failure",
        "crossed_old_failure": result["time_s"] > old["time_s"],
        "target_completed": result["status"] == "present_at_horizon" and result["time_s"] == target,
        "clearance": result["minimum_gap_m"] >= -5e-10,
        "contact_closure": result["max_contact_residual"] <= 1e-8,
        "force_closure": result["max_force_residual"] <= 1e-8,
        "momentum_closure": result["max_momentum_residual"] <= 1e-8,
        "reynolds_envelope": result["max_reynolds"] <= 3,
        "within_budget": result["runtime_seconds"] <= 300.,
    }
    checks = {key: bool(value) for key, value in checks.items()}
    record = {"passed": all(checks.values()), "target_s": target,
              "checks": checks, "result": result,
              "input_hashes": {str(OLD): sha(OLD)},
              "source_hashes": {str(p): sha(p) for p in (
                  Path(__file__), Path(candidate.__file__), Path(source.__file__))},
              "claim_boundary": "Bounded numerical crossing only; not full release, trapping, or morphology inference."}
    path = OUT / "results.json"
    path.write_text(json.dumps(record, indent=2))
    (OUT / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if record["passed"] else "complete_failed",
        "results_sha256": sha(path)}, indent=2))
    print(json.dumps({"passed": record["passed"], "checks": checks,
                      "time_s": result["time_s"], "target_s": target,
                      "runtime_s": result["runtime_seconds"],
                      "status": result["status"], "steps": result["steps"],
                      "rejected": result["rejected"],
                      "reuse": result["within_pose_reuse_stats"],
                      "sweep": result["fail_fast_sweep_stats"]}, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
