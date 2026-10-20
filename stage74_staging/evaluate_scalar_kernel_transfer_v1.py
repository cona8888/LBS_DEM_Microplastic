"""Independent hash, health, and claim-boundary audit for Stage73–74."""
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
    return record, completion, completion["results_sha256"] == sha(path)


def sources_bound(record):
    return all(Path(path).is_file() and sha(path) == expected
               for path, expected in record.get("source_hashes", {}).items())


def healthy(record):
    return bool(record["minimum_gap_m"] >= -5e-10 and
                record["max_contact_residual"] <= 1e-8 and
                record["max_force_residual"] <= 1e-8 and
                record["max_momentum_residual"] <= 1e-8 and
                record["max_reynolds"] <= 3)


def main():
    out = ROOT / "stage74_evaluations" / "independent_transfer_audit_01"
    out.mkdir(parents=True, exist_ok=False)
    profile, pc, pb = read("stage73_evaluations/seed2_local_profile_01")
    kernels, kc, kb = read("stage74_evaluations/scalar_kernel_verification_01")
    smoke, sc, sb = read("stage74_evaluations/manufactured_smoke_01")
    local, lc, lb = read("stage74_evaluations/local_episode_ab_01")
    short, tc, tb = read("stage74_evaluations/s2_short_01")
    historical, hc, hb = read("stage69_evaluations/s2_short_crossing_01")
    checks = {
        "profile_bound": bool(pb and pc["status"] == "complete_profiled" and
                              pc["profile_sha256"] == sha(ROOT / "stage73_evaluations/seed2_local_profile_01/profile.txt") and sources_bound(profile)),
        "kernels_bound_and_pass": bool(kb and kc["status"] == "complete_passed" and
                                       kernels["passed"] and sources_bound(kernels)),
        "smoke_bound_and_pass": bool(sb and sc["status"] == "complete_passed" and
                                     smoke["passed"] and len(smoke["checks"]) == 17),
        "local_ab_bound_and_pass": bool(lb and lc["status"] == "complete_passed" and
                                        local["passed"] and sources_bound(local) and
                                        healthy(local["baseline"]) and healthy(local["candidate"])),
        "short_bound_and_censored": bool(tb and tc["status"] == "complete_failed" and
                                          not short["passed"] and sources_bound(short) and
                                          short["result"]["status"] == "incomplete_budget" and
                                          healthy(short["result"])),
        "historical_bound_and_censored": bool(hb and hc["status"] == "complete_failed" and
                                                historical["result"]["status"] == "incomplete_budget" and
                                                healthy(historical["result"])),
    }
    r = short["result"]
    h = historical["result"]
    summary = {
        "evidence_audit_passed": all(checks.values()),
        "solver_transfer_passed": False,
        "checks": checks,
        "profile_runtime_s": profile["result"]["runtime_seconds"],
        "local_baseline_runtime_s": local["baseline"]["runtime_seconds"],
        "local_candidate_runtime_s": local["candidate"]["runtime_seconds"],
        "local_position_shift_m": local["shifts"]["position_m"],
        "short_target_s": short["target_s"],
        "short_achieved_s": r["time_s"],
        "short_runtime_s": r["runtime_seconds"],
        "short_retries": r["contact_solver_retries"],
        "historical_achieved_s": h["time_s"],
        "historical_runtime_s": h["runtime_seconds"],
        "historical_retries": h["contact_solver_retries"],
        "claim_boundary": "Local kernel verification and speedup only; evolving short trajectory censored. No full release or shape comparison."
    }
    path = out / "audit.json"
    path.write_text(json.dumps(summary, indent=2))
    (out / "completion.json").write_text(json.dumps({
        "status": "complete_evidence_audit_passed_transfer_failed" if summary["evidence_audit_passed"] else "complete_evidence_audit_failed",
        "audit_sha256": sha(path)}, indent=2))
    lines = [
        "# Stage73–74 numerical decision", "",
        "The evolving seed-2 profile identifies projected SOR and its tiny-vector projection/residual loop as a local cost centre; geometry is minor in that local episode. Stage74 re-expresses those two-component calculations with scalar arithmetic while preserving the contact equations and Stage50 gates.", "",
        f"The five-step local A/B check passed with a position shift of {summary['local_position_shift_m']:.3g} m and runtime {summary['local_baseline_runtime_s']:.1f} to {summary['local_candidate_runtime_s']:.1f} s. Randomized kernel comparisons, three frozen contact systems, and 17 manufactured checks also passed.", "",
        f"The original-start seed-2 crossing **did not** pass: achieved {summary['short_achieved_s']:.6f} s versus target {summary['short_target_s']:.6f} s in {summary['short_runtime_s']:.1f} s, with {summary['short_retries']} contact retries. Clearance, contact, force, momentum, and Reynolds gates remained healthy. The historical Stage69 case achieved {summary['historical_achieved_s']:.6f} s in {summary['historical_runtime_s']:.1f} s with {summary['historical_retries']} retries. Those solvers differ, so their runtimes are not a controlled speedup estimate.", "",
        "**Decision:** Reject Stage74 for trajectory promotion. Small arithmetic changes can alter the evolving retry path; local near-identity and local speedup do not establish campaign reliability. Do not infer release fraction, physical trapping, or a sphere–fibre effect. The next route should address the nonlinear contact/time-step algorithm and its many rejected steps, with independent trajectory and time-step verification before a six-case study."
    ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(summary, indent=2))
    if not summary["evidence_audit_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
