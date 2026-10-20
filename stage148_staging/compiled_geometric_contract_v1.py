"""Stage148 scoped sphere-only numerical contract; historical modules untouched.

This is a numerical-method revision, not an equivalent optimization. Normal AND
tangential projected residuals receive an absolute velocity allowance delta/dt.
The friction-work allowance is declared separately, never described as unchanged
physics. Delta is a local arithmetic sensitivity parameter, not a rigorous global
error bound. No warm start, branch enumeration, inertia change or pose snap.
"""
from contextlib import contextmanager
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'stage139_staging'))
import sphere_only_verification_v1 as parent
hot = parent.hot


def audit(v, M, J, g, dt, mu, q, force, delta, tol):
    """Independent NumPy certificate, not the compiled stopping calculation."""
    v, M, J, g, q, f = [np.asarray(x, float) for x in (v, M, J, g, q, force)]
    A, z = J@M@J.T, J@v
    vc = z+A@f
    scale = max(float(np.linalg.norm(v)), 1e-15)
    ceiling = max(tol*scale, delta/dt)
    residual = 0.
    for k in range(len(g)):
        i = 3*k
        step = np.linalg.eigvalsh(A[i+1:i+3, i+1:i+3]).max()
        residual = max(residual, abs(min(A[i, i]*f[i], vc[i]+g[k]/dt)))
        trial = f[i+1:i+3]-vc[i+1:i+3]/step
        projection = trial*min(1., mu*f[i]/max(np.linalg.norm(trial), 1e-300))
        residual = max(residual, np.linalg.norm(f[i+1:i+3]-projection)*step)
    load = J.T@f
    closure = np.linalg.norm(np.linalg.solve(M, q-v)-load)/max(np.linalg.norm(load), 1e-30)
    reproduction = np.linalg.norm(q-(v+M@load))/scale
    work = sum(float(f[3*k+1:3*k+3]@vc[3*k+1:3*k+3]) for k in range(len(g)))
    old_work_limit = 1e-8*max(np.linalg.norm(f)*scale, 1e-30)
    # Only the explicit geometric part is additive; unlike Stage145, delta=0
    # does not add |ft|*tol*scale to the old energy gate.
    extra_work_limit = sum(np.linalg.norm(f[3*k+1:3*k+3]) for k in range(len(g)))*delta/dt
    cone = all(np.linalg.norm(f[3*k+1:3*k+3]) <= mu*f[3*k]+1e-12*max(np.linalg.norm(f), 1e-30)
               for k in range(len(g)))
    checks = {
        'finite': all(np.isfinite(x).all() for x in [q, f, vc]) and np.isfinite([closure, reproduction, work, residual]).all(),
        'nonnegative_normals': bool(np.all(f[::3] >= 0)),
        'circular_coulomb_cones': bool(cone),
        'contact_residual_within_declared_ceiling': bool(residual <= ceiling),
        'force_closure': bool(closure <= 1e-8),
        'velocity_reconstruction': bool(reproduction <= 1e-12),
        'friction_work_within_declared_allowance': bool(work <= old_work_limit+extra_work_limit),
    }
    return {'passed': all(checks.values()), 'checks': checks,
            'raw_residual_m_s': float(residual), 'legacy_residual_over_vfree': float(residual/scale),
            'velocity_ceiling_m_s': float(ceiling), 'residual_over_ceiling': float(residual/ceiling),
            'force_residual': float(closure), 'friction_work_W': float(work),
            'legacy_friction_work_limit_W': float(old_work_limit),
            'added_geometric_work_limit_W': float(extra_work_limit),
            'legacy_work_gate_pass': bool(work <= old_work_limit),
            'delta_geom_m': float(delta), 'dt_s': float(dt),
            'normal_poststep_gap_m': (g+dt*(J@q)[::3]).tolist()}


def solve(v, M, J, g, dt, mu, tol, maxiter, *, delta):
    if not np.isfinite([dt, mu, tol, delta]).all() or dt <= 0 or mu < 0 or tol <= 0 or delta <= 0:
        raise ValueError('invalid geometric contract inputs')
    v, M, J, g = [np.asarray(x, float) for x in (v, M, J, g)]
    if not len(g):
        return v, {'iterations': 0, 'residual': 0., 'force_residual': 0., 'dissipation': 0.,
                   'reactions': [], 'solver': 'stage148_free'}, None
    if len(g) > 3:
        raise ValueError('Stage148 qualification restricted to at most three contacts')
    A, z = J@M@J.T, J@v
    scale = max(float(np.linalg.norm(v)), 1e-15)
    ceiling = max(tol*scale, delta/dt)
    steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max() for k in range(len(g))])
    force, used, converged = hot.phase(A, z, g, dt, mu, steps, scale, ceiling/scale, maxiter)
    if not converged:
        raise RuntimeError('direct contact residual nonconvergence')
    q = v+M@J.T@force
    check = audit(v, M, J, g, dt, mu, q, force, delta, tol)
    if not check['passed']:
        raise RuntimeError('Stage148 independent certificate failed: '+str(check['checks']))
    health = {'iterations': used, 'residual': check['raw_residual_m_s']/max(scale, delta/(dt*tol)),
              'force_residual': check['force_residual'], 'dissipation': -check['friction_work_W'],
              'reactions': force.tolist(), 'solver': 'stage148_compiled_geometric_pgs',
              'numerical_contract': 'sphere_projected_residual_geometric_allowance_v1',
              'legacy_residual_over_vfree': check['legacy_residual_over_vfree'],
              'residual_velocity_units': check['raw_residual_m_s'],
              'velocity_ceiling': ceiling, 'delta_geom_m': delta,
              'work_ceiling': check['legacy_friction_work_limit_W']+check['added_geometric_work_limit_W']}
    return q, health, check


@contextmanager
def scope(spec, *, enabled=False, multiplier=16, certificates=None):
    if not enabled or len(set(spec['config']['prolate_semiaxes_m'])) != 1:
        yield
        return
    if multiplier not in (8, 16, 64):
        raise ValueError('undeclared spatial multiplier')
    # Qualification windows remain within one coordinate-scale L. The dispatcher
    # independently checks that bound; arbitrary unwrapped trajectories excluded.
    delta = multiplier*np.finfo(float).eps*spec['field_metadata']['cell_length_m']
    portfolio = parent.fast.portfolio
    old = portfolio._solve
    def checked(*args, **kwargs):
        q, h, check = solve(*args, **kwargs, delta=delta)
        if check is not None and certificates is not None:
            certificates.append(check)
        return q, h
    portfolio._solve = checked
    try:
        yield
    finally:
        portfolio._solve = old
