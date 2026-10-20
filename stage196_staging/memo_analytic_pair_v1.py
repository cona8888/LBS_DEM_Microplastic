"""Cache one pure residual/Jacobian pair within one optimizer system only.

No contact force, mode or state is reused across physical poses. All arithmetic
is performed by the frozen Stage194 function. Returned arrays are copied so a
consumer cannot mutate a cached value. Float input bytes include signed zero.
"""
from contextlib import contextmanager
import numpy as np
import early_semismooth_dispatch_v1 as repair

@contextmanager
def scope(enabled=False):
    if type(enabled) is not bool:
        raise ValueError('explicit Boolean opt-in')
    if not enabled:
        yield; return
    analytic = repair.prior.analytic
    original = analytic.system
    def system(*args):
        both, *rest = original(*args)
        previous_key = previous_value = None
        def cached(y):
            nonlocal previous_key, previous_value
            a = np.asarray(y)
            key = (a.shape, a.dtype.str, a.tobytes())
            if key != previous_key:
                value = both(y)
                previous_value = tuple(v.copy() for v in value)
                previous_key = key
            return tuple(v.copy() for v in previous_value)
        return (cached, *rest)
    analytic.system = system
    try:
        yield
    finally:
        analytic.system = original
