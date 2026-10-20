"""Conservative whole-grain/interval pruning; unchanged retained minimizers.

For a rigid ellipsoid of largest semiaxis a, translation v and angular speed
|omega|, Hausdorff motion is bounded by L|dt|, L=|v|+a|omega|. Distance from a
fixed grain centre to the solid is therefore L-Lipschitz. Endpoint distances
give a lower bound throughout a time interval. Work is omitted only when
that bound, minus a floating-point safety margin, exceeds an already observed
minimum. The legacy four bounded minimizers and root tolerance are retained.
This does not cure the legacy minimizer's lack of global-minimum certification.
"""
import sys
from pathlib import Path
import numpy as np
from scipy.optimize import minimize_scalar

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage76_staging")]
import geometry_fail_fast_sweep_v1 as legacy
original=legacy.original
_reference_sweep=legacy.swept_gap
_stats={"calls":0,"grains":0,"skipped_grains":0,"skipped_intervals":0,"minimizer_calls":0}


def stats():return dict(_stats)


def interval_lower(f0,f1,speed,dt,lo,hi,padding):
    return max(f0-speed*hi,f1-speed*(dt-lo),(f0+f1-speed*dt)/2)-padding


def swept_gap(geometry,x,p,v,a,b,dt):
    if not isinstance(geometry,original.reference.GrainGeometry) or abs(a-b)<1e-13*a:
        return _reference_sweep(geometry,x,p,v,a,b,dt)
    if not np.isfinite([a,b,dt]).all() or not a>=b>0 or dt<0:
        raise ValueError("finite prolate axes and nonnegative timestep required")
    x,p,v=(original.reference.finite(x),original.reference.finite(p),original.reference.finite(v))
    _stats["calls"]+=1;legacy._stats["calls"]+=1
    travel=np.linalg.norm(v[:3])*dt
    ids=geometry.tree.query_ball_point(np.mod(x,geometry.L),geometry.r.max()+a+travel)
    motion=original._FixedMotion(x,p,v,a)
    speed=float(np.linalg.norm(v[:3])+a*motion.angular_speed)
    threshold=-1e-5*b
    minimum=np.inf;grains=[]
    intervals=np.linspace(0,dt,5)
    for k in ids:
        d=geometry.c[k]-x;d-=geometry.L*np.round(d/geometry.L);c=x+d
        def fun(t):
            xx,pp=motion.at(t)
            return original._gap_at_pose(xx,pp,a,b,c,geometry.r[k])
        f0,f1=fun(0),fun(dt)
        gap=min(f0,f1)
        if gap<threshold:
            legacy._stats["endpoint_early_rejects"]+=1
            return float(gap)
        minimum=min(minimum,gap)
        # This is a conservative engineering roundoff margin, not formal
        # interval arithmetic. It far exceeds the unchanged root xtol scale.
        padding=1e-10*(np.linalg.norm(x)+np.linalg.norm(c)+a+geometry.r[k]+travel)
        grains.append((k,c,f0,f1,padding))
    for k,c,f0,f1,padding in grains:
        _stats["grains"]+=1
        lower=interval_lower(f0,f1,speed,dt,0,dt,padding)
        if lower>=minimum and lower>-geometry.r[k]:
            _stats["skipped_grains"]+=1
            continue
        def fun(t):
            xx,pp=motion.at(t)
            return original._gap_at_pose(xx,pp,a,b,c,geometry.r[k])
        for lo,hi in zip(intervals[:-1],intervals[1:]):
            lower=interval_lower(f0,f1,speed,dt,lo,hi,padding)
            if lower>=minimum and lower>-geometry.r[k]:
                _stats["skipped_intervals"]+=1
                continue
            _stats["minimizer_calls"]+=1
            opt=minimize_scalar(fun,bounds=(lo,hi),method="bounded",options={"xatol":max(dt*1e-8,1e-14)})
            if not opt.success:raise RuntimeError("swept-gap minimization failed")
            minimum=min(minimum,opt.fun)
            if minimum<threshold:
                legacy._stats["interior_early_rejects"]+=1
                return float(minimum)
    legacy._stats["full_evaluations"]+=1
    return float(minimum)
