"""Guard and dimensional mapping tests; no motion integration."""
import json,hashlib
from pathlib import Path
import numpy as np
from guarded_mobility_v1 import GuardedMobility
import guarded_mobility_v1 as module
root=Path(__file__).resolve().parents[1]
source=root/'stage36_evaluations/stage36az_mobility_20260911/verification_01'
out=root/'stage36_evaluations/stage36ba_guard_20260911/verification_01';out.mkdir(parents=True,exist_ok=False)
g=GuardedMobility(source)
kw={'centre':[0,.4,0],'axes':[2,1,1],'orientation':np.eye(3),'cavity_radius':4,'mu':.1}
checks={}
with np.load(source/'operator.npz',allow_pickle=False) as d:R=d['resistance'].copy()
target=np.array([2,-3,4,1,2,-1])*1e-5;load=R@target
V,W=g.motion(load[:3],load[3:]*2,**kw)
checks['dimensional_recovery']=bool(np.allclose(np.r_[V,2*W],target,rtol=1e-12,atol=1e-18))
V,W=g.motion([0,0,0],[0,0,0],**kw);checks['zero_load']=bool(np.array_equal(np.r_[V,W],np.zeros(6)))
changes={'centre':[0,.4000000001,0],'axes':[2.01,1,1],'orientation':[[0,-1,0],[1,0,0],[0,0,1]],'cavity_radius':4.01,'mu':.11}
for key,value in changes.items():
    try:g.motion([0,0,0],[0,0,0],**{**kw,key:value});checks['reject_'+key]=False
    except ValueError:checks['reject_'+key]=True
for name,F,T in [('nan',[float('nan'),0,0],[0,0,0]),('shape',[1,2],[0,0,0]),('infinite_torque',[0,0,0],[0,float('inf'),0])]:
    try:g.motion(F,T,**kw);checks['reject_'+name]=False
    except ValueError:checks['reject_'+name]=True
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(out/'results.json').write_text(json.dumps({'checks':checks,'passed':all(checks.values()),'hashes':{str(p):sha(p) for p in [Path(__file__),Path(module.__file__),source/'results.json',source/'operator.npz']},'trajectory_executed':False},indent=2))
print(checks)
