import argparse,hashlib,json
from pathlib import Path
import numpy as np
import transport_contact as model
import trajectory_farfield_v1 as far

class Empty:
    L=10.0; r=np.array([1.0]); c=np.array([[100.0,100.0,100.0]])
    class Tree:
        def query_ball_point(self,*args,**kwargs): return []
    tree=Tree()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True); args=ap.parse_args()
    out=Path(args.output); out.mkdir(parents=True,exist_ok=False)
    u=np.zeros((3,10,10,10)); u[0]=1.0; field=model.CellField(u,1.0)
    free=far.integrate(field,Empty(),[5,5,5],[1,0,0],1,1,1,6,10,displacement_fraction=.1)
    geom=model.GrainGeometry([[5,2,5]],[1],10)
    near=far.integrate(field,geom,[5,4.19,5],[1,0,0],1,1,1,9,1,clearance_cutoff=.2)
    checks={'analytic_full_exit':bool(abs(free['time_s']-2)<1e-12),
            'near_wall_censored_not_retained':bool(near['status']=='unresolved_near_wall'),
            'finite_accounting':bool(np.isfinite(free['time_s']) and np.isfinite(near['time_s']))}
    sources=[Path(__file__),Path(far.__file__),Path(model.__file__)]
    result={'passed':all(checks.values()),'checks':checks,'free':free,'near':near,
            'hashes':{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    (out/'results.json').write_text(json.dumps(result,indent=2)); print(json.dumps({'passed':result['passed'],'checks':checks}))
if __name__=='__main__': main()
