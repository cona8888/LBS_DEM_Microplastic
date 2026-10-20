"""Bounded original-start seed-2 crossing for Stage76 sweep transfer."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage68_staging"), str(ROOT / "stage76_staging")]
import verify_short_fibre_crossing_v1 as source
import trajectory_fail_fast_sweep_v1 as candidate

source.trajectory = candidate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    out = ROOT / "stage76_evaluations" / "s2_long_transfer_01"
    out.mkdir(parents=True, exist_ok=False)
    old_path = ROOT / "stage55_runs" / "paired_three_packing_pilot_20260912" / "pilot_01" / "s2_prolate_ar4.json"
    old = json.loads(old_path.read_text())["result"]
    target = old["time_s"] + .05
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
              "prior_case_sha256": sha(old_path), "checks": checks,
              "result": result,
              "source_hashes": {str(Path(__file__).resolve()): sha(__file__),
                                str(Path(candidate.__file__).resolve()): sha(candidate.__file__),
                                str((ROOT / "stage76_staging/geometry_fail_fast_sweep_v1.py").resolve()): sha(ROOT / "stage76_staging/geometry_fail_fast_sweep_v1.py")},
              "claim_boundary": "Bounded short crossing only; not full release or morphology inference."}
    path = out / "results.json"
    path.write_text(json.dumps(record, indent=2))
    (out / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if record["passed"] else "complete_failed",
        "results_sha256": sha(path)}, indent=2))
    print(json.dumps({"passed": record["passed"], "checks": checks,
                      "time_s": result["time_s"], "target_s": target,
                      "runtime_s": result["runtime_seconds"], "status": result["status"],
                      "steps": result["steps"], "rejected": result["rejected"],
                      "sweep": result["fail_fast_sweep_stats"]}, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
