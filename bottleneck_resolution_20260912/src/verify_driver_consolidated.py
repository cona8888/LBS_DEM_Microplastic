"""Bounded smoke, corrected event, and full-step diagnostics verification."""
import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path
import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "algorithm_review_20260912" / "src"),
                str(ROOT / "stage41_staging")]
import driver_consolidated as driver
import inertial_consolidated as inertial
import portfolio_explicit as portfolio
import verify_trajectory_optimized_v1 as smoke
import verify_events_v1 as events


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes():
    result = {}
    for module in list(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if path and Path(path).suffix == ".py" and Path(path).resolve().is_relative_to(ROOT):
            result[str(Path(path).resolve())] = sha(path)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    initial_hashes = source_hashes()
    original_argv = sys.argv[:]
    smoke.candidate = driver
    sys.argv = [__file__, "--output", str(output / "smoke")]
    smoke.main()
    events.trajectory = driver
    sys.argv = [__file__, "--output", str(output / "events")]
    events.main()
    sys.argv = original_argv

    records = []
    original_prepared = inertial.stage41._solve_prepared
    original_recovery = portfolio.stage70._recovery
    count = 0

    def fail_once(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 1:
            raise RuntimeError("inertial/contact fixed point did not converge")
        return portfolio.stage53._solve(*args, **kwargs)

    model = driver.make_contact_model(default_solver=fail_once)
    common = dict(a=5e-5, b=5e-5, viscosity=.001002, particle_density=1380.,
        fluid_density=998.2, gravity=[0,0,0], friction=0., outlet=.01, horizon=.001,
        added_mass_fraction=1., max_dt=.001, displacement_fraction=.1,
        relaxation_fraction=.5)
    result = driver.integrate(smoke.Field([.001,0,0]), smoke.Empty(), [0,0,0],
        [1,0,0], np.zeros(6), contact_model=model, attempt_observer=records.append,
        capture_step_inputs=True, capture_prepared_inputs=True, **common)
    checks = {"fixed_point_failure_retried": result["status"] == "present_at_horizon"
        and result["contact_solver_retries"] == 1,
        "failed_physical_attempt_recorded": records[0]["reason"] == "contact_rejection"
        and records[0]["detail"] == "inertial/contact fixed point did not converge",
        "retry_halves_actual_dt": records[1]["dt_s"] == records[0]["dt_s"] / 2
        and records[1]["step_inputs"]["dt"] == records[1]["dt_s"],
        "recovery_enabled_on_retry": records[1]["recovery_mode"] is True,
        "all_physical_attempts_accounted": len(records) == result["steps"] + result["rejected"]
        == result["attempt_diagnostics"]["physical_step_attempts"],
        "failed_inner_solve_cost_recorded": records[0]["inertial_diagnostics"]["contact_solves"][0]["status"] == "rejected"
        and records[0]["inertial_diagnostics"]["contact_solves"][0]["wall_seconds"] >= 0.,
        "historical_bindings_unchanged": inertial.stage41._solve_prepared is original_prepared
        and portfolio.stage70._recovery == original_recovery}
    accepted = next(row for row in records if row["reason"] == "accepted")
    rebuilt, health = inertial.inertial_contact_step(**accepted["step_inputs"],
                                                   prepared_solver=portfolio.stage53._solve)
    checks["full_physical_step_replay_exact"] = np.array_equal(rebuilt, accepted["candidate_velocity_generalized"])
    checks["prepared_snapshot_matches_dt"] = all(
        row["prepared_inputs"]["dt"] == accepted["dt_s"]
        for row in accepted["inertial_diagnostics"]["contact_solves"])
    second_model = driver.make_contact_model()
    checks["portfolio_counters_are_local"] = second_model.stats()["portfolio"] == {}
    class CountingSolver:
        def __init__(self):
            self.iterations = 0
        def stats(self):
            return {"iterations": self.iterations}
        def __call__(self, *args, **kwargs):
            self.iterations += 7
            error = RuntimeError("manufactured rejection")
            error.diagnostics = {"completed_iterations": 7}
            raise error
    counted = CountingSolver()
    counted_portfolio = portfolio.Portfolio(default_solver=counted)
    try:
        counted_portfolio.solve_default(np.zeros(6), np.eye(6), np.empty((0,6)),
                                       np.empty(0), .001, 0., 1e-10, 25000)
    except RuntimeError:
        pass
    failed = counted_portfolio.last_solve_diagnostics[-1]
    checks["failed_primitive_work_delta_recorded"] = failed["work_delta"]["iterations"] == 7
    checks["exception_diagnostics_retained"] = failed["exception_diagnostics"]["diagnostics"]["completed_iterations"] == 7
    checks["fixed_point_residual_and_velocity_recorded"] = all(
        "fixed_point_residual" in row and "updated_velocity_generalized" in row
        for row in accepted["inertial_diagnostics"]["contact_solves"])

    pristine = driver.integrate(smoke.Field([.001,0,0]), smoke.Empty(), [0,0,0],
                               [1,0,0], np.zeros(6), **common)
    def mutate_snapshot(record):
        record["position_m"][:] = 100
        record["orientation"][:] = 100
        record["velocity_generalized"][:] = 100
        record["step_inputs"]["mass_matrix"][:] = 100
        for row in record["inertial_diagnostics"]["contact_solves"]:
            row["prepared_inputs"]["mobility"][:] = 100
    observed = driver.integrate(smoke.Field([.001,0,0]), smoke.Empty(), [0,0,0],
        [1,0,0], np.zeros(6), attempt_observer=mutate_snapshot,
        capture_step_inputs=True, capture_prepared_inputs=True, **common)
    checks["observer_snapshots_cannot_change_trajectory"] = all(pristine[key] == observed[key]
        for key in ("status", "position_m", "orientation", "velocity_generalized", "steps", "rejected", "time_s"))
    final_hashes = source_hashes()
    checks["source_files_stable"] = all(final_hashes.get(k) == v for k,v in initial_hashes.items())
    checks = {key: bool(value) for key,value in checks.items()}
    summary = {"passed": all(checks.values()), "checks": checks,
        "source_hashes_at_start": initial_hashes, "source_hashes": final_hashes,
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "diagnostic_trajectory": result, "scope": "manufactured code verification; no physical validation"}
    (output / "results.json").write_text(json.dumps(summary, indent=2))
    (output / "completion.json").write_text(json.dumps({"status": "complete_passed" if summary["passed"] else "complete_failed",
        "results_sha256": sha(output / "results.json")}))
    print(json.dumps({"passed": summary["passed"], "checks": checks}, indent=2))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
