"""Stage36AH solver plus deterministic zero-momentum roundoff restoration."""
import numpy as np
import periodic_drag_reference_fast_v1 as base

initialize=base.initialize

def step(state,source_impulse_per_cell):
    new,row=base.step(state,source_impulse_per_cell)
    f=new['f'];target=float(new['n']**3);delta=target-f.sum(dtype=np.float64)
    if not np.isfinite(delta) or abs(delta)>1e-9:raise ValueError('mass correction outside qualified bound')
    f[0,0,0,0]+=delta
    residual=target-f.sum(dtype=np.float64)
    if residual:
        f[0,0,0,0]+=residual
        delta+=residual
    if f[0,0,0,0]<=0:raise ValueError('rest-population positivity failure')
    new['f']=f;row['mass_restoration_lu']=float(delta)
    row['mass_relative_drift']=abs(float(f.sum(dtype=np.float64))/target-1)
    row['density_error']=float(np.max(np.abs(f.sum(axis=0)-1)))
    row['minimum_population']=float(f.min())
    return new,row
