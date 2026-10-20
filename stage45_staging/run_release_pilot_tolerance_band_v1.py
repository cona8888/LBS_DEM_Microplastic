"""Rerun the frozen Stage43 pilot with the verified Stage45 tolerance band."""
import hashlib, json, platform, sys, time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage41_staging"),
                str(ROOT / "stage45_staging")]
import matrix_case_v1, geometry_exact_v1
import trajectory_tolerance_band_v1 as trajectory

DESIGN = ROOT / "stage43_designs" / "release_pilot_v1.json"

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def sources():
    paths = {Path(__file__).resolve()}
    for module in list(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if path and Path(path).suffix == ".py" and Path(path).resolve().is_relative_to(ROOT):
            paths.add(Path(path).resolve())
    return {str(path): sha(path) for path in sorted(paths)}

def main():
    output = ROOT / "stage45_runs" / "release_pilot_20260912" / "pilot_01"
    output.mkdir(parents=True, exist_ok=False)
    cfg = json.loads(DESIGN.read_text()); before = sources()
    field, old_geometry, length, spacing, matrix_inputs = matrix_case_v1.load(cfg["packing_seed"])
    geometry = geometry_exact_v1.GrainGeometry.from_geometry(old_geometry)
    start_path = ROOT / cfg["start_source"]
    start = next(row for row in json.loads(start_path.read_text()) if row["id"] == cfg["start_id"])
    a, b, _ = cfg["shape"]["semiaxes_m"]
    horizon = cfg["horizon_pore_volumes"] * length / cfg["target_mean_interstitial_velocity_m_s"]
    rows = []; started = time.perf_counter()
    for level in cfg["levels"]:
        result = trajectory.integrate(
            field, geometry, start["position_m"], start["orientation"], np.zeros(6),
            a, b, cfg["dynamic_viscosity_Pa_s"], cfg["particle_density_kg_m3"],
            cfg["fluid_density_kg_m3"], cfg["gravity_m_s2"], cfg["friction_coefficient"],
            length, horizon, added_mass_fraction=cfg["added_mass_fraction"],
            cutoff_ratio=0.2, roughness_ratio=0.01,
            displacement_fraction=level["displacement_fraction"],
            relaxation_fraction=level["relaxation_fraction"],
            angle_limit=cfg["fixed_numerics"]["angle_limit_rad"],
            max_dt=cfg["fixed_numerics"]["max_dt_s"],
            wall_budget=cfg["fixed_numerics"]["wall_budget_s_per_case"],
            trap_reference_speed=cfg["target_mean_interstitial_velocity_m_s"],
            trap_dwell_time=cfg["trap_dwell_time_s"],
            trap_speed_ratio=cfg["trap_speed_ratio"],
            trap_drift_over_minor_radius=cfg["trap_drift_over_minor_radius"],
            stop_on_trap=False, reynolds_limit=cfg["fixed_numerics"]["reynolds_limit"])
        row = {"level": level, "result": result}; rows.append(row)
        (output / f"{level['name']}.json").write_text(json.dumps(row, indent=2))
        print(json.dumps({"level": level["name"], "status": result["status"],
                          "persistent_contact_observed": result["persistent_contact_observed"],
                          "time_s": result["time_s"], "steps": result["steps"],
                          "tolerance_band_stats": result["tolerance_band_stats"],
                          "runtime_seconds": result["runtime_seconds"]}), flush=True)
    after = sources(); statuses = [row["result"]["status"] for row in rows]
    dwells = [row["result"]["persistent_contact_observed"] for row in rows]
    checks = {
        "both_cases_complete_without_failure_or_budget_censoring": all(
            status not in {"numerical_failure", "incomplete_budget", "unresolved_model", "unresolved_field"}
            for status in statuses),
        "status_and_persistent_dwell_agree": len(set(statuses)) == 1 and len(set(dwells)) == 1,
        "clearance": all(row["result"]["minimum_gap_m"] >= -5e-10 for row in rows),
        "contact_closure": all(row["result"]["max_contact_residual"] <= 1e-8 for row in rows),
        "momentum_closure": all(row["result"]["max_momentum_residual"] <= 1e-8 for row in rows),
        "reynolds_envelope": all(row["result"]["max_reynolds"] <= 3 for row in rows),
        "all_clips_within_geometry_tolerance": all(
            row["result"]["tolerance_band_stats"]["most_negative_clipped_gap_m"] >= -5e-10
            for row in rows),
        "tolerance_band_exercised": all(
            row["result"]["tolerance_band_stats"]["clipped_gaps"] > 0 for row in rows),
        "sources_stable": before == after}
    input_paths = (*matrix_inputs, DESIGN, start_path)
    record = {"completed": True, "passed": bool(all(checks.values())), "checks": checks,
              "rows": rows, "horizon_s": horizon, "cell_length_m": length,
              "spacing_m": spacing, "runtime_seconds": time.perf_counter()-started,
              "source_hashes": after, "source_hashes_at_start": before,
              "input_hashes": {str(path.resolve()): sha(path) for path in input_paths},
              "environment": {"python": platform.python_version(), "numpy": np.__version__},
              "claim_boundary": cfg["claim_boundary"]}
    path = output / "results.json"; path.write_text(json.dumps(record, indent=2))
    (output / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if record["passed"] else "complete_failed",
        "results_sha256": sha(path)}, indent=2))
    print(json.dumps({"passed": record["passed"], "checks": checks,
                      "runtime_seconds": record["runtime_seconds"]}, indent=2))
    if not record["passed"]: raise SystemExit(1)

if __name__ == "__main__": main()
