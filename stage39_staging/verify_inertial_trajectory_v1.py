import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
import trajectory_inertial_v1 as tr
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'stage37_staging'));import transport_contact as m
class Field:
 def __init__(self,u):self.u=np.asarray(u,float)
 def sample(self,x):return self.u.copy(),np.zeros((3,3))
class Empty:
 r=np.array([.3])
 def contacts(self,*args):return []
 def swept_gap(self,*args):return np.inf
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=False);a=b=5e-5;rows=[]
 # Uniform-flow relaxation and full-exit event at three timestep levels.
 for frac in (.2,.1,.05):rows.append({'fraction':frac,'result':tr.integrate(Field([.001,0,0]),Empty(),[0,0,0],[1,0,0],np.zeros(6),a,b,.001002,1380,998.2,[0,0,0],0,.001,.05,added_mass_fraction=1,displacement_fraction=frac,relaxation_fraction=frac,max_dt=.01)})
 times=[r['result']['time_s'] for r in rows];shift=abs(times[-1]-times[-2])/times[-1]
 # Curved two-grain contact at project-scale Re.
 c=np.array([.005,.005,.005]);geom=m.GrainGeometry([[.005,.00535,.005],[.005,.00465,.005]],[.0003,.0003],.01);contact=[]
 for frac in (.2,.1,.05):contact.append({'fraction':frac,'result':tr.integrate(Field([.001,.0002,0]),geom,c,[1,0,0],np.zeros(6),a,b,.001002,1380,998.2,[0,0,0],.3,.006,.02,added_mass_fraction=1,displacement_fraction=frac,relaxation_fraction=frac,max_dt=.01)})
 ctimes=[r['result']['time_s'] for r in contact];cshift=abs(ctimes[-1]-ctimes[-2])/ctimes[-1];allrows=[r['result'] for r in rows+contact];checks={'all_exit':all(r['status']=='full_window_exit' for r in allrows),'uniform_fine_medium_time_shift':shift<=.002,'contact_fine_medium_time_shift':cshift<=.002,'curved_lubrication_active':all(r['max_lubrication_contacts']==2 for r in [x['result'] for x in contact]),'curved_contact_active':all(r['contact_steps']>0 for r in [x['result'] for x in contact]),'no_penetration':all(r['minimum_gap_m'] is None or r['minimum_gap_m']>=-5e-10 for r in allrows),'momentum':max(r['max_momentum_residual'] for r in allrows)<=1e-8,'contact_residual':max(r['max_contact_residual'] for r in allrows)<=1e-8,'force_residual':max(r['max_force_residual'] for r in allrows)<=1e-6,'reynolds_in_domain':max(r['max_reynolds'] for r in allrows)<=3}
 paths=[Path(__file__),Path(tr.__file__),Path(tr.inertial.__file__),Path(tr.lubrication.__file__),Path(m.__file__)];result={'completed':True,'passed':all(checks.values()),'checks':{k:bool(v) for k,v in checks.items()},'uniform_rows':rows,'contact_rows':contact,'uniform_time_shift':shift,'contact_time_shift':cshift,'source_hashes':{str(p.resolve()):sha(p) for p in paths},'scope':'manufactured trajectory verification; no sand-matrix release claim'};(out/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps({'passed':result['passed'],'checks':result['checks'],'uniform_times':times,'contact_times':ctimes,'shifts':[shift,cshift]},indent=2))
if __name__=='__main__':main()
