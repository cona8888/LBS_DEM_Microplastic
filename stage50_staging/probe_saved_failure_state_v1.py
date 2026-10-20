"""Probe Stage50 at the exact Stage43 pre-failure state."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage40_staging"),str(ROOT/"stage41_staging"),str(ROOT/"stage50_staging")]
import matrix_case_v1,geometry_exact_v1
import trajectory_seeded_lm_v1 as trajectory
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    out=ROOT/"stage50_evaluations"/"saved_failure_state_probe_01"; out.mkdir(parents=True,exist_ok=False)
    source=ROOT/"stage43_runs"/"release_pilot_20260912"/"pilot_01"/"coarse.json"; saved=json.loads(source.read_text())["result"]
    field,old,length,spacing,inputs=matrix_case_v1.load(2); geometry=geometry_exact_v1.GrainGeometry.from_geometry(old)
    result=trajectory.integrate(field,geometry,saved["position_m"],saved["orientation"],saved["velocity_generalized"],2e-4,5e-5,
        .001002,1380,998.2,[0,0,-9.80665],.3,length,.002,added_mass_fraction=1,cutoff_ratio=.2,roughness_ratio=.01,
        displacement_fraction=.1,relaxation_fraction=.5,max_dt=.01,wall_budget=300,trap_reference_speed=1e-4,
        trap_dwell_time=.5,stop_on_trap=False,reynolds_limit=3.)
    gap=result["minimum_gap_m"]; stats=result["seeded_lm_stats"]
    checks={"advanced":bool(result["time_s"]>0),"no_failure":bool(result["status"]!="numerical_failure"),
        "seeded_lm_used":bool(stats["lm_solves"]>0),"seeded_lm_did_not_fail":bool(stats["lm_failures"]==0),
        "clearance":bool(gap is not None and gap>=-5e-10),"closure":bool(result["max_contact_residual"]<=1e-8 and result["max_force_residual"]<=1e-8 and result["max_momentum_residual"]<=1e-8),
        "reynolds":bool(result["max_reynolds"]<=3)}
    record={"passed":bool(all(checks.values())),"checks":checks,"result":result,
        "input_hashes":{str(p.resolve()):sha(p) for p in (*inputs,source)},"source_hashes":{
            str(Path(__file__).resolve()):sha(__file__),str(Path(trajectory.__file__).resolve()):sha(trajectory.__file__)},
        "scope":"exact saved-state seeded-LM fallback probe; no release claim"}
    path=out/"results.json"; path.write_text(json.dumps(record,indent=2)); (out/"completion.json").write_text(json.dumps(
        {"status":"complete_passed" if record["passed"] else "complete_failed","results_sha256":sha(path)},indent=2))
    print(json.dumps({"passed":record["passed"],"checks":checks,"status":result["status"],"reason":result["reason"],
        "time_s":result["time_s"],"steps":result["steps"],"stats":stats,"runtime_seconds":result["runtime_seconds"]},indent=2))
    if not record["passed"]: raise SystemExit(1)
if __name__=="__main__": main()
