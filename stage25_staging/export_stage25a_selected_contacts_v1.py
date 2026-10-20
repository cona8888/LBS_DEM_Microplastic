"""Export the independently selected Stage25a YADE checkpoint for visualization."""

from __future__ import print_function

import csv
import hashlib
import json
import os
from datetime import datetime, timezone


EVALUATION_PATH = os.path.abspath(os.environ["STAGE25_EVALUATION"])
OUTPUT = os.path.abspath(os.environ["STAGE25_CONTACT_EXPORT"])
SCRIPT_PATH = os.path.abspath(os.environ.get("STAGE25_EXPORT_SCRIPT", __file__))


def sha256(path):
    value = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_json_exclusive(path, payload):
    with open(path, "x") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


with open(EVALUATION_PATH, "r") as stream:
    evaluation = json.load(stream)
if evaluation.get("passed") is not True or evaluation.get("status") != "passed_and_selected":
    raise RuntimeError("Stage25 evaluation is not accepted")
selection = evaluation["selection"]
if selection["case_id"] != "mu_0.60":
    raise RuntimeError("unexpected selected case")

checkpoint = os.path.join(
    "/mnt/c/MATDEM_MICROPLASTIC/stage25_runs/stage25a_pure_sand_mechanics_20260813/qualification_04",
    selection["case_id"], "load_bearing_state.yade.gz")
if sha256(checkpoint) != selection["checkpoint_sha256"]:
    raise RuntimeError("selected checkpoint hash mismatch")
if os.path.exists(OUTPUT):
    raise RuntimeError("immutable contact export already exists")
os.makedirs(OUTPUT)

O.load(checkpoint)
particle_path = os.path.join(OUTPUT, "particles.csv")
with open(particle_path, "x") as stream:
    writer = csv.writer(stream)
    writer.writerow(["body_id", "x_m", "y_m", "z_m", "radius_m"])
    for body in O.bodies:
        if body is not None and isinstance(body.shape, Sphere):
            writer.writerow([body.id, body.state.pos[0], body.state.pos[1], body.state.pos[2], body.shape.radius])

contact_path = os.path.join(OUTPUT, "contacts.csv")
contact_count = 0
with open(contact_path, "x") as stream:
    writer = csv.writer(stream)
    writer.writerow(["id1", "id2", "normal_force_n", "shear_force_n"])
    for interaction in O.interactions:
        if not interaction.isReal:
            continue
        normal_force = interaction.phys.normalForce.norm() if hasattr(interaction.phys, "normalForce") else 0.0
        shear_force = interaction.phys.shearForce.norm() if hasattr(interaction.phys, "shearForce") else 0.0
        writer.writerow([interaction.id1, interaction.id2, normal_force, shear_force])
        contact_count += 1

cell = {
    "schema": "lbs.stage25a-selected-contact-export.v1.cell",
    "periodic": bool(O.periodic),
    "cell_hsize": [[O.cell.hSize[row, col] for col in range(3)] for row in range(3)],
    "particle_count": sum(1 for body in O.bodies if body is not None and isinstance(body.shape, Sphere)),
    "real_contact_count": contact_count,
}
cell_path = os.path.join(OUTPUT, "cell.json")
write_json_exclusive(cell_path, cell)
completion = {
    "schema": "lbs.stage25a-selected-contact-export.v1.completion",
    "passed": cell["particle_count"] == 216 and contact_count == selection["real_contact_count"],
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "selected_case_id": selection["case_id"],
    "source": {
        "evaluation_sha256": sha256(EVALUATION_PATH),
        "checkpoint_sha256": sha256(checkpoint),
        "exporter_sha256": sha256(SCRIPT_PATH),
    },
    "artifacts": {
        "particles_csv_sha256": sha256(particle_path),
        "contacts_csv_sha256": sha256(contact_path),
        "cell_json_sha256": sha256(cell_path),
    },
    "particle_count": cell["particle_count"],
    "real_contact_count": contact_count,
    "claim_boundary": evaluation["claim_boundary"],
}
completion_path = os.path.join(OUTPUT, "completion.json")
write_json_exclusive(completion_path, completion)
print("STAGE25_CONTACT_EXPORT=" + json.dumps({
    "passed": completion["passed"], "particle_count": cell["particle_count"],
    "real_contact_count": contact_count, "completion_sha256": sha256(completion_path),
}, sort_keys=True))
if not completion["passed"]:
    raise RuntimeError("contact export did not match selected checkpoint evidence")
