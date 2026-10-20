"""Auditable CPU D3Q19/IB reference for a fixed sphere in a periodic cell."""
from __future__ import annotations

import math
import numpy as np
from scipy.sparse import csr_matrix

import immersed_interface_v1 as ib
from body_link_extractor_v1 import C, W
from moving_wall_reference_v1 import equilibrium


def surface(radius: float, count: int) -> np.ndarray:
    if radius <= 0 or count < 32:
        raise ValueError("invalid sphere surface")
    j = np.arange(count)
    z = 1.0 - 2.0 * (j + 0.5) / count
    theta = j * math.pi * (3.0 - math.sqrt(5.0))
    return radius * np.column_stack((np.sqrt(1-z*z)*np.cos(theta), np.sqrt(1-z*z)*np.sin(theta), z))


def interpolation_matrix(points: np.ndarray, n: int) -> csr_matrix:
    ids, weights, _ = ib.stencil(points, n, 1.0)
    return csr_matrix((weights.ravel(), (np.repeat(np.arange(len(points)), 64), ids.ravel())), shape=(len(points), n**3))


def trilinear(field: np.ndarray, points: np.ndarray, n: int) -> np.ndarray:
    a = points - 0.5
    base = np.floor(a).astype(int)
    frac = a - base
    if np.any(base < 0) or np.any(base + 1 >= n):
        raise ValueError("interior quadrature crosses outer seam")
    out = np.zeros((len(points), field.shape[1]))
    for i in (0, 1):
        for j in (0, 1):
            for k in (0, 1):
                corner = np.array([i, j, k])
                weight = np.prod(np.where(corner, frac, 1-frac), axis=1)
                idx = np.ravel_multi_index((base + corner).T, (n, n, n))
                out += field[idx] * weight[:, None]
    return out


def interior_momentum(f: np.ndarray, centre: np.ndarray, radius: float) -> np.ndarray:
    n = f.shape[1]
    body, volume = ib.sphere_quadrature(radius, 8, 16, 32)
    flat = f.reshape(19, -1)
    fields = np.column_stack((flat.sum(axis=0), (C.T @ flat).T))
    return volume @ trilinear(fields, body + centre, n)[..., 1:]


def marker_projection(f: np.ndarray, matrix: csr_matrix) -> tuple[np.ndarray, np.ndarray, float, float]:
    flat = f.reshape(19, -1)
    rho = flat.sum(axis=0)
    velocity = (C.T @ flat).T / rho[:, None]
    rhs = -(matrix @ velocity)
    gram = (matrix.multiply(1/rho) @ matrix.T).toarray()
    condition = float(np.linalg.cond(gram))
    if not np.isfinite(condition) or condition > 1e10:
        raise ValueError("ill-conditioned marker system")
    marker_impulse = np.linalg.solve(gram, rhs)
    grid_impulse = matrix.T @ marker_impulse
    updated_velocity = velocity + grid_impulse/rho[:, None]
    updated = flat + equilibrium(rho, updated_velocity.T) - equilibrium(rho, velocity.T)
    slip = float(np.max(np.abs(matrix @ updated_velocity)))
    return updated.reshape(f.shape), marker_impulse, slip, condition


def initialize(n: int, marker_count: int | None = None) -> dict:
    if n not in (32, 48, 64):
        raise ValueError("grid outside frozen ladder")
    radius = n/8.0
    centre = np.full(3, n/2.0)
    count = marker_count or {32: 256, 48: 576, 64: 1024}[n]
    points = surface(radius, count) + centre
    matrix = interpolation_matrix(points, n)
    f = equilibrium(np.ones(n**3), np.zeros((3, n**3))).reshape(19, n, n, n)
    return {"n": n, "radius": radius, "centre": centre, "marker_count": count, "points": points, "matrix": matrix, "f": f}


def nominal_parameters(n: int, drag_ratio: float = 1.530329436009) -> dict:
    radius = n/8.0
    nu = 0.1
    target_u = 0.05*nu/(2*radius)
    force = 6*math.pi*nu*radius*target_u*drag_ratio
    return {"target_u_lu": target_u, "reference_force_lu": force, "source_impulse_per_cell": force/n**3,
            "viscous_window_steps": int(round(n*n/nu)), "minimum_post_start_windows": 5}


def step(state: dict, source_impulse_per_cell: float) -> tuple[dict, dict]:
    f = state["f"]
    n, centre, radius, matrix = state["n"], state["centre"], state["radius"], state["matrix"]
    if not np.isfinite(source_impulse_per_cell) or source_impulse_per_cell < 0 or source_impulse_per_cell > 1e-4:
        raise ValueError("invalid source impulse")
    flat = f.reshape(19, -1)
    rho = flat.sum(axis=0)
    velocity = (C.T @ flat).T/rho[:, None]
    post = flat - (flat-equilibrium(rho, velocity.T))/.8
    post_velocity = velocity.copy()
    post_velocity[:, 0] += source_impulse_per_cell/rho
    forced = post + equilibrium(rho, post_velocity.T)-equilibrium(rho, velocity.T)
    source_actual = (C.T @ (forced-post)).T
    streamed = np.stack([np.roll(forced[q].reshape(n,n,n), tuple(C[q]), axis=(0,1,2)) for q in range(19)])
    p_before = (C.T @ flat).sum(axis=1)
    interior_before = interior_momentum(streamed, centre, radius)
    projected, marker_impulses, slip, condition = marker_projection(streamed, matrix)
    p_after = (C.T @ projected.reshape(19,-1)).sum(axis=1)
    interior_after = interior_momentum(projected, centre, radius)
    marker_total = marker_impulses.sum(axis=0)
    source_total = source_actual.sum(axis=0)
    body, volume = ib.sphere_quadrature(radius, 8, 16, 32)
    source_inside = volume @ trilinear(source_actual, body+centre, n)
    force = -marker_total + interior_after-interior_before-source_inside
    ledger = p_after-p_before-source_total-marker_total
    new_state = dict(state); new_state["f"] = projected
    record = {"superficial_velocity": (p_after/n**3).tolist(), "force_on_sphere": force.tolist(),
              "source_impulse": source_total.tolist(), "interior_source_impulse": source_inside.tolist(),
              "marker_impulse_on_fluid": marker_total.tolist(), "momentum_ledger_residual": ledger.tolist(),
              "marker_slip": slip, "condition_number": condition, "mass_relative_drift": abs(float(projected.sum())/n**3-1),
              "density_error": float(np.max(np.abs(projected.sum(axis=0)-1))), "minimum_population": float(projected.min())}
    return new_state, record
