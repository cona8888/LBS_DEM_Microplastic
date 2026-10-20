"""Bounded two-boundary MFS consistency test; not soil validation."""
import json,hashlib,platform,time
from pathlib import Path
import numpy as np
import scipy
from scipy.linalg import svd
import sharp_stokes_mfs_v3 as m
import sharp_sphere_reference_v1 as q
out=Path(__file__).resolve().parents[1]/'stage36_evaluations/stage36aw_cavity_20260911/verification_01'
out.mkdir(parents=True,exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
files=[Path(__file__),Path(m.__file__),Path(q.__file__)]
hashes={str(p):sha(p) for p in files}
cfg={'source_pairs':[[768,384],[1024,512]],'independent_points_per_boundary':12800,'axes':[2,1,1],'cavity_radius':4.,'mu':.1,'speed':1e-4,'inner_source_fraction':.6,'outer_source_radius':4/.6,'oversampling':3,'svd_cutoff':1e-12,'boundary_limit':.001,'balance_limit':1e-5,'force_refinement_limit':.001,'scope':'concentric rigid prolate body translating instantaneously inside fixed spherical wall; no trajectories or soil geometry'}
(out/'contract.json').write_text(json.dumps(cfg,indent=2))
unit,_,_=q.surface_quadrature(1,80,160)
control,normal,weight=q.surface_quadrature(3,40,80)
rows=[]
for n,nwall in cfg['source_pairs']:
    start=time.perf_counter()
    inner_axes=np.sqrt(np.array([4.,1.,1.])-.64)
    sources=np.vstack([m.directions(n)*inner_axes,m.directions(nwall)*(4/.6)])
    points=np.vstack([m.directions(3*n)*[2,1,1],m.directions(3*nwall)*4])
    A=m.kernel(points,sources,.1).transpose(0,2,1,3).reshape(9*(n+nwall),3*(n+nwall))
    u,s,v=svd(A,full_matrices=False);keep=s>s[0]*1e-12
    target=np.zeros((3*(n+nwall),3));target[:3*n,0]=1e-4
    lam=(v[keep].T@((u[:,keep].T@target.ravel())/s[keep])).reshape(-1,3)
    state={'sources':sources,'mu':.1};sol={'lambda':lam,'far_velocity':np.zeros(3)}
    errors=[]
    for boundary,expected in [(unit*[2,1,1],np.array([1e-4,0,0])),(unit*4,np.zeros(3))]:
        errors.append(max(float(np.linalg.norm(m.velocity(state,sol,p)-expected,axis=1).max())/1e-4 for p in np.array_split(boundary,32)))
    tr=np.concatenate([m.traction(state,sol,p,nn) for p,nn in zip(np.array_split(control,16),np.array_split(normal,16))])
    force=-lam[:n].sum(axis=0)
    balance=float(np.linalg.norm(weight@tr-force)/np.linalg.norm(force))
    row={'n':n,'wall_sources':nwall,'particle_boundary_error':errors[0],'wall_boundary_error':errors[1],'force':force.tolist(),'stress_force_balance':balance,'condition':float(s[0]/s[-1]),'elapsed_seconds':time.perf_counter()-start}
    rows.append(row);print(json.dumps(row),flush=True)
    np.savez_compressed(out/f'n{n}.npz',sources=sources,points=points,lambda_=lam)
shift=float(np.linalg.norm(np.array(rows[-1]['force'])-rows[-2]['force'])/np.linalg.norm(rows[-1]['force']))
checks={'particle_boundary':rows[-1]['particle_boundary_error']<.001,'wall_boundary':rows[-1]['wall_boundary_error']<.001,'balance':all(r['stress_force_balance']<1e-5 for r in rows),'force_refinement':shift<.001,'opposes_motion':all(r['force'][0]<0 for r in rows),'inputs_unchanged':all(sha(p)==h for p,h in hashes.items())}
result={'rows':rows,'checks':checks,'passed':all(checks.values()),'force_refinement_error':shift,'hashes':hashes,'contract_hash':sha(out/'contract.json'),'artifacts':{p.name:sha(p) for p in out.glob('*.npz')},'python':platform.python_version(),'scipy':scipy.__version__,'production_promoted':False}
(out/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(checks),flush=True)
