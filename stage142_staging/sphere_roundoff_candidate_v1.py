"""Experimental sphere-only geometric backward-error certificate.

This is an explicit numerical-contract revision, NOT an exact raw-gap solve.
Raw gaps remain unchanged and raw residuals are reported. A static candidate
is accepted only if it solves the original Coulomb/force equations for gaps
within a predeclared floating-point-scale spatial budget. The budget does
not grow when dt shrinks. No pose projection, time skip, material change,
force warm start or non-spherical use is allowed.
"""
from contextlib import contextmanager, nullcontext
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'stage139_staging'))
import sphere_only_verification_v1 as parent
fast = parent.fast
work = {'calls': 0, 'original_candidate': 0, 'roundoff_candidate': 0, 'fallback': 0}


def length_budget(cell_length, multiplier=64):
    if not np.isfinite(cell_length) or cell_length <= 0 or multiplier not in (16, 32, 64):
        raise ValueError('invalid geometric error budget')
    # Conservative local arithmetic budget, not a bound on accumulated path
    # error. 16/32/64 are tested as numerical sensitivity levels, not fitted.
    eps = np.finfo(float).eps
    return multiplier*eps/(1-multiplier*eps)*cell_length


def candidate(v, M, J, gaps, dt, mu, tol, maxiter, *, gap_budget_m):
    g = np.asarray(gaps, float)
    if not np.isfinite(gap_budget_m) or gap_budget_m <= 0:
        raise ValueError('invalid gap budget')
    try:
        q, h = fast.candidate(v, M, J, g, dt, mu, tol, maxiter)
    except (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError):
        pass
    else:
        work['original_candidate'] += 1
        h = dict(h); h['geometric_contract'] = 'original_signed_gaps'
        return q, h
    if not 1 <= len(g) <= 3 or not np.isfinite(g).all() or np.max(np.abs(g)) > gap_budget_m:
        raise ValueError('raw signed gap outside roundoff budget')
    q, h = fast.candidate(v, M, J, np.zeros_like(g), dt, mu, tol, maxiter)
    f = np.asarray(h['reactions']); vc = np.asarray(J)@q
    # A nearby gap vector makes this same q satisfy all active normal
    # equalities. Neither g nor the stored geometry is mutated.
    effective = -dt*vc[::3]
    perturb = effective-g
    if np.max(np.abs(perturb)) > gap_budget_m:
        raise RuntimeError('required geometric backward error exceeds budget')
    scale = max(np.linalg.norm(v), 1e-15)
    if np.linalg.norm(q) > 1e-10*scale:
        raise RuntimeError('roundoff branch must be static to velocity precision')
    A = J@M@J.T; z = J@v
    steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max() for k in range(len(g))])
    # Recheck every unchanged force, cone, velocity-projection and energy gate
    # for the EXPLICIT effective gaps; never label this as a raw-gap pass.
    q, health = parent.hot.s50._finish(v, M, J, f, z, A, effective, dt, mu, steps, h['iterations'],
        'stage142_sphere_geometric_backward_error', {})
    raw = parent.hot.s50._residual(f, z, A, g, dt, mu, steps)/scale
    health.update(geometric_contract='sphere_local_roundoff_budget_v1',
        raw_gaps_m=g.tolist(), effective_gaps_m=effective.tolist(), gap_perturbation_m=perturb.tolist(),
        gap_budget_m=float(gap_budget_m), raw_signed_gap_residual=float(raw),
        maximum_geometric_backward_error_m=float(np.max(np.abs(perturb))),
        exact_raw_gap_solve=bool(raw <= 1e-10))
    work['roundoff_candidate'] += 1
    return q, health


def independently_check(v, M, J, g, dt, mu, q, h):
    if h.get('geometric_contract') == 'original_signed_gaps':
        return parent.engine.local.independent_contact(v, M, J, g, dt, mu, q, h)
    f = np.asarray(h['reactions']); effective = np.asarray(h['effective_gaps_m'])
    raw = np.asarray(g); budget = h['gap_budget_m']
    close = np.linalg.norm(q-(v+M@J.T@f)) <= 1e-12*max(np.linalg.norm(v), 1e-15)
    unchanged = np.array_equal(raw, np.asarray(h['raw_gaps_m']))
    bounded = np.max(np.abs(effective-raw)) <= budget
    normal_closure = np.max(np.abs(effective+dt*(J@q)[::3])) <= 1e-10*budget
    velocity = np.linalg.norm(q) <= 1e-10*max(np.linalg.norm(v), 1e-15)
    original_force_gates = parent.engine.local.independent_contact(v, M, J, effective, dt, mu, q, h)
    return bool(close and unchanged and bounded and normal_closure and velocity and original_force_gates)


@contextmanager
def scope(spec, multiplier=64):
    a, b, c = spec['config']['prolate_semiaxes_m']
    if not a == b == c:
        with nullcontext():
            yield
        return
    budget = length_budget(spec['field_metadata']['cell_length_m'], multiplier)
    portfolio = fast.portfolio; old = portfolio._solve
    def solve(*args, **kwargs):
        work['calls'] += 1
        try:
            return candidate(*args, **kwargs, gap_budget_m=budget)
        except (ValueError, RuntimeError, FloatingPointError, np.linalg.LinAlgError):
            work['fallback'] += 1
            return old(*args, **kwargs)
    portfolio._solve = solve
    try:
        yield
    finally:
        portfolio._solve = old
