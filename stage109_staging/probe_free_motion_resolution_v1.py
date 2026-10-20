"""Instantaneous force-free AR4 response to matched CPD2/CPD4 fields."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage109_staging"), str(ROOT / "stage37_staging")]
import probe_matched_start_fields_v1 as prior
import transport_contact as mechanics

PRIOR = prior.OUT / "results.json"
STARTS = prior.STARTS
PROTOCOL = prior.PROTOCOL
OBS = ROOT / "stage108_runs/first_iid_fibre_2pv_01/manifest.json"
OUT = ROOT / "stage109_evaluations/seed2_free_motion_resolution_probe_20260914"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def stats(rows):
    if not rows:
        return {"count": 0}
    v = np.asarray([row["free_translation_difference_over_u0"] for row in rows])
    w = np.asarray([row["fibre_angular_rate_difference_over_u0_per_dx2"] for row in rows])
    return {"count": len(rows),
            "translation_median": float(np.median(v)),
            "translation_p90": float(np.quantile(v, .9)),
            "fibre_angular_rate_median": float(np.median(w)),
            "fibre_angular_rate_p90": float(np.quantile(w, .9)),
            "fibre_angular_rate_max": float(w.max())}


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    previous = read(PRIOR)
    completion = read(prior.OUT / "completion.json")
    protocol = read(PROTOCOL)
    manifest = read(OBS)
    if (sha(PRIOR) != completion["results_sha256"]
            or previous["status"] != "matched_start_centre_flow_probe_only"
            or sha(mechanics.__file__) != manifest["source_hashes"][str(Path(mechanics.__file__).resolve())]):
        raise RuntimeError("prior probe or physical core drift")
    for section in ("source_hashes", "input_hashes"):
        for path, digest in previous[section].items():
            if sha(path) != digest:
                raise RuntimeError(f"prior lineage drift: {path}")
    u0 = protocol["flow"]["reference_u0_m_s"]
    a, b, _ = protocol["prolate_semiaxes_m"]
    mu = protocol["fluid"]["dynamic_viscosity_Pa_s"]
    rho_p = protocol["particle_density_kg_m3"]
    rho_f = protocol["fluid"]["density_kg_m3"]
    gravity = protocol["gravity_m_s2"]
    f2 = prior.field(prior.BASE2, prior.RUN2, u0)
    f4 = prior.field(prior.BASE4, prior.RUN4, u0)
    source_starts = read(STARTS)
    if len(source_starts) != len(previous["rows"]):
        raise RuntimeError("start/result count drift")
    rows = []
    for start, old in zip(source_starts, previous["rows"]):
        if start["id"] != old["sample_id"]:
            raise RuntimeError("start/result order drift")
        position, direction = start["position_m"], start["orientation"]
        u2, g2 = f2.sample(position)
        u4, g4 = f4.sample(position)
        q2, _ = mechanics.free_motion(direction, g2, u2, a, b, mu, rho_p, rho_f, gravity)
        q4, _ = mechanics.free_motion(direction, g4, u4, a, b, mu, rho_p, rho_f, gravity)
        if not (np.isfinite(q2).all() and np.isfinite(q4).all()):
            raise RuntimeError("nonfinite free-motion response")
        if not np.allclose(q2[:3] - q4[:3], u2 - u4, atol=1e-14, rtol=0):
            raise RuntimeError("unexpected change in nonhydrodynamic translation")
        rows.append({
            "sample_id": start["id"],
            "centre_clearance_to_nearest_grain_m": old["centre_clearance_to_nearest_grain_m"],
            "free_translation_difference_over_u0": float(np.linalg.norm(q2[:3] - q4[:3]) / u0),
            "fibre_angular_rate_difference_over_u0_per_dx2":
                float(np.linalg.norm((q2[3:] - q4[3:]) / a) * f2.dx / u0),
        })
    threshold = previous["clearance_split_m"]
    near = [row for row in rows if row["centre_clearance_to_nearest_grain_m"] <= threshold]
    far = [row for row in rows if row["centre_clearance_to_nearest_grain_m"] > threshold]
    result = {
        "status": "instantaneous_free_motion_resolution_probe_only",
        "all": stats(rows),
        "near_grain_centres": stats(near),
        "farther_centres": stats(far),
        "rows": rows,
        "source_hashes": {str(Path(__file__).resolve()): sha(__file__),
                          str(Path(prior.__file__).resolve()): sha(prior.__file__),
                          str(Path(mechanics.__file__).resolve()): sha(mechanics.__file__)},
        "input_hashes": {str(path): sha(path) for path in
                         (PRIOR, prior.OUT / "completion.json", PROTOCOL, STARTS, OBS,
                          prior.BASE2, prior.BASE4, prior.RUN2 / "final_fields.npz",
                          prior.RUN4 / "final_fields.npz")},
        "claim_boundary": "One-packing U0 instantaneous force-free hydrodynamic response at initial centres. No contact, inertia, trajectory, release, high/low-flow physics, or model validation result.",
    }
    OUT.mkdir(parents=True, exist_ok=False)
    write(OUT / "results.json", result)
    write(OUT / "completion.json", {"status": result["status"],
                                    "results_sha256": sha(OUT / "results.json")})
    print(json.dumps({"status": result["status"], "all": result["all"],
                      "near": result["near_grain_centres"]}))


if __name__ == "__main__":
    main()
