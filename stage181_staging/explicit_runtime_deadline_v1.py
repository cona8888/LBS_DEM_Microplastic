"""Resource-only deadline binding for the immutable Stage172 contact scope.

The original generator bytecode, contact dispatch, solver, gates and fallback
are unchanged. A copied execution namespace supplies only END_UTC. This API is
not launch authority: callers must hash-bind an approved resource contract and
also check time/disk before each bounded integration segment.
"""
from contextlib import contextmanager
import datetime,types,time
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage172_staging'))
import reduced_contact_fast_v1 as original


def parse_deadline(value):
    if type(value) is not str:
        raise ValueError('explicit UTC ISO deadline required')
    result=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None or result.utcoffset()!=datetime.timedelta(0):
        raise ValueError('timezone-aware UTC deadline required')
    return result.timestamp()


def bind_scope(deadline_utc):
    deadline=parse_deadline(deadline_utc)
    generator=original.scope.__wrapped__
    namespace=dict(generator.__globals__)
    namespace['END_UTC']=deadline
    cloned=types.FunctionType(generator.__code__,namespace,generator.__name__,
                              generator.__defaults__,generator.__closure__)
    return contextmanager(cloned)


@contextmanager
def scope(runtime,deadline_utc,enabled=False):
    if type(enabled) is not bool:
        raise ValueError('explicit Boolean mode required')
    deadline=parse_deadline(deadline_utc)
    if enabled and time.time()>=deadline:
        raise RuntimeError('explicit execution deadline reached')
    with bind_scope(deadline_utc)(runtime,enabled):
        yield


def structural_identity(deadline_utc):
    """Audit that only the resource timestamp differs in the namespace."""
    old=original.scope.__wrapped__;new=bind_scope(deadline_utc).__wrapped__
    different={k for k in old.__globals__ if old.__globals__[k] is not new.__globals__[k]}
    return {'same_code_object':new.__code__ is old.__code__,
            'same_defaults':new.__defaults__ is old.__defaults__,
            'same_closure':new.__closure__ is old.__closure__,
            'namespace_differences':sorted(different),
            'original_deadline_unchanged':original.END_UTC==old.__globals__['END_UTC'],
            'explicit_deadline':new.__globals__['END_UTC']}
