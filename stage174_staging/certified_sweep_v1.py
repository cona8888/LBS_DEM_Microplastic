"""Opt-in conservative nonpenetration certificate; unchanged fallback.

For rigid motion, a point moves by no more than L*dt where L=|v|+a|omega|.
Distance to the moving solid is L-Lipschitz. Each pair's sweep is bounded below
by max(f0-L*T,f1-L*T,(f0+f1-L*T)/2), minus the original Stage116 roundoff pad.
All omitted periodic images have nonnegative gap under the enforced half-cell
guard; cap the global bound at zero. Only bounds above the unchanged -1e-5*b
gate accept early. All other states use the unchanged Stage116 minimizers.

The returned value on certified steps is a LOWER BOUND, not the measured
minimum gap. The minimum_gap diagnostic must be labelled accordingly. Particle
motion, reaction, step selection and rejection threshold are not modified.
This retains the prior engineering roundoff pad, not formal interval arithmetic.
"""
from contextlib import contextmanager
from pathlib import Path
import sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage116_staging'))
import bounded_sweep_v1 as prior
REFERENCE=prior.swept_gap
original=prior.original
records=[]
collect=True
stats={'calls':0,'certified':0,'fallback':0}


def certificate(geometry,x,p,v,a,b,dt):
    if not isinstance(geometry,original.reference.GrainGeometry) or abs(a-b)<1e-13*a:return None
    if not np.isfinite([a,b,dt]).all() or not a>=b>0 or dt<0:raise ValueError('invalid sweep scales')
    x,p,v=[original.reference.finite(z) for z in [x,p,v]]
    if x.shape!=(3,) or p.shape!=(3,) or v.shape!=(6,):raise ValueError('invalid sweep dimensions')
    travel=float(np.linalg.norm(v[:3])*dt);radius=float(geometry.r.max())
    pad=1e-10*(2*np.linalg.norm(x)+geometry.L+a+radius+travel)
    # This guard ensures no second periodic image can enter the swept bound.
    if 2*(radius+a+travel+pad)>=geometry.L:return None
    ids=geometry.tree.query_ball_point(np.mod(x,geometry.L),radius+a+travel+pad)
    motion=original._FixedMotion(x,p,v,a);speed=float(np.linalg.norm(v[:3])+a*motion.angular_speed)
    lower=0.;pairs=[];xx0,pp0=motion.at(0.);xx1,pp1=motion.at(dt)
    for k in ids:
        delta=geometry.c[k]-x;delta-=geometry.L*np.round(delta/geometry.L);c=x+delta
        f0=original._gap_at_pose(xx0,pp0,a,b,c,geometry.r[k])
        f1=original._gap_at_pose(xx1,pp1,a,b,c,geometry.r[k])
        padding=1e-10*(np.linalg.norm(x)+np.linalg.norm(c)+a+geometry.r[k]+travel)
        bound=max(f0-speed*dt,f1-speed*dt,(f0+f1-speed*dt)/2)-padding
        lower=min(lower,bound)
        pairs.append({'grain':int(k),'f0':float(f0),'f1':float(f1),'pad':float(padding),'lower':float(bound)})
    return {'lower_bound_m':float(lower),'certified':bool(lower>=-1e-5*b),'threshold_m':-1e-5*b,
            'motion_speed_bound':speed,'dt_s':float(dt),'a_m':float(a),'b_m':float(b),'pairs':pairs,
            'x':x.tolist(),'p':p.tolist(),'v':v.tolist(),'periodic_half_cell_guard':True}


def swept_gap(geometry,x,p,v,a,b,dt):
    stats['calls']+=1
    row=certificate(geometry,x,p,v,a,b,dt)
    if row is not None and row['certified']:
        stats['certified']+=1
        if collect:records.append(row)
        return row['lower_bound_m']
    stats['fallback']+=1
    value=REFERENCE(geometry,x,p,v,a,b,dt)
    if collect:records.append({'certified':False,'reference_gap_m':float(value),'dt_s':float(dt)})
    return value


@contextmanager
def scope():
    saved=prior.swept_gap
    if saved is not REFERENCE:raise RuntimeError('unexpected sweep implementation')
    prior.swept_gap=swept_gap
    try:yield
    finally:prior.swept_gap=saved
