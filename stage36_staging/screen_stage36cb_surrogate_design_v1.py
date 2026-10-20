"""Low-resolution screening of a periodic planar pose surrogate design."""
import hashlib,json,time
from pathlib import Path
import numpy as np
from scipy.interpolate import RBFInterpolator
from scipy.stats import qmc
import open_grains_ellipsoid_v1 as flow
R=Path(__file__).resolve().parents[1];O=R/'stage36_evaluations/stage36cb_surrogate_screen_20260911/screen_01';O.mkdir(parents=True,exist_ok=False)
cfg={'train_sobol_power':6,'holdout_count':24,'source_count':128,'x_abs_domain':[0,4.2],'y_domain':[-.2,.2],
 'angle_domain_radians':[0,float(np.pi)],'features':['x/4.2','y/0.2','cos(2 theta)','sin(2 theta)'],
 'kernel':'thin_plate_spline','degree':1,'role':'design screening only; cannot qualify fine trajectories'}
(O/'contract.json').write_text(json.dumps(cfg,indent=2))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();paths=[Path(__file__),Path(flow.__file__),Path(flow.m.__file__),O/'contract.json'];before={str(p):sha(p) for p in paths}
def poses(seed,power=None,count=None):
 s=qmc.Sobol(3,scramble=True,seed=seed);u=s.random_base2(power) if power is not None else s.random(count)
 return np.column_stack((4.2*u[:,0],.4*u[:,1]-.2,np.pi*u[:,2]))
def feat(a):return np.column_stack((a[:,0]/4.2,a[:,1]/.2,np.cos(2*a[:,2]),np.sin(2*a[:,2])))
def solve_all(a):
 out=[]
 for i,(x,y,t) in enumerate(a):
  Q=np.array([[np.cos(t),-np.sin(t),0],[np.sin(t),np.cos(t),0],[0,0,1.]])
  z,h=flow.solve([x,y,0],Q,cfg['source_count'],check=False);out.append([z[0],z[1],z[5]])
  if (i+1)%16==0:print(json.dumps({'completed':i+1,'total':len(a)}),flush=True)
 return np.asarray(out)
start=time.perf_counter();train=poses(3601,power=cfg['train_sobol_power']);test=poses(3602,count=cfg['holdout_count'])
yt=solve_all(train);yv=solve_all(test);model=RBFInterpolator(feat(train),yt,kernel=cfg['kernel'],degree=cfg['degree']);pred=model(feat(test));err=np.abs(pred-yv)
metrics={'translation_max_absolute':float(err[:,:2].max()),'rotation_max_absolute':float(err[:,2].max()),
 'translation_p95_absolute':float(np.quantile(err[:,:2],.95)),'rotation_p95_absolute':float(np.quantile(err[:,2],.95))}
np.savez_compressed(O/'data.npz',train_pose=train,train_motion=yt,holdout_pose=test,holdout_motion=yv,holdout_prediction=pred)
res={'passed_screen':metrics['translation_max_absolute']<.005 and metrics['rotation_max_absolute']<.005,
 'metrics':metrics,'runtime_seconds':time.perf_counter()-start,'input_hashes':before,
 'fine_qualification':False,'next_if_pass':'train fine surrogate and validate on fresh direct poses'}
(O/'results.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2))
