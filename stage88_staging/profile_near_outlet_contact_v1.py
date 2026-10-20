"""Profile the frozen Stage86 fibre state without claiming trajectory continuation.

The saved pose/velocity are restarted with zeroed time and dwell history. This
is a bounded, local algorithm diagnostic. It preserves the Stage81 equations,
contact acceptance gates, and every immutable source artifact.
"""
import cProfile
import hashlib
import io
import json
import pstats
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage41_staging"),
                str(ROOT / "stage70_staging"), str(ROOT / "stage81_staging")]
import matrix_case_v1
import geometry_exact_v1
import inertial_contact_runtime_portfolio_v1 as portfolio
import trajectory_combined_scalar_v1 as trajectory

DESIGN = ROOT / "stage86_designs" / "near_outlet_conditional_pilot_v1.json"
CASE = (ROOT / "stage86_runs" / "near_outlet_conditional_20260913" /
        "seed2_pair_01" / "s2_prolate_ar4.json")
OUT = ROOT / "stage88_evaluations" / "near_outlet_contact_profile_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    config = json.loads(DESIGN.read_text())
    previous = json.loads(CASE.read_text())["result"]
    if previous["status"] != "incomplete_budget":
        raise RuntimeError("expected budget-censored Stage86 fibre")
    OUT.mkdir(parents=True, exist_ok=False)
    field, old_geometry, length, _, _ = matrix_case_v1.load(2)
    geometry = geometry_exact_v1.GrainGeometry.from_geometry(old_geometry)
    a, b, _ = config["prolate_semiaxes_m"]
    calls = []
    systems = []
    original = portfolio._solve

    def observed(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
        start = time.perf_counter()
        try:
            answer = original(vfree, mobility, jacobian, gaps, dt,
                              friction, tol, maxiter)
        except Exception as exc:
            calls.append({"contacts": len(gaps), "elapsed_s": time.perf_counter()-start,
                          "error": type(exc).__name__})
            raise
        elapsed = time.perf_counter()-start
        health = answer[1]
        calls.append({"contacts": len(gaps), "elapsed_s": elapsed,
                      "iterations": health.get("iterations"),
                      "solver": health.get("solver", health.get("method")),
                      "recovery_mode": portfolio.recovery_mode()})
        if len(gaps) >= 1:
            arrays = {"vfree": np.array(vfree, copy=True),
                      "mobility": np.array(mobility, copy=True),
                      "jacobian": np.array(jacobian, copy=True),
                      "gaps": np.array(gaps, copy=True),
                      "dt": np.array(dt), "friction": np.array(friction),
                      "tol": np.array(tol), "maxiter": np.array(maxiter),
                      "velocity": np.array(answer[0], copy=True),
                      "reactions": np.array(health["reactions"], copy=True)}
            systems.append((elapsed, arrays, dict(calls[-1])))
            systems.sort(key=lambda item: item[0], reverse=True)
            del systems[3:]
        return answer

    profile = cProfile.Profile()
    portfolio._solve = observed
    try:
        profile.enable()
        result = trajectory.integrate(
            field, geometry, previous["position_m"], previous["orientation"],
            previous["velocity_generalized"], a, b,
            config["dynamic_viscosity_Pa_s"], config["particle_density_kg_m3"],
            config["fluid_density_kg_m3"], config["gravity_m_s2"],
            config["friction_coefficient"], length, 0.0002,
            added_mass_fraction=config["added_mass_fraction"],
            cutoff_ratio=0.2, roughness_ratio=0.01,
            displacement_fraction=config["numerics"]["displacement_fraction"],
            relaxation_fraction=config["numerics"]["relaxation_fraction"],
            angle_limit=config["numerics"]["angle_limit_rad"],
            max_dt=config["numerics"]["max_dt_s"], wall_budget=20.,
            trap_reference_speed=config["target_mean_interstitial_velocity_m_s"],
            trap_dwell_time=config["trap"]["dwell_time_s"],
            trap_speed_ratio=config["trap"]["speed_ratio"],
            trap_drift_over_minor_radius=config["trap"]["drift_over_minor_radius"],
            stop_on_trap=config["trap"]["absorbing"],
            reynolds_limit=config["numerics"]["reynolds_limit"])
    finally:
        profile.disable()
        portfolio._solve = original
    stream = io.StringIO()
    pstats.Stats(profile, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(60)
    profile_path = OUT / "profile.txt"
    profile_path.write_text(stream.getvalue())
    system_paths = []
    for index, (elapsed, arrays, call) in enumerate(systems, 1):
        path = OUT / f"cold_system_{index}.npz"
        np.savez_compressed(path, **arrays)
        system_paths.append({"path": str(path), "sha256": sha(path),
                             "elapsed_s": elapsed, "call": call})
    record = {
        "diagnostic_only": True,
        "claim_boundary": "Local restarted cost diagnostic, not physical continuation or release evidence.",
        "source_state_time_s": previous["time_s"],
        "local_horizon_s": 0.0002, "wall_budget_s": 20.,
        "result": result, "cold_calls": calls,
        "top_systems": system_paths,
        "input_hashes": {str(p): sha(p) for p in (DESIGN, CASE)},
        "source_hashes": {str(p): sha(p) for p in (Path(__file__),
                          Path(trajectory.__file__), Path(portfolio.__file__),
                          Path(matrix_case_v1.__file__), Path(geometry_exact_v1.__file__))},
        "profile_sha256": sha(profile_path),
        "environment": {"numpy": np.__version__, "python": sys.version},
    }
    results = OUT / "results.json"
    results.write_text(json.dumps(record, indent=2))
    (OUT / "completion.json").write_text(json.dumps({
        "status": "complete_profiled", "results_sha256": sha(results)}, indent=2))
    print(json.dumps({"local_status": result["status"], "local_time_s": result["time_s"],
                      "runtime_s": result["runtime_seconds"], "cold_calls": len(calls),
                      "top_systems": len(system_paths), "output": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
