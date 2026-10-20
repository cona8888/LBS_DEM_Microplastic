"""Evaluate categorical completion when a failure occurs only in a bounded terminal remainder.

Raw trajectory status is never changed.  A derived categorical status is
permitted only when the remaining time is <=1e-6 of the horizon and conservative
local translation/rotation bounds lie below frozen geometry/angle tolerances.
"""
import hashlib,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage37_staging"),str(ROOT/"stage40_staging"),str(ROOT/"stage42_staging")]
import transport_contact as mechanics
import matrix_case_v1
import inertial_contact_robust_v1 as inertial
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    out=ROOT/"stage51_evaluations"/"bounded_terminal_remainder_01"; out.mkdir(parents=True,exist_ok=False)
    coarse_path=ROOT/"stage50_runs"/"release_pilot_20260912"/"coarse_01"/"results.json"
    medium_path=ROOT/"stage50_runs"/"release_pilot_20260912"/"medium_01"/"results.json"
    coarse=json.loads(coarse_path.read_text()); medium=json.loads(medium_path.read_text()); r=medium["result"]
    field,geometry,L,spacing,inputs=matrix_case_v1.load(2); x=np.asarray(r["position_m"]); p=np.asarray(r["orientation"]); q=np.asarray(r["velocity_generalized"])
    a,b,viscosity,rhop,rhof=2e-4,5e-5,.001002,1380.,998.2; remainder=medium["horizon_s"]-r["time_s"]
    fluid,gradient=field.sample(x); background,_=mechanics.free_motion(p,gradient,fluid,a,b,viscosity,1.,1.,[0,0,0])
    resistance=inertial.stokes_generalized_resistance(p,a,b,viscosity); volume=4*np.pi*a*b*b/3
    body=(rhop-rhof)*volume*np.array([0,0,-9.80665]); terminal=np.linalg.norm(body)/np.linalg.eigvalsh(resistance[:3,:3]).min()
    translation_scale=max(np.linalg.norm(q[:3]),np.linalg.norm(background[:3]),terminal)
    rotation_scale=max(np.linalg.norm(q[3:]),np.linalg.norm(background[3:]))/a
    displacement_bound=translation_scale*remainder; angle_bound=rotation_scale*remainder
    checks={"coarse_raw_passed":bool(coarse["passed"]),"medium_only_terminal_contact_failure":bool(
        r["status"]=="numerical_failure" and r["reason"]=="direct contact residual nonconvergence"),
        "relative_remainder_le_1e_6":bool(remainder/medium["horizon_s"]<=1e-6),
        "translation_bound_within_geometry_tolerance":bool(displacement_bound<=5e-10),
        "rotation_bound_within_1e_5_rad":bool(angle_bound<=1e-5),
        "medium_prior_health_passed":bool(all(medium["checks"][k] for k in
            ("clearance","contact_closure","force_closure","momentum_closure","reynolds","sources_stable"))),
        "persistent_dwell_agrees":bool(coarse["result"]["persistent_contact_observed"]==r["persistent_contact_observed"]==True)}
    record={"passed":bool(all(checks.values())),"checks":checks,"raw_statuses":{
        "coarse":coarse["result"]["status"],"medium":r["status"]},"derived_categorical_statuses":{
        "coarse":"present_at_horizon","medium":"present_at_horizon_with_bounded_terminal_remainder"},
        "horizon_s":medium["horizon_s"],"medium_simulated_time_s":r["time_s"],"remainder_s":remainder,
        "relative_remainder":remainder/medium["horizon_s"],"translation_scale_m_s":translation_scale,
        "translation_bound_m":displacement_bound,"rotation_scale_rad_s":rotation_scale,"rotation_bound_rad":angle_bound,
        "input_hashes":{str(p.resolve()):sha(p) for p in (*inputs,coarse_path,medium_path)},
        "source_hashes":{str(Path(__file__).resolve()):sha(__file__)},
        "scope":"categorical pilot completion bound only; raw failure preserved; no release fraction or validation claim"}
    path=out/"results.json"; path.write_text(json.dumps(record,indent=2)); (out/"completion.json").write_text(json.dumps(
        {"status":"complete_passed" if record["passed"] else "complete_failed","results_sha256":sha(path)},indent=2))
    print(json.dumps({"passed":record["passed"],"checks":checks,"remainder_s":remainder,
        "relative_remainder":record["relative_remainder"],"translation_bound_m":displacement_bound,
        "rotation_bound_rad":angle_bound,"derived":record["derived_categorical_statuses"]},indent=2))
    if not record["passed"]: raise SystemExit(1)
if __name__=="__main__": main()
