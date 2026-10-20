"""No-step setter probe for YADE Cell state fields used at a fixed-cell handoff."""
from __future__ import print_function

import hashlib
import json
import os


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


state_path = os.path.abspath(os.environ["STAGE26R_CELL_SETTER_STATE"])
output_path = os.path.abspath(os.environ["STAGE26R_CELL_SETTER_OUTPUT"])
if os.path.exists(output_path):
    raise RuntimeError("immutable setter probe output exists")

O.load(state_path)
attempts = {}
for name, value in (
    ("velGrad", Matrix3.Zero),
    ("nextVelGrad", Matrix3.Zero),
    ("prevVelGrad", Matrix3.Zero),
    ("velGradChanged", True),
):
    try:
        setattr(O.cell, name, value)
        attempts[name] = {"writable": True, "value_after": str(getattr(O.cell, name))}
    except Exception as error:
        attempts[name] = {"writable": False, "error": type(error).__name__ + ": " + str(error)}

payload = {
    "schema": "lbs.stage26r-cell-setter-probe.v1",
    "status": "completed_no_step_setter_probe",
    "simulation_steps_executed": 0,
    "attempts": attempts,
    "input_state": {"path": state_path, "sha256": sha256(state_path)},
    "claim_boundary": "In-memory YADE Cell setter inspection only; no O.step, save, mechanics, fibre, or flow.",
}
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "x") as stream:
    json.dump(payload, stream, indent=2, sort_keys=True)
    stream.write("\n")
print("STAGE26R_CELL_SETTERS=" + json.dumps(payload, sort_keys=True), flush=True)
print("STAGE26R_CELL_SETTERS_SHA256=" + sha256(output_path), flush=True)
