"""Stage145: load the sealed frozen contact systems, verifying their hashes.

Sources, both already immutable in the project record:
  * Stage142 `signed_gap_endpoint_diagnosis_20260919/probe_01/results.json`
    -- seven sphere endpoint systems, rows[*]['system'] = [v, M, J, g, dt, mu, tol, maxiter]
  * Stage141 `fibre_identical_system_branch_check_20260918/probe_01/results.json`
    -- two fibre "identical system" states, systems[*]['inputs'] in the same layout

Nothing here recomputes geometry; the stored matrices are used exactly as sealed.
"""
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPHERE = ROOT / "stage142_evaluations/signed_gap_endpoint_diagnosis_20260919/probe_01/results.json"
FIBRE = ROOT / "stage141_evaluations/fibre_identical_system_branch_check_20260918/probe_01/results.json"

# recorded at Stage145 preparation; the run refuses to proceed if either drifts
SPHERE_SHA = "efc844396b52a8169fac25fd3045f574041938e8c9186c7f828f9ae6abfd3eab"
FIBRE_SHA = "21c8bb0835cff6ba11daeff26361d59a582c8d46984001ecf82e8aa1980befc9"

# Back-computed from the Stage142 certificates, where gap_budget_m = 64 eps/(1-64 eps) * L.
# Both probes come from the same CPD6 field family.
CELL_LENGTH_M = 4.680605809919908e-3


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def _as_system(raw):
    v, M, J, g, dt, mu, tol, maxiter = raw
    return {"vfree": np.array(v, float), "mobility": np.array(M, float),
            "jacobian": np.array(J, float), "gaps": np.array(g, float),
            "dt": float(dt), "mu": float(mu), "tol": float(tol), "maxiter": int(maxiter)}


def load(verify=True):
    """Returns (sphere_systems, fibre_systems, source_hashes)."""
    hashes = {str(SPHERE): sha(SPHERE), str(FIBRE): sha(FIBRE)}
    if verify:
        require(hashes[str(SPHERE)] == SPHERE_SHA, "Stage142 probe evidence drifted")
        require(hashes[str(FIBRE)] == FIBRE_SHA, "Stage141 probe evidence drifted")
    sphere = []
    for row in json.loads(SPHERE.read_text())["rows"]:
        s = _as_system(row["system"])
        s["id"] = row["id"]
        s["grain_ids"] = [int(d["grain"]) for d in row.get("geometry_diagnostic", [])]
        s["legacy_outcomes"] = {x["solver"]: {"returned": x["returned"], "passed": x["passed"],
                                              "error": x.get("error")} for x in row["solvers"]}
        sphere.append(s)
    fibre = []
    for index, entry in enumerate(json.loads(FIBRE.read_text())["systems"]):
        s = _as_system(entry["inputs"])
        s["id"] = f"fibre_identical_{index}"
        s["recorded"] = {
            "velocity_difference_over_reference_flow": entry["velocity_difference_over_reference_flow"],
            "original_velocity": entry["original_velocity"],
            "alternative_velocity": entry["alternative_velocity"],
            "original_solver": entry["original_health"]["solver"],
            "alternative_solver": entry["alternative_health"]["solver"],
            "original_residual": entry["original_health"]["residual"],
            "alternative_residual": entry["alternative_health"]["residual"],
            "jacobian_singular_values": entry["jacobian_singular_values"],
        }
        fibre.append(s)
    return sphere, fibre, hashes


def random_systems(count=200, seed=145):
    """Well-posed random contact systems for the inertness proof, at project scales."""
    rng = np.random.default_rng(seed)
    a, b, rg = 2.0e-4, 5.0e-5, 2.0e-4
    out = []
    for _ in range(count):
        n = int(rng.integers(1, 4))
        rows = []
        for _k in range(n):
            normal = rng.normal(size=3)
            normal /= np.linalg.norm(normal)
            lever = -rg * normal + rng.normal(size=3) * 1e-5
            frame = np.vstack([normal, np.zeros(3), np.zeros(3)])
            axis = np.eye(3)[np.argmin(abs(normal))]
            t = np.cross(normal, axis)
            t /= np.linalg.norm(t)
            frame = np.vstack([normal, t, np.cross(normal, t)])
            rows.extend(np.c_[frame, np.cross(lever, frame) / a])
        J = np.array(rows).reshape(3 * n, 6)
        G = rng.normal(size=(6, 6)) * 0.2 + np.eye(6)
        S = G @ G.T
        D = np.diag([4.5e3] * 3 + [5.0e5] * 3) ** 0.5
        M = D @ S @ D / np.trace(S) * 6
        M = 0.5 * (M + M.T)
        load = np.r_[rng.normal(size=3) * 1e-8, rng.normal(size=3) * 1e-13]
        gap_scale = rng.choice([0.0, 1e-19, 1e-12, 1e-8])
        out.append({"id": f"random_{len(out):03d}", "vfree": M @ load, "mobility": M, "jacobian": J,
                    "gaps": rng.normal(size=n) * gap_scale, "dt": float(rng.choice([2e-5, 5e-6, 1e-6])),
                    "mu": float(rng.choice([0.0, 0.3, 0.6])), "tol": 1e-10, "maxiter": 25000})
    return out
