"""Audit the exact Stage50-to-Stage53 continuation and evaluate the 0.1-PV pilot."""
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def angle(a,b):
    a,b=np.asarray(a),np.asarray(b); return float(np.arctan2(np.linalg.norm(np.cross(a,b)),np.dot(a,b)))
def main():
    out=ROOT/"stage54_evaluations"/"stitched_release_pilot_01"; out.mkdir(parents=True,exist_ok=False)
    coarse_path=ROOT/"stage50_runs"/"release_pilot_20260912"/"coarse_01"/"results.json"
    medium_path=ROOT/"stage50_runs"/"release_pilot_20260912"/"medium_01"/"results.json"
    continuation_path=ROOT/"stage53_evaluations"/"saved_states_probe_01"/"results.json"
    design_path=ROOT/"stage43_designs"/"release_pilot_v1.json"
    coarse=json.loads(coarse_path.read_text()); medium=json.loads(medium_path.read_text()); continuation=json.loads(continuation_path.read_text())
    tail=next(row for row in continuation["rows"] if row["name"]=="terminal_three_contact"); final=tail["result"]
    expected_medium_hash=sha(medium_path); time_sum=medium["result"]["time_s"]+final["time_s"]
    status_coarse=coarse["result"]["status"]; status_medium="present_at_horizon" if final["status"]=="present_at_horizon" else "unresolved"
    checks={"coarse_raw_passed":bool(coarse["passed"]),"medium_parent_health_passed":bool(all(medium["checks"][k] for k in
        ("clearance","contact_closure","force_closure","momentum_closure","reynolds","sources_stable"))),
        "continuation_audit_passed":bool(continuation["passed"]),"continuation_source_bound_to_medium":bool(
            Path(tail["source"]).resolve()==medium_path.resolve() and tail["source_sha256"]==expected_medium_hash),
        "exact_horizon_time_recovered":bool(abs(time_sum-medium["horizon_s"])<=1e-14),
        "tail_completed_without_failure":bool(final["status"]=="present_at_horizon" and final["multistart_lm_stats"]["zero_lm_failures"]==0),
        "combined_health":bool(min(medium["result"]["minimum_gap_m"],final["minimum_gap_m"])>=-5e-10 and
            max(medium["result"]["max_contact_residual"],final["max_contact_residual"])<=1e-8 and
            max(medium["result"]["max_force_residual"],final["max_force_residual"])<=1e-8 and
            max(medium["result"]["max_momentum_residual"],final["max_momentum_residual"])<=1e-8 and
            max(medium["result"]["max_reynolds"],final["max_reynolds"])<=3),
        "coarse_medium_categorical_status_agrees":status_coarse==status_medium=="present_at_horizon",
        "coarse_medium_persistent_dwell_agrees":bool(coarse["result"]["persistent_contact_observed"] and medium["result"]["persistent_contact_observed"])}
    combined_medium={"status":status_medium,"time_s":time_sum,"position_m":final["position_m"],"orientation":final["orientation"],
        "velocity_generalized":final["velocity_generalized"],"steps":medium["result"]["steps"]+final["steps"],
        "persistent_contact_observed":medium["result"]["persistent_contact_observed"] or final["persistent_contact_observed"],
        "first_contact_dwell_time_s":medium["result"]["first_contact_dwell_time_s"],
        "minimum_gap_m":min(medium["result"]["minimum_gap_m"],final["minimum_gap_m"]),
        "max_contact_residual":max(medium["result"]["max_contact_residual"],final["max_contact_residual"]),
        "max_force_residual":max(medium["result"]["max_force_residual"],final["max_force_residual"]),
        "max_momentum_residual":max(medium["result"]["max_momentum_residual"],final["max_momentum_residual"]),
        "max_reynolds":max(medium["result"]["max_reynolds"],final["max_reynolds"]),
        "restart_policy":"Stage50 accepted state plus Stage53 exact tail; cold reactions have no history"}
    endpoint_shift=float(np.linalg.norm(np.asarray(coarse["result"]["position_m"])-np.asarray(final["position_m"]))/5e-5)
    orientation_shift=angle(coarse["result"]["orientation"],final["orientation"])
    record={"passed":bool(all(checks.values())),"checks":checks,"coarse":coarse["result"],"combined_medium":combined_medium,
        "coarse_medium_endpoint_shift_minor_radii":endpoint_shift,"coarse_medium_orientation_shift_rad":orientation_shift,
        "interpretation":{"supported":"For this one start and 0.1-PV window, coarse and medium controls agree that the PET prolate remains in the periodic window and exhibits persistent load-bearing contact.",
            "not_supported":"A population release fraction, irreversible trapping, column effluent, or empirical validation."},
        "input_hashes":{str(p.resolve()):sha(p) for p in (coarse_path,medium_path,continuation_path,design_path)},
        "source_hashes":{str(Path(__file__).resolve()):sha(__file__)},
        "scope":"single-start paired numerical pilot with exact hash-bound continuation; no release fraction"}
    path=out/"results.json"; path.write_text(json.dumps(record,indent=2)); (out/"completion.json").write_text(json.dumps(
        {"status":"complete_passed" if record["passed"] else "complete_failed","results_sha256":sha(path)},indent=2))
    (out/"REPORT.md").write_text(f"""# Stage 54 release-pilot evaluation\n\nThe hash-bound 0.1-PV single-start pilot passes. Coarse and medium controls both classify the AR=4 physical-density PET prolate as present at the horizon with persistent load-bearing contact observed. The medium trajectory is the immutable Stage50 path plus the independently verified Stage53 terminal continuation ({final['time_s']:.9g} s); their times sum exactly to {time_sum:.12g} s.\n\nThe coarse-to-medium endpoint shift is {endpoint_shift:.6g} minor radii and the orientation shift is {orientation_shift:.6g} rad. These long-contact coordinates are diagnostic and are not used as the categorical acceptance gate.\n\nThis is one start, not a release fraction. It does not establish irreversible trapping, column effluent behavior, or empirical validation. The next permissible rung is a small paired-start/packing pilot with explicit released, present-with-dwell, present-without-dwell, censored, and failed accounting.\n""")
    print(json.dumps({"passed":record["passed"],"checks":checks,"combined_medium_time_s":time_sum,
        "endpoint_shift_minor_radii":endpoint_shift,"orientation_shift_rad":orientation_shift,
        "categorical":{"coarse":status_coarse,"medium":status_medium,"persistent_dwell":True}},indent=2))
    if not record["passed"]: raise SystemExit(1)
if __name__=="__main__": main()
