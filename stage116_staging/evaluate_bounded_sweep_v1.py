"""Independent exact A/B checks, preserving health and runtime distinctions."""
import statistics
import verify_bounded_sweep_v1 as job
api=job.api


def main():
    d=api.read(job.DESIGN);job.verify(d)
    out=job.profile.ROOT/"stage116_evaluations/fibre_cost_attribution_20260915/optimization_evaluation_01"
    api.require(not out.exists(),"immutable evaluation exists")
    completion=api.read(job.RUN/"completion.json")
    api.require(completion["design_sha256"]==api.sha(job.DESIGN),"completion drift")
    synthetic=api.read(job.RUN/"synthetic/results.json")
    api.require(api.read(job.RUN/"synthetic/completion.json")["results_sha256"]==api.sha(job.RUN/"synthetic/results.json") and synthetic["passed"],"synthetic gate failed")
    api.require(not any(p.stat().st_size for p in job.RUN.glob("*.stderr.txt")),"stderr requires inspection")
    groups=[]
    ignored={"runtime_seconds","fail_fast_sweep_stats","within_pose_reuse_stats","short_pgs_seed_stats","nullspace_rescue"}
    normalize=lambda r:{k:v for k,v in r.items() if k not in ignored}
    for s in d["replay"]["samples"]:
        records={}
        for mode in d["replay"]["order"]:
            name=s["sample"]+"_"+mode;p=job.RUN/name
            api.require(api.sha(p/"record.json")==completion["records"][name]==api.read(p/"completion.json")["record_sha256"],"record drift")
            records[mode]=api.read(p/"record.json")
            cp=records[mode]["result"]["checkpoint"]
            api.require(cp["state_sha256"]==api.digest(cp["state"]),"checkpoint drift")
        exact=all(normalize(records[m]["result"])==normalize(records["reference_1"]["result"]) for m in records)
        ref=[records[m]["result"]["runtime_seconds"] for m in ["reference_1","reference_2"]]
        opt=[records[m]["result"]["runtime_seconds"] for m in ["candidate_1","candidate_2"]]
        speedup=statistics.median(ref)/statistics.median(opt)
        cost_pass=speedup>=d["gates"]["speedup_required_s2_s3"] if s["sample"]!="rejected_steps_s1" else speedup>=1/d["gates"]["max_s1_slowdown"]
        checks={"exact_state_counters_and_checkpoint":exact,"all_healthy_and_paused":all(r["passed"] for r in records.values()),"cost_gate":cost_pass}
        groups.append({"sample":s["sample"],"checks":checks,"passed":all(checks.values()),"reference_s":ref,"candidate_s":opt,"median_speedup":speedup,
                       "candidate_work":records["candidate_1"]["optimization_stats"]})
    result={"passed":all(g["passed"] for g in groups),"groups":groups,"synthetic_cases":len(synthetic["rows"]),"bound_checks":synthetic["bound_checks"],
            "scope":"Selected local implementation-equivalence/cost verification; no full-horizon convergence or release inference.",
            "bindings":{"design_sha256":api.sha(job.DESIGN),"run_completion_sha256":api.sha(job.RUN/"completion.json"),"evaluator_sha256":api.sha(__file__)}}
    job.verify(d);out.mkdir(parents=True);api.write(out/"results.json",result)
    api.write(out/"completion.json",{"passed":result["passed"],"results_sha256":api.sha(out/"results.json")})
    for g in groups:print(g["sample"],g["checks"],"speedup",g["median_speedup"])
    return 0 if result["passed"] else 4


if __name__=="__main__":raise SystemExit(main())
