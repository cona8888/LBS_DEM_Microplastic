"""Centred spheroid rotation; spherical enclosure gives rotational covariance."""
import json,hashlib
from pathlib import Path
import numpy as np
import rigid_pose_stepper_v1 as step
root=Path(__file__).resolve().parents[1]/'stage36_evaluations/stage36bf_centred_rotation_20260911'
out=root/'rotation_01';out.mkdir(exist_ok=False)
cfg={'projection_limit':.001,'steps':[20,40,80,160],'duration':1000.,'force':[0,0,0],'torque':[.001,.002,.003],'position':[0,0,0],'scope':'centred rigid prolate in spherical cavity; no translation, contact or release','timestep_orientation_limit':1e-5}
(out/'contract.json').write_text(json.dumps(cfg,indent=2))
r=json.loads((root/'verification_01/results.json').read_text())
if not r['passed']:raise ValueError('operator failed')
op=root/'verification_01/operator.npz'
if hashlib.sha256(op.read_bytes()).hexdigest()!=r['operator_hash']:raise ValueError('operator changed')
with np.load(op,allow_pickle=False) as data:R=data['resistance'].copy()
# Exact centred spheroid symmetries: diagonal and equal transverse entries.
diagonal=np.diag(R).copy();diagonal[1:3]=diagonal[1:3].mean();diagonal[4:6]=diagonal[4:6].mean()
Rs=np.diag(diagonal);projection=float(np.linalg.norm(R-Rs)/np.linalg.norm(R))
if projection>.001 or min(diagonal)<=0:raise ValueError('symmetry reduction unqualified')
D=np.diag([1,1,1,.5,.5,.5]);Mb=D@np.linalg.inv(Rs)@D
def provider(x,Q):
    if np.linalg.norm(x)>1e-14:raise ValueError('centred model cannot translate')
    B=np.zeros((6,6));B[:3,:3]=Q;B[3:,3:]=Q
    return B@Mb@B.T
rows=[];last=None
for n in cfg['steps']:
    x,Q=step.integrate(np.zeros(3),np.eye(3),[0,0,0,.001,.002,.003],provider,lambda p,R:2.,1000,n)
    difference=None if last is None else float(np.linalg.norm(Q[-1]-last))
    rows.append({'steps':n,'orientation_difference':difference,'centre_drift':float(np.linalg.norm(x[-1]))});last=Q[-1]
    np.savez_compressed(out/f'n{n}.npz',position=x,orientation=Q)
checks={'symmetry':projection<.001,'timestep':rows[-1]['orientation_difference']<1e-5,'no_translation':all(v['centre_drift']==0 for v in rows)}
result={'checks':checks,'passed':all(checks.values()),'projection_error':projection,'rows':rows,'final_orientation':last.tolist(),'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(step.__file__),op,out/'contract.json']},'scope':cfg['scope']}
(out/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
