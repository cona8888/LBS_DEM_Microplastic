"""Failure injection checks for the independent local-system audit."""
import copy
import evaluate_probe_v1 as evaluator
job = evaluator.job
api = job.api


def main():
    d = api.read(job.DESIGN)
    source = job.RUN / "accepted_control/record.json"
    r = api.read(source)["result"]
    evaluate = lambda v: evaluator.physical_checks(v, d["spec"])
    checks = {"valid_control_passes": evaluate(r)["passed"]}
    bad = copy.deepcopy(r)
    bad["contact_systems"][0]["jacobian"][0][0] += .1
    checks["wrong_jacobian_rejected"] = not evaluate(bad)["passed"]
    bad = copy.deepcopy(r)
    bad["contact_systems"][0]["gaps"][0] += 1e-6
    checks["wrong_gap_rejected"] = not evaluate(bad)["checks"]["exact_geometry_gaps"]
    bad = copy.deepcopy(r)
    bad["contact_systems"][0]["mobility"][0][0] *= 1.01
    checks["wrong_inverse_rejected"] = not evaluate(bad)["checks"]["inverse_consistency"]
    bad = copy.deepcopy(r)
    bad["contact_systems"][0]["vfree"][0] += .01
    checks["wrong_free_load_rejected"] = not evaluate(bad)["checks"]["free_velocity_load_balance"]
    bad = copy.deepcopy(r)
    bad["health"]["contact"]["reactions"][0] *= -1
    checks["negative_reaction_rejected"] = not evaluate(bad)["checks"]["nonnegative_normal"]
    bad = copy.deepcopy(r)
    bad["velocity"][0] += .001
    checks["momentum_error_rejected"] = not evaluate(bad)["checks"]["momentum_balance"]
    bad = copy.deepcopy(r)
    bad["pose_advanced"] = True
    checks["advancement_rejected"] = not evaluate(bad)["checks"]["nonadvancing"]
    out = job.EVAL / "evaluator_regression_01"
    api.require(not out.exists(), "immutable regression exists")
    out.mkdir(parents=True)
    result = {"passed": all(checks.values()), "checks": checks, "source_sha256": api.sha(source), "evaluator_sha256": api.sha(evaluator.__file__), "test_sha256": api.sha(__file__)}
    api.write(out / "results.json", result)
    print(result)
    return 0 if result["passed"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
