"""Per-instance Stage70 branch order with explicit, injectable solver functions.

Historical numerical functions may increment their historical diagnostic
counters. Those counters are never used here for selection or reporting; no
historical recovery switch or function binding is changed.
"""
import copy
import sys
import time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "stage53_staging"), str(ROOT / "stage63_staging"),
                str(ROOT / "stage70_staging")]
import inertial_contact_multistart_lm_v1 as stage53
import inertial_contact_projected_sor_v1 as stage63
import inertial_contact_runtime_portfolio_v1 as stage70


class Portfolio:
    """Original Stage70 Krylov -> projected SOR -> Stage53 recovery."""

    def __init__(self, default_solver=None, sor_solver=None, krylov_solver=None):
        self.default_solver = default_solver or stage53._solve
        self.sor_solver = sor_solver or stage63._solve
        self.krylov_solver = krylov_solver or self._krylov
        self._stats = {}
        self.last_solve_diagnostics = []

    @staticmethod
    def _krylov(*args, **kwargs):
        return stage70._root_candidate("krylov", *args, **kwargs)

    def stats(self):
        return {key: dict(value) for key, value in self._stats.items()}

    def _attempt(self, label, solver, args, kwargs):
        record = {"solver": label}
        owner = getattr(solver, "__self__", solver)
        stats_fn = getattr(solver, "stats", None) or getattr(owner, "stats", None)
        before = copy.deepcopy(stats_fn()) if stats_fn is not None else None
        counts = self._stats.setdefault(label, {"attempts": 0, "accepted": 0,
                                                "failed": 0, "wall_seconds": 0.0})
        counts["attempts"] += 1
        self.last_solve_diagnostics.append(record)
        started = time.perf_counter()
        try:
            answer = solver(*args, **kwargs)
        except Exception as exc:
            counts["failed"] += 1
            record.update(status="rejected", reason=str(exc))
            if vars(exc):
                record["exception_diagnostics"] = copy.deepcopy(vars(exc))
            raise
        else:
            counts["accepted"] += 1
            record.update(status="accepted", iterations=answer[1].get("iterations"))
            return answer
        finally:
            elapsed = time.perf_counter() - started
            record["wall_seconds"] = elapsed
            counts["wall_seconds"] += elapsed
            if before is not None:
                after = copy.deepcopy(stats_fn())
                record["work_delta"] = _numeric_delta(before, after)

    def solve_default(self, vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
        self.last_solve_diagnostics = []
        return self._attempt("default_stage53", self.default_solver,
            (vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter), {})

    def solve_recovery(self, vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
        self.last_solve_diagnostics = []
        args = (vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter)
        if 0 < len(gaps) <= 3:
            try:
                return self._attempt("krylov", self.krylov_solver, args, {})
            except (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError, OverflowError):
                pass
            try:
                return self._attempt("projected_sor", self.sor_solver, args, {})
            except (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError):
                pass
        return self._attempt("recovery_stage53", self.default_solver, args, {})


def _numeric_delta(before, after):
    """Keep complete nested numeric counters, including work in rejected calls."""
    result = {}
    for key, value in after.items():
        prior = before.get(key, {} if isinstance(value, dict) else 0)
        if isinstance(value, dict):
            result[key] = _numeric_delta(prior, value)
        elif isinstance(value, (int, float, np.integer, np.floating)):
            result[key] = value - prior
    return result


def make_contact_model(default_solver=None, recovery_solver=None,
                       sor_solver=None, krylov_solver=None):
    """Inject any solver matching (vfree,M,J,gaps,dt,mu,tol,maxiter)->(q,health).

    By default use Stage53 ordinarily, and the exact Stage70 branch order in
    recovery. Supply recovery_solver to replace the entire recovery path, or
    sor_solver/krylov_solver to replace a single branch explicitly.
    """
    from inertial_consolidated import ContactModel
    portfolio = Portfolio(default_solver, sor_solver, krylov_solver)
    return ContactModel(portfolio.solve_default,
                        recovery_solver or portfolio.solve_recovery,
                        portfolio=portfolio)
