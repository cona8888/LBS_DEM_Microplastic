"""Identify paired archived starts with <=0.1-L outlet travel at mean flow.

Eligibility uses the exact whole-body outlet support for both frozen shapes.
This is a conditional design preflight, not a release-fraction estimator; the
64 archived starts were quota-balanced by x and clearance stratum.
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "stage37_staging"), str(ROOT / "stage40_staging")]
import transport_contact as mechanics
import matrix_case_v1

DESIGN = ROOT / "stage55_designs" / "paired_three_packing_pilot_v1.json"
START_DIR = ROOT / "stage37_runs" / "stage4_farfield_bound_20260912" / "pilot_01"
OUT = ROOT / "stage85_evaluations" / "near_outlet_preflight_01"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    config = json.loads(DESIGN.read_text())
    a, b, _ = config["prolate_semiaxes_m"]
    r = (a*b*b)**(1/3)
    window_pv = config["horizon_pore_volumes"]
    input_hashes = {str(DESIGN): sha(DESIGN)}
    rows = []
    summary = []
    for packing in config["packings"]:
        seed = packing["seed"]
        start_path = START_DIR / f"starts_s{seed}.json"
        input_hashes[str(start_path)] = sha(start_path)
        starts = json.loads(start_path.read_text())
        length = matrix_case_v1.load(seed)[2]
        eligible = []
        for start in starts:
            gaps = {
                "equal_volume_sphere": -mechanics.full_exit_function(
                    start["position_m"], start["orientation"], r, r, length),
                "prolate_ar4": -mechanics.full_exit_function(
                    start["position_m"], start["orientation"], a, b, length),
            }
            paired_gap_pv = max(gaps.values()) / length
            row = {"seed": seed, "start_id": start["id"],
                   "stratum": start["stratum"],
                   "initial_clearance_ratio": start["initial_minimum_clearance_ratio"],
                   "whole_body_gap_pv_by_shape": {k: v/length for k,v in gaps.items()},
                   "paired_gap_pv": paired_gap_pv,
                   "eligible_for_0p1pv_mean_travel": bool(
                       min(gaps.values()) > 0 and paired_gap_pv <= window_pv)}
            rows.append(row)
            if row["eligible_for_0p1pv_mean_travel"]:
                eligible.append(row)
        summary.append({"seed": seed, "archived_starts": len(starts),
                        "eligible_paired_starts": len(eligible),
                        "eligible_ids": [x["start_id"] for x in eligible],
                        "eligible_strata": {str(k): v for k,v in Counter(
                            tuple(x["stratum"]) for x in eligible).items()}})
    checks = {"all_archived_starts_accounted": len(rows) == 192,
              "three_packings": len(summary) == 3,
              "eligibility_subset": all(x["eligible_paired_starts"] <= 64 for x in summary)}
    checks = {key: bool(value) for key,value in checks.items()}
    record = {"passed": all(checks.values()), "checks": checks,
              "window_pv": window_pv, "summary": summary, "rows": rows,
              "input_hashes": input_hashes,
              "source_hashes": {str(p): sha(p) for p in (
                  Path(__file__), Path(mechanics.__file__), Path(matrix_case_v1.__file__),
                  ROOT / "stage37_staging" / "run_stage4_farfield_bound_v1.py")},
              "claim_boundary": "Archived starts were balanced by axial/clearance strata, not weighted for a matrix-wide release fraction. Eligibility is only a mean-travel comparator, not a guarantee of exit."}
    path = OUT / "results.json"
    path.write_text(json.dumps(record, indent=2))
    (OUT / "completion.json").write_text(json.dumps({
        "status": "complete_passed" if record["passed"] else "complete_failed",
        "results_sha256": sha(path)}, indent=2))
    print(json.dumps({"passed": record["passed"], "summary": summary}, indent=2))
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
