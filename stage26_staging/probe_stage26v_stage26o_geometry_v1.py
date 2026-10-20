#!/usr/bin/env python3
"""Read-only export of the accepted Stage26o 216-grain wall geometry."""

from __future__ import print_function

import hashlib
import json
import os
from datetime import datetime, timezone

STATE = os.environ["STAGE26V_SOURCE_STATE"]
OUTPUT = os.environ["STAGE26V_GEOMETRY_OUTPUT"]
EXPECTED_STATE_SHA = os.environ["STAGE26V_SOURCE_STATE_SHA256"]
SOURCE_CHECKPOINT = os.environ["STAGE26V_SOURCE_CHECKPOINT"]
EXPECTED_CHECKPOINT_SHA = os.environ["STAGE26V_SOURCE_CHECKPOINT_SHA256"]
SCRIPT = "/mnt/c/MATDEM_MICROPLASTIC/stage26_staging/probe_stage26v_stage26o_geometry_v1.py"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def vec(value):
    return [float(value[0]), float(value[1]), float(value[2])]


if os.path.exists(OUTPUT):
    raise RuntimeError("refusing to overwrite immutable output %s" % OUTPUT)
if sha(STATE) != EXPECTED_STATE_SHA or sha(SOURCE_CHECKPOINT) != EXPECTED_CHECKPOINT_SHA:
    raise RuntimeError("Stage26o source binding mismatch")
os.makedirs(OUTPUT)
O.load(STATE)

spheres = []
walls = []
for body in O.bodies:
    if body is None:
        continue
    shape_name = body.shape.__class__.__name__
    if shape_name == "Sphere" and not body.isClumpMember:
        spheres.append({"body_id": int(body.id), "centre_m": vec(body.state.pos),
                        "radius_m": float(body.shape.radius), "blocked_dofs": str(body.state.blockedDOFs)})
    elif shape_name == "Box":
        walls.append({"body_id": int(body.id), "centre_m": vec(body.state.pos),
                      "extents_m": vec(body.shape.extents), "blocked_dofs": str(body.state.blockedDOFs)})

spheres.sort(key=lambda item: item["body_id"])
walls.sort(key=lambda item: item["body_id"])
finite = all(all(abs(value) < 1e6 for value in item["centre_m"]) and 0.0 < item["radius_m"] < 0.01 for item in spheres)
checks = {
    "nonperiodic": not bool(O.periodic),
    "exact_sphere_count": len(spheres) == 216,
    "exact_wall_count": len(walls) == 6,
    "finite_geometry": finite,
    "source_state_binding": sha(STATE) == EXPECTED_STATE_SHA,
    "source_checkpoint_binding": sha(SOURCE_CHECKPOINT) == EXPECTED_CHECKPOINT_SHA,
}
passed = all(checks.values())
geometry = {
    "schema": "lbs.stage26v-stage26o-geometry-export.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": passed,
    "checks": checks,
    "periodic": bool(O.periodic),
    "spheres": spheres,
    "walls": walls,
    "source_bindings": {
        "state": {"path": STATE, "sha256": sha(STATE)},
        "checkpoint": {"path": SOURCE_CHECKPOINT, "sha256": sha(SOURCE_CHECKPOINT)},
        "probe": {"path": SCRIPT, "sha256": sha(SCRIPT)},
    },
    "state_metadata": O.tags.get("stage26o_control_metadata_json", ""),
    "claim_boundary": "Read-only geometry export from the accepted Stage26o wall state; no DEM stepping, fibre insertion, mechanics, flow, or permeability result.",
}
path = os.path.join(OUTPUT, "geometry.json")
with open(path, "x") as stream:
    json.dump(geometry, stream, indent=2, sort_keys=True)
    stream.write("\n")
completion = {
    "schema": "lbs.stage26v-stage26o-geometry-export-completion.v1",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": passed,
    "checks": checks,
    "geometry": {"path": path, "sha256": sha(path)},
}
with open(os.path.join(OUTPUT, "completion.json"), "x") as stream:
    json.dump(completion, stream, indent=2, sort_keys=True)
    stream.write("\n")
print(json.dumps(completion, indent=2, sort_keys=True))
raise SystemExit(0 if passed else 2)

