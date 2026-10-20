"""Independent ledger and short-time solution verification, not release inference."""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

import corrected_transport_v1 as api


def independent_health(result,spec):
    def safe(key,limit):
        value=result.get(key)
        return type(value) in (float,int) and math.isfinite(value) and 0 <= value <= limit
    x=np.array(result["position_m"])
    p=np.array(result["orientation"])
    q=np.array(result["velocity_generalized"])
    a,b,_=spec["config"]["prolate_semiaxes_m"]
    with np.load(spec["field_metadata"]["geometry"]["path"]) as g:
        geometry=api.frozen.h.geometry_exact_v1.GrainGeometry(g["sand_centres_m"],g["sand_radii_m"],float(g["cell_length_m"][0]))
    contacts=geometry.contacts(x,p,a,b,0.)
    final_gap=min([c[1] for c in contacts],default=0.)
    outlet_gap=float(x[0]-math.sqrt(b*b+(a*a-b*b)*p[0]**2)-spec["field_metadata"]["cell_length_m"])
    status=result["status"]
    event_consistency=(outlet_gap>=-1e-12 if status=="full_window_exit" else outlet_gap<1e-12)
    checks={"finite_final_state":bool(np.isfinite(np.r_[x,p,q]).all()),
            "unit_axis":bool(abs(np.linalg.norm(p)-1)<1e-10),
            "final_exact_geometry":bool(final_gap>=-1e-5*b),
            "swept_clearance":result["minimum_gap_m"] is not None and result["minimum_gap_m"]>=-1e-5*b,
            "contact":safe("max_contact_residual",1e-10),"force":safe("max_force_residual",1e-8),
            "momentum":safe("max_momentum_residual",1e-8),"particle_Re":safe("max_reynolds",3),
            "whole_body_outlet_status":event_consistency,"nonabsorbing_dwell":result["dwell_is_absorbing"] is False,
            "time_inside_horizon":math.isfinite(result["time_s"]) and 0 <= result["time_s"] <= spec["horizon_s"]+1e-12,
            "horizon_status":status!="present_at_horizon" or abs(result["time_s"]-spec["horizon_s"])<1e-12}
    return {"passed":all(checks.values()),"checks":checks,"final_gap_m":float(final_gap),"whole_body_outlet_function_m":outlet_gap}


def difference(first,second,spec):
    r0,r1=first["result"],second["result"]
    b=spec["config"]["prolate_semiaxes_m"][1]
    angle=float(np.arccos(np.clip(abs(np.dot(r0["orientation"],r1["orientation"])),0,1))) if spec["shape"]=="rigid_prolate_ar4" else 0.
    delta=float(np.linalg.norm(np.array(r0["position_m"])-r1["position_m"])/b)
    speed_scale=max(np.linalg.norm(r1["velocity_generalized"][:3]),spec["field_metadata"]["achieved_mean_interstitial_velocity_m_s"])
    velocity=float(np.linalg.norm(np.array(r0["velocity_generalized"][:3])-r1["velocity_generalized"][:3])/speed_scale)
    return {"position_difference_over_b":delta,"apolar_axis_angle_rad":angle,
            "translational_velocity_relative_difference":velocity,"time_difference_s":abs(r0["time_s"]-r1["time_s"])}


def exit_benchmarks():
    mechanics=api.frozen.h.matrix_case_v1.mechanics
    rows=[]
    outlet=.01
    for shape,a,b in [("sphere",8e-5,8e-5),("ar4",2e-4,5e-5)]:
        for p in [[1.,0,0],[0,1.,0],[2**-.5,2**-.5,0]]:
            half=math.sqrt(b*b+(a*a-b*b)*p[0]**2)
            start=outlet+half-2e-6
            velocity=[1e-4,0,0,0,0,0]
            actual=mechanics.linear_pose_exit_time([start,0,0],p,velocity,a,b,outlet,.04)
            rows.append({"shape":shape,"axis":p,"expected_s":.02,"actual_s":actual,"passed":actual is not None and abs(actual-.02)<1e-12})
            rows.append({"shape":shape,"kind":"insufficient_duration","passed":mechanics.linear_pose_exit_time([start,0,0],p,velocity,a,b,outlet,.01) is None})
    a,b,omega=2e-4,5e-5,2.
    offset=(a+b)/2
    expected=math.acos(math.sqrt((offset**2-b**2)/(a**2-b**2)))/omega
    actual=mechanics.linear_pose_exit_time([outlet+offset,0,0],[1,0,0],[0,0,0,0,0,omega*a],a,b,outlet,math.pi/(2*omega))
    rows.append({"kind":"rotating_stationary_centre_ar4","expected_s":expected,"actual_s":actual,"passed":actual is not None and abs(actual-expected)<1e-12})
    return {"passed":all(r["passed"] for r in rows),"rows":rows,
            "scope":"Analytical translation and monotone rotation crossings for the unchanged within-step constant-velocity/rotation event helper, not universal detection of nonmonotone substep crossings."}


def main(run,output):
    api.require(not output.exists() and output.is_relative_to(api.ROOT/"stage115_evaluations"),"fresh scoped evaluation required")
    design=api.read(api.DESIGN)
    api.verify_design(design)
    root_completion=api.read(run/"completion.json") if (run/"completion.json").exists() else None
    run_manifest=api.read(run/"manifest.json")
    api.require(run_manifest["design_sha256"]==api.sha(api.DESIGN),"run/design drift")
    api.require(run_manifest["case_order"]==[c["case_id"] for c in design["cases"]],"frozen execution order drift")
    api.require(run_manifest["runner_sha256"]==design["source_hashes"][str(api.ROOT/"stage115_staging/run_corrected_diagnostics_v1.py")],"runner digest drift")
    if root_completion:
        api.require(root_completion["design_sha256"]==api.sha(api.DESIGN),"completion design drift")
        api.require(root_completion["status"]=="diagnostics_complete_pending_independent_evaluation","unexpected completion label")
        api.require(set(root_completion["records"])==set(run_manifest["case_order"]),"completion case set drift")
    ledger=[];records={};specs={c["case_id"]:c for c in design["cases"]}
    for spec in design["cases"]:
        name=spec["case_id"];path=run/name/"record.json"
        if not path.exists():
            ledger.append({"case_id":name,"status":"unrun_or_worker_incomplete","qualified":False})
            continue
        record=api.read(path)
        api.require(record["design_sha256"]==api.sha(api.DESIGN) and record["case_id"]==name,"record binding drift")
        api.require(api.read(path.parent/"completion.json")["record_sha256"]==api.sha(path),"record digest drift")
        launch=api.read(path.parent/"launch.json")
        api.require(launch["case_id"]==name and launch["design_sha256"]==api.sha(api.DESIGN),"launch binding drift")
        api.require(record["prior_record_sha256"] is None and launch["prior_record_sha256"] is None and launch["pause_after_steps"] is None,"unexpected initial-run continuation")
        if root_completion:
            api.require(root_completion["records"][name]==api.sha(path),"root record digest drift")
        recomputed=independent_health(record["result"],spec)
        r=record["result"]
        checkpoint=r.get("checkpoint")
        if r["status"]=="incomplete_budget":
            api.require(checkpoint is not None and record["checkpoint_verified"] and api.digest(checkpoint["state"])==checkpoint["state_sha256"],"incomplete checkpoint drift")
        observed_pv=r["time_s"]*spec["field_metadata"]["achieved_mean_interstitial_velocity_m_s"]/spec["field_metadata"]["cell_length_m"]
        api.require(abs(observed_pv-record["observed_pv"])<1e-14,"PV calculation drift")
        records[name]=record
        ledger.append({"case_id":name,"status":r["status"],"qualified":recomputed["passed"] and r["status"] in ["present_at_horizon","full_window_exit"],
            "health":recomputed,"time_s":r["time_s"],"observed_pv":observed_pv,"steps":r["steps"],"rejected_steps":r["rejected"],
            "contact_steps":r["contact_steps"],"runtime_s":r["runtime_seconds"],"worker_runtime_s":record["end_to_end_worker_seconds"],
            "contact_solver_retries":r["contact_solver_retries"],"total_contact_iterations":r["total_contact_iterations"],
            "pgs_seed_stats":r.get("short_pgs_seed_stats"),"nullspace_rescue":r.get("nullspace_rescue"),
            "max_particle_Re":r["max_reynolds"],"downstream_displacement_over_b":(r["position_m"][0]-spec["initial_state"]["position_m"][0])/spec["config"]["prolate_semiaxes_m"][1],
            "record_sha256":api.sha(path)})
    thresholds=design["acceptance"]
    time_groups=[]
    for seed,factor,cpd in api.FLOW_COMBINATIONS:
        for shape in api.SHAPES:
            names=[api.case_id(seed,factor,cpd,shape,r) for r in api.REFINEMENTS]
            item={"seed":seed,"flow_factor":factor,"cpd":cpd,"shape":shape,"case_ids":names}
            available=all(n in records and records[n]["result"]["status"] in ["present_at_horizon","full_window_exit"] for n in names)
            if not available:
                item.update({"passed":False,"reason":"incomplete three-level observation"})
            else:
                coarse,medium,fine=[records[n] for n in names]
                cm=difference(coarse,medium,specs[names[0]])
                mf=difference(medium,fine,specs[names[0]])
                def trend(metric,budget):
                    return bool(mf[metric]<=thresholds["refinement_trend_multiplier_max"]*cm[metric]+thresholds["trend_roundoff_floor"] or max(cm[metric],mf[metric])<=thresholds["trend_waiver_fraction_of_budget"]*budget)
                checks={"same_terminal_label":len({records[n]["result"]["status"] for n in names})==1,
                    "position_error":mf["position_difference_over_b"]<=thresholds["fine_medium_position_over_b_max"],
                    "axis_error":mf["apolar_axis_angle_rad"]<=thresholds["fine_medium_axis_angle_rad_max"],
                    "velocity_error":mf["translational_velocity_relative_difference"]<=thresholds["fine_medium_translational_velocity_relative_max"],
                    "position_refinement_trend":trend("position_difference_over_b",thresholds["fine_medium_position_over_b_max"]),
                    "axis_refinement_trend":trend("apolar_axis_angle_rad",thresholds["fine_medium_axis_angle_rad_max"]),
                    "terminal_time_error":mf["time_difference_s"]<=thresholds["exit_time_difference_s_max"]}
                item.update({"coarse_medium":cm,"medium_fine":mf,"checks":checks,"passed":all(checks.values())})
            time_groups.append(item)
    spatial=[]
    for shape in api.SHAPES:
        n2,n4=[api.case_id(2,1.,cpd,shape,.25) for cpd in [2,4]]
        if (n2 in records and n4 in records and records[n2]["result"]["status"] == records[n4]["result"]["status"] == "present_at_horizon"
                and abs(records[n2]["result"]["time_s"]-records[n4]["result"]["time_s"])<1e-12):
            spatial.append({"shape":shape,"cpd2_case":n2,"cpd4_case":n4,**difference(records[n2],records[n4],specs[n2]),
                "matched_complete_horizon":True,
                "cpd2_mean_m_s":specs[n2]["field_metadata"]["achieved_mean_interstitial_velocity_m_s"],
                "cpd4_mean_m_s":specs[n4]["field_metadata"]["achieved_mean_interstitial_velocity_m_s"],
                "limitation":"Matched nominal-flow diagnostic retaining each directly solved achieved speed; not a pure equal-speed discretization error or full-trajectory bound."})
        else:
            spatial.append({"shape":shape,"cpd2_case":n2,"cpd4_case":n4,"matched_complete_horizon":False,
                            "reason":"No matched complete finest-level horizon; unequal-time states must not be compared as spatial error."})
    restart={"performed":False,"passed":False}
    if root_completion and root_completion["restart"]["performed"]:
        pause=api.read(run/"restart_pause/record.json");resume=api.read(run/"restart_resume/record.json")
        api.require(api.sha(run/"restart_pause/record.json")==root_completion["restart"]["pause_record_sha256"],"pause digest changed")
        api.require(api.sha(run/"restart_resume/record.json")==root_completion["restart"]["resume_record_sha256"],"resume digest changed")
        chosen=design["restart_test"]["case_id"]
        reference=records[chosen]["result"]
        ignored={"runtime_seconds","checkpoint","nullspace_rescue","short_pgs_seed_stats","fail_fast_sweep_stats","within_pose_reuse_stats"}
        normalize=lambda value:{k:v for k,v in value.items() if k not in ignored}
        cp=pause["result"]["checkpoint"]
        checks={"pause_digest":api.digest(cp["state"])==cp["state_sha256"],
            "prior_chain":resume["prior_record_sha256"]==api.sha(run/"restart_pause/record.json"),
            "exact_split_equivalence":normalize(reference)==normalize(resume["result"]),
            "resume_health":independent_health(resume["result"],specs[chosen])["passed"]}
        restart={"performed":True,"passed":all(checks.values()),"checks":checks,"pause_time_s":pause["result"]["time_s"],
            "contact_steps_before_pause":pause["result"]["contact_steps"],"last_reaction_count_at_pause":pause["result"]["last_reaction_count"]}
    events=exit_benchmarks()
    failure_markers=[str(p.relative_to(run)) for p in run.rglob("failure.json")]
    nonempty_stderr=[str(p.relative_to(run)) for p in run.glob("*.stderr.txt") if p.stat().st_size]
    run_complete=root_completion is not None and not failure_markers and not nonempty_stderr and len(records)==36
    health_passed=run_complete and all(row["qualified"] for row in ledger)
    short_time_passed=health_passed and all(g["passed"] for g in time_groups) and restart["passed"] and events["passed"]
    status="short_time_numerics_passed_longer_contact_cost_required" if short_time_passed else "short_time_verification_failed_or_incomplete_preserved"
    result={"status":status,"passed":short_time_passed,"run_complete":run_complete,"all_short_runs_healthy_and_complete":health_passed,
        "ledger":ledger,"three_level_time_groups":time_groups,"matched_spatial_diagnostics":spatial,"restart":restart,"outlet_unit_benchmarks":events,
        "execution_integrity":{"failure_markers":failure_markers,"nonempty_stderr":nonempty_stderr,"frozen_order_and_all_observed_bindings_verified":True},
        "total_integrator_runtime_s":sum(row.get("runtime_s",0) for row in ledger),
        "run_wall_seconds":root_completion["wall_seconds"] if root_completion else None,
        "population_release_measured":False,"full_trajectory_cost_estimated":False,"campaign_authorized":False,
        "claim_boundary":design["research_contract"]["claim_boundary"],
        "bindings":{"design_path":str(api.DESIGN),"design_sha256":api.sha(api.DESIGN),"run_path":str(run),
                    "completion_sha256":api.sha(run/"completion.json") if root_completion else None,"evaluator_sha256":api.sha(__file__)}}
    api.verify_design(design)
    output.mkdir(parents=True)
    api.write(output/"results.json",result)
    api.write(output/"completion.json",{"passed":short_time_passed,"status":status,"results_sha256":api.sha(output/"results.json")})
    print({k:result[k] for k in ["status","run_complete","all_short_runs_healthy_and_complete","total_integrator_runtime_s"]})
    print("time groups passed",sum(g["passed"] for g in time_groups),"of",len(time_groups),"restart",restart,"spatial",spatial)
    return 0 if short_time_passed else 4


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    raise SystemExit(main(a.run.resolve(),a.output.resolve()))
