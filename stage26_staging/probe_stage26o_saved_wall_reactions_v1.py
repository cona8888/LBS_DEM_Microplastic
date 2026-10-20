"""Recompute Stage26o wall stresses from saved-state wall reaction forces."""
from __future__ import print_function

import json
import hashlib
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
    if len(controllers) != 1:
        raise RuntimeError("expected one triaxial controller")
    triax = controllers[0]
    ids = {
        "left": int(triax.wall_left_id), "right": int(triax.wall_right_id),
        "bottom": int(triax.wall_bottom_id), "top": int(triax.wall_top_id),
        "back": int(triax.wall_back_id), "front": int(triax.wall_front_id),
    }
    x0, x1 = float(O.bodies[ids["left"]].state.pos[0]), float(O.bodies[ids["right"]].state.pos[0])
    y0, y1 = float(O.bodies[ids["bottom"]].state.pos[1]), float(O.bodies[ids["top"]].state.pos[1])
    z0, z1 = float(O.bodies[ids["back"]].state.pos[2]), float(O.bodies[ids["front"]].state.pos[2])
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    reactions = {name: [float(value) for value in O.forces.f(wall_id)] for name, wall_id in ids.items()}
    direct_stresses = [
        abs(reactions["right"][0]) / (dy * dz),
        abs(reactions["top"][1]) / (dx * dz),
        abs(reactions["front"][2]) / (dx * dy),
    ]
    cached_stresses = [
        -float(triax.stress(ids["right"])[0]),
        -float(triax.stress(ids["top"])[1]),
        -float(triax.stress(ids["front"])[2]),
    ]
    target = 100.0
    mean = sum(direct_stresses) / 3.0
    result = {
        "schema": "lbs.stage26o-saved-wall-reaction-probe.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "state_sha256": sha256(state),
        "controller_dead": bool(triax.dead),
        "wall_ids": ids,
        "wall_dimensions_m": [dx, dy, dz],
        "wall_reaction_forces_n": reactions,
        "direct_reaction_stresses_pa_compression_positive": direct_stresses,
        "cached_controller_stresses_pa_compression_positive": cached_stresses,
        "maximum_cached_to_direct_absolute_difference_pa": max(abs(a - b) for a, b in zip(cached_stresses, direct_stresses)),
        "direct_mean_stress_pa": mean,
        "direct_relative_mean_stress_error": abs(mean - target) / target,
        "direct_maximum_principal_stress_error": max(abs(value - target) / target for value in direct_stresses),
    }
    path = os.path.join(output, "reaction_probe.json")
    write_json_exclusive(path, result)
    print("STAGE26O_REACTION_PROBE_SHA256=" + sha256(path), flush=True)


if __name__ == "__main__":
    main()
