"""Bounded equivalence and performance evidence for compiled contact sweeps."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

import compiled_sor as candidate
import numpy as np
import numba
import llvmlite
import scipy

ROOT = candidate.ROOT
sys.path.insert(0, str(ROOT / "algorithm_review_20260912/src"))
import inertial_contact_projected_sor_v1 as reference
from probe_analytic_contact_v1 import captured
from verify_analytic_contact_v1 import manufactured, independent_gates


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def raw_reference(A, z, gaps, dt, mu, steps, scale, tol, maxiter, omega):
    force = np.zeros(len(z))
    for iteration in range(maxiter):
        for k in range(len(gaps)):
            i = 3*k
            old = force[i]
            vn = z[i]+A[i]@force+gaps[k]/dt
            trial = max(0., old-vn/A[i, i])
            force[i] = trial if omega == 1. else max(0., old+omega*(trial-old))
            old_t = force[i+1:i+3].copy()
            vt = z[i+1:i+3]+A[i+1:i+3]@force
            trial_t = candidate.s50._project(old_t, vt, steps[k], mu*force[i])
            if omega == 1.:
                force[i+1:i+3] = trial_t
            else:
                trial_t = old_t+omega*(trial_t-old_t)
                force[i+1:i+3] = trial_t*min(1., mu*force[i]/max(np.linalg.norm(trial_t), 1e-300))
        if candidate.s50._residual(force, z, A, gaps, dt, mu, steps)/scale <= tol:
            return force, iteration+1, True
    return force, maxiter, False


def one_call(solver, args):
    begin = time.perf_counter()
    try:
        velocity, health = solver(*args)
        gates = independent_gates(args, velocity, health)
        row = {"accepted": True, "velocity": velocity.tolist(), "health": health, "gates": gates}
    except RuntimeError as exc:
        row = {"accepted": False, "reason": str(exc),
               "iterations": int(getattr(exc, "iterations", args[-1])),
               "diagnostics": getattr(exc, "contact_diagnostics", {})}
    row["seconds"] = time.perf_counter()-begin
    return row


def compare(args):
    old = one_call(reference._solve, args)
    new = one_call(candidate.solve_prepared, args)
    row = {"reference": old, "compiled": new,
           "acceptance_agrees": old["accepted"] == new["accepted"],
           "warmed_wall_speedup": old["seconds"]/max(new["seconds"], 1e-12)}
    if old["accepted"] and new["accepted"]:
        v = np.asarray(new["velocity"])
        old_v = np.asarray(old["velocity"])
        f = np.asarray(new["health"]["reactions"])
        old_f = np.asarray(old["health"]["reactions"])
        row.update(velocity_relative_difference=float(np.linalg.norm(v-old_v)/max(np.linalg.norm(args[0]), 1e-15)),
                   reaction_relative_difference=float(np.linalg.norm(f-old_f)/max(np.linalg.norm(old_f), 1e-30)),
                   iteration_difference=new["health"]["iterations"]-old["health"]["iterations"],
                   velocity_bitwise_equal=bool(np.array_equal(v, old_v)),
                   reactions_bitwise_equal=bool(np.array_equal(f, old_f)))
        row["passed"] = bool(new["gates"]["passed"] and
                             row["velocity_relative_difference"] <= 1e-8 and
                             row["reaction_relative_difference"] <= 1e-8)
    else:
        row["passed"] = row["acceptance_agrees"]
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="compiled_sor_01")
    options = parser.parse_args()
    out = ROOT / "bottleneck_resolution_20260912/evidence" / options.output
    out.mkdir(parents=True, exist_ok=False)
    begin = datetime.now(timezone.utc).isoformat()
    hashes_before = {str(Path(p).resolve()): sha(p) for p in
                     (__file__, candidate.__file__, reference.__file__, candidate.s50.__file__)}
    compile_seconds = candidate.warmup()
    print(json.dumps({"warmup_compile_or_cache_load_seconds": compile_seconds}), flush=True)
    ordinary = []
    for name, args, desired in manufactured():
        row = compare(args)
        row["name"] = name
        if row["compiled"]["accepted"]:
            row["known_velocity_relative_error"] = float(np.linalg.norm(np.asarray(row["compiled"]["velocity"])-desired)/max(np.linalg.norm(args[0]), 1e-15))
            row["passed"] &= row["known_velocity_relative_error"] <= 1e-9
        ordinary.append(row)
    saved = []
    for seed in (1, 2, 3):
        for factor in (1., .5):
            path, args = captured(seed, factor)
            row = compare(args)
            row.update(packing_seed=seed, dt_factor=factor,
                       input_path=str(path.resolve()), input_sha256=sha(path))
            saved.append(row)
            (out / f"saved_s{seed}_dt{factor:g}.json").write_text(json.dumps(row, indent=2))
            print(json.dumps({"seed": seed, "dt_factor": factor, "passed": row["passed"],
                              "reference_accepted": row["reference"]["accepted"],
                              "compiled_accepted": row["compiled"]["accepted"],
                              "speedup": row["warmed_wall_speedup"]}), flush=True)
    rng = np.random.default_rng(12092026)
    projection = []
    for n in (1, 2, 3, 4):
        for sample in range(12):
            B = rng.normal(size=(3*n, 6))
            A = np.ascontiguousarray(B@B.T)
            z = rng.normal(size=3*n)
            gaps = rng.uniform(-1e-7, 1e-7, size=n)
            dt = .01
            mu = (0., .3, 1.)[sample % 3]
            steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max() for k in range(n)])
            for omega in (1., 1.7):
                args = (A, z, gaps, dt, mu, steps, 1., -1., 64, omega)
                original, _, _ = raw_reference(*args)
                compiled, sweeps, accepted = candidate.cold_loop(*args)
                error = np.linalg.norm(compiled-original)/max(np.linalg.norm(original), 1e-30)
                cone_ok = all(np.linalg.norm(compiled[3*k+1:3*k+3]) <= mu*compiled[3*k]+1e-12*max(np.linalg.norm(compiled), 1e-30) for k in range(n))
                projection.append({"contacts": n, "sample": sample, "omega": omega,
                                   "relative_terminal_force_difference": float(error),
                                   "passed": bool(error <= 1e-10 and cone_ok and np.all(compiled[::3] >= 0) and
                                                  np.isfinite(compiled).all() and sweeps == 64 and not accepted)})
    thresholds = []
    for normal in (0., 1e-14, 1e-10, 1.):
        for factor in (1.-1e-12, 1., 1.+1e-12):
            args = [np.array([-normal, .3*normal*factor, 0., 0., 0., 0.]),
                    np.eye(6), np.eye(6)[:3], np.zeros(1), .01, .3, 1e-10, 25000]
            row = compare(args)
            row.update(normal_scale=normal, tangent_to_cone_factor=factor)
            thresholds.append(row)
    failure_args = manufactured()[0][1].copy()
    failure_args[-1] = 0
    failure = one_call(candidate.solve_prepared, failure_args)
    vf = np.arange(6, dtype=float)
    no_contact = candidate.solve_prepared(vf, np.eye(6), np.zeros((0, 6)), np.zeros(0), .01, .3, 1e-10, 25000)
    hashes_after = {p: sha(p) for p in hashes_before}
    checks = {"manufactured_17_cases_equivalent_and_physical": all(r["passed"] for r in ordinary),
              "saved_6_systems_acceptance_and_accepted_reactions_equivalent": all(r["passed"] for r in saved),
              "random_psd_96_fixed_sweep_pgs_and_sor_projection_cases": all(r["passed"] for r in projection),
              "near_threshold_12_cases": all(r["passed"] for r in thresholds),
              "zero_contact_velocity_identical": bool(np.array_equal(vf, no_contact[0])),
              "failure_work_recorded": not failure["accepted"] and failure["iterations"] == 0 and bool(failure["diagnostics"]),
              "sources_unchanged": hashes_before == hashes_after}
    result = {"passed": all(checks.values()), "checks": checks, "start_utc": begin,
              "end_utc": datetime.now(timezone.utc).isoformat(),
              "compile_or_cache_load_seconds": compile_seconds,
              "manufactured": ordinary, "saved_systems": saved, "fixed_sweep_projection": projection,
              "near_threshold": thresholds, "zero_iteration_failure": failure,
              "source_hashes": hashes_after, "stats": candidate.stats(),
              "environment": {"python": sys.version, "platform": platform.platform(),
                              "numpy": np.__version__, "scipy": scipy.__version__,
                              "numba": numba.__version__, "llvmlite": llvmlite.__version__,
                              "fastmath": False, "parallel": False, "dtype": "float64"},
              "limits": ["Frozen saved half-dt systems are algebraic probes, not physical timestep refinement.",
                         "Compiled scalar dot accumulation can differ from NumPy/BLAS rounding; bitwise equivalence is not assumed.",
                         "These measurements isolate contact solves, not full trajectory performance or physical validation.",
                         "Compilation/cache load is reported separately; benchmark timings may share CPU with other tasks."]}
    result_path = out / "results.json"
    result_path.write_text(json.dumps(result, indent=2))
    (out / "completion.json").write_text(json.dumps({"status": "complete_passed" if result["passed"] else "complete_failed",
                                                   "results_sha256": sha(result_path)}, indent=2))
    print(json.dumps({"passed": result["passed"], "checks": checks,
                      "saved_speedups": [r["warmed_wall_speedup"] for r in saved]}, indent=2), flush=True)
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
