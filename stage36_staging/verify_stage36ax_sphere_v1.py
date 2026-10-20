"""Bounded two-boundary MFS consistency test; not soil validation."""
import json,hashlib,platform,time
from pathlib import Path
import numpy as np
import scipy
from scipy.linalg import svd
import sharp_stokes_mfs_v3 as m
import sharp_sphere_reference_v1 as q
import confined_sphere_reference_v1 as ref
out=Path(__file__).resolve().parents[1]/'stage36_evaluations/stage36ax_confined_sphere_20260911/verification_01'
out.mkdir(parents=True,exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
files=[Path(__file__),Path(m.__file__),Path(q.__file__),Path(ref.__file__)]
hashes={str(p):sha(p) for p in files}
cfg={'counts_per_boundary':[192,384],'axes':[1,1,1],'cavity_radius':4.,'mu':.1,'speed':1e-4,'inner_source_fraction':.6,'outer_source_radius':4/.6,'oversampling':3,'svd_cutoff':1e-12,'boundary_limit':.001,'balance_limit':1e-5,'force_refinement_limit':.001,'scope':'concentric sphere axial translation; analytical streamfunction comparison'}
(out/'contract.json').write_text(json.dumps(cfg,indent=2))
unit,_,_=q.surface_quadrature(1,40,80)
control,normal,weight=q.surface_quadrature(2,40,80)
rows=[]
for radius in [3.,4.]:
 for n in cfg['counts_per_boundary']:
     start=time.perf_counter()
     inner_axes=np.array([.6,.6,.6])
     sources=np.vstack([m.directions(n)*inner_axes,m.directions(n)*(radius/.6)])
     points=np.vstack([m.directions(3*n),m.directions(3*n)*radius])
     A=m.kernel(points,sources,.1).transpose(0,2,1,3).reshape(18*n,6*n)
     u,s,v=svd(A,full_matrices=False);keep=s>s[0]*1e-12
     target=np.zeros((6*n,3));target[:3*n,0]=1e-4
     lam=(v[keep].T@((u[:,keep].T@target.ravel())/s[keep])).reshape(-1,3)
     state={'sources':sources,'mu':.1};sol={'lambda':lam,'far_velocity':np.zeros(3)}
     errors=[]
     for boundary,expected in [(unit,np.array([1e-4,0,0])),(unit*radius,np.zeros(3))]:
         errors.append(max(float(np.linalg.norm(m.velocity(state,sol,p)-expected,axis=1).max())/1e-4 for p in np.array_split(boundary,16)))
     tr=np.concatenate([m.traction(state,sol,p,nn) for p,nn in zip(np.array_split(control,16),np.array_split(normal,16))])
     force=-lam[:n].sum(axis=0)
     balance=float(np.linalg.norm(weight@tr-force)/np.linalg.norm(force))
     coeff,truth=ref.solve(1,radius,.1,1e-4)
     probes=unit[::8]*(1+radius)/2
     field_error=float(np.max(np.linalg.norm(m.velocity(state,sol,probes)-ref.velocity(probes,coeff),axis=1)))/1e-4
     row={'radius':radius,'exact_force':truth,'force_error':float(np.linalg.norm(force-[truth,0,0])/abs(truth)),'field_error':field_error,'n':n,'particle_boundary_error':errors[0],'wall_boundary_error':errors[1],'force':force.tolist(),'stress_force_balance':balance,'condition':float(s[0]/s[-1]),'elapsed_seconds':time.perf_counter()-start}
     rows.append(row);print(json.dumps(row),flush=True)
     np.savez_compressed(out/f'r{radius}_n{n}.npz',sources=sources,points=points,lambda_=lam)
shift=float(np.linalg.norm(np.array(rows[-1]['force'])-rows[-2]['force'])/np.linalg.norm(rows[-1]['force']))
checks={'exact_force':all(r['force_error']<.001 for r in rows if r['n']==384),'exact_field':all(r['field_error']<.001 for r in rows if r['n']==384),'particle_boundary':rows[-1]['particle_boundary_error']<.001,'wall_boundary':rows[-1]['wall_boundary_error']<.001,'balance':all(r['stress_force_balance']<1e-5 for r in rows),'force_refinement':shift<.001,'opposes_motion':all(r['force'][0]<0 for r in rows),'inputs_unchanged':all(sha(p)==h for p,h in hashes.items())}
result={'rows':rows,'checks':checks,'passed':all(checks.values()),'force_refinement_error':shift,'hashes':hashes,'contract_hash':sha(out/'contract.json'),'artifacts':{p.name:sha(p) for p in out.glob('*.npz')},'python':platform.python_version(),'scipy':scipy.__version__,'production_promoted':False}
(out/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(checks),flush=True)
