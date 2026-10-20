"""Manufactured variable-mobility ODE, not a pore-flow model."""
import json,hashlib
from pathlib import Path
import numpy as np
import translation_stepper_v1 as m
root=Path(__file__).resolve().parents[1];out=root/'stage36_evaluations/stage36bb_stepper_20260911/verification_01'
out.mkdir(parents=True,exist_ok=False)
cfg={'steps':[20,40,80],'duration':1.,'force':[1,0,0],'initial_position':[0,0,0],'manufactured_mobility':'diag(1+x,1,1)','exact_endpoint':'[exp(1)-1,0,0]','minimum_error_ratio':3.7,'fine_error_limit':.0001,'scope':'translation integrator verification only; no physical cavity mobility'}
(out/'contract.json').write_text(json.dumps(cfg,indent=2))
rows=[]
for n in cfg['steps']:
    calls=[]
    def provider(x):calls.append(x.copy());return np.diag([1+x[0],1,1])
    path=m.integrate([0,0,0],[1,0,0],provider,lambda x:10-np.linalg.norm(x),duration=1,steps=n)
    err=float(np.linalg.norm(path[-1]-[np.e-1,0,0]));rows.append({'steps':n,'endpoint_error':err,'provider_calls':len(calls)})
    np.savez_compressed(out/f'n{n}.npz',path=path,evaluation_positions=np.array(calls))
checks={'second_order':all(rows[i]['endpoint_error']/rows[i+1]['endpoint_error']>3.7 for i in [0,1]),'fine_accuracy':rows[-1]['endpoint_error']<.0001,'updates_each_stage':all(r['provider_calls']==2*r['steps'] for r in rows)}
for name,provider,gap in [('clearance',lambda x:np.eye(3),lambda x:.01-x[0]),('negative_mobility',lambda x:-np.eye(3),lambda x:1),('nonfinite_mobility',lambda x:np.eye(3)*np.nan,lambda x:1)]:
    try:m.integrate([0,0,0],[1,0,0],provider,gap,duration=1,steps=2);checks['reject_'+name]=False
    except ValueError:checks['reject_'+name]=True
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(out/'results.json').write_text(json.dumps({'checks':checks,'passed':all(checks.values()),'rows':rows,'hashes':{str(p):sha(p) for p in [Path(__file__),Path(m.__file__),out/'contract.json']},'artifacts':{p.name:sha(p) for p in out.glob('*.npz')},'physical_trajectory':False},indent=2))
print(json.dumps({'rows':rows,'checks':checks},indent=2))
