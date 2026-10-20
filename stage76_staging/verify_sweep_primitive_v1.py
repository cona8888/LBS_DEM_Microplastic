"""Frozen-pose decision and accepted-gap checks for Stage76 early returns."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage40_staging"), str(ROOT / "stage41_staging"),
                str(ROOT / "stage76_staging")]
import matrix_case_v1
import geometry_exact_v1 as original
import geometry_fail_fast_sweep_v1 as fast


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    out = ROOT / "stage76_evaluations" / "sweep_primitive_01"
    out.mkdir(parents=True, exist_ok=False)
    old_path = ROOT / "stage55_runs" / "paired_three_packing_pilot_20260912" / "pilot_01" / "s2_prolate_ar4.json"
    design_path = ROOT / "stage55_designs" / "paired_three_packing_pilot_v1.json"
    old = json.loads(old_path.read_text())["result"]
    design = json.loads(design_path.read_text())
    field, old_geometry, length, dx, inputs = matrix_case_v1.load(2)
    geometry = original.GrainGeometry.from_geometry(old_geometry)
    a, b, _ = design["prolate_semiaxes_m"]
    threshold = -1e-5 * b
    rows = []
    states = old["history"] + [[old["time_s"], *old["position_m"],
                                *old["orientation"], *old["velocity_generalized"]]]
    for index, state in enumerate(states):
        x, p, v = state[1:4], state[4:7], state[7:13]
        for dt in (1e-4, 1e-3, 1e-2):
            try:
                reference_gap = original.swept_gap(geometry, x, p, v, a, b, dt)
                fast_gap = fast.swept_gap(geometry, x, p, v, a, b, dt)
                same_decision = (reference_gap < threshold) == (fast_gap < threshold)
                accepted_exact = reference_gap < threshold or reference_gap == fast_gap
                rows.append({"state": index, "dt_s": dt, "reference_gap_m": reference_gap,
                             "fast_gap_m": fast_gap, "decision_equal": same_decision,
                             "accepted_gap_exact": accepted_exact})
            except (ValueError, RuntimeError) as exc:
                rows.append({"state": index, "dt_s": dt, "exception": str(exc),
                             "decision_equal": False, "accepted_gap_exact": False})
    result = {"passed": all(r["decision_equal"] and r["accepted_gap_exact"] for r in rows),
              "rows": rows, "fast_stats": fast.stats(),
              "input_hashes": {str(old_path): sha(old_path), str(design_path): sha(design_path)},
              "source_hashes": {str(Path(__file__).resolve()): sha(__file__),
                                str(Path(fast.__file__).resolve()): sha(fast.__file__),
                                str(Path(original.__file__).resolve()): sha(original.__file__)},
              "claim_boundary": "Frozen-pose clearance decision and accepted-gap verification only."}
    path = out / "results.json"
    path.write_text(json.dumps(result, indent=2))
    (out / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if result["passed"] else "complete_failed",
        "results_sha256": sha(path)}, indent=2))
    print(json.dumps({"passed": result["passed"], "cases": len(rows),
                      "fast_stats": result["fast_stats"],
                      "failed_rows": [r for r in rows if not r["decision_equal"] or not r["accepted_gap_exact"]][:5]}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
