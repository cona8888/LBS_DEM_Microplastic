"""Frozen-pose equivalence and performance check for QR candidate."""
import hashlib,json,time
from pathlib import Path
import numpy as np
import open_grains_ellipsoid_qr_v1 as qr
R=Path(__file__).resolve().parents[1];O=R/'stage36_evaluations/stage36ca_qr_acceleration_20260911/verification_01';O.mkdir(parents=True,exist_ok=False)
P=R/'stage36_evaluations/stage36bw_pose_qualification_20260911/run_03/results.json';prior=json.loads(P.read_text())
cfg={'cases':[1,2,5,8,12],'count':384,'translation_absolute_limit':1e-6,'rotation_absolute_limit':1e-5,
 'boundary_limit':.001,'minimum_speedup':2,'comparison':'frozen SVD n384 pose records'}
(O/'contract.json').write_text(json.dumps(cfg,indent=2));rows=[]
radius=float(np.cbrt(.002));start=time.perf_counter()
for number in cfg['cases']:
    ref=prior['rows'][number-1];a=np.deg2rad(ref['angle_degrees']);Q=np.array([[np.cos(a),-np.sin(a),0],[np.sin(a),np.cos(a),0],[0,0,1.]])
    axes=(radius,)*3 if ref['shape']=='sphere' else (.2,.1,.1);tick=time.perf_counter();z,h=qr.solve([0,ref['y'],0],Q,384,axes=axes);elapsed=time.perf_counter()-tick
    frozen=next(s for s in ref['solves'] if s['n']==384);delta=z-np.asarray(frozen['motion'])
    row={'case':number,'shape':ref['shape'],'y':ref['y'],'angle':ref['angle_degrees'],'motion':z.tolist(),**h,'seconds':elapsed,
         'translation_difference':float(np.linalg.norm(delta[:3])),'rotation_difference':float(np.linalg.norm(delta[3:])),
         'speedup':frozen['seconds']/elapsed};rows.append(row);print(json.dumps(row),flush=True)
checks={'prior_pass':prior['passed'],'translation':all(r['translation_difference']<cfg['translation_absolute_limit'] for r in rows),
 'rotation':all(r['rotation_difference']<cfg['rotation_absolute_limit'] for r in rows),
 'boundary':all(max(r['grain_boundary_error'],r['fibre_boundary_error'])<cfg['boundary_limit'] for r in rows),
 'force_free':all(r['force_free_residual']<1e-10 for r in rows),'speedup':min(r['speedup'] for r in rows)>cfg['minimum_speedup']}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
res={'passed':all(checks.values()),'checks':checks,'rows':rows,'runtime_seconds':time.perf_counter()-start,
 'input_hashes':{str(p):sha(p) for p in [Path(__file__),Path(qr.__file__),Path(qr.m.__file__),Path(qr.q.__file__),P,O/'contract.json']}}
(O/'results.json').write_text(json.dumps(res,indent=2));print(json.dumps(checks),flush=True)
