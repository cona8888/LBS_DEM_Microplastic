"""Recheck inherited short-time gates with explicit original/new evidence roles."""
import complete_short_matrix_v1 as job
import evaluate_corrected_diagnostics_v1 as original_evaluator
api=job.api


def expected_contract(spec,binding):
    c=spec["config"];n=c["numerics"];t=c["trap"];a,b,_=c["prolate_semiaxes_m"]
    return api.digest([binding,a,b,c["dynamic_viscosity_Pa_s"],c["particle_density_kg_m3"],c["fluid_density_kg_m3"],list(c["gravity_m_s2"]),
        c["friction_coefficient"],spec["field_metadata"]["cell_length_m"],spec["horizon_s"],c["added_mass_fraction"],.2,.01,
        n["displacement_fraction"],n["angle_limit_rad"],n["relaxation_fraction"],n["max_dt_s"],c["target_mean_interstitial_velocity_m_s"],
        t["dwell_time_s"],t["speed_ratio"],t["drift_over_minor_radius"],t["absorbing"],n["reynolds_limit"]])


def main():
    d=api.read(job.DESIGN);job.verify(d)
    output=job.ROOT/"stage116_evaluations/fibre_cost_attribution_20260915/short_matrix_evaluation_01"
    api.require(not output.exists(),"immutable evaluation exists")
    complete=api.read(job.RUN/"completion.json")
    api.require(complete["design_sha256"]==api.sha(job.DESIGN),"completion design drift")
    api.require(not list(job.RUN.rglob("failure.json")) and not any(p.stat().st_size for p in job.RUN.glob("*.stderr.txt")),"run failure or stderr")
    old=api.read(api.DESIGN);specs={s["case_id"]:s for s in old["cases"]};records={};ledger=[];prefix_checks=[]
    for name,entry in d["reused_completed_records"].items():records[name]=api.read(entry["path"])
    for c in d["cases"]:
        name=c["case_id"];path=job.RUN/name;record=api.read(path/"record.json");completion=api.read(path/"completion.json")
        api.require(complete["records"][name]==completion["record_sha256"]==api.sha(path/"record.json"),"new record drift")
        api.require(completion["prefix_sha256"]==api.sha(path/"prefix_result.json"),"prefix artifact drift")
        api.require(record["design_sha256"]==api.sha(job.DESIGN) and record["prior_record_sha256"]==c["prior_sha256"],"record binding drift")
        prefix=api.read(path/"prefix_result.json");prior=api.read(c["prior_path"])
        cp=prefix.get("checkpoint")
        exact=cp is not None and cp["state_sha256"]==prior["result"]["checkpoint"]["state_sha256"] and cp["state"]==prior["result"]["checkpoint"]["state"]
        contract=expected_contract(specs[name],api.digest([d["binding"],name]))
        api.require(cp is not None and cp["state_sha256"]==api.digest(cp["state"]) and cp["contract"]==contract,"new checkpoint contract/integrity drift")
        api.require(exact==record["prefix_exact"],"prefix equivalence flag drift")
        prefix_checks.append({"case_id":name,"exact_original_prefix":exact,"new_version_contract_verified":True})
        records[name]=record
    for name,spec in specs.items():
        r=records[name];state=r["result"];health=original_evaluator.independent_health(state,spec)
        is_new=name not in d["reused_completed_records"]
        ledger.append({"case_id":name,"source":"optimized_new_run" if is_new else "hash_bound_Stage115_complete",
            "status":state["status"],"health":health,"time_s":state["time_s"],"qualified":health["passed"] and state["status"]=="present_at_horizon",
            "runtime_s":r["total_integrator_runtime_s"] if is_new else state["runtime_seconds"],
            "steps":state["steps"],"rejected_steps":state["rejected"],"contact_steps":state["contact_steps"],"max_particle_Re":state["max_reynolds"]})
    threshold=old["acceptance"];groups=[]
    for seed,factor,cpd in api.FLOW_COMBINATIONS:
        for shape in api.SHAPES:
            names=[api.case_id(seed,factor,cpd,shape,r) for r in api.REFINEMENTS]
            row={"seed":seed,"flow_factor":factor,"cpd":cpd,"shape":shape,"case_ids":names}
            if not all(records[n]["result"]["status"]=="present_at_horizon" for n in names):
                row.update(passed=False,reason="incomplete matched query")
            else:
                cm=original_evaluator.difference(records[names[0]],records[names[1]],specs[names[0]])
                mf=original_evaluator.difference(records[names[1]],records[names[2]],specs[names[0]])
                def trend(key,budget):return mf[key]<=threshold["refinement_trend_multiplier_max"]*cm[key]+threshold["trend_roundoff_floor"] or max(cm[key],mf[key])<=threshold["trend_waiver_fraction_of_budget"]*budget
                checks={"position_error":mf["position_difference_over_b"]<=threshold["fine_medium_position_over_b_max"],
                    "axis_error":mf["apolar_axis_angle_rad"]<=threshold["fine_medium_axis_angle_rad_max"],
                    "velocity_error":mf["translational_velocity_relative_difference"]<=threshold["fine_medium_translational_velocity_relative_max"],
                    "position_refinement_trend":trend("position_difference_over_b",threshold["fine_medium_position_over_b_max"]),
                    "axis_refinement_trend":trend("apolar_axis_angle_rad",threshold["fine_medium_axis_angle_rad_max"]),
                    "matched_query":mf["time_difference_s"]<=threshold["exit_time_difference_s_max"]}
                row.update(coarse_medium=cm,medium_fine=mf,checks=checks,passed=all(checks.values()))
            groups.append(row)
    spatial=[]
    for shape in api.SHAPES:
        n2,n4=[api.case_id(2,1.,cpd,shape,.25) for cpd in [2,4]]
        row={"shape":shape}
        if records[n2]["result"]["status"]==records[n4]["result"]["status"]=="present_at_horizon":
            row.update(matched_horizon=True,**original_evaluator.difference(records[n2],records[n4],specs[n2]))
        else:row.update(matched_horizon=False)
        spatial.append(row)
    passed=all(r["qualified"] for r in ledger) and all(g["passed"] for g in groups) and all(p["exact_original_prefix"] for p in prefix_checks)
    result={"passed":passed,"status":"short_time_response_verified_longer_feasibility_open" if passed else "short_time_response_failed_or_incomplete_preserved",
        "ledger":ledger,"prefix_equivalence":prefix_checks,"three_level_time_groups":groups,"spatial_diagnostics":spatial,
        "reused_count":28,"new_attempt_count":8,"new_integrator_runtime_s":sum(r["runtime_s"] for r in ledger if r["source"]=="optimized_new_run"),
        "run_wall_s":complete["wall_s"],"acceptance_thresholds":threshold,
        "claim_boundary":"Fixed 0.25-s numerical query only. Spatial numbers retain each field's achieved speed. No full-horizon cost, shape/flow ranking, release fraction, or experimental validation is established.",
        "bindings":{"design_sha256":api.sha(job.DESIGN),"completion_sha256":api.sha(job.RUN/"completion.json"),"evaluator_sha256":api.sha(__file__),"inherited_evaluator_sha256":api.sha(original_evaluator.__file__)}}
    job.verify(d);output.mkdir(parents=True);api.write(output/"results.json",result)
    api.write(output/"completion.json",{"passed":passed,"results_sha256":api.sha(output/"results.json")})
    print(result["status"],"complete",sum(r["qualified"] for r in ledger),"/36; time groups",sum(g["passed"] for g in groups),"/12")
    for g in groups:
        if not g["passed"]:print(g)
    print("spatial",spatial,"new runtime",result["new_integrator_runtime_s"])
    return 0 if passed else 4


if __name__=="__main__":raise SystemExit(main())
