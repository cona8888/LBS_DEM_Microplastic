"""Independent Stage131 chain, health, and CPD4 temporal-budget audit."""
from pathlib import Path
import copy, sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage131_staging"))
import refine_cpd4_timesteps_v1 as job

api = job.api
OUT = job.EVAL / "independent_evaluation_01"
PRIOR = {
    "equal_volume_sphere": ROOT / "stage122_runs/sphere_timestep_refinement_20260916/sentinels_01/refined_s2_sphere_f1p0_cpd4_dt16_h0p5/segment_01/record.json",
    "rigid_prolate_ar4": ROOT / "stage121_runs/matched_seed2_resolution_20260916/sentinels_01/fresh_s2_ar4_f1p0_cpd4_dt8_h0p5/segment_01/record.json",
}
BUDGET = {"position_difference_over_b": 0.02, "apolar_axis_angle_rad": 0.01,
          "translational_velocity_relative_difference": 0.05}


def main():
    design = api.read(job.DESIGN)
    job.verify(design)
    done = api.read(job.RUN / "completion.json")
    manifest = api.read(job.RUN / "manifest.json")
    api.require(done["design_sha256"] == manifest["design_sha256"] == api.sha(job.DESIGN), "design drift")
    api.require(done["manifest_sha256"] == api.sha(job.RUN / "manifest.json"), "manifest drift")
    api.require([x["case_id"] for x in done["ledger"]] == manifest["case_order"] == [x["id"] for x in design["cases"]], "order drift")

    artifacts = {}
    ledger = []
    final_records = {}
    for case, entry in zip(design["cases"], done["ledger"]):
        previous = None
        segment_rows = []
        for index in range(1, entry["segments"] + 1):
            folder = job.RUN / case["id"] / f"segment_{index:02d}"
            record = api.read(folder / "record.json")
            completion = api.read(folder / "completion.json")
            launch = api.read(folder / "launch.json")
            api.require(completion["record_sha256"] == api.sha(folder / "record.json"), "record binding drift")
            api.require(completion["launch_sha256"] == api.sha(folder / "launch.json"), "launch binding drift")
            api.require(record["case_id"] == launch["case_id"] == case["id"] and record["segment"] == index, "identity drift")
            api.require(record["prior_record_sha256"] == (None if previous is None else api.sha(job.RUN / case["id"] / f"segment_{index-1:02d}" / "record.json")), "chain drift")
            state = record["result"]
            checkpoint = state["checkpoint"]
            api.require(checkpoint["state_sha256"] == api.digest(checkpoint["state"]), "checkpoint hash drift")
            api.require(checkpoint["state"]["t"] == state["time_s"] and checkpoint["state"]["x"] == state["position_m"], "checkpoint state drift")
            dense = api.read(folder / "accepted_intervals.json")
            api.require(api.sha(folder / "accepted_intervals.json") == record["accepted_intervals_sha256"], "interval binding drift")
            if dense:
                api.require(abs(dense[-1]["time_s"] - state["time_s"]) < 1e-12, "interval endpoint drift")
            health = job.prior.prior.reference.independent_health(state, case["spec"])
            segment_rows.append({"segment": index, "status": state["status"], "time_s": state["time_s"],
                                 "runtime_s": state["runtime_seconds"], "health": health,
                                 "max_interval_s": max((x["dt_s"] for x in dense), default=0.0)})
            for path in folder.iterdir():
                if path.is_file():
                    artifacts[str(path)] = api.sha(path)
            previous = record
        api.require(previous is not None and api.sha(entry["last_record"]) == entry["record_sha256"], "final record drift")
        qualified = previous["result"]["status"] == "present_at_horizon" and abs(previous["result"]["time_s"] - 0.5) < 1e-12 and all(x["health"]["passed"] for x in segment_rows)
        ledger.append({"case_id": case["id"], "shape": case["spec"]["shape"], "qualified": qualified,
                       "segments": segment_rows, "runtime_s": sum(x["runtime_s"] for x in segment_rows)})
        final_records[case["spec"]["shape"]] = previous

    comparisons = []
    for case in design["cases"]:
        shape = case["spec"]["shape"]
        prior_path = PRIOR[shape]
        api.require(prior_path.is_file(), "missing prior record")
        prior_record = api.read(prior_path)
        diff = job.prior.prior.reference.difference(prior_record, final_records[shape], case["spec"])
        doubled = {key: 2.0 * diff[key] for key in BUDGET}
        checks = {key: doubled[key] <= limit for key, limit in BUDGET.items()}
        comparisons.append({"shape": shape, "prior_record": str(prior_path), "prior_record_sha256": api.sha(prior_path),
                            "new_case_id": case["id"], "adjacent_difference": diff,
                            "twice_adjacent_temporal_proxy": doubled, "budget": BUDGET,
                            "checks": checks, "passed": all(checks.values())})

    no_failure = not list(job.RUN.rglob("failure.json")) and not done["stopped_on_failure"] and not any(p.stat().st_size for p in job.RUN.rglob("*.stderr.txt"))
    passed = all(x["qualified"] for x in ledger) and all(x["passed"] for x in comparisons) and no_failure
    result = {"passed": passed,
              "status": "cpd4_temporal_budget_qualified" if passed else "cpd4_temporal_budget_not_qualified",
              "ledger": ledger, "comparisons": comparisons, "no_failure_or_stderr": no_failure,
              "design_sha256": api.sha(job.DESIGN), "run_completion_sha256": api.sha(job.RUN / "completion.json"),
              "artifacts": artifacts,
              "limitations": ["This bounds 0.5-s CPD4 temporal sensitivity for one seed and one start only.",
                              "It does not establish spatial convergence, population release, or physical validation."],
              "next": "Preflight CPD6 field/geometry compatibility before any matched CPD4/CPD6 response run."}
    job.verify(design)
    OUT.mkdir(parents=True, exist_ok=False)
    api.write(OUT / "results.json", result)
    api.write(OUT / "completion.json", {"passed": passed, "qualified": passed,
                                         "results_sha256": api.sha(OUT / "results.json"),
                                         "artifacts": {str(OUT / "results.json"): api.sha(OUT / "results.json")}})
    print("EVALUATION", passed)
    for row in comparisons:
        print(row["shape"], row["twice_adjacent_temporal_proxy"], row["checks"])
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
