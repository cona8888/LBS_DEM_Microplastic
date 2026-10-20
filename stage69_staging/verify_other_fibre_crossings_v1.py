"""Run one bounded non-s3 AR=4 crossing from frozen Stage55 starts."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage68_staging")]
from verify_short_fibre_crossing_v1 import run

OLD=ROOT/"stage55_runs/paired_three_packing_pilot_20260912/pilot_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--seed",type=int,choices=(1,2),required=True)
    args=parser.parse_args()
    seed=args.seed
    out=ROOT/"stage69_evaluations"/f"s{seed}_short_crossing_01"
    out.mkdir(parents=True,exist_ok=False)
    old_path=OLD/f"s{seed}_prolate_ar4.json"
    old=json.loads(old_path.read_text())["result"]
    target=old["time_s"]+.05
    result,_=run(seed,"prolate_ar4",target,300.)
    checks={
        "old_case_failed_numerically":bool(old["status"]=="numerical_failure"),
        "completed_target":bool(result["status"]=="present_at_horizon" and result["time_s"]==target),
        "crossed_old_failure":bool(result["time_s"]>old["time_s"]),
        "contact_retry_exercised":bool(result["contact_solver_retries"]>0),
        "clearance":bool(result["minimum_gap_m"]>=-5e-10),
        "contact_closure":bool(result["max_contact_residual"]<=1e-8),
        "force_closure":bool(result["max_force_residual"]<=1e-8),
        "momentum_closure":bool(result["max_momentum_residual"]<=1e-8),
        "reynolds_envelope":bool(result["max_reynolds"]<=3),
        "within_budget":bool(result["runtime_seconds"]<=300.),
    }
    record={"passed":all(checks.values()),"seed":seed,"target_s":target,
            "prior_case_sha256":sha(old_path),"checks":checks,"result":result,
            "source_hashes":{str(Path(__file__).resolve()):sha(__file__),
                str((ROOT/"stage68_staging/verify_short_fibre_crossing_v1.py").resolve()):sha(ROOT/"stage68_staging/verify_short_fibre_crossing_v1.py"),
                str((ROOT/"stage67_staging/inertial_contact_recovery_portfolio_v1.py").resolve()):sha(ROOT/"stage67_staging/inertial_contact_recovery_portfolio_v1.py"),
                str((ROOT/"stage68_staging/trajectory_extended_recovery_v1.py").resolve()):sha(ROOT/"stage68_staging/trajectory_extended_recovery_v1.py")},
            "claim_boundary":"Short numerical crossing only; no full-horizon or release inference."}
    path=out/"results.json"
    path.write_text(json.dumps(record,indent=2))
    (out/"completion.json").write_text(json.dumps({"status":"complete_passed" if record["passed"] else "complete_failed","results_sha256":sha(path)},indent=2))
    print(json.dumps({"passed":record["passed"],"seed":seed,"checks":checks,
                      "status":result["status"],"reason":result["reason"],
                      "time_s":result["time_s"],"runtime_s":result["runtime_seconds"],
                      "portfolio":result["recovery_portfolio_stats"]},indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__=="__main__":
    main()
