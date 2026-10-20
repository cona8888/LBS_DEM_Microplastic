"""Opt-in stateless candidate inside the unchanged Stage172 near-rest guard.

The original fast solve remains first. On failure, same-system seed refinement
can supply a candidate before primary/general retries. Stage172 still checks
the original nearly-closed input and 1e-4 outgoing/free-speed limits. Original
early successes are unchanged; other ordering equivalence requires tests.
"""
from contextlib import contextmanager
from types import FunctionType,SimpleNamespace
import numpy as np
import semismooth_rejected_seed_v1 as prior
NAME=prior.NAME;ERRORS=prior.ERRORS

@contextmanager
def scope(runtime,enabled=False,stop_epoch=None):
    if type(enabled) is not bool:raise ValueError('explicit Boolean opt-in required')
    if not enabled:yield;return
    original=prior.fast.solve
    ns={**prior.solve.__globals__,'fast':SimpleNamespace(solve=original)}
    solve=FunctionType(prior.solve.__code__,ns,'solve',prior.solve.__defaults__,prior.solve.__closure__)
    # Use the identical fallback scope bytecode, with an explicitly bound seed
    # producer. This prevents recursion when the early fast function is patched.
    generator=prior.scope.__wrapped__
    bound=FunctionType(generator.__code__,{**generator.__globals__,'solve':solve},generator.__name__,generator.__defaults__,generator.__closure__)
    def early_candidate(*args):
        try:return original(*args)
        except RuntimeError as error:
            if str(error) not in ERRORS:raise
            try:return solve(*args,stop_epoch=stop_epoch)
            except (RuntimeError,ValueError,np.linalg.LinAlgError,FloatingPointError):raise error
    with contextmanager(bound)(runtime,True,stop_epoch):
        prior.fast.solve=early_candidate
        try:yield
        finally:prior.fast.solve=original
