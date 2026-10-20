"""Bounded contact recovery with dimensionless equations and an analytic Jacobian.

The ordinary entry point delegates to the frozen Stage53 solver unchanged.
Recovery is explicitly selected by the caller only after a rejected step.
All candidate roots pass the original Stage50 Signorini/Coulomb, normal-force,
cone, force-closure and friction-dissipation checks.  No geometry, gaps, friction,
roughness or reaction history is modified.  The residual target remains 1e-10.
"""
from pathlib import Path
from itertools import combinations
import sys
import numpy as np
from scipy.optimize import root

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "stage50_staging"), str(ROOT / "stage53_staging")]
import inertial_contact_seeded_lm_v1 as stage50
import inertial_contact_multistart_lm_v1 as stage53

LM_EVALUATION_LIMIT = 1500
PGS_SEED_LIMIT = 200
_stats = {"ordinary_calls": 0, "recovery_calls": 0, "analytic_lm_passes": 0,
          "analytic_lm_failures": 0, "lm_nfev": 0, "lm_njev": 0,
          "pgs_seed_iterations": 0, "authoritative_fallbacks": 0}


def stats():
    return dict(_stats)


def _solve_prepared(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
    """Unchanged authoritative path, with no global module rebinding."""
    _stats["ordinary_calls"] += 1
    return stage53._solve(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter)


class DimensionlessContactSystem:
    """u_i = s_i f_i / V; both unknowns and residuals are dimensionless.

    s_n=A_nn and s_t=lambda_max(A_tt), exactly as in the frozen residual.
    V=max(norm(vfree),1e-15), retaining the frozen acceptance normalization.
    Nondimensionalization changes neither the zero set nor the contact law.
    """

    def __init__(self, vfree, mobility, jacobian, gaps, dt, friction):
        self.vfree = np.asarray(vfree, float)
        self.mobility = np.asarray(mobility, float)
        self.jacobian = np.asarray(jacobian, float)
        self.gaps = np.asarray(gaps, float)
        self.dt = float(dt)
        self.friction = float(friction)
        self.count = len(self.gaps)
        self.A = self.jacobian @ self.mobility @ self.jacobian.T
        self.z = self.jacobian @ self.vfree
        self.V = max(np.linalg.norm(self.vfree), 1e-15)
        self.steps = np.array([
            np.linalg.eigvalsh(self.A[3*k+1:3*k+3, 3*k+1:3*k+3]).max()
            for k in range(self.count)])
        self.scales = np.repeat(self.steps, 3)
        self.scales[::3] = np.diag(self.A)[::3]
        if (self.dt <= 0 or self.friction < 0 or
                np.any(self.scales <= 0) or
                not all(np.isfinite(a).all() for a in
                        (self.vfree, self.mobility, self.jacobian, self.gaps, self.scales))):
            raise ValueError("invalid dimensionless contact system")
        self.B = self.A / self.scales[None, :]
        self.zbar = self.z / self.V
        self.gapbar = self.gaps / (self.dt * self.V)
        self.eye = np.eye(len(self.z))

    def force(self, u):
        return np.asarray(u) * self.V / self.scales

    def unknown(self, force):
        return np.asarray(force) * self.scales / self.V

    def equations_and_jacobian(self, u):
        """FB normal residual and Coulomb disk projection with exact branches.

        At the FB origin the zero subgradient of hypot gives the valid Clarke
        element (-1,-1). At a disk boundary the sticking-side derivative is
        selected deterministically. No smoothing parameter is introduced.
        """
        u = np.asarray(u)
        w = self.zbar + self.B @ u
        residual = np.empty_like(u)
        jac = np.empty((len(u), len(u)))
        for k in range(self.count):
            i = 3*k
            normal = w[i] + self.gapbar[k]
            h = np.hypot(u[i], normal)
            residual[i] = h - u[i] - normal
            if h > 0:
                jac[i] = (u[i]/h - 1)*self.eye[i] + (normal/h - 1)*self.B[i]
            else:
                jac[i] = -self.eye[i] - self.B[i]
            block = slice(i+1, i+3)
            trial = u[block] - w[block]
            trial_jac = self.eye[block] - self.B[block]
            norm = np.linalg.norm(trial)
            radius_coefficient = self.friction * self.steps[k] / self.scales[i]
            radius = radius_coefficient * u[i]
            if norm <= radius:
                projected = trial
                projected_jac = trial_jac
            elif norm > 0:
                direction = trial / norm
                projected = radius * direction
                projected_jac = ((radius/norm) *
                                 (np.eye(2) - np.outer(direction, direction)) @ trial_jac)
                projected_jac[:, i] += radius_coefficient * direction
            else:
                # A negative trial normal is never accepted. This deterministic
                # extension only defines the merit function away from its roots.
                projected = trial * (radius / 1e-300)
                projected_jac = trial_jac * (radius / 1e-300)
            residual[block] = u[block] - projected
            jac[block] = self.eye[block] - projected_jac
        return residual, jac

    def equations(self, u):
        return self.equations_and_jacobian(u)[0]

    def jacobian_function(self, u):
        return self.equations_and_jacobian(u)[1]

    def pgs_seed(self, iterations):
        """Cold same-solve PGS iterate; never imports cross-solve reactions."""
        force = np.zeros(len(self.z))
        for _ in range(iterations):
            for k in range(self.count):
                i = 3*k
                vn = self.z[i] + self.A[i] @ force + self.gaps[k]/self.dt
                force[i] = max(0., force[i] - vn/self.A[i, i])
                vt = self.z[i+1:i+3] + self.A[i+1:i+3] @ force
                force[i+1:i+3] = stage50._project(
                    force[i+1:i+3], vt, self.steps[k], self.friction*force[i])
        return force

    def finish(self, u, evaluations, solver, extra, tol=1e-10):
        force = self.force(u)
        if not np.isfinite(force).all():
            raise RuntimeError("nonfinite dimensionless contact solution")
        velocity, health = stage50._finish(
            self.vfree, self.mobility, self.jacobian, force, self.z, self.A,
            self.gaps, self.dt, self.friction, self.steps, evaluations, solver, extra)
        if health["residual"] > tol:
            raise RuntimeError("requested contact tolerance not met")
        return velocity, health


def solve_analytic_prepared(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
    """Bounded recovery attempts only; raises if strict acceptance fails."""
    if len(gaps) > 3 or not len(gaps):
        raise RuntimeError("analytic recovery requires one to three contacts")
    system = DimensionlessContactSystem(vfree, mobility, jacobian, gaps, dt, friction)
    failures = []
    nfev = njev = seed_iterations = 0
    try:
        answer = system.finish(np.zeros(len(system.z)), 0, "zero_reaction_feasible",
                               {"active_force_contacts": []}, min(tol, 1e-10))
    except RuntimeError:
        pass
    else:
        _stats["analytic_lm_passes"] += 1
        return answer
    attempts = [("zero", tuple(range(system.count))),
                ("same_solve_cold_pgs", tuple(range(system.count)))]
    # An inactive contact means exactly zero force, not a rounded negative force.
    # Enumerate smaller active-force sets deterministically and check every full
    # original contact after solving. Geometry and all gap constraints survive.
    attempts += [("inactive_set_" + "_".join(map(str, active)), active)
                 for size in range(system.count-1, 0, -1)
                 for active in combinations(range(system.count), size)]
    pgs_unknown = None
    for name, active in attempts:
        if name == "zero":
            seed = np.zeros(len(system.z))
        elif name == "same_solve_cold_pgs":
            seed_iterations = min(PGS_SEED_LIMIT, int(maxiter))
            seed = system.unknown(system.pgs_seed(seed_iterations))
            pgs_unknown = seed
            _stats["pgs_seed_iterations"] += seed_iterations
        else:
            seed = pgs_unknown.copy()
        indices = np.array([3*k+j for k in active for j in range(3)], int)
        def expand(reduced):
            expanded = np.zeros(len(system.z))
            expanded[indices] = reduced
            return expanded
        def reduced_equations_and_jacobian(reduced):
            residual, jac = system.equations_and_jacobian(expand(reduced))
            return residual, jac[:, indices]
        solved = root(reduced_equations_and_jacobian, seed[indices], jac=True, method="lm",
                      options={"ftol": 1e-14, "xtol": 1e-14, "gtol": 1e-14,
                               "maxiter": LM_EVALUATION_LIMIT})
        nfev += int(solved.nfev)
        njev += int(getattr(solved, "njev", 0))
        _stats["lm_nfev"] += int(solved.nfev)
        _stats["lm_njev"] += int(getattr(solved, "njev", 0))
        try:
            answer = system.finish(
                expand(solved.x), nfev + seed_iterations, "dimensionless_analytic_lm",
                {"lm_seed": name, "lm_nfev": nfev, "lm_njev": njev,
                 "pgs_seed_iterations": seed_iterations, "active_force_contacts": list(active),
                 "lm_success_flag": bool(solved.success), "lm_message": str(solved.message),
                 "prior_attempt_rejections": failures}, min(tol, 1e-10))
        except RuntimeError as exc:
            failures.append({"seed": name, "reason": str(exc),
                             "nfev": int(solved.nfev)})
            continue
        _stats["analytic_lm_passes"] += 1
        return answer
    _stats["analytic_lm_failures"] += 1
    raise RuntimeError("dimensionless analytic LM rejected: " + str(failures))


def solve_recovery_prepared(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
    """Explicit recovery attempt, then unchanged Stage53 authoritative fallback."""
    _stats["recovery_calls"] += 1
    if 0 < len(gaps) <= 3:
        try:
            return solve_analytic_prepared(
                vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter)
        except (RuntimeError, FloatingPointError):
            pass
    _stats["authoritative_fallbacks"] += 1
    return stage53._solve(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter)
