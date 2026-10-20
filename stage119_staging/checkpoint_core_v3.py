"""Stage119 versioned checkpoint core: explicit retry evidence and safe budgets.

Stage68 preserves the Stage41 equations. An explicit local contact rejection
or inertial/contact fixed-point nonconvergence halves the step and enables the
Stage67 portfolio until the active contact neighborhood clears. Other failures
remain fail closed.
"""
import sys, time, json, hashlib, copy
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage37_staging"), str(ROOT / "stage38_staging"),
                str(ROOT / "stage39_staging"), str(ROOT / "stage40_staging"),
                str(ROOT / "stage41_staging")]
import transport_contact as mechanics
import geometry_exact_v1 as geometry_tools
import lubrication_contact_v1 as lubrication
import inertial_contact_cold_optimized_v1 as inertial
import trap_event_v3 as trap_event_v2


def enrich(geometry, contacts):
    return [(*contact, float(geometry.r[contact[0]])) if len(contact) == 4 else contact
            for contact in contacts]


def lubrication_matrix(near, orientation, a, b, ell, viscosity,
                       cutoff_ratio, roughness_ratio):
    matrix = np.zeros((6, 6))
    rows = []
    for grain, gap, normal, lever, radius in near:
        curvature = lubrication.prolate_principal_curvatures(lever, orientation, a, b)
        prefactor = lubrication.squeeze_prefactor(viscosity, radius, curvature)
        cutoff = cutoff_ratio * radius
        roughness = roughness_ratio * radius
        coefficient = lubrication.matched_excess_resistance(gap, cutoff, roughness, prefactor)
        jacobian = lubrication.normal_jacobian(normal, lever, ell)
        matrix += coefficient * np.outer(jacobian, jacobian)
        rows.append({"grain_id": int(grain), "gap": float(gap),
                     "grain_radius": radius, "coefficient": coefficient})
    return matrix, rows


def integrate(field, geometry, position, orientation, velocity, a, b, viscosity,
              particle_density, fluid_density, gravity, friction, outlet, horizon,
              added_mass_fraction=0.0, cutoff_ratio=0.2, roughness_ratio=0.01,
              displacement_fraction=0.1, angle_limit=0.02,
              relaxation_fraction=0.5, max_dt=1.0, max_steps=500000,
              wall_budget=120.0, trap_reference_speed=None, trap_dwell_time=None,
              trap_speed_ratio=0.01, trap_drift_over_minor_radius=0.02,
              stop_on_trap=False, reynolds_limit=3.0, checkpoint=None,
              checkpoint_binding=None, pause_after_steps=None):
    controls = (a, b, viscosity, particle_density, fluid_density, outlet, horizon,
                cutoff_ratio, roughness_ratio, displacement_fraction, angle_limit,
                relaxation_fraction, max_dt, wall_budget, reynolds_limit)
    if not np.isfinite(controls).all() or min(controls) <= 0:
        raise ValueError("finite positive dimensions, physical and numerical scales required")
    if a < b or roughness_ratio >= cutoff_ratio:
        raise ValueError("prolate axes and roughness below cutoff required")
    if not np.isfinite(friction) or friction < 0 or not np.isfinite(added_mass_fraction) or added_mass_fraction < 0:
        raise ValueError("finite nonnegative friction and added-mass fraction required")
    if max_steps < 1 or int(max_steps) != max_steps:
        raise ValueError("positive integer max_steps required")
    x = mechanics.finite(position).copy()
    p = mechanics.unit(orientation)
    q = mechanics.finite(velocity).copy()
    if x.shape != (3,) or p.shape != (3,) or q.shape != (6,):
        raise ValueError("three-dimensional pose and six-dimensional velocity required")
    t = 0.0
    steps = rejected = contact_steps = contact_solver_retries = 0
    started = time.perf_counter()
    minimum_gap = np.inf
    minimum_gap_ratio = np.inf
    max_momentum = max_contact_residual = max_force_residual = max_reynolds = 0.0
    max_near = max_active = max_contact_iterations = total_contact_iterations = 0
    history = []
    rejected_trials = []
    pending_trial = None
    tolerance = 1e-5 * b
    equivalent_diameter = 2 * (a*b*b)**(1/3)
    sphericity = inertial.finite_re.prolate_sphericity(a, b)
    maximum_grain_radius = float(np.max(geometry.r))
    last_reaction_count = 0
    persistent_contact_observed = False
    first_contact_dwell_time = None
    monitor = None
    if (trap_reference_speed is None) != (trap_dwell_time is None):
        raise ValueError("trap reference speed and dwell time must be supplied together")
    if trap_reference_speed is not None:
        monitor = trap_event_v2.TrapMonitor(
            trap_reference_speed, b, trap_dwell_time,
            speed_ratio=trap_speed_ratio,
            drift_over_minor_radius=trap_drift_over_minor_radius,
        )
    last_trap_state = None


    if not isinstance(checkpoint_binding,str) or not checkpoint_binding:
        raise ValueError("explicit immutable checkpoint binding required")
    def encoded(value):
        return json.dumps(value,sort_keys=True,default=lambda z: z.tolist() if isinstance(z,np.ndarray) else z.item(),allow_nan=True)
    def digest(value):
        return hashlib.sha256(encoded(value).encode()).hexdigest()
    contract = [checkpoint_binding, a,b,viscosity,particle_density,fluid_density,list(gravity),
                friction,outlet,horizon,added_mass_fraction,cutoff_ratio,roughness_ratio,
                displacement_fraction,angle_limit,relaxation_fraction,max_dt,
                trap_reference_speed,trap_dwell_time,trap_speed_ratio,
                trap_drift_over_minor_radius,stop_on_trap,reynolds_limit]
    if checkpoint is not None:
        if checkpoint["schema"] != 1 or checkpoint["contract"] != digest(contract) or checkpoint["state_sha256"] != digest(checkpoint["state"]):
            raise ValueError("checkpoint binding or integrity mismatch")
        state = copy.deepcopy(checkpoint["state"])
        x,p,q = (np.asarray(state[k],float) for k in ("x","p","q"))
        t = state["t"]
        steps = state["steps"]
        rejected = state["rejected"]
        contact_steps = state["contact_steps"]
        contact_solver_retries = state["contact_solver_retries"]
        minimum_gap = state["minimum_gap"]
        minimum_gap_ratio = state["minimum_gap_ratio"]
        max_momentum = state["max_momentum"]
        max_contact_residual = state["max_contact_residual"]
        max_force_residual = state["max_force_residual"]
        max_reynolds = state["max_reynolds"]
        max_near = state["max_near"]
        max_active = state["max_active"]
        max_contact_iterations = state["max_contact_iterations"]
        total_contact_iterations = state["total_contact_iterations"]
        history = state["history"]
        rejected_trials = state.get("rejected_trials", [])
        pending_trial = state.get("pending_trial")
        last_reaction_count = state["last_reaction_count"]
        persistent_contact_observed = state["persistent_contact_observed"]
        first_contact_dwell_time = state["first_contact_dwell_time"]
        last_trap_state = state["last_trap_state"]
        if monitor is not None:
            monitor.__dict__.update(state["monitor"])
            if monitor.anchor is not None: monitor.anchor = np.asarray(monitor.anchor,float)
            monitor.contact_ids = tuple(monitor.contact_ids)
            monitor.load_bearing_ids = tuple(monitor.load_bearing_ids)
        inertial.set_recovery_mode(state["recovery"])
    def snapshot():
        state = {"x": x, "p": p, "q": q, "t": t, "steps": steps, "rejected": rejected, "contact_steps": contact_steps, "contact_solver_retries": contact_solver_retries, "minimum_gap": minimum_gap, "minimum_gap_ratio": minimum_gap_ratio, "max_momentum": max_momentum, "max_contact_residual": max_contact_residual, "max_force_residual": max_force_residual, "max_reynolds": max_reynolds, "max_near": max_near, "max_active": max_active, "max_contact_iterations": max_contact_iterations, "total_contact_iterations": total_contact_iterations, "history": history, "last_reaction_count": last_reaction_count, "persistent_contact_observed": persistent_contact_observed, "first_contact_dwell_time": first_contact_dwell_time, "last_trap_state": last_trap_state}
        state["rejected_trials"] = copy.deepcopy(rejected_trials)
        state["pending_trial"] = copy.deepcopy(pending_trial)
        state["monitor"] = None if monitor is None else copy.deepcopy(monitor.__dict__)
        state["recovery"] = bool(inertial.recovery_mode())
        return {"schema":1,"contract":digest(contract),"state":state,"state_sha256":digest(state)}

    def record_dwell(interval, endpoint, end_orientation, candidate, active, health):
        nonlocal last_trap_state, persistent_contact_observed, first_contact_dwell_time
        if monitor is None or interval <= 0:
            return False
        bearing = health["load_bearing_grain_ids"]
        # Positive implicit reactions can anticipate contact at the step end.
        # Do not count that approach interval as sustained contact. Both sampled
        # endpoints must support every bearing contact within geometry tolerance.
        touching_start = {contact[0] for contact in active if contact[1] <= tolerance}
        supported = bool(bearing) and set(bearing).issubset(touching_start)
        if supported:
            touching_end = {contact[0] for contact in geometry.contacts(
                endpoint, end_orientation, a, b, tolerance)}
            supported = set(bearing).issubset(touching_end)
        last_trap_state = monitor.update(
            interval, endpoint, candidate, [contact[0] for contact in active],
            bearing if supported else [])
        if last_trap_state["persistent_contact_observed"]:
            persistent_contact_observed = True
            if first_contact_dwell_time is None:
                first_contact_dwell_time = t + interval
            return True
        return False

    def finish(status, reason=None):
        return {
            "status": status, "reason": reason, "time_s": t,
            "checkpoint": snapshot(),
            "rejected_trials": copy.deepcopy(rejected_trials),
            "position_m": x.tolist(), "orientation": p.tolist(),
            "velocity_generalized": q.tolist(), "steps": steps, "rejected": rejected,
            "minimum_gap_m": None if not np.isfinite(minimum_gap) else minimum_gap,
            "minimum_gap_over_grain_radius": None if not np.isfinite(minimum_gap_ratio) else minimum_gap_ratio,
            "max_momentum_residual": max_momentum,
            "max_contact_residual": max_contact_residual,
            "max_force_residual": max_force_residual,
            "max_reynolds": max_reynolds,
            "max_lubrication_contacts": max_near,
            "max_active_contacts": max_active,
            "contact_steps": contact_steps,
            "contact_solver_retries": contact_solver_retries,
            "max_contact_iterations_per_nonlinear_solve": max_contact_iterations,
            "total_contact_iterations": total_contact_iterations,
            "cached_reaction_count": 0,
            "last_reaction_count": last_reaction_count,
            "reaction_policy": "discard_between_all_solves",
            "persistent_contact_observed": persistent_contact_observed,
            "first_contact_dwell_time_s": first_contact_dwell_time,
            "dwell_is_absorbing": bool(stop_on_trap),
            "observable": "conditional whole-body periodic-window passage",
            "reynolds_limit": reynolds_limit,
            "trap_state": last_trap_state,
            "runtime_seconds": time.perf_counter() - started,
            "history": history,
        }

    try:
        while t < horizon:
            if pause_after_steps is not None and steps >= pause_after_steps:
                return finish("paused_checkpoint")
            if steps >= max_steps or time.perf_counter() - started > wall_budget:
                return finish("incomplete_budget")
            initial = geometry.contacts(x, p, a, b, 0.0)
            if initial and min(contact[1] for contact in initial) < -tolerance:
                raise RuntimeError("inadmissible penetration")
            fluid_velocity, gradient = field.sample(x)
            background, _ = mechanics.free_motion(p, gradient, fluid_velocity, a, b,
                                                   viscosity, 1.0, 1.0, [0, 0, 0])
            initial_reynolds = inertial.finite_re.reynolds_number(
                q[:3] - background[:3], fluid_density, viscosity, equivalent_diameter)
            max_reynolds = max(max_reynolds, initial_reynolds)
            if max_reynolds > reynolds_limit:
                return finish("unresolved_model", "initial particle Reynolds number exceeds declared envelope")
            resistance = inertial.stokes_generalized_resistance(p, a, b, viscosity)
            mass, _ = inertial.generalized_mass_matrix(
                p, a, b, particle_density, fluid_density, added_mass_fraction
            )
            mass[3:, 3:] = 0.0
            volume = 4 * np.pi * a * b * b / 3
            body_load = np.r_[(particle_density-fluid_density) * volume * mechanics.finite(gravity), np.zeros(3)]
            near = enrich(geometry, geometry.contacts(x, p, a, b, cutoff_ratio*maximum_grain_radius))
            lubrication_resistance, lubrication_rows = lubrication_matrix(
                near, p, a, b, a, viscosity, cutoff_ratio, roughness_ratio
            )
            translation_scale = max(
                np.linalg.norm(q[:3]), np.linalg.norm(background[:3]),
                np.linalg.norm(body_load[:3]) / max(np.linalg.eigvalsh(resistance[:3, :3]).min(), 1e-30),
                1e-30,
            )
            rotation_scale = max(np.linalg.norm(q[3:]), np.linalg.norm(background[3:]), 1e-30) / a
            relaxation_time = (np.linalg.eigvalsh(mass[:3, :3]).min()
                               / np.linalg.eigvalsh(resistance[:3, :3]).max())
            dt = min(max_dt, horizon-t, displacement_fraction*b/translation_scale,
                     angle_limit/rotation_scale, relaxation_fraction*relaxation_time)
            accepted = False
            first_attempt = 0
            if pending_trial is not None:
                if pending_trial["time_s"] != t:
                    raise ValueError("pending trial checkpoint time mismatch")
                dt = pending_trial["dt_s"]
                first_attempt = pending_trial["attempt"]
                pending_trial = None
            for _attempt in range(first_attempt, 30):
                if time.perf_counter() - started > wall_budget:
                    pending_trial = {"time_s": t, "dt_s": dt, "attempt": _attempt}
                    return finish("incomplete_budget", "budget reached before uncommitted adaptive trial")
                reach = (translation_scale + a*rotation_scale) * dt + tolerance
                active = geometry.contacts(x, p, a, b, reach)
                try:
                    candidate, health = inertial.inertial_contact_step(
                        q, background, body_load, resistance, lubrication_resistance, mass,
                        active, a, dt, friction, fluid_density, viscosity,
                        equivalent_diameter, sphericity,
                    )
                except RuntimeError as exc:
                    if str(exc) not in {
                        "direct contact residual nonconvergence",
                        "direct contact negative normal force",
                        "direct contact cone violation",
                        "inertial/contact fixed point did not converge",
                    }:
                        raise
                    rejected_trials.append({"time_s": t, "dt_s": dt, "attempt": _attempt, "reason": str(exc), "contact_ids": [int(c[0]) for c in active]})
                    dt *= 0.5
                    rejected += 1
                    contact_solver_retries += 1
                    if hasattr(inertial, "set_recovery_mode"):
                        inertial.set_recovery_mode(True)
                    continue
                if (np.linalg.norm(candidate[:3])*dt > 1.1*displacement_fraction*b
                        or np.linalg.norm(candidate[3:])*dt/a > 1.1*angle_limit):
                    rejected_trials.append({"time_s": t, "dt_s": dt, "attempt": _attempt, "reason": "motion cap exceeded"})
                    dt *= 0.5
                    rejected += 1
                    continue
                swept_gap = geometry_tools.swept_gap(geometry, x, p, candidate, a, b, dt)
                if swept_gap < -tolerance:
                    dt *= 0.5
                    rejected += 1
                    continue
                next_x, next_p = mechanics.advance_pose(x, p, candidate, a, dt)
                accepted = True
                break
            if not accepted:
                raise RuntimeError("adaptive trial budget exhausted; last rejection: " + (rejected_trials[-1]["reason"] if rejected_trials else "unknown"))
            if not active and hasattr(inertial, "set_recovery_mode"):
                inertial.set_recovery_mode(False)
            # Account for accepted candidate health before every terminal event.
            # The swept clearance covers the full proposed interval, hence is
            # conservative if the exit occurs partway through that interval.
            for contact in near:
                minimum_gap_ratio = min(minimum_gap_ratio, contact[1] / contact[4])
            minimum_gap = min(minimum_gap, swept_gap)
            max_momentum = max(max_momentum, health["momentum_residual"])
            max_contact_residual = max(max_contact_residual, health["contact"]["residual"])
            max_force_residual = max(max_force_residual, health["contact"]["force_residual"])
            max_reynolds = max(max_reynolds, health["reynolds"])
            max_near = max(max_near, len(lubrication_rows))
            max_active = max(max_active, len(active))
            max_contact_iterations = max(max_contact_iterations, health["contact"]["iterations"])
            total_contact_iterations += health["total_contact_iterations"]
            contact_steps += int(bool(health["load_bearing_grain_ids"]))
            last_reaction_count = len(health["reaction_world_by_grain"])
            endpoint_reynolds = inertial.finite_re.reynolds_number(
                candidate[:3] - background[:3], fluid_density, viscosity, equivalent_diameter)
            max_reynolds = max(max_reynolds, endpoint_reynolds)
            if max_reynolds > reynolds_limit:
                return finish("unresolved_model", "particle Reynolds number exceeds declared envelope")
            if max_contact_residual > 1e-8 or max_force_residual > 1e-8:
                return finish("numerical_failure", "contact or force closure failed")
            event = mechanics.linear_pose_exit_time(x, p, candidate, a, b, outlet, dt)
            if event is not None:
                end_x, end_p = mechanics.advance_pose(x, p, candidate, a, event)
                record_dwell(event, end_x, end_p, candidate, active, health)
                x, p = end_x, end_p
                q = candidate
                t += event
                steps += 1
                return finish("full_window_exit")
            dwell_observed = record_dwell(dt, next_x, next_p, candidate, active, health)
            x, p, q = next_x, next_p, candidate
            t += dt
            steps += 1
            if dwell_observed and stop_on_trap:
                return finish("persistent_contact_dwell")
            if steps % 250 == 0:
                history.append([t, *x, *p, *q, minimum_gap, minimum_gap_ratio,
                                total_contact_iterations])
        return finish("present_at_horizon")
    except (ValueError, FloatingPointError, RuntimeError, np.linalg.LinAlgError) as exc:
        status = "unresolved_field" if "mixed fluid/solid" in str(exc) else "numerical_failure"
        return finish(status, str(exc))


