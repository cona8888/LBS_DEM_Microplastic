"""Development test: dimensionless nonlinear unknowns, unchanged physical gate."""
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
OUT=ROOT/'stage99_evaluations/dimensionless_contact_01'
CAP=ROOT/'stage99_evaluations/first_failure_01/capture.json'

def solve(vfree,mobility,jacobian,gaps,dt,friction,tol,maxiter):
    A=jacobian@mobility@jacobian.T; z=jacobian@vfree
    scale=max(np.linalg.norm(vfree),1e-15)
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(len(gaps))])
    scales=np.repeat(steps,3); scales[::3]=np.diag(A)[::3]
    def equations(y):
        f=y*scale/scales; velocity=(z+A@f)/scale
        out=np.empty_like(y)
        for k in range(len(gaps)):
            i=3*k; vn=velocity[i]+gaps[k]/dt/scale
            out[i]=np.hypot(y[i],vn)-y[i]-vn
            trial=y[i+1:i+3]-velocity[i+1:i+3]
            projected=trial*min(1.,max(0.,friction*f[i])*steps[k]/scale/max(np.linalg.norm(trial),1e-300))
            out[i+1:i+3]=y[i+1:i+3]-projected
        return out
    r=root(equations,np.zeros(len(z)),method='lm',options=dict(ftol=1e-14,xtol=1e-14,gtol=1e-14,maxiter=50000))
    return s._finish(vfree,mobility,jacobian,r.x*scale/scales,z,A,gaps,dt,friction,steps,r.nfev,'dimensionless_zero_lm',{})

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    row=json.loads(CAP.read_text())['systems'][0]
    args=[np.asarray(x) if i<4 else x for i,x in enumerate(row['args'])]
    t=time.perf_counter()
    try:
        velocity,health=solve(*args,**row['kwargs'])
        result=dict(passed=True,velocity=velocity,health=health)
    except RuntimeError as e: result=dict(passed=False,exception=str(e))
    result.update(runtime_s=time.perf_counter()-t,source_sha256=h.sha(__file__),capture_sha256=h.sha(CAP))
    h.dump(OUT/'results.json',result)
    print(json.dumps(result,default=h.json_value))
if __name__=='__main__':main()
