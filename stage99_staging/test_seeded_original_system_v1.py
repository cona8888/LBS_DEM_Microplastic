"""Use zero-gap solution only as initializer; accept on ORIGINAL gaps."""
import json
import sys
import time
from pathlib import Path
import numpy as np
from scipy.optimize import root
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage89_staging'))
import verify_short_seed_local_v1 as h
s=h.candidate.stage50
CAP=ROOT/'stage99_evaluations/first_failure_01/capture.json'
OUT=ROOT/'stage99_evaluations/seeded_original_01'
def main():
    OUT.mkdir(parents=True,exist_ok=False)
    raw=json.loads(CAP.read_text())['systems'][0]
    args=[np.asarray(x) if i<4 else x for i,x in enumerate(raw['args'])]
    v,M,J,g,dt,mu,tol,maxiter=args
    seedargs=list(args);seedargs[3]=np.zeros_like(g)
    _,seed=h.candidate.stage53._solve(*seedargs)
    A=J@M@J.T;z=J@v;scale=max(np.linalg.norm(v),1e-15)
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(len(g))])
    scales=np.repeat(steps,3);scales[::3]=np.diag(A)[::3]
    def eq(y):
        f=y*scale/scales;vc=z+A@f;out=np.empty_like(y)
        for k in range(len(g)):
            i=3*k;vn=(vc[i]+g[k]/dt)/scale
            out[i]=np.hypot(y[i],vn)-y[i]-vn
            out[i+1:i+3]=y[i+1:i+3]-steps[k]/scale*s._project(f[i+1:i+3],vc[i+1:i+3],steps[k],mu*f[i])
        return out
    t=time.perf_counter()
    solved=root(eq,np.array(seed['reactions'])*scales/scale,method='lm',options=dict(ftol=1e-14,xtol=1e-14,gtol=1e-14,maxiter=50000))
    force=solved.x*scale/scales
    try:
        velocity,health=s._finish(v,M,J,force,z,A,g,dt,mu,steps,solved.nfev,'zero_gap_seed_original_gate',{})
        result=dict(passed=True,velocity=velocity,health=health)
    except RuntimeError as e:result=dict(passed=False,exception=str(e))
    result.update(original_residual=s._residual(force,z,A,g,dt,mu,steps)/scale,runtime_s=time.perf_counter()-t,
                  source_sha256=h.sha(__file__),capture_sha256=h.sha(CAP),original_gaps=g)
    h.dump(OUT/'results.json',result)
    print(json.dumps(result,default=h.json_value))
if __name__=='__main__':main()
