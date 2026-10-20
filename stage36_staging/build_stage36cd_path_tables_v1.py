"""Mixed-resolution path-specific mobility tables from discovery corridors."""
import hashlib,json,time
from pathlib import Path
import numpy as np
import open_grains_ellipsoid_v1 as flow
R=Path(__file__).resolve().parents[1];D=R/'stage36_evaluations/stage36cc_path_discovery_20260911/run_01'
Q=R/'stage36_evaluations/stage36bw_pose_qualification_20260911/run_03/results.json'
O=R/'stage36_evaluations/stage36cd_path_tables_20260911/table_01';O.mkdir(parents=True,exist_ok=False)
nodes=[-4.2,-2.8,-1.4,0,1.4,2.8,4.2]
cfg={'path_source':str(D),'training_x':nodes,'source_rule':'384 for |x|<=1.4; 256 otherwise',
 'boundary_limit':.001,'force_free_limit':1e-10,'role':'provisional path tables; qualification requires fresh direct poses'}
(O/'contract.json').write_text(json.dumps(cfg,indent=2))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();paths=[Path(__file__),Path(flow.__file__),D/'results.json',Q,O/'contract.json']
before={str(p):sha(p) for p in paths};disc=json.loads((D/'results.json').read_text());assert disc['completed'] and json.loads(Q.read_text())['passed']
rows=[];start=time.perf_counter();radius=float(np.cbrt(.002))
for case,meta in enumerate(disc['rows'],1):
 a=np.load(D/f'path_{case:02}.npz')['state'];initial=np.array([[-4.2,0,meta['initial_y'],np.deg2rad(meta['initial_angle'])]])
 a=np.vstack((initial,a));axes=(radius,)*3 if meta['shape']=='sphere' else (.2,.1,.1);samples=[]
 for x in nodes:
  y=float(np.interp(x,a[:,0],a[:,2]));theta=float(np.interp(x,a[:,0],np.unwrap(a[:,3])))
  M=np.array([[np.cos(theta),-np.sin(theta),0],[np.sin(theta),np.cos(theta),0],[0,0,1.]])
  n=384 if abs(x)<=1.4 else 256;tick=time.perf_counter();z,h=flow.solve([x,y,0],M,n,axes=axes)
  s={'x':x,'y':y,'theta':theta,'n':n,'motion':[float(z[0]),float(z[1]),float(z[5])],**h,'seconds':time.perf_counter()-tick}
  samples.append(s);print(json.dumps({'case':case,'node':len(samples),'shape':meta['shape'],'x':x,'n':n}),flush=True)
 row={**meta,'case':case,'axes':axes,'samples':samples,'passed_health':all(max(s['grain_boundary_error'],s['fibre_boundary_error'])<.001 and s['force_free_residual']<1e-10 for s in samples)}
 rows.append(row);(O/f'case_{case:02}.json').write_text(json.dumps(row,indent=2))
checks={'discovery_complete':disc['completed'],'local_poses_qualified':json.loads(Q.read_text())['passed'],'sample_health':all(r['passed_health'] for r in rows),'inputs_unchanged':before=={str(p):sha(p) for p in paths}}
res={'passed_provisional':all(checks.values()),'checks':checks,'rows':rows,'runtime_seconds':time.perf_counter()-start,'input_hashes':before,'trajectory_release_qualified':False}
(O/'results.json').write_text(json.dumps(res,indent=2));print(json.dumps({'checks':checks,'seconds':res['runtime_seconds']}),flush=True)
