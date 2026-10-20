"""Independent immutable ledger, timestep/event gates and spatial sensitivity."""
from pathlib import Path
import numpy as np
import longer_sentinels_v1 as job
api = job.api
OUT = job.EVAL / "independent_evaluation_01"


def compare_group(records, specs, group, thresholds, event_thresholds, ledgers):
    names = group["case_ids"]
    item = dict(group)
    if not all(records[n]["result"]["status"] in ["present_at_horizon", "full_window_exit"] for n in names):
        return {**item, "passed": False, "reason": "budget-incomplete matched observation"}
    cm = job.reference.difference(records[names[0]], records[names[1]], specs[names[0]])
    mf = job.reference.difference(records[names[1]], records[names[2]], specs[names[0]])
    def trend(key, maximum):
        return mf[key] <= thresholds["refinement_trend_multiplier_max"] * cm[key] + thresholds["trend_roundoff_floor"] or max(cm[key], mf[key]) <= thresholds["trend_waiver_fraction_of_budget"] * maximum
    results = [records[n]["result"] for n in names]
    dwell_flags = [r["persistent_contact_observed"] for r in results]
    dwell_times = [r["first_contact_dwell_time_s"] for r in results]
    dwell_difference = abs(dwell_times[1] - dwell_times[2]) if all(dwell_flags) else None
    checks = {"same_terminal_label": len({r["status"] for r in results}) == 1,
        "position_error": mf["position_difference_over_b"] <= thresholds["fine_medium_position_over_b_max"],
        "axis_error": mf["apolar_axis_angle_rad"] <= thresholds["fine_medium_axis_angle_rad_max"],
        "velocity_error": mf["translational_velocity_relative_difference"] <= thresholds["fine_medium_translational_velocity_relative_max"],
        "position_trend": trend("position_difference_over_b", thresholds["fine_medium_position_over_b_max"]),
        "axis_trend": trend("apolar_axis_angle_rad", thresholds["fine_medium_axis_angle_rad_max"]),
        "terminal_time_error": mf["time_difference_s"] <= thresholds["exit_time_difference_s_max"],
        "same_dwell_observation": len(set(dwell_flags)) == 1,
        "dwell_time_error": not any(dwell_flags) or (dwell_difference is not None and dwell_difference <= event_thresholds["first_dwell_time_difference_max_s"]),
        "finest_accepted_interval": ledgers[names[-1]]["max_accepted_interval_s"] <= event_thresholds["finest_max_accepted_interval_s"] + 1e-12,
        "all_health": all(ledgers[n]["health_passed"] for n in names)}
    return {**item, "coarse_medium": cm, "medium_fine": mf, "dwell_flags": dwell_flags, "first_dwell_times_s": dwell_times,
            "medium_fine_dwell_time_difference_s": dwell_difference, "checks": checks, "passed": bool(all(checks.values()))}


def main():
    d = api.read(job.DESIGN)
    job.verify(d)
    api.require(not OUT.exists(), "immutable evaluation exists")
    done = api.read(job.RUN / "completion.json")
    manifest = api.read(job.RUN / "manifest.json")
    api.require(done["design_sha256"] == manifest["design_sha256"] == api.sha(job.DESIGN), "design drift")
    api.require(done["manifest_sha256"] == api.sha(job.RUN / "manifest.json"), "manifest drift")
    api.require(manifest["preflight_sha256"] == api.sha(job.PREFLIGHT) and api.read(job.PREFLIGHT)["passed"], "preflight drift")
    specs = {s["case_id"]: s for s in d["cases"]}
    api.require(manifest["case_order"] == list(specs) and set(done["records"]) == set(specs), "case set/order drift")
    failures = list(job.RUN.rglob("failure.json"))
    stderr = [str(p) for p in job.RUN.glob("*.stderr.txt") if p.stat().st_size]
    api.require(not failures and not stderr, "failure marker/nonempty stderr")
    records = {}
    ledger = {}
    artifact_hashes = {str(job.RUN / "completion.json"): api.sha(job.RUN / "completion.json")}
    for name, spec in specs.items():
        chain = done["records"][name]
        limit = d["budget"]["max_sphere_segments" if spec["shape"] == api.SHAPES[0] else "max_fibre_segments"]
        api.require(0 < len(chain) <= limit, "segment count outside contract")
        previous = None
        previous_sha = None
        runtime = 0.
        dense = []
        segment_health = []
        trap = spec["config"]["trap"]
        monitor = api.frozen.core.trap_event_v2.TrapMonitor(spec["config"]["target_mean_interstitial_velocity_m_s"], spec["config"]["prolate_semiaxes_m"][1], trap["dwell_time_s"], speed_ratio=trap["speed_ratio"], drift_over_minor_radius=trap["drift_over_minor_radius"])
        clock = 0.
        for index, entry in enumerate(chain, 1):
            path = Path(entry["path"])
            api.require(path == job.RUN / name / f"segment_{index:02d}/record.json", "record outside bound path")
            completion = api.read(path.parent / "completion.json")
            launch = api.read(path.parent / "launch.json")
            record = api.read(path)
            api.require(entry["sha256"] == completion["record_sha256"] == api.sha(path), "record hash drift")
            api.require(completion["launch_sha256"] == api.sha(path.parent / "launch.json"), "launch hash drift")
            api.require(launch["case_id"] == record["case_id"] == name and launch["segment"] == record["segment"] == index, "identity drift")
            api.require(launch["design_sha256"] == record["design_sha256"] == api.sha(job.DESIGN), "case design drift")
            api.require(launch["prior_record_sha256"] == record["prior_record_sha256"] == previous_sha, "chain drift")
            if previous is not None:
                api.require(previous["status"] == "incomplete_budget", "terminal case resumed")
                api.require(record["checkpoint_input_sha256"] == api.digest(previous["checkpoint"]), "input checkpoint drift")
            else:
                api.require(record["checkpoint_input_sha256"] is None, "unexpected warm start")
            r = record["result"]
            api.require(completion["status"] == r["status"], "status drift")
            cp = r.get("checkpoint")
            if r["status"] == "incomplete_budget":
                api.require(cp and cp["contract"] == job.contracts.expected_contract(spec, job.binding(d, name)) and api.digest(cp["state"]) == cp["state_sha256"], "checkpoint integrity drift")
                api.require(cp["state"]["t"] == r["time_s"] and cp["state"]["steps"] == r["steps"], "checkpoint/result drift")
                api.require(cp["state"]["x"] == r["position_m"] and cp["state"]["p"] == r["orientation"] and cp["state"]["q"] == r["velocity_generalized"], "checkpoint pose drift")
            health = job.reference.independent_health(r, spec)
            segment_health.append(health)
            rows_path = path.parent / "accepted_intervals.json"
            api.require(api.sha(rows_path) == record["accepted_intervals_sha256"], "dense observation drift")
            rows = api.read(rows_path)
            api.require(len(rows) == r["steps"] - (0 if previous is None else previous["steps"]), "missing accepted intervals")
            for row in rows:
                api.require(row["dt_s"] > 0 and np.isfinite(row["dt_s"]), "invalid interval")
                clock += row["dt_s"]
                api.require(abs(clock - row["time_s"]) < 1e-12, "dense clock drift")
                api.require(np.isfinite(row["position_m"] + row["orientation"] + row["velocity_generalized"]).all() and abs(np.linalg.norm(row["orientation"]) - 1) < 1e-10, "invalid dense state")
                replay = monitor.update(row["dt_s"], row["position_m"], row["velocity_generalized"], row["active_contact_ids"], row["supported_bearing_ids"])
                api.require(replay == row["dwell"], "dwell observer replay drift")
            api.require(abs(clock - r["time_s"]) < 1e-12, "result clock drift")
            if rows:
                api.require(rows[-1]["position_m"] == r["position_m"] and np.allclose(rows[-1]["orientation"], r["orientation"], rtol=0, atol=1e-12), "dense final state drift")
            dense.extend(rows)
            runtime += r["runtime_seconds"]
            previous = r
            previous_sha = api.sha(path)
            for p in [path, rows_path, path.parent / "launch.json", path.parent / "completion.json"]:
                artifact_hashes[str(p)] = api.sha(p)
        last = previous
        first_events = [row["time_s"] for row in dense if row["dwell"]["persistent_contact_observed"]]
        api.require(bool(first_events) == last["persistent_contact_observed"], "dwell flag drift")
        if first_events:
            api.require(abs(first_events[0] - last["first_contact_dwell_time_s"]) < 1e-12, "dwell time drift")
        records[name] = {"result": last}
        ledger[name] = {"case_id": name, "status": last["status"], "time_s": last["time_s"], "pv": last["time_s"] * spec["field_metadata"]["pv_per_second"],
            "health_passed": all(h["passed"] for h in segment_health), "segment_health": segment_health,
            "segments": len(chain), "integrator_runtime_s": runtime, "steps": last["steps"], "rejected_steps": last["rejected"],
            "contact_steps": last["contact_steps"], "dense_interval_count": len(dense),
            "supported_contact_duration_s": sum(r["dt_s"] for r in dense if r["supported_bearing_ids"]),
            "max_accepted_interval_s": max([r["dt_s"] for r in dense], default=0.),
            "persistent_contact_observed": last["persistent_contact_observed"], "first_contact_dwell_time_s": last["first_contact_dwell_time_s"],
            "max_dwell_elapsed_s": max([r["dwell"]["elapsed_s"] for r in dense], default=0.),
            "max_particle_Re": last["max_reynolds"], "final_record_sha256": previous_sha}
    groups = [compare_group(records, specs, g, d["acceptance"], d["event_acceptance"], ledger) for g in d["groups"]]
    spatial = []
    for shape in api.SHAPES:
        names = [next(g["case_ids"][-1] for g in d["groups"] if g["seed"] == 2 and g["cpd"] == cpd and g["shape"] == shape) for cpd in [2, 4]]
        row = {"shape": shape, "case_ids": names, "matched_complete_query": all(records[n]["result"]["status"] == "present_at_horizon" for n in names)}
        if row["matched_complete_query"]:
            row.update(job.reference.difference(records[names[0]], records[names[1]], specs[names[0]]))
        row["claim_boundary"] = "Each direct field retains its achieved speed; not pure equal-speed spatial error, not a pass/fail transport resolution certificate."
        spatial.append(row)
    passed = all(g["passed"] for g in groups) and all(r["health_passed"] for r in ledger.values())
    result = {"passed": passed, "status": "longer_prefix_verified_full_trajectory_gate_open" if passed else "longer_prefix_accuracy_failed_or_incomplete_preserved",
        "workflow_complete": True, "case_ledger": ledger, "three_level_groups": groups, "spatial_sensitivity": spatial,
        "complete_queries": sum(r["status"] in ["present_at_horizon", "full_window_exit"] for r in ledger.values()),
        "passing_triplets": sum(g["passed"] for g in groups), "integration_cost_s": sum(r["integrator_runtime_s"] for r in ledger.values()),
        "run_wall_s": done["wall_s"], "independent_lineage_and_chain_verified": True, "failure_markers": [], "nonempty_stderr": [],
        "population_release_measured": False, "population_campaign_authorized": False, "full_trajectory_cost_extrapolated": False,
        "interpretation": d["claim_boundary"], "artifact_hashes": artifact_hashes, "design_sha256": api.sha(job.DESIGN), "evaluator_sha256": api.sha(__file__)}
    job.verify(d)
    OUT.mkdir(parents=True)
    api.write(OUT / "results.json", result)
    api.write(OUT / "completion.json", {"results_sha256": api.sha(OUT / "results.json"), "passed": passed})
    print(result["status"], "complete", result["complete_queries"], "/18; triplets", result["passing_triplets"], "/6; cost", result["integration_cost_s"])
    for g in groups:
        print(g)
    print("SPATIAL", spatial)
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
