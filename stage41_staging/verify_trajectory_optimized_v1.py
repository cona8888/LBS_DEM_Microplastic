"""Frozen manufactured and paired matrix checks for the Stage 41 candidate."""
import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path
import numpy as np
import scipy
import trajectory_optimized_v1 as candidate
import geometry_exact_v1
import trap_event_v3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage40_staging"))
import matrix_case_v1
import trajectory_cold_trap_v1 as baseline
from verify_trajectory_cached_trap_v1 import Field, Empty


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def loaded_sources():
    sources = {Path(__file__).resolve()}
    for module in list(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if path and Path(path).suffix == ".py" and Path(path).resolve().is_relative_to(ROOT):
            sources.add(Path(path).resolve())
    return {str(p): sha(p) for p in sorted(sources)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--fractions", type=float, nargs="+", default=[0.1, 0.05, 0.025])
    parser.add_argument("--frictions", type=float, nargs="+", default=[0.0, 0.3])
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    source_hashes_at_start = loaded_sources()
    checks, values, inputs = {}, {}, []
    if not args.matrix and not args.profile:
        dwell_times = []
        for dt in (0.02, 0.01, 0.005):
            monitor = trap_event_v3.TrapMonitor(1e-4, 5e-5, 0.2)
            for k in range(100):
                state = monitor.update(dt, np.zeros(3), np.zeros(6), [1, 2], [1])
                if state["trapped"]:
                    dwell_times.append((k+1)*dt)
                    break
        checks["three_level_full_dwell"] = all(0.2 <= t <= 0.221 for t in dwell_times) and len(dwell_times) == 3
        monitor = trap_event_v3.TrapMonitor(1e-4, 5e-5, 0.2)
        monitor.update(0.15, np.zeros(3), np.zeros(6), [1, 2], [1])
        changed = monitor.update(0.1, np.zeros(3), np.zeros(6), [1, 2], [2])
        checks["load_bearing_change_resets_clock"] = not changed["trapped"] and changed["elapsed_s"] == 0.1
        monitor = trap_event_v3.TrapMonitor(1e-4, 5e-5, 2.0)
        first = monitor.update(2.0, [2e-6, 0, 0], [1e-6, 0, 0, 0, 0, 0], [1], [1])
        checks["first_interval_motion_counted"] = not first["trapped"]
        monitor = trap_event_v3.TrapMonitor(1e-4, 5e-5, 2.0)
        spin = monitor.update(2.0, np.zeros(3), [0, 0, 0, 1e-6, 0, 0], [1], [1])
        checks["accumulated_rotation_counted"] = not spin["trapped"]
        try:
            monitor.update(float("nan"), np.zeros(3), np.zeros(6), [1], [1])
        except ValueError:
            checks["nonfinite_dwell_fails"] = True
        else:
            checks["nonfinite_dwell_fails"] = False
        common = dict(a=5e-5, b=5e-5, viscosity=0.001002, particle_density=1380,
                      fluid_density=998.2, added_mass_fraction=1, max_dt=0.01)
        exits = []
        for fraction in (0.2, 0.1, 0.05):
            exits.append(candidate.integrate(
                Field([0.001, 0, 0]), Empty(), [0, 0, 0], [1, 0, 0], np.zeros(6),
                gravity=[0, 0, 0], friction=0, outlet=1e-4, horizon=0.3,
                displacement_fraction=fraction, relaxation_fraction=fraction, **common))
        times = [row["time_s"] for row in exits]
        checks["uniform_three_level_exits"] = all(row["status"] == "full_window_exit" for row in exits)
        checks["uniform_fine_medium_shift"] = abs(times[-1]-times[-2])/times[-1] <= 0.002
        centre = np.array([0.005, 0.005, 0.005])
        geometry = geometry_exact_v1.GrainGeometry([[0.005, 0.00465, 0.005]], [3e-4], 0.01)
        supported = dict(gravity=[0, -9.80665, 0], friction=0.3,
                         outlet=0.009, horizon=0.05, trap_reference_speed=1e-4,
                         trap_dwell_time=0.02, **common)
        stationary = candidate.integrate(Field([0, 0, 0]), geometry, centre, [1, 0, 0], np.zeros(6), **supported)
        stopped = candidate.integrate(Field([0, 0, 0]), geometry, centre, [1, 0, 0], np.zeros(6), stop_on_trap=True, **supported)
        checks["dwell_is_nonabsorbing_default"] = (stationary["status"] == "present_at_horizon"
            and stationary["persistent_contact_observed"] and stationary["time_s"] == 0.05)
        checks["explicit_dwell_stop_named"] = stopped["status"] == "persistent_contact_dwell" and stopped["time_s"] >= 0.02
        checks["no_persisted_reactions"] = stationary["cached_reaction_count"] == 0 and stationary["last_reaction_count"] >= 1

        class SwitchedField:
            """Manufactured forcing switch by sample count; no physical timing claim."""
            def __init__(self):
                self.calls = 0
            def sample(self, position):
                self.calls += 1
                return (np.zeros(3) if self.calls <= 100 else np.array([0.01, 0.01, 0])), np.zeros((3, 3))

        resumed = candidate.integrate(SwitchedField(), geometry, centre, [1, 0, 0], np.zeros(6),
            **{**supported, "outlet": 0.0051, "horizon": 0.3, "trap_dwell_time": 0.001})
        checks["exit_after_observed_dwell"] = resumed["persistent_contact_observed"] and resumed["status"] == "full_window_exit"
        outside = candidate.integrate(Field([0.1, 0, 0]), Empty(), [0, 0, 0], [1, 0, 0], np.zeros(6),
            gravity=[0, 0, 0], friction=0, outlet=1e-4, horizon=0.01, **common)
        checks["reynolds_envelope_fails_closed"] = outside["status"] == "unresolved_model" and outside["max_reynolds"] > 3
        fast_initial = candidate.integrate(Field([0, 0, 0]), Empty(), [0, 0, 0], [1, 0, 0], [0.1, 0, 0, 0, 0, 0],
            gravity=[0, 0, 0], friction=0, outlet=1e-4, horizon=0.01, **common)
        checks["initially_fast_particle_censored"] = fast_initial["status"] == "unresolved_model" and fast_initial["steps"] == 0 and fast_initial["max_reynolds"] > 3

        class Plane:
            r = np.array([3e-4])
            def contacts(self, x, p, a, b, skin=0.):
                gap = float(x[0] - a)
                return [(0, gap, np.array([1.,0,0]), np.array([-a,0,0]))] if gap <= skin else []
            def swept_gap(self, x, p, v, a, b, dt):
                return min(x[0]-a, x[0]+dt*v[0]-a)

        # One slow, long implicit approach can generate a positive reaction at
        # first touch. Its positive initial gap must invalidate the dwell credit.
        approach = candidate.integrate(Field([-1e-5, 0, 0]), Plane(), [5.05e-5,0,0], [1,0,0], np.zeros(6),
            gravity=[0,0,0], friction=0, outlet=0.009, horizon=1.0,
            trap_reference_speed=1e-4, trap_dwell_time=0.5,
            **{**common, "max_dt":1.0, "displacement_fraction":1.0, "relaxation_fraction":1e6})
        checks["approach_interval_is_not_dwell"] = (approach["status"] == "present_at_horizon"
            and approach["steps"] == 1 and approach["contact_steps"] == 1
            and not approach["persistent_contact_observed"])
        single_exit = candidate.integrate(Field([0.001, 0, 0]), Empty(), [0, 0, 0], [1, 0, 0], np.zeros(6),
            gravity=[0, 0, 0], friction=0, outlet=1e-8, horizon=0.1,
            **{**common, "max_dt": 1.0, "displacement_fraction": 10.0, "relaxation_fraction": 100.0})
        checks["exit_step_health_recorded"] = single_exit["status"] == "full_window_exit" and single_exit["max_reynolds"] > 0
        rows = exits + [stationary, stopped, resumed, single_exit]
        checks["manufactured_clearance_and_closure"] = all(
            (row["minimum_gap_m"] is None or row["minimum_gap_m"] >= -5e-10)
            and row["max_momentum_residual"] <= 1e-8
            and row["max_contact_residual"] <= 1e-8 for row in rows)
        values.update(dwell_times_s=dwell_times, uniform_exit_times_s=times,
                      stationary=stationary, explicit_stop=stopped, resumed=resumed,
                      outside_envelope=outside, one_step_exit=single_exit)
        values.update(fast_initial=fast_initial, approach=approach)
    else:
        field, old_geometry, length, spacing, source_inputs = matrix_case_v1.load(2)
        inputs.extend(source_inputs)
        geometry = geometry_exact_v1.GrainGeometry.from_geometry(old_geometry)
        if args.profile:
            path = ROOT / "stage37_runs/stage4_farfield_bound_20260912/pilot_01/starts_s2.json"
            start = json.loads(path.read_text())[0]
            start["velocity_generalized"] = np.zeros(6)
            horizon = 0.02 * length / 1e-4
            fractions = (0.1,)
            frictions = (0.3,)
        else:
            path = ROOT / "stage39_evaluations/matrix_profile_01/results.json"
            start = json.loads(path.read_text())["result"]
            horizon = 0.02
            fractions = args.fractions
            frictions = args.frictions
        inputs.append(path)
        rows = []
        for friction in frictions:
            for fraction in fractions:
                pair = {}
                for label, solver, geom in (("baseline", baseline, old_geometry), ("candidate", candidate, geometry)):
                    result = solver.integrate(
                        field, geom, start["position_m"], start["orientation"], start["velocity_generalized"],
                        2e-4, 5e-5, 0.001002, 1380, 998.2, [0, 0, -9.80665], friction, length, horizon,
                        added_mass_fraction=1, cutoff_ratio=0.2, roughness_ratio=0.01,
                        displacement_fraction=fraction, relaxation_fraction=5*fraction,
                        max_dt=0.01, wall_budget=240, trap_reference_speed=1e-4,
                        trap_dwell_time=0.5)
                    pair[label] = result
                base, new = pair["baseline"], pair["candidate"]
                angle = float(np.arctan2(np.linalg.norm(np.cross(base["orientation"], new["orientation"])),
                                         np.dot(base["orientation"], new["orientation"])))
                delta = float(np.linalg.norm(np.array(base["position_m"])-new["position_m"]))
                name = f"mu{friction}_fraction{fraction}"
                checks[name+"_equivalent"] = (base["status"] == new["status"] == "present_at_horizon"
                    and delta <= 5e-7 and angle <= 1e-3
                    and abs(base["time_s"]-new["time_s"]) <= 0.002*horizon
                    and abs(base["minimum_gap_m"]-new["minimum_gap_m"]) <= 5e-10)
                checks[name+"_health"] = (new["minimum_gap_m"] >= -5e-10
                    and new["max_contact_residual"] <= 1e-8 and new["max_momentum_residual"] <= 1e-8
                    and new["max_reynolds"] <= 3)
                rows.append({"friction": friction, "fraction": fraction, "pair": pair,
                             "endpoint_shift_m": delta, "orientation_shift_rad": angle,
                             "speedup": base["runtime_seconds"]/new["runtime_seconds"]})
                print(json.dumps({"case": name, "status": new["status"], "shift_m": delta,
                                  "speedup": rows[-1]["speedup"]}), flush=True)
        convergence = []
        if args.matrix:
            if len(fractions) < 3 or any(f <= 0 for f in fractions) or any(
                    fractions[k+1] >= fractions[k] for k in range(len(fractions)-1)):
                raise ValueError("at least three positive decreasing refinement fractions required")
            for friction in frictions:
                cases = [row["pair"]["candidate"] for row in rows if row["friction"] == friction]
                shift = float(np.linalg.norm(np.array(cases[-1]["position_m"])-cases[-2]["position_m"])/5e-5)
                angle = float(np.arctan2(np.linalg.norm(np.cross(cases[-1]["orientation"], cases[-2]["orientation"])),
                                         np.dot(cases[-1]["orientation"], cases[-2]["orientation"])))
                convergence.append({"friction": friction, "fine_medium_shift_minor_radii": shift,
                                    "fine_medium_orientation_rad": angle})
                # These are observed solution-verification gates, separate from equivalence.
                checks[f"mu{friction}_replay_refinement"] = shift <= 0.01 and angle <= 1e-3
        values.update(rows=rows, convergence=convergence, spacing_m=spacing, horizon_s=horizon)
    final_hashes = loaded_sources()
    checks["source_files_stable_during_run"] = all(final_hashes.get(k) == v for k,v in source_hashes_at_start.items())
    result = {"passed": bool(all(checks.values())), "checks": {k: bool(v) for k,v in checks.items()},
              "values": values, "source_hashes": final_hashes,
              "source_hashes_at_start": source_hashes_at_start,
              "input_hashes": {str(p): sha(p) for p in inputs},
              "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
              "scope": "algorithm verification, finite dwell semantics and short-case cost; no physical release or campaign qualification"}
    (output / "results.json").write_text(json.dumps(result, indent=2))
    (output / "completion.json").write_text(json.dumps({"status": "complete_passed" if result["passed"] else "complete_failed", "results_sha256": sha(output/"results.json")}))
    print(json.dumps({"passed": result["passed"], "checks": result["checks"]}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
