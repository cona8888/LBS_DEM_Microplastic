"""Independent second-quarter-point qualification of refined path tables."""
import hashlib,json,time
from pathlib import Path
import numpy as np
from scipy.interpolate import PchipInterpolator
import open_grains_ellipsoid_v1 as flow
import planar_passage_stepper_v1 as stepper
R=Path(__file__).resolve().parents[1];T=R/'stage36_evaluations/stage36ch_refined_path_tables_20260911/table_03';O=R/'stage36_evaluations/stage36ci_refined_path_validation_20260911/run_01';O.mkdir(parents=True,exist_ok=False)
fresh_x=[-3.675,-1.575,.175,2.275];gates={'axial_relative_error_max':.01,'transverse_absolute_error_max':.002,'angular_absolute_error_max':.003,'boundary_error_max':.001,'force_free_residual_max':1e-10,'fine_vs_medium_event_time_relative_max':.002}
contract={'role':'fresh second-quarter-point qualification','validation_x':fresh_x,'integration_dx':[.2,.1,.05],'gates':gates,'gates_unchanged':True,'interpretation':'bounded benchmark qualification only'};(O/'contract.json').write_text(json.dumps(contract,indent=2))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();inputs=[Path(__file__),Path(flow.__file__),Path(stepper.__file__),T/'results.json',O/'contract.json'];before={str(p):sha(p) for p in inputs};assert json.loads((T/'results.json').read_text())['passed_provisional'];rows=[];start=time.perf_counter()
for case in range(1,13):
 src=json.loads((T/f'case_{case:02}.json').read_text());x=np.array([s['x'] for s in src['samples']]);m=np.array([s['motion'] for s in src['samples']]);fits=[PchipInterpolator(x,m[:,j],extrapolate=False) for j in range(3)]
 def provider(q,y,theta):return np.array([f(q) for f in fits],float)
 traj={str(dx):stepper.integrate(provider,src['axes'],src['initial_y'],np.deg2rad(src['initial_angle']),dx) for dx in contract['integration_dx']};fine=traj['0.05']['history'];hx=np.array([s['x'] for s in fine]);hy=np.array([s['y'] for s in fine]);ht=np.unwrap(np.array([s['theta'] for s in fine]));validation=[]
 for q in fresh_x:
  y=float(np.interp(q,hx,hy));theta=float(np.interp(q,hx,ht));c,s=np.cos(theta),np.sin(theta);M=np.array([[c,-s,0],[s,c,0],[0,0,1.]])
  n=384 if abs(q)<=1.4 else 256;tick=time.perf_counter();z,h=flow.solve([q,y,0],M,n,axes=src['axes']);p=provider(q,y,theta);e={'axial_relative':float(abs(p[0]-z[0])/abs(z[0])),'transverse_absolute':float(abs(p[1]-z[1])),'angular_absolute':float(abs(p[2]-z[5]))}
  passed=e['axial_relative']<=.01 and e['transverse_absolute']<=.002 and e['angular_absolute']<=.003 and max(h['grain_boundary_error'],h['fibre_boundary_error'])<=.001 and h['force_free_residual']<=1e-10
  item={'x':q,'y':y,'theta':theta,'n':n,'predicted':p.tolist(),'direct':[float(z[0]),float(z[1]),float(z[5])],'errors':e,**h,'passed':bool(passed),'seconds':time.perf_counter()-tick};validation.append(item);print(json.dumps({'case':case,'x':q,'passed':bool(passed),'errors':e}),flush=True)
 times={k:v['history'][-1]['t'] for k,v in traj.items()};conv=abs(times['0.05']-times['0.1'])/abs(times['0.05']);row={'case':case,'shape':src['shape'],'initial_y':src['initial_y'],'initial_angle':src['initial_angle'],'trajectories':traj,'validation':validation,'event_times':times,'event_time_fine_vs_medium_relative':float(conv),'passed':bool(all(v['passed'] for v in validation) and conv<=.002 and traj['0.05']['status']=='released')};rows.append(row);(O/f'case_{case:02}.json').write_text(json.dumps(row,indent=2))
checks={'all_48_fresh_poses_pass':all(v['passed'] for r in rows for v in r['validation']),'all_time_integrations_converged':all(r['event_time_fine_vs_medium_relative']<=.002 for r in rows),'all_terminal_statuses_released':all(r['trajectories']['0.05']['status']=='released' for r in rows),'inputs_unchanged':before=={str(p):sha(p) for p in inputs}}
result={'passed':all(checks.values()),'checks':checks,'rows':rows,'runtime_seconds':time.perf_counter()-start,'input_hashes':before};(O/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps({'passed':result['passed'],'checks':checks,'seconds':result['runtime_seconds']}),flush=True)
