"""Static D3Q19 halfway bounce-back link loads, triply periodic, CPU only."""
from math import fsum
import numpy as np

C = np.array([[0,0,0],[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1],
              [1,1,0],[-1,-1,0],[1,-1,0],[-1,1,0],[1,0,1],[-1,0,-1],
              [1,0,-1],[-1,0,1],[0,1,1],[0,-1,-1],[0,1,-1],[0,-1,1]], dtype=np.int64)
OPP = np.array([0,2,1,4,3,6,5,8,7,10,9,12,11,14,13,16,15,18,17])
W = np.array([1/3]+[1/18]*6+[1/36]*12, dtype=np.float32)
for _a in (C, OPP, W):
    _a.flags.writeable = False


def sum3(a):
    return np.array([fsum(a[:, j]) for j in range(3)])


def extract(g, phase, owners, anchors, *, boundary='triply_periodic'):
    if boundary != 'triply_periodic':
        raise ValueError('only static triply periodic boundaries supported')
    phase, owners, g = np.asarray(phase), np.asarray(owners), np.asarray(g)
    if phase.dtype != np.uint8 or phase.ndim != 3 or min(phase.shape) < 3 or phase.size > 262144:
        raise ValueError('invalid phase dimensions/dtype/resource bound')
    if not np.isin(phase, [0, 1, 2]).all():
        raise ValueError('invalid phase or overlap')
    if owners.shape != phase.shape or owners.dtype.kind not in 'iu' or np.any(owners < 0):
        raise ValueError('invalid owner map')
    solid = phase != 0
    if not solid.any() or solid.all() or not np.array_equal(owners > 0, solid):
        raise ValueError('owner/phase mismatch or absent fluid/solid')
    ids = [int(k) for k in np.unique(owners[solid])]
    if not isinstance(anchors, dict) or any(type(k) is not int or k <= 0 for k in anchors) or set(anchors) != set(ids):
        raise ValueError('body IDs and anchors differ')
    anchor_arrays = {}
    for key, value in anchors.items():
        a = np.asarray(value)
        if a.dtype.kind not in 'fiu' or a.shape != (3,) or not np.isfinite(a).all():
            raise ValueError('invalid anchor')
        anchor_arrays[key] = a.astype(float)
    if g.dtype != np.float32 or g.shape != (19, *phase.shape) or not np.isfinite(g).all():
        raise ValueError('finite shifted FP32 state of shape [19,z,y,x] required')
    if np.any(g[:, solid] != 0):
        raise ValueError('solid shifted state must be zero')
    fluid = ~solid
    for q in range(19):
        if np.any(g[q, fluid].astype(float)+float(W[q]) <= 0):
            raise ValueError('nonpositive reconstructed population')
    nz, ny, nx = phase.shape
    lengths = np.array([nx, ny, nz], dtype=float)
    rows = {name: [] for name in ['q', 'destination', 'source', 'owner', 'midpoint', 'shifted_force', 'baseline_force']}
    count = 0
    for q in range(1, 19):
        cx, cy, cz = C[q]
        selected = fluid & np.roll(solid, (cz, cy, cx), axis=(0,1,2))
        z, y, x = np.nonzero(selected)
        if not len(x):
            continue
        count += len(x)
        if count > 200000:
            raise ValueError('link resource bound exceeded')
        source = np.column_stack(((x-cx)%nx, (y-cy)%ny, (z-cz)%nz))
        identity = owners[source[:,2], source[:,1], source[:,0]]
        midpoint = np.column_stack((x, y, z))+.5-.5*C[q]
        for key in np.unique(identity):
            which = identity == key
            delta = (midpoint[which]-anchor_arrays[int(key)]+lengths/2)%lengths-lengths/2
            if np.any(np.abs(delta) == lengths/2):
                raise ValueError('ambiguous half-box body image')
            midpoint[which] = anchor_arrays[int(key)]+delta
        shifted = -2*g[OPP[q], z, y, x].astype(float)[:,None]*C[q]
        baseline = np.broadcast_to(-2*float(W[OPP[q]])*C[q], shifted.shape).copy()
        values = [np.full(len(x), q), np.column_stack((x,y,z)), source, identity, midpoint, shifted, baseline]
        for name, value in zip(rows, values):
            rows[name].append(value)
    if not count:
        raise ValueError('no fluid-solid links')
    links = {name: np.concatenate(value) for name, value in rows.items()}
    bodies = {}
    for key in ids:
        which = links['owner'] == key
        arm = links['midpoint'][which]-anchor_arrays[key]
        sf, bf = links['shifted_force'][which], links['baseline_force'][which]
        fs, fb = sum3(sf), sum3(bf)
        ts, tb = sum3(np.cross(arm,sf)), sum3(np.cross(arm,bf))
        bodies[key] = {'link_count': int(np.count_nonzero(which)), 'anchor_lu': anchor_arrays[key],
                       'shifted_force_lu': fs, 'baseline_force_lu': fb, 'force_lu': fs+fb,
                       'shifted_torque_lu': ts, 'baseline_torque_lu': tb, 'torque_lu': ts+tb}
    return links, bodies
