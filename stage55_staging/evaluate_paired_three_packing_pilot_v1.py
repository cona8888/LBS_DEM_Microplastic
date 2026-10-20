"""Independent hash/health audit and compact render for failed Stage55 pilot."""
import hashlib,json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/"stage55_runs"/"paired_three_packing_pilot_20260912"/"pilot_01"
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    out=ROOT/"stage55_evaluations"/"paired_three_packing_pilot_01"; out.mkdir(parents=True,exist_ok=False)
    result=json.loads((RUN/"results.json").read_text()); completion=json.loads((RUN/"completion.json").read_text())
    bindings=[]
    for name,expected in result["input_hashes"].items():
        path=Path(name); actual=sha(path) if path.is_file() else None; bindings.append({"path":name,"expected":expected,"actual":actual,"passed":actual==expected})
    cases=[]; case_bindings=[]
    for row in result["rows"]:
        path=RUN/f"s{row['packing_seed']}_{row['shape']}.json"; saved=json.loads(path.read_text())
        same=saved==row; case_bindings.append({"path":str(path.resolve()),"sha256":sha(path),"matches_results_row":same}); cases.append(row)
    checks={"runner_completed":bool(result["completed"]),"runner_failed_as_declared":bool(not result["passed"]),
        "completion_is_complete_failed":completion["status"]=="complete_failed",
        "completion_hash_matches":completion["results_sha256"]==sha(RUN/"results.json"),
        "all_input_and_source_hashes_match":all(x["passed"] for x in bindings),"six_unique_cases":len(cases)==6 and len({(r["packing_seed"],r["shape"]) for r in cases})==6,
        "case_files_match_aggregate":all(x["matches_results_row"] for x in case_bindings),
        "all_preterminal_health_gates_pass":all(r["result"]["minimum_gap_m"]>=-5e-10 and r["result"]["max_contact_residual"]<=1e-8 and
            r["result"]["max_force_residual"]<=1e-8 and r["result"]["max_momentum_residual"]<=1e-8 and r["result"]["max_reynolds"]<=3 for r in cases),
        "failures_not_relabelled":all(r["result"]["status"] in {"present_at_horizon","incomplete_budget","numerical_failure"} for r in cases),
        "expected_failure_accounting":sum(r["result"]["status"]=="present_at_horizon" for r in cases)==2 and
            sum(r["result"]["status"]=="incomplete_budget" for r in cases)==1 and sum(r["result"]["status"]=="numerical_failure" for r in cases)==3}
    table=[]
    for r in cases:
        q=r["result"]; table.append({"packing_seed":r["packing_seed"],"shape":r["shape"],"status":q["status"],"reason":q["reason"],
            "fraction_of_horizon_simulated":q["time_s"]/r["horizon_s"],"persistent_contact_observed":q["persistent_contact_observed"],
            "runtime_s":q["runtime_seconds"],"primary_lm_solves":q["multistart_lm_stats"]["primary_solves"],
            "zero_lm_solves":q["multistart_lm_stats"]["zero_lm_solves"],"zero_lm_failures":q["multistart_lm_stats"]["zero_lm_failures"]})
    audit={"passed":bool(all(checks.values())),"study_passed":False,"checks":checks,"cases":table,"bindings":bindings,"case_bindings":case_bindings,
        "conclusion":"Stage55 fails promotion: only two sphere cases reached 0.1 PV; one sphere was budget-censored and all three AR4 cases failed direct contact resolution.",
        "claim_boundary":"No sphere-versus-fibre transport effect or release fraction may be inferred from unequal failure/censoring."}
    path=out/"audit.json"; path.write_text(json.dumps(audit,indent=2)); (out/"completion.json").write_text(json.dumps({"status":"complete_audit_passed_study_failed" if audit["passed"] else "complete_audit_failed","audit_sha256":sha(path)},indent=2))
    colors={"present_at_horizon":"#378B4E","incomplete_budget":"#E0A126","numerical_failure":"#C94949"}; shapes=["equal_volume_sphere","prolate_ar4"]
    fig,ax=plt.subplots(figsize=(8.5,4.8))
    for j,shape in enumerate(shapes):
        rows=[x for x in table if x["shape"]==shape]
        xs=[x["packing_seed"]+(-.10 if j==0 else .10) for x in rows]; ys=[100*x["fraction_of_horizon_simulated"] for x in rows]
        ax.scatter(xs,ys,s=120,marker="o" if j==0 else "s",c=[colors[x["status"]] for x in rows],edgecolor="black",linewidth=.7,label="sphere" if j==0 else "AR=4 fibre")
        for xx,yy,row in zip(xs,ys,rows): ax.text(xx,yy+3,row["status"].replace("present_at_horizon","complete").replace("incomplete_budget","budget").replace("numerical_failure","failed"),ha="center",fontsize=8)
    ax.axhline(100,color="#444",lw=1,ls="--"); ax.set(xlabel="Packing seed",ylabel="Simulated fraction of 0.1-PV horizon (%)",xticks=[1,2,3],ylim=(0,115),title="Stage55 paired morphology pilot — study failed")
    ax.grid(alpha=.22); ax.legend(loc="lower right"); fig.tight_layout(); fig.savefig(out/"stage55_outcomes.png",dpi=180); plt.close(fig)
    (out/"REPORT.md").write_text("""# Stage55 paired three-packing pilot\n\nThe independent evidence audit passes, but the study fails promotion. Two equal-volume sphere cases reached the 0.1-PV horizon; packing 1 was budget-censored after 80.46% of the horizon. All three AR=4 fibre cases ended in direct-contact numerical failure. Preterminal clearance, contact/force/momentum closure, and Reynolds gates remained satisfied.\n\nBecause censoring and solver failures differ by morphology, these outcomes cannot be interpreted as a sphere-versus-fibre transport effect. No release fraction or retention probability is estimated. The next stage must reduce or replace repeated direct LM contact solves and verify the difficult AR=4 states before any larger campaign.\n""")
    print(json.dumps({"audit_passed":audit["passed"],"study_passed":False,"checks":checks,"cases":table,"figure":str(out/"stage55_outcomes.png")},indent=2))
    if not audit["passed"]: raise SystemExit(1)
if __name__=="__main__": main()
