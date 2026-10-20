"""Cost replay of the real three-grain state using cross-step reaction caching."""
import argparse, hashlib, json, time
from pathlib import Path
import trajectory_cached_trap_v1 as trajectory
import matrix_case_v1

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    parent_path = ROOT / "stage39_evaluations/matrix_profile_01/results.json"
    parent = json.loads(parent_path.read_text())["result"]
    field, geometry, length, spacing, inputs = matrix_case_v1.load(2)
    rows = []
    for friction in (0.0, 0.3):
        started = time.perf_counter()
        result = trajectory.integrate(
            field, geometry, parent["position_m"], parent["orientation"],
            parent["velocity_generalized"], 2e-4, 5e-5, 0.001002,
            1380, 998.2, [0, 0, -9.80665], friction, length, 0.02,
            added_mass_fraction=1, cutoff_ratio=0.2, roughness_ratio=0.01,
            displacement_fraction=0.1, relaxation_fraction=0.5,
            max_dt=0.01, max_steps=100000, wall_budget=60,
        )
        rows.append({"friction": friction, "external_runtime_s": time.perf_counter()-started,
                     "result": result})
    checks = {
        "both_advance_full_interval": all(row["result"]["status"] == "present_at_horizon" for row in rows),
        "no_penetration": min(row["result"]["minimum_gap_m"] for row in rows) >= -5e-10,
        "closures": max(row["result"]["max_momentum_residual"] for row in rows) <= 1e-8
                    and max(row["result"]["max_contact_residual"] for row in rows) <= 1e-8,
        "reynolds_in_domain": max(row["result"]["max_reynolds"] for row in rows) <= 3,
        "cache_populated": all(row["result"]["cached_reaction_count"] > 0 for row in rows),
    }
    sources = [Path(__file__), Path(trajectory.__file__), Path(trajectory.inertial.__file__),
               Path(matrix_case_v1.__file__), parent_path, *inputs]
    result = {"completed": True, "passed": all(checks.values()),
              "checks": {key: bool(value) for key, value in checks.items()}, "rows": rows,
              "input_hashes": {str(path.resolve()): sha(path) for path in sources},
              "comparison_parent": "../../stage39_evaluations/matrix_failure_diagnostic_01/results.json",
              "claim_boundary": "real-state cost replay only; not a release result"}
    (output / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({"passed": result["passed"], "checks": result["checks"],
                      "rows": [{"friction": row["friction"], "status": row["result"]["status"],
                                "steps": row["result"]["steps"], "runtime_s": row["external_runtime_s"],
                                "contact_iterations": row["result"]["total_contact_iterations"]}
                               for row in rows]}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
