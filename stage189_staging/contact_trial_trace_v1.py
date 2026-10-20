"""Scoped observation of Stage79/42 inner solves; no numerical changes.

All backend calls get a sequential trial ID and inner-call count. Detailed
systems are retained only for trials that exercised early or fallback routes.
The Stage42 function is changed at one call site only, to observe the exact
input and return of the currently installed Stage41 solver (including reuse).
"""
from contextlib import contextmanager
from pathlib import Path
import ast
import copy
import hashlib
import inspect
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'stage187_staging'), str(ROOT / 'stage79_staging')]
import integrated_paired_campaign_v1 as old
import inertial_contact_within_pose_reuse_v1 as backend

SCHEMA = 'stage189-explicit-inner-trial-v1'
_active = False


def clone_step(original, observer):
    source = inspect.getsource(original)
    tree = ast.parse(source)
    count = 0

    class Observe(ast.NodeTransformer):
        def visit_Call(self, node):
            nonlocal count
            if (isinstance(node.func, ast.Attribute) and node.func.attr == '_solve_prepared'
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == 'stage41'):
                count += 1
                return ast.copy_location(ast.Call(func=ast.Name(id='_observe_inner', ctx=ast.Load()),
                    args=[node.func, ast.Name(id='iteration', ctx=ast.Load()), *node.args], keywords=node.keywords), node)
            return self.generic_visit(node)

    Observe().visit(tree)
    if count != 1:
        raise RuntimeError('exactly one original inner-solver call required')
    ast.fix_missing_locations(tree)
    namespace = {**original.__globals__, '_observe_inner': observer}
    exec(compile(tree, str(Path(__file__).resolve()) + '::observation_only', 'exec'), namespace)
    identity = {'original_source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                'observed_ast_sha256': hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest(),
                'solver_calls_wrapped': count, 'other_ast_edits': 0}
    return namespace[original.__name__], identity


def plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    return copy.deepcopy(value)


@contextmanager
def scope(runtime, enabled=False):
    global _active
    if type(enabled) is not bool:
        raise ValueError('explicit Boolean observation mode required')
    if not enabled:
        yield None
        return
    if _active:
        raise RuntimeError('nested contact trial observer is unsupported')
    original_outer = backend.inertial_contact_step
    original_inner_step = backend.stage42.inertial_contact_step
    log = {'schema': SCHEMA, 'trial_inner_counts': [], 'trial_route_counts': [], 'detailed_trials': []}
    current = None

    def observe_inner(solver, inner_index, v, M, J, g, dt, mu, tol, maxiter):
        if current is None or inner_index != len(current['inner_systems']):
            raise RuntimeError('inner solver outside a sequential observed trial')
        lo, lf = len(old.fast.attempts), len(old.capture.records)
        item = {'inner_index': inner_index, 'vfree': plain(v), 'mobility': plain(M),
                'jacobian': plain(J), 'gaps_m': plain(g), 'dt_s': float(dt),
                'friction': float(mu), 'tolerance': float(tol), 'maxiter': int(maxiter)}
        current['inner_systems'].append(item)
        try:
            answer = solver(v, M, J, g, dt, mu, tol, maxiter)
        except Exception as error:
            item.update(accepted=False, error=repr(error))
            raise
        else:
            item.update(accepted=True, velocity=plain(answer[0]), health=plain(answer[1]))
            return answer
        finally:
            item['early_range'] = [lo, len(old.fast.attempts)]
            item['fallback_range'] = [lf, len(old.capture.records)]

    observed_step, identity = clone_step(original_inner_step, observe_inner)
    log['structural_identity'] = identity

    def outer(*args, **kwargs):
        nonlocal current
        if current is not None:
            raise RuntimeError('nested outer contact call')
        if kwargs or len(args) != 14:
            raise RuntimeError('qualified positional outer contact interface required')
        lo, lf = len(old.fast.attempts), len(old.capture.records)
        current = {'trial_index': len(log['trial_inner_counts']), 'inner_systems': [],
                   'outer_inputs': [plain(v) for v in args], 'early_range': [lo, lo],
                   'fallback_range': [lf, lf]}
        try:
            answer = original_outer(*args, **kwargs)
        except Exception as error:
            current.update(accepted=False, error=repr(error))
            raise
        else:
            current.update(accepted=True, velocity=plain(answer[0]), health=plain(answer[1]))
            return answer
        finally:
            current['early_range'][1] = len(old.fast.attempts)
            current['fallback_range'][1] = len(old.capture.records)
            log['trial_inner_counts'].append(len(current['inner_systems']))
            log['trial_route_counts'].append([len(old.fast.attempts)-lo, len(old.capture.records)-lf])
            if not current['accepted'] or len(old.fast.attempts) != lo or len(old.capture.records) != lf:
                log['detailed_trials'].append(current)
            current = None

    _active = True
    backend.inertial_contact_step = outer
    backend.stage42.inertial_contact_step = observed_step
    try:
        yield log
    finally:
        backend.inertial_contact_step = original_outer
        backend.stage42.inertial_contact_step = original_inner_step
        _active = False


STRUCTURAL_IDENTITY = clone_step(backend.stage42.inertial_contact_step, None)[1]
