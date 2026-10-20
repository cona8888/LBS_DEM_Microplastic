"""Test additive position/orientation interpolation on an unused mixed pose."""
import json,hashlib
from pathlib import Path
import numpy as np
base=Path(__file__).resolve().parents[1]/'stage36_evaluations';out=base/'stage36bl_mixed_pose_20260911/holdout_01';out.mkdir(exist_ok=False)
cfg={'x':.005,'y':.4,'angle':30.5,'relative_limit':.001,'method':'R(theta)+R(x)-R(base)','role':'held-out mixed pose; not used in construction'}
(out/'contract.json').write_text(json.dumps(cfg,indent=2))
hashes={}
def load(path):
    p=base/path;r=json.loads((p/'results.json').read_text());op=p/'operator.npz';h=hashlib.sha256(op.read_bytes()).hexdigest()
    if not r['passed'] or h!=r['operator_hash']:raise ValueError('unqualified input')
    hashes[str(op)]=h
    with np.load(op,allow_pickle=False) as d:return d['resistance'].copy()
R0=load('stage36bh_offset_tilt_20260911/verification_01')
Ra=load('stage36bj_orientation_table_20260911/angle_29');Rb=load('stage36bj_orientation_table_20260911/angle_31')
Rx=load('stage36bk_position_table_20260911/offset_-0.01');Ry=load('stage36bk_position_table_20260911/offset_0.01')
prediction=.25*Ra+.75*Rb+.25*Rx+.75*Ry-R0
truth=load('stage36bl_mixed_pose_20260911/verification_01')
rel=lambda a,b:float(np.linalg.norm(a-b)/np.linalg.norm(b))
F=np.array([1e-4,0,0,0,0,0]);zp=np.linalg.solve(prediction,F);zt=np.linalg.solve(truth,F)
errors={'matrix':rel(prediction,truth),'coupling':rel(prediction[:3,3:],truth[:3,3:]),'lateral':float(abs((zp[1]-zt[1])/zt[1])),'angular':float(abs((zp[5]-zt[5])/zt[5]))}
checks={k:v<.001 for k,v in errors.items()};checks['positive']=bool(np.linalg.eigvalsh((prediction+prediction.T)/2).min()>0)
(out/'results.json').write_text(json.dumps({'errors':errors,'checks':checks,'passed':all(checks.values()),'hashes':hashes},indent=2));print(json.dumps(errors));print(checks)
