"""Exact cold-solver equivalence on primitives and the saved matrix state.

The benchmark is paired and alternates execution order. Wall-clock speed is
reported, not used to accept scientific equivalence. The baseline is unedited.
"""
import argparse
import hashlib
import json
import platform
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import scipy

import inertial_contact_cold_optimized_v1 as optimized

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage39_staging")]
import inertial_contact_cold_v1 as baseline
import matrix_case_v1
import trajectory_cold_trap_v1
import verify_inertial_contact_v4 as existing_suite


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def equivalent(reference, candidate):
    return bool(np.array_equal(reference[0], candidate[0]) and reference[1] == candidate[1])


def matrix_step_inputs():
    """Capture the actual first attempted step at the frozen failure pose."""
    path = ROOT / "stage39_evaluations/matrix_profile_01/results.json"
    state = json.loads(path.read_text())["result"]
    field, geometry, length, _, inputs = matrix_case_v1.load(2)
    captured = []

    class Captured(Exception):
        pass

    def capture(*args, **kwargs):
        captured.append((args, kwargs))
        raise Captured()

    original = baseline.inertial_contact_step
    baseline.inertial_contact_step = capture
    try:
        trajectory_cold_trap_v1.integrate(
            field, geometry, state["position_m"], state["orientation"],
            state["velocity_generalized"], 2e-4, 5e-5, .001002, 1380., 998.2,
            [0, 0, -9.80665], .3, length, .02,
            added_mass_fraction=1., cutoff_ratio=.2, roughness_ratio=.01,
            displacement_fraction=.1, relaxation_fraction=.5, max_dt=.01,
            max_steps=1, wall_budget=60.,
        )
    except Captured:
        pass
    finally:
        baseline.inertial_contact_step = original
    if len(captured) != 1:
        raise RuntimeError("could not capture first matrix replay step")
    return captured[0], (path, *inputs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 1:
        raise ValueError("at least one benchmark repeat required")
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(4101)
    rows = []
    hard_case = None
    for count in (0, 1, 2, 3):
        for friction in (0., .3, .8):
            for scale in (1e-3, 1., 1e3):
                # A well-conditioned positive mobility and a convex cluster of
                # planes with positive gaps exercise activation and disk slip.
                factor = rng.normal(size=(6, 6))
                mobility = scale * (factor @ factor.T + np.eye(6))
                contacts = []
                for k in range(count):
                    normal = np.array([.2*rng.normal(), 1., .2*rng.normal()])
                    normal /= np.linalg.norm(normal)
                    lever = -.4*normal + .1*rng.normal(size=3)
                    contacts.append((k, .001*float(k), normal, lever))
                free = rng.normal(size=6)
                free[1] = -abs(free[1]) - .1
                arguments = (free, mobility, contacts, 1., .1, friction)
                reference = baseline.contact_model.contact_solve(*arguments, tol=1e-10, maxiter=10000)
                candidate = optimized.contact_solve(*arguments, tol=1e-10, maxiter=10000)
                rows.append({"contacts": count, "friction": friction, "mobility_scale": scale,
                             "exact_velocity_and_health": equivalent(reference, candidate),
                             "iterations": reference[1]["iterations"]})
                if reference[1]["iterations"] > 1:
                    hard_case = arguments

    failures = []
    for solve in (baseline.contact_model.contact_solve, optimized.contact_solve):
        try:
            solve(*hard_case, tol=1e-10, maxiter=1)
            failures.append(None)
        except RuntimeError as exc:
            failures.append(str(exc))

    (matrix_arguments, matrix_keywords), matrix_sources = matrix_step_inputs()
    matrix_rows = []
    for friction in (0., .3):
        arguments = list(matrix_arguments)
        arguments[9] = friction
        reference = baseline.inertial_contact_step(*arguments, **matrix_keywords)
        candidate = optimized.inertial_contact_step(*arguments, **matrix_keywords)
        # Deliberately extreme supplied reactions cannot alter a cold solve.
        supplied = {str(contact[0]): [1e12, -1e12, 1e12] for contact in arguments[6]}
        candidate_with_ignored_cache = optimized.inertial_contact_step(*arguments, world_reactions=supplied)
        timings = {"baseline": [], "optimized": []}
        for repeat in range(args.repeats):
            order = ("baseline", "optimized") if repeat % 2 == 0 else ("optimized", "baseline")
            for name in order:
                model = baseline if name == "baseline" else optimized
                started = time.perf_counter()
                result = model.inertial_contact_step(*arguments, **matrix_keywords)
                timings[name].append(time.perf_counter()-started)
                if not equivalent(reference, result):
                    raise AssertionError("timed solve changed its result")
        matrix_rows.append({
            "friction": friction, "contact_grain_ids": [int(c[0]) for c in arguments[6]],
            "exact_velocity_and_health": equivalent(reference, candidate),
            "supplied_reactions_ignored_exactly": equivalent(candidate, candidate_with_ignored_cache),
            "total_contact_iterations": reference[1]["total_contact_iterations"],
            "finite_re_iterations": reference[1]["iterations"],
            "health": candidate[1], "timings_s": timings,
            "median_speedup": statistics.median(timings["baseline"])/statistics.median(timings["optimized"]),
        })

    previous_model, old_argv = existing_suite.model, sys.argv[:]
    try:
        existing_suite.model = optimized
        sys.argv = [__file__, "--output", str(output / "existing_primitives")]
        existing_suite.main()
    finally:
        existing_suite.model, sys.argv = previous_model, old_argv
    primitives = json.loads((output / "existing_primitives/results.json").read_text())
    checks = {
        "36_contact_cases_exact": len(rows) == 36 and all(r["exact_velocity_and_health"] for r in rows),
        "nonconvergence_still_fails_closed": failures == ["contact nonconvergence"]*2,
        "saved_three_grain_cases_exact": all(r["exact_velocity_and_health"] and len(r["contact_grain_ids"]) == 3 for r in matrix_rows),
        "reaction_cache_ignored": all(r["supplied_reactions_ignored_exactly"] for r in matrix_rows),
        "existing_inertial_primitives_pass": primitives["passed"],
    }
    sources = [Path(__file__), Path(optimized.__file__), Path(baseline.__file__),
               Path(baseline.contact_model.__file__), Path(baseline.previous.__file__),
               Path(existing_suite.__file__), Path(matrix_case_v1.__file__),
               Path(trajectory_cold_trap_v1.__file__), Path(trajectory_cold_trap_v1.previous.__file__),
               Path(baseline.finite_re.__file__), Path(baseline.base.__file__),
               *matrix_sources]
    report = {
        "completed": True, "passed": all(checks.values()), "checks": checks,
        "contact_cases": rows, "matrix_step_cases": matrix_rows,
        "environment": {"python": sys.version, "numpy": np.__version__,
                        "scipy": scipy.__version__, "platform": platform.platform()},
        "command": [sys.executable, str(Path(__file__).resolve()), "--output", str(output),
                    "--repeats", str(args.repeats)],
        "source_hashes": {str(path.resolve()): sha(path) for path in sources},
        "claim_boundary": "code equivalence and local cost only; no physical validation or release qualification",
    }
    (output / "results.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({"passed": report["passed"], "checks": checks,
                      "matrix_median_speedups": [r["median_speedup"] for r in matrix_rows]}, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
