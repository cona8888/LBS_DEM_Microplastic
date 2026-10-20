"""Exact prolate geometry with immutable inputs and cheaper swept evaluation.

This retains Stage37's closest-point equation, Brent root tolerance, periodic
image selection, four sweep subintervals and bounded-minimizer tolerance.  It
does not certify global minima of rotating sweeps: that existing limitation
still requires trajectory refinement checks.
"""
from pathlib import Path
import sys

import numpy as np
from scipy.optimize import brentq, minimize_scalar
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "stage37_staging") not in sys.path:
    sys.path.insert(0, str(ROOT / "stage37_staging"))
import transport_contact as reference


def _immutable(array):
    """A bytes-backed copy also prevents callers restoring writeability."""
    value = np.asarray(array, dtype=float)
    return np.frombuffer(value.tobytes(), dtype=float).reshape(value.shape)


class GrainGeometry(reference.GrainGeometry):
    """Fixed periodic grains; reuse exact contacts only at an identical pose.

    Every new skin still receives the reference cKDTree query.  Closest points
    for grain IDs shared by those queries are cached, using exact input bytes,
    never rounded coordinates.  Cache storage is limited to the latest pose.
    Returned normals and levers are copies, so callers cannot change the cache.
    """
    def __init__(self, centres, radii, length):
        c, r = reference.finite(centres), reference.finite(radii)
        length = float(length)
        if (r.ndim != 1 or c.shape != (len(r), 3) or len(r) == 0
                or not np.isfinite(length) or length <= 0 or np.any(r <= 0)):
            raise ValueError("invalid grains")
        self._c, self._r, self._L = _immutable(c), _immutable(r), length
        self._tree = cKDTree(_immutable(np.mod(self._c, self._L)),
                             boxsize=self._L, copy_data=False)
        self._max_radius = self._r.max()
        self._pose = None
        self._contacts = {}
        self._stats = {"queries": 0, "closest_point_evaluations": 0,
                       "reused_closest_points": 0, "pose_changes": 0}

    @property
    def c(self):
        return self._c

    @property
    def r(self):
        return self._r

    @property
    def L(self):
        return self._L

    @property
    def tree(self):
        return self._tree

    @property
    def stats(self):
        return dict(self._stats)

    @classmethod
    def from_geometry(cls, geometry):
        return cls(geometry.c, geometry.r, geometry.L)

    def contacts(self, x, p, a, b, skin=0.0):
        x, p = reference.finite(x), reference.finite(p)
        if x.shape != (3,) or p.shape != (3,):
            raise ValueError("three-dimensional position and orientation required")
        if not np.isfinite([a, b, skin]).all() or not a >= b > 0:
            raise ValueError("finite prolate axes and skin required")
        # Compare the unnormalised orientation too; no numerical coalescing.
        key = (x.tobytes(), p.tobytes(), float(a), float(b))
        if key != self._pose:
            self._pose, self._contacts = key, {}
            self._stats["pose_changes"] += 1
        ids = self._tree.query_ball_point(np.mod(x, self._L),
                                          self._max_radius + a + skin)
        self._stats["queries"] += 1
        result = []
        for k in sorted(ids):
            if k not in self._contacts:
                d = self._c[k] - x
                d -= self._L * np.round(d / self._L)
                gap, normal, lever = reference.ellipsoid_grain_contact(
                    x, p, a, b, x+d, self._r[k])
                self._contacts[k] = (gap, normal, lever)
                self._stats["closest_point_evaluations"] += 1
            else:
                self._stats["reused_closest_points"] += 1
            gap, normal, lever = self._contacts[k]
            if gap <= skin:
                result.append((k, gap, normal.copy(), lever.copy()))
        return result


def _gap_at_pose(x, p, a, b, c, radius):
    """Reference external-centre solve, omitting the unused output normal.

    The operation order and p normalization match ellipsoid_grain_contact.
    Fixed input validity is checked by swept_gap before this private kernel.
    """
    p = reference.unit(p)
    d = (c-x)/a
    ratio = b/a
    parallel = np.dot(d, p)*p
    transverse = d-parallel
    val = np.dot(parallel, parallel) + np.dot(transverse, transverse)/(ratio*ratio)
    if val <= 1:
        raise ValueError("grain centre inside ellipsoid")
    if abs(a-b) < 1e-13*a:
        lever = a*reference.unit(d)
    else:
        d2p = np.dot(parallel, parallel)
        d2t = np.dot(transverse, transverse)

        def fun(t):
            return d2p/(1+t)**2 + ratio**2*d2t/(ratio**2+t)**2 - 1

        hi = max(1.0, np.linalg.norm(d))
        while fun(hi) > 0:
            hi *= 2
        t = brentq(fun, 0.0, hi, xtol=1e-14)
        lever = a*(parallel/(1+t) + ratio**2*transverse/(ratio**2+t))
    distance = np.linalg.norm(x+lever-c)
    # The reference rejects an undefined normal when roundoff puts the grain
    # centre exactly on the computed surface, even though only gap is needed.
    if distance == 0:
        raise ValueError("zero direction")
    gap = float(distance-radius)
    if not np.isfinite(gap):
        raise FloatingPointError("nonfinite state")
    return gap


class _FixedMotion:
    """Hoist identical constant-velocity Rodrigues factors out of minimizers."""
    def __init__(self, x, p, v, a):
        self.x, self.p, self.v = (reference.finite(x), reference.unit(p),
                                 reference.finite(v))
        self.a = a
        omega = self.v[3:]/a
        self.angular_speed = np.linalg.norm(omega)
        if self.angular_speed > 0:
            self.axis = reference.unit(omega)
            self.cross = np.cross(self.axis, self.p)
            self.parallel = self.axis*(self.axis@self.p)

    def at(self, time):
        x = self.x + time*self.v[:3]
        theta = self.angular_speed*time
        p = self.p
        if theta > 0:
            p = (p*np.cos(theta) + self.cross*np.sin(theta)
                 + self.parallel*(1-np.cos(theta)))
        return x, reference.unit(p)


def swept_gap(geometry, x, p, v, a, b, dt):
    """Drop-in Stage37 sweep with unchanged numerical search and geometry."""
    if not isinstance(geometry, reference.GrainGeometry):
        return geometry.swept_gap(x, p, v, a, b, dt)
    if not np.isfinite([a, b, dt]).all() or not a >= b > 0 or dt < 0:
        raise ValueError("finite prolate axes and nonnegative timestep required")
    x, p, v = reference.finite(x), reference.finite(p), reference.finite(v)
    travel = np.linalg.norm(v[:3])*dt
    ids = geometry.tree.query_ball_point(np.mod(x, geometry.L),
                                         geometry.r.max()+a+travel)
    minimum = np.inf
    spherical = abs(a-b) < 1e-13*a
    motion = None if spherical else _FixedMotion(x, p, v, a)
    intervals = np.linspace(0, dt, 5)
    for k in ids:
        d = geometry.c[k]-x
        d -= geometry.L*np.round(d/geometry.L)
        c = x+d
        if spherical:
            disp = v[:3]*dt
            den = disp@disp
            time = np.clip(d@disp/den, 0, 1) if den > 0 else 0
            gap = np.linalg.norm(x+time*disp-c)-a-geometry.r[k]
        else:
            def fun(time):
                xx, pp = motion.at(time)
                return _gap_at_pose(xx, pp, a, b, c, geometry.r[k])

            gap = min(fun(0), fun(dt))
            for lo, hi in zip(intervals[:-1], intervals[1:]):
                opt = minimize_scalar(fun, bounds=(lo, hi), method="bounded",
                                      options={"xatol": max(dt*1e-8, 1e-14)})
                if not opt.success:
                    raise RuntimeError("swept-gap minimization failed")
                gap = min(gap, opt.fun)
        minimum = min(minimum, gap)
    return float(minimum)
