"""Known deterministic cold portfolio with exact outer-cycle early rejection.

No arbitrary solver injection is exposed here. Custom solvers must use the
default-off ContactModel API and establish determinism before opting in.
"""
import compiled_blas_loop
from compiled_stage53_blas import CompiledStage53
from portfolio_explicit import Portfolio
from inertial_cycle_guard import ContactModel


class _Sor:
    def __call__(self, *args, **kwargs):
        return compiled_blas_loop.solve_prepared(*args, **kwargs)

    def stats(self):
        return compiled_blas_loop.stats()


def make_cycle_contact_model():
    portfolio = Portfolio(default_solver=CompiledStage53(), sor_solver=_Sor())
    return ContactModel(portfolio.solve_default, portfolio.solve_recovery,
                        portfolio=portfolio,
                        deterministic_stateless_cold_solver=True)
