import argparse,json,hashlib
from pathlib import Path
import numpy as np
import transport_contact as m
import trajectory as tr

ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
class Constant:
    def __init__(self,u):self.u=np.asarray(u,float)
    def sample(self,x):return self.u.copy(),np.zeros((3,3))
class Empty:
    def contacts(self,*args):return []
    def swept_gap(self,*args):return np.inf
class Plane:
    def contacts(self,x,p,a,b,skin):
        gap=x[1]-a
        return [(0,gap,np.array([0.,1,0]),np.array([0.,-a,0]))] if gap<=skin else []
    def swept_gap(self,x,p,v,a,b,dt):return min(x[1],x[1]+v[1]*dt)-a

rows=[];checks={}
for h in [.2,.1,.05]:
    free=tr.integrate(Constant([2,0,0]),Empty(),[9,5,5],[1,0,0],1,1,1,1,1,[0,0,0],0,10,2,displacement_fraction=h)
    # Sphere forced normally into plane and advected along it: rolling/sliding
    # couples rotation. Analytical slip solution for isotropic sphere:
    # Fn=6*pi; Ft=min(mu Fn,6*pi/(1+6*pi/(8*pi))) for unit slip speed.
    slide=tr.integrate(Constant([1,-1,0]),Plane(),[0,1,0],[1,0,0],1,1,1,1,1,[0,0,0],.3,2,10,displacement_fraction=h)
    rows.append({'h':h,'free':free,'slide':slide})
checks['full_exit_time_all_levels']=all(r['free']['status']=='full_window_exit' and abs(r['free']['time']-1)<1e-10 for r in rows)
checks['contact_sliding_and_rotation']=all(r['slide']['status']=='full_window_exit' and abs(r['slide']['time']-3/.7)<1e-8 and r['slide']['contact_steps']>0 and r['slide']['minimum_gap']>=-1e-8 for r in rows)
checks['force_and_contact_residuals']=all(r['slide']['max_force_residual']<1e-6 and r['slide']['max_contact_residual']<1e-6 for r in rows)
# Swept collision detects a sphere crossing a small obstacle between sampled endpoints.
gr=m.GrainGeometry([[.23,5,5]],[.015],10)
gap=tr.swept_gap(gr,np.array([0.,5,5]),np.array([1.,0,0]),np.array([1.,0,0,0,0,0]),.01,.01,1.)
checks['thin_obstacle_sweep']=abs(gap+.025)<1e-12
bad=tr.integrate(Constant([np.nan,0,0]),Empty(),[0,0,0],[1,0,0],1,1,1,1,1,[0,0,0],0,10,1.)
checks['nonfinite_trajectory_fails']=bad['status']=='numerical_failure'
result={'passed':all(checks.values()),'checks':checks,'swept_gap':gap,'rows':rows,'invalid':bad,'hashes':{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(m.__file__),Path(tr.__file__)]}}
(out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False));print(json.dumps({'passed':result['passed'],'checks':checks,'slide_times':[r['slide']['time'] for r in rows],'slide_status':[r['slide']['status'] for r in rows]}))
