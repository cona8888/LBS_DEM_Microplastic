"""Read-only arithmetic audit of repeated original PGS iterates.

All 25,000 sweeps are executed. A byte-identical repeat proves a deterministic
cycle for these fixed systems; this script does not skip or change a sweep.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage50_staging"), str(ROOT / "stage63_staging"),
                str(ROOT / "stage74_staging")]
import inertial_contact_seeded_lm_v1 as gate
import scalar_contact_kernels_v1 as kernels

PROFILE = ROOT / "stage88_evaluations/near_outlet_contact_profile_01/results.json"
OUT = ROOT / "stage91_evaluations/pgs_cycle_audit_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    profile = json.loads(PROFILE.read_text())
    OUT.mkdir(parents=True, exist_ok=False)
    rows = []
    for item in profile["top_systems"]:
        if sha(item["path"]) != item["sha256"]:
            raise RuntimeError("captured system hash drift")
        with np.load(item["path"]) as data:
            vfree, mobility, jacobian, gaps = [data[k].copy() for k in
                                             ("vfree", "mobility", "jacobian", "gaps")]
            dt, friction, tol = [float(data[k]) for k in ("dt", "friction", "tol")]
            maxiter = int(data["maxiter"])
        A = jacobian @ mobility @ jacobian.T
        z = jacobian @ vfree
        scale = max(np.linalg.norm(vfree), 1e-15)
        steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3,3*k+1:3*k+3]).max()
                          for k in range(len(gaps))])
        force = np.zeros(len(z))
        seen = {force.tobytes(): 0}
        first_repeat = None
        for iteration in range(maxiter):
            for k in range(len(gaps)):
                i = 3*k
                vn = z[i]+A[i]@force+gaps[k]/dt
                force[i] = max(0., force[i]-vn/A[i,i])
                vt = z[i+1:i+3]+A[i+1:i+3]@force
                force[i+1:i+3] = kernels.project(force[i+1:i+3], vt, steps[k], friction*force[i])
            residual = kernels.residual(force,z,A,gaps,dt,friction,steps)/scale
            state = force.tobytes()
            if state in seen and first_repeat is None:
                first_repeat = {"first_iteration": seen[state], "repeat_iteration": iteration+1,
                                "period": iteration+1-seen[state], "residual": residual}
            seen.setdefault(state, iteration+1)
            if residual <= tol:
                break
        rows.append({"system": item["path"], "sweeps_executed": iteration+1,
                     "first_repeat": first_repeat, "unique_iterates": len(seen),
                     "final_residual": residual, "final_force": force.tolist()})
    record = {"rows": rows, "input_hashes": {str(PROFILE): sha(PROFILE)},
              "source_hashes": {str(p): sha(p) for p in (Path(__file__), Path(gate.__file__), Path(kernels.__file__))}}
    path = OUT / "results.json"
    path.write_text(json.dumps(record, indent=2))
    (OUT / "completion.json").write_text(json.dumps({"status": "complete_audited", "results_sha256": sha(path)}, indent=2))
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
