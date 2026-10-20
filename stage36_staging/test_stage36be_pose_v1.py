"""Exact isolated sphere and manufactured orientation-dependent refinement."""
import json,hashlib
from pathlib import Path
import numpy as np
import rigid_pose_stepper_v1 as m
out=Path(__file__).resolve().parents[1]/'stage36_evaluations/stage36be_pose_20260911/verification_01';out.mkdir(parents=True,exist_ok=False)
cfg={'steps':[20,40,80],'duration':1,'refinement_ratio_min':3.5,'orientation_limit':1e-12,'scope':'unbounded sphere analytical motion plus manufactured pose-dependent mobility; no fibre trajectory'}
(out/'contract.json').write_text(json.dumps(cfg,indent=2))
mu=.1;a=1.;M=np.diag([1/(6*np.pi*mu*a)]*3+[1/(8*np.pi*mu*a**3)]*3)
load=np.array([.01,.02,-.01,.03,-.02,.01]);calls=[]
def sphere(p,Q):calls.append(Q.copy());return M
x,Q=m.integrate(np.zeros(3),np.eye(3),load,sphere,lambda p,Q:1,1,20)
z=M@load
checks={'sphere_translation':bool(np.linalg.norm(x[-1]-z[:3])<1e-12),'sphere_rotation':bool(np.linalg.norm(Q[-1]-m.exp_rotation(z[3:]))<1e-12),'stage_updates':len(calls)==40}
def variable(p,Q):
    # Manufactured anisotropic SPD operator rotated into the world frame.
    block=Q@np.diag([1.,2.,3.])@Q.T
    mat=np.zeros((6,6));mat[:3,:3]=block;mat[3:,3:]=block
    return mat
load2=np.array([.1,.2,.3,.3,.2,.1]);rows=[]
for n in [20,40,80,640]:
    xp,qp=m.integrate(np.zeros(3),np.eye(3),load2,variable,lambda p,Q:1,1,n)
    rows.append((n,xp[-1],qp[-1]));np.savez_compressed(out/f'n{n}.npz',position=xp,orientation=qp)
    checks[f'rotation_group_{n}']=bool(np.max(np.linalg.norm(qp.transpose(0,2,1)@qp-np.eye(3),axis=(1,2)))<1e-12 and np.min(np.linalg.det(qp))>0)
errors=[float(np.linalg.norm(p-rows[-1][1])+np.linalg.norm(R-rows[-1][2])) for _,p,R in rows[:-1]]
checks['second_order']=all(errors[i]/errors[i+1]>3.5 for i in [0,1])
for name,R,gap in [('reflection',np.diag([-1,1,1]),lambda p,Q:1),('clearance',np.eye(3),lambda p,Q:-1)]:
    try:m.integrate(np.zeros(3),R,load,sphere,gap,1,2);checks[name]=False
    except ValueError:checks[name]=True
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(out/'results.json').write_text(json.dumps({'checks':checks,'passed':all(checks.values()),'manufactured_errors':errors,'hashes':{str(p):sha(p) for p in [Path(__file__),Path(m.__file__),out/'contract.json']},'artifacts':{p.name:sha(p) for p in out.glob('*.npz')},'soil_motion':False},indent=2));print(json.dumps({'checks':checks,'errors':errors},indent=2))
