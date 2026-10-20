"""Off-centre six-DOF cavity resistance and inverse consistency."""
import json,hashlib,time,platform
import sys
angle=int(sys.argv[1])
if angle not in [29,31]:raise ValueError('only frozen endpoint angles')
from pathlib import Path
import numpy as np
import scipy
from scipy.linalg import svd
import sharp_stokes_mfs_v3 as m
import sharp_sphere_reference_v1 as q
out=Path(__file__).resolve().parents[1]/f'stage36_evaluations/stage36bj_orientation_table_20260911/angle_{angle}'
out.mkdir(parents=True,exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
hashes={str(p):sha(p) for p in [Path(__file__),Path(m.__file__),Path(q.__file__)]}
cfg={'inner_sources':768,'wall_sources':384,'source_fraction':.55,'wall_source_radius':4/.6,'centre':[0,.4,0],'axes':[2,1,1],'cavity_radius':4,'mu':.1,'speed':1e-4,'length_scale':2,'boundary_limit':.001,'reciprocity_limit':.001,'balance_limit':1e-5,'inverse_limit':1e-10,'svd_cutoff':1e-12,'orientation_degrees_z':angle,'scope':'tilted off-centre instantaneous resistance; no trajectories'}
(out/'contract.json').write_text(json.dumps(cfg,indent=2))
theta=np.deg2rad(angle)
Q=np.array([[np.cos(theta),-np.sin(theta),0],[np.sin(theta),np.cos(theta),0],[0,0,1.]])
n=768;nw=384;c=np.array(cfg['centre']);start=time.perf_counter()
sources=np.vstack([c+(m.directions(n)*np.sqrt(np.array([4,1,1])-(1-.55**2)))@Q.T,m.directions(nw)*(4/.6)])
points=np.vstack([c+(m.directions(3*n)*[2,1,1])@Q.T,m.directions(3*nw)*4])
A=m.kernel(points,sources,.1).transpose(0,2,1,3).reshape(9*(n+nw),3*(n+nw))
u,s,v=svd(A,full_matrices=False);keep=s>s[0]*1e-12
setup=time.perf_counter()-start
unit,_,_=q.surface_quadrature(1,80,160)
control,normal,weight=q.surface_quadrature(3,40,80)
state={'sources':sources,'mu':.1};rows=[];columns=[];strengths=[]
for d in range(6):
    V=np.eye(3)[d]*1e-4 if d<3 else np.zeros(3)
    W=np.eye(3)[d-3]*5e-5 if d>=3 else np.zeros(3)
    target=np.zeros((3*(n+nw),3));target[:3*n]=V+np.cross(W,points[:3*n]-c)
    lam=(v[keep].T@((u[:,keep].T@target.ravel())/s[keep])).reshape(-1,3)
    sol={'lambda':lam,'far_velocity':np.zeros(3)};errors=[]
    for boundary,inner in [(c+(unit*[2,1,1])@Q.T,True),(unit*4,False)]:
        errors.append(max(float(np.linalg.norm(m.velocity(state,sol,p)-(V+np.cross(W,p-c) if inner else 0),axis=1).max())/1e-4 for p in np.array_split(boundary,32)))
    force=-lam[:n].sum(axis=0);torque=-np.cross(sources[:n]-c,lam[:n]).sum(axis=0)
    tr=np.concatenate([m.traction(state,sol,p,nn) for p,nn in zip(np.array_split(control,16),np.array_split(normal,16))])
    load=np.r_[force,torque/2]
    balance=float(np.linalg.norm(np.r_[weight@tr-force,(weight@np.cross(control-c,tr)-torque)/2])/np.linalg.norm(load))
    columns.append(-load/1e-4);strengths.append(lam)
    row={'dof':d,'particle_error':errors[0],'wall_error':errors[1],'balance':balance};rows.append(row);print(json.dumps(row),flush=True)
R=np.column_stack(columns);M=np.linalg.inv(R)
reciprocity=float(np.linalg.norm(R-R.T)/np.linalg.norm(R))
# No symmetrization: test the actual computed operator.
motion=np.array([.2,-.3,.4,.1,.25,-.15])*1e-4
recovered=M@(R@motion);inverse_error=float(np.linalg.norm(recovered-motion)/np.linalg.norm(motion))
checks={'boundary':all(max(r['particle_error'],r['wall_error'])<.001 for r in rows),'balance':all(r['balance']<1e-5 for r in rows),'reciprocity':reciprocity<.001,'positive_dissipation':bool(np.linalg.eigvalsh((R+R.T)/2).min()>0),'inverse':inverse_error<1e-10,'inputs_unchanged':all(sha(p)==h for p,h in hashes.items())}
np.savez_compressed(out/'operator.npz',resistance=R,mobility=M,sources=sources,strengths=np.array(strengths))
result={'checks':checks,'passed':all(checks.values()),'rows':rows,'reciprocity_error':reciprocity,'inverse_error':inverse_error,'setup_seconds':setup,'source_condition':float(s[0]/s[-1]),'resistance_condition':float(np.linalg.cond(R)),'hashes':hashes,'operator_hash':sha(out/'operator.npz'),'contract_hash':sha(out/'contract.json'),'python':platform.python_version(),'scipy':scipy.__version__,'production_promoted':False,'inverse_test_role':'algebraic consistency only, not independent physical validation'}
(out/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(checks),flush=True)
