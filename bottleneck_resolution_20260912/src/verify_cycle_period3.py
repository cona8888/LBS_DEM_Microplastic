"""Second captured cycle: exact archived prefix plus independent cold repeat."""
import argparse
import json
from pathlib import Path
import numpy as np
import verify_inertial_cycle_guard as verification


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    trace = verification.ROOT / "bottleneck_resolution_20260912/evidence/crossing_blas_01/s2_blas_l1_attempts.jsonl"
    inputs, record, hashes = verification.rebuilt_capture(trace, 2, 5720)
    verification.compiled_portfolio()
    before = verification.sources()
    attempts = []
    for _ in range(2):
        portfolio = verification.compiled_portfolio()
        solver = portfolio.solve_recovery if record["recovery_mode"] else portfolio.solve_default
        attempts.append(verification.run_step(verification.candidate, inputs, solver, True))
    archived = record["inertial_diagnostics"]["contact_solves"]
    checks = {}
    for index, answer in enumerate(attempts):
        rows = answer["diagnostics"]["contact_solves"]
        cycle = answer["diagnostics"].get("cycle_guard", {})
        checks[f"repeat_{index}_period3_exact_rejection"] = (answer["status"] == "rejected"
            and answer["reason"] == "inertial/contact fixed point did not converge"
            and len(rows) == 7 and cycle.get("cycle_length") == 3)
        checks[f"repeat_{index}_exact_archived_prefix"] = all(
            np.array_equal(row["updated_velocity_generalized"], old["updated_velocity_generalized"])
            and row["fixed_point_residual"] == old["fixed_point_residual"]
            for row,old in zip(rows, archived))
    checks["independent_cold_replays_identical_cycle"] = (
        attempts[0]["diagnostics"]["cycle_guard"] == attempts[1]["diagnostics"]["cycle_guard"])
    after = verification.sources()
    checks["sources_stable"] = all(after.get(k) == v for k,v in before.items())
    checks = {k: bool(v) for k,v in checks.items()}
    payload = {"passed": all(checks.values()), "checks": checks, "attempts": attempts,
        "input_hashes": hashes, "source_hashes_before": before, "source_hashes": after,
        "scope": "two independent cold replays versus archived physical-step prefix; no 80-step reference rerun"}
    (output / "results.json").write_text(json.dumps(verification.plain(payload), indent=2, allow_nan=False))
    (output / "completion.json").write_text(json.dumps({"status": "complete_passed" if payload["passed"] else "complete_failed",
        "results_sha256": verification.sha(output / "results.json")}))
    print(json.dumps({"passed": payload["passed"], "checks": checks,
        "wall_seconds": [row["wall_seconds"] for row in attempts]}, indent=2))
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
