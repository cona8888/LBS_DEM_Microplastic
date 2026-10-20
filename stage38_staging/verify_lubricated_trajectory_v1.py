import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import trajectory_lubricated_v1 as trajectory

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "stage37_staging"))
import transport_contact as mechanics


class ConstantField:
    def __init__(self, velocity):
        self.velocity = np.asarray(velocity, float)

    def sample(self, _position):
        return self.velocity.copy(), np.zeros((3, 3))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)

    # A sphere starts in exact curved contact with one of two fixed grains.
    # The normal load closes through contact while tangential Coulomb slip and
    # the lubrication-modified mobility are solved together.
    a = b = 0.1
    centre = np.array([5.0, 5.0, 5.0])
    geometry = mechanics.GrainGeometry(
        [[5.0, 5.4, 5.0], [5.0, 4.6, 5.0]], [0.3, 0.3], 10.0
    )
    rows = []
    for fraction in (0.2, 0.1, 0.05):
        result = trajectory.integrate(
            ConstantField([1.0, 0.2, 0.0]), geometry, centre, [1, 0, 0],
            a, b, 1.0, 1.0, 1.0, [0, 0, 0], 0.3,
            outlet=6.0, horizon=10.0, cutoff_ratio=0.2,
            roughness_ratio=0.01, displacement_fraction=fraction,
            angle_limit=0.02, max_dt=1.0,
        )
        rows.append({"displacement_fraction": fraction, "result": result})
    times = [row["result"]["time_s"] for row in rows]
    fine_medium = abs(times[-1] - times[-2]) / abs(times[-1])
    checks = {
        "all_levels_exit": all(row["result"]["status"] == "full_window_exit" for row in rows),
        "curved_multigrain_lubrication_active": all(row["result"]["max_lubrication_contacts"] == 2 for row in rows),
        "contact_active": all(row["result"]["contact_steps"] > 0 for row in rows),
        "no_penetration": all(row["result"]["minimum_gap_m"] >= -1e-6 for row in rows),
        "contact_residual": all(row["result"]["max_contact_residual"] <= 1e-6 for row in rows),
        "force_residual": all(row["result"]["max_force_residual"] <= 1e-6 for row in rows),
        "fine_medium_event_time": fine_medium <= 0.002,
    }
    source_paths = [Path(__file__), Path(trajectory.__file__), Path(mechanics.__file__)]
    checks = {key: bool(value) for key, value in checks.items()}
    result = {
        "completed": True,
        "passed": all(checks.values()),
        "checks": checks,
        "fine_medium_event_time_relative_shift": fine_medium,
        "event_times_s": times,
        "rows": rows,
        "source_hashes": {str(path.resolve()): sha(path) for path in source_paths},
        "scope": "manufactured curved two-grain contact trajectory; no matrix release or experimental validation claim",
    }
    (out / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({"passed": result["passed"], "checks": checks, "times": times, "shift": fine_medium}, indent=2))


if __name__ == "__main__":
    main()
