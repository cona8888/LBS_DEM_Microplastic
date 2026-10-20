"""Audit every attempted segment and explicitly account for unrun frozen cases.

This is a post-failure read-only audit, not a replacement acceptance protocol.
It neither resumes transport nor changes the frozen design or pass criteria.
"""
from pathlib import Path
import numpy as np
import longer_sentinels_v1 as job
api = job.api
OUT = job.EVAL / "failure_audit_01"


def main():
    d = api.read(job.DESIGN)
    job.verify(d)
    api.require(not OUT.exists(), "immutable failure audit exists")
    stopped = api.read(job.RUN / "failure.json")
    manifest = api.read(job.RUN / "manifest.json")
    api.require(not (job.RUN / "completion.json").exists(), "unexpected complete run")
    api.require(manifest["design_sha256"] == api.sha(job.DESIGN), "design drift")
    api.require(manifest["case_order"] == [s["case_id"] for s in d["cases"]], "order drift")
    api.require(manifest["preflight_sha256"] == api.sha(job.PREFLIGHT), "preflight drift")
    api.require(api.read(job.PREFLIGHT)["raw_sha256"] == api.sha(job.PREFLIGHT.parent / "raw_equivalence.json"), "preflight evidence drift")
    ledger = []
    artifacts = {}
    all_healthy = True
    segment_count = 0
    failure_detail = None
    for spec in d["cases"]:
        name = spec["case_id"]
        entries = stopped["records"].get(name, [])
        if not entries:
            api.require(not (job.RUN / name).exists(), "unaccounted attempted case")
            ledger.append({"case_id": name, "status": "not_run_after_fail_closed_stop", "segments": 0, "runtime_s": 0., "qualified": False})
            continue
        prior = None
        prior_sha = None
        clock = 0.
        runtime = 0.
        dense = []
        health_rows = []
        c = spec["config"]
        a, b, _ = c["prolate_semiaxes_m"]
        trap = c["trap"]
        monitor = api.frozen.core.trap_event_v2.TrapMonitor(c["target_mean_interstitial_velocity_m_s"], b, trap["dwell_time_s"], speed_ratio=trap["speed_ratio"], drift_over_minor_radius=trap["drift_over_minor_radius"])
        for index, entry in enumerate(entries, 1):
            path = Path(entry["path"])
            api.require(path == job.RUN / name / f"segment_{index:02d}/record.json", "out-of-scope record")
            record = api.read(path)
            completion = api.read(path.parent / "completion.json")
            launch = api.read(path.parent / "launch.json")
            api.require(api.sha(path) == entry["sha256"] == completion["record_sha256"], "record drift")
            api.require(api.sha(path.parent / "launch.json") == completion["launch_sha256"], "launch drift")
            api.require(record["case_id"] == launch["case_id"] == name and record["segment"] == launch["segment"] == index, "identity drift")
            api.require(record["design_sha256"] == launch["design_sha256"] == api.sha(job.DESIGN), "case/design drift")
            api.require(record["prior_record_sha256"] == launch["prior_record_sha256"] == prior_sha, "chain drift")
            if prior is None:
                api.require(record["checkpoint_input_sha256"] is None, "unexpected warm start")
            else:
                api.require(prior["status"] == "incomplete_budget" and record["checkpoint_input_sha256"] == api.digest(prior["checkpoint"]), "invalid continuation")
            r = record["result"]
            api.require(r["status"] == completion["status"], "status drift")
            cp = r["checkpoint"]
            if r["status"] == "incomplete_budget":
                api.require(cp is not None and cp["state_sha256"] == api.digest(cp["state"]) and cp["contract"] == job.contracts.expected_contract(spec, job.binding(d, name)), "checkpoint drift")
                api.require(cp["state"]["t"] == r["time_s"] and cp["state"]["x"] == r["position_m"] and cp["state"]["p"] == r["orientation"] and cp["state"]["q"] == r["velocity_generalized"], "checkpoint/result drift")
            rows_path = path.parent / "accepted_intervals.json"
            api.require(api.sha(rows_path) == record["accepted_intervals_sha256"], "telemetry drift")
            rows = api.read(rows_path)
            api.require(len(rows) == r["steps"] - (0 if prior is None else prior["steps"]), "missing accepted steps")
            for row in rows:
                api.require(row["dt_s"] > 0 and np.isfinite(row["position_m"] + row["orientation"] + row["velocity_generalized"] + [row["dt_s"]]).all(), "invalid interval state")
                clock += row["dt_s"]
                api.require(abs(clock - row["time_s"]) < 1e-12 and abs(np.linalg.norm(row["orientation"]) - 1) < 1e-10, "time/axis drift")
                replay = monitor.update(row["dt_s"], row["position_m"], row["velocity_generalized"], row["active_contact_ids"], row["supported_bearing_ids"])
                api.require(replay == row["dwell"], "dwell replay drift")
            api.require(abs(clock - r["time_s"]) < 1e-12, "dense/result clock mismatch")
            if rows:
                api.require(rows[-1]["position_m"] == r["position_m"] and np.allclose(rows[-1]["orientation"], r["orientation"], rtol=0, atol=1e-12), "dense/result pose mismatch")
            h = job.reference.independent_health(r, spec)
            health_rows.append(h)
            all_healthy = all_healthy and h["passed"]
            runtime += r["runtime_seconds"]
            segment_count += 1
            dense.extend(rows)
            if r["status"] == "numerical_failure":
                marker = api.read(path.parent / "failure.json")
                api.require(marker["status"] == r["status"] and marker["reason"] == r["reason"], "failure marker mismatch")
                with np.load(spec["field_metadata"]["geometry"]["path"]) as g:
                    geometry = api.frozen.h.geometry_exact_v1.GrainGeometry(g["sand_centres_m"], g["sand_radii_m"], float(g["cell_length_m"][0]))
                contacts = geometry.contacts(r["position_m"], r["orientation"], a, b, 1e-5*b)
                failure_detail = {"case_id": name, "segment": index, "failure_reason": r["reason"], "last_accepted_time_s": r["time_s"],
                    "remaining_horizon_s": spec["horizon_s"] - r["time_s"], "last_reaction_count": r["last_reaction_count"],
                    "exact_final_contacts": [{"grain_id": int(v[0]), "gap_m": float(v[1])} for v in contacts],
                    "last_translational_speed_m_s": float(np.linalg.norm(r["velocity_generalized"][:3])),
                    "segment_accepted_steps": len(rows), "segment_rejected_steps": r["rejected"] - (0 if prior is None else prior["rejected"]),
                    "segment_contact_solver_retries": r["contact_solver_retries"] - (0 if prior is None else prior["contact_solver_retries"]),
                    "segment_runtime_s": r["runtime_seconds"], "total_rejected_steps": r["rejected"],
                    "total_contact_iterations": r["total_contact_iterations"], "recovery_diagnostics": r["nullspace_rescue"],
                    "dwell_elapsed_s": r["trap_state"]["elapsed_s"], "required_dwell_s": trap["dwell_time_s"],
                    "interpretation": "The generic terminal reason means all adaptive retries were exhausted. It does not identify whether the last rejected candidate failed contact solve, motion caps or swept clearance. Last accepted state remains admissible; no successful step, retention or export can be inferred.",
                    "next_hypotheses_not_proven": ["Three-contact solve conditioning/recovery failure", "Short remaining-horizon step interaction", "Swept-clearance rejection versus solver rejection must be distinguished by local instrumentation"]}
            for p in path.parent.iterdir():
                if p.is_file():
                    artifacts[str(p)] = api.sha(p)
            prior = r
            prior_sha = api.sha(path)
        first_dwell = [row["time_s"] for row in dense if row["dwell"]["persistent_contact_observed"]]
        api.require(bool(first_dwell) == prior["persistent_contact_observed"], "dwell event drift")
        if first_dwell:
            api.require(abs(first_dwell[0] - prior["first_contact_dwell_time_s"]) < 1e-12, "first dwell time drift")
        ledger.append({"case_id": name, "status": prior["status"], "segments": len(entries), "time_s": prior["time_s"], "runtime_s": runtime,
            "qualified": all(h["passed"] for h in health_rows) and prior["status"] in ["present_at_horizon", "full_window_exit"],
            "last_accepted_state_health_passed": all(h["passed"] for h in health_rows), "segment_health": health_rows,
            "steps": prior["steps"], "rejected_steps": prior["rejected"], "contact_steps": prior["contact_steps"],
            "supported_contact_duration_s": sum(row["dt_s"] for row in dense if row["supported_bearing_ids"]),
            "max_accepted_interval_s": max([row["dt_s"] for row in dense], default=0.),
            "max_finite_dwell_elapsed_s": max([row["dwell"]["elapsed_s"] for row in dense], default=0.),
            "persistent_contact_observed": prior["persistent_contact_observed"], "pv": prior["time_s"] * spec["field_metadata"]["pv_per_second"]})
    observed_paths = {str(p) for p in job.RUN.rglob("record.json")}
    bound_paths = {e["path"] for entries in stopped["records"].values() for e in entries}
    api.require(observed_paths == bound_paths, "unindexed raw records")
    counts = {status: sum(row["status"] == status for row in ledger) for status in sorted({row["status"] for row in ledger})}
    api.require(sum(counts.values()) == 18 and counts.get("numerical_failure") == 1, "unexpected stop accounting")
    stderr = [str(p) for p in job.RUN.glob("*.stderr.txt") if p.stat().st_size]
    api.require(not stderr, "unexpected worker exception")
    for p in job.RUN.iterdir():
        if p.is_file():
            artifacts[str(p)] = api.sha(p)
    groups = [{**g, "passed": False, "reason": "No complete three-level observation; numerical failure, budget incomplete or not executed."} for g in d["groups"]]
    result = {"audit_passed": True, "scientific_numerical_gate_passed": False, "status": "fail_closed_adaptive_advance_failure_preserved",
        "case_accounting": counts, "ledger": ledger, "three_level_groups": groups, "all_last_accepted_states_healthy": all_healthy,
        "attempted_segments": segment_count, "total_integrator_runtime_s": sum(row["runtime_s"] for row in ledger),
        "failure_detail": failure_detail, "nonempty_worker_stderr": stderr, "record_chain_and_lineage_verified": True,
        "same_time_spatial_or_shape_comparison_available": False, "population_campaign_authorized": False,
        "population_release_measured": False, "irreversible_retention_inferred": False,
        "design_sha256": api.sha(job.DESIGN), "auditor_sha256": api.sha(__file__), "artifact_hashes": artifacts,
        "next": "Freeze a local non-advancing rejected-step diagnostic at the saved three-contact episode, separately recording solver, step-cap and swept-gap rejection causes. Compare reference/pruned geometry and inspect remaining-horizon conditioning. No automatic rerun, tolerance relaxation or population dispatch."}
    job.verify(d)
    OUT.mkdir(parents=True)
    api.write(OUT / "results.json", result)
    api.write(OUT / "completion.json", {"audit_passed": True, "scientific_gate_passed": False, "results_sha256": api.sha(OUT / "results.json")})
    print("COUNTS", counts, "INTEGRATOR S", result["total_integrator_runtime_s"])
    print("FAILURE", failure_detail)


if __name__ == "__main__":
    main()
