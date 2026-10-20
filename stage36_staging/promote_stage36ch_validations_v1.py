"""Promote all Stage36CG direct audit poses into a new provisional table."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
T=R/'stage36_evaluations/stage36cf_dense_path_tables_20260911/table_02';V=R/'stage36_evaluations/stage36cg_dense_path_validation_20260911/run_01'
O=R/'stage36_evaluations/stage36ch_refined_path_tables_20260911/table_03';O.mkdir(parents=True,exist_ok=False)
contract={'role':'second adaptive densification after preserved Stage36CG angular failures','promoted_direct_x':[-3.85,-1.75,.35,2.45],
 'gates_unchanged':True,'trajectory_release_qualified':False}
(O/'contract.json').write_text(json.dumps(contract,indent=2));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs=[Path(__file__),T/'results.json',V/'results.json',O/'contract.json'];before={str(p):sha(p) for p in inputs};assert json.loads((T/'results.json').read_text())['passed_provisional'];assert not json.loads((V/'results.json').read_text())['passed']
rows=[]
for case in range(1,13):
 old=json.loads((T/f'case_{case:02}.json').read_text());val=json.loads((V/f'case_{case:02}.json').read_text());pool={round(s['x'],10):{**s} for s in old['samples']}
 for s in val['validation']:
  pool[round(s['x'],10)]={'x':s['x'],'y':s['y'],'theta':s['theta'],'n':s['n'],'motion':s['direct'],'force_free_residual':s['force_free_residual'],
   'condition':s['condition'],'grain_boundary_error':s['grain_boundary_error'],'fibre_boundary_error':s['fibre_boundary_error'],'seconds':s['seconds'],'source':'stage36cg_direct'}
 samples=[pool[x] for x in sorted(pool)];health=all(max(s['grain_boundary_error'],s['fibre_boundary_error'])<=.001 and s['force_free_residual']<=1e-10 for s in samples)
 row={k:old[k] for k in ['case','shape','initial_y','initial_angle','axes']};row.update({'samples':samples,'passed_health':health});rows.append(row);(O/f'case_{case:02}.json').write_text(json.dumps(row,indent=2))
checks={'all_17_nodes':all(len(r['samples'])==17 for r in rows),'sample_health':all(r['passed_health'] for r in rows),'inputs_unchanged':before=={str(p):sha(p) for p in inputs}}
result={'passed_provisional':all(checks.values()),'checks':checks,'rows':rows,'input_hashes':before,'trajectory_release_qualified':False};(O/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result['checks']))
