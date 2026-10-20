"""Frozen-system checks of Stage72 against the unchanged Stage53 solution."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage53_staging"), str(ROOT / "stage72_staging")]
import inertial_contact_multistart_lm_v1 as baseline
import inertial_contact_capped_krylov_v1 as candidate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    out = ROOT / "stage72_evaluations" / "fixed_capped_01"
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    for seed in (1, 2, 3):
        source = ROOT / "stage56_runs" / "stage55_fibre_failure_capture_20260912" / "diagnostic_02" / f"s{seed}_prolate_ar4" / "failure_state.npz"
        with np.load(source) as data:
            args = (data["vfree"], data["mobility"], data["jacobian"], data["gaps"],
                    float(data["dt"]) * .5, float(data["friction"]),
                    float(data["tol"]), int(data["maxiter"]))
        reference, reference_health = baseline._solve(*args)
        candidate.set_recovery_mode(True)
        try:
            velocity, health = candidate._solve(*args)
        finally:
            candidate.set_recovery_mode(False)
        shift = float(np.linalg.norm(velocity - reference))
        rows.append({"seed": seed, "input_sha256": sha(source),
                     "reference_solver": reference_health["solver"],
                     "candidate_solver": health["solver"],
                     "velocity_shift_m_s": shift,
                     "contact_residual": health["residual"],
                     "force_residual": health["force_residual"],
                     "passed": bool(shift <= 1e-7 and health["residual"] <= 1e-10 and
                                    health["force_residual"] <= 1e-8)})
    result = {"passed": all(x["passed"] for x in rows), "rows": rows,
              "source_hashes": {str(Path(__file__).resolve()): sha(__file__),
                                str(Path(candidate.__file__).resolve()): sha(candidate.__file__)},
              "claim_boundary": "Local numerical verification only; no trajectory or release inference."}
    path = out / "results.json"
    path.write_text(json.dumps(result, indent=2))
    (out / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if result["passed"] else "complete_failed",
        "results_sha256": sha(path)}, indent=2))
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
