"""Manufactured end-to-end verification for the inertial trajectory solver."""
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np
import trajectory_inertial_v2 as tr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "stage37_staging"))
import transport_contact as mechanics


class Field:
    def __init__(self, velocity):
        self.velocity = np.asarray(velocity, float)

    def sample(self, position):
        return self.velocity.copy(), np.zeros((3, 3))


class Empty:
    r = np.array([3e-4])

    def contacts(self, *args):
        return []

    def swept_gap(self, *args):
        return np.inf


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    a = b = 5e-5

    uniform = []
    for fraction in (0.2, 0.1, 0.05):
        result = tr.integrate(
            Field([0.001, 0, 0]), Empty(), [0, 0, 0], [1, 0, 0], np.zeros(6),
            a, b, 0.001002, 1380, 998.2, [0, 0, 0], 0, 0.0001, 0.3,
            added_mass_fraction=1, displacement_fraction=fraction,
            relaxation_fraction=fraction, max_dt=0.01,
        )
        uniform.append({"fraction": fraction, "result": result})
    uniform_times = [row["result"]["time_s"] for row in uniform]
    uniform_shift = abs(uniform_times[-1] - uniform_times[-2]) / uniform_times[-1]

    center = np.array([0.005, 0.005, 0.005])
    geometry = mechanics.GrainGeometry(
        [[0.005, 0.00535, 0.005], [0.005, 0.00465, 0.005]],
        [0.0003, 0.0003], 0.01,
    )
    contact = []
    for fraction in (0.2, 0.1, 0.05):
        result = tr.integrate(
            Field([0.001, 0.0002, 0]), geometry, center, [1, 0, 0], np.zeros(6),
            a, b, 0.001002, 1380, 998.2, [0, 0, 0], 0.3, 0.006, 0.02,
            added_mass_fraction=1, displacement_fraction=fraction,
            relaxation_fraction=fraction, max_dt=0.01,
        )
        contact.append({"fraction": fraction, "result": result})
    contact_positions = [np.asarray(row["result"]["position_m"]) for row in contact]
    contact_shift = float(np.linalg.norm(contact_positions[-1] - contact_positions[-2]) / a)
    all_results = [row["result"] for row in uniform + contact]
    contact_results = [row["result"] for row in contact]
    checks = {
        "uniform_full_exit": all(row["result"]["status"] == "full_window_exit" for row in uniform),
        "contact_present_at_horizon": all(row["result"]["status"] == "present_at_horizon" for row in contact),
        "uniform_fine_medium_time_shift": uniform_shift <= 0.002,
        "contact_fine_medium_position_shift_over_body_radius": contact_shift <= 0.002,
        "curved_lubrication_active": all(row["max_lubrication_contacts"] == 2 for row in contact_results),
        "curved_contact_active": all(row["contact_steps"] > 0 for row in contact_results),
        "no_penetration": all(row["minimum_gap_m"] is None or row["minimum_gap_m"] >= -5e-10 for row in all_results),
        "momentum": max(row["max_momentum_residual"] for row in all_results) <= 1e-8,
        "contact_residual": max(row["max_contact_residual"] for row in all_results) <= 1e-8,
        "force_residual": max(row["max_force_residual"] for row in all_results) <= 1e-6,
        "reynolds_in_domain": max(row["max_reynolds"] for row in all_results) <= 3,
    }
    sources = [
        Path(__file__), Path(tr.__file__), Path(tr.previous.__file__),
        Path(tr.inertial.__file__), Path(tr.lubrication.__file__), Path(mechanics.__file__),
    ]
    result = {
        "completed": True,
        "passed": all(checks.values()),
        "checks": {key: bool(value) for key, value in checks.items()},
        "uniform_rows": uniform,
        "contact_rows": contact,
        "uniform_time_shift": uniform_shift,
        "contact_position_shift_over_body_radius": contact_shift,
        "source_hashes": {str(path.resolve()): sha(path) for path in sources},
        "supersedes_failed_test_design": "../inertial_trajectory_verification_01",
        "scope": "manufactured trajectory verification; no sand-matrix release claim",
    }
    (output / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({
        "passed": result["passed"], "checks": result["checks"],
        "uniform_times": uniform_times,
        "uniform_shift": uniform_shift,
        "contact_position_shift": contact_shift,
    }, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
