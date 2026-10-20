"""Small contact-set active-mode solver; original gaps and Coulomb law.

The contact velocities are parameterized in the nullspace of exact closed
normal/stick constraints. Force balance and sliding directions are solved
in separately scaled velocity/force coordinates. Every candidate is judged
by the unchanged Stage50 physical gates, not optimizer success.
"""
from __future__ import annotations
from itertools import product
from pathlib import Path
import sys
import numpy as np
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage50_staging"))
import inertial_contact_seeded_lm_v1 as original


def solve(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
    v, M, J, g = (np.asarray(z, float) for z in (vfree, mobility, jacobian, gaps))
    n = len(g)
    if not 1 <= n <= 3:
        raise ValueError("mixed solve supports one to three contacts")
    B = np.linalg.inv(M)
    load = B @ v
    A, z = J @ M @ J.T, J @ v
    steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max() for k in range(n)])
    fs = max(np.linalg.norm(load), 1e-30)
    vs = max(np.linalg.norm(v), 1e-15)
    small = np.max(np.abs(g / dt))
    qs = small if 0 < small < .01 * vs else vs
    # 0=open, 1=stick, 2=slide. Most constrained modes first.
    modes = sorted(product(range(3), repeat=n), key=lambda m: (-sum(x == 1 for x in m), sum(x == 0 for x in m), m))
    evaluations = 0
    failures = []
    for mode in modes:
        active = [k for k in range(n) if mode[k]]
        fi = [3*k+j for k in active for j in range(3)]
        constraints, target = [], []
        for k in active:
            constraints.append(J[3*k]); target.append(-g[k] / dt / qs)
            if mode[k] == 1:
                constraints.extend(J[3*k+1:3*k+3]); target.extend([0., 0.])
        if constraints:
            C, d = np.asarray(constraints), np.asarray(target)
            u, s, vh = np.linalg.svd(C, full_matrices=True)
            rank = int(np.sum(s > s[0] * 1e-12))
            q0 = vh[:rank].T @ ((u[:, :rank].T @ d) / s[:rank])
            if np.max(np.abs(C @ q0 - d)) > 1e-11 * max(np.max(np.abs(d)), 1e-15):
                continue
            N = vh[rank:].T
        else:
            q0, N = np.zeros(6), np.eye(6)
        width = N.shape[1]
        JT = J.T[:, fi]
        f0 = np.linalg.lstsq(JT, B @ (q0 * qs) - load, rcond=1e-12)[0] / fs if fi else np.empty(0)

        def unpack(y):
            q = q0 + N @ y[:width]
            f = np.zeros(3*n); f[fi] = y[width:]
            return q, f

        def equations(y):
            q, f = unpack(y)
            residual = list((B @ (q * qs) - load) / fs - J.T @ f)
            vc = J @ q
            for k in active:
                if mode[k] == 2:
                    vt = vc[3*k+1:3*k+3]
                    direction = vt / max(np.linalg.norm(vt), 1e-30)
                    residual.extend(f[3*k+1:3*k+3] + friction * f[3*k] * direction)
            return np.asarray(residual)

        seeds = [np.zeros(width)]
        if width:
            seeds += [np.ones(width), -np.ones(width)]
        for seed in seeds:
            initial = np.r_[seed, f0]
            if len(initial):
                opt = least_squares(equations, initial, xtol=1e-14, ftol=1e-14, gtol=1e-14, max_nfev=200, x_scale="jac")
                y = opt.x; evaluations += opt.nfev
            else:
                y = initial
            q, f = unpack(y)
            try:
                answer = original._finish(v, M, J, f*fs, z, A, g, dt, friction, steps,
                    evaluations, "stage119_scaled_active_modes", {"contact_modes": list(mode), "velocity_scale_m_s": float(qs), "force_scale_N": float(fs)})
            except RuntimeError as exc:
                failures.append(str(exc))
                continue
            return answer
    raise RuntimeError("direct contact residual nonconvergence")
