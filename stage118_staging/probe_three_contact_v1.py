"""Non-advancing, source-bound local diagnosis of the Stage117 failed episode."""
from __future__ import annotations
import argparse
import copy
import inspect
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage117_staging"))
import longer_sentinels_v1 as previous
api = previous.api
BASE = "three_contact_diagnosis_20260916"
DESIGN = ROOT / "stage118_designs" / BASE / "design_01.json"
RUN = ROOT / "stage118_runs" / BASE / "local_probe_01"
EVAL = ROOT / "stage118_evaluations" / BASE
SEAL = previous.EVAL / "completion.json"
CASE = "s1_ar4_f1p0_cpd2_dt1_h0p5"
FAILED = previous.RUN / CASE / "segment_02/record.json"
DENSE = FAILED.parent / "accepted_intervals.json"
CORE = api.frozen.core
RECOVERY = api.frozen.parent


def prepare():
    api.require(not DESIGN.exists(), "immutable design exists")
    previous.verify(api.read(previous.DESIGN))
    api.verify_mapping(api.read(SEAL)["artifacts"])
    spec = next(s for s in api.read(previous.DESIGN)["cases"] if s["case_id"] == CASE)
    failed = api.read(FAILED)["result"]
    rows = api.read(DENSE)
    before = rows[-2]
    state = lambda r: {k: copy.deepcopy(r[k]) for k in ["position_m", "orientation", "velocity_generalized", "time_s"]}
    scenarios = [
        {"id": "accepted_control", "state": state(before), "dt_mode": "explicit", "dt_s": rows[-1]["dt_s"], "expected_velocity": rows[-1]["velocity_generalized"], "expected_pose": state(rows[-1])},
        {"id": "failed_remaining", "state": state(failed), "dt_mode": "remaining", "factor": 1.},
        {"id": "failed_half", "state": state(failed), "dt_mode": "remaining", "factor": .5},
        {"id": "failed_retry10", "state": state(failed), "dt_mode": "remaining", "factor": 2.**-10},
        {"id": "failed_retry29", "state": state(failed), "dt_mode": "remaining", "factor": 2.**-29},
        {"id": "failed_without_endpoint_clip", "state": state(failed), "dt_mode": "unclipped"},
    ]
    sources = {str(Path(m.__file__).resolve()): api.sha(m.__file__) for m in list(sys.modules.values()) if getattr(m, "__file__", None) and Path(m.__file__).suffix == ".py" and ROOT in Path(m.__file__).resolve().parents}
    sources.update({str(p.resolve()): api.sha(p) for p in Path(__file__).parent.glob("*.py")})
    d = {"stage": "Stage118", "question": "Which local solver rejects the saved three-contact state, and is endpoint step clipping implicated?",
        "spec": spec, "scenarios": scenarios, "recovery_mode": True, "physical_changes": [],
        "contract": "One frozen-pose inertial/contact solve per scenario, under the identical Stage104/89/81/80/79 solver wrappers. No physical time, position, orientation, geometry, field or trajectory checkpoint is advanced or committed.",
        "acceptance": {"accepted_control_velocity_absolute_max": 1e-20, "accepted_control_pose_absolute_max": 1e-18, "contact_residual_max": 1e-10, "momentum_max": 1e-8, "force_max": 1e-8,
            "interpretation": "Expected solver failures are diagnostic outcomes. A successful algebraic candidate is not an accepted trajectory, retention event, or resolution pass."},
        "budget": {"max_local_step_calls": 6, "dispatch_wall_s": 300., "maximum_original_inner_iterations": 80,
            "hard_interrupt": False, "rule": "Stop further dispatch if budget expired; original solver internal ceilings retained. No auto retries or trajectory continuation."},
        "inputs": {str(SEAL): api.sha(SEAL), str(FAILED): api.sha(FAILED), str(DENSE): api.sha(DENSE), str(previous.DESIGN): api.sha(previous.DESIGN)},
        "source_hashes": sources,
        "claim_boundary": "Local numerical failure diagnosis only. No empirical validation, model revision, population release or new physics."}
    d["binding"] = api.digest(d)
    DESIGN.parent.mkdir(parents=True, exist_ok=True)
    api.write(DESIGN, d)
    print("FROZEN", api.sha(DESIGN), flush=True)


def verify(d):
    api.require(d["binding"] == api.digest({k: v for k, v in d.items() if k != "binding"}), "design self-binding drift")
    api.verify_mapping(d["source_hashes"])
    api.verify_mapping(d["inputs"])
    api.verify_mapping(api.read(SEAL)["artifacts"])
    previous.verify(api.read(previous.DESIGN))
    expected = next(s for s in api.read(previous.DESIGN)["cases"] if s["case_id"] == CASE)
    api.require(d["spec"] == expected and d["physical_changes"] == [], "physical model drift")
    api.require(len(d["scenarios"]) == d["budget"]["max_local_step_calls"] == 6, "probe matrix drift")


def matrix_diagnostics(v, M, J, g, dt):
    A = J @ M @ J.T
    singular = np.linalg.svd(A, compute_uv=False)
    rank = int(np.linalg.matrix_rank(A))
    return {"system_condition_2": float(np.linalg.cond(np.linalg.inv(M))), "mobility_condition_2": float(np.linalg.cond(M)),
        "jacobian_rank": int(np.linalg.matrix_rank(J)), "delassus_rank": rank, "delassus_dimension": len(A),
        "delassus_singular_values": singular, "delassus_nonzero_condition": float(singular[0] / singular[rank-1]) if rank else None,
        "free_speed_scale_m_s": max(float(np.linalg.norm(v)), 1e-15), "gap_over_dt_m_s": g / dt,
        "gap_m": g, "warning": "For three contacts the 9x9 Delassus matrix has rank at most six by construction; singularity alone is not a diagnosis."}


def finish_metrics(args):
    v, M, J, f, z, A, g, dt, mu, steps, iterations, solver, extra = args
    vc = z + A @ f
    scale = max(float(np.linalg.norm(v)), 1e-15)
    normal = vc[::3] + g / dt
    projection_terms = []
    for k in range(len(g)):
        i = 3*k
        trial = f[i+1:i+3] - vc[i+1:i+3] / steps[k]
        projected = trial * min(1., mu*f[i] / max(np.linalg.norm(trial), 1e-300))
        projection_terms.append(float(np.linalg.norm(f[i+1:i+3] - projected) * steps[k]))
    residual = max([abs(min(A[3*k, 3*k]*f[3*k], normal[k])) for k in range(len(g))] + projection_terms)
    velocity = v + M @ J.T @ f
    load = J.T @ f
    closure = np.linalg.norm(np.linalg.solve(M, velocity-v) - load) / max(np.linalg.norm(load), 1e-30)
    work = sum(float(f[3*k+1:3*k+3] @ vc[3*k+1:3*k+3]) for k in range(len(g)))
    cone_margin = [float(mu*f[3*k] - np.linalg.norm(f[3*k+1:3*k+3])) for k in range(len(g))]
    return {"solver": solver, "iterations": int(iterations), "normalized_residual": float(residual/scale),
        "force_closure": float(closure), "normal_reactions": f[::3], "coulomb_margin_N": cone_margin,
        "normal_velocity_plus_gap_rate_m_s": normal, "tangential_contact_velocity_m_s": vc.reshape(-1, 3)[:, 1:],
        "friction_work_W": float(work), "free_speed_scale_m_s": scale, "force": f, "extra": extra}


def local_driver(scenario, *args, **kwargs):
    """Assemble exactly one original step and call its frozen solver; no integrator."""
    inputs = inspect.signature(CORE.integrate).bind(*args, **kwargs)
    inputs.apply_defaults()
    c = inputs.arguments
    inertial = api.frozen.oldcore.inertial
    mechanics = CORE.mechanics
    field, geometry = c["field"], c["geometry"]
    s = scenario["state"]
    x, p, q = [np.asarray(s[k], float) for k in ["position_m", "orientation", "velocity_generalized"]]
    a, b, mu = c["a"], c["b"], c["viscosity"]
    fluid_velocity, gradient = field.sample(x)
    background, _ = mechanics.free_motion(p, gradient, fluid_velocity, a, b, mu, 1., 1., [0, 0, 0])
    resistance = inertial.stokes_generalized_resistance(p, a, b, mu)
    mass, _ = inertial.generalized_mass_matrix(p, a, b, c["particle_density"], c["fluid_density"], c["added_mass_fraction"])
    mass[3:, 3:] = 0.
    volume = 4*np.pi*a*b*b/3
    body = np.r_[(c["particle_density"]-c["fluid_density"])*volume*mechanics.finite(c["gravity"]), np.zeros(3)]
    near = CORE.enrich(geometry, geometry.contacts(x, p, a, b, c["cutoff_ratio"]*float(np.max(geometry.r))))
    lub, lub_rows = CORE.lubrication_matrix(near, p, a, b, a, mu, c["cutoff_ratio"], c["roughness_ratio"])
    translation = max(np.linalg.norm(q[:3]), np.linalg.norm(background[:3]), np.linalg.norm(body[:3])/max(np.linalg.eigvalsh(resistance[:3, :3]).min(), 1e-30), 1e-30)
    rotation = max(np.linalg.norm(q[3:]), np.linalg.norm(background[3:]), 1e-30)/a
    relaxation = np.linalg.eigvalsh(mass[:3, :3]).min()/np.linalg.eigvalsh(resistance[:3, :3]).max()
    caps = {"maximum_s": c["max_dt"], "remaining_s": c["horizon"]-s["time_s"], "translation_s": c["displacement_fraction"]*b/translation,
            "rotation_s": c["angle_limit"]/rotation, "relaxation_s": c["relaxation_fraction"]*relaxation}
    original_dt = min(caps.values())
    unclipped = min(v for k, v in caps.items() if k != "remaining_s")
    dt = scenario["dt_s"] if scenario["dt_mode"] == "explicit" else (unclipped if scenario["dt_mode"] == "unclipped" else original_dt*scenario["factor"])
    active = geometry.contacts(x, p, a, b, (translation+a*rotation)*dt+1e-5*b)
    snapshots = []
    finishes = []
    portfolio = RECOVERY.portfolio
    gate = RECOVERY.s
    old_solve, old_finish = portfolio._solve, gate._finish

    def traced_solve(v, M, J, g, dt, friction, tol, maxiter):
        row = {"vfree": v.copy(), "mobility": M.copy(), "jacobian": J.copy(), "gaps": g.copy(), "dt_s": dt,
               "friction": friction, "tol": tol, "maxiter": maxiter, "matrices": matrix_diagnostics(v, M, J, g, dt)}
        snapshots.append(row)
        start = time.perf_counter()
        try:
            answer = old_solve(v, M, J, g, dt, friction, tol, maxiter)
            row.update(status="returned", candidate=answer[0], health=answer[1])
            return answer
        except Exception as exc:
            row.update(status="raised", exception_type=type(exc).__name__, exception=str(exc))
            raise
        finally:
            row["runtime_s"] = time.perf_counter()-start

    def traced_finish(*args):
        row = finish_metrics(args)
        finishes.append(row)
        try:
            value = old_finish(*args)
            row.update(status="accepted_by_original_gate")
            return value
        except Exception as exc:
            row.update(status="rejected_by_original_gate", exception=str(exc))
            raise

    started = time.perf_counter()
    result = {"scenario": scenario["id"], "pose_advanced": False, "time_advanced": False,
        "dt_s": dt, "controller_caps_s": caps, "unclipped_dt_s": unclipped, "original_dt_s": original_dt,
        "active_contacts": api.normalized(active), "input_pose": s, "background": background, "mass": mass,
        "stokes_resistance": resistance, "lubrication_resistance": lub, "body_load": body,
        "contact_systems": snapshots, "finish_candidates": finishes, "lubrication_rows": lub_rows}
    inertial.set_recovery_mode(True)
    portfolio._solve, gate._finish = traced_solve, traced_finish
    try:
        velocity, health = inertial.inertial_contact_step(q, background, body, resistance, lub, mass, active, a, dt,
            c["friction"], c["fluid_density"], mu, 2*(a*b*b)**(1/3), inertial.finite_re.prolate_sphericity(a, b))
        result.update(status="solver_returned", velocity=velocity, health=health)
        # Calculate candidate checks without accepting or committing a trajectory.
        result["candidate_motion_caps_pass"] = bool(np.linalg.norm(velocity[:3])*dt <= 1.1*c["displacement_fraction"]*b and np.linalg.norm(velocity[3:])*dt/a <= 1.1*c["angle_limit"])
        ref_gap = previous.candidate._reference_sweep(geometry, x, p, velocity, a, b, dt)
        fast_gap = previous.candidate.swept_gap(geometry, x, p, velocity, a, b, dt)
        result["candidate_sweep"] = {"reference_gap_m": ref_gap, "pruned_gap_m": fast_gap, "identical": ref_gap == fast_gap, "clearance_pass": min(ref_gap, fast_gap) >= -1e-5*b}
        if scenario["id"] == "accepted_control":
            end_x, end_p = mechanics.advance_pose(x, p, velocity, a, dt)
            result["positive_control"] = {"velocity_max_absolute_error": float(np.max(np.abs(velocity-scenario["expected_velocity"]))),
                "position_max_absolute_error": float(np.max(np.abs(end_x-scenario["expected_pose"]["position_m"]))),
                "axis_max_absolute_error": float(np.max(np.abs(end_p-scenario["expected_pose"]["orientation"]))) }
    except RuntimeError as exc:
        result.update(status="solver_raised", exception_type=type(exc).__name__, exception=str(exc))
    finally:
        portfolio._solve, gate._finish = old_solve, old_finish
        result["runtime_s"] = time.perf_counter()-started
    return result


def execute(spec, scenario):
    field, data, metadata = api.fields.load(spec["seed"], spec["flow_factor"], spec["cpd"])
    api.require(metadata == spec["field_metadata"], "field metadata drift")
    geometry = api.frozen.h.geometry_exact_v1.GrainGeometry(data["sand_centres_m"], data["sand_radii_m"], metadata["cell_length_m"])
    field_before = api.hashlib.sha256(field.u.tobytes()).hexdigest()
    old = api.frozen.oldcore.integrate
    class ProbeDispatch:
        @staticmethod
        def integrate(*args, **kwargs):
            api.frozen.oldcore.integrate = lambda *a, **kw: local_driver(scenario, *a, **kw)
            try:
                return RECOVERY.integrate(*args, **kwargs)
            finally:
                api.frozen.oldcore.integrate = old
    result = api.dispatch(ProbeDispatch, spec, field, geometry, wall_budget=45.)
    api.require(api.hashlib.sha256(field.u.tobytes()).hexdigest() == field_before, "field mutated")
    return api.normalized(result)


def worker(name):
    d = api.read(DESIGN)
    verify(d)
    scenario = next(s for s in d["scenarios"] if s["id"] == name)
    out = RUN / name
    api.require(not out.exists(), "immutable worker exists")
    out.mkdir(parents=True)
    api.write(out / "launch.json", {"design_sha256": api.sha(DESIGN), "pid": os.getpid(), "command": sys.argv, "python": sys.version})
    try:
        result = execute(d["spec"], scenario)
        verify(d)
        api.write(out / "record.json", {"design_sha256": api.sha(DESIGN), "result": result}, raw=True)
        api.write(out / "completion.json", {"record_sha256": api.sha(out / "record.json"), "launch_sha256": api.sha(out / "launch.json")})
        print(name, result["status"], result.get("exception"), result["runtime_s"], flush=True)
    except Exception as exc:
        api.write(out / "failure.json", {"error": repr(exc), "traceback": traceback.format_exc()})
        raise


def run():
    d = api.read(DESIGN)
    verify(d)
    api.require(not RUN.exists(), "immutable local probe exists")
    RUN.mkdir(parents=True)
    env = os.environ.copy()
    env.update(OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", OMP_NUM_THREADS="1", PYTHONDONTWRITEBYTECODE="1")
    api.write(RUN / "manifest.json", {"design_sha256": api.sha(DESIGN), "order": [s["id"] for s in d["scenarios"]], "command": sys.argv, "pid": os.getpid(), "python": sys.version})
    started = time.perf_counter()
    records = {}
    try:
        for scenario in d["scenarios"]:
            name = scenario["id"]
            api.require(time.perf_counter()-started < d["budget"]["dispatch_wall_s"], "dispatch budget expired")
            with (RUN / (name+".stdout.txt")).open("x") as out, (RUN / (name+".stderr.txt")).open("x") as err:
                child = subprocess.run([sys.executable, "-B", "-u", __file__, "worker", "--case", name], stdout=out, stderr=err, env=env)
            api.require(child.returncode == 0, "diagnostic software failure: "+name)
            path = RUN / name / "record.json"
            records[name] = api.sha(path)
            r = api.read(path)["result"]
            print(name, r["status"], r.get("exception"), round(r["runtime_s"], 3), flush=True)
            if name == "accepted_control":
                p = r.get("positive_control", {})
                api.require(r["status"] == "solver_returned" and p.get("velocity_max_absolute_error", 1.) <= d["acceptance"]["accepted_control_velocity_absolute_max"] and p.get("position_max_absolute_error", 1.) <= d["acceptance"]["accepted_control_pose_absolute_max"] and p.get("axis_max_absolute_error", 1.) <= d["acceptance"]["accepted_control_pose_absolute_max"], "positive-control reproduction failed")
        api.write(RUN / "completion.json", {"design_sha256": api.sha(DESIGN), "manifest_sha256": api.sha(RUN / "manifest.json"), "records": records, "wall_s": time.perf_counter()-started})
    except Exception as exc:
        api.write(RUN / "failure.json", {"error": repr(exc), "traceback": traceback.format_exc(), "records": records})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "run", "worker"])
    parser.add_argument("--case")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    elif args.action == "run":
        run()
    else:
        worker(args.case)
