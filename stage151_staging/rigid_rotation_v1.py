"""Opt-in rigid rotation; unchanged archived core and default-off arithmetic.

World-frame Euler equation: I*domega/dt + omega x (I*omega) = torque.
q_rot=a*omega and generalized torque=torque/a. The gyroscopic load is
explicit at the accepted old state; drag/contact and acceleration are implicit.
This is a first-order model candidate, not a production promotion.
"""
import ast
import copy
import hashlib
import inspect
import json
from contextlib import contextmanager
from pathlib import Path
import sys
import types
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage150_staging'))
import full_horizon_sensitivity_v1 as prior
api,engine,hot=prior.api,prior.engine,prior.hot
core=engine.runtime.core
MODE='rigid_euler_old_gyro_v1'


def binding_for(binding,enabled):
    return api.digest([binding,MODE]) if enabled else binding


def gyro_load(mass,q,ell):
    """omega x (I*omega)/a, in world coordinates, units of force."""
    return np.cross(q[3:],mass[3:,3:]@q[3:])/ell


def make_integrate():
    tree=ast.parse(inspect.getsource(core.integrate));fn=tree.body[0]
    fn.args.kwonlyargs.append(ast.arg(arg='rigid_rotation'))
    fn.args.kw_defaults.append(ast.Constant(value=False))
    fn.body[0:0]=ast.parse("""
if type(rigid_rotation) is not bool:
    raise ValueError('rigid_rotation must be an explicit bool')
checkpoint_binding = binding_for(checkpoint_binding, rigid_rotation)
""").body
    counts={'mass':0,'body':0,'dt':0}
    class Change(ast.NodeTransformer):
        def visit_Assign(self,node):
            text=ast.unparse(node)
            if text=='mass[3:, 3:] = 0.0':
                counts['mass']+=1
                return ast.If(test=ast.UnaryOp(op=ast.Not(),operand=ast.Name(id='rigid_rotation',ctx=ast.Load())),body=[node],orelse=[])
            if text.startswith('body_load = np.r_['):
                counts['body']+=1
                return [node,*ast.parse("""
if rigid_rotation:
    body_load[3:] -= gyro_load(mass,q,a)
""").body]
            if text.startswith('dt = min(max_dt, horizon - t,'):
                counts['dt']+=1
                return [node,*ast.parse("""
if rigid_rotation:
    tau_rot = np.linalg.eigvalsh(mass[3:,3:]).min()/np.linalg.eigvalsh(resistance[3:,3:]).max()
    dt = min(dt,relaxation_fraction*tau_rot)
""").body]
            return self.generic_visit(node)
    Change().visit(tree)
    if counts!={'mass':1,'body':1,'dt':1}:raise RuntimeError('archived core structure changed: '+str(counts))
    ast.fix_missing_locations(tree)
    namespace=dict(core.__dict__);namespace.update(binding_for=binding_for,gyro_load=gyro_load)
    exec(compile(tree,'<Stage151:explicit_rigid_rotation>','exec'),namespace)
    return namespace['integrate'],ast.unparse(tree)


INTEGRATE,GENERATED_SOURCE=make_integrate()


@contextmanager
def scope(enabled=False):
    if type(enabled) is not bool:raise ValueError('explicit bool required')
    if not enabled:
        yield
        return
    replacement=types.ModuleType('stage151_checkpoint_core')
    replacement.__dict__.update(core.__dict__)
    def integrate(*args,**kwargs):
        if 'rigid_rotation' in kwargs:raise ValueError('duplicate rotation mode')
        return INTEGRATE(*args,**kwargs,rigid_rotation=True)
    replacement.integrate=integrate
    original=engine.runtime.core;engine.runtime.core=replacement
    try:yield
    finally:engine.runtime.core=original


def checkpoint(spec,binding,source,enabled):
    cp=copy.deepcopy(source)
    cp['contract']=engine.prior.contracts.expected_contract(spec,binding_for(binding,enabled))
    return cp
