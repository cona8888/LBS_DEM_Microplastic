"""Bounded s3 AR=4 crossing and unchanged s2 sphere control for Stage68."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage40_staging"),str(ROOT/"stage41_staging"),str(ROOT/"stage68_staging")]
import matrix_case_v1
import geometry_exact_v1
import trajectory_extended_portfolio_v1 as trajectory

DESIGN=ROOT/"stage55_designs"/"paired_three_packing_pilot_v1.json"
OLD=ROOT/"stage55_runs"/"paired_three_packing_pilot_20260912"/"pilot_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(seed,shape,horizon,wall_budget):
    cfg=json.loads(DESIGN.read_text())
    item=next(x for x in cfg["packings"] if x["seed"]==seed)
    field,old,L,dx,inputs=matrix_case_v1.load(seed)
    geometry=geometry_exact_v1.GrainGeometry.from_geometry(old)
    starts=ROOT/f"stage37_runs/stage4_farfield_bound_20260912/pilot_01/starts_s{seed}.json"
    start=next(x for x in json.loads(starts.read_text()) if x["id"]==item["start_id"])
    a,b,_=cfg["prolate_semiaxes_m"]
    if shape=="equal_volume_sphere":
        a=b=(a*b*b)**(1/3)
    result=trajectory.integrate(
        field,geometry,start["position_m"],start["orientation"],np.zeros(6),a,b,
        cfg["dynamic_viscosity_Pa_s"],cfg["particle_density_kg_m3"],
        cfg["fluid_density_kg_m3"],cfg["gravity_m_s2"],cfg["friction_coefficient"],
        L,horizon,added_mass_fraction=cfg["added_mass_fraction"],
        cutoff_ratio=.2,roughness_ratio=.01,
        displacement_fraction=cfg["numerics"]["displacement_fraction"],
        relaxation_fraction=cfg["numerics"]["relaxation_fraction"],
        angle_limit=cfg["numerics"]["angle_limit_rad"],
        max_dt=cfg["numerics"]["max_dt_s"],wall_budget=wall_budget,
        trap_reference_speed=cfg["target_mean_interstitial_velocity_m_s"],
        trap_dwell_time=cfg["trap"]["dwell_time_s"],
        trap_speed_ratio=cfg["trap"]["speed_ratio"],
        trap_drift_over_minor_radius=cfg["trap"]["drift_over_minor_radius"],
        stop_on_trap=cfg["trap"]["absorbing"],
        reynolds_limit=cfg["numerics"]["reynolds_limit"])
    return result,L


def main():
    out=ROOT/"stage68_evaluations"/"short_fibre_crossing_01"
    out.mkdir(parents=True,exist_ok=False)
    cfg=json.loads(DESIGN.read_text())
    L2=matrix_case_v1.load(2)[2]
    sphere_horizon=cfg["horizon_pore_volumes"]*L2/cfg["target_mean_interstitial_velocity_m_s"]
    sphere,_=run(2,"equal_volume_sphere",sphere_horizon,60.)
    prior_sphere=json.loads((OLD/"s2_equal_volume_sphere.json").read_text())["result"]
    excluded={"runtime_seconds","contact_solver_retries","recovery_portfolio_stats","multistart_lm_stats"}
    same={k:v for k,v in sphere.items() if k not in excluded}=={k:v for k,v in prior_sphere.items() if k not in excluded}
    prior_fibre=json.loads((OLD/"s3_prolate_ar4.json").read_text())["result"]
    target=prior_fibre["time_s"]+.05
    fibre,_=run(3,"prolate_ar4",target,300.)
    health=(fibre["minimum_gap_m"]>=-5e-10 and fibre["max_contact_residual"]<=1e-8
            and fibre["max_force_residual"]<=1e-8 and
            fibre["max_momentum_residual"]<=1e-8 and fibre["max_reynolds"]<=3)
    checks={"sphere_exact_unchanged":bool(same),
            "fibre_crossed_prior_failure":bool(fibre["status"]=="present_at_horizon"
                                               and fibre["time_s"]==target and
                                               fibre["contact_solver_retries"]>0),
            "fibre_health":bool(health),
            "fibre_within_budget":bool(fibre["runtime_seconds"]<=300.)}
    record={"passed":all(checks.values()),"checks":checks,
            "sphere":sphere,"fibre":fibre,
            "source_hashes":{str(Path(__file__).resolve()):sha(__file__),
                             str((ROOT/"stage67_staging/inertial_contact_recovery_portfolio_v1.py").resolve()):sha(ROOT/"stage67_staging/inertial_contact_recovery_portfolio_v1.py"),
                             str((ROOT/"stage68_staging/trajectory_extended_recovery_v1.py").resolve()):sha(ROOT/"stage68_staging/trajectory_extended_recovery_v1.py"),
                             str((ROOT/"stage68_staging/trajectory_extended_portfolio_v1.py").resolve()):sha(ROOT/"stage68_staging/trajectory_extended_portfolio_v1.py")},
            "claim_boundary":"Numerical application verification only; no morphology or release inference."}
    path=out/"results.json"
    path.write_text(json.dumps(record,indent=2))
    (out/"completion.json").write_text(json.dumps({"status":"complete_passed" if record["passed"] else "complete_failed","results_sha256":sha(path)},indent=2))
    print(json.dumps({"passed":record["passed"],"checks":checks,
                      "fibre_time_s":fibre["time_s"],
                      "fibre_status":fibre["status"],
                      "fibre_runtime_s":fibre["runtime_seconds"],
                      "portfolio_stats":fibre["recovery_portfolio_stats"]},indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__=="__main__":
    main()
