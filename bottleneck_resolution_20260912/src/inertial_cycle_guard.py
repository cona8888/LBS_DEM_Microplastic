"""Optional exact-cycle rejection for deterministic, stateless cold contact maps.

The original convergence test is evaluated first. With explicit caller
attestation, repetition of the complete six-component binary64 map input proves
that the deterministic fixed-input map will repeat its nonconvergent cycle.
Only redundant iterations are skipped; no candidate is accepted by this guard.
Counter values, elapsed time, and warm state must not affect the prepared solve.
"""
import sys
from pathlib import Path
import copy
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "stage41_staging"))
import inertial_contact_cold_optimized_v1 as stage41

base = stage41.base
generalized_mass_matrix = stage41.generalized_mass_matrix
stokes_generalized_resistance = stage41.stokes_generalized_resistance
contact_model = stage41.contact_model
finite_re = stage41.finite_re
contact_solve = stage41.contact_solve
CONTACT_ITERATION_CEILING = 25000


def _binary64_key(value):
    """Exact representation; signed zeros differ and near equality is irrelevant."""
    value = np.asarray(value)
    if value.shape != (6,) or value.dtype != np.float64 or not np.isfinite(value).all():
        raise ValueError("exact-cycle detection requires six finite binary64 map states")
    return value.tobytes(order="C")


def inertial_contact_step(old_velocity, fluid_background_velocity, body_load,
                          stokes_resistance, lubrication_resistance, mass_matrix,
                          contacts, ell, dt, friction, fluid_density, viscosity,
                          equivalent_diameter, sphericity, world_reactions=None,
                          tolerance=1e-10, max_iterations=80, prepared_solver=None,
                          diagnostics=None, capture_prepared_inputs=False,
                          deterministic_stateless_cold_solver=False):
    if prepared_solver is None:
        raise ValueError("an explicit contact solver is required")
    old_velocity = np.asarray(old_velocity, float)
    background = np.asarray(fluid_background_velocity, float)
    body_load = np.asarray(body_load, float)
    stokes = np.asarray(stokes_resistance, float)
    lubrication = np.asarray(lubrication_resistance, float)
    mass = np.asarray(mass_matrix, float)
    if dt <= 0 or ell <= 0 or friction < 0:
        raise ValueError("invalid contact parameter")
    jacobian, gaps, frames = stage41._prepare_geometry(contacts, ell)
    candidate = old_velocity.copy()
    seen_inputs = ({_binary64_key(candidate): 0}
                   if deterministic_stateless_cold_solver else None)
    velocity_scale = max(np.linalg.norm(old_velocity), np.linalg.norm(background), 1e-30)
    total_contact_iterations = 0
    for iteration in range(max_iterations):
        reynolds = finite_re.reynolds_number(
            candidate[:3] - background[:3], fluid_density, viscosity, equivalent_diameter)
        multiplier = finite_re.inertial_multiplier(reynolds, sphericity)
        drag = stokes.copy()
        drag[:3, :3] *= multiplier
        system = mass / dt + drag + lubrication
        compliance = np.linalg.inv(system)
        free_velocity = compliance @ (mass @ old_velocity / dt + drag @ background + body_load)
        solve_record = None
        if diagnostics is not None:
            solve_record = {"fixed_point_iteration": iteration + 1,
                            "reynolds": float(reynolds),
                            "finite_re_multiplier": float(multiplier)}
            if capture_prepared_inputs:
                solve_record["prepared_inputs"] = {
                    "vfree": free_velocity.copy(), "mobility": compliance.copy(),
                    "jacobian": jacobian.copy(), "gaps": gaps.copy(), "dt": dt,
                    "friction": friction, "tol": 1e-10,
                    "maxiter": CONTACT_ITERATION_CEILING}
            diagnostics.setdefault("contact_solves", []).append(solve_record)
        solve_started = time.perf_counter()
        try:
            updated, contact_health = prepared_solver(
                free_velocity, compliance, jacobian, gaps, dt, friction,
                tol=1e-10, maxiter=CONTACT_ITERATION_CEILING)
        except Exception as exc:
            if solve_record is not None:
                solve_record.update(status="rejected", reason=str(exc))
                if vars(exc):
                    solve_record["exception_diagnostics"] = copy.deepcopy(vars(exc))
            raise
        else:
            if solve_record is not None:
                solve_record.update(status="accepted", health=copy.deepcopy(contact_health))
        finally:
            if solve_record is not None:
                solve_record["wall_seconds"] = time.perf_counter() - solve_started
                owner = getattr(prepared_solver, "__self__", prepared_solver)
                details = getattr(owner, "last_solve_diagnostics", None)
                if details is not None:
                    solve_record["solver_attempts"] = copy.deepcopy(details)
        total_contact_iterations += contact_health["iterations"]
        fixed_point_residual = np.linalg.norm(updated - candidate) / velocity_scale
        if solve_record is not None:
            solve_record["updated_velocity_generalized"] = updated.copy()
            solve_record["fixed_point_residual"] = float(fixed_point_residual)
        if fixed_point_residual <= tolerance:
            candidate = updated
            break
        if seen_inputs is not None:
            key = _binary64_key(updated)
            repeated_input_index = iteration + 1
            if key in seen_inputs:
                first_input_index = seen_inputs[key]
                cycle = {
                    "comparison": "exact_full_binary64_state",
                    "cycle_length": repeated_input_index - first_input_index,
                    "first_input_index": first_input_index,
                    "repeated_input_index": repeated_input_index,
                    "current_outer_iteration": iteration + 1,
                    "state_index_convention": "q_0 is the initial map input",
                    "fixed_point_residual_at_repetition": float(fixed_point_residual),
                    "deterministic_stateless_cold_solver_attested": True,
                }
                if diagnostics is not None:
                    diagnostics["cycle_guard"] = cycle
                error = RuntimeError("inertial/contact fixed point did not converge")
                error.diagnostics = {
                    "cycle_guard": cycle,
                    "completed_outer_iterations": iteration + 1,
                    "total_contact_iterations": total_contact_iterations,
                }
                raise error
            seen_inputs[key] = repeated_input_index
        candidate = updated
    else:
        raise RuntimeError("inertial/contact fixed point did not converge")
    reaction = np.asarray(contact_health["reactions"], float)
    reaction_load = jacobian.T @ reaction if len(reaction) else np.zeros(6)
    acceleration_load = mass @ (candidate - old_velocity) / dt
    slip_drag = drag @ (candidate - background)
    lubrication_load = lubrication @ candidate
    residual = acceleration_load + slip_drag + lubrication_load - body_load - reaction_load
    denominator = max(np.linalg.norm(acceleration_load), np.linalg.norm(slip_drag),
                      np.linalg.norm(lubrication_load), np.linalg.norm(body_load),
                      np.linalg.norm(reaction_load), np.linalg.norm(drag @ background), 1e-30)
    momentum_residual = float(np.linalg.norm(residual) / denominator)
    if momentum_residual > 1e-8 or not np.isfinite(candidate).all():
        raise RuntimeError("inertial momentum closure failed")
    world = {str(int(contact[0])): (frames[k].T @ reaction[3*k:3*k+3]).tolist()
             for k, contact in enumerate(contacts)}
    return candidate, {"iterations": iteration + 1, "reynolds": reynolds,
                       "finite_re_multiplier": multiplier,
                       "momentum_residual": momentum_residual,
                       "momentum_reference_load": float(denominator),
                       "contact": contact_health,
                       "total_contact_iterations": total_contact_iterations,
                       "reaction_world_by_grain": world,
                       "load_bearing_grain_ids": [int(contacts[k][0]) for k in range(len(contacts))
                                                  if reaction[3*k] > 0],
                       "cache_policy": "discard_between_all_solves",
                       "minimum_system_eigenvalue": float(
                           np.linalg.eigvalsh((system + system.T) / 2).min()),
                       "contact_iteration_ceiling": CONTACT_ITERATION_CEILING}


class ContactModel:
    """Per-trajectory algorithm selection; no reaction state or global rebinding."""
    base = base
    finite_re = finite_re
    contact_model = contact_model
    generalized_mass_matrix = staticmethod(generalized_mass_matrix)
    stokes_generalized_resistance = staticmethod(stokes_generalized_resistance)

    def __init__(self, default_solver, recovery_solver=None, portfolio=None,
                 deterministic_stateless_cold_solver=False):
        self.default_solver = default_solver
        self.recovery_solver = recovery_solver or default_solver
        self._recovery = False
        self._calls = {"default_steps": 0, "recovery_steps": 0}
        self.portfolio = portfolio
        self.deterministic_stateless_cold_solver = bool(deterministic_stateless_cold_solver)

    def set_recovery_mode(self, value):
        self._recovery = bool(value)

    def recovery_mode(self):
        return self._recovery

    def stats(self):
        result = dict(self._calls)
        if self.portfolio is not None:
            result["portfolio"] = self.portfolio.stats()
        return result

    def inertial_contact_step(self, *args, **kwargs):
        solver = self.recovery_solver if self._recovery else self.default_solver
        self._calls["recovery_steps" if self._recovery else "default_steps"] += 1
        return inertial_contact_step(*args, **kwargs, prepared_solver=solver,
            deterministic_stateless_cold_solver=self.deterministic_stateless_cold_solver)
