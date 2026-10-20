"""Frozen Stage81 candidate: bounded crossings in the other two packings."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage68_staging"), str(ROOT / "stage81_staging")]
import verify_short_fibre_crossing_v1 as source
import trajectory_combined_scalar_v1 as candidate

OLD_DIR = ROOT / "stage55_runs" / "paired_three_packing_pilot_20260912" / "pilot_01"
STAGE81 = ROOT / "stage81_evaluations" / "scalar_s2_long_transfer_01"
OUT = ROOT / "stage82_evaluations" / "fibre_cross_packing_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def gate(seed, old, result, target):
    return {key: bool(value) for key, value in {
        "old_numerical_failure": old["status"] == "numerical_failure",
        "crossed_old_failure": result["time_s"] > old["time_s"],
        "target_completed": result["status"] == "present_at_horizon" and result["time_s"] == target,
        "clearance": result["minimum_gap_m"] >= -5e-10,
        "contact_closure": result["max_contact_residual"] <= 1e-8,
        "force_closure": result["max_force_residual"] <= 1e-8,
        "momentum_closure": result["max_momentum_residual"] <= 1e-8,
        "reynolds_envelope": result["max_reynolds"] <= 3,
        "within_budget": result["runtime_seconds"] <= 300.,
    }.items()}


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    prior_result = STAGE81 / "results.json"
    prior_completion = STAGE81 / "completion.json"
    c = json.loads(prior_completion.read_text())
    if c["status"] != "complete_passed" or c["results_sha256"] != sha(prior_result):
        raise RuntimeError("Stage81 seed-2 prerequisite binding failed")
    source.trajectory = candidate
    rows = []
    input_hashes = {str(p): sha(p) for p in (prior_result, prior_completion)}
    for seed in (3, 1):
        old_path = OLD_DIR / f"s{seed}_prolate_ar4.json"
        old = json.loads(old_path.read_text())["result"]
        target = old["time_s"] + .05
        result, _ = source.run(seed, "prolate_ar4", target, 300.)
        checks = gate(seed, old, result, target)
        rows.append({"seed": seed, "target_s": target,
                     "passed": all(checks.values()), "checks": checks,
                     "result": result})
        input_hashes[str(old_path)] = sha(old_path)
        case_path = OUT / f"s{seed}_short_crossing.json"
        case_path.write_text(json.dumps(rows[-1], indent=2))
        print(json.dumps({"seed": seed, "passed": rows[-1]["passed"],
                          "status": result["status"], "time_s": result["time_s"],
                          "target_s": target, "runtime_s": result["runtime_seconds"],
                          "steps": result["steps"], "rejected": result["rejected"]}), flush=True)
    sources = [Path(__file__), Path(candidate.__file__), Path(source.__file__),
               ROOT / "stage80_staging" / "trajectory_combined_pruning_v1.py",
               ROOT / "stage79_staging" / "inertial_contact_within_pose_reuse_v1.py",
               ROOT / "stage76_staging" / "geometry_fail_fast_sweep_v1.py",
               ROOT / "stage74_staging" / "scalar_contact_kernels_v1.py"]
    record = {"passed": all(row["passed"] for row in rows), "rows": rows,
              "input_hashes": input_hashes,
              "case_hashes": {str(p): sha(p) for p in OUT.glob("s*_short_crossing.json")},
              "source_hashes": {str(p): sha(p) for p in sources},
              "claim_boundary": "Only short numerical transfer across packings; no release fraction or morphology inference."}
    path = OUT / "results.json"
    path.write_text(json.dumps(record, indent=2))
    (OUT / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if record["passed"] else "complete_failed",
        "results_sha256": sha(path)}, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
