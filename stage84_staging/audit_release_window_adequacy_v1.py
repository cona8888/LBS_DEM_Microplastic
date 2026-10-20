"""Dimensionless outlet-distance audit for the frozen Stage55 starts.

This is a design/observability check, not a transport simulation. Required
axial displacement is based on the exact whole-body outlet criterion and
reported relative to the declared mean-flow travel in 0.1 PV. Local pore
velocities and contacts can differ, so this is not a proof of impossibility.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage37_staging"), str(ROOT / "stage40_staging")]
import transport_contact as mechanics
import matrix_case_v1

DESIGN = ROOT / "stage55_designs" / "paired_three_packing_pilot_v1.json"
PAIR = (ROOT / "stage83_runs" / "s2_full_window_pair_20260913" /
        "pair_01" / "results.json")
PAIR_COMPLETION = PAIR.parent / "completion.json"
START_DIR = ROOT / "stage37_runs" / "stage4_farfield_bound_20260912" / "pilot_01"
OUT = ROOT / "stage84_evaluations" / "release_window_adequacy_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def axes(config, shape):
    a, b, _ = config["prolate_semiaxes_m"]
    if shape == "equal_volume_sphere":
        a = b = (a*b*b)**(1/3)
    return a, b


def outlet_gap(x, p, a, b, length):
    return -mechanics.full_exit_function(x, p, a, b, length)


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    config = json.loads(DESIGN.read_text())
    completion = json.loads(PAIR_COMPLETION.read_text())
    if completion["status"] != "complete_passed" or completion["results_sha256"] != sha(PAIR):
        raise RuntimeError("Stage83 paired result binding failed")
    paired = json.loads(PAIR.read_text())
    if not paired["passed"] or len(paired["rows"]) != 2:
        raise RuntimeError("Stage83 paired result incomplete")
    input_hashes = {str(p): sha(p) for p in (DESIGN, PAIR, PAIR_COMPLETION)}
    rows = []
    U = config["target_mean_interstitial_velocity_m_s"]
    pv_window = config["horizon_pore_volumes"]
    for packing in config["packings"]:
        seed = packing["seed"]
        start_path = START_DIR / f"starts_s{seed}.json"
        input_hashes[str(start_path)] = sha(start_path)
        starts = json.loads(start_path.read_text())
        start = next(x for x in starts if x["id"] == packing["start_id"])
        length = matrix_case_v1.load(seed)[2]
        declared_horizon_s = pv_window * length / U
        for shape in config["shapes"]:
            a, b = axes(config, shape)
            initial_gap = outlet_gap(start["position_m"], start["orientation"], a, b, length)
            if initial_gap <= 0:
                raise RuntimeError("frozen start already beyond whole-body outlet")
            row = {
                "packing_seed": seed, "start_id": start["id"], "shape": shape,
                "column_length_m": length,
                "initial_axial_whole_body_outlet_gap_m": initial_gap,
                "mean_flow_travel_in_window_m": U * declared_horizon_s,
                "mean_flow_pore_volumes_required": initial_gap / length,
                "required_to_window_mean_travel_ratio": initial_gap / (U * declared_horizon_s),
                "declared_horizon_s": declared_horizon_s,
                "actual_full_window_result": None,
            }
            if seed == 2:
                case = next(x for x in paired["rows"] if x["shape"] == shape)
                result = case["result"]
                final_gap = outlet_gap(result["position_m"], result["orientation"], a, b, length)
                row["actual_full_window_result"] = {
                    "status": result["status"],
                    "axial_center_displacement_m": result["position_m"][0] - start["position_m"][0],
                    "final_axial_whole_body_outlet_gap_m": final_gap,
                    "final_gap_over_column_length": final_gap / length,
                    "persistent_contact_observed": result["persistent_contact_observed"],
                    "finite_dwell_not_irreversible": result["trap_state"]["interpretation"],
                }
            rows.append(row)
    checks = {
        "six_frozen_start_shape_rows": len(rows) == 6,
        "all_start_gaps_positive": all(r["initial_axial_whole_body_outlet_gap_m"] > 0 for r in rows),
        "all_require_more_than_window_mean_travel": all(
            r["required_to_window_mean_travel_ratio"] > 1 for r in rows),
        "seed2_pair_no_exit": all(
            r["actual_full_window_result"]["status"] == "present_at_horizon"
            for r in rows if r["packing_seed"] == 2),
        "seed2_pair_still_short_of_outlet": all(
            r["actual_full_window_result"]["final_axial_whole_body_outlet_gap_m"] > 0
            for r in rows if r["packing_seed"] == 2),
    }
    checks = {key: bool(value) for key, value in checks.items()}
    record = {
        "passed": all(checks.values()), "checks": checks, "rows": rows,
        "design_decision": "0.1 PV is a short conditional dwell/transport window, not an adequate stand-alone release-fraction observation for these starts.",
        "input_hashes": input_hashes,
        "source_hashes": {str(p): sha(p) for p in (
            Path(__file__), Path(mechanics.__file__), Path(matrix_case_v1.__file__))},
        "claim_boundary": "Mean-flow travel is a dimensional comparator, not an upper bound on local particle velocity or proof that exit cannot occur."
    }
    path = OUT / "results.json"
    path.write_text(json.dumps(record, indent=2))
    (OUT / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if record["passed"] else "complete_failed",
        "results_sha256": sha(path)}, indent=2))
    print(json.dumps({"passed": record["passed"], "checks": checks,
                      "rows": [{"seed": r["packing_seed"], "shape": r["shape"],
                                "required_pv_at_mean_flow": r["mean_flow_pore_volumes_required"],
                                "ratio_to_window": r["required_to_window_mean_travel_ratio"],
                                "final_gap_m": (r["actual_full_window_result"] or {}).get(
                                    "final_axial_whole_body_outlet_gap_m")}
                               for r in rows]}, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
