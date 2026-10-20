"""Preserve failed pose checks; refine only failures at unchanged tolerances."""
import json,hashlib,time
from pathlib import Path
import numpy as np
import open_grains_ellipsoid_v1 as flow
R=Path(__file__).resolve().parents[1];P=R/'stage36_evaluations/stage36bw_pose_qualification_20260911/run_01/results.json'
O=P.parent.parent/'run_02';O.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
d=json.loads(P.read_text());cfg={'prior_sha256':sha(P),'additional_count':512,'boundary_limit':.001,'translation_limit':.0001,'rotation_limit':.0001,'action':'refine failed poses; reuse passed poses; no tolerance change'}
(O/'contract.json').write_text(json.dumps(cfg,indent=2));hashes={str(p):sha(p) for p in [Path(__file__),Path(flow.__file__),P,O/'contract.json']}
rows=[]
for i,v in enumerate(d['rows']):
 row=dict(v)
 if not row['passed']:
  angle=np.deg2rad(v['angle_degrees']);Q=np.array([[np.cos(angle),-np.sin(angle),0],[np.sin(angle),np.cos(angle),0],[0,0,1.]])
  r=float(np.cbrt(.002));axes=(r,)*3 if v['shape']=='sphere' else (.2,.1,.1)
  start=time.perf_counter();z,h=flow.solve([0,v['y'],0],Q,512,axes=axes)
  fine={'n':512,'motion':z.tolist(),**h,'seconds':time.perf_counter()-start}
  delta=z-np.asarray(v['solves'][-1]['motion']);row['solves']=v['solves']+[fine]
  row['checks']={'boundary':max(h['grain_boundary_error'],h['fibre_boundary_error'])<.001,'translation':bool(np.linalg.norm(delta[:3])<.0001),'rotation':bool(np.linalg.norm(delta[3:])<.0001),'force_free':h['force_free_residual']<1e-10}
  row['passed']=all(row['checks'].values());row['qualification_pair']=[384,512]
 else:row['qualification_pair']=[256,384]
 rows.append(row);(O/f'case_{i+1:02}.json').write_text(json.dumps(row,indent=2))
 print(json.dumps({'completed':i+1,'shape':v['shape'],'y':v['y'],'angle':v['angle_degrees'],'checks':row['checks']}),flush=True)
res={'passed':all(r['passed'] for r in rows),'rows':rows,'input_hashes':hashes,'inputs_unchanged':all(sha(p)==h for p,h in hashes.items()),'trajectories_executed':False}
(O/'results.json').write_text(json.dumps(res,indent=2));print(json.dumps({'passed':res['passed']}),flush=True)
