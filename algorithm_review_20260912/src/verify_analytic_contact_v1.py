"""Independent manufactured, derivative, scaling and saved-state verification."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
import numpy as np
import scipy
import contact_dimensionless_lm_v1 as solver
from probe_analytic_contact_v1 import captured

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def independent_gates(args, velocity, health):
    vf, mobility, J, gaps, dt, mu, tol, _ = args
    force = np.asarray(health["reactions"])
    A = J @ mobility @ J.T
    contact_velocity = J @ velocity
    V = max(np.linalg.norm(vf), 1e-15)
    residual = 0.
    cones = []
    work = 0.
    for k in range(len(gaps)):
        i = 3*k
        normal = contact_velocity[i] + gaps[k]/dt
        residual = max(residual, abs(min(A[i, i]*force[i], normal)))
        step = np.linalg.eigvalsh(A[i+1:i+3, i+1:i+3]).max()
        trial = force[i+1:i+3] - contact_velocity[i+1:i+3]/step
        disk = mu*force[i]
        projection = trial if np.linalg.norm(trial) <= disk else trial*disk/max(np.linalg.norm(trial), 1e-300)
        residual = max(residual, np.linalg.norm(force[i+1:i+3] - projection)*step)
        cones.append(np.linalg.norm(force[i+1:i+3]) <= disk + 1e-12*max(np.linalg.norm(force), 1e-30))
        work += force[i+1:i+3] @ contact_velocity[i+1:i+3]
    closure = np.linalg.norm(np.linalg.solve(mobility, velocity-vf) - J.T@force)/max(np.linalg.norm(J.T@force), 1e-30)
    passed = bool(np.isfinite(velocity).all() and np.all(force[::3] >= 0) and
                  all(cones) and residual/V <= min(tol, 1e-10) and closure <= 1e-8 and
                  work <= 1e-8*max(np.linalg.norm(force)*V, 1e-30))
    return {"passed": passed, "independent_residual": float(residual/V),
            "independent_closure": float(closure), "tangential_power": float(work),
            "minimum_normal_force": float(min(force[::3]))}


def manufactured():
    cases = []
    mobility = np.diag([.5, 1., 1.5, .7, .9, 1.1])
    for n in (1, 2):
        J = np.eye(6)[:3*n]
        for mode in ("sticking", "sliding", "frictionless", "separating"):
            for gap_offset in (0., -2e-12):
                mu = 0. if mode == "frictionless" else .3
                desired = np.zeros(6)
                force = np.zeros(3*n)
                gaps = np.full(n, gap_offset)
                dt = .01
                for k in range(n):
                    i = 3*k
                    if mode == "separating":
                        desired[i] = 1.
                        desired[i+1:i+3] = [.2, -.1]
                        continue
                    desired[i] = -gap_offset/dt
                    force[i] = 2.+k
                    if mode in ("sliding", "frictionless"):
                        desired[i+1:i+3] = [.8, -.2]
                        force[i+1:i+3] = -mu*force[i]*desired[i+1:i+3]/np.linalg.norm(desired[i+1:i+3])
                    else:
                        force[i+1:i+3] = [.1, -.1]
                free = desired - mobility @ J.T @ force
                args = [free, mobility, J, gaps, dt, mu, 1e-10, 25000]
                cases.append((f"{n}_contact_{mode}_gap_{gap_offset:g}", args, desired))
    # Three geometrical contact frames share six rigid-body velocity DOFs.
    import inertial_contact_cold_optimized_v1 as s41
    contacts = [(0, 0., np.array([0., 0., 1.]), np.array([1., 0., 0.])),
                (1, 0., np.array([0., 0., 1.]), np.array([-1., 0., 0.])),
                (2, 0., np.array([0., 0., 1.]), np.array([0., 1., 0.]))]
    J, gaps, _ = s41._prepare_geometry(contacts, 1.)
    force = np.tile([2., .1, -.1], 3)
    cases.append(("3_contact_rank_deficient_sticking",
                  [-mobility @ J.T @ force, mobility, J, gaps, .01, .3, 1e-10, 25000], np.zeros(6)))
    return cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="contact_primitives_01")
    options = parser.parse_args()
    out = ROOT / "algorithm_review_20260912/evidence" / options.output
    out.mkdir(parents=True, exist_ok=False)
    records, checks, inputs = [], {}, {}
    # Validate analytic derivatives independently in smooth sticking/sliding
    # branches; nonsmooth transition points are checked via physical residuals.
    rng = np.random.default_rng(12092026)
    errors = []
    for seed in (1, 2, 3):
        path, args = captured(seed)
        inputs[str(path.resolve())] = sha(path)
        system = solver.DimensionlessContactSystem(*args[:6])
        for sample in range(20):
            u = rng.normal(size=len(system.z))
            u[::3] = np.abs(u[::3])+.1
            analytic = system.jacobian_function(u)
            h = 2e-6
            numeric = np.column_stack([
                (system.equations(u+h*system.eye[j]) - system.equations(u-h*system.eye[j]))/(2*h)
                for j in range(len(u))])
            errors.append(float(np.max(np.abs(analytic-numeric))/max(np.max(np.abs(analytic)), 1.)))
    checks["analytic_jacobian_60_smooth_states"] = max(errors) < 2e-8
    for name, args, desired in manufactured():
        start = time.perf_counter()
        try:
            v, health = solver.solve_analytic_prepared(*args)
            gates = independent_gates(args, v, health)
            error = np.linalg.norm(v-desired)/max(np.linalg.norm(args[0]), 1e-15)
            row = {"name": name, "passed": bool(gates["passed"] and error <= 1e-9),
                   "known_velocity_relative_error": float(error), "gates": gates, "health": health}
        except Exception as exc:
            row = {"name": name, "passed": False, "reason": str(exc)}
        row["wall_seconds"] = time.perf_counter()-start
        records.append(row)
    checks["manufactured_17_cases"] = all(r["passed"] for r in records)
    saved = []
    for seed in (1, 2, 3):
        for factor in (1., .5):
            _, args = captured(seed, factor)
            start = time.perf_counter()
            v, health = solver.solve_analytic_prepared(*args)
            elapsed = time.perf_counter()-start
            gates = independent_gates(args, v, health)
            baseline_start = time.perf_counter()
            try:
                old_v, old_health = solver.stage53._solve(*args)
                baseline = {"passed": True, "health": old_health,
                            "velocity_relative_shift": float(np.linalg.norm(v-old_v)/max(np.linalg.norm(old_v), 1e-15))}
            except Exception as exc:
                baseline = {"passed": False, "reason": str(exc)}
            baseline["wall_seconds"] = time.perf_counter()-baseline_start
            row = {"packing_seed": seed, "dt_factor": factor, "passed": gates["passed"],
                   "gates": gates, "health": health, "wall_seconds": elapsed,
                   "velocity": v.tolist(), "baseline": baseline}
            saved.append(row)
            print(json.dumps({"saved_state": seed, "dt_factor": factor, "passed": gates["passed"],
                              "new_seconds": elapsed, "baseline": baseline}), flush=True)
    checks["all_six_saved_systems_strict_gates"] = all(r["passed"] for r in saved)
    checks["half_dt_baseline_velocity_agreement"] = all(
        r["baseline"].get("velocity_relative_shift", np.inf) < 1e-7 for r in saved if r["dt_factor"] == .5)
    # Scale speed and gap together. Root equations are mathematically identical.
    scaling = []
    for seed in (1, 2, 3):
        _, args = captured(seed, .5)
        reference = np.array(next(r["velocity"] for r in saved if r["packing_seed"] == seed and r["dt_factor"] == .5))
        for scale in (1e-3, 1e3):
            changed = [a.copy() if isinstance(a, np.ndarray) else a for a in args]
            changed[0] *= scale
            changed[3] *= scale
            try:
                v, health = solver.solve_analytic_prepared(*changed)
                gates = independent_gates(changed, v, health)
                shift = np.linalg.norm(v/scale-reference)/max(np.linalg.norm(reference), 1e-15)
                row = {"packing_seed": seed, "velocity_gap_scale": scale,
                       "passed": bool(gates["passed"] and shift < 1e-9),
                       "velocity_relative_shift": float(shift), "gates": gates}
            except Exception as exc:
                row = {"packing_seed": seed, "velocity_gap_scale": scale, "passed": False, "reason": str(exc)}
            scaling.append(row)
    checks["dimensionless_speed_gap_scaling_six_cases"] = all(r["passed"] for r in scaling)
    # Mobility-unit changes A -> c A require f -> f/c at unchanged velocity.
    for seed in (1, 2, 3):
        _, args = captured(seed, .5)
        reference = np.array(next(r["velocity"] for r in saved if r["packing_seed"] == seed and r["dt_factor"] == .5))
        for scale in (1e-3, 1e3):
            changed = [a.copy() if isinstance(a, np.ndarray) else a for a in args]
            changed[1] *= scale
            try:
                v, health = solver.solve_analytic_prepared(*changed)
                gates = independent_gates(changed, v, health)
                shift = np.linalg.norm(v-reference)/max(np.linalg.norm(reference), 1e-15)
                row = {"packing_seed": seed, "mobility_scale": scale,
                       "passed": bool(gates["passed"] and shift < 1e-9),
                       "velocity_relative_shift": float(shift), "gates": gates}
            except Exception as exc:
                row = {"packing_seed": seed, "mobility_scale": scale, "passed": False, "reason": str(exc)}
            scaling.append(row)
    checks["mobility_force_unit_scaling_six_cases"] = all(r["passed"] for r in scaling if "mobility_scale" in r)
    result = {"passed": all(checks.values()), "checks": checks,
              "jacobian_max_relative_error": max(errors), "manufactured": records,
              "saved_systems": saved, "rescaling": scaling, "stats": solver.stats(),
              "input_hashes": inputs,
              "source_hashes": {str(Path(p).resolve()): sha(p) for p in
                                (__file__, solver.__file__, solver.stage50.__file__, solver.stage53.__file__)},
              "environment": {"python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__,
                              "platform": platform.platform(), "utc": datetime.now(timezone.utc).isoformat()},
              "scope": "Contact primitives only; trajectory, timestep and physical validation are separate gates."}
    path = out / "results.json"
    path.write_text(json.dumps(result, indent=2))
    (out / "completion.json").write_text(json.dumps({"status": "complete_passed" if result["passed"] else "complete_failed",
                                                   "results_sha256": sha(path)}, indent=2))
    print(json.dumps({"passed": result["passed"], "checks": checks, "jacobian_error": max(errors)}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
