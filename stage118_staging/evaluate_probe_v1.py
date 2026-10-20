"""Independently check local assembly, artifact bindings and physical gates."""
from pathlib import Path
import numpy as np
import probe_three_contact_v1 as job
api = job.api
OUT = job.EVAL / "independent_evaluation_01"


def physical_checks(r, spec):
    dt = r["dt_s"]
    c = spec["config"]
    state = r["input_pose"]
    q = np.asarray(state["velocity_generalized"])
    bg = np.asarray(r["background"])
    mass, stokes, lub = [np.asarray(r[k]) for k in ["mass", "stokes_resistance", "lubrication_resistance"]]
    a, b, _ = c["prolate_semiaxes_m"]
    inertial = job.RECOVERY.portfolio
    re = inertial.finite_re.reynolds_number(q[:3]-bg[:3], c["fluid_density_kg_m3"], c["dynamic_viscosity_Pa_s"], 2*(a*b*b)**(1/3))
    factor = inertial.finite_re.inertial_multiplier(re, inertial.finite_re.prolate_sphericity(a, b))
    drag = stokes.copy()
    drag[:3, :3] *= factor
    system = mass/dt + drag + lub
    first = r["contact_systems"][0]
    M, J, v, g = [np.asarray(first[k]) for k in ["mobility", "jacobian", "vfree", "gaps"]]
    rhs = mass@q/dt + drag@bg + np.asarray(r["body_load"])
    inverse_error = np.linalg.norm(system@M-np.eye(6), ord=np.inf)
    free_error = np.linalg.norm(system@v-rhs)/max(np.linalg.norm(rhs), 1e-30)
    expected_J, expected_g, _ = inertial.s41._prepare_geometry(r["active_contacts"], a)
    condition = float(np.linalg.cond(system))
    checks = {"exact_contact_jacobian": bool(np.array_equal(J, expected_J)), "exact_geometry_gaps": bool(np.array_equal(g, expected_g)),
        "inverse_consistency": bool(inverse_error <= 1e-10), "free_velocity_load_balance": bool(free_error <= 1e-10),
        "overdamped_rotation_preserved": bool(np.array_equal(mass[3:, 3:], np.zeros((3, 3)))),
        "condition_recomputed": bool(np.isclose(condition, first["matrices"]["system_condition_2"], rtol=1e-10)),
        "field_particle_Re_applicable": bool(re <= 3), "nonadvancing": r["pose_advanced"] is False and r["time_advanced"] is False}
    extra = {"inverse_error_inf": float(inverse_error), "free_load_residual": float(free_error), "system_condition_2": condition,
             "active_grain_ids": [int(contact[0]) for contact in r["active_contacts"]], "gap_over_dt_m_s": (g/dt).tolist()}
    if r["status"] == "solver_returned":
        api.require(len(r["contact_systems"]) == 1, "new multi-iteration evaluation needed")
        f = np.asarray(r["health"]["contact"]["reactions"])
        velocity = np.asarray(r["velocity"])
        A = J@M@J.T
        z = J@v
        vc = z + A@f
        steps = [np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max() for k in range(len(g))]
        res = 0.
        mu = c["friction_coefficient"]
        for k in range(len(g)):
            i = 3*k
            res = max(res, abs(min(A[i, i]*f[i], vc[i]+g[k]/dt)))
            trial = f[i+1:i+3]-vc[i+1:i+3]/steps[k]
            projection = trial*min(1., mu*f[i]/max(np.linalg.norm(trial), 1e-300))
            res = max(res, np.linalg.norm(f[i+1:i+3]-projection)*steps[k])
        res /= max(np.linalg.norm(v), 1e-15)
        closure = np.linalg.norm(np.linalg.solve(M, velocity-v)-J.T@f)/max(np.linalg.norm(J.T@f), 1e-30)
        acceleration = mass@(velocity-q)/dt
        slip = drag@(velocity-bg)
        lubrication = lub@velocity
        body = np.asarray(r["body_load"])
        reaction = J.T@f
        momentum = np.linalg.norm(acceleration+slip+lubrication-body-reaction)/max(*[np.linalg.norm(t) for t in [acceleration, slip, lubrication, body, reaction, drag@bg]], 1e-30)
        work = sum(float(f[3*k+1:3*k+3]@vc[3*k+1:3*k+3]) for k in range(len(g)))
        checks.update(nonnegative_normal=bool(np.all(f[::3] >= 0)), coulomb_cone=bool(all(np.linalg.norm(f[3*k+1:3*k+3]) <= mu*f[3*k]+1e-12*max(np.linalg.norm(f), 1e-30) for k in range(len(g)))),
            contact_residual=bool(res <= 1e-10), force_balance=bool(closure <= 1e-8), momentum_balance=bool(momentum <= 1e-8),
            dissipative_friction=bool(work <= 1e-8*max(np.linalg.norm(f)*max(np.linalg.norm(v), 1e-15), 1e-30)),
            candidate_motion_caps=r["candidate_motion_caps_pass"], reference_pruned_sweep_identical=r["candidate_sweep"]["identical"], candidate_clearance=r["candidate_sweep"]["clearance_pass"])
        extra.update(contact_residual=float(res), force_closure=float(closure), momentum_residual=float(momentum), friction_work_W=work)
    return {"passed": all(checks.values()), "checks": checks, **extra}


def main():
    d = api.read(job.DESIGN)
    job.verify(d)
    api.require(not OUT.exists(), "immutable evaluation exists")
    done = api.read(job.RUN/"completion.json")
    manifest = api.read(job.RUN/"manifest.json")
    api.require(done["design_sha256"] == manifest["design_sha256"] == api.sha(job.DESIGN), "design drift")
    api.require(done["manifest_sha256"] == api.sha(job.RUN/"manifest.json"), "manifest drift")
    order = [s["id"] for s in d["scenarios"]]
    api.require(manifest["order"] == order and set(done["records"]) == set(order), "scenario drift")
    api.require(not list(job.RUN.rglob("failure.json")), "diagnostic software failure")
    api.require(not any(p.stat().st_size for p in job.RUN.glob("*.stderr.txt")), "unexpected worker stderr")
    ledger = []
    hashes = {}
    for scenario in d["scenarios"]:
        name = scenario["id"]
        path = job.RUN/name/"record.json"
        record = api.read(path)
        completion = api.read(path.parent/"completion.json")
        launch = api.read(path.parent/"launch.json")
        api.require(api.sha(path) == done["records"][name] == completion["record_sha256"], "record drift")
        api.require(api.sha(path.parent/"launch.json") == completion["launch_sha256"], "launch drift")
        api.require(record["design_sha256"] == launch["design_sha256"] == api.sha(job.DESIGN), "record binding drift")
        r = record["result"]
        api.require(r["scenario"] == name and r["input_pose"] == scenario["state"], "pose/identity drift")
        expected_dt = scenario.get("dt_s") if scenario["dt_mode"] == "explicit" else (r["unclipped_dt_s"] if scenario["dt_mode"] == "unclipped" else min(r["controller_caps_s"].values())*scenario["factor"])
        api.require(r["dt_s"] == expected_dt, "timestep drift")
        checks = physical_checks(r, d["spec"])
        if name == "accepted_control":
            p = r["positive_control"]
            checks["positive_control_exact"] = all(value == 0 for value in p.values())
            checks["passed"] = checks["passed"] and checks["positive_control_exact"]
        ledger.append({"scenario": name, "dt_s": r["dt_s"], "status": r["status"], "exception": r.get("exception"), "verification": checks,
            "runtime_s": r["runtime_s"], "contact_system_count": len(r["contact_systems"]), "finish_candidate_count": len(r["finish_candidates"]),
            "rescue_diagnostics": r["nullspace_rescue"], "solver": r.get("health", {}).get("contact", {}).get("solver")})
        for p in path.parent.iterdir():
            if p.is_file():
                hashes[str(p)] = api.sha(p)
    passed = all(row["verification"]["passed"] for row in ledger)
    by_id = {row["scenario"]: row for row in ledger}
    localized = by_id["failed_remaining"]["status"] == "solver_raised" and by_id["failed_without_endpoint_clip"]["status"] == "solver_returned"
    result = {"diagnostic_verified": passed, "endpoint_clipping_local_failure_isolated": localized,
        "ledger": ledger, "run_wall_s": done["wall_s"], "local_step_runtime_s": sum(row["runtime_s"] for row in ledger),
        "condition_ratio_endpoint_vs_unclipped": by_id["failed_remaining"]["verification"]["system_condition_2"]/by_id["failed_without_endpoint_clip"]["verification"]["system_condition_2"],
        "conclusion": "The frozen portfolio rejects the endpoint-clipped step at the exact same pose where it accepts the unclipped step. Halving increases system anisotropy and does not recover these tested steps. The accepted-control output is exact; this is a numerical solver/endpoint interaction, not evidence of physical trapping or leakage.",
        "limitations": ["Six non-advancing local probes, not a successful trajectory rerun.", "Four selected failure-step sizes were tested, not a new replay of all thirty retries.", "Unclipped candidate extends beyond the query interval and is not an authorized endpoint treatment.", "Condition number alone does not establish uniqueness or prove the sole cause of nonlinear solver failure.", "Successful zero-gap seed candidates inside the rescue are not successes of the original-gap contact problem."],
        "physical_model_changed": False, "trajectory_advanced": False, "numerical_failure_repaired": False,
        "population_release_measured": False, "population_campaign_authorized": False,
        "next": "Develop a separately versioned, better-conditioned three-contact solve for small endpoint steps, preserving original gap, Coulomb, force, momentum and dissipation gates. Verify it on these captured systems and stick/slip/open-contact toys before any trajectory rerun. Also improve rejected-trial diagnostics and safe budget checkpointing.",
        "artifact_hashes": hashes, "design_sha256": api.sha(job.DESIGN), "run_completion_sha256": api.sha(job.RUN/"completion.json"), "evaluator_sha256": api.sha(__file__)}
    job.verify(d)
    OUT.mkdir(parents=True)
    api.write(OUT/"results.json", result)
    api.write(OUT/"completion.json", {"results_sha256": api.sha(OUT/"results.json"), "diagnostic_verified": passed})
    print("VERIFIED", passed, "ENDPOINT_LOCALIZED", localized, "CONDITION_RATIO", result["condition_ratio_endpoint_vs_unclipped"])
    for row in ledger:
        print(row["scenario"], row["verification"])
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
