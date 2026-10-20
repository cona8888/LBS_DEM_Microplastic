"""Compare accepted CPD2/CPD4 clean flow at frozen seed-2 particle centres."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage39_staging"))
import wall_field_v1

BASE2 = ROOT / "stage31_designs/stage31d_replicated_nested_cpd2_geometry_20260826/geometry_01/s31b_n216_s2_clean/geometry_cpd2.npz"
RUN2 = ROOT / "stage31_runs/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_screen_01/stage31e_s31b_n216_s2_clean_cpd2"
BASE4 = ROOT / "stage31_designs/stage31f_selected_replicated_cpd4_20260827/geometry_01/s31b_n216_s2_clean/geometry_cpd4.npz"
RUN4 = ROOT / "stage31_runs/stage31f_selected_replicated_cpd4_20260827/gpu_confirmation_01/stage31f_s31b_n216_s2_clean_cpd4"
G4_COMPLETION = BASE4.parents[1] / "completion.json"
STARTS = ROOT / "stage95_designs/common_admissible_population_01/starts_s2.json"
PROTOCOL = ROOT / "stage109_designs/shape_flow_protocol_20260914/protocol.json"
OUT = ROOT / "stage109_evaluations/seed2_matched_start_field_probe_20260914"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def field(geometry_path, run_path, target):
    geometry = np.load(geometry_path)
    data = np.load(run_path / "final_fields.npz")
    if not np.array_equal(geometry["phase"], data["phase"]):
        raise RuntimeError("flow/geometry phase mismatch")
    fluid = np.asarray(data["phase"]).transpose(2, 1, 0) == 0
    velocity = np.asarray(data["velocity_xyz_lu"], dtype=float).transpose(0, 3, 2, 1)
    if np.any(velocity[:, ~fluid] != 0):
        raise RuntimeError("nonzero solid-cell velocity")
    velocity *= target / float(velocity[0, fluid].mean())
    return wall_field_v1.WallCellField(velocity, float(geometry["spacing_m"][0]), fluid)


def statistics(rows):
    if not rows:
        return {"count": 0}
    vel = np.asarray([row["velocity_difference_over_u0"] for row in rows])
    grad = np.asarray([row["gradient_frobenius_difference_over_u0_per_dx2"] for row in rows])
    return {"count": len(rows), "velocity_median": float(np.median(vel)),
            "velocity_p90": float(np.quantile(vel, .9)),
            "velocity_max": float(np.max(vel)),
            "gradient_median": float(np.median(grad)),
            "gradient_p90": float(np.quantile(grad, .9))}


def main():
    if OUT.exists():
        raise FileExistsError(OUT)
    protocol = read(PROTOCOL)
    protocol_completion = read(PROTOCOL.with_name("completion.json"))
    r2, r4 = read(RUN2 / "record.json"), read(RUN4 / "record.json")
    c4 = read(G4_COMPLETION)
    bound = c4["artifacts"]["s31b_n216_s2_clean"]
    if (sha(PROTOCOL) != protocol_completion["protocol_sha256"]
            or sha(STARTS) != protocol["input_hashes"][str(STARTS)]
            or not r2["passed"] or not r2["converged"]
            or not r4["passed"] or not r4["converged"] or not c4["passed"]
            or sha(BASE2) != bound["source_cpd2_geometry_sha256"]
            or sha(BASE4) != bound["geometry_sha256"]
            or sha(RUN2 / "final_fields.npz") != r2["artifacts"]["final_fields_npz_sha256"]
            or sha(RUN4 / "final_fields.npz") != r4["artifacts"]["final_fields_npz_sha256"]):
        raise RuntimeError("frozen field/start lineage drift")
    g2, g4 = np.load(BASE2), np.load(BASE4)
    if (not np.array_equal(g2["sand_centres_m"], g4["sand_centres_m"])
            or not np.array_equal(g2["sand_radii_m"], g4["sand_radii_m"])
            or not np.isclose(float(g2["spacing_m"][0]), 2 * float(g4["spacing_m"][0]))):
        raise RuntimeError("unmatched physical grain geometry")
    u0 = protocol["flow"]["reference_u0_m_s"]
    f2 = field(BASE2, RUN2, u0)
    f4 = field(BASE4, RUN4, u0)
    length = float(g2["cell_length_m"][0])
    centers = np.asarray(g2["sand_centres_m"])
    radii = np.asarray(g2["sand_radii_m"])
    starts = read(STARTS)
    if len(starts) != 256 or [s["id"] for s in starts] != list(range(256)):
        raise RuntimeError("start count/order drift")
    rows = []
    for start in starts:
        p = np.asarray(start["position_m"], dtype=float)
        delta = np.abs(centers - p)
        delta = np.minimum(delta, length - delta)
        clearance = float(np.min(np.linalg.norm(delta, axis=1) - radii))
        v2, d2 = f2.sample(p)
        v4, d4 = f4.sample(p)
        rows.append({
            "sample_id": int(start["id"]),
            "centre_clearance_to_nearest_grain_m": clearance,
            "velocity_difference_over_u0": float(np.linalg.norm(v2 - v4) / u0),
            "gradient_frobenius_difference_over_u0_per_dx2":
                float(np.linalg.norm(d2 - d4) * f2.dx / u0),
            "cpd2_speed_over_u0": float(np.linalg.norm(v2) / u0),
            "cpd4_speed_over_u0": float(np.linalg.norm(v4) / u0),
        })
    threshold = 2 * f2.dx
    near = [row for row in rows if row["centre_clearance_to_nearest_grain_m"] <= threshold]
    far = [row for row in rows if row["centre_clearance_to_nearest_grain_m"] > threshold]
    result = {
        "status": "matched_start_centre_flow_probe_only",
        "packing_seed": 2,
        "flow_factor": 1.0,
        "clearance_split_m": threshold,
        "all": statistics(rows),
        "near_grain_centres": statistics(near),
        "farther_centres": statistics(far),
        "rows": rows,
        "source_hashes": {str(Path(__file__).resolve()): sha(__file__),
                          str(Path(wall_field_v1.__file__).resolve()): sha(wall_field_v1.__file__)},
        "input_hashes": {str(p): sha(p) for p in (PROTOCOL, PROTOCOL.with_name("completion.json"), STARTS,
                                                  BASE2, BASE4, RUN2 / "record.json", RUN4 / "record.json",
                                                  RUN2 / "final_fields.npz", RUN4 / "final_fields.npz",
                                                  G4_COMPLETION)},
        "claim_boundary": "Exact same seed-2 initial centres and wall-field interpolation at U0 only. It does not test particle-surface velocity, lubrication/contact response, trajectories, independent packings, or 0.5/2 U0 flow physics.",
    }
    OUT.mkdir(parents=True, exist_ok=False)
    write(OUT / "results.json", result)
    write(OUT / "completion.json", {"status": result["status"],
                                    "results_sha256": sha(OUT / "results.json")})
    print(json.dumps({"status": result["status"], "all": result["all"],
                      "near": result["near_grain_centres"], "far": result["farther_centres"]}))


if __name__ == "__main__":
    main()
