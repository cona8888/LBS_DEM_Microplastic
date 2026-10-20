"""Freeze and execute a serial, bounded short-time numerical test matrix."""
from __future__ import annotations

import argparse
import copy
import os
import platform
import subprocess
import sys
import time
import traceback
from pathlib import Path

import corrected_transport_v1 as api

ROOT, DESIGN = api.ROOT, api.DESIGN


def prepare():
    api.require(not DESIGN.exists(), "immutable design exists")
    old = api.read(ROOT / "stage108_runs/first_iid_fibre_2pv_01/manifest.json")
    api.verify_mapping(old["source_hashes"])
    api.verify_mapping(old["input_hashes"])
    cases = [api.prepare_spec(seed,factor,cpd,shape,ref) for seed,factor,cpd in api.FLOW_COMBINATIONS
             for shape in api.SHAPES for ref in api.REFINEMENTS]
    sources = dict(old["source_hashes"])
    for module in list(sys.modules.values()):
        filename = getattr(module,"__file__",None)
        if filename and Path(filename).suffix == ".py" and Path(filename).resolve().is_relative_to(ROOT):
            sources[str(Path(filename).resolve())] = api.sha(filename)
    sources[str(Path(__file__).resolve())] = api.sha(__file__)
    inputs = {str(api.PROTOCOL):api.sha(api.PROTOCOL), str(api.fields.EVALUATION):api.sha(api.fields.EVALUATION),
              str(ROOT / "stage114_evaluations/stationary_flow_requalification_20260915/completion.json"):
                  api.sha(ROOT / "stage114_evaluations/stationary_flow_requalification_20260915/completion.json")}
    for spec in cases:
        for key in ["field","geometry","evaluation"]:
            value = spec["field_metadata"][key]
            inputs[value["path"]] = value["sha256"]
    config = {"schema":"matdem.stage115.corrected-flow-short-time.v1", "cases":cases,
        "source_hashes":sources,"input_hashes":inputs,
        "research_contract":{
            "question":"Does the unchanged both-shape contact/transport implementation remain healthy, restartable and locally time-resolved with corrected SI fields? How large is short-time CPD2/CPD4 sensitivity?",
            "system":"3D dilute independent rigid particles in fixed saturated periodic sand with prescribed one-way steady flow and downstream observation plane.",
            "initialization":"Original Stage109 sentinel IDs, zero initial velocities, same centre/orientation paired across shapes; no outcome-dependent replacement.",
            "horizon_s":.25,"refinement_factors":[1,.5,.25],
            "refinement_rule":"Multiply displacement, relaxation, angular and maximum-time-step caps together; each step rebuilds contact/inertial systems.",
            "observables":"Status, position/b, apolar fibre-axis angle, velocity, contact steps, force/contact/momentum closure, swept clearance, particle Re, physical time, achieved-flow PV and measured runtime.",
            "claim_boundary":"Short-time numerical diagnostic only. Not full-horizon convergence, experimental validation, export fraction, or a full-trajectory cost estimate.",
            "omissions":"No flexible fibre, particle-particle interactions, mobile sand, chemical adhesion, clogging or flow feedback."},
        "budget":{"wall_s_per_run":45.,"total_worker_budget_s":1800.,"serial_fresh_processes":True,"automatic_resume":False},
        "acceptance":{"contact_residual_max":1e-10,"force_momentum_max":1e-8,"swept_gap_min_over_b":-1e-5,"particle_Re_max":3.,
            "fine_medium_position_over_b_max":.02,"fine_medium_axis_angle_rad_max":.01,
            "fine_medium_translational_velocity_relative_max":.05,
            "refinement_trend_multiplier_max":1.1,"trend_roundoff_floor":1e-8,
            "trend_waiver_fraction_of_budget":.1,"exit_time_difference_s_max":.0025,
            "spatial_comparison":"Quantify, do not automatically pass transport resolution from this prefix.",
            "incomplete_rule":"Preserve unresolved and failed cases. Stop on physical/numerical/source failure; record budget incompletes without counting them as horizon observations."},
        "restart_test":{"case_id":"s2_ar4_f1p0_cpd2_dt1","pause_rule":"floor(0.75*completed baseline accepted steps), at least 1 and strictly before terminal step", "fresh_process_resume":True,
            "comparison":"Exact final state, physical counters and health; ignore runtime/checkpoint and solver-work counters. Record whether checkpoint actually exercises contact."},
        "authority":{"short_diagnostics":True,"population_campaign":False,"new_physics":False}}
    config["binding"] = api.digest(config)
    DESIGN.parent.mkdir(parents=True,exist_ok=True)
    api.write(DESIGN,config)
    print("FROZEN",len(cases),"cases",api.sha(DESIGN),flush=True)


def worker(args):
    design=api.read(DESIGN)
    api.verify_design(design)
    spec=next(c for c in design["cases"] if c["case_id"]==args.case)
    output=args.output.resolve()
    api.require(output.is_relative_to(ROOT/"stage115_runs") and not output.exists(),"fresh scoped output required")
    checkpoint=None
    if args.restart:
        prior=api.read(args.restart)
        api.require(prior["design_sha256"]==api.sha(DESIGN) and prior["case_id"]==args.case,"restart input binding drift")
        checkpoint=prior["result"]["checkpoint"]
        api.require(checkpoint is not None and checkpoint["state_sha256"]==api.digest(checkpoint["state"]),"invalid checkpoint digest")
    output.mkdir(parents=True)
    api.write(output/"launch.json",{"case_id":args.case,"design_sha256":api.sha(DESIGN),"pause_after_steps":args.pause,
        "prior_record_sha256":api.sha(args.restart) if args.restart else None,"command":sys.argv,
        "environment":{"python":platform.python_version(),"numpy":api.np.__version__,"threads":{k:os.environ.get(k) for k in ["OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","OMP_NUM_THREADS"]}}})
    started=time.perf_counter()
    try:
        result=api.execute(spec,api.digest([design["binding"],args.case]),design["budget"]["wall_s_per_run"],checkpoint,args.pause)
        result=api.normalized(result)
        gate=api.health(result,spec)
        cp=result.get("checkpoint")
        resumable=bool(cp is not None and cp["state_sha256"]==api.digest(cp["state"]))
        record={"case_id":args.case,"design_sha256":api.sha(DESIGN),"result":result,"health":gate,
            "checkpoint_verified":resumable,"observed_pv":result["time_s"]*spec["field_metadata"]["pv_per_second"],
            "end_to_end_worker_seconds":time.perf_counter()-started,"prior_record_sha256":api.sha(args.restart) if args.restart else None}
        api.write(output/"record.json",record,raw=True)
        api.write(output/"completion.json",{"status":result["status"],"health_passed":gate["passed"],"record_sha256":api.sha(output/"record.json")})
        print(args.case,result["status"],"t",result["time_s"],"steps",result["steps"],"contacts",result["contact_steps"],"healthy",gate["passed"],flush=True)
        return 0 if gate["passed"] and result["status"] in ["present_at_horizon","full_window_exit","incomplete_budget","paused_checkpoint"] else 4
    except Exception as exc:
        api.write(output/"failure.json",{"error":repr(exc),"traceback":traceback.format_exc()})
        raise


def campaign(output):
    design=api.read(DESIGN)
    api.require(not output.exists() and output.is_relative_to(ROOT/"stage115_runs"),"fresh scoped run required")
    api.verify_design(design)
    audit=api.read(DESIGN.parent/"pre_execution_audit.json")
    api.require(audit["passed"] is True and audit["design_sha256"] == api.sha(DESIGN), "pre-execution audit missing or stale")
    output.mkdir(parents=True)
    api.write(output/"manifest.json",{"design_sha256":api.sha(DESIGN),"runner_sha256":api.sha(__file__),"case_order":[c["case_id"] for c in design["cases"]]})
    environment=os.environ.copy()
    environment.update({"OPENBLAS_NUM_THREADS":"1","MKL_NUM_THREADS":"1","OMP_NUM_THREADS":"1","PYTHONDONTWRITEBYTECODE":"1"})
    started=time.perf_counter()
    records={}
    def launch(case,path,extra=None):
        command=[sys.executable,"-B","-u",str(Path(__file__).resolve()),"worker","--case",case,"--output",str(path)]+(extra or [])
        with (output/(path.name+".stdout.txt")).open("x",encoding="utf-8") as stdout, (output/(path.name+".stderr.txt")).open("x",encoding="utf-8") as stderr:
            completed=subprocess.run(command,env=environment,stdout=stdout,stderr=stderr,check=False)
        api.require(completed.returncode==0,"worker failed: "+case+"; see immutable stderr/result")
        record=api.read(path/"record.json")
        print(path.name,record["result"]["status"],"time",record["result"]["time_s"],"contacts",record["result"]["contact_steps"],flush=True)
        return record
    try:
        for spec in design["cases"]:
            if time.perf_counter()-started>design["budget"]["total_worker_budget_s"]:
                raise RuntimeError("total diagnostic budget reached; remaining cases are unrun")
            name=spec["case_id"]
            launch(name,output/name)
            records[name]=api.sha(output/name/"record.json")
        chosen=design["restart_test"]["case_id"]
        baseline=api.read(output/chosen/"record.json")["result"]
        restart={"performed":False}
        if baseline["status"]=="present_at_horizon" and baseline["steps"]>2:
            pause=max(1,min(baseline["steps"]-1,int(.75*baseline["steps"])))
            paused=launch(chosen,output/"restart_pause",["--pause",str(pause)])
            api.require(paused["result"]["status"]=="paused_checkpoint" and paused["checkpoint_verified"],"pause not reached")
            launch(chosen,output/"restart_resume",["--restart",str(output/"restart_pause/record.json")])
            restart={"performed":True,"pause_after_steps":pause,"pause_record_sha256":api.sha(output/"restart_pause/record.json"),"resume_record_sha256":api.sha(output/"restart_resume/record.json")}
        api.verify_mapping(design["source_hashes"])
        api.verify_mapping(design["input_hashes"])
        api.write(output/"completion.json",{"status":"diagnostics_complete_pending_independent_evaluation","design_sha256":api.sha(DESIGN),"records":records,"restart":restart,"wall_seconds":time.perf_counter()-started})
    except Exception as exc:
        api.write(output/"failure.json",{"error":repr(exc),"traceback":traceback.format_exc(),"completed_records":records,"unrun_remain_visible":True})
        raise


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode",choices=["prepare","run","worker"])
    p.add_argument("--output",type=Path)
    p.add_argument("--case")
    p.add_argument("--restart",type=Path)
    p.add_argument("--pause",type=int)
    args=p.parse_args()
    if args.mode=="prepare":prepare()
    elif args.mode=="worker":raise SystemExit(worker(args))
    else:campaign(args.output.resolve())
