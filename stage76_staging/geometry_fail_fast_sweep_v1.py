"""Exact Stage41 swept gap with a proven-violation early return.

For an accepted step, every grain and four minimizer intervals are evaluated in
the original order, producing the original gap. For a rejected step, any exact
endpoint/minimizer value below the unchanged -1e-5*b clearance threshold proves
that the global minimum is also below it; later work cannot change rejection.
The rejected gap is not recorded by Stage68. This module is single-threaded.
"""
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage41_staging"))
import geometry_exact_v1 as original

_stats = {"calls": 0, "endpoint_early_rejects": 0,
          "interior_early_rejects": 0, "full_evaluations": 0}


def stats():
    return dict(_stats)


def swept_gap(geometry, x, p, v, a, b, dt):
    _stats["calls"] += 1
    if not isinstance(geometry, original.reference.GrainGeometry):
        _stats["full_evaluations"] += 1
        return geometry.swept_gap(x, p, v, a, b, dt)
    if not np.isfinite([a, b, dt]).all() or not a >= b > 0 or dt < 0:
        raise ValueError("finite prolate axes and nonnegative timestep required")
    x, p, v = (original.reference.finite(x), original.reference.finite(p),
               original.reference.finite(v))
    travel = np.linalg.norm(v[:3]) * dt
    ids = geometry.tree.query_ball_point(np.mod(x, geometry.L),
                                         geometry.r.max() + a + travel)
    minimum = np.inf
    spherical = abs(a-b) < 1e-13*a
    motion = None if spherical else original._FixedMotion(x, p, v, a)
    intervals = np.linspace(0, dt, 5)
    threshold = -1e-5*b
    for k in ids:
        d = geometry.c[k] - x
        d -= geometry.L * np.round(d / geometry.L)
        c = x + d
        if spherical:
            disp = v[:3] * dt
            den = disp @ disp
            time = np.clip(d @ disp / den, 0, 1) if den > 0 else 0
            gap = np.linalg.norm(x + time*disp - c) - a - geometry.r[k]
        else:
            def fun(time):
                xx, pp = motion.at(time)
                return original._gap_at_pose(xx, pp, a, b, c, geometry.r[k])

            gap = min(fun(0), fun(dt))
            if gap < threshold:
                _stats["endpoint_early_rejects"] += 1
                return float(gap)
            for lo, hi in zip(intervals[:-1], intervals[1:]):
                opt = minimize_scalar(fun, bounds=(lo, hi), method="bounded",
                                      options={"xatol": max(dt*1e-8, 1e-14)})
                if not opt.success:
                    raise RuntimeError("swept-gap minimization failed")
                gap = min(gap, opt.fun)
                if gap < threshold:
                    _stats["interior_early_rejects"] += 1
                    return float(gap)
        minimum = min(minimum, gap)
    _stats["full_evaluations"] += 1
    return float(minimum)
