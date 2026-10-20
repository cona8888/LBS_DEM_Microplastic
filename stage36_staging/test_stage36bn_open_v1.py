import json,hashlib
from pathlib import Path
import numpy as np
import open_grain_fibre_v1 as m
out=Path(__file__).resolve().parents[1]/'stage36_evaluations/stage36bn_open_fibre_20260911/verification_01';out.mkdir(parents=True,exist_ok=False)
cfg={'counts':[96,192,384],'centre':[-3,2,0],'axes':[.2,.1,.1],'boundary_limit':.001,'velocity_shift_limit':.001,'scope':'finite force-free body in open flow, no contacts'}
(out/'contract.json').write_text(json.dumps(cfg,indent=2));rows=[]
for n in cfg['counts']:
    z,h=m.solve([-3,2,0],np.eye(3),n);rows.append({'n':n,'motion':z.tolist(),**h});print(json.dumps(rows[-1]),flush=True)
shift=float(np.linalg.norm(np.array(rows[-1]['motion'])-rows[-2]['motion']))
checks={'boundaries':max(rows[-1]['grain_boundary_error'],rows[-1]['fibre_boundary_error'])<.001,'refinement':shift<.001,'force_free':rows[-1]['force_free_residual']<1e-10}
(out/'results.json').write_text(json.dumps({'rows':rows,'checks':checks,'passed':all(checks.values()),'motion_shift':shift,'source_hash':hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()},indent=2));print(checks)
