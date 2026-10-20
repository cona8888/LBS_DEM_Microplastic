"""Profile a short seed-2 contact episode from the last accepted Stage55 state.

The pose and velocity are copied from the immutable failed case. Time and trap
history restart at zero, so this is a local cost diagnostic, not a trajectory
continuation or a release/trapping result. The Stage70 equations and gates stay
unchanged. No output is written to the source run.
"""
import cProfile
import hashlib
import io
import json
import pstats
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage41_staging"),
                str(ROOT / "stage70_staging")]
import matrix_case_v1
import geometry_exact_v1
import trajectory_runtime_portfolio_v1 as trajectory

DESIGN = ROOT / "stage55_designs" / "paired_three_packing_pilot_v1.json"
OLD = ROOT / "stage55_runs" / "paired_three_packing_pilot_20260912" / "pilot_01" / "s2_prolate_ar4.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output = ROOT / "stage73_evaluations" / "seed2_local_profile_01"
    output.mkdir(parents=True, exist_ok=False)
    config = json.loads(DESIGN.read_text())
    previous = json.loads(OLD.read_text())["result"]
    if previous["status"] != "numerical_failure":
        raise RuntimeError("expected frozen numerical-failure state")
    field, old_geometry, length, dx, inputs = matrix_case_v1.load(2)
    geometry = geometry_exact_v1.GrainGeometry.from_geometry(old_geometry)
    a, b, _ = config["prolate_semiaxes_m"]
    profile = cProfile.Profile()
    profile.enable()
    try:
        result = trajectory.integrate(
            field, geometry, previous["position_m"], previous["orientation"],
            previous["velocity_generalized"], a, b,
            config["dynamic_viscosity_Pa_s"], config["particle_density_kg_m3"],
            config["fluid_density_kg_m3"], config["gravity_m_s2"],
            config["friction_coefficient"], length, 0.002,
            added_mass_fraction=config["added_mass_fraction"],
            cutoff_ratio=0.2, roughness_ratio=0.01,
            displacement_fraction=config["numerics"]["displacement_fraction"],
            relaxation_fraction=config["numerics"]["relaxation_fraction"],
            angle_limit=config["numerics"]["angle_limit_rad"],
            max_dt=config["numerics"]["max_dt_s"], wall_budget=30.,
            trap_reference_speed=config["target_mean_interstitial_velocity_m_s"],
            trap_dwell_time=config["trap"]["dwell_time_s"],
            trap_speed_ratio=config["trap"]["speed_ratio"],
            trap_drift_over_minor_radius=config["trap"]["drift_over_minor_radius"],
            stop_on_trap=config["trap"]["absorbing"],
            reynolds_limit=config["numerics"]["reynolds_limit"])
    finally:
        profile.disable()
    stream = io.StringIO()
    pstats.Stats(profile, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(50)
    (output / "profile.txt").write_text(stream.getvalue())
    record = {"diagnostic_only": True, "prior_status": previous["status"],
              "prior_time_s": previous["time_s"], "local_horizon_s": 0.002,
              "wall_budget_s": 30., "result": result,
              "input_hashes": {str(OLD): sha(OLD), str(DESIGN): sha(DESIGN)},
              "source_hashes": {
                  str(Path(__file__).resolve()): sha(__file__),
                  str(Path(trajectory.__file__).resolve()): sha(trajectory.__file__),
                  str(Path(geometry_exact_v1.__file__).resolve()): sha(geometry_exact_v1.__file__)},
              "claim_boundary": "Local restarted cost diagnostic only; not a physical continuation, release event, or validation."}
    path = output / "results.json"
    path.write_text(json.dumps(record, indent=2))
    (output / "completion.json").write_text(json.dumps({
        "status": "complete_profiled", "results_sha256": sha(path),
        "profile_sha256": sha(output / "profile.txt")}, indent=2))
    print(json.dumps({"status": result["status"], "reason": result["reason"],
                      "time_s": result["time_s"], "runtime_s": result["runtime_seconds"],
                      "steps": result["steps"], "contact_steps": result["contact_steps"],
                      "contact_solver_retries": result["contact_solver_retries"]}, indent=2))


if __name__ == "__main__":
    main()
