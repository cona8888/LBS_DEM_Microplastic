"""The same Lipschitz certificate with at most four subintervals.

When the full-interval bound is inconclusive, sample the original four
subinterval endpoints for that grain and bound each subinterval separately.
No minimizer, physics, penetration threshold or fallback is weakened.
"""
from contextlib import contextmanager
import numpy as np
import certified_sweep_v1 as base
prior,original,REFERENCE=base.prior,base.original,base.REFERENCE
records=[]
collect=True
stats={'calls':0,'certified':0,'fallback':0,'subdivided_grains':0}


def certificate(geometry,x,p,v,a,b,dt):
    row=base.certificate(geometry,x,p,v,a,b,dt)
    if row is None or row['certified']:return row
    motion=original._FixedMotion(x,p,v,a);times=np.linspace(0.,dt,5);minimum=0.
    for pair in row['pairs']:
        if pair['lower']>=row['threshold_m']:
            minimum=min(minimum,pair['lower']);continue
        k=pair['grain'];delta=geometry.c[k]-x;delta-=geometry.L*np.round(delta/geometry.L);centre=x+delta
        gaps=[pair['f0']]+[original._gap_at_pose(*motion.at(t),a,b,centre,geometry.r[k]) for t in times[1:-1]]+[pair['f1']]
        bounds=[]
        for i in range(4):
            travel=row['motion_speed_bound']*(times[i+1]-times[i]);left,right=gaps[i:i+2]
            bounds.append(max(left-travel,right-travel,(left+right-travel)/2)-pair['pad'])
        pair['partition_times_s']=times.tolist();pair['partition_gaps_m']=[float(z) for z in gaps]
        pair['partition_lower_bounds_m']=[float(z) for z in bounds]
        pair['whole_interval_lower_m']=pair['lower'];pair['lower']=float(min(bounds))
        minimum=min(minimum,pair['lower']);stats['subdivided_grains']+=1
    row['lower_bound_m']=float(minimum);row['certified']=bool(minimum>=row['threshold_m']);row['partition_cap']=4
    return row


def swept_gap(geometry,x,p,v,a,b,dt):
    stats['calls']+=1;row=certificate(geometry,x,p,v,a,b,dt)
    if row is not None and row['certified']:
        stats['certified']+=1
        if collect:records.append(row)
        return row['lower_bound_m']
    stats['fallback']+=1;value=REFERENCE(geometry,x,p,v,a,b,dt)
    if collect:records.append({'certified':False,'reference_gap_m':float(value),'dt_s':float(dt)})
    return value


@contextmanager
def scope():
    saved=prior.swept_gap
    if saved is not REFERENCE:raise RuntimeError('unexpected sweep implementation')
    prior.swept_gap=swept_gap
    try:yield
    finally:prior.swept_gap=saved
