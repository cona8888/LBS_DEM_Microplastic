"""One bounded candidate attempt for each of the eight unresolved short cases."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

import verify_bounded_sweep_v1 as opt
api=opt.api
ROOT=opt.profile.ROOT
DESIGN=ROOT/"stage116_designs/fibre_cost_attribution_20260915/short_matrix_01.json"
RUN=ROOT/"stage116_runs/fibre_cost_attribution_20260915/short_matrix_01"
PRIOR=opt.profile.PRIOR


def prepare():
    api.require(not DESIGN.exists(),"immutable design exists")
    opt.verify(api.read(opt.DESIGN))
    ev=ROOT/"stage116_evaluations/fibre_cost_attribution_20260915/optimization_evaluation_01/results.json"
    api.require(api.read(ev)["passed"] and api.read(ev.parent/"completion.json")["results_sha256"]==api.sha(ev),"optimization gate not accepted")
    old=api.read(api.DESIGN);cases=[];reuse={}
    for s in old["cases"]:
        path=PRIOR/s["case_id"]/"record.json";r=api.read(path)
        api.require(api.sha(path)==api.read(path.parent/"completion.json")["record_sha256"],"prior binding drift")
        if r["result"]["status"]=="incomplete_budget":cases.append({"case_id":s["case_id"],"prior_path":str(path),"prior_sha256":api.sha(path),"prefix_steps":r["result"]["steps"]})
        else:reuse[s["case_id"]]={"path":str(path),"sha256":api.sha(path)}
    api.require(len(cases)==8 and len(reuse)==28,"prior disposition changed")
    d={"question":"Can the verified bounded-sweep implementation finish the eight unresolved 0.25-s tests at unchanged accuracy and compute limits?",
       "cases":cases,"reused_completed_records":reuse,"budget":{"per_case_s":45.,"total_s":450.,"one_attempt_only":True},
       "physical_changes":[],"numerical_controls":"All inherited unchanged from Stage115; original common query remains 0.25 s.",
       "prefix_gate":"From original initial state, pause at the original partial record's accepted-step count; require identical full checkpoint state/hash before continuing. New version-specific checkpoint contract is used throughout.",
       "source_hashes":{str(Path(__file__).resolve()):api.sha(__file__)},"optimization_design_sha256":api.sha(opt.DESIGN),
       "optimization_evaluation_path":str(ev),"optimization_evaluation_sha256":api.sha(ev),"prior_design_sha256":api.sha(api.DESIGN),
       "claim_boundary":"Short-time numerical/implementation verification only; not population release or full-horizon feasibility."}
    d["binding"]=api.digest(d);api.write(DESIGN,d);print("FROZEN SHORT MATRIX",api.sha(DESIGN))


def verify(d):
    api.require(d["binding"]==api.digest({k:v for k,v in d.items() if k!="binding"}),"design drift")
    api.verify_mapping(d["source_hashes"]);opt.verify(api.read(opt.DESIGN))
    api.require(api.sha(opt.DESIGN)==d["optimization_design_sha256"] and api.sha(api.DESIGN)==d["prior_design_sha256"],"parent design drift")
    api.require(api.sha(d["optimization_evaluation_path"])==d["optimization_evaluation_sha256"],"acceptance drift")
    for c in d["cases"]:api.require(api.sha(c["prior_path"])==c["prior_sha256"],"original incomplete record drift")
    for r in d["reused_completed_records"].values():api.require(api.sha(r["path"])==r["sha256"],"reused record drift")


def worker(name):
    d=api.read(DESIGN);verify(d)
    s=next(s for s in d["cases"] if s["case_id"]==name)
    prior=api.read(s["prior_path"]);old=api.read(api.DESIGN);spec=next(s for s in old["cases"] if s["case_id"]==name)
    out=RUN/name;api.require(not out.exists(),"immutable worker exists");out.mkdir(parents=True)
    api.write(out/"launch.json",{"design_sha256":api.sha(DESIGN),"command":sys.argv,"prior_record_sha256":s["prior_sha256"]})
    original=opt.candidate.legacy.swept_gap
    start=time.perf_counter();phases=[];exact=False
    binding=api.digest([d["binding"],name])
    try:
        opt.candidate.legacy.swept_gap=opt.candidate.swept_gap
        first=api.normalized(api.execute(spec,binding,45.,pause=s["prefix_steps"]))
        phases.append(first);api.write(out/"prefix_result.json",first,raw=True)
        if first["status"]=="paused_checkpoint":
            exact=first["checkpoint"]["state_sha256"]==prior["result"]["checkpoint"]["state_sha256"] and first["checkpoint"]["state"]==prior["result"]["checkpoint"]["state"]
            api.require(exact,"optimized prefix differs from frozen original")
            remaining=45.-(time.perf_counter()-start)
            if remaining>.05:
                phases.append(api.normalized(api.execute(spec,binding,min(45.,remaining),checkpoint=first["checkpoint"])))
        result=phases[-1];health=api.health(result,spec)
        record={"design_sha256":api.sha(DESIGN),"case_id":name,"prior_record_sha256":s["prior_sha256"],"prefix_exact":exact,
            "result":result,"health":health,"phases":len(phases),"total_integrator_runtime_s":sum(r["runtime_seconds"] for r in phases),
            "worker_wall_s":time.perf_counter()-start,"candidate_work":opt.candidate.stats(),
            "observed_pv":result["time_s"]*spec["field_metadata"]["pv_per_second"]}
        api.write(out/"record.json",record,raw=True)
        api.write(out/"completion.json",{"record_sha256":api.sha(out/"record.json"),"prefix_sha256":api.sha(out/"prefix_result.json"),"status":result["status"]})
        print(name,result["status"],"time",result["time_s"],"runtime",record["total_integrator_runtime_s"],"prefix exact",exact,flush=True)
        return 0 if health["passed"] and result["status"] in ["present_at_horizon","incomplete_budget","paused_checkpoint"] else 4
    except Exception as exc:
        api.write(out/"failure.json",{"error":repr(exc),"traceback":traceback.format_exc()});raise
    finally:opt.candidate.legacy.swept_gap=original


def run():
    d=api.read(DESIGN);verify(d);api.require(not RUN.exists(),"immutable run exists");RUN.mkdir(parents=True)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS="1",MKL_NUM_THREADS="1",OMP_NUM_THREADS="1",PYTHONDONTWRITEBYTECODE="1")
    start=time.perf_counter();records={}
    try:
        for s in d["cases"]:
            api.require(time.perf_counter()-start<d["budget"]["total_s"],"total budget reached")
            name=s["case_id"]
            with (RUN/(name+".stdout.txt")).open("x") as out,(RUN/(name+".stderr.txt")).open("x") as err:
                p=subprocess.run([sys.executable,"-B","-u",__file__,"worker","--case",name],env=env,stdout=out,stderr=err)
            api.require(p.returncode==0,"worker failed: "+name)
            records[name]=api.sha(RUN/name/"record.json")
            r=api.read(RUN/name/"record.json");print(name,r["result"]["status"],"seconds",round(r["total_integrator_runtime_s"],3),flush=True)
        verify(d);api.write(RUN/"completion.json",{"design_sha256":api.sha(DESIGN),"records":records,"wall_s":time.perf_counter()-start})
    except Exception as exc:
        api.write(RUN/"failure.json",{"error":repr(exc),"traceback":traceback.format_exc(),"records":records});raise


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("action",choices=["prepare","run","worker"]);p.add_argument("--case")
    a=p.parse_args()
    if a.action=="prepare":prepare()
    elif a.action=="run":run()
    else:raise SystemExit(worker(a.case))
