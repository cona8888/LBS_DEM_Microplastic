import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pair_operator_mfs_v3 as pair


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--n-body", type=int, default=768)
    parser.add_argument("--n-grain", type=int, default=384)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    axes = np.array([0.0002, 0.00005, 0.00005]) / 0.000385
    rows = []
    started = time.perf_counter()
    for degrees in (0, 45, 90):
        operator, health = pair.solve(axes, 0.2, np.deg2rad(degrees), args.n_body, args.n_grain)
        operator_path = out / f"operator_{degrees:02}.npy"
        np.save(operator_path, operator)
        checks = {
            "boundary_error": health["boundary_error_max"] <= 0.002,
            "surface_source_balance": health["surface_source_balance_max"] <= 0.002,
            "reciprocity": health["reciprocity_residual"] <= 0.002,
            "positive_dissipation": health["minimum_symmetric_eigenvalue"] > 0,
        }
        row = {
            "angle_degrees": degrees,
            "n_body": args.n_body,
            "n_grain": args.n_grain,
            "health": health,
            "checks": checks,
            "passed": all(checks.values()),
            "operator_sha256": sha(operator_path),
        }
        rows.append(row)
        print(json.dumps(row), flush=True)
    sources = [Path(__file__), Path(pair.__file__)]
    result = {
        "completed": True,
        "passed": all(row["passed"] for row in rows),
        "rows": rows,
        "runtime_seconds": time.perf_counter() - started,
        "scope": "equal-area reference pair operators at clearance/grain-radius 0.2; no trajectory promotion",
        "hashes": {str(path.resolve()): sha(path) for path in sources},
    }
    (out / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({"passed": result["passed"], "seconds": result["runtime_seconds"]}))


if __name__ == "__main__":
    main()
