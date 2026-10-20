"""Independently verify the exact Stage25 read-only network-export bundle."""

import ast
import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(r"C:\MATDEM_MICROPLASTIC")
STAGING = PROJECT / "stage26_staging"
sys.path.insert(0, str(STAGING))
from stage26b_revision2_prefilter_common_v1 import iterative_core

CONFIG = STAGING / "stage26b_revision2_network_export_execution_v4.json"
PRERUN = PROJECT / "stage26_checkpoints" / "stage26b_tier1_placement_stability_revision2_20260816" / "network_export_prerun_checkpoint_04" / "checkpoint_manifest.json"
BUNDLE = PROJECT / "stage26_network_exports" / "stage26b_revision2_stage25_network_20260816" / "export_04"
OUTPUT = PROJECT / "stage26_evaluations" / "stage26b_tier1_placement_stability_revision2_20260816" / "network_export_evaluation_01"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def csv_rows(path):
    with path.open("r", newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def o_calls(path):
    parsed = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result = []
    for node in ast.walk(parsed):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "O":
                result.append(node.func.attr)
    return result


def same_float(left, right):
    return float(left) == float(right)


def main():
    if OUTPUT.exists():
        raise RuntimeError("immutable network-export evaluation already exists")
    expected_names = {"network.json", "particles.csv", "contacts.csv", "completion.json"}
    actual_names = {path.name for path in BUNDLE.iterdir() if path.is_file()}
    cfg = load_json(CONFIG)
    prerun = load_json(PRERUN)
    completion = load_json(BUNDLE / "completion.json")
    network = load_json(BUNDLE / "network.json")
    particles_csv = csv_rows(BUNDLE / "particles.csv")
    contacts_csv = csv_rows(BUNDLE / "contacts.csv")
    particles = network["particles"]
    contacts = network["contacts"]
    ids = [int(row["sand_body_id"]) for row in particles]
    id_set = set(ids)
    edges = [(int(row["id1"]), int(row["id2"])) for row in contacts]
    undirected = [tuple(sorted(edge)) for edge in edges]
    degree, core_degree, core = iterative_core(ids, edges, int(network["core_degree_threshold"]))
    incident = {body_id: [] for body_id in ids}
    force_valid = True
    endpoints_valid = True
    for row in contacts:
        first, second = int(row["id1"]), int(row["id2"])
        normal, shear = float(row["normal_force_n"]), float(row["shear_force_n"])
        endpoints_valid = endpoints_valid and first in id_set and second in id_set and first != second
        force_valid = force_valid and math.isfinite(normal) and math.isfinite(shear) and normal >= 0.0 and shear >= 0.0
        incident[first].append(normal)
        incident[second].append(normal)
    particle_fields_match = True
    for row in particles:
        body_id = int(row["sand_body_id"])
        values = incident[body_id]
        expected_sum = sum(values)
        expected_min = min(values) if values else 0.0
        expected_mean = expected_sum / len(values) if values else 0.0
        particle_fields_match = particle_fields_match and (
            int(row["sand_network_degree"]) == degree[body_id]
            and bool(row["load_bearing_core_member"]) == (body_id in core)
            and int(row["load_bearing_core_degree"]) == core_degree.get(body_id, 0)
            and same_float(row["incident_normal_force_sum_n"], expected_sum)
            and same_float(row["minimum_incident_normal_force_n"], expected_min)
            and same_float(row["mean_incident_normal_force_n"], expected_mean)
            and len(row["position_m"]) == 3
            and all(math.isfinite(float(value)) for value in row["position_m"])
            and math.isfinite(float(row["radius_m"])) and float(row["radius_m"]) > 0.0
        )
    json_particles_by_id = {int(row["sand_body_id"]): row for row in particles}
    csv_particles_match = len(particles_csv) == len(particles) and all(
        int(row["sand_body_id"]) in json_particles_by_id
        and same_float(row["x_m"], json_particles_by_id[int(row["sand_body_id"])]["position_m"][0])
        and same_float(row["y_m"], json_particles_by_id[int(row["sand_body_id"])]["position_m"][1])
        and same_float(row["z_m"], json_particles_by_id[int(row["sand_body_id"])]["position_m"][2])
        and same_float(row["radius_m"], json_particles_by_id[int(row["sand_body_id"])]["radius_m"])
        and int(row["sand_network_degree"]) == json_particles_by_id[int(row["sand_body_id"])]["sand_network_degree"]
        and (row["load_bearing_core_member"] == "True") == json_particles_by_id[int(row["sand_body_id"])]["load_bearing_core_member"]
        and int(row["load_bearing_core_degree"]) == json_particles_by_id[int(row["sand_body_id"])]["load_bearing_core_degree"]
        and same_float(row["incident_normal_force_sum_n"], json_particles_by_id[int(row["sand_body_id"])]["incident_normal_force_sum_n"])
        and same_float(row["minimum_incident_normal_force_n"], json_particles_by_id[int(row["sand_body_id"])]["minimum_incident_normal_force_n"])
        and same_float(row["mean_incident_normal_force_n"], json_particles_by_id[int(row["sand_body_id"])]["mean_incident_normal_force_n"])
        for row in particles_csv
    )
    csv_contacts_match = len(contacts_csv) == len(contacts) and all(
        int(csv_row["id1"]) == int(json_row["id1"])
        and int(csv_row["id2"]) == int(json_row["id2"])
        and same_float(csv_row["normal_force_n"], json_row["normal_force_n"])
        and same_float(csv_row["shear_force_n"], json_row["shear_force_n"])
        for csv_row, json_row in zip(contacts_csv, contacts)
    )
    exporter = Path(cfg["sources"]["network_exporter"])
    calls = o_calls(exporter)
    expected_source_hashes = {
        "config": digest(CONFIG),
        "exporter": digest(exporter),
        "common": digest(Path(cfg["sources"]["common"])),
        "stage25_checkpoint": digest(Path(cfg["sources"]["stage25_checkpoint"])),
    }
    checks = {
        "exact_four_file_bundle": actual_names == expected_names,
        "completion_passed": completion.get("passed") is True and completion.get("status") == "passed_read_only_network_export",
        "network_passed": network.get("passed") is True and network.get("status") == "exported_exact_stage25_contact_network_without_stepping",
        "completion_artifact_hashes_match": (
            completion["network_sha256"] == digest(BUNDLE / "network.json")
            and completion["particles_csv_sha256"] == digest(BUNDLE / "particles.csv")
            and completion["contacts_csv_sha256"] == digest(BUNDLE / "contacts.csv")
        ),
        "source_bindings_exact": completion["source_hashes"] == expected_source_hashes and network["source_hashes"] == expected_source_hashes,
        "prerun_authority_exact": (
            prerun.get("passed") is True
            and prerun["evidence"]["config_sha256"] == digest(CONFIG)
            and prerun["authority"]["network_export_execution_authorized"] is True
            and all(value is False for name, value in prerun["authority"].items() if name.endswith("_authorized") and name != "network_export_execution_authorized")
        ),
        "exact_counts_and_periodicity": (
            network["sand_particle_count"] == 216
            and network["sand_contact_count"] == 361
            and network["load_bearing_particle_count"] == 175
            and network["core_degree_threshold"] == 2
            and network["periodic"] is True
            and len(network["cell_hsize_m"]) == 3
        ),
        "particle_ids_unique": len(ids) == 216 and len(id_set) == 216,
        "contact_topology_valid": endpoints_valid and len(undirected) == len(set(undirected)) == 361,
        "force_magnitudes_finite_nonnegative": force_valid,
        "independent_degree2_core_is_175": len(core) == 175,
        "derived_particle_fields_exact": particle_fields_match,
        "particles_csv_equals_json": csv_particles_match,
        "contacts_csv_equals_json": csv_contacts_match,
        "exporter_static_read_only": calls.count("load") == 1 and not any(name in calls for name in ("run", "step", "save", "saveTmp", "reset")),
        "authority_stays_narrow": (
            completion["authority"] == {
                "placement_generation_authorized": False,
                "prefilter_yade_execution_authorized": False,
                "two_fibre_free_release_authorized": False,
                "four_fibre_execution_authorized": False,
                "flow_execution_authorized": False,
            }
        ),
    }
    passed = all(checks.values())
    evaluation = {
        "schema": "lbs.stage26b-revision2-stage25-network-export-evaluation.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "status": "passed_independent_exact_stage25_network_export_verification" if passed else "failed_stage25_network_export_verification",
        "checks": checks,
        "independent_summary": {
            "sand_particle_count": len(ids),
            "real_sand_contact_count": len(edges),
            "degree2_load_bearing_core_count": len(core),
            "periodic": network["periodic"],
            "network_degree_min": min(degree.values()),
            "network_degree_max": max(degree.values()),
            "network_degree_mean": sum(degree.values()) / len(degree),
            "normal_force_min_n": min(float(row["normal_force_n"]) for row in contacts),
            "normal_force_max_n": max(float(row["normal_force_n"]) for row in contacts),
            "normal_force_mean_n": sum(float(row["normal_force_n"]) for row in contacts) / len(contacts),
        },
        "evidence": {
            "bundle_path": str(BUNDLE),
            "network_path": str(BUNDLE / "network.json"), "network_sha256": digest(BUNDLE / "network.json"),
            "particles_csv_path": str(BUNDLE / "particles.csv"), "particles_csv_sha256": digest(BUNDLE / "particles.csv"),
            "contacts_csv_path": str(BUNDLE / "contacts.csv"), "contacts_csv_sha256": digest(BUNDLE / "contacts.csv"),
            "completion_path": str(BUNDLE / "completion.json"), "completion_sha256": digest(BUNDLE / "completion.json"),
            "config_path": str(CONFIG), "config_sha256": digest(CONFIG),
            "prerun_checkpoint_path": str(PRERUN), "prerun_checkpoint_sha256": digest(PRERUN),
            "verifier_sha256": digest(Path(__file__)),
        },
        "authority": {
            "authorized_next_activity": "Freeze this verified read-only network bundle and prepare an independently audited deterministic two-fibre placement-generation configuration; do not generate placements or execute YADE yet.",
            "placement_generation_preparation_authorized": passed,
            "placement_generation_authorized": False,
            "prefilter_yade_execution_authorized": False,
            "two_fibre_free_release_authorized": False,
            "four_fibre_execution_authorized": False,
            "flow_execution_authorized": False,
        },
        "claim_boundary": completion["claim_boundary"],
    }
    OUTPUT.mkdir(parents=True)
    path = OUTPUT / "evaluation.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(evaluation, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"passed": passed, "evaluation_sha256": digest(path), "core_count": len(core)}, sort_keys=True))
    if not passed:
        failed = [name for name, value in checks.items() if not value]
        print(json.dumps({"failed_checks": failed}, sort_keys=True))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
