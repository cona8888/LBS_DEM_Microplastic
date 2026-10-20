"""Sphere--prolate Stokes pair operator with equal-area body nodes.

The prolate surface nodes are distributed by the exact spheroid area
Jacobian rather than by mapping uniform spherical directions.  This avoids
systematically undersampling the large-area equatorial belt at aspect ratio 4.
"""
import sys
from pathlib import Path

import numpy as np
from scipy.linalg import svd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage36_staging"))
import sharp_stokes_mfs_v3 as mfs
import sharp_sphere_reference_v1 as sphere


def frame(p):
    p = np.asarray(p, float)
    p /= np.linalg.norm(p)
    e = np.eye(3)[np.argmin(abs(p))]
    q = np.cross(p, e)
    q /= np.linalg.norm(q)
    return np.column_stack((p, q, np.cross(p, q)))


def spheroid_directions(count, axes):
    """Deterministic approximately equal-area nodes for axes (a,b,b)."""
    axes = np.asarray(axes, float)
    if not np.isclose(axes[1], axes[2]):
        raise ValueError("equal-area sampler requires a spheroid")
    grid = np.linspace(-1.0, 1.0, 20001)
    jac = axes[1] * np.sqrt(axes[0] ** 2 * (1.0 - grid**2) + axes[1] ** 2 * grid**2)
    cdf = np.r_[0.0, np.cumsum((jac[:-1] + jac[1:]) * np.diff(grid) / 2.0)]
    cdf /= cdf[-1]
    mu = np.interp((np.arange(count) + 0.5) / count, cdf, grid)
    phi = (np.arange(count) * np.pi * (3.0 - np.sqrt(5.0))) % (2.0 * np.pi)
    radial = np.sqrt(np.maximum(0.0, 1.0 - mu**2))
    return np.column_stack((mu, radial * np.cos(phi), radial * np.sin(phi)))


def ellipsoid_quadrature(centre, Q, axes, nmu=40, ntheta=80):
    unit, _normal, weight = sphere.surface_quadrature(1.0, nmu, ntheta)
    axes = np.asarray(axes, float)
    inverse = unit / axes
    scale = np.prod(axes) * np.linalg.norm(inverse, axis=1)
    normals = (inverse / np.linalg.norm(inverse, axis=1)[:, None]) @ Q.T
    return centre + (unit * axes) @ Q.T, normals, weight * scale


def solve(axes, gap, angle, n_body=768, n_grain=384, rtol=1e-12):
    axes = np.asarray(axes, float)
    a = float(axes[0])
    normal = np.array([0.0, 1.0, 0.0])
    p = np.cos(angle) * normal + np.sin(angle) * np.array([1.0, 0.0, 0.0])
    Q = frame(p)
    support = np.sqrt(np.sum((axes * (Q.T @ normal)) ** 2))
    centre = normal * (1.0 + support + gap)

    grain_sources = mfs.directions(n_grain)
    grain_points = mfs.directions(3 * n_grain)
    body_sources = spheroid_directions(n_body, axes)
    body_points = spheroid_directions(3 * n_body, axes)
    confocal = np.sqrt(axes**2 - (1.0 - 0.55**2) * min(axes) ** 2)
    sources = np.vstack((0.6 * grain_sources, centre + (body_sources * confocal) @ Q.T))
    points = np.vstack((grain_points, centre + (body_points * axes) @ Q.T))
    total = n_grain + n_body
    A = mfs.kernel(points, sources, 1.0).transpose(0, 2, 1, 3).reshape(9 * total, 3 * total)
    left, singular, right = svd(A, full_matrices=False)
    keep = singular > singular[0] * rtol

    rhs = np.zeros((3 * total, 3, 6))
    body_start = 3 * n_grain
    for j in range(3):
        rhs[body_start:, :, j] = np.eye(3)[j]
        rhs[body_start:, :, j + 3] = np.cross(np.eye(3)[j], points[body_start:] - centre)
    lam = (
        right[keep].T
        @ ((left[:, keep].T @ rhs.reshape(9 * total, 6)) / singular[keep, None])
    ).reshape(total, 3, 6)

    lever = sources[n_grain:] - centre
    wrench = np.vstack(
        (
            lam[n_grain:].sum(axis=0),
            np.stack(
                [np.cross(lever, lam[n_grain:, :, j]).sum(axis=0) for j in range(6)], axis=1
            ),
        )
    )
    D = np.diag([1, 1, 1, 1 / a, 1 / a, 1 / a])
    resistance = D @ wrench @ D

    # Independent no-slip evaluation, retained by surface and motion.
    grain_eval, _gn, _gw = sphere.surface_quadrature(1.0, 24, 48)
    body_eval, _bn, _bw = ellipsoid_quadrature(centre, Q, axes, 24, 48)
    state = {"sources": sources, "mu": 1.0}
    boundary_matrix = []
    for boundary, is_body in ((grain_eval, False), (body_eval, True)):
        by_motion = np.zeros(6)
        for chunk in np.array_split(boundary, 8):
            pred = np.stack(
                [mfs.velocity(state, {"lambda": lam[:, :, j], "far_velocity": np.zeros(3)}, chunk) for j in range(6)],
                axis=2,
            )
            target = np.zeros_like(pred)
            if is_body:
                for j in range(3):
                    target[:, :, j] = np.eye(3)[j]
                    target[:, :, j + 3] = np.cross(np.eye(3)[j], chunk - centre)
            by_motion = np.maximum(by_motion, np.linalg.norm(pred - target, axis=1).max(axis=0))
        boundary_matrix.append(by_motion.tolist())
    max_error = float(np.max(boundary_matrix))

    # Independent surface-stress integration on the body.
    qp, qn, qw = ellipsoid_quadrature(centre, Q, axes)
    balance = []
    for j in range(6):
        traction = []
        for pts, normals in zip(np.array_split(qp, 16), np.array_split(qn, 16)):
            traction.append(mfs.traction(state, {"lambda": lam[:, :, j]}, pts, normals))
        traction = np.vstack(traction)
        force = (qw[:, None] * traction).sum(axis=0)
        torque = (qw[:, None] * np.cross(qp - centre, traction)).sum(axis=0)
        reference = np.r_[wrench[:3, j], wrench[3:, j]]
        balance.append(float(np.linalg.norm(np.r_[force, torque] + reference) / max(np.linalg.norm(reference), 1e-30)))

    reciprocity = float(np.linalg.norm(resistance - resistance.T) / np.linalg.norm(resistance))
    eigenvalues = np.linalg.eigvalsh((resistance + resistance.T) / 2)
    return resistance, {
        "boundary_error_max": max_error,
        "boundary_error_by_surface_motion": {"grain": boundary_matrix[0], "body": boundary_matrix[1]},
        "surface_source_balance_max": max(balance),
        "reciprocity_residual": reciprocity,
        "minimum_symmetric_eigenvalue": float(eigenvalues.min()),
        "condition": float(singular[0] / singular[-1]),
        "retained_singular_values": int(keep.sum()),
        "centre": centre.tolist(),
        "orientation_matrix": Q.tolist(),
        "body_node_distribution": "spheroid_equal_area",
    }
