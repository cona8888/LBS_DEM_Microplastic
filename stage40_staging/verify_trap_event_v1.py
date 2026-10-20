"""Limiting-case and timestep verification for the trapping event."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import trap_event_v1 as model


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(dt, velocity, contacts=(3, 7), load=(3, 7), change=False):
    monitor = model.TrapMonitor(1e-4, 5e-5, 0.2)
    time = 0.0
    event = None
    while time < 0.5:
        ids = contacts if not change or time < 0.12 else (3, 8)
        state = monitor.update(dt, np.array([velocity[0] * time, 0, 0]), velocity, ids, load)
        time += dt
        if state["trapped"]:
            event = time
            break
    return event, state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    static_times = [run(dt, np.zeros(6))[0] for dt in (0.02, 0.01, 0.005)]
    slow_time, slow_state = run(0.01, np.array([5e-7, 0, 0, 0, 0, 0]))
    fast_time, _ = run(0.01, np.array([2e-6, 0, 0, 0, 0, 0]))
    no_load_time, _ = run(0.01, np.zeros(6), load=())
    changing_time, changing_state = run(0.01, np.zeros(6), change=True)
    checks = {
        "static_contact_traps": all(value is not None for value in static_times),
        "event_time_within_one_step": max(abs(value - 0.2) for value in static_times) <= 0.0200000001,
        "subthreshold_drift_traps": slow_time is not None and slow_state["maximum_drift_m"] <= 1e-6,
        "above_speed_threshold_does_not_trap": fast_time is None,
        "no_load_bearing_contact_does_not_trap": no_load_time is None,
        "contact_change_resets_dwell": changing_time is not None and changing_time >= 0.31,
        "reported_contact_set_updated": changing_state["contact_ids"] == [3, 8],
    }
    result = {"completed": True, "passed": all(checks.values()),
              "checks": {key: bool(value) for key, value in checks.items()},
              "values": {"static_event_times_s": static_times, "slow_event_time_s": slow_time,
                         "changing_event_time_s": changing_time},
              "source_hashes": {str(Path(__file__).resolve()): sha(__file__),
                                str(Path(model.__file__).resolve()): sha(model.__file__)},
              "scope": "steady-flow persistent-contact event only; no adhesion or detachment"}
    (output / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
