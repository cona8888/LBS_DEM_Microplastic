"""Persistent volume quadrature for prescribed rigid capsule-union geometry.

Not a dynamics, fluid, or deforming-fibre model. Units are SI, except CPD.
"""
from dataclasses import dataclass
import numpy as np


def scalar(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.number)):
        raise ValueError(name)
    value = float(value)
    if not np.isfinite(value):
        raise ValueError(name)
    return value


def points(value, name, minimum=1):
    a = np.array(value, dtype=float, copy=True)
    if a.ndim != 2 or a.shape[1] != 3 or len(a) < minimum or not np.isfinite(a).all():
        raise ValueError(name)
    return a


def rigid(value, rotation, translation):
    p = points(value, 'points')
    r = np.asarray(rotation, dtype=float)
    t = np.asarray(translation, dtype=float)
    if r.shape != (3, 3) or t.shape != (3,) or not np.isfinite(r).all() or not np.isfinite(t).all():
        raise ValueError('nonfinite or malformed rigid transform')
    if not np.allclose(r.T @ r, np.eye(3), atol=1e-12, rtol=0) or abs(np.linalg.det(r)-1) > 1e-12:
        raise ValueError('rotation must be proper orthogonal')
    out = p @ r.T + t
    if not np.isfinite(out).all():
        raise ValueError('transform overflow')
    return out


@dataclass(frozen=True)
class Cloud:
    nodes: np.ndarray
    radius: float
    samples: np.ndarray
    spacing: float
    candidate_count: int

    @property
    def raw_volume(self):
        return len(self.samples) * self.spacing ** 3

    def categories(self, rotation, translation, inlet, outlet):
        a, b = scalar(inlet, 'inlet'), scalar(outlet, 'outlet')
        if a >= b:
            raise ValueError('inlet must precede outlet')
        x = rigid(self.samples, rotation, translation)[:, 0]
        return np.where(x < a, -1, np.where(x > b, 1, 0)).astype(np.int8)

    def full_exit(self, rotation, translation, outlet):
        x = rigid(self.nodes, rotation, translation)[:, 0]
        return bool(np.min(x) - self.radius >= scalar(outlet, 'outlet'))


def make_cloud(nodes, radius, cpd, max_candidates=4_000_000):
    n = points(nodes, 'centreline', minimum=2)
    radius = scalar(radius, 'radius')
    if radius <= 0 or isinstance(cpd, bool) or not isinstance(cpd, int) or cpd < 2:
        raise ValueError('positive radius and integer CPD >= 2 required')
    if isinstance(max_candidates, bool) or not isinstance(max_candidates, int) or max_candidates < 1:
        raise ValueError('invalid resource bound')
    segments = np.diff(n, axis=0)
    length2 = np.einsum('ij,ij->i', segments, segments)
    if not np.isfinite(length2).all() or np.any(length2 <= 0):
        raise ValueError('zero-length or overflowing segment')
    h = 2 * radius / cpd
    lo, hi = n.min(axis=0)-radius, n.max(axis=0)+radius
    dims_float = np.ceil((hi-lo)/h)
    if not np.isfinite(dims_float).all() or np.any(dims_float > max_candidates):
        raise ValueError('grid exceeds resource bound')
    dims = tuple(int(v) for v in dims_float)
    count = dims[0]*dims[1]*dims[2]
    if count > max_candidates:
        raise ValueError('grid exceeds resource bound')
    selected = []
    for start in range(0, count, 32768):
        idx = np.arange(start, min(start+32768, count))
        ijk = np.column_stack(np.unravel_index(idx, dims))
        p = lo + (ijk+0.5)*h
        mask = np.zeros(len(p), dtype=bool)
        for a, d, d2 in zip(n[:-1], segments, length2):
            delta = p-a
            fraction = np.clip(np.einsum('ij,j->i', delta, d)/d2, 0, 1)
            offset = delta-fraction[:, None]*d
            mask |= np.einsum('ij,ij->i', offset, offset) <= radius*radius
        selected.append(p[mask])
    samples = np.concatenate(selected)
    if not len(samples):
        raise ValueError('empty volume cloud')
    n.flags.writeable = False
    samples.flags.writeable = False
    return Cloud(n, radius, samples, h, count)


def fractions(categories):
    c = np.asarray(categories)
    if c.ndim != 1 or not len(c) or not np.isin(c, [-1, 0, 1]).all():
        raise ValueError('invalid categories')
    return {name: float(np.count_nonzero(c == key)/len(c))
            for name, key in [('upstream', -1), ('inside', 0), ('downstream', 1)]}


def crossing(old, new, mass):
    """Inputs MUST have the same persistent sample order; endpoint counts only."""
    old, new = np.asarray(old), np.asarray(new)
    previous, current = fractions(old), fractions(new)
    if old.shape != new.shape:
        raise ValueError('material sample count changed')
    mass = scalar(mass, 'mass')
    if mass <= 0:
        raise ValueError('mass must be positive')
    unit = mass/len(old)
    out = {'mass_kg': mass, 'fractions': current}
    for name, key in [('outlet', 1), ('inlet', -1)]:
        out[name+'_outward_kg'] = float(np.count_nonzero((old != key) & (new == key))*unit)
        out[name+'_return_kg'] = float(np.count_nonzero((old == key) & (new != key))*unit)
    out['relative_inventory_residual'] = sum(current.values())-1
    for name, side in [('outlet', 'downstream'), ('inlet', 'upstream')]:
        out[name+'_relative_crossing_residual'] = (
            out[name+'_outward_kg']-out[name+'_return_kg'])/mass-(current[side]-previous[side])
    if max(abs(out[k]) for k in out if 'residual' in k) > 1e-12:
        raise ValueError('accounting closure failed')
    return out
