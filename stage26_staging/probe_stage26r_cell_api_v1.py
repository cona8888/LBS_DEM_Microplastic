"""Read-only YADE Cell API probe for the Stage26r fixed-cell handoff."""
from __future__ import print_function

import hashlib
import json
import os

from yade import config


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


state_path = os.path.abspath(os.environ["STAGE26R_CELL_API_STATE"])
output_path = os.path.abspath(os.environ["STAGE26R_CELL_API_OUTPUT"])
if os.path.exists(output_path):
    raise RuntimeError("immutable API probe output already exists")

O.load(state_path)
names = sorted(
    name
    for name in dir(O.cell)
    if any(token in name.lower() for token in ("vel", "size", "trsf", "integr", "grad"))
)

values = {}
for name in names:
    try:
        value = getattr(O.cell, name)
        values[name] = str(value)
    except Exception as error:
        values[name] = "ERROR: " + repr(error)

payload = {
    "schema": "lbs.stage26r-cell-api-probe.v1",
    "status": "completed_read_only_api_probe",
    "yade_version": str(config.version),
    "periodic": bool(O.periodic),
    "cell_api_names": names,
    "cell_api_values": values,
    "input_state": {"path": state_path, "sha256": sha256(state_path)},
    "claim_boundary": "Read-only YADE Cell API inspection; no simulation step or state publication.",
}

os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "x") as stream:
    json.dump(payload, stream, indent=2, sort_keys=True)
    stream.write("\n")

print("STAGE26R_CELL_API=" + json.dumps(payload, sort_keys=True), flush=True)
print("STAGE26R_CELL_API_SHA256=" + sha256(output_path), flush=True)
