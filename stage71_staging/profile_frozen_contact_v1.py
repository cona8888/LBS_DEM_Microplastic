"""Bounded, read-only CPU profile of the three frozen Stage56 contact systems.

This is a cost diagnostic, not a new physics or release calculation.
"""
import cProfile
import hashlib
import io
import json
import pstats
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage70_staging"))
import inertial_contact_runtime_portfolio_v1 as solver


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output = ROOT / "stage71_evaluations" / "frozen_contact_profile_01"
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for seed in (1, 2, 3):
        source = ROOT / "stage56_runs" / "stage55_fibre_failure_capture_20260912" / "diagnostic_02" / f"s{seed}_prolate_ar4" / "failure_state.npz"
        with np.load(source) as data:
            args = (data["vfree"], data["mobility"], data["jacobian"], data["gaps"],
                    float(data["dt"]) * .5, float(data["friction"]),
                    float(data["tol"]), int(data["maxiter"]))
        profile = cProfile.Profile()
        solver.set_recovery_mode(True)
        start = time.perf_counter()
        try:
            profile.enable()
            velocity, health = solver._solve(*args)
            profile.disable()
        finally:
            solver.set_recovery_mode(False)
        buffer = io.StringIO()
        pstats.Stats(profile, stream=buffer).strip_dirs().sort_stats("cumulative").print_stats(25)
        (output / f"s{seed}_profile.txt").write_text(buffer.getvalue())
        rows.append({"seed": seed, "source_sha256": sha(source),
                     "contacts": len(args[3]), "solver": health["solver"],
                     "runtime_s": time.perf_counter() - start,
                     "contact_residual": health["residual"],
                     "force_residual": health["force_residual"],
                     "velocity_finite": bool(np.isfinite(velocity).all())})
    result = {"rows": rows,
              "passed": all(r["velocity_finite"] and r["contact_residual"] <= 1e-10 and
                            r["force_residual"] <= 1e-8 for r in rows),
              "source_hashes": {
                  str(Path(__file__).resolve()): sha(__file__),
                  str(Path(solver.__file__).resolve()): sha(solver.__file__)},
              "claim_boundary": "Frozen local contact systems only; profile cannot establish trajectory speedup or release."}
    path = output / "results.json"
    path.write_text(json.dumps(result, indent=2))
    (output / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if result["passed"] else "complete_failed",
        "results_sha256": sha(path)}, indent=2))
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
