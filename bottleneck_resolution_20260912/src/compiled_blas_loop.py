"""Compiled sweep dispatch into the same BLAS DLL used by installed NumPy.

Qualification target: NumPy 2.3.1 Windows ILP64 OpenBLAS 0.3.29. The matrix-vector
and dot operations mirror NumPy's matmul.c.src and linalg/_linalg.py dispatch.
No SciPy BLAS, fastmath, parallelism, force warm start, or tolerance change.
This module intentionally does not cache JIT code containing process pointers.
"""
import ctypes
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bottleneck_resolution_20260912/deps"))
import numpy as np
from numba import njit
sys.path.insert(0, str(ROOT / "stage50_staging"))
import inertial_contact_seeded_lm_v1 as s50

_stats = {"calls": 0, "successes": 0, "failures": 0, "iterations": 0,
          "loop_seconds": 0., "finish_seconds": 0.}


def stats():
    return dict(_stats)

if np.__version__ != "2.3.1" or sys.platform != "win32":
    raise RuntimeError("NumPy-BLAS contact loop requires qualification on this platform/version")
_libraries = list((Path(np.__file__).resolve().parent.parent / "numpy.libs").glob("*openblas*.dll"))
if len(_libraries) != 1:
    raise RuntimeError("Cannot uniquely identify installed NumPy OpenBLAS library")
BLAS_PATH = _libraries[0]
_library = ctypes.CDLL(str(BLAS_PATH))
_double_p = ctypes.POINTER(ctypes.c_double)
_int64 = ctypes.c_longlong
_ddot = _library.scipy_cblas_ddot64_
_ddot.argtypes = [_int64, _double_p, _int64, _double_p, _int64]
_ddot.restype = ctypes.c_double
_dgemv = _library.scipy_cblas_dgemv64_
_dgemv.argtypes = [ctypes.c_int, ctypes.c_int, _int64, _int64, ctypes.c_double,
                  _double_p, _int64, _double_p, _int64, ctypes.c_double,
                  _double_p, _int64]
_dgemv.restype = None
_config = _library.scipy_openblas_get_config64_
_config.argtypes = []
_config.restype = ctypes.c_char_p
BLAS_CONFIGURATION = _config().decode()
if "USE64BITINT" not in BLAS_CONFIGURATION or "OpenBLAS 0.3.29" not in BLAS_CONFIGURATION:
    raise RuntimeError("NumPy OpenBLAS ABI/version has not been qualified")


@njit(cache=False, fastmath=False, parallel=False, inline="always")
def _norm2(trial):
    return np.sqrt(_ddot(2, trial.ctypes, 1, trial.ctypes, 1))


@njit(cache=False, fastmath=False, parallel=False)
def _sweep(A, z, gaps, dt, mu, steps, force, omega, tangent, trial, velocity):
    n = len(z)
    for k in range(len(gaps)):
        i = 3*k
        old = force[i]
        vn = z[i]+_ddot(n, A[i].ctypes, 1, force.ctypes, 1)+gaps[k]/dt
        candidate = max(0., old-vn/A[i, i])
        if omega == 1.:
            force[i] = candidate
        else:
            force[i] = max(0., old+omega*(candidate-old))
        old_x = force[i+1]
        old_y = force[i+2]
        # NumPy DOUBLE_gemv: CblasColMajor, CblasTrans, N, M, lda=N.
        _dgemv(102, 112, n, 2, 1., A[i+1:].ctypes, n, force.ctypes, 1,
               0., tangent.ctypes, 1)
        vx = z[i+1]+tangent[0]
        vy = z[i+2]+tangent[1]
        trial[0] = old_x-vx/steps[k]
        trial[1] = old_y-vy/steps[k]
        limit = mu*force[i]
        factor = min(1., limit/max(_norm2(trial), 1e-300))
        candidate_x = trial[0]*factor
        candidate_y = trial[1]*factor
        if omega == 1.:
            force[i+1] = candidate_x
            force[i+2] = candidate_y
        else:
            trial[0] = old_x+omega*(candidate_x-old_x)
            trial[1] = old_y+omega*(candidate_y-old_y)
            factor = min(1., limit/max(_norm2(trial), 1e-300))
            force[i+1] = trial[0]*factor
            force[i+2] = trial[1]*factor
    _dgemv(102, 112, n, n, 1., A.ctypes, n, force.ctypes, 1,
           0., velocity.ctypes, 1)
    for i in range(n):
        velocity[i] = z[i]+velocity[i]
    value = 0.
    for k in range(len(gaps)):
        i = 3*k
        value = max(value, abs(min(A[i, i]*force[i], velocity[i]+gaps[k]/dt)))
        trial[0] = force[i+1]-velocity[i+1]/steps[k]
        trial[1] = force[i+2]-velocity[i+2]/steps[k]
        factor = min(1., mu*force[i]/max(_norm2(trial), 1e-300))
        trial[0] = force[i+1]-trial[0]*factor
        trial[1] = force[i+2]-trial[1]*factor
        value = max(value, _norm2(trial)*steps[k])
    return value


@njit(cache=False, fastmath=False, parallel=False)
def cold_loop(A, z, gaps, dt, mu, steps, scale, tol, maxiter, omega=1.7):
    """Internal core: return cold (force, sweeps, residual_converged).

    Caller must validate finite float64 C-contiguous A/z/gaps/steps; A is square
    len(z), len(z)=3*len(gaps), steps has len(gaps), diagonal/scales/dt positive,
    controls finite and maxiter positive integer. Original final gates required.
    Public solve_prepared and the explicit Stage53 wrapper enforce these bounds.
    """
    force = np.zeros(len(z))
    tangent = np.empty(2)
    trial = np.empty(2)
    velocity = np.empty(len(z))
    for iteration in range(maxiter):
        residual = _sweep(A, z, gaps, dt, mu, steps, force, omega,
                          tangent, trial, velocity)
        if residual/scale <= tol:
            return force, iteration+1, True
    return force, maxiter, False


@njit(cache=False, fastmath=False, parallel=False)
def trace_loop(A, z, gaps, dt, mu, steps, count, omega):
    """Verification-only force/residual trace after every cold sweep."""
    force = np.zeros(len(z))
    tangent = np.empty(2)
    trial = np.empty(2)
    velocity = np.empty(len(z))
    forces = np.empty((count, len(z)))
    residuals = np.empty(count)
    for iteration in range(count):
        residuals[iteration] = _sweep(A, z, gaps, dt, mu, steps, force, omega,
                                    tangent, trial, velocity)
        forces[iteration, :] = force
    return forces, residuals


def warmup():
    start = time.perf_counter()
    cold_loop(np.eye(3), np.array([-1., .2, -.1]), np.zeros(1), .01, .3,
              np.ones(1), 1., 1e-10, 25000, 1.7)
    return time.perf_counter()-start


def solve_prepared(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter):
    """Stage63 SOR update with original Stage50 final physical gates."""
    _stats["calls"] += 1
    try:
        # Preserve matrix/vector input strides for original NumPy assembly.
        # Only derived A/z cross the BLAS pointer boundary; never change their
        # preparation by converting J or mobility to a different memory order.
        vfree = np.asarray(vfree, dtype=np.float64)
        mobility = np.asarray(mobility, dtype=np.float64)
        jacobian = np.asarray(jacobian, dtype=np.float64)
        gaps = np.asarray(gaps, dtype=np.float64)
        if (vfree.ndim != 1 or gaps.ndim != 1 or not len(vfree) or
                mobility.shape != (len(vfree), len(vfree)) or
                jacobian.shape != (3*len(gaps), len(vfree)) or
                not gaps.flags.c_contiguous or
                not all(np.isfinite(x).all() for x in (vfree, mobility, jacobian, gaps)) or
                not np.isfinite([dt, friction, tol, maxiter]).all() or
                dt <= 0 or friction < 0 or tol <= 0 or maxiter < 1 or int(maxiter) != maxiter):
            raise ValueError("invalid compiled contact inputs")
    except (ValueError, TypeError, OverflowError):
        _stats["failures"] += 1
        raise ValueError("invalid compiled contact inputs") from None
    dt, friction, tol, maxiter = float(dt), float(friction), float(tol), int(maxiter)
    if not len(gaps):
        _stats["successes"] += 1
        return vfree, {"iterations": 0, "residual": 0., "force_residual": 0.,
                       "dissipation": 0., "reactions": [], "solver": "projected_sor"}
    A = jacobian@mobility@jacobian.T
    z = jacobian@vfree
    scale = max(np.linalg.norm(vfree), 1e-15)
    steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max()
                      for k in range(len(gaps))])
    if (not all(np.isfinite(x).all() for x in (A, z, gaps, steps)) or not np.isfinite(scale) or
            A.dtype != np.float64 or z.dtype != np.float64 or
            not A.flags.c_contiguous or not z.flags.c_contiguous or
            np.any(np.diag(A)[::3] <= 0) or np.any(steps <= 0) or
            not np.isfinite([dt, friction, tol]).all() or dt <= 0 or friction < 0 or
            tol <= 0 or maxiter < 0):
        _stats["failures"] += 1
        raise RuntimeError("invalid compiled contact inputs")
    started = time.perf_counter()
    force, sweeps, converged = cold_loop(A, z, gaps, dt, friction, steps,
                                       scale, tol, maxiter, 1.7)
    elapsed = time.perf_counter()-started
    _stats["loop_seconds"] += elapsed
    _stats["iterations"] += int(sweeps)
    diagnostics = {"solver": "numpy_blas_projected_sor", "iterations": int(sweeps),
                   "loop_seconds": elapsed, "compiled_converged": bool(converged)}
    started = time.perf_counter()
    try:
        if not converged or not np.isfinite(force).all():
            raise RuntimeError("direct contact residual nonconvergence")
        answer = s50._finish(vfree, mobility, jacobian, force, z, A, gaps, dt,
                            friction, steps, int(sweeps), "projected_sor", {"relaxation": 1.7})
        if not np.isfinite([answer[1][key] for key in
                            ("residual", "force_residual", "dissipation")]).all():
            raise RuntimeError("nonfinite compiled contact health")
    except RuntimeError as exc:
        _stats["failures"] += 1
        exc.iterations = int(sweeps)
        exc.contact_diagnostics = diagnostics
        raise
    finally:
        _stats["finish_seconds"] += time.perf_counter()-started
    _stats["successes"] += 1
    return answer


_solve_prepared = solve_prepared
_solve = solve_prepared
