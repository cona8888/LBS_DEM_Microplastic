"""Nonuniform-flow manufactured solution for the bounded event integrator."""
import json
from pathlib import Path
import numpy as np
from scipy.optimize import brentq
from planar_passage_stepper_v1 import integrate,support
R=Path(__file__).resolve().parents[1];O=R/'stage36_evaluations/stage36bx_bounded_events_20260911/variable_flow_01';O.mkdir(exist_ok=False)
axes=(.2,.1,.1);spin=.07
def exact_x(t):return .58*np.exp(.1*t)/.1-10
exact=brentq(lambda t:exact_x(t)-support(spin*t,axes)-4,0,20)
rows=[]
for dx in [.8,.4,.2]:
 r=integrate(lambda x,y,theta:[1+.1*x,.03,spin],axes,0,0,dx)
 last=r['history'][-1];rows.append({'dx':dx,'t':last['t'],'time_error':abs(last['t']-exact),'status':r['status']})
checks={'all_release':all(r['status']=='released' for r in rows),'refinement':rows[2]['time_error']<rows[1]['time_error']<rows[0]['time_error'],'fine_error':rows[2]['time_error']<1e-6}
res={'passed':all(checks.values()),'checks':checks,'rows':rows,'analytic_event_time':exact}
(O/'results.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2))
