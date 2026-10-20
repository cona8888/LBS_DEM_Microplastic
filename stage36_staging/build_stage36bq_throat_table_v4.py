"""Final local midpoint refinement of the verified throat table."""
import hashlib,json,platform,time
from pathlib import Path
import numpy as np
from scipy.interpolate import PchipInterpolator
import open_grains_fibre_v2 as flow
ROOT=Path(__file__).resolve().parents[1]
P3=ROOT/'stage36_evaluations/stage36bq_throat_table_20260911/table_03/results.json'
OUT=ROOT/'stage36_evaluations/stage36bq_throat_table_20260911/table_04'
if OUT.exists():raise FileExistsError(OUT)
OUT.mkdir(parents=True)
cfg={'training_abs_x':[0,.25,.5,.625,.75,1,1.25,1.5,2,2.5,3,3.6,4.2],
 'heldout_abs_x':[.125,.375,.5625,.6875,.875,1.125,1.375,2.75,3.9],
 'new_source_count':256,'interpolator':'PCHIP','boundary_limit':.001,
 'interpolation_limit':.001,'force_free_limit':1e-10,'symmetry_residual_limit':1e-4,
 'refinement_reason':'table_03 only x=0.625 failed at 0.001198; threshold unchanged',
 'scope':'symmetric centreline aligned prolate only; pre-comparison; no validation claim'}
(OUT/'contract.json').write_text(json.dumps(cfg,indent=2))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs=[Path(__file__),Path(flow.__file__),P3,OUT/'contract.json'];before={str(p):sha(p) for p in inputs}
d=json.loads(P3.read_text())
if d['passed']:raise ValueError('table_03 expected preserved near-miss')
byx={r['abs_x']:r for r in d['rows']}
training=[]
for x in [0,.25,.5,.75,1,1.25,1.5,2,2.5,3,3.6,4.2]:
 r=dict(byx[x]);r['role']='training';r['source']='hash-bound qualified solve from table_03';training.append(r)
heldout=[]
for x in [.125,.375,.875,1.125,1.375,2.75,3.9]:
 r=dict(byx[x]);r['role']='heldout';r['source']='hash-bound passing held-out solve from table_03';heldout.append(r)
start=time.perf_counter()
for role,positions in [('training',[.625]),('heldout',[.5625,.6875])]:
 for x in positions:
  z,h=flow.solve([x,0,0],np.eye(3),cfg['new_source_count'])
  r={'abs_x':x,'n':cfg['new_source_count'],'motion':z.tolist(),**h,'source':'new','role':role}
  (training if role=='training' else heldout).append(r);print(json.dumps(r),flush=True)
training.sort(key=lambda r:r['abs_x']);heldout.sort(key=lambda r:r['abs_x'])
x=np.array([r['abs_x'] for r in training]);u=np.array([r['motion'][0] for r in training]);p=PchipInterpolator(x,u)
for r in heldout:
 r['interpolated_axial_speed']=float(p(r['abs_x']))
 r['relative_interpolation_error']=abs(r['interpolated_axial_speed']-r['motion'][0])/abs(r['motion'][0])
rows=training+heldout;after={str(p):sha(p) for p in inputs}
checks={'lineage_status':not d['passed'],'input_hashes_unchanged':before==after,
 'boundary':all(max(r['grain_boundary_error'],r['fibre_boundary_error'])<cfg['boundary_limit'] for r in rows),
 'force_free':all(r['force_free_residual']<cfg['force_free_limit'] for r in rows),
 'symmetry':max(float(np.linalg.norm(np.asarray(r['motion'])[1:])) for r in rows)<cfg['symmetry_residual_limit'],
 'heldout_interpolation':all(r['relative_interpolation_error']<cfg['interpolation_limit'] for r in heldout),
 'positive_speed':bool(np.all(u>0))}
np.savez_compressed(OUT/'table.npz',abs_x=x,axial_speed=u)
res={'checks':checks,'passed':all(checks.values()),'rows':rows,
 'max_interpolation_error':max(r['relative_interpolation_error'] for r in heldout),
 'max_boundary_error':max(max(r['grain_boundary_error'],r['fibre_boundary_error']) for r in rows),
 'runtime_seconds':time.perf_counter()-start,'input_hashes':before,'table_hash':sha(OUT/'table.npz'),
 'python':platform.python_version(),'production_promoted':False}
(OUT/'results.json').write_text(json.dumps(res,indent=2))
print(json.dumps({'checks':checks,'max_interpolation_error':res['max_interpolation_error'],
 'heldout_errors':[(r['abs_x'],r['relative_interpolation_error']) for r in heldout]},indent=2))
