"""Bounded, unchanged-core cost attribution with exact profiled/plain matching."""
from __future__ import annotations
import argparse
import cProfile
import os
from pathlib import Path
import platform
import pstats
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"stage115_staging"))
import corrected_transport_v1 as api

DESIGN=ROOT/"stage116_designs/fibre_cost_attribution_20260915/design_01.json"
RUN=ROOT/"stage116_runs/fibre_cost_attribution_20260915/profile_01"
PRIOR=ROOT/"stage115_runs/corrected_flow_short_time_20260915/diagnostic_01"
SAMPLES=[("precontact_s3","s3_ar4_f1p0_cpd2_dt4",32),
         ("contact_s2","s2_ar4_f1p0_cpd2_dt4",32),
         ("rejected_steps_s1","s1_ar4_f1p0_cpd2_dt2",8)]


def prepare():
    api.require(not DESIGN.exists(),"immutable design exists")
    old=api.read(api.DESIGN);api.verify_design(old)
    seal=api.read(ROOT/"stage115_evaluations/corrected_flow_short_time_20260915/completion.json")
    api.verify_mapping(seal["artifacts"])
    samples=[]
    for name,case,steps in SAMPLES:
        path=PRIOR/case/"record.json";r=api.read(path)
        api.require(api.sha(path)==api.read(path.parent/"completion.json")["record_sha256"],"prior record drift")
        cp=r["result"]["checkpoint"]
        api.require(r["checkpoint_verified"] and cp["state_sha256"]==api.digest(cp["state"]),"invalid prior checkpoint")
        samples.append(dict(sample=name,case_id=case,record_path=str(path),record_sha256=api.sha(path),
                            extra_accepted_steps=steps,pause_after_steps=cp["state"]["steps"]+steps))
    d={"question":"Which unchanged fibre calculations dominate cost, before and during active contact and repeated-step rejection?",
       "system":"Existing 3D rigid AR4 particle, fixed periodic saturated sand, corrected prescribed SI flow; unchanged physical and numerical laws.",
       "claim":"Local CPU cost attribution only; no full-horizon accuracy, affordability, release or experimental-validation inference.",
       "samples":samples,"order":["plain_1","profile","plain_2"],
       "budget":{"per_worker_seconds":45.,"total_seconds":450.},
       "gates":{"pause_and_checkpoint_required":True,"exact_profile_plain_state_and_counters":True,"all_existing_numerical_health":True,
                "profile_overhead_separated":True,"no_automatic_retries":True},
       "prior_design_sha256":api.sha(api.DESIGN),"runner_sha256":api.sha(__file__),
       "next_decision":"Only optimize after identifying the dominant functions; require independent equivalence and unchanged health gates."}
    d["binding"]=api.digest(d)
    DESIGN.parent.mkdir(parents=True,exist_ok=True);api.write(DESIGN,d)
    print("FROZEN",api.sha(DESIGN))


def verify(d):
    api.require(api.digest({k:v for k,v in d.items() if k!="binding"})==d["binding"],"design drift")
    api.require(api.sha(__file__)==d["runner_sha256"] and api.sha(api.DESIGN)==d["prior_design_sha256"],"runner/prior design drift")
    api.verify_design(api.read(api.DESIGN))
    for s in d["samples"]:api.require(api.sha(s["record_path"])==s["record_sha256"],"checkpoint record drift")


def worker(sample,mode):
    d=api.read(DESIGN);verify(d)
    selected=next(s for s in d["samples"] if s["sample"]==sample)
    out=RUN/(sample+"_"+mode);api.require(not out.exists(),"immutable worker exists")
    old=api.read(api.DESIGN);spec=next(s for s in old["cases"] if s["case_id"]==selected["case_id"])
    prior=api.read(selected["record_path"]);cp=prior["result"]["checkpoint"]
    out.mkdir(parents=True)
    api.write(out/"launch.json",{"design_sha256":api.sha(DESIGN),"sample":sample,"mode":mode,"command":sys.argv,
         "python":platform.python_version(),"numpy":api.np.__version__,"threads":{k:os.getenv(k) for k in ["OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"]}})
    profiler=cProfile.Profile();original=api.BoundRunner
    class ProfileRunner(original):
        @classmethod
        def integrate(cls,*args,**kwargs):
            profiler.enable()
            try:return super().integrate(*args,**kwargs)
            finally:profiler.disable()
    try:
        if mode=="profile":api.BoundRunner=ProfileRunner
        started=time.perf_counter()
        result=api.normalized(api.execute(spec,api.digest([old["binding"],selected["case_id"]]),45.,cp,selected["pause_after_steps"]))
        elapsed=time.perf_counter()-started
        result_health=api.health(result,spec)
        if mode=="profile":
            profiler.dump_stats(str(out/"calls.prof"))
            rows=[]
            for (file,line,func),(primitive,calls,exclusive,cumulative,callers) in pstats.Stats(profiler).stats.items():
                rows.append({"file":file,"line":line,"function":func,"primitive_calls":primitive,"calls":calls,
                    "exclusive_s":exclusive,"cumulative_s":cumulative,
                    "callers":[{"file":k[0],"line":k[1],"function":k[2],"stats":v} for k,v in callers.items()]})
            api.write(out/"profile.json",{"rows":sorted(rows,key=lambda r:r["cumulative_s"],reverse=True),
                "exclusive_sum_s":sum(r["exclusive_s"] for r in rows),
                "scope":"Only integration is profiled, excluding field loading and output; cumulative rows overlap and must not be summed."})
        checkpoint=result.get("checkpoint")
        checks={"paused_at_declared_step":result["status"]=="paused_checkpoint" and result["steps"]==selected["pause_after_steps"],
                "checkpoint_integrity":checkpoint is not None and checkpoint["state_sha256"]==api.digest(checkpoint["state"]),
                "numerical_health":result_health["passed"]}
        api.write(out/"record.json",{"sample":sample,"mode":mode,"design_sha256":api.sha(DESIGN),"prior_record_sha256":selected["record_sha256"],
             "result":result,"health":result_health,"checks":checks,"passed":all(checks.values()),"worker_wall_s":elapsed},raw=True)
        api.write(out/"completion.json",{"passed":all(checks.values()),"record_sha256":api.sha(out/"record.json"),
            "artifacts":{p.name:api.sha(p) for p in out.iterdir()}})
        print(sample,mode,result["status"],"seconds",result["runtime_seconds"],"steps",result["steps"]-cp["state"]["steps"],flush=True)
        return 0 if all(checks.values()) else 4
    except Exception as exc:
        api.write(out/"failure.json",{"error":repr(exc),"traceback":traceback.format_exc()});raise
    finally:api.BoundRunner=original


def run():
    d=api.read(DESIGN);verify(d)
    api.require(not RUN.exists(),"immutable run exists");RUN.mkdir(parents=True)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS="1",MKL_NUM_THREADS="1",OMP_NUM_THREADS="1",PYTHONDONTWRITEBYTECODE="1")
    start=time.perf_counter();records={}
    try:
        for s in d["samples"]:
            for mode in d["order"]:
                api.require(time.perf_counter()-start<d["budget"]["total_seconds"],"total profile budget reached")
                name=s["sample"]+"_"+mode
                with (RUN/(name+".stdout.txt")).open("x") as stdout,(RUN/(name+".stderr.txt")).open("x") as stderr:
                    p=subprocess.run([sys.executable,"-B","-u",__file__,"worker","--sample",s["sample"],"--mode",mode],env=env,stdout=stdout,stderr=stderr)
                api.require(p.returncode==0,"incomplete/failed worker: "+name)
                r=api.read(RUN/name/"record.json")
                records[name]=api.sha(RUN/name/"record.json")
                print(name,round(r["result"]["runtime_seconds"],3),"s",flush=True)
        verify(d)
        api.write(RUN/"completion.json",{"status":"complete_pending_cost_evaluation","design_sha256":api.sha(DESIGN),"records":records,"wall_s":time.perf_counter()-start})
    except Exception as exc:
        api.write(RUN/"failure.json",{"error":repr(exc),"traceback":traceback.format_exc(),"records":records});raise


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("action",choices=["prepare","run","worker"])
    p.add_argument("--sample");p.add_argument("--mode");args=p.parse_args()
    if args.action=="prepare":prepare()
    elif args.action=="run":run()
    else:raise SystemExit(worker(args.sample,args.mode))
