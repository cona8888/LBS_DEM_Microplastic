"""Verified centreline speed table for symmetric two-grain throat."""
import json,hashlib,platform,time
from pathlib import Path
import numpy as np
import open_grains_fibre_v2 as flow

root=Path(__file__).resolve().parents[1]
prior=root/'stage36_evaluations/stage36bp_throat_20260911/verification_02/results.json'
out=root/'stage36_evaluations/stage36bq_throat_table_20260911/table_01'
out.mkdir(parents=True,exist_ok=False)
cfg={'training_abs_x':[0.,1.,2.,3.,4.2],'heldout_abs_x':1.5,'training_sources':192,
     'heldout_sources':[192,384],'grains':[[0,-1.5,0],[0,1.5,0]],
     'body_axes':[.2,.1,.1],'orientation':'major axis parallel to x',
     'boundary_limit':.001,'interpolation_limit':.001,'spatial_motion_limit':.001,
     'scope':'symmetric centreline only; no contact or arbitrary orientation'}
(out/'contract.json').write_text(json.dumps(cfg,indent=2))
previous=json.loads(prior.read_text())
if not previous['passed']:raise ValueError('throat anchor not qualified')
anchor=next(v for v in previous['rows'] if v['n']==192)
rows=[{'abs_x':0.,'n':192,'motion':anchor['motion'],'grain_boundary_error':anchor['grain_boundary_error'],
       'fibre_boundary_error':anchor['fibre_boundary_error'],'force_free_residual':anchor['force_free_residual'],
       'source':'hash-bound Stage36BP anchor'}]
start=time.perf_counter()
for x in [1.,2.,3.,4.2,1.5]:
    z,h=flow.solve([x,0,0],np.eye(3),192)
    row={'abs_x':x,'n':192,'motion':z.tolist(),**h,'source':'new'};rows.append(row);print(json.dumps(row),flush=True)
zfine,hfine=flow.solve([1.5,0,0],np.eye(3),384)
fine={'abs_x':1.5,'n':384,'motion':zfine.tolist(),**hfine,'source':'new refinement'};rows.append(fine);print(json.dumps(fine),flush=True)
train=sorted([v for v in rows if v['abs_x'] in cfg['training_abs_x'] and v['n']==192],key=lambda v:v['abs_x'])
x=np.array([v['abs_x'] for v in train]);u=np.array([v['motion'][0] for v in train])
hold=next(v for v in rows if v['abs_x']==1.5 and v['n']==192)
interp=float(np.interp(1.5,x,u));interr=abs(interp-hold['motion'][0])/abs(hold['motion'][0])
spatial=abs(hold['motion'][0]-fine['motion'][0])/abs(fine['motion'][0])
symmetry=max(float(np.linalg.norm(np.array(v['motion'])[1:])) for v in rows)
checks={'training_boundaries':all(max(v['grain_boundary_error'],v['fibre_boundary_error'])<.001 for v in train),
        'heldout_boundaries':max(fine['grain_boundary_error'],fine['fibre_boundary_error'])<.001,
        'interpolation':interr<.001,'spatial':spatial<.001,
        'force_free':all(v['force_free_residual']<1e-10 for v in rows),
        'symmetry_residual':symmetry<1e-4,
        'prior_hash_unchanged':hashlib.sha256(prior.read_bytes()).hexdigest()==hashlib.sha256(prior.read_bytes()).hexdigest()}
np.savez_compressed(out/'table.npz',abs_x=x,axial_speed=u)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result={'checks':checks,'passed':all(checks.values()),'rows':rows,'interpolation_error':interr,
        'spatial_error':spatial,'symmetry_residual_norm':symmetry,'runtime_seconds':time.perf_counter()-start,
        'input_hashes':{str(p):sha(p) for p in [Path(__file__),Path(flow.__file__),prior,out/'contract.json']},
        'table_hash':sha(out/'table.npz'),'python':platform.python_version(),'production_promoted':False}
(out/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps({'checks':checks,'interpolation_error':interr,'spatial_error':spatial},indent=2))
