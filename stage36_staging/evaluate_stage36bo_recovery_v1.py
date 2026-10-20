"""Recover derived summary from immutable completed paths after reporting failure."""
import json,hashlib
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[1]/'stage36_evaluations/stage36bo_finite_release_20260911';raw=root/'run_01';out=root/'evaluation_01';out.mkdir(exist_ok=False)
rows=[];checks={}
for n in [12,24,48]:
    with np.load(raw/f'path_{n}.npz',allow_pickle=False) as d:x=d['position'];Q=d['orientation']
    trace=json.loads((raw/f'trace_{n}.json').read_text());t=np.array([a['t'] for a in trace['rows']]);health=trace['health']
    h=np.linalg.norm(Q[:,0,:]*[.2,.1,.1],axis=1);f=x[:,0]-h-4
    j=np.flatnonzero(f>=0)[0];exit_time=float(t[j-1]+(t[j]-t[j-1])*(-f[j-1])/(f[j]-f[j-1]))
    rows.append({'steps':n,'exit_time':exit_time,'released_mass_fraction':float(trace['rows'][-1]['downstream']),'remaining_mass_fraction':float(trace['rows'][-1]['inside']),'max_boundary_error':max(max(a['grain_boundary_error'],a['fibre_boundary_error']) for a in health)})
    checks[f'health_{n}']=bool(all(max(a['grain_boundary_error'],a['fibre_boundary_error'])<.001 and a['force_free_residual']<1e-10 for a in health))
error=abs(rows[-1]['exit_time']-rows[-2]['exit_time']);checks['timestep']=error<.02;checks['mass_balance']=all(abs(a['released_mass_fraction']+a['remaining_mass_fraction']-1)<1e-12 for a in rows)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result={'checks':checks,'passed':all(checks.values()),'summary':rows,'exit_refinement_error':error,'artifacts':{p.name:sha(p) for p in raw.iterdir() if p.suffix in ['.npz','.json']},'reporting_failure':'Raw runner completed all paths but failed final JSON serialization; this independent evaluator reconstructs exit times from saved poses. No original report was overwritten.','soil_release_validated':False}
(out/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result['summary']));print(checks)
