"""Serialization-corrected finite-body release measurement (new immutable run)."""
import hashlib,json,platform,time
from pathlib import Path
import numpy as np
from scipy.integrate import quad
from scipy.interpolate import PchipInterpolator
ROOT=Path(__file__).resolve().parents[1]
TABLE_RESULT=ROOT/'stage36_evaluations/stage36bq_throat_table_20260911/table_04/results.json'
TABLE_DATA=ROOT/'stage36_evaluations/stage36bq_throat_table_20260911/table_04/table.npz'
FAILED=ROOT/'stage36_evaluations/stage36br_finite_body_release_20260911/release_01/failure.json'
OUT=ROOT/'stage36_evaluations/stage36br_finite_body_release_20260911/release_02'
if OUT.exists():raise FileExistsError(OUT)
OUT.mkdir(parents=True)
cfg={'initial_centre_x':-4.2,'measurement_plane_x':4.0,'complete_centre_x':4.2,
 'body_axes':[.2,.1,.1],'orientation':'major axis parallel to x','lateral_centre':[0,0],
 'grains':[[0,-1.5,0],[0,1.5,0]],'time_steps':[.04,.02,.01],
 'relative_time_agreement_limit':.001,'quadrature_relative_limit':.0001,
 'minimum_surface_clearance_at_throat':.4,
 'scope':'single deterministic finite body on symmetry centreline; pre-comparison; not soil-scale release fraction'}
(OUT/'contract.json').write_text(json.dumps(cfg,indent=2))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs=[Path(__file__),TABLE_RESULT,TABLE_DATA,FAILED,OUT/'contract.json'];before={str(p):sha(p) for p in inputs}
tr=json.loads(TABLE_RESULT.read_text())
if not tr['passed'] or tr['table_hash']!=sha(TABLE_DATA):raise ValueError('unqualified table')
if json.loads(FAILED.read_text())['accepted']:raise ValueError('failed predecessor unexpectedly accepted')
d=np.load(TABLE_DATA);p=PchipInterpolator(d['abs_x'],d['axial_speed'])
speed=lambda x:float(p(abs(x)))
def fraction(x):
 s=(cfg['measurement_plane_x']-x)/cfg['body_axes'][0]
 if s>=1:return 0.
 if s<=-1:return 1.
 return float(.5-.75*s+.25*s**3)
targets={'first_release':3.8,'half_release':4.,'complete_release':4.2}
def simulate(dt):
 x=cfg['initial_centre_x'];t=0.;ts=[t];xs=[x];fs=[fraction(x)];events={}
 while x<4.2 and t<100:
  ox=x;ot=t;mid=x+.5*dt*speed(x);x+=dt*speed(mid);t+=dt
  for name,target in targets.items():
   if name not in events and ox<target<=x:events[name]=ot+dt*(target-ox)/(x-ox)
  ts.append(t);xs.append(x);fs.append(fraction(x))
 if x<4.2:raise RuntimeError('passage horizon exceeded')
 return {'dt':dt,'events':events,'steps':len(ts)-1,'final_time':t,'final_centre_x':x},(np.array(ts),np.array(xs),np.array(fs))
start=time.perf_counter();runs=[];hist=None
for dt in cfg['time_steps']:
 r,h=simulate(dt);runs.append(r);hist=h if dt==min(cfg['time_steps']) else hist;print(json.dumps(r),flush=True)
exact={name:float(quad(lambda z:1/speed(z),cfg['initial_centre_x'],target,epsabs=1e-11,epsrel=1e-11,limit=200)[0]) for name,target in targets.items()}
fine,medium=runs[-1],runs[-2]
refine=float(max(abs(fine['events'][k]-medium['events'][k])/exact[k] for k in exact))
qerr=float(max(abs(fine['events'][k]-exact[k])/exact[k] for k in exact))
t,x,f=hist;after={str(p):sha(p) for p in inputs}
checks={'qualified_table':bool(tr['passed'] and tr['table_hash']==sha(TABLE_DATA)),
 'failed_predecessor_preserved':bool(not json.loads(FAILED.read_text())['accepted']),
 'input_hashes_unchanged':bool(before==after),'time_refinement':bool(refine<cfg['relative_time_agreement_limit']),
 'quadrature_agreement':bool(qerr<cfg['quadrature_relative_limit']),
 'release_monotone':bool(np.all(np.diff(f)>=-1e-14)),'initially_retained':bool(f[0]==0.),
 'complete_release':bool(f[-1]==1.),
 'event_order':bool(fine['events']['first_release']<fine['events']['half_release']<fine['events']['complete_release']),
 'positive_clearance':bool(cfg['minimum_surface_clearance_at_throat']>0)}
np.savez_compressed(OUT/'release_history.npz',time=t,centre_x=x,released_volume_fraction=f)
res={'checks':checks,'passed':bool(all(checks.values())),'runs':runs,'quadrature_event_times':exact,
 'relative_time_refinement_error':refine,'relative_quadrature_error':qerr,
 'measured_release_fraction':1.0 if checks['complete_release'] else float(f[-1]),
 'released_bodies':1 if checks['complete_release'] else 0,'total_bodies':1,'censored_contact_bodies':0,
 'interpretation':'verified single-body throat passage; not population retention or soil validation',
 'runtime_seconds':time.perf_counter()-start,'input_hashes':before,
 'history_hash':sha(OUT/'release_history.npz'),'python':platform.python_version(),'production_promoted':False}
(OUT/'results.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2))
