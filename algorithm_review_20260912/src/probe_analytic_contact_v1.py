"""Print bounded analytic-LM diagnostics for immutable captured systems."""
import json
import time
from pathlib import Path
import numpy as np
import contact_dimensionless_lm_v1 as solver

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "stage56_runs/stage55_fibre_failure_capture_20260912/diagnostic_02"


def captured(seed, dt_factor=1.):
    path = RUN / f"s{seed}_prolate_ar4/failure_state.npz"
    with np.load(path) as data:
        args = [data[k].copy() for k in ("vfree", "mobility", "jacobian", "gaps")]
        args += [float(data["dt"])*dt_factor, float(data["friction"]),
                 float(data["tol"]), int(data["maxiter"])]
    return path, args


def main():
    rows = []
    for seed in (1, 2, 3):
        for factor in (1., .5):
            _, args = captured(seed, factor)
            start = time.perf_counter()
            try:
                velocity, health = solver.solve_analytic_prepared(*args)
                row = {"packing_seed": seed, "dt_factor": factor, "passed": True,
                       "velocity": velocity.tolist(), "health": health}
            except Exception as exc:
                row = {"packing_seed": seed, "dt_factor": factor, "passed": False,
                       "reason": str(exc)}
            row["wall_seconds"] = time.perf_counter() - start
            rows.append(row)
            print(json.dumps(row), flush=True)
    print(json.dumps({"stats": solver.stats()}), flush=True)


if __name__ == "__main__":
    main()
