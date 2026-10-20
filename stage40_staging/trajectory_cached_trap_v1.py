"""Inertial rigid-body trajectory with cross-step reaction cache and trapping."""
import sys, time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage37_staging"), str(ROOT / "stage38_staging"),
                str(ROOT / "stage39_staging"), str(ROOT / "stage40_staging")]
import transport_contact as mechanics
import trajectory as geometry_tools
import lubrication_contact_v1 as lubrication
import inertial_contact_cached_v1 as inertial
import trap_event_v2


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
              trap_speed_ratio=0.01, trap_drift_over_minor_radius=0.02):
    x = mechanics.finite(position).copy()
    p = mechanics.unit(orientation)
    q = mechanics.finite(velocity).copy()
    t = 0.0
    steps = rejected = contact_steps = 0
    started = time.perf_counter()
    minimum_gap = np.inf
    minimum_gap_ratio = np.inf
    max_momentum = max_contact_residual = max_force_residual = max_reynolds = 0.0
    max_near = max_active = max_contact_iterations = total_contact_iterations = 0
    history = []
    tolerance = 1e-5 * b
    equivalent_diameter = 2 * (a*b*b)**(1/3)
    sphericity = inertial.finite_re.prolate_sphericity(a, b)
    maximum_grain_radius = float(np.max(geometry.r))
    reaction_cache = {}
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

    def finish(status, reason=None):
        return {
            "status": status, "reason": reason, "time_s": t,
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
            "max_contact_iterations_per_nonlinear_solve": max_contact_iterations,
            "total_contact_iterations": total_contact_iterations,
            "cached_reaction_count": len(reaction_cache),
            "trap_state": last_trap_state,
            "runtime_seconds": time.perf_counter() - started,
            "history": history,
        }

    try:
        while t < horizon:
            if steps >= max_steps or time.perf_counter() - started > wall_budget:
                return finish("incomplete_budget")
            initial = geometry.contacts(x, p, a, b, 0.0)
            if initial and min(contact[1] for contact in initial) < -tolerance:
                raise RuntimeError("inadmissible penetration")
            fluid_velocity, gradient = field.sample(x)
            background, _ = mechanics.free_motion(p, gradient, fluid_velocity, a, b,
                                                   viscosity, 1.0, 1.0, [0, 0, 0])
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
            for _attempt in range(30):
                reach = (translation_scale + a*rotation_scale) * dt + tolerance
                active = geometry.contacts(x, p, a, b, reach)
                candidate, health = inertial.inertial_contact_step(
                    q, background, body_load, resistance, lubrication_resistance, mass,
                    active, a, dt, friction, fluid_density, viscosity,
                    equivalent_diameter, sphericity, world_reactions=reaction_cache,
                )
                if (np.linalg.norm(candidate[:3])*dt > 1.1*displacement_fraction*b
                        or np.linalg.norm(candidate[3:])*dt/a > 1.1*angle_limit):
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
                raise RuntimeError("adaptive step failed to maintain clearance")
            event = mechanics.linear_pose_exit_time(x, p, candidate, a, b, outlet, dt)
            if event is not None:
                x, p = mechanics.advance_pose(x, p, candidate, a, event)
                q = candidate
                t += event
                steps += 1
                return finish("full_window_exit")
            for contact in enrich(geometry, geometry.contacts(x, p, a, b, cutoff_ratio*maximum_grain_radius)):
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
            reaction_cache = health["reaction_world_by_grain"]
            x, p, q = next_x, next_p, candidate
            t += dt
            steps += 1
            if monitor is not None:
                last_trap_state = monitor.update(
                    dt, x, q, [contact[0] for contact in active],
                    health["load_bearing_grain_ids"],
                )
                if last_trap_state["trapped"]:
                    return finish("persistent_contact_trap")
            if steps % 250 == 0:
                history.append([t, *x, *p, *q, minimum_gap, minimum_gap_ratio,
                                total_contact_iterations])
        return finish("present_at_horizon")
    except (ValueError, FloatingPointError, RuntimeError, np.linalg.LinAlgError) as exc:
        status = "unresolved_field" if "mixed fluid/solid" in str(exc) else "numerical_failure"
        return finish(status, str(exc))
