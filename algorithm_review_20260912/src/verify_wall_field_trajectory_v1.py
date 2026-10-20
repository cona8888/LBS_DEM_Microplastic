"""Paired original/exact field samples through the unchanged default contact path."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np
import scipy

import trajectory_explicit_v1 as trajectory
import inertial_explicit_v1
from wall_field_exact_v1 import WallCellFieldExact

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage41_staging")]
import matrix_case_v1
import geometry_exact_v1


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources():
    paths = {Path(__file__).resolve()}
    for module in list(sys.modules.values()):
        value = getattr(module, "__file__", None)
        if value and Path(value).suffix == ".py" and Path(value).resolve().is_relative_to(ROOT):
            paths.add(Path(value).resolve())
    return {str(path): sha(path) for path in sorted(paths)}


class RecordedField:
    def __init__(self, field):
        self.field = field
        self.rows = []

    def sample(self, position):
        velocity, gradient = self.field.sample(position)
        self.rows.append(np.r_[position, velocity, gradient.ravel()])
        return velocity, gradient


class RecordedGeometry(geometry_exact_v1.GrainGeometry):
    def __init__(self, *args):
        super().__init__(*args)
        self.rows = []

    def contacts(self, x, p, a, b, skin=0.0):
        self.rows.append(np.r_[x, p, a, b, skin])
        return super().contacts(x, p, a, b, skin)


class RecordedContact(inertial_explicit_v1.ContactModel):
    def __init__(self):
        # Explicitly use Stage53 for both modes. No experimental recovery solver.
        super().__init__(trajectory.default_contact._solve)
        self.rows = []
        self.health = []

    def inertial_contact_step(self, *args, **kwargs):
        candidate, health = super().inertial_contact_step(*args, **kwargs)
        self.rows.append(np.r_[args[0], args[8], candidate])
        self.health.append(health)
        return candidate, health


def exact_array(a, b):
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--horizon", type=float, default=0.02)
    parser.add_argument("--budget", type=float, default=30.0)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    design = ROOT / "stage55_designs/paired_three_packing_pilot_v1.json"
    cfg = json.loads(design.read_text())
    hashes_before = sources()
    input_hashes = {str(design): sha(design)}
    started = datetime.now(timezone.utc).isoformat()
    overall_start = time.perf_counter()
    rows, checks = [], {}
    a, b, _ = cfg["prolate_semiaxes_m"]
    sphere = (a*b*b)**(1/3)
    for seed in args.seeds:
        baseline_field, old, length, spacing, paths = matrix_case_v1.load(
            seed, target_velocity=cfg["target_mean_interstitial_velocity_m_s"])
        fast_field = WallCellFieldExact.from_field(baseline_field)
        starts_path = ROOT / f"stage37_runs/stage4_farfield_bound_20260912/pilot_01/starts_s{seed}.json"
        start_id = next(item["start_id"] for item in cfg["packings"] if item["seed"] == seed)
        start = next(item for item in json.loads(starts_path.read_text()) if item["id"] == start_id)
        for path in (*paths, starts_path):
            input_hashes[str(path)] = sha(path)
        for shape, aa, bb in (("prolate_ar4", a, b), ("equal_volume_sphere", sphere, sphere)):
            name = f"s{seed}_{shape}"
            kwargs = dict(
                added_mass_fraction=cfg["added_mass_fraction"], cutoff_ratio=0.2, roughness_ratio=0.01,
                displacement_fraction=cfg["numerics"]["displacement_fraction"],
                relaxation_fraction=cfg["numerics"]["relaxation_fraction"],
                angle_limit=cfg["numerics"]["angle_limit_rad"], max_dt=cfg["numerics"]["max_dt_s"],
                wall_budget=args.budget, trap_reference_speed=cfg["target_mean_interstitial_velocity_m_s"],
                trap_dwell_time=cfg["trap"]["dwell_time_s"], trap_speed_ratio=cfg["trap"]["speed_ratio"],
                trap_drift_over_minor_radius=cfg["trap"]["drift_over_minor_radius"],
                stop_on_trap=cfg["trap"]["absorbing"], reynolds_limit=cfg["numerics"]["reynolds_limit"],
            )
            data, traces = {}, {}
            order = ("baseline", "candidate") if len(rows) % 2 == 0 else ("candidate", "baseline")
            for kind in order:
                field = RecordedField(baseline_field if kind == "baseline" else fast_field)
                geometry = RecordedGeometry.from_geometry(old)
                contact = RecordedContact()
                result = trajectory.integrate(
                    field, geometry, start["position_m"], start["orientation"], np.zeros(6), aa, bb,
                    cfg["dynamic_viscosity_Pa_s"], cfg["particle_density_kg_m3"], cfg["fluid_density_kg_m3"],
                    cfg["gravity_m_s2"], cfg["friction_coefficient"], length, args.horizon,
                    **kwargs, contact_model=contact)
                trace = {"field": np.asarray(field.rows), "geometry": np.asarray(geometry.rows),
                         "contact": np.asarray(contact.rows)}
                np.savez_compressed(args.output / f"{name}_{kind}_trace.npz", **trace)
                health_text = json.dumps(contact.health, sort_keys=True)
                (args.output / f"{name}_{kind}_contact_health.json").write_text(health_text)
                data[kind] = result
                traces[kind] = {**trace, "contact_health_json": health_text}
            base, fast = data["baseline"], data["candidate"]
            compared_keys = sorted(set(base) | set(fast) - {"runtime_seconds"})
            compared_keys = [key for key in compared_keys if key != "runtime_seconds"]
            case_checks = {
                "complete": all(result["status"] == "present_at_horizon" and result["time_s"] == args.horizon
                                for result in data.values()),
                "all_result_values_exact_except_runtime": all(base.get(key) == fast.get(key) for key in compared_keys),
                "all_field_values_and_positions_bitwise_exact": exact_array(traces["baseline"]["field"], traces["candidate"]["field"]),
                "all_geometry_query_poses_bitwise_exact": exact_array(traces["baseline"]["geometry"], traces["candidate"]["geometry"]),
                "all_contact_trial_velocities_and_dt_bitwise_exact": exact_array(traces["baseline"]["contact"], traces["candidate"]["contact"]),
                "every_contact_trial_health_exact": traces["baseline"]["contact_health_json"] == traces["candidate"]["contact_health_json"],
                "recovery_unused": all(result["solver_selection_stats"]["recovery_steps"] == 0 for result in data.values()),
                "physical_health": all(
                    (result["minimum_gap_m"] is None or result["minimum_gap_m"] >= -1e-5*bb)
                    and all(result[key] <= 1e-8 for key in ("max_contact_residual", "max_force_residual", "max_momentum_residual"))
                    and result["max_reynolds"] <= cfg["numerics"]["reynolds_limit"] for result in data.values()),
            }
            checks.update({f"{name}:{key}": value for key, value in case_checks.items()})
            row = {"name": name, "packing_seed": seed, "shape": shape, "start": start,
                   "semiaxes_m": [aa, bb, bb], "initial_velocity": [0.0]*6, "outlet_m": length,
                   "spacing_m": spacing, "horizon_s": args.horizon, "options": kwargs,
                   "checks": case_checks, "run_order": order, "compared_result_keys": compared_keys,
                   "trace_counts": {key: len(traces["baseline"][key]) for key in ("field", "geometry", "contact")},
                   "baseline": base, "candidate": fast}
            rows.append(row)
            (args.output / f"{name}.json").write_text(json.dumps(row, indent=2))
            print(json.dumps({"case": name, "passed": all(case_checks.values()), "steps": fast["steps"],
                              "baseline_s": base["runtime_seconds"], "candidate_s": fast["runtime_seconds"],
                              "trace_counts": row["trace_counts"]}), flush=True)
            if not case_checks["complete"]:
                break
        if time.perf_counter() - overall_start > 45 or not all(checks.values()):
            break
    hashes_after = sources()
    checks["source_hashes_stable"] = hashes_before == hashes_after
    checks["input_hashes_stable"] = all(sha(path) == value for path, value in input_hashes.items())
    checks["all_requested_cases_executed"] = len(rows) == 2*len(args.seeds)
    result = {
        "passed": all(checks.values()), "checks": checks, "rows": rows,
        "source_hashes_before": hashes_before, "source_hashes_after": hashes_after, "input_hashes": input_hashes,
        "resolved_arguments": {**vars(args), "output": str(args.output)}, "physical_config": cfg,
        "started_utc": started, "completed_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "scope": "Paired field implementation equivalence for short real-packing paths; all contact solvers Stage53. Concurrent host work makes timing descriptive only; no speed or physical-validation claim.",
    }
    path = args.output / "results.json"
    path.write_text(json.dumps(result, indent=2))
    (args.output / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if result["passed"] else "complete_failed", "results_sha256": sha(path)}, indent=2))
    print(json.dumps({"passed": result["passed"], "cases": len(rows), "source_hashes_stable": checks["source_hashes_stable"]}), flush=True)
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
