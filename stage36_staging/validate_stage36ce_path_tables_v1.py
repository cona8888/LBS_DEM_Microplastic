"""Integrate Stage36CD tables and test fresh poses with direct solves.

This is a qualification experiment, not a calibrated release result.  Motion
is interpolated only along each case's tabulated path; new direct solves are
made at positions absent from the training table and at the updated path pose.
"""
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator

import open_grains_ellipsoid_v1 as flow
import planar_passage_stepper_v1 as stepper

R = Path(__file__).resolve().parents[1]
T = R / "stage36_evaluations/stage36cd_path_tables_20260911/table_01"
O = R / "stage36_evaluations/stage36ce_fresh_path_validation_20260911/run_01"
O.mkdir(parents=True, exist_ok=False)

validation_x = [-2.1, 0.7, 3.5]
contract = {
    "role": "fresh-pose qualification of path-specific interpolation",
    "training_x": [-4.2, -2.8, -1.4, 0.0, 1.4, 2.8, 4.2],
    "validation_x": validation_x,
    "integration_dx": [0.2, 0.1, 0.05],
    "direct_resolution": "384 for |x| <= 1.4; 256 otherwise",
    "gates": {
        "axial_relative_error_max": 0.01,
        "transverse_absolute_error_max": 0.002,
        "angular_absolute_error_max": 0.003,
        "boundary_error_max": 0.001,
        "force_free_residual_max": 1e-10,
        "fine_vs_medium_event_time_relative_max": 0.002,
    },
    "interpretation": "passing supports this bounded 12-case benchmark only; it is not porous-soil validation",
}
(O / "contract.json").write_text(json.dumps(contract, indent=2))

sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
inputs = [Path(__file__), Path(flow.__file__), Path(stepper.__file__), T / "results.json", O / "contract.json"]
before = {str(p): sha(p) for p in inputs}
table_summary = json.loads((T / "results.json").read_text())
assert table_summary["passed_provisional"]

rows = []
started = time.perf_counter()
for case in range(1, 13):
    source = json.loads((T / f"case_{case:02}.json").read_text())
    x = np.array([s["x"] for s in source["samples"]], float)
    motion = np.array([s["motion"] for s in source["samples"]], float)
    fits = [PchipInterpolator(x, motion[:, j], extrapolate=False) for j in range(3)]

    def provider(q, y, theta):
        # y and theta are intentionally not used: this is a path-specific,
        # one-dimensional table whose validity is tested below at updated poses.
        return np.array([f(q) for f in fits], float)

    trajectories = {}
    for dx in contract["integration_dx"]:
        trajectories[str(dx)] = stepper.integrate(
            provider,
            source["axes"],
            source["initial_y"],
            np.deg2rad(source["initial_angle"]),
            dx,
        )
    fine = trajectories["0.05"]
    state = fine["history"]
    sx = np.array([s["x"] for s in state])
    sy = np.array([s["y"] for s in state])
    st = np.unwrap(np.array([s["theta"] for s in state]))
    checks = []
    for q in validation_x:
        y = float(np.interp(q, sx, sy))
        theta = float(np.interp(q, sx, st))
        c, s = np.cos(theta), np.sin(theta)
        M = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
        n = 384 if abs(q) <= 1.4 else 256
        tick = time.perf_counter()
        direct, health = flow.solve([q, y, 0.0], M, n, axes=source["axes"])
        predicted = provider(q, y, theta)
        errors = {
            "axial_relative": float(abs(predicted[0] - direct[0]) / abs(direct[0])),
            "transverse_absolute": float(abs(predicted[1] - direct[1])),
            "angular_absolute": float(abs(predicted[2] - direct[5])),
        }
        passed = (
            errors["axial_relative"] <= 0.01
            and errors["transverse_absolute"] <= 0.002
            and errors["angular_absolute"] <= 0.003
            and max(health["grain_boundary_error"], health["fibre_boundary_error"]) <= 0.001
            and health["force_free_residual"] <= 1e-10
        )
        item = {
            "x": q, "y": y, "theta": theta, "n": n,
            "predicted": predicted.tolist(),
            "direct": [float(direct[0]), float(direct[1]), float(direct[5])],
            "errors": errors, **health, "passed": bool(passed),
            "seconds": time.perf_counter() - tick,
        }
        checks.append(item)
        print(json.dumps({"case": case, "x": q, "passed": bool(passed), "errors": errors}), flush=True)
    times = {k: v["history"][-1]["t"] for k, v in trajectories.items()}
    convergence = abs(times["0.05"] - times["0.1"]) / abs(times["0.05"])
    row = {
        "case": case,
        "shape": source["shape"],
        "initial_y": source["initial_y"],
        "initial_angle": source["initial_angle"],
        "trajectories": trajectories,
        "validation": checks,
        "event_times": times,
        "event_time_fine_vs_medium_relative": float(convergence),
        "passed": bool(all(c["passed"] for c in checks) and convergence <= 0.002),
    }
    rows.append(row)
    (O / f"case_{case:02}.json").write_text(json.dumps(row, indent=2))

checks = {
    "all_fresh_poses_pass": all(c["passed"] for r in rows for c in r["validation"]),
    "all_time_integrations_converged": all(r["event_time_fine_vs_medium_relative"] <= 0.002 for r in rows),
    "all_terminal_statuses_released": all(r["trajectories"]["0.05"]["status"] == "released" for r in rows),
    "inputs_unchanged": before == {str(p): sha(p) for p in inputs},
}
result = {
    "passed": bool(all(checks.values())),
    "checks": checks,
    "rows": rows,
    "runtime_seconds": time.perf_counter() - started,
    "input_hashes": before,
}
(O / "results.json").write_text(json.dumps(result, indent=2))
print(json.dumps({"passed": result["passed"], "checks": checks, "seconds": result["runtime_seconds"]}), flush=True)
