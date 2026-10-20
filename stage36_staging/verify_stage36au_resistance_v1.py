"""Six-DOF isolated spheroid consistency tests, not experimental validation."""
import hashlib,json,time,platform
from pathlib import Path
import numpy as np
import scipy
import sharp_stokes_mfs_v3 as m
import sharp_sphere_reference_v1 as q
out=Path(__file__).resolve().parents[1]/'stage36_evaluations/stage36au_resistance_20260911/verification_01'
out.mkdir(parents=True,exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
files=[Path(__file__),Path(m.__file__),Path(q.__file__)]
hashes={str(p):sha(p) for p in files}
cfg={'counts':[768,1024],'axes':[2,1,1],'source_fraction':.6,'mu':.1,'speed_scale':1e-4,'length_scale':2.,'boundary_limit':.001,'reciprocity_limit':.001,'balance_limit':1e-5,'resistance_refinement_limit':.001,'scope':'isolated unbounded steady Stokes; no independent analytical spheroid torque comparison'}
(out/'contract.json').write_text(json.dumps(cfg,indent=2))
surface,_,_=q.surface_quadrature(1,80,160)
boundary=surface*np.array([2,1,1])
control,normals,weights=q.surface_quadrature(3,40,80)
rows=[];matrices=[]
for n in cfg['counts']:
    start=time.perf_counter();s=m.prepare([2,1,1],n,.6,.1);setup=time.perf_counter()-start
    columns=[]
    for d in range(6):
        v=np.eye(3)[d]*1e-4 if d<3 else np.zeros(3)
        w=np.eye(3)[d-3]*1e-4/2 if d>=3 else np.zeros(3)
        sol=m.solve(s,body_velocity=v,omega=w)
        slip=max(float(np.max(np.linalg.norm(m.velocity(s,sol,p)-v-np.cross(w,p),axis=1)))/1e-4 for p in np.array_split(boundary,32))
        tr=np.concatenate([m.traction(s,sol,p,nn) for p,nn in zip(np.array_split(control,16),np.array_split(normals,16))])
        f=weights@tr;t=weights@np.cross(control,tr)
        load=np.r_[sol['force'],sol['torque']/2]
        balance=float(np.linalg.norm(np.r_[f-sol['force'],(t-sol['torque'])/2])/np.linalg.norm(load))
        columns.append(-load/1e-4)
        row={'count':n,'dof':d,'boundary_error':slip,'control_surface_balance':balance,'setup_seconds':setup}
        rows.append(row);print(json.dumps(row),flush=True)
        np.savez_compressed(out/f'n{n}_d{d}.npz',sources=s['sources'],lambda_=sol['lambda'])
    R=np.column_stack(columns);matrices.append(R)
    np.save(out/f'resistance_n{n}.npy',R)
fine=matrices[-1]
reciprocity=float(np.linalg.norm(fine-fine.T)/np.linalg.norm(fine))
refinement=float(np.linalg.norm(fine-matrices[0])/np.linalg.norm(fine))
checks={'boundary':all(r['boundary_error']<.001 for r in rows),'balance':all(r['control_surface_balance']<1e-5 for r in rows),'reciprocity':reciprocity<.001,'positive_dissipation':bool(np.linalg.eigvalsh((fine+fine.T)/2).min()>0),'refinement':refinement<.001,'inputs_unchanged':all(sha(p)==h for p,h in hashes.items())}
result={'checks':checks,'passed':all(checks.values()),'rows':rows,'reciprocity_error':reciprocity,'resistance_refinement_error':refinement,'input_hashes':hashes,'contract_sha256':sha(out/'contract.json'),'python':platform.python_version(),'scipy':scipy.__version__,'artifacts':{p.name:sha(p) for p in out.iterdir() if p.suffix in ['.npz','.npy']},'production_promoted':False}
(out/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(checks),flush=True)
