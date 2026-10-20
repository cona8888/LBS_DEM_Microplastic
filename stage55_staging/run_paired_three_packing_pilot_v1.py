"""Run the frozen Stage55 six-case paired morphology pilot sequentially."""
import hashlib,json,platform,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage40_staging"),str(ROOT/"stage41_staging"),str(ROOT/"stage53_staging")]
import matrix_case_v1,geometry_exact_v1
import trajectory_multistart_lm_v1 as trajectory
DESIGN=ROOT/"stage55_designs"/"paired_three_packing_pilot_v1.json"
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sources():
    paths={Path(__file__).resolve()}
    for module in list(sys.modules.values()):
        p=getattr(module,"__file__",None)
        if p and Path(p).suffix==".py" and Path(p).resolve().is_relative_to(ROOT): paths.add(Path(p).resolve())
    return {str(p):sha(p) for p in sorted(paths)}
def main():
    out=ROOT/"stage55_runs"/"paired_three_packing_pilot_20260912"/"pilot_01"; out.mkdir(parents=True,exist_ok=False)
    cfg=json.loads(DESIGN.read_text()); before=sources(); rows=[]; input_hashes={str(DESIGN.resolve()):sha(DESIGN)}; begun=time.perf_counter()
    a,b,_=cfg["prolate_semiaxes_m"]; sphere=(a*b*b)**(1/3)
    for item in cfg["packings"]:
        seed=item["seed"]; field,old,L,dx,inputs=matrix_case_v1.load(seed); geometry=geometry_exact_v1.GrainGeometry.from_geometry(old)
        starts_path=ROOT/f"stage37_runs/stage4_farfield_bound_20260912/pilot_01/starts_s{seed}.json"
        start=next(x for x in json.loads(starts_path.read_text()) if x["id"]==item["start_id"])
        for p in (*inputs,starts_path): input_hashes[str(p.resolve())]=sha(p)
        for shape,aa,bb in (("equal_volume_sphere",sphere,sphere),("prolate_ar4",a,b)):
            horizon=cfg["horizon_pore_volumes"]*L/cfg["target_mean_interstitial_velocity_m_s"]
            result=trajectory.integrate(field,geometry,start["position_m"],start["orientation"],np.zeros(6),aa,bb,
                cfg["dynamic_viscosity_Pa_s"],cfg["particle_density_kg_m3"],cfg["fluid_density_kg_m3"],cfg["gravity_m_s2"],
                cfg["friction_coefficient"],L,horizon,added_mass_fraction=cfg["added_mass_fraction"],cutoff_ratio=.2,roughness_ratio=.01,
                displacement_fraction=cfg["numerics"]["displacement_fraction"],relaxation_fraction=cfg["numerics"]["relaxation_fraction"],
                angle_limit=cfg["numerics"]["angle_limit_rad"],max_dt=cfg["numerics"]["max_dt_s"],wall_budget=cfg["numerics"]["wall_budget_s_per_case"],
                trap_reference_speed=cfg["target_mean_interstitial_velocity_m_s"],trap_dwell_time=cfg["trap"]["dwell_time_s"],
                trap_speed_ratio=cfg["trap"]["speed_ratio"],trap_drift_over_minor_radius=cfg["trap"]["drift_over_minor_radius"],
                stop_on_trap=cfg["trap"]["absorbing"],reynolds_limit=cfg["numerics"]["reynolds_limit"])
            row={"packing_seed":seed,"start_id":start["id"],"initial_clearance_ratio":start["initial_minimum_clearance_ratio"],
                "shape":shape,"horizon_s":horizon,"result":result}; rows.append(row)
            case=out/f"s{seed}_{shape}.json"; case.write_text(json.dumps(row,indent=2))
            print(json.dumps({"case":case.stem,"status":result["status"],"time_s":result["time_s"],"steps":result["steps"],
                "persistent_contact_observed":result["persistent_contact_observed"],"lm":result["multistart_lm_stats"],
                "runtime_seconds":result["runtime_seconds"]}),flush=True)
    after=sources(); input_hashes.update({str(Path(p)):h for p,h in after.items()})
    checks={"all_six_accounted":len(rows)==6,"no_failure_or_budget_censoring":all(r["result"]["status"] not in
        {"numerical_failure","incomplete_budget","unresolved_model","unresolved_field"} for r in rows),
        "clearance":all(r["result"]["minimum_gap_m"]>=-5e-10 for r in rows),
        "closure":all(r["result"]["max_contact_residual"]<=1e-8 and r["result"]["max_force_residual"]<=1e-8 and r["result"]["max_momentum_residual"]<=1e-8 for r in rows),
        "reynolds":all(r["result"]["max_reynolds"]<=3 for r in rows),
        "no_direct_fallback_failure":all(r["result"]["multistart_lm_stats"]["zero_lm_failures"]==0 for r in rows),
        "sources_stable":before==after}
    record={"completed":True,"passed":bool(all(checks.values())),"checks":checks,"rows":rows,"runtime_seconds":time.perf_counter()-begun,
        "source_hashes":after,"source_hashes_at_start":before,"input_hashes":input_hashes,
        "environment":{"python":platform.python_version(),"numpy":np.__version__},"claim_boundary":cfg["claim_boundary"]}
    path=out/"results.json"; path.write_text(json.dumps(record,indent=2)); (out/"completion.json").write_text(json.dumps(
        {"status":"complete_passed" if record["passed"] else "complete_failed","results_sha256":sha(path)},indent=2))
    print(json.dumps({"passed":record["passed"],"checks":checks,"runtime_seconds":record["runtime_seconds"]},indent=2))
    if not record["passed"]: raise SystemExit(1)
if __name__=="__main__": main()
