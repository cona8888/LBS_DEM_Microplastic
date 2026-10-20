"""Frozen synthetic bounds and matched saved-state replay A/B verification."""
import argparse
import contextlib
import os
from pathlib import Path
import subprocess
import sys
import time

import profile_fibre_cost_v1 as profile
import bounded_sweep_v1 as candidate
api=profile.api
DESIGN=profile.ROOT/"stage116_designs/fibre_cost_attribution_20260915/optimization_01.json"
RUN=profile.ROOT/"stage116_runs/fibre_cost_attribution_20260915/optimization_01"


def prepare():
    api.require(not DESIGN.exists(),"immutable optimization design exists")
    profile.verify(api.read(profile.DESIGN))
    d={"question":"Can conservative geometric lower bounds omit irrelevant swept-distance minimizers without changing accepted states or rejection decisions?",
       "proof":"Rigid-body Hausdorff displacement <= (|v|+a|omega|)*dt. Distance-to-solid is Lipschitz; combine endpoint cones to bound an interval. Skip only above the incumbent minimum, with a positive centre-to-solid lower bound and a conservative floating margin.",
       "unchanged":"Geometry, four-subinterval bounded minimizer, Brent tolerance, physical laws, timestep caps, health gates and checkpoints.",
       "limitations":"Retains reference minimizer limitations. Roundoff margin is not interval arithmetic. Selected local replay timings are not a full-trajectory cost estimate.",
       "synthetic":{"seed":116,"cases":180,"bound_samples":17,"acceptance":"Identical reject/accept decision and exact accepted gap; sampled true gaps never below bound beyond 1e-14 m."},
       "replay":{"samples":api.read(profile.DESIGN)["samples"],"order":["reference_1","candidate_1","candidate_2","reference_2"],"seconds_per_worker":45.,"total_seconds":600.},
       "gates":{"accepted_state_and_physical_counters":"exact equality excluding runtime and implementation-work counters; includes checkpoint state/hash and accepted minimum gap",
                "health":"all inherited Stage115 gates","speedup_required_s2_s3":1.25,"max_s1_slowdown":1.05},
       "source_hashes":{str(Path(p).resolve()):api.sha(p) for p in [__file__,candidate.__file__]},
       "profile_design_sha256":api.sha(profile.DESIGN),"prior_design_sha256":api.sha(api.DESIGN),"no_population_campaign":True}
    d["binding"]=api.digest(d);api.write(DESIGN,d)
    print("FROZEN OPTIMIZATION",api.sha(DESIGN))


def verify(d):
    api.require(api.digest({k:v for k,v in d.items() if k!="binding"})==d["binding"],"optimization design drift")
    api.verify_mapping(d["source_hashes"]);profile.verify(api.read(profile.DESIGN))
    api.require(api.sha(profile.DESIGN)==d["profile_design_sha256"] and api.sha(api.DESIGN)==d["prior_design_sha256"],"parent design drift")


def synthetic():
    d=api.read(DESIGN);verify(d)
    out=RUN/"synthetic";api.require(not out.exists(),"immutable synthetic results exist")
    rng=api.np.random.default_rng(d["synthetic"]["seed"])
    rows=[];bound_checks=0
    for i in range(d["synthetic"]["cases"]):
        a=2e-4;b=a/(1 if i%12==0 else 4);length=.006
        x=rng.uniform(-length,2*length,3);p=rng.normal(size=3);p/=api.np.linalg.norm(p)
        directions=rng.normal(size=(6,3));directions/=api.np.linalg.norm(directions,axis=1)[:,None]
        distances=rng.uniform(1.01*a,4*a,6)
        centres=api.np.mod(x+directions*distances[:,None],length)
        radii=rng.uniform(.1*a,1.4*a,6)
        geometry=candidate.original.GrainGeometry(centres,radii,length)
        v=rng.normal(size=6)*.002;dt=0. if i%17==0 else float(rng.uniform(1e-6,.004))
        if i%11==0:v[3:]=0
        ref=candidate._reference_sweep(geometry,x,p,v,a,b,dt)
        got=candidate.swept_gap(geometry,x,p,v,a,b,dt)
        reject=ref < -1e-5*b
        matched=bool((got < -1e-5*b)==reject and (reject or ref==got))
        motion=candidate.original._FixedMotion(x,p,v,a)
        speed=float(api.np.linalg.norm(v[:3])+a*motion.angular_speed)
        for k in range(6):
            delta=centres[k]-x;delta-=length*api.np.round(delta/length);c=x+delta
            def fun(t):
                xx,pp=motion.at(t)
                return candidate.original._gap_at_pose(xx,pp,a,b,c,radii[k])
            f0,f1=fun(0),fun(dt)
            lower=candidate.interval_lower(f0,f1,speed,dt,0,dt,1e-12)
            for t in api.np.linspace(0,dt,d["synthetic"]["bound_samples"]):
                api.require(fun(t)>=lower-1e-14,"geometric bound violation")
                bound_checks+=1
        rows.append({"index":i,"reference":ref,"candidate":got,"rejected":reject,"passed":matched})
    passed=all(r["passed"] for r in rows)
    out.mkdir(parents=True)
    api.write(out/"results.json",{"passed":passed,"rows":rows,"bound_checks":bound_checks,"design_sha256":api.sha(DESIGN)},raw=True)
    api.write(out/"completion.json",{"passed":passed,"results_sha256":api.sha(out/"results.json")})
    print("synthetic",passed,"cases",len(rows),"bound checks",bound_checks,flush=True)
    api.require(passed,"synthetic equivalence failed")


def worker(sample,mode):
    d=api.read(DESIGN);verify(d)
    s=next(s for s in d["replay"]["samples"] if s["sample"]==sample)
    out=RUN/(sample+"_"+mode);api.require(not out.exists(),"immutable worker exists")
    prior=api.read(s["record_path"])
    old=api.read(api.DESIGN);spec=next(x for x in old["cases"] if x["case_id"]==s["case_id"])
    previous=candidate.legacy.swept_gap
    out.mkdir(parents=True)
    api.write(out/"launch.json",{"command":sys.argv,"design_sha256":api.sha(DESIGN),"prior_record_sha256":api.sha(s["record_path"])})
    try:
        if mode.startswith("candidate"):candidate.legacy.swept_gap=candidate.swept_gap
        result=api.normalized(api.execute(spec,api.digest([old["binding"],s["case_id"]]),45.,prior["result"]["checkpoint"],s["pause_after_steps"]))
        health=api.health(result,spec)
        passed=result["status"]=="paused_checkpoint" and result["steps"]==s["pause_after_steps"] and health["passed"]
        api.write(out/"record.json",{"sample":sample,"mode":mode,"design_sha256":api.sha(DESIGN),"result":result,"health":health,"passed":passed,"optimization_stats":candidate.stats()},raw=True)
        api.write(out/"completion.json",{"passed":passed,"record_sha256":api.sha(out/"record.json")})
        print(sample,mode,result["runtime_seconds"],"s",passed,flush=True)
        return 0 if passed else 4
    finally:candidate.legacy.swept_gap=previous


def run():
    d=api.read(DESIGN);verify(d);api.require(not RUN.exists(),"immutable run exists")
    RUN.mkdir(parents=True);synthetic()
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS="1",MKL_NUM_THREADS="1",OMP_NUM_THREADS="1",PYTHONDONTWRITEBYTECODE="1")
    start=time.perf_counter();records={}
    for s in d["replay"]["samples"]:
        for mode in d["replay"]["order"]:
            api.require(time.perf_counter()-start<d["replay"]["total_seconds"],"optimization budget reached")
            name=s["sample"]+"_"+mode
            with (RUN/(name+".stdout.txt")).open("x") as out,(RUN/(name+".stderr.txt")).open("x") as err:
                p=subprocess.run([sys.executable,"-B","-u",__file__,"worker","--sample",s["sample"],"--mode",mode],env=env,stdout=out,stderr=err)
            api.require(p.returncode==0,"worker failed: "+name)
            records[name]=api.sha(RUN/name/"record.json")
            r=api.read(RUN/name/"record.json");print(name,round(r["result"]["runtime_seconds"],3),flush=True)
    verify(d);api.write(RUN/"completion.json",{"design_sha256":api.sha(DESIGN),"records":records,"wall_s":time.perf_counter()-start})


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("action",choices=["prepare","run","worker"])
    p.add_argument("--sample");p.add_argument("--mode");args=p.parse_args()
    if args.action=="prepare":prepare()
    elif args.action=="run":run()
    else:raise SystemExit(worker(args.sample,args.mode))
