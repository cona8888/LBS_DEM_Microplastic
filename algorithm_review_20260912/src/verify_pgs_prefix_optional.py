"""Small comparison gate for the unpromoted 200-PGS-prefix candidate."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
import scipy
import contact_pgs_prefix_optional as candidate
from probe_analytic_contact_v1 import captured
from verify_analytic_contact_v1 import manufactured, independent_gates

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="pgs_prefix_optional_01")
    options = parser.parse_args()
    out = ROOT / "algorithm_review_20260912/evidence" / options.output
    out.mkdir(parents=True, exist_ok=False)
    cases = manufactured()
    cases.append(("zero_contacts", [np.ones(6), np.eye(6), np.zeros((0, 6)),
                                   np.zeros(0), .01, .3, 1e-10, 25000], np.ones(6)))
    cases.append(("four_contacts_direct_baseline", [np.ones(6), np.eye(6),
                  np.tile(np.eye(6)[:3], (4, 1)), np.zeros(4), .01, .3, 1e-10, 25000], np.ones(6)))
    ordinary = []
    for name, args, expected in cases:
        v, health = candidate.solve_prepared(*args)
        baseline_v, baseline_health = candidate.analytic.stage53._solve(*args)
        identical = bool(np.array_equal(v, baseline_v) and health == baseline_health)
        gates = independent_gates(args, v, health) if len(args[3]) else {"passed": True}
        ordinary.append({"name": name, "passed": identical and gates["passed"],
                         "velocity_and_full_health_bitwise_equal": identical,
                         "gates": gates, "iterations": health["iterations"]})
    source = ROOT / "algorithm_review_20260912/evidence/contact_primitives_01/results.json"
    reference = json.loads(source.read_text())
    saved = []
    for seed in (1, 2, 3):
        for factor in (1., .5):
            path, args = captured(seed, factor)
            start = time.perf_counter()
            v, health = candidate.solve_prepared(*args)
            elapsed = time.perf_counter()-start
            previous = next(r for r in reference["saved_systems"] if
                            r["packing_seed"] == seed and r["dt_factor"] == factor)
            gates = independent_gates(args, v, health)
            velocity_shift = np.linalg.norm(v-np.asarray(previous["velocity"]))/max(np.linalg.norm(v), 1e-15)
            saved.append({"packing_seed": seed, "dt_factor": factor,
                          "passed": bool(gates["passed"] and velocity_shift < 1e-12),
                          "gates": gates, "health": health, "wall_seconds": elapsed,
                          "velocity_relative_shift_from_verified_analytic": float(velocity_shift),
                          "input_sha256": sha(path)})
    checks = {"seventeen_manufactured_and_two_dispatch_cases_exactly_preserved": all(r["passed"] for r in ordinary),
              "all_six_captured_systems_pass_unchanged_gates": all(r["passed"] for r in saved),
              "analytic_hard_case_branch_exercised": candidate.stats()["analytic_passes"] == 6}
    result = {"passed": all(checks.values()), "checks": checks, "ordinary": ordinary,
              "saved_systems": saved, "candidate_stats": candidate.stats(),
              "source_hashes": {str(Path(p).resolve()): sha(p) for p in
                                (__file__, candidate.__file__, candidate.analytic.__file__)},
              "reference_evidence_sha256": sha(source),
              "environment": {"python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__},
              "scope": "Optional candidate primitive comparison only. Not promoted; matrix trajectories and refinement required."}
    path = out / "results.json"
    path.write_text(json.dumps(result, indent=2))
    (out / "completion.json").write_text(json.dumps({"status": "complete_passed" if result["passed"] else "complete_failed",
                                                   "results_sha256": sha(path)}, indent=2))
    print(json.dumps({"passed": result["passed"], "checks": checks, "stats": candidate.stats()}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
