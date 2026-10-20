"""Compare bounded direct solvers on the three immutable Stage56 failure states."""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares, root

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage50_staging")]
import inertial_contact_seeded_lm_v1 as s50

RUN = ROOT / "stage56_runs" / "stage55_fibre_failure_capture_20260912" / "diagnostic_02"


def system(path):
    data = np.load(path)
    vfree = data["vfree"]
    mobility = data["mobility"]
    jacobian = data["jacobian"]
    gaps = data["gaps"]
    dt = float(data["dt"])
    friction = float(data["friction"])
    maxiter = int(data["maxiter"])
    A = jacobian @ mobility @ jacobian.T
    z = jacobian @ vfree
    scale = max(np.linalg.norm(vfree), 1e-15)
    steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max() for k in range(len(gaps))])
    scales = np.repeat(steps, 3)
    for k in range(len(gaps)):
        scales[3*k] = A[3*k, 3*k]
    return vfree, mobility, jacobian, gaps, dt, friction, maxiter, A, z, scale, steps, scales


def pgs_seed(A, z, gaps, dt, friction, steps, maxiter):
    force = np.zeros(len(z))
    for _ in range(maxiter):
        for k in range(len(gaps)):
            i = 3*k
            vn = z[i] + A[i] @ force + gaps[k] / dt
            force[i] = max(0.0, force[i] - vn / A[i, i])
            vt = z[i+1:i+3] + A[i+1:i+3] @ force
            force[i+1:i+3] = s50._project(force[i+1:i+3], vt, steps[k], friction*force[i])
    return force


def diagnose(force, vfree, mobility, jacobian, z, A, gaps, dt, friction, steps):
    residual = s50._residual(force, z, A, gaps, dt, friction, steps) / max(np.linalg.norm(vfree), 1e-15)
    contact_velocity = z + A @ force
    velocity = vfree + mobility @ jacobian.T @ force
    closure = np.linalg.norm(np.linalg.solve(mobility, velocity-vfree)-jacobian.T@force) / max(np.linalg.norm(jacobian.T@force), 1e-30)
    cone_margin = min(friction*force[3*k]-np.linalg.norm(force[3*k+1:3*k+3]) for k in range(len(gaps)))
    work = sum(float(force[3*k+1:3*k+3] @ contact_velocity[3*k+1:3*k+3]) for k in range(len(gaps)))
    return {"residual": float(residual), "minimum_normal_force": float(force[::3].min()), "minimum_cone_margin": float(cone_margin), "force_closure": float(closure), "friction_work": float(work)}


def main():
    out = ROOT / "stage56_evaluations" / "bounded_contact_probe_01"
    out.mkdir(parents=True, exist_ok=False)
    records = []
    for seed in (1, 2, 3):
        path = RUN / f"s{seed}_prolate_ar4" / "failure_state.npz"
        vfree, mobility, jacobian, gaps, dt, friction, maxiter, A, z, scale, steps, scales = system(path)
        pgs = pgs_seed(A, z, gaps, dt, friction, steps, maxiter)

        def equations(u):
            force = u / scales
            velocity = z + A @ force
            result = np.empty_like(u)
            for k in range(len(gaps)):
                i = 3*k
                vn = velocity[i] + gaps[k]/dt
                result[i] = np.hypot(u[i], vn) - u[i] - vn
                result[i+1:i+3] = u[i+1:i+3] - steps[k]*s50._project(force[i+1:i+3], velocity[i+1:i+3], steps[k], friction*force[i])
            return result/scale

        lower = np.full(len(z), -np.inf)
        lower[::3] = 0.0
        methods = []
        for start_name, start in (("zero", np.zeros(len(z))), ("pgs", pgs*scales)):
            lm = root(equations, start, method="lm", options={"ftol":1e-14,"xtol":1e-14,"gtol":1e-14,"maxiter":100000})
            methods.append({"method":f"lm_{start_name}","optimizer_success":bool(lm.success),"nfev":int(lm.nfev),**diagnose(lm.x/scales,vfree,mobility,jacobian,z,A,gaps,dt,friction,steps)})
            for algorithm in ("trf", "dogbox"):
                bounded = least_squares(equations, np.maximum(start, lower), method=algorithm, bounds=(lower, np.inf),
                    ftol=1e-14, xtol=1e-14, gtol=1e-14, max_nfev=100000, x_scale="jac")
                methods.append({"method":f"{algorithm}_{start_name}","optimizer_success":bool(bounded.success),"nfev":int(bounded.nfev),
                    **diagnose(bounded.x/scales,vfree,mobility,jacobian,z,A,gaps,dt,friction,steps)})
        record = {"packing_seed":seed,"contacts":int(len(gaps)),"condition_number_A":float(np.linalg.cond(A)),"methods":methods}
        records.append(record)
        print(json.dumps(record, indent=2), flush=True)
    acceptance = lambda m: m["residual"] <= 1e-10 and m["minimum_normal_force"] >= 0 and m["minimum_cone_margin"] >= -1e-12 and m["force_closure"] <= 1e-8 and m["friction_work"] <= 1e-8
    summary = {"records":records,"accepted_methods":{str(r["packing_seed"]):[m["method"] for m in r["methods"] if acceptance(m)] for r in records},
        "claim_boundary":"Fixed rejected-system algorithm probe only; no physical trajectory or release claim."}
    (out / "results.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
