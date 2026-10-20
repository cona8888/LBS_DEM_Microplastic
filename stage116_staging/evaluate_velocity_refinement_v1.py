"""Apply the original acceptance gates to one additional, declared triplet."""
import refine_short_velocity_v1 as job
import evaluate_corrected_diagnostics_v1 as reference
api=job.api


def main():
    d=api.read(job.DESIGN);job.verify(d)
    output=job.ROOT/"stage116_evaluations/fibre_cost_attribution_20260915/refinement_evaluation_01"
    api.require(not output.exists(),"immutable evaluation exists")
    done=api.read(job.RUN/"completion.json")
    api.require(done["design_sha256"]==api.sha(job.DESIGN),"run/design drift")
    api.require(not list(job.RUN.rglob("failure.json")) and not any(p.stat().st_size for p in job.RUN.glob("*.stderr.txt")),"run failure/stderr")
    previous=api.read(job.PREVIOUS);threshold=d["acceptance"];groups=[];ledger=[];new_records={}
    for c in d["cases"]:
        spec=c["spec"];name=spec["case_id"];path=job.RUN/name/"record.json";r=api.read(path)
        api.require(api.sha(path)==done["records"][name]==api.read(path.parent/"completion.json")["record_sha256"],"record drift")
        api.require(r["design_sha256"]==api.sha(job.DESIGN) and r["case_id"]==name,"record metadata drift")
        health=reference.independent_health(r["result"],spec)
        new_records[name]=r
        ledger.append({"case_id":name,"health":health,"status":r["result"]["status"],"time_s":r["result"]["time_s"],"runtime_s":r["result"]["runtime_seconds"]})
        old_group=next(g for g in previous["three_level_time_groups"] if g["case_ids"][-1]==c["parent_case_id"])
        quarter=api.read(job.parent.RUN/c["parent_case_id"]/"record.json")
        item={"case_id":name,"seed":spec["seed"],"cpd":spec["cpd"],"flow_factor":spec["flow_factor"],"shape":spec["shape"],"triplet":c["triplet"],"coarse_medium":old_group["medium_fine"]}
        if r["result"]["status"]!="present_at_horizon":item.update(passed=False,reason="eighth-step observation incomplete")
        else:
            cm=old_group["medium_fine"];mf=reference.difference(quarter,r,spec)
            def trend(key,budget):return mf[key]<=threshold["refinement_trend_multiplier_max"]*cm[key]+threshold["trend_roundoff_floor"] or max(cm[key],mf[key])<=threshold["trend_waiver_fraction_of_budget"]*budget
            checks={"position_error":mf["position_difference_over_b"]<=threshold["fine_medium_position_over_b_max"],
                "axis_error":mf["apolar_axis_angle_rad"]<=threshold["fine_medium_axis_angle_rad_max"],
                "velocity_error":mf["translational_velocity_relative_difference"]<=threshold["fine_medium_translational_velocity_relative_max"],
                "position_refinement_trend":trend("position_difference_over_b",threshold["fine_medium_position_over_b_max"]),
                "axis_refinement_trend":trend("apolar_axis_angle_rad",threshold["fine_medium_axis_angle_rad_max"]),
                "matched_query":mf["time_difference_s"]<=threshold["exit_time_difference_s_max"],"health":health["passed"]}
            item.update(medium_fine=mf,checks=checks,passed=all(checks.values()))
        groups.append(item)
    n2,n4=[api.case_id(2,1.,cpd,"rigid_prolate_ar4",.125) for cpd in [2,4]]
    spatial={"matched_horizon":False}
    if new_records[n2]["result"]["status"]==new_records[n4]["result"]["status"]=="present_at_horizon":
        spec=next(c["spec"] for c in d["cases"] if c["spec"]["case_id"]==n2)
        spatial={"matched_horizon":True,**reference.difference(new_records[n2],new_records[n4],spec),
                 "limitation":"Each directly solved field retains its own achieved speed; short matched-nominal-flow sensitivity, not a pure equal-speed discretization error."}
    passing_previous=sum(g["passed"] for g in previous["three_level_time_groups"])
    passed=all(g["passed"] for g in groups) and passing_previous==8
    result={"passed":passed,"groups":groups,"ledger":ledger,"passing_inherited_groups":passing_previous,
        "passing_latest_triplets":passing_previous+sum(g["passed"] for g in groups),"fibre_spatial_eighth_step":spatial,
        "total_new_integrator_runtime_s":sum(r["runtime_s"] for r in ledger),"run_wall_s":done["wall_s"],
        "status":"short_time_response_verified_full_trajectory_feasibility_open" if passed else "additional_refinement_failed_or_incomplete_stop_preserved",
        "scope":"Declared adaptive numerical refinement, not independent model validation; original failed triplets remain failed. No full-horizon or release inference.",
        "bindings":{"design_sha256":api.sha(job.DESIGN),"run_completion_sha256":api.sha(job.RUN/"completion.json"),"prior_evaluation_sha256":api.sha(job.PREVIOUS),"evaluator_sha256":api.sha(__file__)}}
    job.verify(d);output.mkdir(parents=True);api.write(output/"results.json",result)
    api.write(output/"completion.json",{"passed":passed,"results_sha256":api.sha(output/"results.json")})
    print(result["status"],"passing latest triplets",result["passing_latest_triplets"],"/12")
    for g in groups:print(g)
    print("spatial",spatial)
    return 0 if passed else 4


if __name__=="__main__":raise SystemExit(main())
