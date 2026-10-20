"""Pre-dispatch contract and observational-equivalence tests, no extra physics."""
import copy
import longer_sentinels_v1 as job
api = job.api


def main():
    d = api.read(job.DESIGN)
    job.verify(d)
    out = job.PREFLIGHT.parent
    api.require(not out.exists(), "immutable preflight exists")
    out.mkdir(parents=True)
    checks = {"eighteen_cases": len(d["cases"]) == 18, "six_triplets": len(d["groups"]) == 6,
              "all_common_query": all(s["horizon_s"] == .5 for s in d["cases"]),
              "no_absorbing_trap": all(s["config"]["trap"]["absorbing"] is False for s in d["cases"])}
    for seed, cpd in [(1, 2), (2, 2), (2, 4)]:
        rows = [s for s in d["cases"] if s["seed"] == seed and s["cpd"] == cpd]
        checks[f"paired_start_s{seed}_cpd{cpd}"] = all(s["initial_state"] == rows[0]["initial_state"] for s in rows)
    spec = next(s for s in d["cases"] if s["case_id"] == "s2_ar4_f1p0_cpd2_dt2_h0p5")
    bound = job.binding(d, spec["case_id"])
    ignored = {"runtime_seconds", "nullspace_rescue", "short_pgs_seed_stats", "fail_fast_sweep_stats", "within_pose_reuse_stats"}
    normalize = lambda r: {k: v for k, v in r.items() if k not in ignored}
    plain, _ = job.execute(spec, bound, pause=5, observe=False)
    observed, telemetry = job.execute(spec, bound, pause=5)
    checks["observer_exact_result_and_checkpoint"] = normalize(plain) == normalize(observed)
    checks["one_row_per_accepted_step"] = len(telemetry) == observed["steps"] == 5
    checks["contract_independently_reconstructed"] = observed["checkpoint"]["contract"] == job.contracts.expected_contract(spec, bound)
    cp = observed["checkpoint"]
    resumed, resumed_rows = job.execute(spec, bound, checkpoint=cp, pause=10)
    full, full_rows = job.execute(spec, bound, pause=10)
    checks["split_exact_state"] = normalize(resumed) == normalize(full)
    checks["split_exact_dense_observations"] = telemetry + resumed_rows == full_rows
    for label, bad in [("binding", copy.deepcopy(cp)), ("state", copy.deepcopy(cp))]:
        if label == "binding":
            bad["contract"] = "wrong"
        else:
            bad["state"]["t"] += 1
        try:
            job.execute(spec, bound, checkpoint=bad, pause=10)
        except ValueError:
            checks[label + "_tamper_rejected"] = True
        else:
            checks[label + "_tamper_rejected"] = False
    changed = copy.deepcopy(spec)
    changed["horizon_s"] = 1.
    try:
        job.execute(changed, bound, checkpoint=cp, pause=10)
    except ValueError:
        checks["horizon_migration_rejected"] = True
    else:
        checks["horizon_migration_rejected"] = False
    api.write(out / "raw_equivalence.json", {"plain": plain, "observed": observed, "resumed": resumed, "full": full, "telemetry": full_rows}, raw=True)
    checks["previous_outlet_tests"] = job.reference.exit_benchmarks()["passed"]
    job.verify(d)
    result = {"passed": all(checks.values()), "checks": checks, "design_sha256": api.sha(job.DESIGN),
              "raw_sha256": api.sha(out / "raw_equivalence.json"), "scope": "Small prefix observer/restart verification plus unchanged analytical event tests; not full-path convergence."}
    api.write(job.PREFLIGHT, result)
    api.write(out / "completion.json", {"results_sha256": api.sha(job.PREFLIGHT), "passed": result["passed"]})
    print(result)
    return 0 if result["passed"] else 4


if __name__ == "__main__":
    raise SystemExit(main())
