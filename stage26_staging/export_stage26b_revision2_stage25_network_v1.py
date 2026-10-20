"""YADE read-only exporter for the exact Stage25 load-bearing contact network.

This script loads one frozen checkpoint and never advances or saves the DEM state.
It requires a future execution configuration with explicit network-export authority.
"""

from __future__ import print_function

import csv
import json
import math
import os
import sys
from datetime import datetime, timezone

SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(os.environ.get("STAGE26B_R2_NETWORK_SCRIPT", __file__)))
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)

from stage26b_revision2_prefilter_common_v1 import (
    iterative_core,
    load_json,
    sha256,
    windows_to_wsl,
    write_json_exclusive,
)


def assert_export_authority(cfg):
    if cfg.get("status") != "authorized_stage26b_revision2_network_export":
        raise RuntimeError("configuration is not network-export authorized")
    authority = cfg["authority"]
    if authority.get("network_export_execution_authorized") is not True:
        raise RuntimeError("network-export authority is false")
    forbidden = (
        "placement_generation_authorized",
        "prefilter_yade_execution_authorized",
        "two_fibre_free_release_authorized",
        "four_fibre_execution_authorized",
        "eight_or_more_fibre_execution_authorized",
        "flow_execution_authorized",
        "deformation_coupled_flow_authorized",
        "transient_two_way_coupling_authorized",
        "production_parametric_study_authorized",
    )
    if any(authority.get(name, False) for name in forbidden):
        raise RuntimeError("network-export configuration exceeds its authority")


def bind_sources(cfg):
    for key, value in cfg["sources"].items():
        if key.endswith("_sha256") or key == "expected_yade_version":
            continue
        expected = cfg["sources"].get(key + "_sha256")
        if expected is not None and sha256(windows_to_wsl(value)) != expected:
            raise RuntimeError("source hash mismatch: " + key)


def main():
    from yade import config

    config_path = os.path.abspath(os.environ["STAGE26B_R2_NETWORK_CONFIG"])
    output = os.path.abspath(os.environ["STAGE26B_R2_NETWORK_OUTPUT"])
    script_path = os.path.abspath(os.environ.get("STAGE26B_R2_NETWORK_SCRIPT", __file__))
    common_path = os.path.join(os.path.dirname(script_path), "stage26b_revision2_prefilter_common_v1.py")
    cfg = load_json(config_path)
    assert_export_authority(cfg)
    bind_sources(cfg)
    expected_version = str(cfg["sources"]["expected_yade_version"])
    if str(config.version) != expected_version:
        raise RuntimeError("unexpected YADE version")
    if os.path.exists(output):
        raise RuntimeError("immutable network-export output already exists")

    checkpoint = windows_to_wsl(cfg["sources"]["stage25_checkpoint"])
    O.load(checkpoint)
    sand_ids = sorted(
        int(body.id) for body in O.bodies
        if body is not None and isinstance(body.shape, Sphere) and not body.isClumpMember
    )
    required = cfg["network_export"]
    if len(sand_ids) != int(required["required_sand_particle_count"]):
        raise RuntimeError("Stage25 sand-particle count mismatch")
    sand_set = set(sand_ids)
    edges = []
    contacts = []
    incident_normal = dict((body_id, []) for body_id in sand_ids)
    for interaction in O.interactions:
        if not interaction.isReal:
            continue
        first, second = int(interaction.id1), int(interaction.id2)
        if first not in sand_set or second not in sand_set:
            continue
        normal_force = float(interaction.phys.normalForce.norm()) if hasattr(interaction.phys, "normalForce") else 0.0
        shear_force = float(interaction.phys.shearForce.norm()) if hasattr(interaction.phys, "shearForce") else 0.0
        if not math.isfinite(normal_force) or not math.isfinite(shear_force) or normal_force < 0.0 or shear_force < 0.0:
            raise RuntimeError("non-finite or negative contact-force magnitude")
        edges.append((first, second))
        incident_normal[first].append(normal_force)
        incident_normal[second].append(normal_force)
        contacts.append({
            "id1": first,
            "id2": second,
            "normal_force_n": normal_force,
            "shear_force_n": shear_force,
        })
    if len(contacts) != int(required["required_sand_contact_count"]):
        raise RuntimeError("Stage25 real sand-contact count mismatch")
    initial_degree, core_degree, active = iterative_core(
        sand_ids, edges, int(required["core_degree_threshold"])
    )
    if len(active) != int(required["required_load_bearing_particle_count"]):
        raise RuntimeError("Stage25 load-bearing-core count mismatch")

    particles = []
    for body_id in sand_ids:
        body = O.bodies[body_id]
        forces = incident_normal[body_id]
        particles.append({
            "sand_body_id": body_id,
            "position_m": [float(body.state.pos[index]) for index in range(3)],
            "radius_m": float(body.shape.radius),
            "sand_network_degree": int(initial_degree[body_id]),
            "load_bearing_core_member": body_id in active,
            "load_bearing_core_degree": int(core_degree[body_id]),
            "incident_normal_force_sum_n": float(sum(forces)),
            "minimum_incident_normal_force_n": float(min(forces)) if forces else 0.0,
            "mean_incident_normal_force_n": float(sum(forces) / len(forces)) if forces else 0.0,
        })
    cell_hsize = [[float(O.cell.hSize[row, col]) for col in range(3)] for row in range(3)]
    network = {
        "schema": "lbs.stage26b-revision2-stage25-network.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "exported_exact_stage25_contact_network_without_stepping",
        "periodic": bool(O.periodic),
        "cell_hsize_m": cell_hsize,
        "sand_particle_count": len(sand_ids),
        "sand_contact_count": len(contacts),
        "load_bearing_particle_count": len(active),
        "core_degree_threshold": int(required["core_degree_threshold"]),
        "particles": particles,
        "contacts": contacts,
        "source_hashes": {
            "config": sha256(config_path),
            "stage25_checkpoint": sha256(checkpoint),
            "exporter": sha256(script_path),
            "common": sha256(common_path),
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    os.makedirs(output)
    network_path = os.path.join(output, "network.json")
    write_json_exclusive(network_path, network)
    particles_path = os.path.join(output, "particles.csv")
    with open(particles_path, "x") as stream:
        fields = [
            "sand_body_id", "x_m", "y_m", "z_m", "radius_m",
            "sand_network_degree", "load_bearing_core_member", "load_bearing_core_degree",
            "incident_normal_force_sum_n", "minimum_incident_normal_force_n", "mean_incident_normal_force_n",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in particles:
            flat = dict(row)
            flat["x_m"], flat["y_m"], flat["z_m"] = flat.pop("position_m")
            writer.writerow(flat)
    contacts_path = os.path.join(output, "contacts.csv")
    with open(contacts_path, "x") as stream:
        writer = csv.DictWriter(stream, fieldnames=["id1", "id2", "normal_force_n", "shear_force_n"])
        writer.writeheader()
        writer.writerows(contacts)
    completion = {
        "schema": "lbs.stage26b-revision2-stage25-network-completion.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "status": "passed_read_only_network_export",
        "network_sha256": sha256(network_path),
        "particles_csv_sha256": sha256(particles_path),
        "contacts_csv_sha256": sha256(contacts_path),
        "source_hashes": network["source_hashes"],
        "authority": {
            "placement_generation_authorized": False,
            "prefilter_yade_execution_authorized": False,
            "two_fibre_free_release_authorized": False,
            "four_fibre_execution_authorized": False,
            "flow_execution_authorized": False,
        },
        "claim_boundary": cfg["claim_boundary"],
    }
    completion_path = os.path.join(output, "completion.json")
    write_json_exclusive(completion_path, completion)
    print("STAGE26B_R2_NETWORK=" + json.dumps({
        "passed": True,
        "sand_contacts": len(contacts),
        "load_bearing_particles": len(active),
        "completion_sha256": sha256(completion_path),
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
