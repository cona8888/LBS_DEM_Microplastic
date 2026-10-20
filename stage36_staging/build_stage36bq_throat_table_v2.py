"""Qualified centreline speed table for a symmetric two-grain throat.

This is a verification/pre-comparison artifact.  It does not claim a soil-scale
release fraction and it does not compare shapes.
"""
import hashlib
import json
import platform
import time
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator

import open_grains_fibre_v2 as flow


ROOT = Path(__file__).resolve().parents[1]
PRIOR = ROOT / "stage36_evaluations/stage36bp_throat_20260911/verification_02/results.json"
FAILED = ROOT / "stage36_evaluations/stage36bq_throat_table_20260911/table_01/results.json"
OUT = ROOT / "stage36_evaluations/stage36bq_throat_table_20260911/table_02"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if OUT.exists():
    raise FileExistsError(OUT)
OUT.mkdir(parents=True)

contract = {
    "training_abs_x": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.6, 4.2],
    "heldout_abs_x": [0.75, 2.75, 3.9],
    "new_source_count": 256,
    "interpolator": "shape-preserving piecewise cubic Hermite (PCHIP)",
    "grains": [[0.0, -1.5, 0.0], [0.0, 1.5, 0.0]],
    "body_axes": [0.2, 0.1, 0.1],
    "orientation": "major axis parallel to x",
    "boundary_limit": 0.001,
    "interpolation_limit": 0.001,
    "force_free_limit": 1e-10,
    "symmetry_residual_limit": 1e-4,
    "scope": "symmetric centreline only; no contact, arbitrary pose, shape comparison, or validation claim",
}
(OUT / "contract.json").write_text(json.dumps(contract, indent=2))

inputs = [Path(__file__), Path(flow.__file__), PRIOR, FAILED, OUT / "contract.json"]
input_hashes_before = {str(p): sha(p) for p in inputs}
prior = json.loads(PRIOR.read_text())
failed = json.loads(FAILED.read_text())
if not prior["passed"] or failed["passed"]:
    raise ValueError("unexpected lineage status")

prior_anchor = next(r for r in prior["rows"] if r["n"] == 384)
fine_anchor = next(r for r in failed["rows"] if r["abs_x"] == 1.5 and r["n"] == 384)
rows = [
    {
        "abs_x": 0.0,
        "n": 384,
        "motion": prior_anchor["motion"],
        "grain_boundary_error": prior_anchor["grain_boundary_error"],
        "fibre_boundary_error": prior_anchor["fibre_boundary_error"],
        "force_free_residual": prior_anchor["force_free_residual"],
        "source": "hash-bound Stage36BP fine anchor",
        "role": "training",
    },
    {
        "abs_x": 1.5,
        "n": 384,
        "motion": fine_anchor["motion"],
        "grain_boundary_error": fine_anchor["grain_boundary_error"],
        "fibre_boundary_error": fine_anchor["fibre_boundary_error"],
        "force_free_residual": fine_anchor["force_free_residual"],
        "source": "hash-bound failed-table fine solve (solve itself qualified)",
        "role": "training",
    },
]

start = time.perf_counter()
for role, positions in (
    ("training", [0.5, 1.0, 2.0, 2.5, 3.0, 3.6, 4.2]),
    ("heldout", contract["heldout_abs_x"]),
):
    for x in positions:
        z, health = flow.solve([x, 0.0, 0.0], np.eye(3), contract["new_source_count"])
        row = {"abs_x": x, "n": contract["new_source_count"], "motion": z.tolist(), **health,
               "source": "new", "role": role}
        rows.append(row)
        print(json.dumps(row), flush=True)

training = sorted((r for r in rows if r["role"] == "training"), key=lambda r: r["abs_x"])
x_train = np.array([r["abs_x"] for r in training])
u_train = np.array([r["motion"][0] for r in training])
interpolator = PchipInterpolator(x_train, u_train)
heldout = sorted((r for r in rows if r["role"] == "heldout"), key=lambda r: r["abs_x"])
for row in heldout:
    row["interpolated_axial_speed"] = float(interpolator(row["abs_x"]))
    row["relative_interpolation_error"] = abs(row["interpolated_axial_speed"] - row["motion"][0]) / abs(row["motion"][0])

input_hashes_after = {str(p): sha(p) for p in inputs}
all_rows = training + heldout
checks = {
    "lineage_status": prior["passed"] and not failed["passed"],
    "input_hashes_unchanged": input_hashes_before == input_hashes_after,
    "boundary": all(max(r["grain_boundary_error"], r["fibre_boundary_error"]) < contract["boundary_limit"] for r in all_rows),
    "force_free": all(r["force_free_residual"] < contract["force_free_limit"] for r in all_rows),
    "symmetry": max(float(np.linalg.norm(np.asarray(r["motion"])[1:])) for r in all_rows) < contract["symmetry_residual_limit"],
    "heldout_interpolation": all(r["relative_interpolation_error"] < contract["interpolation_limit"] for r in heldout),
    "positive_speed": bool(np.all(u_train > 0.0)),
}
np.savez_compressed(OUT / "table.npz", abs_x=x_train, axial_speed=u_train)
result = {
    "checks": checks,
    "passed": all(checks.values()),
    "rows": all_rows,
    "max_interpolation_error": max(r["relative_interpolation_error"] for r in heldout),
    "max_boundary_error": max(max(r["grain_boundary_error"], r["fibre_boundary_error"]) for r in all_rows),
    "max_symmetry_residual": max(float(np.linalg.norm(np.asarray(r["motion"])[1:])) for r in all_rows),
    "runtime_seconds": time.perf_counter() - start,
    "input_hashes": input_hashes_before,
    "table_hash": sha(OUT / "table.npz"),
    "python": platform.python_version(),
    "production_promoted": False,
}
(OUT / "results.json").write_text(json.dumps(result, indent=2))
print(json.dumps({"checks": checks, "max_interpolation_error": result["max_interpolation_error"],
                  "max_boundary_error": result["max_boundary_error"]}, indent=2))
