"""Quantify off-centre coupling; do not rotate cached geometry silently."""
import json,hashlib
from pathlib import Path
import numpy as np
base=Path(__file__).resolve().parents[1]/'stage36_evaluations'
out=base/'stage36bh_offset_tilt_20260911/analysis_01';out.mkdir(exist_ok=False)
def read(stage):
    p=base/stage/'verification_01';r=json.loads((p/'results.json').read_text())
    if not r['passed']:raise ValueError('unqualified operator')
    raw=(p/'operator.npz').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=r['operator_hash']:raise ValueError('hash mismatch')
    with np.load(p/'operator.npz',allow_pickle=False) as d:return d['resistance'].copy(),d['mobility'].copy()
R,M=read('stage36bh_offset_tilt_20260911');old,_=read('stage36az_mobility_20260911')
Q=np.array([[np.sqrt(3)/2,-.5,0],[.5,np.sqrt(3)/2,0],[0,0,1]])
B=np.zeros((6,6));B[:3,:3]=Q;B[3:,3:]=Q
wrong=B@old@B.T
z=M@np.array([1e-4,0,0,0,0,0])
result={'naive_cached_rotation_relative_error':float(np.linalg.norm(R-wrong)/np.linalg.norm(R)),'coupling_relative_norm':float(np.linalg.norm(R[:3,3:])/np.linalg.norm(R)),'force_only_velocity':z[:3].tolist(),'force_only_omega':(z[3:]/2).tolist(),'note':'instantaneous response only; naive transform changes orientation but fails to transform off-centre position consistently; not a trajectory','source_hash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(out/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
