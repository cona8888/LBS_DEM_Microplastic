"""Held-out midpoint orientation check; fixed position only."""
import json,hashlib
from pathlib import Path
import numpy as np
base=Path(__file__).resolve().parents[1]/'stage36_evaluations'
root=base/'stage36bj_orientation_table_20260911';out=root/'holdout_01';out.mkdir(exist_ok=False)
cfg={'angles':[29,31],'held_out_angle':30,'relative_limit':.001,'position':[0,.4,0],'scope':'orientation slice only; translation is outside table'}
(out/'contract.json').write_text(json.dumps(cfg,indent=2))
def load(p):
    r=json.loads((p/'results.json').read_text());op=p/'operator.npz'
    if not r['passed'] or hashlib.sha256(op.read_bytes()).hexdigest()!=r['operator_hash']:raise ValueError('invalid evidence')
    with np.load(op,allow_pickle=False) as d:return d['resistance'].copy()
A=load(root/'angle_29');B=load(root/'angle_31');truth=load(base/'stage36bi_coupling_refinement_20260911/verification_01')
approx=(A+B)/2
rel=lambda a,b:float(np.linalg.norm(a-b)/np.linalg.norm(b))
force=np.array([1e-4,0,0,0,0,0]);za=np.linalg.solve(approx,force);zt=np.linalg.solve(truth,force)
errors={'resistance':rel(approx,truth),'coupling_block':rel(approx[:3,3:],truth[:3,3:]),'lateral_velocity':float(abs((za[1]-zt[1])/zt[1])),'angular_velocity':float(abs((za[5]-zt[5])/zt[5]))}
checks={k:v<.001 for k,v in errors.items()};checks['positive_dissipation']=bool(np.linalg.eigvalsh((approx+approx.T)/2).min()>0)
np.savez_compressed(out/'table.npz',angles=[29,31],resistance=np.array([A,B]))
(out/'results.json').write_text(json.dumps({'errors':errors,'checks':checks,'passed':all(checks.values()),'scope':cfg['scope']},indent=2));print(json.dumps(errors));print(checks)
