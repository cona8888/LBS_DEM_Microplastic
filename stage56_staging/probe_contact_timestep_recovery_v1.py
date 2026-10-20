"""Test whether standard adaptive time-step reduction resolves captured failures."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage41_staging"), str(ROOT / "stage42_staging"), str(ROOT / "stage50_staging"), str(ROOT / "stage53_staging")]
import inertial_contact_multistart_lm_v1 as solver

RUN = ROOT / "stage56_runs" / "stage55_fibre_failure_capture_20260912" / "diagnostic_02"


def main():
    out = ROOT / "stage56_evaluations" / "contact_timestep_probe_01"
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    for seed in (1, 2, 3):
        data = np.load(RUN / f"s{seed}_prolate_ar4" / "failure_state.npz")
        for factor in (1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125):
            try:
                _, health = solver._solve(data["vfree"], data["mobility"], data["jacobian"], data["gaps"],
                    float(data["dt"])*factor, float(data["friction"]), float(data["tol"]), int(data["maxiter"]))
                row = {"packing_seed":seed,"dt_factor":factor,"status":"passed","solver":health["solver"],
                    "residual":health["residual"],"force_residual":health["force_residual"],"iterations":health["iterations"]}
            except Exception as exc:
                row = {"packing_seed":seed,"dt_factor":factor,"status":"failed","reason":str(exc)}
            rows.append(row)
            print(json.dumps(row), flush=True)
    result = {"rows":rows,"all_failures_recover_at_smaller_dt":all(any(r["packing_seed"]==s and r["dt_factor"]<1 and r["status"]=="passed" for r in rows) for s in (1,2,3)),
        "claim_boundary":"Frozen local-system numerical probe only."}
    (out / "results.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
