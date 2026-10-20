"""Independent hash, accounting and claim-boundary audit for Stage75–76."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(relative):
    folder = ROOT / relative
    path = folder / "results.json"
    record = json.loads(path.read_text())
    completion = json.loads((folder / "completion.json").read_text())
    bound = sha(path) == completion["results_sha256"]
    bound &= all(Path(p).is_file() and sha(p) == h
                 for p, h in record.get("source_hashes", {}).items())
    return record, completion["status"], bound


def main():
    out = ROOT / "stage76_evaluations" / "independent_audit_01"
    out.mkdir(parents=True, exist_ok=False)
    diagnosis, ds, db = read("stage75_evaluations/s2_rejection_diagnostic_01")
    primitive, ps, pb = read("stage76_evaluations/sweep_primitive_01")
    early, es, eb = read("stage76_evaluations/original_start_ab_01")
    episode, rs, rb = read("stage76_evaluations/rejection_episode_ab_01")
    smoke, ss, sb = read("stage76_evaluations/manufactured_smoke_01")
    fast = episode["candidate"]["fail_fast_sweep_stats"]
    checks = {
        "diagnosis_bound": bool(db and ds == "complete_passed" and diagnosis["passed"]),
        "diagnosis_accounted": bool(diagnosis["result"]["rejected"] == diagnosis["swept_clearance_rejects"] == 538 and diagnosis["displacement_rejects"] == 0 and not diagnosis["runtime_failures"]),
        "primitive_bound": bool(pb and ps == "complete_passed" and primitive["passed"] and len(primitive["rows"]) == 45),
        "zero_reject_ab_bound": bool(eb and es == "complete_failed" and not early["passed"] and early["checks"]["all_nonruntime_fields_equal"] and early["baseline"]["rejected"] == 0),
        "rejection_ab_bound": bool(rb and rs == "complete_passed" and episode["passed"] and episode["checks"]["all_nonruntime_fields_equal"] and fast["endpoint_early_rejects"] == episode["candidate"]["rejected"]),
        "smoke_bound": bool(sb and ss == "complete_passed" and smoke["passed"] and len(smoke["checks"]) == 17),
    }
    audit = {
        "evidence_audit_passed": all(checks.values()),
        "local_numerical_gate_passed": bool(primitive["passed"] and episode["passed"] and smoke["passed"]),
        "full_release_gate_passed": False,
        "checks": checks,
        "diagnostic_sweep_runtime_s": diagnosis["swept_elapsed_s"],
        "diagnostic_contact_runtime_s": diagnosis["inertial_elapsed_s"],
        "diagnostic_clearance_rejects": diagnosis["swept_clearance_rejects"],
        "ab_accepted_steps": episode["candidate"]["steps"],
        "ab_rejected_steps": episode["candidate"]["rejected"],
        "ab_early_endpoint_rejects": fast["endpoint_early_rejects"],
        "ab_baseline_runtime_s": episode["baseline"]["runtime_seconds"],
        "ab_candidate_runtime_s": episode["candidate"]["runtime_seconds"],
        "claim_boundary": "Local numerical optimization only; no long-trajectory, release, trapping, or morphology claim."
    }
    path = out / "audit.json"
    path.write_text(json.dumps(audit, indent=2))
    (out / "completion.json").write_text(json.dumps({
        "status": "complete_local_numerical_pass_full_release_unverified" if audit["evidence_audit_passed"] else "complete_audit_failed",
        "audit_sha256": sha(path)}, indent=2))
    report = (
        "# Stage75–76 algorithm audit\n\n"
        "The original-start diagnostic found 538 rejected proposals, all from exact swept clearance. "
        "Sweep evaluation used 28.46 of 30.09 seconds; contact calls used 1.05 seconds. "
        "This is an early-trajectory bottleneck only: the Stage73 near-failure episode was contact-dominated.\n\n"
        "Stage76 stops exact sweep search once an endpoint or interval minimum proves a clearance violation. "
        "Rejected gaps are not recorded; accepted sweeps retain the complete original search.\n\n"
        f"The 0.3 s A/B run matched every non-runtime field ({audit['ab_accepted_steps']} accepted, "
        f"{audit['ab_rejected_steps']} rejected). All {audit['ab_early_endpoint_rejects']} rejected sweeps "
        f"used exact endpoint proof. Runtime was {audit['ab_baseline_runtime_s']:.2f} s versus "
        f"{audit['ab_candidate_runtime_s']:.2f} s. Forty-five frozen-pose checks and 17 manufactured checks passed. "
        "The 0.05 s A/B run matched exactly but had no rejections, so it was not a performance test.\n\n"
        "Decision: Stage76 is locally code-verified, not promoted to the release study. "
        "Long-trajectory transfer, late contact/retry behavior, and time-step convergence remain unverified. "
        "Do not infer release fraction or physical trapping. Preserve all failed and censored evidence.\n")
    (out / "REPORT.md").write_text(report)
    print(json.dumps(audit, indent=2))
    if not audit["evidence_audit_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
