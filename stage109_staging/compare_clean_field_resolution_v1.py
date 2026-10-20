"""Matched seed-2 clean CPD2/CPD4 field comparison; excludes mixed wall blocks."""
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE2 = ROOT / "stage31_designs/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_01/s31b_n216_s2_clean/geometry_cpd2.npz"
RUN2 = ROOT / "stage31_runs/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_screen_01/stage31e_s31b_n216_s2_clean_cpd2"
BASE4 = ROOT / "stage31_designs/stage31f_selected_replicated_cpd4_20260827/geometry_01/s31b_n216_s2_clean/geometry_cpd4.npz"
RUN4 = ROOT / "stage31_runs/stage31f_selected_replicated_cpd4_20260827/gpu_confirmation_01/stage31f_s31b_n216_s2_clean_cpd4"
GEOM4_COMPLETION = BASE4.parents[1] / "completion.json"
OUT = ROOT / "stage109_evaluations/seed2_clean_cpd2_cpd4_field_20260914"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    r2, r4 = read(RUN2 / "record.json"), read(RUN4 / "record.json")
    c4 = read(GEOM4_COMPLETION)
    geom_entry = c4["artifacts"]["s31b_n216_s2_clean"]
    if (not r2["passed"] or not r2["converged"]
            or not r4["passed"] or not r4["converged"] or not c4["passed"]
            or sha(RUN2 / "final_fields.npz") != r2["artifacts"]["final_fields_npz_sha256"]
            or sha(RUN4 / "final_fields.npz") != r4["artifacts"]["final_fields_npz_sha256"]
            or sha(BASE4) != geom_entry["geometry_sha256"]
            or sha(BASE2) != geom_entry["source_cpd2_geometry_sha256"]):
        raise RuntimeError("accepted clean-field/geometry lineage failed")
    g2, g4 = np.load(BASE2), np.load(BASE4)
    f2, f4 = np.load(RUN2 / "final_fields.npz"), np.load(RUN4 / "final_fields.npz")
    if (g4["phase"].shape != tuple(2 * v for v in g2["phase"].shape)
            or not np.array_equal(g2["sand_centres_m"], g4["sand_centres_m"])
            or not np.array_equal(g2["sand_radii_m"], g4["sand_radii_m"])
            or not np.array_equal(g2["phase"], f2["phase"])
            or not np.array_equal(g4["phase"], f4["phase"])
            or not np.isclose(float(g2["spacing_m"][0]), 2 * float(g4["spacing_m"][0]))):
        raise RuntimeError("CPD2/CPD4 clean geometry mismatch")
    fluid2 = g2["phase"] == 0
    fluid4 = g4["phase"] == 0
    n = g2["phase"].shape[0]
    # Each CPD2 cell corresponds exactly to one 2x2x2 CPD4 block.
    full_fluid4 = fluid4.reshape(n, 2, n, 2, n, 2).all(axis=(1, 3, 5))
    mask = fluid2 & full_fluid4
    if not mask.any():
        raise RuntimeError("no common fully fluid cells")
    v2 = np.asarray(f2["velocity_xyz_lu"], dtype=np.float64)
    v4 = np.asarray(f4["velocity_xyz_lu"], dtype=np.float64)
    v2 /= float(v2[0, fluid2].mean())
    v4 /= float(v4[0, fluid4].mean())
    v4_mean = v4.reshape(3, n, 2, n, 2, n, 2).mean(axis=(2, 4, 6))
    a = v2[:, mask]
    b = v4_mean[:, mask]
    error = np.linalg.norm(a - b, axis=0)
    base = np.linalg.norm(b, axis=0)
    result = {
        "status": "matched_interior_field_resolution_diagnostic_only",
        "packing_seed": 2,
        "cpd2_fluid_cells": int(fluid2.sum()),
        "common_fully_fluid_cpd2_cells": int(mask.sum()),
        "common_fully_fluid_fraction_of_cpd2_fluid": float(mask.sum() / fluid2.sum()),
        "rms_vector_difference_over_rms_cpd4_speed": float(np.sqrt(np.mean(error**2) / np.mean(base**2))),
        "median_vector_difference_over_mean_interstitial_speed": float(np.median(error)),
        "p90_vector_difference_over_mean_interstitial_speed": float(np.quantile(error, .90)),
        "p99_vector_difference_over_mean_interstitial_speed": float(np.quantile(error, .99)),
        "input_hashes": {str(p): sha(p) for p in (BASE2, BASE4, RUN2 / "record.json", RUN4 / "record.json",
                                                  RUN2 / "final_fields.npz", RUN4 / "final_fields.npz", GEOM4_COMPLETION)},
        "source_hashes": {str(Path(__file__).resolve()): sha(__file__)},
        "claim_boundary": "Normalized interior velocity-field comparison for one clean packing. Excludes all mixed wall blocks; does not verify near-wall gradients, particle trajectories, other packings or flow scaling at 0.5/2 U0.",
    }
    OUT.mkdir(parents=True, exist_ok=False)
    write(OUT / "results.json", result)
    write(OUT / "completion.json", {"status": result["status"],
                                    "results_sha256": sha(OUT / "results.json")})
    print(json.dumps({k: result[k] for k in ("status", "common_fully_fluid_fraction_of_cpd2_fluid",
                                                 "rms_vector_difference_over_rms_cpd4_speed")}))


if __name__ == "__main__":
    main()
