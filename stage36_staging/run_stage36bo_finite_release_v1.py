"""Single rigid prolate first-exit pilot; direct open two-body Stokes solves."""
import json,hashlib,time
from pathlib import Path
import numpy as np
import open_grain_fibre_v1 as flow
from rigid_pose_stepper_v1 import exp_rotation
out=Path(__file__).resolve().parents[1]/'stage36_evaluations/stage36bo_finite_release_20260911/run_01';out.mkdir(parents=True,exist_ok=False)
cfg={'steps':[12,24,48],'horizon':14.,'initial_centre':[-3,2,0],'axes':[.2,.1,.1],'inlet':-4.,'outlet':4.,'outlet_type':'absorbing collector only after whole body crosses','boundary_limit':.001,'force_free_limit':1e-10,'exit_time_refinement_limit':.02,'clearance_margin':.05,'source_counts':[192,384],'scope':'one rigid prolate, one fixed grain, force-free Stokes flow, no contact or adhesion; not packed soil','initial_tagged_mass':1.,'mass_units':'normalized tagged body mass; uniform density'}
(out/'contract.json').write_text(json.dumps(cfg,indent=2))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
hashes={str(p):sha(p) for p in [Path(__file__),Path(flow.__file__)]}
def support(Q):return float(np.linalg.norm(Q[0]*flow.AXES))
def portion(x,Q):
    s=np.clip((4-x[0])/support(Q),-1,1)
    return float(1-(.5+.75*s-.25*s**3))
def solve(x,Q):
    for n in [192,384]:
        z,h=flow.solve(x,Q,n)
        if max(h['grain_boundary_error'],h['fibre_boundary_error'])<.001 and h['force_free_residual']<1e-10:return z,{**h,'n':n}
    raise ValueError('spatial health gate failed at pose')
summary=[]
for steps in cfg['steps']:
    start=time.perf_counter();dt=14/steps;x=np.array([-3.,2,0]);Q=np.eye(3);rows=[{'t':0.,'downstream':0.,'inside':1.}];xs=[x.copy()];Qs=[Q.copy()];health=[];exit_time=None
    for i in range(steps):
        z,h=solve(x,Q);health.append(h)
        mid=x+dt/2*z[:3];midQ=exp_rotation(dt/2*z[3:])@Q
        zm,hm=solve(mid,midQ);health.append(hm)
        new=x+dt*zm[:3];newQ=exp_rotation(dt*zm[3:])@Q
        if np.linalg.norm(new)<=1+max(flow.AXES)+.05:raise ValueError('clearance failed')
        prev=x[0]-support(Q)-4;now=new[0]-support(newQ)-4
        if prev<0<=now:exit_time=i*dt+dt*(-prev)/(now-prev)
        x,Q=new,newQ;down=portion(x,Q)
        rows.append({'t':(i+1)*dt,'downstream':down,'inside':1-down});xs.append(x.copy());Qs.append(Q.copy())
        if i%4==0:print(json.dumps({'steps':steps,'step':i+1,'x':x[0],'released_mass_fraction':down}),flush=True)
        if exit_time is not None:break
    np.savez_compressed(out/f'path_{steps}.npz',position=xs,orientation=Qs)
    (out/f'trace_{steps}.json').write_text(json.dumps({'rows':rows,'health':health},indent=2))
    summary.append({'steps':steps,'exit_time':exit_time,'released_mass_fraction':rows[-1]['downstream'],'remaining_mass_fraction':rows[-1]['inside'],'runtime_seconds':time.perf_counter()-start,'max_boundary_error':max(max(h['grain_boundary_error'],h['fibre_boundary_error']) for h in health)})
    print(json.dumps(summary[-1]),flush=True)
error=None if any(r['exit_time'] is None for r in summary) else abs(summary[-1]['exit_time']-summary[-2]['exit_time'])
checks={'complete_exit':all(r['exit_time'] is not None for r in summary),'timestep':error is not None and error<.02,'mass_balance':all(abs(r['released_mass_fraction']+r['remaining_mass_fraction']-1)<1e-12 for r in summary),'source_hashes':all(sha(p)==h for p,h in hashes.items())}
(out/'results.json').write_text(json.dumps({'checks':checks,'passed':all(checks.values()),'summary':summary,'exit_refinement_error':error,'hashes':hashes,'artifacts':{p.name:sha(p) for p in out.iterdir() if p.suffix in ['.npz']},'soil_release_validated':False},indent=2));print(checks)
