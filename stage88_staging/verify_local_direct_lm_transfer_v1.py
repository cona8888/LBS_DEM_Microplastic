"""Local restarted Stage81 trajectory A/B for direct-LM-first contact solve.

This is not a continuation of Stage86 and cannot produce release evidence.
The candidate attempts the same equations and original Stage50 gates, then
falls back to unchanged Stage53 on any candidate failure.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage41_staging"),
                str(ROOT / "stage53_staging"), str(ROOT / "stage81_staging"),
                str(ROOT / "stage88_staging")]
import matrix_case_v1
import geometry_exact_v1
import inertial_contact_multistart_lm_v1 as stage53
import trajectory_combined_scalar_v1 as trajectory
from benchmark_direct_lm_v1 import direct

DESIGN = ROOT / "stage86_designs" / "near_outlet_conditional_pilot_v1.json"
CASE = (ROOT / "stage86_runs" / "near_outlet_conditional_20260913" /
        "seed2_pair_01" / "s2_prolate_ar4.json")
BENCH = ROOT / "stage88_evaluations" / "direct_lm_frozen_systems_01" / "results.json"
OUT = ROOT / "stage88_evaluations" / "local_direct_lm_transfer_03"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    bench_completion = json.loads((BENCH.parent / "completion.json").read_text())
    benchmark = json.loads(BENCH.read_text())
    if (bench_completion["status"] != "complete_benchmarked" or
            bench_completion["results_sha256"] != sha(BENCH) or
            not benchmark["all_candidate_gates_passed"]):
        raise RuntimeError("frozen-system prerequisite failed")
    for path, digest in {**benchmark["input_hashes"], **benchmark["source_hashes"]}.items():
        if sha(path) != digest:
            raise RuntimeError(f"benchmark lineage drift: {path}")
    config = json.loads(DESIGN.read_text())
    previous = json.loads(CASE.read_text())["result"]
    if previous["status"] != "incomplete_budget":
        raise RuntimeError("wrong source state")
    OUT.mkdir(parents=True, exist_ok=False)
    field, old_geometry, length, _, _ = matrix_case_v1.load(2)
    geometry = geometry_exact_v1.GrainGeometry.from_geometry(old_geometry)
    a, b, _ = config["prolate_semiaxes_m"]

    def run():
        return trajectory.integrate(
            field, geometry, previous["position_m"], previous["orientation"],
            previous["velocity_generalized"], a, b,
            config["dynamic_viscosity_Pa_s"], config["particle_density_kg_m3"],
            config["fluid_density_kg_m3"], config["gravity_m_s2"],
            config["friction_coefficient"], length, 0.01,
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

    baseline = run()
    counts = {"attempts": 0, "direct_accepted": 0, "fallbacks": 0}
    original = stage53._solve

    def candidate(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
        if 0 < len(gaps) <= 3:
            counts["attempts"] += 1
            try:
                answer = direct(vfree, mobility, jacobian, gaps, dt, friction)
            except (RuntimeError, ValueError, FloatingPointError,
                    np.linalg.LinAlgError, OverflowError):
                counts["fallbacks"] += 1
            else:
                counts["direct_accepted"] += 1
                return answer
        return original(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter)

    stage53._solve = candidate
    try:
        trial = run()
    finally:
        stage53._solve = original
    fields = ("position_m", "orientation", "velocity_generalized")
    differences = {key: float(np.max(np.abs(np.asarray(baseline[key])-
                                             np.asarray(trial[key])))) for key in fields}
    status_match = baseline["status"] == trial["status"]
    time_match = abs(baseline["time_s"]-trial["time_s"]) <= 1e-12
    health_ok = bool(all(trial[key] <= limit for key, limit in (
        ("max_contact_residual", 1e-8), ("max_force_residual", 1e-8),
        ("max_momentum_residual", 1e-8), ("max_reynolds", 3.))))
    passed = bool(status_match and time_match and health_ok and
                  max(differences.values()) <= 1e-9 and counts["direct_accepted"] > 0)
    record = {
        "diagnostic_only": True, "passed": passed,
        "claim_boundary": "Local restarted trajectory A/B only; no Stage86 continuation, release, or validation claim.",
        "local_horizon_s": 0.01, "wall_budget_s_per_arm": 30.,
        "baseline": baseline, "candidate": trial,
        "candidate_counts": counts, "differences": differences,
        "status_match": status_match, "time_match": time_match,
        "candidate_health_ok": health_ok,
        "input_hashes": {str(p): sha(p) for p in (DESIGN, CASE, BENCH)},
        "source_hashes": {str(p): sha(p) for p in (Path(__file__),
                          Path(trajectory.__file__), Path(stage53.__file__),
                          Path(matrix_case_v1.__file__), Path(geometry_exact_v1.__file__))},
    }
    path = OUT / "results.json"
    path.write_text(json.dumps(record, indent=2,
                               default=lambda value: value.item() if isinstance(
                                   value, np.generic) else value.tolist() if isinstance(
                                       value, np.ndarray) else str(value)))
    (OUT / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if passed else "complete_failed",
        "results_sha256": sha(path)}, indent=2))
    print(json.dumps({"passed": passed, "baseline_runtime_s": baseline["runtime_seconds"],
                      "candidate_runtime_s": trial["runtime_seconds"],
                      "counts": counts, "differences": differences}, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
