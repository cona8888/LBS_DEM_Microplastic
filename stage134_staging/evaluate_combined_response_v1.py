"""Independent temporal and CPD2/CPD4/CPD6 response-budget evaluation."""
from pathlib import Path
import json, sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage134_staging"), str(ROOT / "stage131_staging")]
import sphere_combined_budget_refinement_v1 as job

api = job.api
reference = job.prior4.prior.prior.reference
OUT = job.EVAL / "independent_evaluation_01"
LIMITS = {"position_difference_over_b": .02, "apolar_axis_angle_rad": .01,
          "translational_velocity_relative_difference": .05}


def read(relative): return api.read(ROOT / relative)


PATHS = {
 "sphere": {
  "cpd2": "stage122_runs/sphere_timestep_refinement_20260916/sentinels_01/refined_s2_sphere_f1p0_cpd2_dt16_h0p5/segment_01/record.json",
  "cpd4_m": "stage131_runs/cpd4_timestep_refinement_20260916/sentinels_01/refined_s2_sphere_dt32_f1p0_cpd4_h0p5/segment_01/record.json",
  "cpd4": "stage134_runs/sphere_combined_budget_refinement_20260916/sentinels_01/refined_s2_sphere_f1p0_cpd4_dt64_h0p5/segment_01/record.json",
  "cpd6_c": "stage133_runs/cpd6_response_refinement_20260916/sentinels_01/fresh_s2_sphere_f1p0_cpd6_dt16_h0p5/segment_01/record.json",
  "cpd6_m": "stage133_runs/cpd6_response_refinement_20260916/sentinels_01/fresh_s2_sphere_f1p0_cpd6_dt32_h0p5/segment_01/record.json",
  "cpd6": "stage134_runs/sphere_combined_budget_refinement_20260916/sentinels_01/refined_s2_sphere_f1p0_cpd6_dt64_h0p5/segment_01/record.json"},
 "fibre": {
  "cpd2": "stage121_runs/matched_seed2_resolution_20260916/sentinels_01/fresh_s2_ar4_f1p0_cpd2_dt8_h0p5/segment_01/record.json",
  "cpd4_m": "stage121_runs/matched_seed2_resolution_20260916/sentinels_01/fresh_s2_ar4_f1p0_cpd4_dt8_h0p5/segment_01/record.json",
  "cpd4": "stage131_runs/cpd4_timestep_refinement_20260916/sentinels_01/refined_s2_ar4_dt16_f1p0_cpd4_h0p5/segment_02/record.json",
  "cpd6_c": "stage133_runs/cpd6_response_refinement_20260916/sentinels_01/fresh_s2_ar4_f1p0_cpd6_dt4_h0p5/segment_01/record.json",
  "cpd6_m": "stage133_runs/cpd6_response_refinement_20260916/sentinels_01/fresh_s2_ar4_f1p0_cpd6_dt8_h0p5/segment_01/record.json",
  "cpd6": "stage133_runs/cpd6_response_refinement_20260916/sentinels_01/fresh_s2_ar4_f1p0_cpd6_dt16_h0p5/segment_02/record.json"}}


def audit_run(design_path, run_path):
    design, done = api.read(design_path), api.read(run_path / "completion.json")
    api.require(done["design_sha256"] == api.sha(design_path), "run/design drift")
    rows = []
    for case, entry in zip(design["cases"], done["ledger"]):
        api.require(case["id"] == entry["case_id"] and entry["status"] == "present_at_horizon", "incomplete case")
        record_path = Path(entry["last_record"]); record = api.read(record_path)
        api.require(api.sha(record_path) == entry["record_sha256"], "record drift")
        health = reference.independent_health(record["result"], case["spec"])
        api.require(health["passed"] and abs(record["result"]["time_s"]-.5) < 1e-12, "unhealthy trajectory")
        rows.append({"case_id": case["id"], "health": health, "record_sha256": api.sha(record_path)})
    return rows, not list(run_path.rglob("failure.json")) and not done["stopped_on_failure"] and not any(p.stat().st_size for p in run_path.rglob("*.stderr.txt"))


def main():
    rows133, clean133 = audit_run(job.prior6.DESIGN, job.prior6.RUN)
    rows134, clean134 = audit_run(job.DESIGN, job.RUN)
    spec_by_shape = {"sphere": api.read(job.DESIGN)["cases"][0]["spec"],
                     "fibre": next(c["spec"] for c in api.read(job.prior6.DESIGN)["cases"] if c["spec"]["shape"] == api.SHAPES[1])}
    shapes = []
    for name, paths in PATHS.items():
        records = {key: read(path) for key, path in paths.items()}
        spec = spec_by_shape[name]
        d24 = reference.difference(records["cpd2"], records["cpd4"], spec)
        d46 = reference.difference(records["cpd4"], records["cpd6"], spec)
        t4 = reference.difference(records["cpd4_m"], records["cpd4"], spec)
        t6 = reference.difference(records["cpd6_m"], records["cpd6"], spec)
        c6m = reference.difference(records["cpd6_c"], records["cpd6_m"], spec)
        combined = {key: d46[key] + 2*t4[key] + 2*t6[key] for key in LIMITS}
        checks = {"grid_difference_decreases_"+key: d46[key] <= d24[key] + 1e-12 for key in LIMITS}
        checks.update({"combined_budget_"+key: combined[key] <= limit for key,limit in LIMITS.items()})
        checks.update({"cpd6_temporal_"+key: t6[key] <= limit for key,limit in LIMITS.items()})
        checks.update({"cpd6_temporal_trend_"+key: t6[key] <= 1.1*c6m[key] + 1e-8 for key in LIMITS})
        checks["same_event_class"] = len({records[x]["result"]["persistent_contact_observed"] for x in records}) == 1
        shapes.append({"shape": name, "cpd2_to_cpd4": d24, "cpd4_to_cpd6": d46,
                       "latest_cpd4_temporal": t4, "latest_cpd6_temporal": t6,
                       "combined_spatial_plus_twice_temporal": combined, "limits": LIMITS,
                       "checks": checks, "passed": all(checks.values()),
                       "record_bindings": {key: {"path": str(ROOT/path), "sha256": api.sha(ROOT/path)} for key,path in paths.items()}})
    passed = clean133 and clean134 and all(x["passed"] for x in shapes)
    result = {"passed": passed, "status": "matched_cpd4_cpd6_response_budget_qualified" if passed else "matched_cpd4_cpd6_response_budget_unresolved",
              "stage133_cases": rows133, "stage134_cases": rows134, "no_failure_or_stderr": clean133 and clean134,
              "shapes": shapes,
              "claim": "Finite-level 0.5-s numerical response screening for one matched seed/start; not asymptotic convergence or population release validation.",
              "next": "Return to the separate literature-matched physical-validation branch; do not extrapolate this sentinel to matrix release."}
    OUT.mkdir(parents=True, exist_ok=False); api.write(OUT / "results.json", result)
    artifacts = {str(OUT / "results.json"): api.sha(OUT / "results.json"), str(Path(__file__).resolve()): api.sha(Path(__file__).resolve()),
                 str(job.prior6.RUN / "completion.json"): api.sha(job.prior6.RUN / "completion.json"), str(job.RUN / "completion.json"): api.sha(job.RUN / "completion.json")}
    api.write(OUT / "completion.json", {"passed": passed, "qualified": passed, "results_sha256": api.sha(OUT / "results.json"), "artifacts": artifacts})
    print(result["status"])
    for row in shapes: print(row["shape"], row["combined_spatial_plus_twice_temporal"], row["passed"])
    return 0 if passed else 4


if __name__ == "__main__": raise SystemExit(main())
