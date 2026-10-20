"""Independent fixed-system gates for the Stage70 runtime portfolio."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"stage53_staging"),str(ROOT/"stage70_staging")]
import inertial_contact_multistart_lm_v1 as baseline
import inertial_contact_runtime_portfolio_v1 as candidate

INPUT=ROOT/"stage56_runs"/"stage55_fibre_failure_capture_20260912"/"diagnostic_02"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    out=ROOT/"stage70_evaluations"/"fixed_runtime_01"
    out.mkdir(parents=True,exist_ok=False)
    rows=[]
    for seed in (1,2,3):
        path=INPUT/f"s{seed}_prolate_ar4"/"failure_state.npz"
        with np.load(path) as data:
            args=(data["vfree"],data["mobility"],data["jacobian"],data["gaps"],
                  float(data["dt"])*.5,float(data["friction"]),
                  float(data["tol"]),int(data["maxiter"]))
        baseline_velocity,baseline_health=baseline._solve(*args)
        before=candidate.stats()
        candidate.set_recovery_mode(True)
        try:
            velocity,health=candidate._solve(*args)
        finally:
            candidate.set_recovery_mode(False)
        after=candidate.stats()
        stats={k:after[k]-before[k] for k in after}
        shift=float(np.linalg.norm(velocity-baseline_velocity))
        row={"packing_seed":seed,"source_sha256":sha(path),
             "baseline_solver":baseline_health["solver"],
             "candidate_solver":health["solver"],
             "baseline_contact_residual":baseline_health["residual"],
             "candidate_contact_residual":health["residual"],
             "candidate_force_closure":health["force_residual"],
             "velocity_shift_m_s":shift,"stats":stats,
             "passed":bool(health["residual"]<=1e-10 and
                           health["force_residual"]<=1e-8 and
                           shift<=1e-7 and stats["recovery_failures"]==0)}
        rows.append(row)
        print(json.dumps(row),flush=True)
    result={"passed":all(r["passed"] for r in rows),"rows":rows,
            "source_hashes":{str(Path(__file__).resolve()):sha(__file__),
                             str((ROOT/"stage70_staging/inertial_contact_runtime_portfolio_v1.py").resolve()):sha(ROOT/"stage70_staging/inertial_contact_runtime_portfolio_v1.py")},
            "claim_boundary":"Algorithm verification on frozen local systems only; no release inference."}
    path=out/"results.json"
    path.write_text(json.dumps(result,indent=2))
    (out/"completion.json").write_text(json.dumps({"status":"complete_passed" if result["passed"] else "complete_failed","results_sha256":sha(path)},indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__=="__main__":
    main()
