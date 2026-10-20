"""Fixed-geometry CPU optimization; NOT a qualified moving-particle solver.

Same constant-reference-density projection as the fast reference. Geometry
must stay fixed. Corrected traction uses interior momentum over the FULL step.
Legacy force is retained solely for regression, never as a physical observable.
All impulses have dt=1 in lattice units; pressure-gradient contribution is
reported separately to prevent changing force conventions silently.
"""
import numpy as np
from scipy.linalg import cho_solve
import periodic_drag_reference_fast_v1 as reference
from body_link_extractor_v1 import C
from moving_wall_reference_v1 import equilibrium


def prepare(state):
    s = dict(state)
    n = s['n']
    body, volume = reference.base.ib.sphere_quadrature(s['radius'], 8, 16, 32)
    a = body + s['centre'] - .5
    lower = np.floor(a).astype(int)
    frac = a - lower
    if np.any(lower < 0) or np.any(lower + 1 >= n):
        raise ValueError('interior quadrature crosses seam')
    weights = np.zeros(n**3)
    for i in (0, 1):
        for j in (0, 1):
            for k in (0, 1):
                corner = np.array([i, j, k])
                w = volume * np.prod(np.where(corner, frac, 1-frac), axis=1)
                ids = np.ravel_multi_index((lower+corner).T, (n, n, n))
                np.add.at(weights, ids, w)
    ids = np.flatnonzero(weights)
    s['interior_ids'], s['interior_weights'] = ids, weights[ids]
    active = np.unique(s['matrix'].indices)
    s['active_ids'] = active
    s['local_matrix'] = s['matrix'][:, active].tocsr()
    s['local_transpose'] = s['local_matrix'].T.tocsr()
    # Cheap pose guard; this API does not support edits to matrix/marker arrays.
    s['fixed_pose'] = (n, float(s['radius']), tuple(s['centre']))
    return s


def initialize(n):
    return prepare(reference.initialize(n))


def interior_integral(state, vector_field):
    return state['interior_weights'] @ vector_field[state['interior_ids']]


def step(state, source_impulse_per_cell):
    n = state['n']
    if (n, float(state['radius']), tuple(state['centre'])) != state['fixed_pose']:
        raise ValueError('geometry changed: rebuild cache, do not reuse fixed-sphere solver')
    if not np.isfinite(source_impulse_per_cell) or not 0 <= source_impulse_per_cell <= 1e-4:
        raise ValueError('invalid source impulse')
    flat = state['f'].reshape(19, -1)
    rho = flat.sum(axis=0)
    momentum0 = (C.T @ flat).T
    u = momentum0 / rho[:, None]
    eq0 = equilibrium(rho, u.T)
    post = flat - (flat-eq0)/.8
    uf = u.copy()
    uf[:, 0] += source_impulse_per_cell/rho
    forced = post + equilibrium(rho, uf.T) - eq0
    source_actual = (C.T @ (forced-post)).T
    streamed = np.stack([np.roll(forced[q].reshape(n,n,n), tuple(C[q]), axis=(0,1,2)) for q in range(19)])
    stream_flat = streamed.reshape(19, -1)
    pi_stream = interior_integral(state, (C.T @ stream_flat).T)
    active = state['active_ids']
    local = stream_flat[:, active]
    local_rho = local.sum(axis=0)
    local_u = (C.T @ local).T / local_rho[:, None]
    J = state['local_matrix']
    marker = cho_solve(state['factor'], -(J @ local_u), check_finite=False)
    up = local_u + (state['local_transpose'] @ marker) / local_rho[:, None]
    stream_flat[:, active] = local + equilibrium(local_rho, up.T) - equilibrium(local_rho, local_u.T)
    momentum1 = (C.T @ stream_flat).T
    mt, st = marker.sum(axis=0), source_actual.sum(axis=0)
    pi0 = interior_integral(state, momentum0)
    pi1 = interior_integral(state, momentum1)
    si = interior_integral(state, source_actual)
    traction = -mt + pi1 - pi0 - si
    p0, p1 = momentum0.sum(axis=0), momentum1.sum(axis=0)
    target = float(n**3)
    raw_mass = float(streamed.sum(dtype=np.float64))
    delta = target - raw_mass
    if not np.isfinite(delta) or abs(delta) > 1e-9:
        raise ValueError('mass correction outside qualified bound')
    streamed[0,0,0,0] += delta
    residual = target - streamed.sum(dtype=np.float64)
    streamed[0,0,0,0] += residual
    delta += residual
    if not np.isfinite(streamed).all() or streamed.min() <= 0:
        raise ValueError('invalid populations')
    new = dict(state)
    new['f'] = streamed
    row = {
        'superficial_velocity': (p1/n**3).tolist(),
        'force_on_sphere': traction.tolist(),
        'force_convention': 'periodic-stress traction, full-step interior inertia, dt=1',
        'total_with_pressure_gradient': (traction+si).tolist(),
        'legacy_substep_force_NOT_PHYSICAL': (-mt+pi1-pi_stream-si).tolist(),
        'full_step_interior_momentum_change': (pi1-pi0).tolist(),
        'projection_substep_interior_momentum_change': (pi1-pi_stream).tolist(),
        'marker_impulse_on_fluid': mt.tolist(), 'source_impulse': st.tolist(),
        'interior_source_impulse': si.tolist(),
        'momentum_ledger_residual': (p1-p0-st-mt).tolist(),
        'marker_slip': float(np.max(np.abs(J@up))),
        'condition_number': state['factor_condition'],
        'mass_relative_drift_before_restoration': abs(raw_mass/target-1),
        'mass_relative_drift': abs(float(streamed.sum())/target-1),
        'mass_restoration_lu': float(delta),
        'density_error': float(np.max(np.abs(streamed.sum(axis=0)-1))),
        'minimum_population': float(streamed.min()),
    }
    return new, row
