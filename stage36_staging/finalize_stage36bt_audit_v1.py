"""Finalize saved audit cases after NumPy-bool serialization failure; no rerun."""
import json,hashlib
from pathlib import Path
import numpy as np
from scipy.integrate import quad
R=Path(__file__).resolve().parents[1];O=R/'stage36_evaluations/stage36bt_scientific_review_20260911/audit_01'
dest=O.parent/'audit_02';dest.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
paths=[O/f'case_{i}.json' for i in range(1,7)];rows=[json.loads(p.read_text()) for p in paths]
cap_error=float(max(abs(quad(lambda s:.75*(1-s*s),v,1)[0]-(.5-.75*v+.25*v**3)) for v in np.linspace(-1,1,17)))
T=R/'stage36_evaluations/stage36bq_throat_table_20260911/table_04';d=json.loads((T/'results.json').read_text())
checks={'frozen_table_hash':sha(T/'table.npz')==d['table_hash'],'fresh_speed':all(r['relative_table_speed_error']<.001 for r in rows),'boundary':all(max(r['grain_boundary_error'],r['fibre_boundary_error'])<.001 for r in rows),'force_free':all(r['force_free_residual']<1e-10 for r in rows),'cap_formula':cap_error<1e-12}
res={'passed':all(checks.values()),'checks':checks,'rows':rows,'cap_formula_error':cap_error,'input_hashes':{str(p):sha(p) for p in paths+[Path(__file__),O/'contract.json',T/'results.json']},'prior_failure':'all case solves completed; result serialization failed on NumPy boolean; recovered saved cases without rerunning','external_validation':False}
(dest/'results.json').write_text(json.dumps(res,indent=2));print(json.dumps(checks))
