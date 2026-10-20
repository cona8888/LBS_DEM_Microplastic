"""End-to-end verification of cached reactions and persistent trapping."""
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np
import trajectory_cached_trap_v1 as model

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
    common = dict(a=a, b=b, viscosity=0.001002, particle_density=1380,
                  fluid_density=998.2, added_mass_fraction=1,
                  displacement_fraction=0.1, relaxation_fraction=0.1, max_dt=0.01)
    exits = []
    for fraction in (0.2, 0.1, 0.05):
        exits.append(model.integrate(
            Field([0.001, 0, 0]), Empty(), [0, 0, 0], [1, 0, 0], np.zeros(6),
            gravity=[0, 0, 0], friction=0, outlet=0.0001, horizon=0.3,
            **{**common, "displacement_fraction": fraction, "relaxation_fraction": fraction}
        ))
    times = [row["time_s"] for row in exits]

    radius = 3e-4
    centre = np.array([0.005, 0.005, 0.005])
    support_geometry = mechanics.GrainGeometry(
        [[centre[0], centre[1]-(radius+b), centre[2]]], [radius], 0.01
    )
    trapped = model.integrate(
        Field([0, 0, 0]), support_geometry, centre, [1, 0, 0], np.zeros(6),
        gravity=[0, -9.80665, 0], friction=0.3, outlet=0.009, horizon=0.05,
        trap_reference_speed=1e-4, trap_dwell_time=0.02, **common
    )
    sliding = model.integrate(
        Field([0.001, 0, 0]), support_geometry, centre, [1, 0, 0], np.zeros(6),
        gravity=[0, -9.80665, 0], friction=0, outlet=0.009, horizon=0.02,
        trap_reference_speed=1e-4, trap_dwell_time=0.01, **common
    )
    rows = exits + [trapped, sliding]
    checks = {
        "uniform_exits": all(row["status"] == "full_window_exit" for row in exits),
        "uniform_fine_medium_shift": abs(times[-1]-times[-2])/times[-1] <= 0.002,
        "supported_body_traps": trapped["status"] == "persistent_contact_trap",
        "trap_requires_dwell": trapped["time_s"] >= 0.019,
        "sliding_body_not_trapped": sliding["status"] != "persistent_contact_trap",
        "reaction_cache_populated": trapped["cached_reaction_count"] >= 1,
        "contact_iterations_recorded": trapped["total_contact_iterations"] > 0,
        "no_penetration": all(row["minimum_gap_m"] is None or row["minimum_gap_m"] >= -5e-10 for row in rows),
        "momentum_closure": max(row["max_momentum_residual"] for row in rows) <= 1e-8,
        "contact_closure": max(row["max_contact_residual"] for row in rows) <= 1e-8,
        "reynolds_in_domain": max(row["max_reynolds"] for row in rows) <= 3,
    }
    sources = [Path(__file__), Path(model.__file__), Path(model.inertial.__file__),
               Path(model.trap_event_v2.__file__), Path(mechanics.__file__)]
    result = {"completed": True, "passed": all(checks.values()),
              "checks": {key: bool(value) for key, value in checks.items()},
              "values": {"uniform_times_s": times, "trapped": trapped, "sliding": sliding},
              "source_hashes": {str(path.resolve()): sha(path) for path in sources},
              "scope": "manufactured cached-contact trajectory and trapping; no matrix release claim"}
    (output / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({"passed": result["passed"], "checks": result["checks"],
                      "uniform_times": times, "trap_time": trapped["time_s"],
                      "trap_iterations": trapped["total_contact_iterations"]}, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
