"""Projected-SOR sweep probe on immutable reduced-dt failure systems."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage50_staging")]
import inertial_contact_seeded_lm_v1 as s50
RUN=ROOT/"stage56_runs"/"stage55_fibre_failure_capture_20260912"/"diagnostic_02"


def solve(vfree,mobility,J,gaps,dt,friction,omega,maxiter=25000):
    A=J@mobility@J.T; z=J@vfree; force=np.zeros(len(z)); scale=max(np.linalg.norm(vfree),1e-15)
    steps=np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(len(gaps))])
    for iteration in range(maxiter):
        for k in range(len(gaps)):
            i=3*k
            old=force[i]; vn=z[i]+A[i]@force+gaps[k]/dt
            candidate=max(0.,old-vn/A[i,i]); force[i]=max(0.,old+omega*(candidate-old))
            old_t=force[i+1:i+3].copy(); vt=z[i+1:i+3]+A[i+1:i+3]@force
            candidate_t=s50._project(old_t,vt,steps[k],friction*force[i])
            trial=old_t+omega*(candidate_t-old_t)
            limit=friction*force[i]; force[i+1:i+3]=trial*min(1.,limit/max(np.linalg.norm(trial),1e-300))
        residual=s50._residual(force,z,A,gaps,dt,friction,steps)/scale
        if residual<=1e-10:
            return {"status":"passed","iterations":iteration+1,"residual":float(residual)}
    return {"status":"failed","iterations":maxiter,"residual":float(residual)}


def main():
    out=ROOT/"stage62_evaluations"/"projected_sor_01"; out.mkdir(parents=True,exist_ok=False); rows=[]
    for seed in (1,2,3):
        d=np.load(RUN/f"s{seed}_prolate_ar4"/"failure_state.npz")
        for omega in (1.0,1.1,1.25,1.5,1.7,1.85,1.95):
            row={"packing_seed":seed,"dt_factor":0.5,"omega":omega,**solve(d["vfree"],d["mobility"],d["jacobian"],d["gaps"],float(d["dt"])*.5,float(d["friction"]),omega)}
            rows.append(row); print(json.dumps(row),flush=True)
    best={str(seed):min((r for r in rows if r["packing_seed"]==seed and r["status"]=="passed"),key=lambda r:r["iterations"],default=None) for seed in (1,2,3)}
    result={"passed":all(best.values()),"best":best,"rows":rows,"claim_boundary":"Fixed local-system convergence probe; unchanged complementarity equations."}
    (out/"results.json").write_text(json.dumps(result,indent=2))
    if not result["passed"]: raise SystemExit(1)


if __name__=="__main__": main()
