"""Independently check replay equivalence and report inclusive profiling costs."""
from pathlib import Path
import statistics

import profile_fibre_cost_v1 as job
api=job.api


def main():
    d=api.read(job.DESIGN);job.verify(d)
    output=job.ROOT/"stage116_evaluations/fibre_cost_attribution_20260915/profile_evaluation_01"
    api.require(not output.exists(),"immutable evaluation exists")
    completion=api.read(job.RUN/"completion.json")
    api.require(completion["design_sha256"]==api.sha(job.DESIGN),"run binding drift")
    api.require(not list(job.RUN.rglob("failure.json")),"profile failure")
    api.require(not any(p.stat().st_size for p in job.RUN.glob("*.stderr.txt")),"nonempty stderr")
    groups=[]
    for selected in d["samples"]:
        sample=selected["sample"];records={}
        for mode in d["order"]:
            name=sample+"_"+mode;path=job.RUN/name
            api.require(completion["records"][name]==api.sha(path/"record.json"),"record drift")
            for file,digest in api.read(path/"completion.json")["artifacts"].items():
                api.require(api.sha(path/file)==digest,"artifact drift")
            records[mode]=api.read(path/"record.json")
        normalize=lambda r:{k:v for k,v in r.items() if k!="runtime_seconds"}
        exact=all(normalize(records[m]["result"])==normalize(records["plain_1"]["result"]) for m in d["order"])
        prior=api.read(selected["record_path"])["result"]
        reference=records["plain_1"]["result"]
        profile=api.read(job.RUN/(sample+"_profile")/"profile.json")
        total=profile["exclusive_sum_s"]
        sweep=sum(row["cumulative_s"] for row in profile["rows"] if row["function"]=="swept_gap" and Path(row["file"]).name=="geometry_fail_fast_sweep_v1.py")
        times=[records[m]["result"]["runtime_seconds"] for m in ["plain_1","plain_2"]]
        row={"sample":sample,"case_id":selected["case_id"],"exact_profile_plain_results":exact,
            "all_workers_passed":all(r["passed"] for r in records.values()),"unprofiled_runtime_s":times,
            "unprofiled_median_s":statistics.median(times),"profiled_runtime_s":records["profile"]["result"]["runtime_seconds"],
            "profiler_overhead_ratio":records["profile"]["result"]["runtime_seconds"]/statistics.median(times),
            "profile_exclusive_total_s":total,"sweep_inclusive_fraction":sweep/total,
            "extra_accepted_steps":reference["steps"]-prior["steps"],"extra_rejections":reference["rejected"]-prior["rejected"],
            "extra_contact_steps":reference["contact_steps"]-prior["contact_steps"],"physical_interval_s":[prior["time_s"],reference["time_s"]],
            "top_profile_rows":profile["rows"][:30],"checkpoint_sha256":reference["checkpoint"]["state_sha256"]}
        groups.append(row)
    passed=all(g["exact_profile_plain_results"] and g["all_workers_passed"] for g in groups)
    result={"passed":passed,"groups":groups,"runner_wall_s":completion["wall_s"],
            "bindings":{"design_sha256":api.sha(job.DESIGN),"run_completion_sha256":api.sha(job.RUN/"completion.json"),"evaluator_sha256":api.sha(__file__)},
            "interpretation":"Cost attribution on three selected short checkpoints, not full-trajectory timing or complete representation of every contact regime. Inclusive function timings overlap.",
            "no_release_or_accuracy_claim":True}
    job.verify(d);output.mkdir(parents=True)
    api.write(output/"results.json",result)
    api.write(output/"completion.json",{"passed":passed,"results_sha256":api.sha(output/"results.json")})
    for g in groups:print(g["sample"],"exact",g["exact_profile_plain_results"],"sweep fraction",g["sweep_inclusive_fraction"],"extra rejections",g["extra_rejections"],"contacts",g["extra_contact_steps"])
    return 0 if passed else 4


if __name__=="__main__":raise SystemExit(main())
