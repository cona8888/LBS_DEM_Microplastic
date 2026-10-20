"""Development-only mixed velocity/reaction solve on frozen three contacts."""
import itertools
import json
import sys
import time
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'stage89_staging'))
import verify_short_seed_local_v1 as h
s=h.candidate.stage50
CAP=ROOT/'stage99_evaluations/first_failure_01/capture.json'
OUT=ROOT/'stage102_evaluations/mixed_active_sets_01'
def main():
    OUT.mkdir(parents=True,exist_ok=False)
    raw=json.loads(CAP.read_text())['systems'][0]
    args=[np.asarray(x) if i<4 else x for i,x in enumerate(raw['args'])]
    v,M,J,g,dt,mu,tol,maxiter=args
    h.dump(OUT/'protocol.json',dict(source_sha256=h.sha(__file__),capture_sha256=h.sha(CAP),
      assignments='All eight closed-contact stick/slip assignments. Open contacts not covered.',max_nfev=3000,
      scope='Captured-system development only. No trajectory or production promotion.'))
    seedargs=list(args);seedargs[3]=np.zeros_like(g)
    _,seed=h.candidate.stage53._solve(*seedargs)
    fs=max(np.linalg.norm(seed['reactions']),1e-30);vs=max(np.max(np.abs(g/dt)),1e-15)
    B=np.linalg.inv(M);load=B@v;ls=max(np.linalg.norm(load),1e-30)
    target=np.zeros(9);target[::3]=-g/dt
    q0=np.linalg.lstsq(J,target,rcond=1e-12)[0]/vs
    y0=np.r_[q0,np.array(seed['reactions'])/fs]
    low=np.full(15,-np.inf);low[6::3]=0
    A=J@M@J.T;z=J@v
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(3)])
    rows=[]
    for mask in itertools.product([False,True],repeat=3):
        def eq(y):
            q=y[:6]*vs;f=y[6:]*fs;w=J@y[:6]
            out=list((B@q-load-J.T@f)/ls)
            for k,slip in enumerate(mask):
                i=3*k;out.append(w[i]+g[k]/dt/vs)
                tang=w[i+1:i+3]
                if slip:
                    out.extend(y[6+i+1:6+i+3]+mu*y[6+i]*tang/max(np.linalg.norm(tang),1e-30))
                else:out.extend(tang)
            return np.array(out)
        t=time.perf_counter()
        opt=least_squares(eq,y0,bounds=(low,np.full(15,np.inf)),xtol=1e-13,ftol=1e-13,gtol=1e-13,max_nfev=3000)
        force=opt.x[6:]*fs
        row=dict(sliding=mask,nfev=opt.nfev,mixed_residual=float(np.linalg.norm(eq(opt.x))),runtime_s=time.perf_counter()-t,
                 original_residual=float(s._residual(force,z,A,g,dt,mu,steps)/np.linalg.norm(v)),reaction=force)
        try:
            velocity,health=s._finish(v,M,J,force,z,A,g,dt,mu,steps,opt.nfev,'mixed_active_set',{})
            row.update(passed=True,velocity=velocity,health=health)
        except RuntimeError as e:row.update(passed=False,exception=str(e))
        rows.append(row);h.dump(OUT/f'case_{len(rows)}.json',row)
        print(json.dumps({k:row[k] for k in ('sliding','passed','original_residual','runtime_s')},default=h.json_value),flush=True)
    result=dict(any_passed=any(r['passed'] for r in rows),rows=rows,
      artifact_hashes={str(p):h.sha(p) for p in OUT.glob('*.json')})
    h.dump(OUT/'results.json',result);h.dump(OUT/'completion.json',dict(status='complete_development_test',results_sha256=h.sha(OUT/'results.json')))
if __name__=='__main__':main()
