"""Verify Stage74 scalar kernels against frozen vector implementations."""
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage50_staging"), str(ROOT / "stage53_staging"),
                str(ROOT / "stage63_staging"), str(ROOT / "stage74_staging")]
import inertial_contact_seeded_lm_v1 as s50
import inertial_contact_multistart_lm_v1 as s53
import inertial_contact_scalar_kernel_v1 as candidate
import scalar_contact_kernels_v1 as kernels


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    out = ROOT / "stage74_evaluations" / "scalar_kernel_verification_01"
    out.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(7417)
    max_projection_difference = 0.
    max_residual_difference = 0.
    for _ in range(1000):
        ft, vt = rng.normal(size=(2, 2)) * 1e-5
        step = float(10 ** rng.uniform(-3, 4))
        limit = float(10 ** rng.uniform(-12, -3))
        difference = np.linalg.norm(kernels.project(ft, vt, step, limit) -
                                    s50._project(ft, vt, step, limit))
        max_projection_difference = max(max_projection_difference, float(difference))
    for _ in range(300):
        nc = int(rng.integers(1, 4))
        n = nc * 3
        base = rng.normal(size=(n, n))
        A = base.T @ base + np.eye(n)
        force = rng.normal(size=n) * 1e-6
        force[::3] = np.abs(force[::3])
        z = rng.normal(size=n) * 1e-4
        gaps = rng.normal(size=nc) * 1e-8
        steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max()
                          for k in range(nc)])
        difference = abs(kernels.residual(force, z, A, gaps, 1e-3, .3, steps) -
                         s50._residual(force, z, A, gaps, 1e-3, .3, steps))
        max_residual_difference = max(max_residual_difference, float(difference))
    rows = []
    for seed in (1, 2, 3):
        source = ROOT / "stage56_runs" / "stage55_fibre_failure_capture_20260912" / "diagnostic_02" / f"s{seed}_prolate_ar4" / "failure_state.npz"
        with np.load(source) as data:
            args = (data["vfree"], data["mobility"], data["jacobian"], data["gaps"],
                    float(data["dt"]) * .5, float(data["friction"]),
                    float(data["tol"]), int(data["maxiter"]))
        reference, reference_health = s53._solve(*args)
        candidate.set_recovery_mode(True)
        try:
            velocity, health = candidate._solve(*args)
        finally:
            candidate.set_recovery_mode(False)
        shift = float(np.linalg.norm(reference - velocity))
        rows.append({"seed": seed, "input_sha256": sha(source),
                     "candidate_solver": health["solver"],
                     "velocity_shift_m_s": shift,
                     "contact_residual": health["residual"],
                     "force_residual": health["force_residual"],
                     "passed": bool(shift <= 1e-7 and health["residual"] <= 1e-10 and
                                    health["force_residual"] <= 1e-8)})
    result = {"passed": bool(max_projection_difference <= 1e-15 and
                             max_residual_difference <= 1e-12 and
                             all(row["passed"] for row in rows)),
              "max_projection_difference": max_projection_difference,
              "max_residual_difference": max_residual_difference,
              "frozen_rows": rows,
              "source_hashes": {str(Path(__file__).resolve()): sha(__file__),
                                str(Path(kernels.__file__).resolve()): sha(kernels.__file__),
                                str(Path(candidate.__file__).resolve()): sha(candidate.__file__)},
              "claim_boundary": "Kernel and frozen-system code verification only."}
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
