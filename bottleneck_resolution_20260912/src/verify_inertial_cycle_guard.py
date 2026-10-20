"""Bounded exact-cycle checks and one rebuilt captured physical-step comparison.

Manufactured prepared solvers below test control flow, not physical acceptance.
The captured case uses the actual frozen field, loads, contact geometry, and
compiled Stage70 portfolio. No half-dt algebraic proxy is used.
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import sys
import time
import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage41_staging"),
                str(ROOT / "algorithm_review_20260912" / "src")]
import driver_consolidated as driver
import inertial_consolidated as baseline
import inertial_cycle_guard as candidate
from portfolio_explicit import Portfolio


def plain(value):
    if isinstance(value, dict):
        return {str(k): plain(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources():
    found = {}
    for module in tuple(sys.modules.values()):
        value = getattr(module, "__file__", None)
        if value:
            path = Path(value).resolve()
            if path.suffix == ".py" and path.is_relative_to(ROOT) and "deps" not in path.parts:
                found[str(path)] = sha(path)
    return found


def fixture():
    return dict(old_velocity=np.array([.02,0,0,0,0,0]),
        fluid_background_velocity=np.zeros(6), body_load=np.zeros(6),
        stokes_resistance=np.eye(6), lubrication_resistance=np.zeros((6,6)),
        mass_matrix=np.eye(6), contacts=[], ell=1., dt=1., friction=0.,
        fluid_density=1., viscosity=1., equivalent_diameter=1., sphericity=1.)


def compliance_for(q, inputs):
    reynolds = baseline.finite_re.reynolds_number(q[:3] - inputs["fluid_background_velocity"][:3],
        inputs["fluid_density"], inputs["viscosity"], inputs["equivalent_diameter"])
    multiplier = baseline.finite_re.inertial_multiplier(reynolds, inputs["sphericity"])
    drag = inputs["stokes_resistance"].copy()
    drag[:3,:3] *= multiplier
    return np.linalg.inv(inputs["mass_matrix"] / inputs["dt"] + drag + inputs["lubrication_resistance"])


class ManufacturedMap:
    """A fixed lookup map keyed only by this call's actual prepared compliance."""
    def __init__(self, states, inputs):
        self.mapping = {}
        for before, after in zip(states, states[1:]):
            key = compliance_for(before, inputs).tobytes()
            if key in self.mapping:
                assert np.array_equal(self.mapping[key], after)
            self.mapping[key] = after.copy()

    def __call__(self, vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
        velocity = self.mapping[mobility.tobytes()].copy()
        return velocity, {"iterations": 1, "residual": 0., "force_residual": 0.,
            "dissipation": 0., "reactions": [], "solver": "manufactured_control_flow_map"}


def run_step(module, inputs, solver, enabled=None, max_iterations=80):
    diagnostics = {}
    options = dict(prepared_solver=solver, diagnostics=diagnostics,
                   max_iterations=max_iterations)
    if enabled is not None:
        options["deterministic_stateless_cold_solver"] = enabled
    started = time.perf_counter()
    try:
        velocity, health = module.inertial_contact_step(**inputs, **options)
    except RuntimeError as exc:
        return {"status": "rejected", "reason": str(exc), "exception": vars(exc),
                "diagnostics": diagnostics, "wall_seconds": time.perf_counter() - started}
    return {"status": "accepted", "velocity": velocity, "health": health,
            "diagnostics": diagnostics, "wall_seconds": time.perf_counter() - started}


def rebuilt_capture(trace_path, seed, attempt_id=None):
    import matrix_case_v1
    import geometry_exact_v1
    import wall_field_exact_v1
    cfg_path = ROOT / "stage55_designs/paired_three_packing_pilot_v1.json"
    cfg = json.loads(cfg_path.read_text())
    with trace_path.open() as handle:
        record = next(json.loads(line) for line in handle
            if (lambda row: row.get("detail") == "inertial/contact fixed point did not converge"
                and (attempt_id is None or row["attempt_id"] == attempt_id))(json.loads(line)))
    field, old_geometry, length, spacing, paths = matrix_case_v1.load(seed)
    field = wall_field_exact_v1.WallCellFieldExact.from_field(field)
    geometry = geometry_exact_v1.GrainGeometry.from_geometry(old_geometry)
    x, p, q = (np.array(record[key], dtype=np.float64) for key in
               ("position_m", "orientation", "velocity_generalized"))
    a, b, _ = cfg["prolate_semiaxes_m"]
    viscosity = cfg["dynamic_viscosity_Pa_s"]
    rho, rho_f = cfg["particle_density_kg_m3"], cfg["fluid_density_kg_m3"]
    fluid_velocity, gradient = field.sample(x)
    background, _ = driver.mechanics.free_motion(p, gradient, fluid_velocity,
        a, b, viscosity, 1., 1., [0,0,0])
    stokes = baseline.stokes_generalized_resistance(p, a, b, viscosity)
    mass, _ = baseline.generalized_mass_matrix(p, a, b, rho, rho_f, cfg["added_mass_fraction"])
    mass[3:,3:] = 0.
    volume = 4 * np.pi * a * b * b / 3
    body = np.r_[(rho-rho_f) * volume * driver.mechanics.finite(cfg["gravity_m_s2"]), np.zeros(3)]
    near = driver.enrich(geometry, geometry.contacts(x,p,a,b,.2*float(np.max(geometry.r))))
    lubrication, _ = driver.lubrication_matrix(near,p,a,b,a,viscosity,.2,.01)
    contacts = [(int(row[0]), float(row[1]), np.array(row[2]), np.array(row[3]))
                for row in record["active_contacts"]]
    inputs = dict(old_velocity=q, fluid_background_velocity=background, body_load=body,
        stokes_resistance=stokes, lubrication_resistance=lubrication, mass_matrix=mass,
        contacts=contacts, ell=a, dt=record["dt_s"], friction=cfg["friction_coefficient"],
        fluid_density=rho_f, viscosity=viscosity, equivalent_diameter=2*(a*b*b)**(1/3),
        sphericity=baseline.finite_re.prolate_sphericity(a,b))
    hashes = {str(path): sha(path) for path in [cfg_path, trace_path, *paths]}
    return inputs, record, hashes


def compiled_portfolio():
    import compiled_blas_loop
    from compiled_stage53_blas import CompiledStage53
    class Sor:
        def __call__(self, *args, **kwargs):
            return compiled_blas_loop.solve_prepared(*args, **kwargs)
        def stats(self):
            return compiled_blas_loop.stats()
    return Portfolio(default_solver=CompiledStage53(), sor_solver=Sor())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--manufactured-only", action="store_true")
    parser.add_argument("--trace", type=Path, default=ROOT / "bottleneck_resolution_20260912/evidence/crossing_blas_01/s2_blas_l1_attempts.jsonl")
    parser.add_argument("--seed", type=int, default=2)
    parser.add_argument("--attempt-id", type=int)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    # Load numerical modules before recording the source manifest.
    if not args.manufactured_only:
        import compiled_blas_loop
        compiled_blas_loop.warmup()
        compiled_portfolio()
    initial_hashes = sources()
    inputs = fixture()
    first = inputs["old_velocity"].copy()
    second = first.copy(); second[0] = .03
    cyclic = ManufacturedMap([first, second, first], inputs)
    unchecked = run_step(baseline, inputs, cyclic)
    disabled = run_step(candidate, inputs, cyclic, False)
    guarded = run_step(candidate, inputs, cyclic, True)
    checks = {"guard_default_off": candidate.ContactModel(cyclic).deterministic_stateless_cold_solver is False,
        "unchanged_cycle_failure_message": unchecked["reason"] == disabled["reason"] == guarded["reason"]
        == "inertial/contact fixed point did not converge",
        "disabled_preserves_80_iterations": len(unchecked["diagnostics"]["contact_solves"])
            == len(disabled["diagnostics"]["contact_solves"]) == 80,
        "exact_two_cycle_stops_after_two": len(guarded["diagnostics"]["contact_solves"]) == 2
            and guarded["diagnostics"]["cycle_guard"]["cycle_length"] == 2,
        "failed_iteration_actual_work_preserved": guarded["exception"]["diagnostics"]["total_contact_iterations"] == 2}
    near_states = []
    for k in range(10):
        state = first.copy()
        state[0] = (.02 if k % 2 == 0 else .03) + (k//2) * 1e-9
        near_states.append(state)
    near = run_step(candidate, inputs, ManufacturedMap(near_states, inputs), True, max_iterations=9)
    checks["near_but_not_exact_cycle_not_pruned"] = (np.allclose(near_states[0], near_states[2])
        and "cycle_guard" not in near["diagnostics"] and len(near["diagnostics"]["contact_solves"]) == 9)
    signed = first.copy(); signed[1] = -0.
    adjacent = first.copy(); adjacent[0] = np.nextafter(first[0], np.inf)
    checks["signed_zero_and_adjacent_binary64_distinguished"] = (
        candidate._binary64_key(signed) != candidate._binary64_key(first)
        and candidate._binary64_key(adjacent) != candidate._binary64_key(first))
    success_before = run_step(baseline, inputs, Portfolio().solve_default)
    success_after = run_step(candidate, inputs, Portfolio().solve_default, True)
    checks["successful_full_step_unchanged"] = (success_before["status"] == success_after["status"] == "accepted"
        and np.array_equal(success_before["velocity"], success_after["velocity"])
        and success_before["health"] == success_after["health"])
    # Exact fixed points must pass the original convergence test before lookup.
    stationary = {**inputs, "old_velocity": np.zeros(6)}
    fixed = run_step(candidate, stationary, Portfolio().solve_default, True)
    checks["fixed_point_accepted_before_cycle_lookup"] = (fixed["status"] == "accepted"
        and fixed["health"]["iterations"] == 1 and "cycle_guard" not in fixed["diagnostics"])
    captures = None
    input_hashes = {}
    if not args.manufactured_only:
        captured_inputs, record, input_hashes = rebuilt_capture(args.trace, args.seed, args.attempt_id)
        ordinary_portfolio, guarded_portfolio = compiled_portfolio(), compiled_portfolio()
        recovery = record["recovery_mode"]
        ordinary_solver = ordinary_portfolio.solve_recovery if recovery else ordinary_portfolio.solve_default
        guarded_solver = guarded_portfolio.solve_recovery if recovery else guarded_portfolio.solve_default
        ordinary = run_step(baseline, captured_inputs, ordinary_solver)
        shortened = run_step(candidate, captured_inputs, guarded_solver, True)
        old_rows = ordinary["diagnostics"]["contact_solves"]
        new_rows = shortened["diagnostics"]["contact_solves"]
        archived = record["inertial_diagnostics"]["contact_solves"]
        checks["captured_full_step_reproduces_archived_map"] = len(old_rows) == len(archived) == 80 and all(
            np.array_equal(row["updated_velocity_generalized"], archive["updated_velocity_generalized"])
            for row,archive in zip(old_rows,archived))
        checks["captured_guard_preserves_exact_solve_prefix"] = len(new_rows) < len(old_rows) and all(
            np.array_equal(one["updated_velocity_generalized"], two["updated_velocity_generalized"])
            and one["fixed_point_residual"] == two["fixed_point_residual"]
            for one,two in zip(old_rows,new_rows))
        checks["captured_guard_same_failure_with_exact_cycle"] = (ordinary["status"] == shortened["status"] == "rejected"
            and ordinary["reason"] == shortened["reason"] == "inertial/contact fixed point did not converge"
            and "cycle_guard" in shortened["diagnostics"])
        captures = {"attempt_id": record["attempt_id"], "original": ordinary, "guarded": shortened,
            "physical_step_inputs": captured_inputs, "original_work": ordinary_portfolio.stats(),
            "guarded_work": guarded_portfolio.stats(),
            "step_speedup": ordinary["wall_seconds"] / shortened["wall_seconds"]}
    final_hashes = sources()
    checks["source_files_stable"] = all(final_hashes.get(k) == v for k,v in initial_hashes.items())
    checks = {key: bool(value) for key,value in checks.items()}
    payload = {"passed": all(checks.values()), "checks": checks,
        "manufactured": {"baseline_cycle": unchecked, "disabled_cycle": disabled,
            "guarded_cycle": guarded, "near_cycle": near, "success_before": success_before,
            "success_after": success_after, "fixed_point": fixed}, "captured": captures,
        "source_hashes_before": initial_hashes, "source_hashes": final_hashes,
        "input_hashes": input_hashes, "arguments": vars(args),
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "claim": "exact rejection equivalence for explicitly deterministic stateless cold maps; no new physical acceptance"}
    payload["arguments"]["trace"] = str(payload["arguments"]["trace"])
    (output / "results.json").write_text(json.dumps(plain(payload), indent=2, allow_nan=False))
    (output / "completion.json").write_text(json.dumps({"status": "complete_passed" if payload["passed"] else "complete_failed",
        "results_sha256": sha(output / "results.json")}))
    print(json.dumps({"passed": payload["passed"], "checks": checks}, indent=2))
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
