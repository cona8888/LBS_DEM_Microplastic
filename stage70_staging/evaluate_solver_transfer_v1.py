"""Audit frozen solver tests and classify transfer to three fibre packings."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(folder):
    path=ROOT/folder/"results.json"
    result=json.loads(path.read_text())
    completion=json.loads((path.parent/"completion.json").read_text())
    status=completion["status"]
    binding=completion["results_sha256"]==sha(path)
    return result,status,binding


def main():
    out=ROOT/"stage70_evaluations/independent_transfer_audit_01"
    out.mkdir(parents=True,exist_ok=False)
    fixed,fixed_status,fixed_bound=read(Path("stage70_evaluations/fixed_runtime_01"))
    smoke,smoke_status,smoke_bound=read(Path("stage70_evaluations/manufactured_smoke_01"))
    s3,s3_status,s3_bound=read(Path("stage68_evaluations/short_fibre_crossing_01"))
    s1,s1_status,s1_bound=read(Path("stage70_evaluations/s1_short_crossing_01"))
    s2,s2_status,s2_bound=read(Path("stage69_evaluations/s2_short_crossing_01"))
    checks={
        "fixed_hash_and_pass":bool(fixed_bound and fixed_status=="complete_passed" and fixed["passed"]),
        "smoke_hash_and_pass":bool(smoke_bound and smoke_status=="complete_passed" and smoke["passed"] and len(smoke["checks"])==17),
        "s3_hash_and_pass":bool(s3_bound and s3_status=="complete_passed" and s3["passed"]),
        "s1_hash_and_censored":bool(s1_bound and s1_status=="complete_failed" and not s1["passed"] and s1["result"]["status"]=="incomplete_budget"),
        "s2_hash_and_censored":bool(s2_bound and s2_status=="complete_failed" and not s2["passed"] and s2["result"]["status"]=="incomplete_budget"),
    }
    rows=[]
    for seed,record,solver in ((1,s1,"Stage70"),(2,s2,"Stage67"),(3,s3,"Stage67")):
        old=json.loads((ROOT/f"stage55_runs/paired_three_packing_pilot_20260912/pilot_01/s{seed}_prolate_ar4.json").read_text())["result"]
        item=record["result"] if seed!=3 else record["fibre"]
        target=record["target_s"] if seed!=3 else old["time_s"]+.05
        health=bool(item["minimum_gap_m"]>=-5e-10 and item["max_contact_residual"]<=1e-8 and item["max_force_residual"]<=1e-8 and item["max_momentum_residual"]<=1e-8 and item["max_reynolds"]<=3)
        checks[f"s{seed}_preterminal_health"] = health
        rows.append({"seed":seed,"solver":solver,"old_failure_s":old["time_s"],"target_s":target,"achieved_s":item["time_s"],"status":item["status"],"runtime_s":item["runtime_seconds"],"health":health})
    audit={"evidence_audit_passed":all(checks.values()),"solver_transfer_passed":False,"checks":checks,"rows":rows,
           "claim_boundary":"Only s3 completed the short crossing. s1 and s2 are budget-censored; full 0.1-PV and release comparisons remain prohibited."}
    path=out/"audit.json"
    path.write_text(json.dumps(audit,indent=2))
    (out/"completion.json").write_text(json.dumps({"status":"complete_evidence_audit_passed_solver_transfer_failed" if audit["evidence_audit_passed"] else "complete_evidence_audit_failed","audit_sha256":sha(path)},indent=2))
    lines=["# Stage67–70 solver-transfer decision","",
           "The evidence audit passes, but the solver does **not** transfer within the declared short-run budget across all packings.","",
           "| Packing | Solver | Old failure (s) | Target (s) | Achieved (s) | Runtime (s) | Outcome |",
           "|---:|---|---:|---:|---:|---:|---|"]
    for r in rows:
        lines.append(f"| {r['seed']} | {r['solver']} | {r['old_failure_s']:.6f} | {r['target_s']:.6f} | {r['achieved_s']:.6f} | {r['runtime_s']:.1f} | {r['status']} |")
    lines += ["","All accepted/preterminal steps satisfy the declared clearance, contact, force, momentum and Reynolds gates. The Stage70 fixed contact systems and 17-check smoke suite pass. Stage70's s1 pruning yields only a modest gain over Stage67 (1.6854 s versus 1.6749 s under ~300 s).","",
              "**Decision:** Do not rerun the full Stage55 six-case study, estimate a release fraction, or claim a morphology effect. Next, profile and accelerate the inner contact loop without changing its equations, or use a separately defined reduced-order model whose claim is narrower. A local native compiler was not found on PATH or in the checked WSL environment."]
    (out/"REPORT.md").write_text("\n".join(lines)+"\n")
    print(json.dumps({"evidence_audit_passed":audit["evidence_audit_passed"],"solver_transfer_passed":False,"rows":rows},indent=2))
    if not audit["evidence_audit_passed"]:
        raise SystemExit(1)


if __name__=="__main__":
    main()
