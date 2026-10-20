"""Qualify the twelve frozen ensemble poses before trajectory execution."""
import hashlib,json,time
from pathlib import Path
import numpy as np
import open_grains_ellipsoid_v1 as flow
R=Path(__file__).resolve().parents[1];O=R/'stage36_evaluations/stage36bw_pose_qualification_20260911/run_01'
O.mkdir(parents=True,exist_ok=False)
design=R/'stage36_evaluations/stage36bv_review_and_next_20260911/review_01/next_stage_contract.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cfg={'design_sha256':sha(design),'qualification_x':0.,'counts':[256,384],
 'boundary_limit':.001,'translation_refinement_absolute_limit':.0001,
 'rotation_refinement_absolute_limit':.0001,'force_free_limit':1e-10,
 'meaning':'pose qualification only; no trajectory or release inference'}
(O/'contract.json').write_text(json.dumps(cfg,indent=2))
inputs=[Path(__file__),Path(flow.__file__),Path(flow.m.__file__),Path(flow.q.__file__),design,O/'contract.json']
hashes={str(p):sha(p) for p in inputs};(O/'inputs.json').write_text(json.dumps(hashes,indent=2))
rows=[];start=time.perf_counter();radius=float(np.cbrt(.002))
for shape in ['sphere','prolate']:
 for y in [0.,.15,-.15]:
  for angle in ([0] if shape=='sphere' else [0,45,90]):
   a=np.deg2rad(angle);Q=np.array([[np.cos(a),-np.sin(a),0],[np.sin(a),np.cos(a),0],[0,0,1.]])
   axes=(radius,)*3 if shape=='sphere' else (.2,.1,.1);solves=[]
   for n in cfg['counts']:
    tick=time.perf_counter();z,h=flow.solve([0,y,0],Q,n,axes=axes)
    solves.append({'n':n,'motion':z.tolist(),**h,'seconds':time.perf_counter()-tick})
   delta=np.asarray(solves[-1]['motion'])-solves[0]['motion'];fine=solves[-1]
   checks={'boundary':max(fine['grain_boundary_error'],fine['fibre_boundary_error'])<.001,
    'translation':bool(np.linalg.norm(delta[:3])<.0001),'rotation':bool(np.linalg.norm(delta[3:])<.0001),
    'force_free':all(s['force_free_residual']<1e-10 for s in solves)}
   row={'shape':shape,'y':y,'angle_degrees':angle,'solves':solves,'checks':checks,'passed':all(checks.values())}
   rows.append(row);(O/f'case_{len(rows):02}.json').write_text(json.dumps(row,indent=2))
   print(json.dumps({'completed':len(rows),'shape':shape,'y':y,'angle':angle,'checks':checks}),flush=True)
res={'passed':all(v['passed'] for v in rows) and all(sha(p)==h for p,h in hashes.items()),'rows':rows,
 'input_hashes':hashes,'runtime_seconds':time.perf_counter()-start,'trajectories_executed':False}
(O/'results.json').write_text(json.dumps(res,indent=2));print(json.dumps({'passed':res['passed'],'seconds':res['runtime_seconds']}),flush=True)
