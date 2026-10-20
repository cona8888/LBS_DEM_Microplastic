"""Rebuild forces for one fixed-wall step, then recompute Stage26o wall stresses."""
from __future__ import print_function

import hashlib
import json
import os
from datetime import datetime, timezone


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_exclusive(path, payload):
    with open(path, "x") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main():
    state = os.path.abspath(os.environ["STAGE26O_REACTION_STATE"])
    output = os.path.abspath(os.environ["STAGE26O_REACTION_OUTPUT"])
    if os.path.exists(output):
        raise RuntimeError("immutable reaction-probe output exists")
    os.makedirs(output)
    O.load(state)
    controllers = [engine for engine in O.engines if isinstance(engine, TriaxialStressController)]
    if len(controllers) != 1 or not controllers[0].dead:
        raise RuntimeError("expected one disabled triaxial controller")
    triax = controllers[0]
    ids = {"left": int(triax.wall_left_id), "right": int(triax.wall_right_id), "bottom": int(triax.wall_bottom_id), "top": int(triax.wall_top_id), "back": int(triax.wall_back_id), "front": int(triax.wall_front_id)}
    before = {name: [float(value) for value in O.bodies[wall_id].state.pos] for name, wall_id in ids.items()}
    O.run(1, True)
    after = {name: [float(value) for value in O.bodies[wall_id].state.pos] for name, wall_id in ids.items()}
    x0, x1 = after["left"][0], after["right"][0]
    y0, y1 = after["bottom"][1], after["top"][1]
    z0, z1 = after["back"][2], after["front"][2]
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    reactions = {name: [float(value) for value in O.forces.f(wall_id)] for name, wall_id in ids.items()}
    stresses = [abs(reactions["right"][0]) / (dy * dz), abs(reactions["top"][1]) / (dx * dz), abs(reactions["front"][2]) / (dx * dy)]
    target = 100.0
    mean = sum(stresses) / 3.0
    max_wall_shift = max(abs(after[name][axis] - before[name][axis]) for name in ids for axis in range(3))
    result = {
        "schema": "lbs.stage26o-saved-wall-reaction-probe.v2",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "state_sha256": sha256(state),
        "force_rebuild_steps": 1,
        "controller_dead": bool(triax.dead),
        "maximum_wall_shift_during_probe_m": max_wall_shift,
        "wall_ids": ids,
        "wall_dimensions_m": [dx, dy, dz],
        "wall_reaction_forces_n": reactions,
        "direct_reaction_stresses_pa_compression_positive": stresses,
        "direct_mean_stress_pa": mean,
        "direct_relative_mean_stress_error": abs(mean - target) / target,
        "direct_maximum_principal_stress_error": max(abs(value - target) / target for value in stresses),
    }
    path = os.path.join(output, "reaction_probe.json")
    write_json_exclusive(path, result)
    print("STAGE26O_REACTION_PROBE_SHA256=" + sha256(path), flush=True)


if __name__ == "__main__":
    main()
