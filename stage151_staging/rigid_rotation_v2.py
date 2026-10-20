"""Runtime-binding correction only; Stage151 v1 mechanics are unchanged.

The archived checkpoint trampoline installs its contact backend immediately
before integrate(). Bind the generated function at that point, not at import.
The failed v1 attempt and all its files remain immutable.
"""
from contextlib import contextmanager
import types
from rigid_rotation_v1 import *
import rigid_rotation_v1 as original

calls=[]


@contextmanager
def scope(enabled=False):
    if type(enabled) is not bool:raise ValueError('explicit bool required')
    if not enabled:
        yield
        return
    replacement=types.ModuleType('stage151_checkpoint_core_live_bound')
    replacement.__dict__.update(core.__dict__)
    def integrate(*args,**kwargs):
        if 'rigid_rotation' in kwargs:raise ValueError('duplicate rotation mode')
        namespace=dict(original.INTEGRATE.__globals__)
        namespace['inertial']=replacement.inertial
        if not hasattr(namespace['inertial'],'set_recovery_mode'):
            raise RuntimeError('live checkpoint contact backend not installed')
        bound=types.FunctionType(original.INTEGRATE.__code__,namespace,argdefs=original.INTEGRATE.__defaults__)
        bound.__kwdefaults__=dict(original.INTEGRATE.__kwdefaults__)
        calls.append({'backend':str(replacement.inertial.__file__),'enabled':True})
        return bound(*args,**kwargs,rigid_rotation=True)
    replacement.integrate=integrate
    saved=engine.runtime.core;engine.runtime.core=replacement
    try:yield
    finally:engine.runtime.core=saved
