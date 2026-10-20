"""Low-resolution path discovery only; never used as accepted release evidence."""
import hashlib,json,time
from pathlib import Path
import numpy as np
import open_grains_ellipsoid_v1 as flow
R=Path(__file__).resolve().parents[1];O=R/'stage36_evaluations/stage36cc_path_discovery_20260911/run_01';O.mkdir(parents=True,exist_ok=False)
cfg={'source_count':64,'dx':.4,'method':'explicit midpoint in x','x_bounds':[-4.2,4.2],
 'initial_y':[0,.15,-.15],'prolate_angles_degrees':[0,45,90],
 'role':'trajectory-domain discovery only; outputs prohibited from release inference'}
(O/'contract.json').write_text(json.dumps(cfg,indent=2));radius=float(np.cbrt(.002));rows=[];start=time.perf_counter()
for shape in ['sphere','prolate']:
 for y0 in cfg['initial_y']:
  for deg in ([0] if shape=='sphere' else cfg['prolate_angles_degrees']):
   axes=(radius,)*3 if shape=='sphere' else (.2,.1,.1);x=-4.2;s=np.array([0.,y0,np.deg2rad(deg)]);hist=[];status='domain_end'
   try:
    while x<4.2-1e-12:
     h=min(cfg['dx'],4.2-x)
     def rhs(q,z):
      th=z[2];Q=np.array([[np.cos(th),-np.sin(th),0],[np.sin(th),np.cos(th),0],[0,0,1.]])
      v,_=flow.solve([q,z[1],0],Q,cfg['source_count'],check=False,axes=axes)
      if v[0]<=0:raise ValueError('nonpositive axial velocity')
      return np.array([1.,v[1],v[5]])/v[0]
     k=rhs(x,s);mid=s+h*k/2;s+=h*rhs(x+h/2,mid);x+=h;hist.append([x,*s])
   except ValueError as exc:status='unresolved: '+str(exc)
   a=np.asarray(hist);row={'shape':shape,'initial_y':y0,'initial_angle':deg,'status':status,'steps':len(hist),
    'y_min':float(a[:,2].min()) if len(a) else y0,'y_max':float(a[:,2].max()) if len(a) else y0,
    'theta_min':float(a[:,3].min()) if len(a) else s[2],'theta_max':float(a[:,3].max()) if len(a) else s[2]}
   rows.append(row);np.savez_compressed(O/f'path_{len(rows):02}.npz',state=a);print(json.dumps(row),flush=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();res={'completed':len(rows)==12,'rows':rows,'runtime_seconds':time.perf_counter()-start,
 'accepted_release_evidence':False,'input_hashes':{str(p):sha(p) for p in [Path(__file__),Path(flow.__file__),O/'contract.json']}}
(O/'results.json').write_text(json.dumps(res,indent=2));print(json.dumps({'completed':res['completed'],'seconds':res['runtime_seconds']}))
