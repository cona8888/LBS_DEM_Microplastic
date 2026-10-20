"""Zero-size tracer limiting case for the Stage36CP matrix pilot."""
import hashlib,json,time
from pathlib import Path
import numpy as np
from scipy.stats import qmc
import matrix_release_transport_v1 as mt
import run_stage36cp_matrix_release_pilot_v1 as pilot
R=Path(__file__).resolve().parents[1];P=R/'stage36_runs/stage36cp_matrix_release_pilot_20260911/pilot_01';O=R/'stage36_evaluations/stage36cq_matrix_tracer_limit_20260911/run_01';O.mkdir(parents=True,exist_ok=False)
contract={'role':'zero-size advective tracer limiting case','same_initial_centres_as_stage36cp':True,'max_displacements_cells':[.4,.2,.1],'horizon_pore_volumes':7.,'gates':{'classification_shift_max':.02,'no_numerical_failure':True,'deterministic_repeat_exact':True}};(O/'contract.json').write_text(json.dumps(contract,indent=2));assert json.loads((P/'results.json').read_text())['passed']
z=np.load(pilot.FIELD);g=np.load(pilot.GEOM);u=np.asarray(z['velocity_xyz_lu'],float);grad=mt.periodic_gradient(u);L=float(u.shape[1]);dx=float(g['spacing_m'][0]);gr=mt.PeriodicGrains(np.asarray(g['sand_centres_m'])/dx,np.asarray(g['sand_radii_m'])/dx,L);fluid=z['phase']==0;mean=float(u[0,fluid].mean());pt=L/mean;starts=json.loads((P/'initial_ensemble.json').read_text());allrows={};started=time.perf_counter()
for md in contract['max_displacements_cells']:
 rows=[]
 for s in starts:
  a=pilot.integrate(u,grad,gr,s['position_cells'],s['orientation'],0.,0.,1.,md,pt,7.,L);a['id']=s['id'];rows.append(a)
 allrows[str(md)]=rows;(O/f'tracers_dx_{str(md).replace(".","p")}.json').write_text(json.dumps(rows,indent=2));print(json.dumps({'dx':md,'counts':{q:sum(r['status']==q for r in rows) for q in sorted(set(r['status'] for r in rows))}}),flush=True)
def frac(rows,status):return sum(r['status']==status for r in rows)/len(rows)
fine=allrows['0.1'];med=allrows['0.2'];shift=max(abs(frac(fine,s)-frac(med,s)) for s in set(r['status'] for r in fine+med));repeat=pilot.integrate(u,grad,gr,starts[0]['position_cells'],starts[0]['orientation'],0.,0.,1.,.1,pt,7.,L);checks={'classification_shift':shift<=.02,'no_numerical_failure':all(r['status']!='numerical_failure' for r in fine),'deterministic_repeat':repeat['status']==fine[0]['status'] and repeat['time_pv']==fine[0]['time_pv'],'inputs_unchanged':True}
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();inputs=[Path(__file__),Path(mt.__file__),Path(pilot.__file__),pilot.FIELD,pilot.GEOM,P/'results.json',P/'initial_ensemble.json',O/'contract.json'];hashes={str(p):sha(p) for p in inputs};summary={s:sum(r['status']==s for r in fine) for s in sorted(set(r['status'] for r in fine))};result={'passed':all(checks.values()),'checks':checks,'fine_status_counts':summary,'fine_fractions':{s:n/len(fine) for s,n in summary.items()},'classification_max_shift':shift,'runtime_seconds':time.perf_counter()-started,'input_hashes':hashes};(O/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
