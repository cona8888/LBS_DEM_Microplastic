"""SI force/couple transfer for one body's prescribed attachment map.

No fluid forces are generated here. All positions are unwrapped world-frame m.
Forces are fluid-on-body N, intrinsic couples Nm. Nodal rotational DOFs are
required. Ownership and attachment weights must come from a separate adapter.
"""
from dataclasses import dataclass
from math import fsum
import numpy as np


def array(value, shape, name):
    raw = np.asarray(value)
    if raw.dtype.kind not in 'fiu' or raw.shape != shape:
        raise ValueError(name + ': expected real numeric array of shape ' + str(shape))
    result = np.array(raw, dtype=np.float64, copy=True)
    if not np.isfinite(result).all():
        raise ValueError(name + ': nonfinite')
    return result


def triples(value, name):
    raw = np.asarray(value)
    if raw.ndim != 2 or raw.shape[1] != 3 or len(raw) == 0:
        raise ValueError(name + ': nonempty n by 3 required')
    return array(raw, raw.shape, name)


def finite_result(value):
    if not np.isfinite(value).all():
        raise ValueError('arithmetic overflow')
    return value


def vector_sum(values):
    return finite_result(np.array([fsum(values[:, j]) for j in range(3)]))


def wrench(positions_m, forces_N, couples_Nm, origin_m):
    x = triples(positions_m, 'positions_m')
    f = array(forces_N, x.shape, 'forces_N')
    c = array(couples_Nm, x.shape, 'couples_Nm')
    origin = array(origin_m, (3,), 'origin_m')
    with np.errstate(over='raise', invalid='raise'):
        try:
            return vector_sum(f), vector_sum(np.cross(x-origin, f)+c)
        except (FloatingPointError, OverflowError) as error:
            raise ValueError('wrench arithmetic overflow') from error


@dataclass(frozen=True)
class Transfer:
    forces_N: np.ndarray
    couples_Nm: np.ndarray


class AttachmentMap:
    """A fixed one-body map; caller supplies two host nodes and t in [0,1].

    At each node j: fj += wj*f; cj += wj*(c+(xs-xj) cross f).
    Its adjoint samples rigid-offset velocity from both nodal translations and
    rotations. This is a defined discrete interface, not a verified beam element.
    """
    def __init__(self, nodes_m, samples_m, host_pairs, t, *, accepts_nodal_couples):
        if accepts_nodal_couples is not True:
            raise ValueError('explicit nodal-couple support required')
        self.nodes_m = triples(nodes_m, 'nodes_m')
        self.samples_m = triples(samples_m, 'samples_m')
        pairs = np.asarray(host_pairs)
        ns = len(self.samples_m)
        if pairs.shape != (ns, 2) or pairs.dtype.kind not in 'iu':
            raise ValueError('integer host_pairs n by 2 required')
        if np.any(pairs < 0) or np.any(pairs >= len(self.nodes_m)) or np.any(pairs[:, 0] == pairs[:, 1]):
            raise ValueError('invalid node ownership indices')
        self.host_pairs = pairs.astype(np.int64, copy=True)
        if np.any(np.all(self.nodes_m[pairs[:, 0]] == self.nodes_m[pairs[:, 1]], axis=1)):
            raise ValueError('zero-length host segment')
        alpha = array(t, (ns,), 't')
        if np.any(alpha < 0) or np.any(alpha > 1):
            raise ValueError('attachment outside host segment')
        self.weights = np.column_stack((1-alpha, alpha))
        for value in (self.nodes_m, self.samples_m, self.host_pairs, self.weights):
            value.flags.writeable = False

    def transfer(self, forces_N, couples_Nm):
        f = array(forces_N, self.samples_m.shape, 'forces_N')
        c = array(couples_Nm, self.samples_m.shape, 'couples_Nm')
        nf, nc = np.zeros_like(self.nodes_m), np.zeros_like(self.nodes_m)
        with np.errstate(over='raise', invalid='raise'):
            try:
                for k in range(2):
                    idx, weight = self.host_pairs[:, k], self.weights[:, k, None]
                    np.add.at(nf, idx, weight*f)
                    np.add.at(nc, idx, weight*(c+np.cross(self.samples_m-self.nodes_m[idx], f)))
                finite_result(nf)
                finite_result(nc)
            except FloatingPointError as error:
                raise ValueError('transfer arithmetic overflow') from error
        return Transfer(nf, nc)

    def sample_velocities(self, node_velocities_m_s, node_angular_velocities_rad_s):
        v = array(node_velocities_m_s, self.nodes_m.shape, 'node_velocities_m_s')
        omega = array(node_angular_velocities_rad_s, self.nodes_m.shape, 'node_angular_velocities_rad_s')
        sv, sw = np.zeros_like(self.samples_m), np.zeros_like(self.samples_m)
        with np.errstate(over='raise', invalid='raise'):
            try:
                for k in range(2):
                    idx, weight = self.host_pairs[:, k], self.weights[:, k, None]
                    sv += weight*(v[idx]+np.cross(omega[idx], self.samples_m-self.nodes_m[idx]))
                    sw += weight*omega[idx]
                return finite_result(sv), finite_result(sw)
            except FloatingPointError as error:
                raise ValueError('velocity arithmetic overflow') from error


def power_W(forces_N, couples_Nm, velocities_m_s, angular_velocities_rad_s):
    f = triples(forces_N, 'forces_N')
    c = array(couples_Nm, f.shape, 'couples_Nm')
    v = array(velocities_m_s, f.shape, 'velocities_m_s')
    omega = array(angular_velocities_rad_s, f.shape, 'angular_velocities_rad_s')
    with np.errstate(over='raise', invalid='raise'):
        try:
            return float(finite_result(np.asarray(fsum((f*v+c*omega).ravel()))))
        except (FloatingPointError, OverflowError) as error:
            raise ValueError('power arithmetic overflow') from error
