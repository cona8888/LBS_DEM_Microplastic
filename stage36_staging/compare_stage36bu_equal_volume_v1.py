"""Bounded equal-volume shape comparison: local mobility, not recovery calibration."""
import json,hashlib
from pathlib import Path
import numpy as np
import open_grains_ellipsoid_v1 as flow
R=Path(__file__).resolve().parents[1];O=R/'stage36_evaluations/stage36bu_equal_volume_comparison_20260911/run_01'
O.mkdir(parents=True,exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
A=R/'stage36_evaluations/stage36bt_scientific_review_20260911/audit_02/results.json'
audit=json.loads(A.read_text());assert audit['passed'],'fresh audit failed'
r=float(np.cbrt(.2*.1*.1))
cfg={'sphere_radius':r,'prolate_axes':[.2,.1,.1],'positions':[.9375,1.75,3.3],
 'source_counts':[256,384],'boundary_limit':.001,'relative_spatial_speed_limit':.001,
 'reproduction_limit':1e-12,'primary_observable':'local axial mobility U/U_infinity',
 'claim':'equal-volume local shape sensitivity in the same two-grain geometry',
 'excluded_claim':'soil retention or ensemble release comparison'}
(O/'contract.json').write_text(json.dumps(cfg,indent=2))
paths=[Path(__file__),Path(flow.__file__),Path(flow.m.__file__),Path(flow.q.__file__),A,O/'contract.json']
before={str(p):sha(p) for p in paths}
anchor=next(v for v in audit['rows'] if v['x']==.9375)
z,h=flow.solve([.9375,0,0],np.eye(3),384)
repro=float(np.max(np.abs(z-np.asarray(anchor['motion']))));assert repro<1e-12,'generalized solver changed prolate'
rows=[]
for x in cfg['positions']:
 ref=next(v for v in audit['rows'] if v['x']==x)
 solves=[]
 for n in cfg['source_counts']:
  z,h=flow.solve([x,0,0],np.eye(3),n,axes=(r,r,r))
  s={'n':n,'motion':z.tolist(),**h};solves.append(s)
  (O/f'sphere_x{x}_n{n}.json').write_text(json.dumps(s,indent=2));print(json.dumps({'x':x,**s}),flush=True)
 a,b=solves
 rows.append({'x':x,'sphere':solves,'prolate_speed':ref['motion'][0],
 'relative_spatial_error':abs(a['motion'][0]-b['motion'][0])/abs(b['motion'][0]),
 'prolate_to_sphere_speed_ratio':ref['motion'][0]/b['motion'][0]})
checks={'audit_pass':audit['passed'],'reproduction':repro<1e-12,
 'equal_volume':abs(r**3-.002)<1e-15,'inputs_unchanged':before=={str(p):sha(p) for p in paths},
 'spatial':all(v['relative_spatial_error']<.001 for v in rows),
 'fine_boundary':all(max(v['sphere'][-1]['grain_boundary_error'],v['sphere'][-1]['fibre_boundary_error'])<.001 for v in rows),
 'force_free':all(s['force_free_residual']<1e-10 for v in rows for s in v['sphere'])}
res={'passed':all(checks.values()),'checks':checks,'rows':rows,'input_hashes':before,'reproduction_error':repro,'external_validation':False}
(O/'results.json').write_text(json.dumps(res,indent=2));print(json.dumps(checks),flush=True)
