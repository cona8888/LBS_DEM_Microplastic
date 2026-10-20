"""Experimental local translation projection; not promoted for release runs."""
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'stage89_staging'),str(ROOT/'stage100_staging')]
import verify_short_seed_local_v1 as h
import audit_high_precision_gaps_v1 as hp
core=h.candidate.parent.parent.core

def integrate(*args,**kwargs):
    args=list(args);geometry=args[1];a,b=args[5:7];outlet=args[12]
    # Preserve the original velocity-level solve, only change accepted positions.
    budget=5e-12;target=1e-16;total=0.;events=[]
    original=core.mechanics.advance_pose
    def project(x,p):
        nonlocal total
        x=np.asarray(x).copy();initial=x.copy()
        for iteration in range(4):
            near=geometry.contacts(x,p,a,b,1e-12)
            gaps=[float(hp.gap(x,p,a,b,geometry.c[c[0]],geometry.r[c[0]],geometry.L,60)) for c in near]
            if not gaps or min(gaps)>=0:break
            N=np.array([c[2] for c in near]);rhs=target-np.array(gaps)
            dx=np.linalg.lstsq(N,rhs,rcond=1e-12)[0]
            if np.linalg.norm(dx)>budget-total:raise RuntimeError('projection displacement budget exceeded')
            x=x+dx
        else:raise RuntimeError('projection did not restore clearance')
        distance=float(np.linalg.norm(x-initial))
        if distance:
            if min(abs(initial[0]-outlet),abs(initial[0]))<a+budget:raise RuntimeError('projection near axial boundary prohibited')
            total+=distance
            if total>budget:raise RuntimeError('projection cumulative budget exceeded')
            events.append(dict(translation_m=distance,dx_m=(x-initial).tolist(),minimum_verified_near_gap_m=min(gaps),near_grains_checked=len(near)))
        return x,p
    def advance(x,p,v,ell,dt):
        xx,pp=original(x,p,v,ell,dt)
        return project(xx,pp)
    args[2],args[3]=project(args[2],args[3])
    core.mechanics.advance_pose=advance
    try:r=h.candidate.integrate(*args,**kwargs)
    finally:core.mechanics.advance_pose=original
    r['projection']=dict(total_translation_m=total,events=events,budget_m=budget,
                         policy='translation only; velocity and orientation unchanged; local experimental use')
    return r
