"""Verify Stage53 on both independently preserved difficult contact states."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage40_staging"),str(ROOT/"stage41_staging"),str(ROOT/"stage53_staging")]
import matrix_case_v1,geometry_exact_v1
import trajectory_multistart_lm_v1 as trajectory
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    out=ROOT/"stage53_evaluations"/"saved_states_probe_01"; out.mkdir(parents=True,exist_ok=False)
    field,old,L,spacing,inputs=matrix_case_v1.load(2); geometry=geometry_exact_v1.GrainGeometry.from_geometry(old)
    specs=[
        ("original_three_contact",ROOT/"stage43_runs"/"release_pilot_20260912"/"pilot_01"/"coarse.json",.002,.1,.5),
        ("terminal_three_contact",ROOT/"stage50_runs"/"release_pilot_20260912"/"medium_01"/"results.json",None,.05,.25)]
    rows=[]
    for name,path,horizon,disp,relax in specs:
        data=json.loads(path.read_text()); saved=data["result"]
        if horizon is None: horizon=data["horizon_s"]-saved["time_s"]
        result=trajectory.integrate(field,geometry,saved["position_m"],saved["orientation"],saved["velocity_generalized"],
            2e-4,5e-5,.001002,1380,998.2,[0,0,-9.80665],.3,L,horizon,added_mass_fraction=1,cutoff_ratio=.2,
            roughness_ratio=.01,displacement_fraction=disp,relaxation_fraction=relax,max_dt=.01,wall_budget=300,
            trap_reference_speed=1e-4,trap_dwell_time=.5,stop_on_trap=False,reynolds_limit=3.)
        rows.append({"name":name,"source":str(path),"source_sha256":sha(path),"requested_horizon_s":horizon,"result":result})
    checks={"both_advanced":all(x["result"]["time_s"]>0 for x in rows),"both_complete":all(x["result"]["status"]=="present_at_horizon" for x in rows),
        "no_multistart_failure":all(x["result"]["multistart_lm_stats"]["zero_lm_failures"]==0 for x in rows),
        "original_primary_lm_used":rows[0]["result"]["multistart_lm_stats"]["primary_solves"]>0,
        "terminal_zero_lm_used":rows[1]["result"]["multistart_lm_stats"]["zero_lm_solves"]>0,
        "clearance":all(x["result"]["minimum_gap_m"]>=-5e-10 for x in rows),
        "closure":all(x["result"]["max_contact_residual"]<=1e-8 and x["result"]["max_force_residual"]<=1e-8 and x["result"]["max_momentum_residual"]<=1e-8 for x in rows),
        "reynolds":all(x["result"]["max_reynolds"]<=3 for x in rows)}
    record={"passed":bool(all(checks.values())),"checks":checks,"rows":rows,"input_hashes":{str(p.resolve()):sha(p) for p in inputs},
        "source_hashes":{str(Path(__file__).resolve()):sha(__file__),str(Path(trajectory.__file__).resolve()):sha(trajectory.__file__)},
        "scope":"two saved difficult-state algorithm verification; no release claim"}
    path=out/"results.json"; path.write_text(json.dumps(record,indent=2)); (out/"completion.json").write_text(json.dumps(
        {"status":"complete_passed" if record["passed"] else "complete_failed","results_sha256":sha(path)},indent=2))
    print(json.dumps({"passed":record["passed"],"checks":checks,"rows":[{"name":x["name"],"status":x["result"]["status"],
        "time_s":x["result"]["time_s"],"steps":x["result"]["steps"],"stats":x["result"]["multistart_lm_stats"]} for x in rows]},indent=2))
    if not record["passed"]: raise SystemExit(1)
if __name__=="__main__": main()
