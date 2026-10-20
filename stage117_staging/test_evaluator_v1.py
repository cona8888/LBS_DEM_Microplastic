"""Synthetic failure-path tests for the frozen Stage117 comparison function."""
import copy
import evaluate_longer_sentinels_v1 as evaluation
job = evaluation.job
api = job.api


def main():
    d = api.read(job.DESIGN)
    job.verify(d)
    group = next(g for g in d["groups"] if g["shape"] == api.SHAPES[1])
    specs = {s["case_id"]: s for s in d["cases"]}
    names = group["case_ids"]
    state = {"position_m": [0., 0., 0.], "orientation": [1., 0., 0.], "velocity_generalized": [.001, 0., 0., 0., 0., 0.],
             "time_s": .5, "status": "present_at_horizon", "persistent_contact_observed": False, "first_contact_dwell_time_s": None}
    records = {n: {"result": copy.deepcopy(state)} for n in names}
    ledger = {n: {"health_passed": True, "max_accepted_interval_s": .001} for n in names}
    apply = lambda rr, ll=ledger: evaluation.compare_group(rr, specs, group, d["acceptance"], d["event_acceptance"], ll)
    checks = {"identical_states_pass": apply(records)["passed"]}
    def mutated(key, value, target=2):
        altered = copy.deepcopy(records)
        altered[names[target]]["result"][key] = value
        return apply(altered)
    checks["incomplete_rejected"] = not mutated("status", "incomplete_budget")["passed"]
    checks["status_mismatch_rejected"] = not mutated("status", "full_window_exit")["checks"]["same_terminal_label"]
    checks["position_error_rejected"] = not mutated("position_m", [1e-4, 0., 0.])["checks"]["position_error"]
    checks["axis_error_rejected"] = not mutated("orientation", [0., 1., 0.])["checks"]["axis_error"]
    checks["velocity_error_rejected"] = not mutated("velocity_generalized", [.003, 0., 0., 0., 0., 0.])["checks"]["velocity_error"]
    checks["unequal_time_rejected"] = not mutated("time_s", .4)["checks"]["terminal_time_error"]
    checks["dwell_mismatch_rejected"] = not mutated("persistent_contact_observed", True)["passed"]
    dwells = copy.deepcopy(records)
    for i, n in enumerate(names):
        dwells[n]["result"].update(persistent_contact_observed=True, first_contact_dwell_time_s=.2 + .01 * i)
    checks["dwell_time_error_rejected"] = not apply(dwells)["checks"]["dwell_time_error"]
    poor = copy.deepcopy(ledger)
    poor[names[-1]]["max_accepted_interval_s"] = .003
    checks["event_sampling_rejected"] = not apply(records, poor)["checks"]["finest_accepted_interval"]
    unhealthy = copy.deepcopy(ledger)
    unhealthy[names[0]]["health_passed"] = False
    checks["coarse_health_failure_rejected"] = not apply(records, unhealthy)["passed"]
    trend = copy.deepcopy(records)
    b = specs[names[0]]["config"]["prolate_semiaxes_m"][1]
    trend[names[1]]["result"]["position_m"] = [.001*b, 0., 0.]
    trend[names[2]]["result"]["position_m"] = [.011*b, 0., 0.]
    checks["nonconverging_trend_rejected"] = not apply(trend)["checks"]["position_trend"]
    out = job.EVAL / "evaluator_regression_01"
    api.require(not out.exists(), "immutable regression exists")
    out.mkdir(parents=True)
    result = {"passed": all(checks.values()), "checks": checks, "test_sha256": api.sha(__file__), "evaluator_sha256": api.sha(evaluation.__file__), "design_sha256": api.sha(job.DESIGN)}
    api.write(out / "results.json", result)
    print(result)
    return 0 if result["passed"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
