"""Fresh frozen-table solution audit; no tuning on these audit points."""
import json,hashlib
from pathlib import Path
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.integrate import quad
import open_grains_fibre_v2 as flow
R=Path(__file__).resolve().parents[1]
O=R/'stage36_evaluations/stage36bt_scientific_review_20260911/audit_01'
O.mkdir(parents=True,exist_ok=False)
T=R/'stage36_evaluations/stage36bq_throat_table_20260911/table_04'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cfg={'fresh_positions':[.1875,.9375,1.75,2.25,3.3,-.9375],'sources':384,'relative_speed_limit':.001,'boundary_limit':.001,'scope':'solution verification; no experimental validation'}
(O/'contract.json').write_text(json.dumps(cfg,indent=2))
paths=[Path(__file__),Path(flow.__file__),Path(flow.m.__file__),Path(flow.q.__file__),T/'results.json',T/'table.npz',O/'contract.json']
before={str(p):sha(p) for p in paths}
old=json.loads((T/'results.json').read_text());assert old['passed'] and old['table_hash']==sha(T/'table.npz')
d=np.load(T/'table.npz');p=PchipInterpolator(d['abs_x'],d['axial_speed'],extrapolate=False)
rows=[]
for x in cfg['fresh_positions']:
 z,h=flow.solve([x,0,0],np.eye(3),384)
 row={'x':x,'motion':z.tolist(),**h,'relative_table_speed_error':float(abs(p(abs(x))-z[0])/abs(z[0]))}
 rows.append(row);print(json.dumps(row),flush=True)
 # Save each completed solve once for failure recovery.
 (O/('case_'+str(len(rows))+'.json')).write_text(json.dumps(row,indent=2))
# Independent ellipsoid slice integration verifies the cumulative volume formula.
cap_error=max(abs(quad(lambda s:.75*(1-s*s),v,1)[0]-(.5-.75*v+.25*v**3)) for v in np.linspace(-1,1,17))
checks={'inputs_unchanged':before=={str(p):sha(p) for p in paths},'fresh_speed':all(r['relative_table_speed_error']<.001 for r in rows),'boundary':all(max(r['grain_boundary_error'],r['fibre_boundary_error'])<.001 for r in rows),'force_free':all(r['force_free_residual']<1e-10 for r in rows),'cap_formula':cap_error<1e-12}
res={'passed':all(checks.values()),'checks':checks,'rows':rows,'input_hashes':before,'cap_formula_error':cap_error,'external_validation':'not established'}
(O/'results.json').write_text(json.dumps(res,indent=2));print(json.dumps(checks),flush=True)
