"""Adaptive 6-DOF trajectory with matched normal lubrication and contact."""
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage37_staging"))
sys.path.insert(0, str(ROOT / "stage38_staging"))
import transport_contact as mechanics
import trajectory as base
import lubrication_contact_v2 as lubrication


def _with_radii(geometry, contacts):
    enriched = []
    for contact in contacts:
        if len(contact) == 5:
            enriched.append(contact)
        elif len(contact) == 4 and hasattr(geometry, "r"):
            enriched.append((*contact, float(geometry.r[contact[0]])))
        else:
            raise ValueError("grain radius unavailable for lubrication")
    return enriched


def integrate(field, geometry, x, p, a, b, mu, rhop, rhof, gravity, friction,
              outlet, horizon, cutoff_ratio=0.2, roughness_ratio=0.01,
              displacement_fraction=0.1, angle_limit=0.02, max_dt=1.0,
              max_steps=200000, wall_budget=120.0):
    """Advance a rigid body; fixed sand and one-way steady flow are assumed."""
    x = mechanics.finite(x).copy()
    p = mechanics.unit(p)
    t = 0.0
    started = time.perf_counter()
    steps = rejected = contact_steps = 0
    minimum_gap = np.inf
    minimum_gap_ratio = np.inf
    max_contact_residual = max_force_residual = 0.0
    max_contacts = max_lubrication_contacts = 0
    max_excess_coefficient = 0.0
    history = []
    tolerance = 1e-5 * b

    def finish(status, reason=None):
        return {
            "status": status,
            "reason": reason,
            "time_s": t,
            "position_m": x.tolist(),
            "orientation": p.tolist(),
            "steps": steps,
            "rejected": rejected,
            "minimum_gap_m": None if not np.isfinite(minimum_gap) else minimum_gap,
            "minimum_gap_over_grain_radius": None if not np.isfinite(minimum_gap_ratio) else minimum_gap_ratio,
            "max_contact_residual": max_contact_residual,
            "max_force_residual": max_force_residual,
            "max_contacts": max_contacts,
            "contact_steps": contact_steps,
            "max_lubrication_contacts": max_lubrication_contacts,
            "max_excess_coefficient": max_excess_coefficient,
            "runtime_seconds": time.perf_counter() - started,
            "history": history,
        }

    try:
        if not hasattr(geometry, "r"):
            raise ValueError("geometry must expose grain radii")
        maximum_radius = float(np.max(geometry.r))
        while t < horizon:
            if steps >= max_steps or time.perf_counter() - started > wall_budget:
                return finish("incomplete_budget")
            initial = geometry.contacts(x, p, a, b, 0.0)
            if initial and min(contact[1] for contact in initial) < -tolerance:
                raise RuntimeError("inadmissible penetration")
            fluid_velocity, gradient = field.sample(x)
            vfar, mfar = mechanics.free_motion(p, gradient, fluid_velocity, a, b, mu, rhop, rhof, gravity)
            near = _with_radii(geometry, geometry.contacts(x, p, a, b, cutoff_ratio * maximum_radius))
            vfree, mobility, lubrication_health = lubrication.lubricated_motion(
                vfar, mfar, near, p, a, b, a, mu, cutoff_ratio, roughness_ratio
            )
            speed = np.linalg.norm(vfree[:3])
            rotation = np.linalg.norm(vfree[3:]) / a
            dt = min(
                max_dt,
                horizon - t,
                displacement_fraction * b / max(speed, 1e-30),
                angle_limit / max(rotation, 1e-30),
            )
            for _attempt in range(30):
                reach = (speed + a * rotation) * dt + tolerance
                active = geometry.contacts(x, p, a, b, reach)
                active_contact = [contact[:4] for contact in active]
                velocity, contact_health = mechanics.contact_solve(
                    vfree, mobility, active_contact, a, dt, friction, tol=1e-8
                )
                if (
                    np.linalg.norm(velocity[:3]) * dt > 1.1 * displacement_fraction * b
                    or np.linalg.norm(velocity[3:]) * dt / a > 1.1 * angle_limit
                ):
                    dt *= 0.5
                    rejected += 1
                    continue
                gap = base.swept_gap(geometry, x, p, velocity, a, b, dt)
                if gap < -tolerance:
                    dt *= 0.5
                    rejected += 1
                    continue
                next_x, next_p = mechanics.advance_pose(x, p, velocity, a, dt)
                break
            else:
                raise RuntimeError("adaptive step failed to maintain clearance")

            minimum_gap = min(minimum_gap, gap)
            for contact in _with_radii(geometry, geometry.contacts(x, p, a, b, cutoff_ratio * maximum_radius)):
                minimum_gap_ratio = min(minimum_gap_ratio, contact[1] / contact[4])
            max_contact_residual = max(max_contact_residual, contact_health["residual"])
            max_force_residual = max(max_force_residual, contact_health["force_residual"])
            max_contacts = max(max_contacts, len(active_contact))
            contact_steps += int(any(value > 0 for value in contact_health["reactions"][::3]))
            max_lubrication_contacts = max(max_lubrication_contacts, len(lubrication_health["contacts"]))
            if lubrication_health["contacts"]:
                max_excess_coefficient = max(
                    max_excess_coefficient,
                    max(row["excess_coefficient"] for row in lubrication_health["contacts"]),
                )
            steps += 1
            event = mechanics.linear_pose_exit_time(x, p, velocity, a, b, outlet, dt)
            if event is not None:
                x, p = mechanics.advance_pose(x, p, velocity, a, event)
                t += event
                return finish("full_window_exit")
            x, p = next_x, next_p
            t += dt
            if steps % 100 == 0:
                history.append([t, *x, *p, minimum_gap, minimum_gap_ratio])
        return finish("present_at_horizon")
    except (ValueError, FloatingPointError, RuntimeError, np.linalg.LinAlgError) as exc:
        category = "unresolved_field" if "mixed fluid/solid" in str(exc) else "numerical_failure"
        return finish(category, str(exc))

