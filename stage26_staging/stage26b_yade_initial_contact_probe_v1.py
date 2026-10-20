"""YADE insertion-instant contact probe for an exact frozen Stage26b placement."""

from __future__ import print_function

import hashlib
import json
import math
import os
from datetime import datetime, timezone

from yade import config


CONFIG_PATH = os.path.abspath(os.environ["STAGE26B_CONFIG"])
CASE_ID = os.environ["STAGE26B_CASE_ID"]
OUTPUT_PATH = os.path.abspath(os.environ["STAGE26B_PROBE_OUTPUT"])
SCRIPT_PATH = os.path.abspath(os.environ.get("STAGE26B_SCRIPT", __file__))


def sha256(path):
    value = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with open(path, "r") as stream:
        return json.load(stream)


def windows_to_wsl(path):
    value = str(path).replace("\\", "/")
    return "/mnt/%s/%s" % (value[0].lower(), value[3:]) if len(value) >= 3 and value[1:3] == ":/" else value


def minimum_image(vector, lengths):
    return [float(vector[i] - round(float(vector[i]) / lengths[i]) * lengths[i]) for i in range(3)]


def norm(vector):
    return math.sqrt(sum(float(value) ** 2 for value in vector))


def main():
    if os.path.exists(OUTPUT_PATH):
        raise RuntimeError("immutable probe output already exists")
    cfg = load_json(CONFIG_PATH)
    if cfg["status"] != "authorized_bounded_tier1_dry_yade_execution":
        raise RuntimeError("unexpected config status")
    case = next((row for row in cfg["cases"] if row["case_id"] == CASE_ID), None)
    if case is None:
        raise RuntimeError("case outside frozen Tier-1 authority")
    if sha256(windows_to_wsl(case["placement"])) != case["placement_sha256"]:
        raise RuntimeError("placement hash mismatch")
    placement = load_json(windows_to_wsl(case["placement"]))
    O.load(windows_to_wsl(cfg["sources"]["stage25_checkpoint"]))
    sand_ids = [int(body.id) for body in O.bodies if body is not None and isinstance(body.shape, Sphere) and not body.isClumpMember]
    plastic_id = O.materials.append(FrictMat(
        young=float(cfg["contacts"]["plastic_young_pa"]),
        poisson=float(cfg["contacts"]["plastic_poisson"]),
        frictionAngle=math.atan(float(cfg["contacts"]["plastic_friction_coefficient"])),
        density=float(cfg["fibre"]["density_kg_m3"]), label="stage26b_probe_plastic",
    ))
    parents = []
    members_by_fibre = []
    for fibre in placement["fibres"]:
        bodies = [sphere(Vector3(*centre), float(placement["member_radius_m"]), material=plastic_id) for centre in fibre["member_centres_m"]]
        parent_id, members = O.bodies.appendClumped(bodies, 20)
        parent_id = int(parent_id)
        members = [int(value) for value in members]
        O.bodies[parent_id].state.blockedDOFs = "xyzXYZ"
        parents.append(parent_id)
        members_by_fibre.append(members)
    O.step()
    sand_set = set(sand_ids)
    member_to_fibre = {}
    for fibre_index, members in enumerate(members_by_fibre):
        for member in members:
            member_to_fibre[member] = fibre_index
    contacts = [set() for _ in parents]
    real_details = []
    for interaction in O.interactions:
        if not interaction.isReal:
            continue
        first, second = int(interaction.id1), int(interaction.id2)
        if first in sand_set and second in member_to_fibre:
            fibre_index, sand_id, member_id = member_to_fibre[second], first, second
        elif second in sand_set and first in member_to_fibre:
            fibre_index, sand_id, member_id = member_to_fibre[first], second, first
        else:
            continue
        contacts[fibre_index].add(sand_id)
        real_details.append({"fibre_index": fibre_index, "sand_body_id": sand_id, "member_body_id": member_id, "penetration_m": float(interaction.geom.penetrationDepth)})
    lengths = [float(O.cell.hSize[index, index]) for index in range(3)]
    anchor_geometry = []
    for fibre_index, fibre in enumerate(placement["fibres"]):
        rows = []
        for sand_id, member_local_index in zip(fibre["anchor_sand_body_ids"], fibre["anchor_member_indices"]):
            member_id = members_by_fibre[fibre_index][member_local_index]
            sand = O.bodies[int(sand_id)]
            member = O.bodies[member_id]
            delta = minimum_image([float(member.state.pos[index] - sand.state.pos[index]) for index in range(3)], lengths)
            clearance = norm(delta) - float(sand.shape.radius) - float(member.shape.radius)
            rows.append({"sand_body_id": int(sand_id), "member_body_id": member_id, "clearance_m": clearance})
        anchor_geometry.append(rows)
    declared = [sorted(int(value) for value in fibre["anchor_sand_body_ids"]) for fibre in placement["fibres"]]
    observed = [sorted(value) for value in contacts]
    payload = {
        "schema": "lbs.stage26b-tier1-initial-contact-probe.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": observed == declared,
        "case_id": CASE_ID,
        "yade_version": str(config.version),
        "declared_anchor_sand_body_ids_by_fibre": declared,
        "observed_real_sand_contact_ids_by_fibre_after_one_step": observed,
        "real_contact_details": real_details,
        "anchor_geometry_after_one_step": anchor_geometry,
        "source_hashes": {"config": sha256(CONFIG_PATH), "placement": sha256(windows_to_wsl(case["placement"])), "runner": sha256(SCRIPT_PATH)},
        "interpretation_if_passed": "YADE created every declared anchor contact before conditioning; later contact loss is a conditioning/local-network outcome, not an insertion or collision-detection defect.",
        "claim_boundary": cfg["claim_boundary"],
    }
    with open(OUTPUT_PATH, "x") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print("STAGE26B_CONTACT_PROBE=" + json.dumps({"passed": payload["passed"], "observed": observed, "probe_sha256": sha256(OUTPUT_PATH)}, sort_keys=True), flush=True)


main()
