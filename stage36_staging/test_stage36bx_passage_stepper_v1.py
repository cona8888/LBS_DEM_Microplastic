"""Independent manufactured-solution tests of bounded finite-body events."""
import json,hashlib
from pathlib import Path
import numpy as np
from scipy.optimize import brentq
from planar_passage_stepper_v1 import integrate,support
R=Path(__file__).resolve().parents[1];O=R/'stage36_evaluations/stage36bx_bounded_events_20260911/test_01';O.mkdir(parents=True,exist_ok=False)
axes=(.2,.1,.1);rows=[]
for spin in [0.,.17]:
    # Uniform Ux=1, Uy=.03, omega=spin admits exact t=x+4.2 and theta=spin*t.
    exact=brentq(lambda t:-4.2+t-support(spin*t,axes)-4,8.,8.5)
    for dx in [.8,.4,.2]:
        queries=[]
        def provider(x,y,theta):queries.append(x);return [1.,.03,spin]
        r=integrate(provider,axes,0.,0.,dx);last=r['history'][-1]
        row={'spin':spin,'dx':dx,'status':r['status'],'time_error':abs(last['t']-exact),
             'y_error':abs(last['y']-.03*exact),'max_query_x':max(queries),'final_fraction':last['released_volume_fraction']}
        rows.append(row)
limited=integrate(lambda *args:[1.,0.,0.],axes,0.,0.,.4,horizon=2.)
invalid_rejected=False
try:integrate(lambda *args:[-1.,0.,0.],axes,0.,0.,.4)
except ValueError:invalid_rejected=True
checks={'exact_translating_rotating_events':all(v['status']=='released' and v['time_error']<1e-9 and v['y_error']<1e-9 for v in rows),
 'no_extrapolation':all(v['max_query_x']<=4.2+1e-13 for v in rows),
 'horizon':limited['status']=='horizon' and abs(limited['history'][-1]['t']-2)<1e-10,
 'nonpositive_flow_rejected':invalid_rejected}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
res={'passed':all(checks.values()),'checks':checks,'rows':rows,'input_hashes':{str(p):sha(p) for p in [Path(__file__),R/'stage36_staging/planar_passage_stepper_v1.py']}}
(O/'results.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2))
