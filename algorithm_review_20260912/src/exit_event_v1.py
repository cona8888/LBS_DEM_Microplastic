"""Earliest whole-prolate exit during a constant-twist numerical interval.

Unlike endpoint sign testing this detects exit-and-return events. Intervals are
discarded only when a rigid-motion Lipschitz or second-derivative bound keeps
the whole support function inside. Tangency unresolved at floating precision
fails closed rather than silently declaring no exit.
"""
import sys
from pathlib import Path
import numpy as np
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "stage37_staging"))
import transport_contact as mechanics


def linear_pose_exit_time(x, p, v, a, b, outlet, dt):
    x, p, v = mechanics.finite(x), mechanics.unit(p), mechanics.finite(v)
    if (x.shape != (3,) or p.shape != (3,) or v.shape != (6,)
            or not np.isfinite([a,b,outlet,dt]).all() or not a >= b > 0 or dt < 0):
        raise ValueError("valid prolate pose and nonnegative interval required")
    start = mechanics.full_exit_function(x, p, a, b, outlet)
    if start >= 0:
        return 0.0
    if dt == 0:
        return None
    omega = float(np.linalg.norm(v[3:])/a)
    roundoff = 32*np.finfo(float).eps * max(abs(x[0]), abs(outlet), a)
    rate_bound = abs(v[0]) + a*omega
    if start + rate_bound*dt < -roundoff:
        return None
    # Orientation-invariant support is linear in time: no minimizer needed.
    if a == b or omega == 0:
        if v[0] <= 0:
            return None
        event = -start/v[0]
        return float(event) if event <= dt else None

    def fn(time):
        return mechanics.full_exit_function(
            *mechanics.advance_pose(x,p,v,a,time),a,b,outlet)

    c = a*a-b*b
    # h'' = c*b^2*(p_x')^2/h^3 + c*p_x*p_x''/h.
    curvature_bound = 2*c/b*omega*omega
    angular_velocity = v[3:]/a

    def derivative(time):
        _, axis = mechanics.advance_pose(x,p,v,a,time)
        z = axis[0]
        dz = np.cross(angular_velocity,axis)[0]
        return v[0]-c*z*dz/np.sqrt(b*b+c*z*z)
    tolerance = max(1e-14, dt*1e-12)
    stack = [(0.0, dt, start, fn(dt))]
    visited = 0
    while stack:
        lo, hi, flo, fhi = stack.pop()
        visited += 1
        if visited > 100000:
            raise RuntimeError("exit localization unresolved within interval budget")
        if flo >= 0:
            return lo
        width = hi-lo
        upper = max(flo,fhi) + curvature_bound*width*width/8
        # A second independent bound helps degenerate low-curvature intervals.
        upper = min(upper, min(flo,fhi)+rate_bound*width)
        if upper < -roundoff:
            continue
        middle = (lo+hi)/2
        slope = derivative(middle)
        variation = curvature_bound*width/2
        if slope-variation > 0:
            # A proven monotone bracket has at most one crossing. This avoids
            # chasing roundoff-sized negative intervals adjacent to the root.
            if fhi >= 0:
                return float(brentq(fn,lo,hi,xtol=tolerance))
            continue
        if slope+variation < 0:
            continue
        if width <= tolerance:
            if fhi >= 0:
                return float(brentq(fn,lo,hi,xtol=tolerance))
            raise RuntimeError("exit tangency unresolved at floating precision")
        fmid = fn(middle)
        # LIFO: inspect the earlier interval before considering a later root.
        stack.append((middle,hi,fmid,fhi))
        stack.append((lo,middle,flo,fmid))
    return None
