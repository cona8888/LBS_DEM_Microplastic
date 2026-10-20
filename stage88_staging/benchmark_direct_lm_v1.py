"""Frozen-system benchmark of zero-seeded LM against the accepted Stage81 solve.

The candidate uses Stage53's identical scaled equations, but attempts LM
before the 25,000-iteration PGS seed. Only original Stage50 gates may accept it.
No trajectory or physical outcome is inferred from this microbenchmark.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import root

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage50_staging"), str(ROOT / "stage70_staging"),
                str(ROOT / "stage74_staging")]
import inertial_contact_seeded_lm_v1 as gate
import inertial_contact_runtime_portfolio_v1 as baseline
import scalar_contact_kernels_v1 as kernels

PROFILE = ROOT / "stage88_evaluations" / "near_outlet_contact_profile_01"
OUT = ROOT / "stage88_evaluations" / "direct_lm_frozen_systems_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def direct(vfree, mobility, jacobian, gaps, dt, friction):
    A = jacobian @ mobility @ jacobian.T
    z = jacobian @ vfree
    scale = max(np.linalg.norm(vfree), 1e-15)
    steps = np.array([np.linalg.eigvalsh(A[3*k+1:3*k+3, 3*k+1:3*k+3]).max()
                      for k in range(len(gaps))])
    scales = np.repeat(steps, 3)
    for k in range(len(gaps)):
        scales[3*k] = A[3*k, 3*k]
    if np.any(scales <= 0) or not np.isfinite(scales).all():
        raise RuntimeError("nonpositive direct contact scale")

    def equations(u):
        force = u/scales
        velocity = z + A @ force
        residual = np.empty_like(u)
        for k in range(len(gaps)):
            i = 3*k
            vn = velocity[i] + gaps[k]/dt
            residual[i] = np.hypot(u[i], vn) - u[i] - vn
            residual[i+1:i+3] = u[i+1:i+3] - steps[k]*gate._project(
                force[i+1:i+3], velocity[i+1:i+3], steps[k], friction*force[i])
        return residual/scale

    solved = root(equations, np.zeros(len(z)), method="lm", options={
        "ftol": 1e-14, "xtol": 1e-14, "gtol": 1e-14, "maxiter": 50000})
    return gate._finish(vfree, mobility, jacobian, solved.x/scales, z, A,
                        gaps, dt, friction, steps, int(solved.nfev),
                        "zero_seeded_scaled_lm_first", {
                            "lm_nfev": int(solved.nfev),
                            "lm_success_flag": bool(solved.success)})


def main():
    completion = json.loads((PROFILE / "completion.json").read_text())
    results_path = PROFILE / "results.json"
    if completion["status"] != "complete_profiled" or completion["results_sha256"] != sha(results_path):
        raise RuntimeError("source profile not hash-bound")
    profile = json.loads(results_path.read_text())
    for path, digest in {**profile["input_hashes"], **profile["source_hashes"]}.items():
        if sha(path) != digest:
            raise RuntimeError(f"profile lineage drift: {path}")
    OUT.mkdir(parents=True, exist_ok=False)
    old_project, old_residual = gate._project, gate._residual
    gate._project, gate._residual = kernels.project, kernels.residual
    rows = []
    try:
        for item in profile["top_systems"]:
            path = Path(item["path"])
            if sha(path) != item["sha256"]:
                raise RuntimeError("captured system hash drift")
            with np.load(path) as data:
                vfree = data["vfree"]
                mobility = data["mobility"]
                jacobian = data["jacobian"]
                gaps = data["gaps"]
                dt = float(data["dt"])
                friction = float(data["friction"])
                tol = float(data["tol"])
                maxiter = int(data["maxiter"])
                captured_velocity = data["velocity"].copy()
                captured_reactions = data["reactions"].copy()
            start = time.perf_counter()
            old = baseline._solve(vfree, mobility, jacobian, gaps, dt, friction, tol, maxiter)
            baseline_elapsed = time.perf_counter()-start
            start = time.perf_counter()
            try:
                new = direct(vfree, mobility, jacobian, gaps, dt, friction)
            except Exception as exc:
                candidate_elapsed = time.perf_counter()-start
                rows.append({"system": str(path), "candidate_passed": False,
                             "candidate_error": f"{type(exc).__name__}: {exc}",
                             "baseline_elapsed_s": baseline_elapsed,
                             "candidate_elapsed_s": candidate_elapsed})
                continue
            candidate_elapsed = time.perf_counter()-start
            rows.append({
                "system": str(path), "candidate_passed": True,
                "baseline_elapsed_s": baseline_elapsed,
                "candidate_elapsed_s": candidate_elapsed,
                "baseline_solver": old[1]["solver"],
                "candidate_lm_nfev": new[1]["lm_nfev"],
                "baseline_residual": old[1]["residual"],
                "candidate_residual": new[1]["residual"],
                "candidate_force_residual": new[1]["force_residual"],
                "candidate_dissipation": new[1]["dissipation"],
                "max_velocity_difference": float(np.max(np.abs(old[0]-new[0]))),
                "max_reaction_difference": float(np.max(np.abs(
                    np.asarray(old[1]["reactions"])-np.asarray(new[1]["reactions"])))),
                "baseline_matches_captured_velocity": bool(np.allclose(
                    old[0], captured_velocity, rtol=0, atol=1e-15)),
                "baseline_matches_captured_reactions": bool(np.allclose(
                    old[1]["reactions"], captured_reactions, rtol=0, atol=1e-15)),
            })
    finally:
        gate._project, gate._residual = old_project, old_residual
    record = {"diagnostic_only": True, "rows": rows,
              "all_candidate_gates_passed": all(r["candidate_passed"] for r in rows),
              "input_hashes": {str(results_path): sha(results_path),
                               **{x["path"]: x["sha256"] for x in profile["top_systems"]}},
              "source_hashes": {str(p): sha(p) for p in (Path(__file__),
                                Path(gate.__file__), Path(baseline.__file__),
                                Path(kernels.__file__))},
              "claim_boundary": "Frozen contact-system microbenchmark only; no trajectory or release validation."}
    result_path = OUT / "results.json"
    result_path.write_text(json.dumps(record, indent=2))
    (OUT / "completion.json").write_text(json.dumps({
        "status": "complete_benchmarked", "results_sha256": sha(result_path)}, indent=2))
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
