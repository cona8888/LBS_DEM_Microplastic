"""Scoped failure-only repair; successful original solves are unchanged."""
from contextlib import contextmanager
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'stage118_staging'), str(ROOT/'stage119_staging')]
import probe_three_contact_v1 as probe
import mixed_contact_v1 as mixed
import checkpoint_core_v3 as core
api = probe.api
previous = probe.previous
_calls = []


@contextmanager
def repair_scope():
    portfolio = probe.RECOVERY.portfolio
    old = portfolio._solve
    def repaired(v, M, J, g, dt, mu, tol, maxiter):
        try:
            return old(v, M, J, g, dt, mu, tol, maxiter)
        except RuntimeError as error:
            if len(g) > 3 or not len(g) or str(error) not in {
                'direct contact residual nonconvergence',
                'direct contact negative normal force',
                'direct contact cone violation'}:
                raise
            started = time.perf_counter()
            row = {'original_exception': str(error), 'dt_s': float(dt), 'gaps_m': list(g)}
            try:
                answer = mixed.solve(v, M, J, g, dt, mu, tol, maxiter)
                row.update(accepted=True, health=answer[1])
                return answer
            except RuntimeError as exc:
                row.update(accepted=False, repair_exception=str(exc))
                raise error
            finally:
                row['wall_s'] = time.perf_counter()-started
                _calls.append(api.normalized(row))
    portfolio._solve = repaired
    try:
        yield
    finally:
        portfolio._solve = old


def execute(spec, binding, checkpoint=None, pause=None, observe=True):
    oldcore = api.frozen.core
    _calls.clear()
    api.frozen.core = core
    try:
        with repair_scope():
            result, rows = previous.execute(spec, binding, checkpoint=checkpoint, pause=pause, observe=observe)
    finally:
        api.frozen.core = oldcore
    result['stage119_repair_calls'] = list(_calls)
    return result, rows
