"""Multi-grain extension regression and throat refinement."""
import json,hashlib
from pathlib import Path
import numpy as np
import open_grain_fibre_v1 as old
import open_grains_fibre_v1 as new
out=Path(__file__).resolve().parents[1]/'stage36_evaluations/stage36bp_throat_20260911/verification_01';out.mkdir(parents=True,exist_ok=False)
cfg={'grains':[[0,-1.5,0],[0,1.5,0]],'pose':[0,0,0],'axes':[.2,.1,.1],'counts':[96,192,384],'boundary_limit':.001,'motion_shift_limit':.001,'scope':'two fixed noncontact grains; no soil validation'}
(out/'contract.json').write_text(json.dumps(cfg,indent=2))
a,_=old.solve([-3,2,0],np.eye(3),96);b,_=new.solve([-3,2,0],np.eye(3),96,grains=[[0,0,0]])
regression=float(np.linalg.norm(a-b));rows=[]
for n in cfg['counts']:
    z,h=new.solve([0,0,0],np.eye(3),n);rows.append({'n':n,'motion':z.tolist(),**h});print(json.dumps(rows[-1]),flush=True)
shift=float(np.linalg.norm(np.array(rows[-1]['motion'])-rows[-2]['motion']))
checks={'single_grain_regression':regression<1e-12,'fine_boundary':max(rows[-1]['grain_boundary_error'],rows[-1]['fibre_boundary_error'])<.001,'motion_refinement':shift<.001,'force_free':rows[-1]['force_free_residual']<1e-10}
(out/'results.json').write_text(json.dumps({'checks':checks,'passed':all(checks.values()),'rows':rows,'motion_shift':shift,'regression_error':regression,'source_hash':hashlib.sha256(Path(new.__file__).read_bytes()).hexdigest()},indent=2));print(checks)
