"""Independent audit of Stage76's bounded long-transfer outcome."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    out = ROOT / "stage77_evaluations" / "sweep_transfer_decision_01"
    out.mkdir(parents=True, exist_ok=False)
    short_dir = ROOT / "stage76_evaluations" / "s2_long_transfer_01"
    path = short_dir / "results.json"
    record = json.loads(path.read_text())
    completion = json.loads((short_dir / "completion.json").read_text())
    result = record["result"]
    local_dir = ROOT / "stage76_evaluations" / "independent_audit_01"
    local_path = local_dir / "audit.json"
    local = json.loads(local_path.read_text())
    local_completion = json.loads((local_dir / "completion.json").read_text())
    checks = {
        "long_result_hash_bound": sha(path) == completion["results_sha256"],
        "long_sources_bound": all(Path(p).is_file() and sha(p) == h
                                  for p, h in record["source_hashes"].items()),
        "local_audit_bound": sha(local_path) == local_completion["audit_sha256"] and local["evidence_audit_passed"],
        "long_censored": completion["status"] == "complete_failed" and not record["passed"] and result["status"] == "incomplete_budget",
        "progress_past_old_failure": result["time_s"] > 2.37162479172013,
        "target_not_reached": result["time_s"] < record["target_s"],
        "clearance": result["minimum_gap_m"] >= -5e-10,
        "contact": result["max_contact_residual"] <= 1e-8,
        "force": result["max_force_residual"] <= 1e-8,
        "momentum": result["max_momentum_residual"] <= 1e-8,
        "reynolds": result["max_reynolds"] <= 3,
        "sweep_accounting": result["fail_fast_sweep_stats"]["calls"] == (
            result["fail_fast_sweep_stats"]["endpoint_early_rejects"] +
            result["fail_fast_sweep_stats"]["full_evaluations"]),
    }
    checks = {k: bool(v) for k, v in checks.items()}
    audit = {
        "evidence_audit_passed": all(checks.values()),
        "long_transfer_passed": False,
        "checks": checks,
        "achieved_s": result["time_s"], "target_s": record["target_s"],
        "runtime_s": result["runtime_seconds"],
        "accepted_steps": result["steps"], "rejected_steps": result["rejected"],
        "endpoint_early_rejects": result["fail_fast_sweep_stats"]["endpoint_early_rejects"],
        "contact_solver_retries": result["contact_solver_retries"],
        "total_contact_iterations": result["total_contact_iterations"],
        "claim_boundary": "Stage76 preserves local tested trajectory but long transfer is budget-censored; no release or trapping inference."
    }
    audit_path = out / "audit.json"
    audit_path.write_text(json.dumps(audit, indent=2))
    (out / "completion.json").write_text(json.dumps({
        "status": "complete_evidence_audit_passed_transfer_failed" if audit["evidence_audit_passed"] else "complete_audit_failed",
        "audit_sha256": sha(audit_path)}, indent=2))
    report = (
        "# Stage76 long-transfer decision\n\n"
        "Stage76's exact-endpoint fail-fast sweep passed the 45 frozen-pose checks, "
        "17 manufactured checks, and an all-fields-identical 0.3 s rejection-heavy A/B trajectory. "
        "These are local numerical-verification results, not release measurements.\n\n"
        f"The original-start seed-2 long transfer reached {audit['achieved_s']:.6f} s "
        f"against a {audit['target_s']:.6f} s target in {audit['runtime_s']:.1f} s: "
        "`incomplete_budget`. The record and source hashes bind, and clearance, "
        "contact, force, momentum, and Reynolds gates passed up to censoring. "
        f"It accepted {audit['accepted_steps']} steps and rejected {audit['rejected_steps']}; "
        f"{audit['endpoint_early_rejects']} rejected sweeps returned after exact endpoint proof. "
        f"The contact solver still required {audit['total_contact_iterations']:,} iterations.\n\n"
        "Decision: retain Stage76 only as a locally verified optimization; do not "
        "promote it to the six-case release study. The early geometry cost was reduced, "
        "but late nonlinear contact/retry behavior and time-step convergence remain "
        "unresolved. No physical trapping, release fraction, or sphere–fibre effect is supported.\n")
    (out / "REPORT.md").write_text(report)
    print(json.dumps(audit, indent=2))
    if not audit["evidence_audit_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
