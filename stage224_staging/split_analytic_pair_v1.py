"""Unqualified isolated prototype: lazy original-law residual/Jacobian pair.

The intended domain is the frozen dense nine-variable float64 contact call.
This module does not install a scope, patch a binding, or integrate a trajectory.
The existing Stage196 arithmetic, NumPy reductions and sliding-matrix product
order are retained. Separate callbacks avoid derivative work for residual-only
trial points. Qualification against the frozen implementation is still required.

All memo state belongs to one constructed contact system. Input keys include
shape, dtype and complete bytes, including signed zero and NaN payloads. Stored
input and output arrays are private copies; returned arrays cannot mutate them.
No physical pose, force, mode, material parameter or acceptance gate is reused
or changed. There is no added finite-value clipping or validation policy.
"""
import compiled_analytic_pair_v3 as previous

np = previous.np
numba = previous.numba


@numba.njit(cache=True, fastmath=False, parallel=False)
def residual_only(y, vc, gap, norms, H, eye, steps, scales, mu, dr):
    """Original assemble residual expressions, without derivative allocation."""
    count = len(gap)
    size = len(y)
    result = np.empty(size)
    for k in range(count):
        i = 3*k
        n = y[i]
        vn = vc[i]+gap[k]
        norm = norms[k]
        if norm:
            result[i] = norm-n-vn
        else:
            result[i] = 0.
        r = mu*y[i]*steps[k]/scales[i]
        x0 = y[i+1]-vc[i+1]
        x1 = y[i+2]-vc[i+2]
        speed = np.sqrt(x0*x0+x1*x1)
        if r <= 0:
            for t in range(2):
                result[i+1+t] = y[i+1+t]
        elif speed <= r:
            for t in range(2):
                result[i+1+t] = vc[i+1+t]
        else:
            direction = np.empty(2)
            for t in range(2):
                direction[t] = (y[i+1+t]-vc[i+1+t])/speed
            for t in range(2):
                result[i+1+t] = y[i+1+t]-r*direction[t]
    return result


@numba.njit(cache=True, fastmath=False, parallel=False)
def jacobian_only(y, vc, gap, norms, H, eye, steps, scales, mu, dr):
    """Original assemble derivative expressions and sliding projection order."""
    count = len(gap)
    size = len(y)
    jac = np.empty_like(H)
    projection = np.zeros((count, 2, 2))
    sliding = np.zeros(count, np.bool_)
    for k in range(count):
        i = 3*k
        n = y[i]
        vn = vc[i]+gap[k]
        norm = norms[k]
        if norm:
            for j in range(size):
                jac[i, j] = (n/norm-1)*eye[i, j]+(vn/norm-1)*H[i, j]
        else:
            for j in range(size):
                jac[i, j] = -eye[i, j]-H[i, j]
        r = mu*y[i]*steps[k]/scales[i]
        x0 = y[i+1]-vc[i+1]
        x1 = y[i+2]-vc[i+2]
        speed = np.sqrt(x0*x0+x1*x1)
        if r <= 0:
            for t in range(2):
                for j in range(size):
                    jac[i+1+t, j] = eye[i+1+t, j]
        elif speed <= r:
            for t in range(2):
                for j in range(size):
                    jac[i+1+t, j] = H[i+1+t, j]
        else:
            sliding[k] = True
            direction = np.empty(2)
            for t in range(2):
                direction[t] = (y[i+1+t]-vc[i+1+t])/speed
            for t in range(2):
                for j in range(size):
                    jac[i+1+t, j] = eye[i+1+t, j]-direction[t]*dr[k, j]
                for u in range(2):
                    projection[k, t, u] = (r/speed)*((1. if t == u else 0.)-direction[t]*direction[u])
    return jac, projection, sliding


def optimized_system(v, M, J, g, dt, mu):
    """Construct a private lazy pair with the unchanged Stage196 constants.

    ``both(y)`` retains the ordinary tuple interface. ``both.residual(y)`` and
    ``both.derivative(y)`` request only their respective component. Counters
    describe actual computations and cache hits; they are diagnostic metadata.
    """
    A = J@M@J.T
    z = J@v
    vs = max(np.linalg.norm(v), 1e-15)
    steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max() for k in range(len(g))])
    scales = np.repeat(steps, 3)
    scales[::3] = A.diagonal()[::3]
    H = A/scales[None, :]
    zv = z/vs
    gap = g/dt/vs
    eye = np.eye(len(z))
    constants = [(3*k, eye[3*k+1:3*k+3]-H[3*k+1:3*k+3]) for k in range(len(g))]
    dr = np.array([mu*steps[k]/scales[3*k]*eye[3*k] for k in range(len(g))])

    key = None
    input_snapshot = None
    cached_vc = None
    cached_norms = None
    cached_residual = None
    cached_jacobian = None
    counters = dict(state_computations=0, residual_computations=0,
                    jacobian_computations=0, input_cache_hits=0,
                    residual_cache_hits=0, jacobian_cache_hits=0)

    def state_for(y):
        nonlocal key, input_snapshot, cached_vc, cached_norms
        nonlocal cached_residual, cached_jacobian
        a = np.asarray(y)
        new_key = (a.shape, a.dtype.str, a.tobytes())
        if new_key == key:
            counters['input_cache_hits'] += 1
            return
        # Retain the original NumPy operations on the supplied input. The
        # independent snapshot only serves the subsequent scalar kernels.
        vc = zv+H@y
        norms = np.hypot(y[::3], vc[::3]+gap)
        input_snapshot = a.copy()
        cached_vc = vc
        cached_norms = norms
        cached_residual = None
        cached_jacobian = None
        key = new_key
        counters['state_computations'] += 1

    def residual(y):
        nonlocal cached_residual
        state_for(y)
        if cached_residual is None:
            cached_residual = residual_only(input_snapshot, cached_vc, gap,
                                            cached_norms, H, eye, steps,
                                            scales, mu, dr)
            counters['residual_computations'] += 1
        else:
            counters['residual_cache_hits'] += 1
        return cached_residual.copy()

    def derivative(y):
        nonlocal cached_jacobian
        state_for(y)
        if cached_jacobian is None:
            jac, projection, sliding = jacobian_only(input_snapshot, cached_vc,
                                                      gap, cached_norms, H,
                                                      eye, steps, scales, mu, dr)
            for k, (i, dx) in enumerate(constants):
                if sliding[k]:
                    jac[i+1:i+3] -= projection[k]@dx
            cached_jacobian = jac
            counters['jacobian_computations'] += 1
        else:
            counters['jacobian_cache_hits'] += 1
        return cached_jacobian.copy()

    def both(y):
        return residual(y), derivative(y)

    both.residual = residual
    both.derivative = derivative
    both.counters = counters
    return both, A, z, steps, scales, vs
