"""Fresh tilted-geometry solve versus cached centred covariance prediction."""
import json,hashlib,time
from pathlib import Path
import numpy as np
from scipy.linalg import svd
import sharp_stokes_mfs_v3 as m
import sharp_sphere_reference_v1 as q
root=Path(__file__).resolve().parents[1]
prior=root/'stage36_evaluations/stage36bf_centred_rotation_20260911'
out=root/'stage36_evaluations/stage36bg_tilt_20260911/verification_01';out.mkdir(parents=True,exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
op=prior/'verification_01/operator.npz';meta=json.loads((prior/'verification_01/results.json').read_text())
if not meta['passed'] or sha(op)!=meta['operator_hash']:raise ValueError('unqualified reference')
Q=np.array(json.loads((prior/'rotation_01/results.json').read_text())['final_orientation'])
with np.load(op,allow_pickle=False) as data:R=data['resistance'].copy()
W=np.array([1.,2.,3.])*1e-4
B=np.zeros((6,6));B[:3,:3]=Q;B[3:,3:]=Q
prediction=-(B@R@B.T)@np.r_[np.zeros(3),2*W]
cfg={'pairs':[[768,384],[1024,512]],'orientation':Q.tolist(),'omega':W.tolist(),'source_fraction':.55,'boundary_limit':.001,'load_prediction_limit':.001,'balance_limit':1e-5,'scope':'centred tilted rigid prolate; fresh solve; no trajectories'}
(out/'contract.json').write_text(json.dumps(cfg,indent=2))
hashes={str(p):sha(p) for p in [Path(__file__),Path(m.__file__),Path(q.__file__),op,prior/'rotation_01/results.json']}
unit,_,_=q.surface_quadrature(1,80,160);control,normal,weight=q.surface_quadrature(3,40,80);rows=[]
for n,nw in cfg['pairs']:
    start=time.perf_counter()
    sources=np.vstack([(m.directions(n)*np.sqrt(np.array([4,1,1])-(1-.55**2)))@Q.T,m.directions(nw)*(4/.6)])
    points=np.vstack([(m.directions(3*n)*[2,1,1])@Q.T,m.directions(3*nw)*4])
    A=m.kernel(points,sources,.1).transpose(0,2,1,3).reshape(9*(n+nw),3*(n+nw))
    u,s,v=svd(A,full_matrices=False);keep=s>s[0]*1e-12
    target=np.zeros((3*(n+nw),3));target[:3*n]=np.cross(W,points[:3*n])
    lam=(v[keep].T@((u[:,keep].T@target.ravel())/s[keep])).reshape(-1,3)
    state={'sources':sources,'mu':.1};sol={'lambda':lam,'far_velocity':np.zeros(3)}
    errs=[];scale=2*np.linalg.norm(W)
    for p,inner in [((unit*[2,1,1])@Q.T,True),(unit*4,False)]:
        errs.append(max(float(np.linalg.norm(m.velocity(state,sol,a)-(np.cross(W,a) if inner else 0),axis=1).max())/scale for a in np.array_split(p,32)))
    load=-np.r_[lam[:n].sum(axis=0),np.cross(sources[:n],lam[:n]).sum(axis=0)/2]
    traction=np.concatenate([m.traction(state,sol,p,nn) for p,nn in zip(np.array_split(control,16),np.array_split(normal,16))])
    integrated=np.r_[weight@traction,weight@np.cross(control,traction)/2]
    row={'n':n,'nw':nw,'particle_error':errs[0],'wall_error':errs[1],'prediction_error':float(np.linalg.norm(load-prediction)/np.linalg.norm(prediction)),'balance':float(np.linalg.norm(integrated-load)/np.linalg.norm(load)),'load':load.tolist(),'seconds':time.perf_counter()-start};rows.append(row);print(json.dumps(row),flush=True)
    np.savez_compressed(out/f'n{n}.npz',sources=sources,lambda_=lam)
checks={'boundaries':all(max(r['particle_error'],r['wall_error'])<.001 for r in rows),'covariance':all(r['prediction_error']<.001 for r in rows),'balance':all(r['balance']<1e-5 for r in rows),'hashes':all(sha(p)==h for p,h in hashes.items())}
(out/'results.json').write_text(json.dumps({'rows':rows,'checks':checks,'passed':all(checks.values()),'hashes':hashes,'contract_hash':sha(out/'contract.json'),'artifacts':{p.name:sha(p) for p in out.glob('*.npz')}},indent=2));print(checks)
