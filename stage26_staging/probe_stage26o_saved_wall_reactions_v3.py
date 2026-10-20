"""Independently rebuild direct wall reactions from an active-servo YADE state.

The saved file is loaded into a disposable YADE process.  The single triaxial
controller is disabled in memory, all wall velocities are zeroed, and exactly
one step is advanced so that contact reactions are rebuilt without servo wall
motion.  The immutable source state is never modified.
"""
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
    result_path = os.path.abspath(os.environ["STAGE26O_REACTION_RESULT"])
    output = os.path.abspath(os.environ["STAGE26O_REACTION_OUTPUT"])
    if os.path.exists(output):
        raise RuntimeError("immutable reaction-probe output exists")

    with open(result_path, "r") as stream:
        accepted_result = json.load(stream)
    expected = [
        float(value)
        for value in accepted_result["terminal"][
            "principal_wall_stress_pa_compression_positive"
        ]
    ]
    target = float(accepted_result["terminal"]["mean_wall_stress_pa_compression_positive"])
    if not accepted_result.get("qualified") or not accepted_result.get("passed"):
        raise RuntimeError("source result is not qualified")

    O.load(state)
    controllers = [
        engine for engine in O.engines if isinstance(engine, TriaxialStressController)
    ]
    if len(controllers) != 1:
        raise RuntimeError("expected exactly one triaxial controller")
    triax = controllers[0]
    controller_was_active = not bool(triax.dead)
    ids = {
        "left": int(triax.wall_left_id),
        "right": int(triax.wall_right_id),
        "bottom": int(triax.wall_bottom_id),
        "top": int(triax.wall_top_id),
        "back": int(triax.wall_back_id),
        "front": int(triax.wall_front_id),
    }

    # Freeze the controller and wall kinematics only in this disposable copy.
    triax.dead = True
    for wall_id in ids.values():
        O.bodies[wall_id].state.vel = (0.0, 0.0, 0.0)
        O.bodies[wall_id].state.angVel = (0.0, 0.0, 0.0)

    before = {
        name: [float(value) for value in O.bodies[wall_id].state.pos]
        for name, wall_id in ids.items()
    }
    O.run(1, True)
    after = {
        name: [float(value) for value in O.bodies[wall_id].state.pos]
        for name, wall_id in ids.items()
    }

    x0, x1 = after["left"][0], after["right"][0]
    y0, y1 = after["bottom"][1], after["top"][1]
    z0, z1 = after["back"][2], after["front"][2]
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    reactions = {
        name: [float(value) for value in O.forces.f(wall_id)]
        for name, wall_id in ids.items()
    }
    stresses = [
        abs(reactions["right"][0]) / (dy * dz),
        abs(reactions["top"][1]) / (dx * dz),
        abs(reactions["front"][2]) / (dx * dy),
    ]
    mean = sum(stresses) / 3.0
    max_wall_shift = max(
        abs(after[name][axis] - before[name][axis])
        for name in ids
        for axis in range(3)
    )
    terminal_match_error = max(
        abs(observed - reference) / 100.0
        for observed, reference in zip(stresses, expected)
    )
    checks = {
        "controller_was_active": controller_was_active,
        "controller_disabled_for_probe": bool(triax.dead),
        "fixed_walls": max_wall_shift <= 1.0e-15,
        "particle_count": len([body for body in O.bodies if body and body.dynamic]) == 216,
        "mean_stress": abs(mean - 100.0) / 100.0 <= 0.05,
        "principal_stress": max(abs(value - 100.0) / 100.0 for value in stresses)
        <= 0.10,
        "terminal_reaction_match": terminal_match_error <= 0.02,
    }
    passed = all(checks.values())
    payload = {
        "schema": "lbs.stage26o-saved-wall-reaction-probe.v3",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "checks": checks,
        "state_sha256": sha256(state),
        "result_sha256": sha256(result_path),
        "force_rebuild_steps": 1,
        "controller_was_active": controller_was_active,
        "controller_disabled_for_probe": bool(triax.dead),
        "maximum_wall_shift_during_probe_m": max_wall_shift,
        "wall_ids": ids,
        "wall_dimensions_m": [dx, dy, dz],
        "wall_reaction_forces_n": reactions,
        "direct_reaction_stresses_pa_compression_positive": stresses,
        "source_terminal_reaction_stresses_pa": expected,
        "direct_mean_stress_pa": mean,
        "direct_relative_mean_stress_error": abs(mean - 100.0) / 100.0,
        "direct_maximum_principal_stress_error": max(
            abs(value - 100.0) / 100.0 for value in stresses
        ),
        "maximum_terminal_reaction_match_error": terminal_match_error,
        "source_terminal_mean_stress_pa": target,
    }
    os.makedirs(output)
    path = os.path.join(output, "reaction_probe.json")
    write_json_exclusive(path, payload)
    print("STAGE26O_REACTION_PROBE_SHA256=" + sha256(path), flush=True)
    if not passed:
        raise RuntimeError("saved-state direct-reaction probe failed")


if __name__ == "__main__":
    main()
