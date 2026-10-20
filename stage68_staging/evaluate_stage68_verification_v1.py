"""Independent read-only audit of Stage67/68 numerical verification evidence."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXED=ROOT/"stage67_evaluations/fixed_recovery_01"
SMOKE=ROOT/"stage68_evaluations/manufactured_smoke_01"
SHORT=ROOT/"stage68_evaluations/short_fibre_crossing_01"
OLD=ROOT/"stage55_runs/paired_three_packing_pilot_20260912/pilot_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_bound(folder):
    path=folder/"results.json"
    result=json.loads(path.read_text())
    completion=json.loads((folder/"completion.json").read_text())
    return result,completion["status"]=="complete_passed" and completion["results_sha256"]==sha(path)


def main():
    out=ROOT/"stage68_evaluations/independent_audit_01"
    out.mkdir(parents=True,exist_ok=False)
    fixed,fixed_complete=load_bound(FIXED)
    smoke,smoke_complete=load_bound(SMOKE)
    short,short_complete=load_bound(SHORT)
    old_s3=json.loads((OLD/"s3_prolate_ar4.json").read_text())["result"]
    fibre=short["fibre"]
    checked_hashes={}
    for source,expected in {**fixed["source_hashes"],**smoke["source_hashes"],**short["source_hashes"]}.items():
        path=Path(source)
        checked_hashes[source]={"expected":expected,"actual":sha(path) if path.is_file() else None}
    checks={
        "fixed_completion_hash":fixed_complete,
        "smoke_completion_hash":smoke_complete,
        "short_completion_hash":short_complete,
        "source_hashes_match":all(v["expected"]==v["actual"] for v in checked_hashes.values()),
        "three_fixed_systems_pass":bool(fixed["passed"] and len(fixed["rows"])==3 and all(r["passed"] for r in fixed["rows"])),
        "all_smoke_checks_pass":bool(smoke["passed"] and len(smoke["checks"])==17 and all(smoke["checks"].values())),
        "sphere_exact_control":bool(short["checks"]["sphere_exact_unchanged"]),
        "fibre_crossed_old_failure":bool(fibre["status"]=="present_at_horizon" and fibre["time_s"]>old_s3["time_s"] and fibre["contact_solver_retries"]>0),
        "fibre_local_health":bool(fibre["minimum_gap_m"]>=-5e-10 and fibre["max_contact_residual"]<=1e-8 and fibre["max_force_residual"]<=1e-8 and fibre["max_momentum_residual"]<=1e-8 and fibre["max_reynolds"]<=3),
        "fibre_within_budget":bool(fibre["runtime_seconds"]<300.),
    }
    result={"passed":all(checks.values()),"checks":checks,"source_bindings":checked_hashes,
            "stage55_fibre_failure_time_s":old_s3["time_s"],
            "stage68_fibre_short_horizon_s":fibre["time_s"],
            "stage68_fibre_runtime_s":fibre["runtime_seconds"],
            "claim_boundary":"Stage68 is verified for fixed systems, smoke suite, and one short s3 crossing only. It is not yet verified across all three fibre packings, the 0.1-PV horizon, or time-step refinement; no sphere-fibre release inference."}
    path=out/"audit.json"
    path.write_text(json.dumps(result,indent=2))
    (out/"completion.json").write_text(json.dumps({"status":"complete_passed" if result["passed"] else "complete_failed","audit_sha256":sha(path)},indent=2))
    report=("# Stage68 independent numerical audit\n\n"
            f"Audit: **{'pass' if result['passed'] else 'fail'}**. Frozen fixed-state and 17-check smoke evidence are hash-bound.\n\n"
            f"The s3 AR=4 surrogate advanced from its former numerical failure at {old_s3['time_s']:.9f} s to a bounded {fibre['time_s']:.9f} s horizon in {fibre['runtime_seconds']:.1f} wall seconds. The s2 sphere control was exact.\n\n"
            "This is numerical verification only. The other two AR=4 packings, full 0.1-PV horizon and solution refinement remain open; Stage55 remains failed and no release-fraction or morphology claim is made.\n")
    (out/"REPORT.md").write_text(report)
    print(json.dumps({"passed":result["passed"],"checks":checks},indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__=="__main__":
    main()
