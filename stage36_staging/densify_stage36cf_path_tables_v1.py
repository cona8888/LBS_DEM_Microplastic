"""Densify failed Stage36CD tables using Stage36CE direct midpoint evidence."""
import hashlib, json, time
from pathlib import Path
import numpy as np
import open_grains_ellipsoid_v1 as flow

R=Path(__file__).resolve().parents[1]
T=R/'stage36_evaluations/stage36cd_path_tables_20260911/table_01'
V=R/'stage36_evaluations/stage36ce_fresh_path_validation_20260911/run_01'
O=R/'stage36_evaluations/stage36cf_dense_path_tables_20260911/table_02';O.mkdir(parents=True,exist_ok=False)
nodes=[round(-4.2+.7*i,10) for i in range(13)]
contract={'role':'adaptive densification after preserved failed fresh-pose audit','training_x':nodes,
 'reused_direct_x':[-2.1,.7,3.5],'new_direct_x':[-3.5,-.7,2.1],
 'source_rule':'384 for |x|<=1.4; 256 otherwise','boundary_limit':.001,'force_free_limit':1e-10,
 'trajectory_release_qualified':False}
(O/'contract.json').write_text(json.dumps(contract,indent=2))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();inputs=[Path(__file__),Path(flow.__file__),T/'results.json',V/'results.json',O/'contract.json']
before={str(p):sha(p) for p in inputs};assert json.loads((T/'results.json').read_text())['passed_provisional'];assert not json.loads((V/'results.json').read_text())['passed']
rows=[];start=time.perf_counter()
for case in range(1,13):
 old=json.loads((T/f'case_{case:02}.json').read_text());val=json.loads((V/f'case_{case:02}.json').read_text())
 pool={round(s['x'],10):{**s,'source':'stage36cd'} for s in old['samples']}
 for s in val['validation']:
  pool[round(s['x'],10)]={'x':s['x'],'y':s['y'],'theta':s['theta'],'n':s['n'],'motion':s['direct'],
   'force_free_residual':s['force_free_residual'],'condition':s['condition'],'grain_boundary_error':s['grain_boundary_error'],
   'fibre_boundary_error':s['fibre_boundary_error'],'seconds':s['seconds'],'source':'stage36ce_direct'}
 hist=val['trajectories']['0.05']['history'];hx=np.array([s['x'] for s in hist]);hy=np.array([s['y'] for s in hist]);ht=np.unwrap(np.array([s['theta'] for s in hist]))
 for x in contract['new_direct_x']:
  y=float(np.interp(x,hx,hy));theta=float(np.interp(x,hx,ht));c,s=np.cos(theta),np.sin(theta);M=np.array([[c,-s,0],[s,c,0],[0,0,1.]])
  n=384 if abs(x)<=1.4 else 256;tick=time.perf_counter();z,h=flow.solve([x,y,0],M,n,axes=old['axes'])
  pool[round(x,10)]={'x':x,'y':y,'theta':theta,'n':n,'motion':[float(z[0]),float(z[1]),float(z[5])],**h,
   'seconds':time.perf_counter()-tick,'source':'stage36cf_direct'}
  print(json.dumps({'case':case,'x':x,'n':n}),flush=True)
 samples=[pool[x] for x in nodes]
 health=all(max(s['grain_boundary_error'],s['fibre_boundary_error'])<=.001 and s['force_free_residual']<=1e-10 for s in samples)
 row={k:old[k] for k in ['case','shape','initial_y','initial_angle','axes']};row.update({'samples':samples,'passed_health':health})
 rows.append(row);(O/f'case_{case:02}.json').write_text(json.dumps(row,indent=2))
checks={'all_13_nodes':all(len(r['samples'])==13 for r in rows),'sample_health':all(r['passed_health'] for r in rows),'inputs_unchanged':before=={str(p):sha(p) for p in inputs}}
result={'passed_provisional':all(checks.values()),'checks':checks,'rows':rows,'runtime_seconds':time.perf_counter()-start,'input_hashes':before,'trajectory_release_qualified':False}
(O/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps({'checks':checks,'seconds':result['runtime_seconds']}),flush=True)
