"""Read-only YADE probe of the accepted Stage25 periodic state."""
from __future__ import print_function

import hashlib
import json
import math
import os


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


state = os.environ["STAGE26R_STATE"]
expected = os.environ["STAGE26R_STATE_SHA256"]
output = os.environ["STAGE26R_OUTPUT"]
if os.path.exists(output):
    raise RuntimeError("immutable probe output exists")
if sha256(state) != expected:
    raise RuntimeError("Stage25 state hash mismatch")
os.makedirs(output)
O.load(state)
sand = [body for body in O.bodies if body is not None and isinstance(body.shape, Sphere) and not body.isClumpMember]
solid = sum(4.0 * math.pi * float(body.shape.radius) ** 3 / 3.0 for body in sand)
engines = [engine.__class__.__name__ for engine in O.engines]
cell = [float(value) for value in O.cell.size]
data = {
    "schema": "lbs.stage26r-stage25-periodic-state-probe.v1",
    "passed": bool(O.periodic) and len(sand) == 216,
    "periodic": bool(O.periodic),
    "particle_count": len(sand),
    "cell_dimensions_m": cell,
    "cell_volume_m3": cell[0] * cell[1] * cell[2],
    "solid_volume_m3": solid,
    "void_ratio": cell[0] * cell[1] * cell[2] / solid - 1.0,
    "radius_min_m": min(float(body.shape.radius) for body in sand),
    "radius_max_m": max(float(body.shape.radius) for body in sand),
    "engines": engines,
    "source_state": {"path": state, "sha256": expected},
    "claim_boundary": "Read-only accepted-state API probe; no preparation, fibre, flow, or permeability result.",
}
path = os.path.join(output, "probe.json")
with open(path, "x") as stream:
    json.dump(data, stream, indent=2, sort_keys=True)
    stream.write("\n")
print("STAGE26R_PROBE=" + json.dumps(data, sort_keys=True), flush=True)
print("STAGE26R_PROBE_SHA256=" + sha256(path), flush=True)
raise SystemExit(0 if data["passed"] else 2)
