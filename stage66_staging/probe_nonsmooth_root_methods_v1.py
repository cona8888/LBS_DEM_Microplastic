"""Probe derivative-free/root accelerators on immutable feasible half-step systems."""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import root

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage50_staging")]
import inertial_contact_seeded_lm_v1 as s50
RUN=ROOT/"stage56_runs"/"stage55_fibre_failure_capture_20260912"/"diagnostic_02"


def main():
    out=ROOT/"stage66_evaluations"/"nonsmooth_roots_01"; out.mkdir(parents=True,exist_ok=False); rows=[]
    for seed in (1,2,3):
        d=np.load(RUN/f"s{seed}_prolate_ar4"/"failure_state.npz")
        vfree,mobility,J,gaps=d["vfree"],d["mobility"],d["jacobian"],d["gaps"]
        dt=float(d["dt"])*.5; friction=float(d["friction"]); A=J@mobility@J.T; z=J@vfree; scale=max(np.linalg.norm(vfree),1e-15)
        steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(len(gaps))]); scales=np.repeat(steps,3)
        for k in range(len(gaps)): scales[3*k]=A[3*k,3*k]
        def equations(u):
            force=u/scales; velocity=z+A@force; residual=np.empty_like(u)
            for k in range(len(gaps)):
                i=3*k; vn=velocity[i]+gaps[k]/dt; residual[i]=np.hypot(u[i],vn)-u[i]-vn
                residual[i+1:i+3]=u[i+1:i+3]-steps[k]*s50._project(force[i+1:i+3],velocity[i+1:i+3],steps[k],friction*force[i])
            return residual/scale
        for method in ("anderson","broyden1","broyden2","diagbroyden","krylov","df-sane"):
            try:
                solved=root(equations,np.zeros(len(z)),method=method,options={"maxiter":10000,"fatol":1e-12})
                force=solved.x/scales
                _,health=s50._finish(vfree,mobility,J,force,z,A,gaps,dt,friction,steps,int(getattr(solved,"nfev",0)),method,{})
                row={"packing_seed":seed,"method":method,"status":"passed","nfev":int(getattr(solved,"nfev",0)),"residual":health["residual"]}
            except Exception as exc:
                row={"packing_seed":seed,"method":method,"status":"failed","reason":str(exc)}
            rows.append(row); print(json.dumps(row),flush=True)
    winners={str(s):[r for r in rows if r["packing_seed"]==s and r["status"]=="passed"] for s in (1,2,3)}
    result={"passed":all(winners.values()),"winners":winners,"rows":rows,"claim_boundary":"Fixed-system numerical probe only."}
    (out/"results.json").write_text(json.dumps(result,indent=2))
    if not result["passed"]: raise SystemExit(1)


if __name__=="__main__": main()
