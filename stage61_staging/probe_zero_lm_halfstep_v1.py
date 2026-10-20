"""Test zero-seeded scaled LM directly on captured systems at reduced dt."""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import root

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage50_staging")]
import inertial_contact_seeded_lm_v1 as s50

RUN = ROOT / "stage56_runs" / "stage55_fibre_failure_capture_20260912" / "diagnostic_02"


def main():
    out = ROOT / "stage61_evaluations" / "zero_lm_halfstep_01"
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    for seed in (1, 2, 3):
        data = np.load(RUN / f"s{seed}_prolate_ar4" / "failure_state.npz")
        vfree, mobility, J, gaps = data["vfree"], data["mobility"], data["jacobian"], data["gaps"]
        friction = float(data["friction"])
        A = J @ mobility @ J.T
        z = J @ vfree
        scale = max(np.linalg.norm(vfree), 1e-15)
        steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max() for k in range(len(gaps))])
        scales = np.repeat(steps, 3)
        for k in range(len(gaps)):
            scales[3*k] = A[3*k,3*k]
        for factor in (0.5, 0.25, 0.125):
            dt = float(data["dt"])*factor
            def equations(u):
                force = u/scales
                velocity = z + A@force
                residual = np.empty_like(u)
                for k in range(len(gaps)):
                    i = 3*k
                    vn = velocity[i] + gaps[k]/dt
                    residual[i] = np.hypot(u[i],vn)-u[i]-vn
                    residual[i+1:i+3] = u[i+1:i+3]-steps[k]*s50._project(force[i+1:i+3],velocity[i+1:i+3],steps[k],friction*force[i])
                return residual/scale
            solved = root(equations, np.zeros(len(z)), method="lm", options={"ftol":1e-14,"xtol":1e-14,"gtol":1e-14,"maxiter":50000})
            try:
                _, health = s50._finish(vfree,mobility,J,solved.x/scales,z,A,gaps,dt,friction,steps,int(solved.nfev),"zero_lm_probe",{})
                row={"packing_seed":seed,"dt_factor":factor,"status":"passed","nfev":int(solved.nfev),"residual":health["residual"],"force_residual":health["force_residual"]}
            except Exception as exc:
                row={"packing_seed":seed,"dt_factor":factor,"status":"failed","nfev":int(solved.nfev),"reason":str(exc)}
            rows.append(row)
            print(json.dumps(row),flush=True)
    result={"passed":all(any(r["packing_seed"]==s and r["status"]=="passed" for r in rows) for s in (1,2,3)),"rows":rows,"claim_boundary":"Fixed local-system solver probe only."}
    (out/"results.json").write_text(json.dumps(result,indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__=="__main__":
    main()
