"""Run the medium branch of the frozen 0.1-PV pilot with Stage50."""
import hashlib,json,platform,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage40_staging"),str(ROOT/"stage41_staging"),str(ROOT/"stage50_staging")]
import matrix_case_v1,geometry_exact_v1
import trajectory_seeded_lm_v1 as trajectory
DESIGN=ROOT/"stage43_designs"/"release_pilot_v1.json"
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sources():
    paths={Path(__file__).resolve()}
    for module in list(sys.modules.values()):
        p=getattr(module,"__file__",None)
        if p and Path(p).suffix==".py" and Path(p).resolve().is_relative_to(ROOT): paths.add(Path(p).resolve())
    return {str(p):sha(p) for p in sorted(paths)}
def main():
    out=ROOT/"stage50_runs"/"release_pilot_20260912"/"medium_01"; out.mkdir(parents=True,exist_ok=False)
    cfg=json.loads(DESIGN.read_text()); level=next(x for x in cfg["levels"] if x["name"]=="medium"); before=sources()
    field,old,L,dx,inputs=matrix_case_v1.load(cfg["packing_seed"]); geometry=geometry_exact_v1.GrainGeometry.from_geometry(old)
    start_path=ROOT/cfg["start_source"]; start=next(x for x in json.loads(start_path.read_text()) if x["id"]==cfg["start_id"])
    a,b,_=cfg["shape"]["semiaxes_m"]; horizon=cfg["horizon_pore_volumes"]*L/cfg["target_mean_interstitial_velocity_m_s"]
    begun=time.perf_counter(); result=trajectory.integrate(field,geometry,start["position_m"],start["orientation"],np.zeros(6),a,b,
        cfg["dynamic_viscosity_Pa_s"],cfg["particle_density_kg_m3"],cfg["fluid_density_kg_m3"],cfg["gravity_m_s2"],
        cfg["friction_coefficient"],L,horizon,added_mass_fraction=cfg["added_mass_fraction"],cutoff_ratio=.2,roughness_ratio=.01,
        displacement_fraction=level["displacement_fraction"],relaxation_fraction=level["relaxation_fraction"],
        angle_limit=cfg["fixed_numerics"]["angle_limit_rad"],max_dt=cfg["fixed_numerics"]["max_dt_s"],
        wall_budget=cfg["fixed_numerics"]["wall_budget_s_per_case"],trap_reference_speed=cfg["target_mean_interstitial_velocity_m_s"],
        trap_dwell_time=cfg["trap_dwell_time_s"],trap_speed_ratio=cfg["trap_speed_ratio"],
        trap_drift_over_minor_radius=cfg["trap_drift_over_minor_radius"],stop_on_trap=False,reynolds_limit=cfg["fixed_numerics"]["reynolds_limit"])
    after=sources(); gap=result["minimum_gap_m"]; stats=result["seeded_lm_stats"]
    checks={"completed_without_failure_or_budget":bool(result["status"] not in {"numerical_failure","incomplete_budget","unresolved_model","unresolved_field"}),
        "clearance":bool(gap is not None and gap>=-5e-10),"contact_closure":bool(result["max_contact_residual"]<=1e-8),
        "force_closure":bool(result["max_force_residual"]<=1e-8),"momentum_closure":bool(result["max_momentum_residual"]<=1e-8),
        "reynolds":bool(result["max_reynolds"]<=3),"no_lm_failure":bool(stats["lm_failures"]==0),"sources_stable":before==after}
    record={"completed":True,"passed":bool(all(checks.values())),"checks":checks,"level":level,"result":result,"horizon_s":horizon,
        "runtime_seconds":time.perf_counter()-begun,"source_hashes":after,"source_hashes_at_start":before,
        "input_hashes":{str(p.resolve()):sha(p) for p in (*inputs,DESIGN,start_path)},"environment":{"python":platform.python_version(),"numpy":np.__version__},
        "claim_boundary":"single-start medium numerical pilot; no release fraction or validation claim"}
    path=out/"results.json"; path.write_text(json.dumps(record,indent=2)); (out/"completion.json").write_text(json.dumps(
        {"status":"complete_passed" if record["passed"] else "complete_failed","results_sha256":sha(path)},indent=2))
    print(json.dumps({"passed":record["passed"],"checks":checks,"status":result["status"],"reason":result["reason"],
        "time_s":result["time_s"],"steps":result["steps"],"persistent_contact_observed":result["persistent_contact_observed"],
        "stats":stats,"runtime_seconds":result["runtime_seconds"]},indent=2))
    if not record["passed"]: raise SystemExit(1)
if __name__=="__main__": main()
