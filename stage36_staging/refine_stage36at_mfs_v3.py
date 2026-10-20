"""Bounded, unchanged-method spheroid refinement; no production promotion."""
import json, hashlib, time
from pathlib import Path
import numpy as np
import sharp_stokes_mfs_v3 as m
from verify_stage36as_mfs_v2 import prolate_drag

out=Path(__file__).resolve().parents[1]/'stage36_evaluations/stage36at_sharp_mfs_20260911/refinement_01'
out.mkdir(parents=True,exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
inputs={str(p):sha(p) for p in [Path(__file__),Path(m.__file__)]}
contract={'counts':[768,1024],'axes':[2,1,1],'source_fraction':.6,'boundary_oversampling':3,'force_limit':.001,'independent_boundary_limit':.001,'independent_points':12800,'production_promoted':False}
(out/'contract.json').write_text(json.dumps(contract,indent=2))
x,w=np.polynomial.legendre.leggauss(80)
t=np.arange(160)*2*np.pi/160
p=np.stack(np.broadcast_arrays(2*x[:,None],np.sqrt(1-x[:,None]**2)*np.cos(t),np.sqrt(1-x[:,None]**2)*np.sin(t)),axis=-1).reshape(-1,3)
rows=[]
for n in contract['counts']:
    start=time.perf_counter();s=m.prepare([2,1,1],n,.6,.1);elapsed=time.perf_counter()-start
    for d in [0,1]:
        sol=m.solve(s,np.eye(3)[d]*1e-4)
        slip=max(float(np.max(np.linalg.norm(m.velocity(s,sol,q),axis=1)))/1e-4 for q in np.array_split(p,32))
        target=np.eye(3)[d]*prolate_drag(.1,2,1)[d]*1e-4
        error=float(np.linalg.norm(sol['force']-target)/np.linalg.norm(target))
        row={'count':n,'direction':d,'setup_seconds':elapsed,'force_error':error,'independent_boundary_error':slip,'condition':s['condition'],'passed':error<.001 and slip<.001}
        rows.append(row);print(json.dumps(row),flush=True)
        np.savez_compressed(out/f'n{n}_d{d}.npz',sources=s['sources'],points=s['points'],forces=sol['lambda'])
result={'contract':contract,'rows':rows,'inputs':inputs,'inputs_unchanged':all(sha(p)==h for p,h in inputs.items()),'artifacts':{p.name:sha(p) for p in out.glob('*.npz')},'production_promoted':False}
(out/'results.json').write_text(json.dumps(result,indent=2))
