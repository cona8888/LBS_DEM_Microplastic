"""Verify Stage50 is identical to accepted Stage42 when LM is not needed."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage40_staging"),str(ROOT/"stage41_staging"),str(ROOT/"stage50_staging")]
import matrix_case_v1,geometry_exact_v1
import trajectory_seeded_lm_v1 as trajectory
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def angle(a,b):
    a,b=np.asarray(a),np.asarray(b); return float(np.arctan2(np.linalg.norm(np.cross(a,b)),np.dot(a,b)))
def main():
    out=ROOT/"stage50_evaluations"/"matrix_refinement_01"; out.mkdir(parents=True,exist_ok=False)
    field,old,L,dx,inputs=matrix_case_v1.load(2); geometry=geometry_exact_v1.GrainGeometry.from_geometry(old)
    start_path=ROOT/"stage39_evaluations"/"matrix_profile_01"/"results.json"; start=json.loads(start_path.read_text())["result"]
    accepted_path=ROOT/"stage42_evaluations"/"robust_matrix_refinement_01"/"results.json"; accepted=json.loads(accepted_path.read_text())
    prior_path=ROOT/"stage41_evaluations"/"matrix_replay_refinement_02"/"results.json"; prior=json.loads(prior_path.read_text())
    fine=next(row["pair"]["candidate"] for row in prior["values"]["rows"] if row["friction"]==.3 and row["fraction"]==.00625)
    result=trajectory.integrate(field,geometry,start["position_m"],start["orientation"],start["velocity_generalized"],
        2e-4,5e-5,.001002,1380,998.2,[0,0,-9.80665],.3,L,.02,added_mass_fraction=1,cutoff_ratio=.2,
        roughness_ratio=.01,displacement_fraction=.00625,relaxation_fraction=.015625,max_dt=.01,wall_budget=480,
        trap_reference_speed=1e-4,trap_dwell_time=.5)
    reference=accepted["result"]; shift=float(np.linalg.norm(np.asarray(fine["position_m"])-np.asarray(result["position_m"]))/5e-5)
    rotation=angle(fine["orientation"],result["orientation"]); stats=result["seeded_lm_stats"]
    exact=(result["status"]==reference["status"] and result["steps"]==reference["steps"] and result["position_m"]==reference["position_m"]
        and result["orientation"]==reference["orientation"] and result["velocity_generalized"]==reference["velocity_generalized"]
        and result["minimum_gap_m"]==reference["minimum_gap_m"] and result["total_contact_iterations"]==reference["total_contact_iterations"])
    checks={"completed":bool(result["status"]=="present_at_horizon"),"health":bool(result["minimum_gap_m"]>=-5e-10 and result["max_contact_residual"]<=1e-8 and result["max_force_residual"]<=1e-8 and result["max_momentum_residual"]<=1e-8 and result["max_reynolds"]<=3),
        "fine_extra_fine_position":bool(shift<=.01),"fine_extra_fine_orientation":bool(rotation<=1e-3),
        "exact_stage42_match":bool(exact),"fallback_not_invoked":bool(stats["lm_solves"]==0 and stats["lm_failures"]==0)}
    record={"passed":bool(all(checks.values())),"checks":checks,"shift_minor_radii":shift,"orientation_shift_rad":rotation,
        "result":result,"input_hashes":{str(p.resolve()):sha(p) for p in (*inputs,start_path,accepted_path,prior_path)},
        "source_hashes":{str(Path(__file__).resolve()):sha(__file__),str(Path(trajectory.__file__).resolve()):sha(trajectory.__file__)},
        "scope":"extra-fine numerical equivalence and convergence; no release claim"}
    path=out/"results.json"; path.write_text(json.dumps(record,indent=2)); (out/"completion.json").write_text(json.dumps(
        {"status":"complete_passed" if record["passed"] else "complete_failed","results_sha256":sha(path)},indent=2))
    print(json.dumps({"passed":record["passed"],"checks":checks,"shift_minor_radii":shift,"orientation_shift_rad":rotation,
        "stats":stats,"runtime_seconds":result["runtime_seconds"]},indent=2))
    if not record["passed"]: raise SystemExit(1)
if __name__=="__main__": main()
