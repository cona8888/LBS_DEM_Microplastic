"""Corrected [z,y,x] -> [x,y,z] zero-size tracer limit."""
import hashlib,json,time
from pathlib import Path
import numpy as np
import matrix_release_transport_v1 as mt
import run_stage36cp_matrix_release_pilot_v1 as engine
import run_stage36cr_matrix_release_pilot_v2 as corrected
R=Path(__file__).resolve().parents[1];P=R/'stage36_runs/stage36cr_matrix_release_pilot_corrected_20260911/pilot_01';O=R/'stage36_evaluations/stage36cs_corrected_tracer_limit_20260911/run_01';O.mkdir(parents=True,exist_ok=False)
contract={'role':'corrected zero-size tracer limit','same_initial_centres':True,'max_displacements_cells':[.4,.2,.1],'horizon_pore_volumes':7.,'gates':{'classification_shift_max':.02,'released_fraction_min':.5,'no_numerical_failure':True,'deterministic_repeat_exact':True}};(O/'contract.json').write_text(json.dumps(contract,indent=2));assert json.loads((P/'results.json').read_text())['passed']
zf=np.load(engine.FIELD);zg=np.load(engine.GEOM);phase=np.asarray(zf['phase']).transpose(2,1,0);u=np.asarray(zf['velocity_xyz_lu'],float).transpose(0,3,2,1);grad=mt.periodic_gradient(u);L=float(phase.shape[0]);dx=float(zg['spacing_m'][0]);gr=mt.PeriodicGrains(np.asarray(zg['sand_centres_m'])/dx,np.asarray(zg['sand_radii_m'])/dx,L);fluid=phase==0;pt=L/float(u[0,fluid].mean());starts=json.loads((P/'initial_ensemble.json').read_text());runs={};started=time.perf_counter()
for md in contract['max_displacements_cells']:
 rows=[]
 for s in starts:
  q=engine.integrate(u,grad,gr,s['position_cells'],s['orientation'],0.,0.,1.,md,pt,7.,L);q['id']=s['id'];rows.append(q)
 runs[str(md)]=rows;(O/f'tracers_dx_{str(md).replace(".","p")}.json').write_text(json.dumps(rows,indent=2));print(json.dumps({'dx':md,'counts':{v:sum(r['status']==v for r in rows) for v in sorted(set(r['status'] for r in rows))}}),flush=True)
fine=runs['0.1'];med=runs['0.2'];states=set(r['status'] for r in fine+med);shift=max(abs(sum(r['status']==s for r in fine)-sum(r['status']==s for r in med))/len(fine) for s in states);rep=engine.integrate(u,grad,gr,starts[0]['position_cells'],starts[0]['orientation'],0.,0.,1.,.1,pt,7.,L);counts={s:sum(r['status']==s for r in fine) for s in sorted(set(r['status'] for r in fine))};checks={'classification_shift':shift<=.02,'released_fraction_min':counts.get('released',0)/len(fine)>=.5,'no_numerical_failure':counts.get('numerical_failure',0)==0,'deterministic_repeat':rep['status']==fine[0]['status'] and rep['time_pv']==fine[0]['time_pv']}
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();inputs=[Path(__file__),Path(mt.__file__),Path(engine.__file__),Path(corrected.__file__),engine.FIELD,engine.GEOM,P/'results.json',P/'initial_ensemble.json',O/'contract.json'];result={'passed':all(checks.values()),'checks':checks,'fine_status_counts':counts,'fine_fractions':{s:n/len(fine) for s,n in counts.items()},'classification_max_shift':shift,'runtime_seconds':time.perf_counter()-started,'input_hashes':{str(p):sha(p) for p in inputs}};(O/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
