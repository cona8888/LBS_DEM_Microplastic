"""One prospective extra level for every failed seed-2 fibre velocity check."""
import argparse
import copy
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

import complete_short_matrix_v1 as parent
api=parent.api
ROOT=parent.ROOT
DESIGN=ROOT/"stage116_designs/fibre_cost_attribution_20260915/velocity_refinement_01.json"
RUN=ROOT/"stage116_runs/fibre_cost_attribution_20260915/velocity_refinement_01"
PREVIOUS=ROOT/"stage116_evaluations/fibre_cost_attribution_20260915/short_matrix_evaluation_01/results.json"


def prepare():
    api.require(not DESIGN.exists(),"immutable design exists")
    parent.verify(api.read(parent.DESIGN));old=api.read(api.DESIGN)
    evaluation=api.read(PREVIOUS)
    api.require(api.read(PREVIOUS.parent/"completion.json")["results_sha256"]==api.sha(PREVIOUS),"previous evaluation drift")
    failed=[g for g in evaluation["three_level_time_groups"] if not g["passed"]]
    api.require(len(failed)==4 and all(g["seed"]==2 and g["shape"]=="rigid_prolate_ar4" and [k for k,v in g["checks"].items() if not v]==["velocity_error"] for g in failed),"unexpected failure set")
    cases=[]
    for g in failed:
        base=next(s for s in old["cases"] if s["case_id"]==g["case_ids"][-1])
        new=copy.deepcopy(base)
        new["refinement"]=.125;new["case_id"]=api.case_id(g["seed"],g["flow_factor"],g["cpd"],g["shape"],.125)
        for key in api.DT_CONTROLS:new["config"]["numerics"][key]*=.5
        cases.append({"spec":new,"parent_case_id":base["case_id"],"triplet":[g["case_ids"][1],g["case_ids"][2],new["case_id"]]})
    d={"question":"Does one additional uniform refinement satisfy the unchanged short-time velocity gate in all four failing fibre cases?",
       "cases":cases,"budget":{"per_case_s":45.,"total_s":240.,"further_automatic_refinement":False},
       "acceptance":old["acceptance"],"comparison":"Latest three levels: half, quarter, eighth of all four original timestep caps. Preserve failed original triplets.",
       "physical_changes":[],"source_hashes":{str(Path(__file__).resolve()):api.sha(__file__)},
       "parent_design_sha256":api.sha(parent.DESIGN),"prior_evaluation_sha256":api.sha(PREVIOUS),
       "claim_boundary":"Only the 0.25-s response; no full-trajectory accuracy, release ranking or population dispatch."}
    d["binding"]=api.digest(d);api.write(DESIGN,d);print("FROZEN REFINEMENT",api.sha(DESIGN))


def verify(d):
    api.require(d["binding"]==api.digest({k:v for k,v in d.items() if k!="binding"}),"refinement design drift")
    api.verify_mapping(d["source_hashes"]);parent.verify(api.read(parent.DESIGN))
    api.require(api.sha(parent.DESIGN)==d["parent_design_sha256"] and api.sha(PREVIOUS)==d["prior_evaluation_sha256"],"parent evidence drift")
    old=api.read(api.DESIGN)
    for c in d["cases"]:
        reference=copy.deepcopy(next(s for s in old["cases"] if s["case_id"]==c["parent_case_id"]))
        reference["case_id"]=c["spec"]["case_id"];reference["refinement"]=.125
        for key in api.DT_CONTROLS:reference["config"]["numerics"][key]*=.5
        api.require(reference==c["spec"],"non-timestep change in refinement")


def worker(name):
    d=api.read(DESIGN);verify(d);s=next(c["spec"] for c in d["cases"] if c["spec"]["case_id"]==name)
    out=RUN/name;api.require(not out.exists(),"immutable worker exists");out.mkdir(parents=True)
    api.write(out/"launch.json",{"design_sha256":api.sha(DESIGN),"command":sys.argv})
    original=parent.opt.candidate.legacy.swept_gap
    try:
        parent.opt.candidate.legacy.swept_gap=parent.opt.candidate.swept_gap
        result=api.normalized(api.execute(s,api.digest([d["binding"],name]),45.))
        health=api.health(result,s)
        api.write(out/"record.json",{"case_id":name,"design_sha256":api.sha(DESIGN),"result":result,"health":health,"candidate_work":parent.opt.candidate.stats()},raw=True)
        api.write(out/"completion.json",{"record_sha256":api.sha(out/"record.json"),"status":result["status"]})
        print(name,result["status"],"seconds",result["runtime_seconds"],flush=True)
        return 0 if health["passed"] and result["status"] in ["present_at_horizon","incomplete_budget"] else 4
    except Exception as exc:
        api.write(out/"failure.json",{"error":repr(exc),"traceback":traceback.format_exc()});raise
    finally:parent.opt.candidate.legacy.swept_gap=original


def run():
    d=api.read(DESIGN);verify(d);api.require(not RUN.exists(),"immutable run exists");RUN.mkdir(parents=True)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS="1",MKL_NUM_THREADS="1",OMP_NUM_THREADS="1",PYTHONDONTWRITEBYTECODE="1")
    start=time.perf_counter();records={}
    try:
        for c in d["cases"]:
            name=c["spec"]["case_id"];api.require(time.perf_counter()-start<d["budget"]["total_s"],"refinement budget reached")
            with (RUN/(name+".stdout.txt")).open("x") as out,(RUN/(name+".stderr.txt")).open("x") as err:
                p=subprocess.run([sys.executable,"-B","-u",__file__,"worker","--case",name],env=env,stdout=out,stderr=err)
            api.require(p.returncode==0,"worker failed: "+name)
            records[name]=api.sha(RUN/name/"record.json")
            r=api.read(RUN/name/"record.json");print(name,r["result"]["status"],round(r["result"]["runtime_seconds"],3),flush=True)
        verify(d);api.write(RUN/"completion.json",{"design_sha256":api.sha(DESIGN),"records":records,"wall_s":time.perf_counter()-start})
    except Exception as exc:
        api.write(RUN/"failure.json",{"error":repr(exc),"traceback":traceback.format_exc(),"records":records});raise


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("action",choices=["prepare","run","worker"]);p.add_argument("--case")
    a=p.parse_args()
    if a.action=="prepare":prepare()
    elif a.action=="run":run()
    else:raise SystemExit(worker(a.case))
