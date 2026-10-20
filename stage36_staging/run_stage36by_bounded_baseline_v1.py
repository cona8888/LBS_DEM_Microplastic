"""Reproduce the qualified physical centreline case with bounded event handling."""
import json,hashlib
from pathlib import Path
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.integrate import quad
from planar_passage_stepper_v1 import integrate
R=Path(__file__).resolve().parents[1];T=R/'stage36_evaluations/stage36bq_throat_table_20260911/table_04'
O=R/'stage36_evaluations/stage36by_bounded_baseline_20260911/run_01';O.mkdir(parents=True,exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
prior=json.loads((T/'results.json').read_text());assert prior['passed'] and prior['table_hash']==sha(T/'table.npz')
d=np.load(T/'table.npz');p=PchipInterpolator(d['abs_x'],d['axial_speed'],extrapolate=False)
cfg={'axial_steps':[.2,.1,.05],'relative_timing_limit':.0001,'initial_y':0,'initial_angle':0,'outlet':4.}
(O/'contract.json').write_text(json.dumps(cfg,indent=2))
ref=float(2*quad(lambda x:1/float(p(x)),0,4.2,epsabs=1e-10,points=d['abs_x'])[0]);rows=[]
for dx in cfg['axial_steps']:
 r=integrate(lambda x,y,theta:[float(p(abs(x))),0,0],(.2,.1,.1),0,0,dx)
 (O/f'trajectory_dx{dx}.json').write_text(json.dumps(r,indent=2))
 last=r['history'][-1];rows.append({'dx':dx,'status':r['status'],'complete_release_t':last['t'],'relative_error':abs(last['t']-ref)/ref,'final_x':last['x'],'final_fraction':last['released_volume_fraction']})
checks={'all_complete':all(r['status']=='released' for r in rows),'timing':all(r['relative_error']<.0001 for r in rows),'bounded_endpoint':all(r['final_x']<=4.2+1e-13 for r in rows)}
res={'passed':all(checks.values()),'checks':checks,'rows':rows,'quadrature_time':ref,'independent_population_cases':1,
 'input_hashes':{str(p):sha(p) for p in [Path(__file__),R/'stage36_staging/planar_passage_stepper_v1.py',T/'results.json',T/'table.npz']}}
(O/'results.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2))
