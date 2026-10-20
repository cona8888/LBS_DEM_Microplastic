"""One-dimensional inertialess physical motion, restricted to sampled domain."""
import json,hashlib
from pathlib import Path
import numpy as np
from translation_stepper_v1 import integrate
root=Path(__file__).resolve().parents[1]/'stage36_evaluations/stage36bd_prolate_motion_20260911'
out=root/'motion_01';out.mkdir(exist_ok=False)
r=json.loads((root/'verification_01/results.json').read_text());fine=json.loads((root/'spatial_01/results.json').read_text())
if not r['passed'] or not fine['passed']:raise ValueError('unqualified inputs')
x=np.array([v['offset'] for v in r['rows']]);mob=np.array([-1e-4/v['force'][0] for v in r['rows']])
train=[0,2];hold=[1]
hold_error=max(abs(np.interp(x[i],x[train],mob[train])-mob[i])/mob[i] for i in hold)
spatial=abs(fine['rows'][0]['force'][0]-r['rows'][1]['force'][0])/abs(fine['rows'][0]['force'][0])
if hold_error>.001 or spatial>.001:raise ValueError('interpolation/spatial gate failed')
def provider(p):
    if not 0<=p[0]<=.02 or abs(p[1])+abs(p[2])>1e-15:raise ValueError('outside axial table domain')
    # Only xx is used; transverse motion is explicitly disallowed.
    return np.eye(3)*np.interp(p[0],x[train],mob[train])
rows=[]
for n in [20,40,80,160]:
    path=integrate([0,0,0],[1e-4,0,0],provider,lambda p:2-np.linalg.norm(p),duration=1000,steps=n)
    np.save(out/f'path_n{n}.npy',path);rows.append({'steps':n,'endpoint':float(path[-1,0])})
error=abs(rows[-2]['endpoint']-rows[-1]['endpoint'])
result={'rows':rows,'interpolation_holdout_relative_error':float(hold_error),'spatial_force_relative_shift':float(spatial),'last_timestep_endpoint_difference':error,'passed':error<1e-6,'scope':'axial prolate translation only; rigid prolate semiaxes [2,1,1], cavity radius 4, mu .1, force 1e-4, duration 1000 in consistent benchmark units; quasi-steady inertialess; no release','input_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'verification_01/results.json',root/'spatial_01/results.json',Path(__file__)]}}
(out/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
