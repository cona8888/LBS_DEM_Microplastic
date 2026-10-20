"""Independent static audit of the Stage26f robust-cage campaign."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def exclusive_json(path: Path, value) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def clearance(members, centres, radii, lengths, member_radius):
    delta = members[:, None, :] - centres[None, :, :]
    delta -= np.round(delta / lengths) * lengths
    return np.linalg.norm(delta, axis=2) - (member_radius + radii[None, :]), delta


def independent_metrics(members, support_indices, clearances, delta, member_radius):
    tip_span = float(np.linalg.norm(members[-1] - members[0]))
    centre = members.mean(axis=0)
    points, normals, member_indices = [], [], []
    for sand_index in support_indices:
        member_index = int(np.argmin(clearances[:, sand_index]))
        normal = delta[member_index, sand_index]
        normal /= np.linalg.norm(normal)
        point = members[member_index] - member_radius * normal
        points.append(point)
        normals.append(normal)
        member_indices.append(member_index)
    points = np.asarray(points)
    normals = np.asarray(normals)
    wrench_columns = []
    contact_centre = points.mean(axis=0)
    for point in points:
        arm = (point - contact_centre) / tip_span
        for basis in np.eye(3):
            wrench_columns.append(np.r_[basis, np.cross(arm, basis)])
    wrench = np.asarray(wrench_columns).T
    singular = np.linalg.svd(wrench, compute_uv=False)
    tolerance = singular[0] * max(wrench.shape) * np.finfo(float).eps
    normal_singular = np.linalg.svd(normals.T, compute_uv=False)
    moments = [np.cross(point - centre, normal) / tip_span for point, normal in zip(points, normals)]
    return {
        "support_member_indices": member_indices,
        "frictional_wrench_rank": int(np.sum(singular > tolerance)),
        "frictional_wrench_condition_ratio": float(singular[-1] / singular[0]),
        "normal_span_condition_ratio": float(normal_singular[-1] / normal_singular[0]),
        "equal_normal_force_residual_relative": float(np.linalg.norm(normals.sum(axis=0)) / len(normals)),
        "equal_normal_moment_residual_relative": float(np.linalg.norm(np.sum(moments, axis=0)) / len(moments)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    campaign = Path(args.campaign).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise RuntimeError("immutable Stage26f audit output already exists")
    config = load_json(config_path)
    completion_path = campaign / "completion.json"
    completion = load_json(completion_path)
    index_path = campaign / "candidate_index.csv"
    if completion["candidate_index_sha256"] != digest(index_path):
        raise RuntimeError("campaign candidate index hash mismatch")
    if completion["source_hashes"]["config"] != digest(config_path):
        raise RuntimeError("campaign config hash mismatch")
    for key in ("network", "f37_geometry_review", "exploratory_multicontact_probe"):
        if digest(Path(config["sources"][key])) != config["sources"][key + "_sha256"]:
            raise RuntimeError("config source hash mismatch: " + key)
    network = load_json(Path(config["sources"]["network"]))
    probe = load_json(Path(config["sources"]["exploratory_multicontact_probe"]))
    exploratory_sets = {
        tuple(sorted(int(value) for value in row["support_sand_body_ids"]))
        for row in probe["accepted_singles"]
    }
    particles = network["particles"]
    centres = np.asarray([row["position_m"] for row in particles], dtype=float)
    radii = np.asarray([row["radius_m"] for row in particles], dtype=float)
    ids = np.asarray([int(row["sand_body_id"]) for row in particles], dtype=int)
    id_to_index = {int(value): index for index, value in enumerate(ids)}
    degrees = np.asarray([int(row["sand_network_degree"]) for row in particles], dtype=int)
    core = np.asarray([bool(row["load_bearing_core_member"]) for row in particles])
    lengths = np.diag(np.asarray(network["cell_hsize_m"], dtype=float))
    member_radius = float(config["fibre"]["member_radius_m"])
    excluded = set(config["static_acceptance"]["excluded_spent_support_body_ids"])
    threshold = -0.001 * member_radius
    maximum_penetration = config["fibre"]["maximum_contact_penetration_over_member_radius"] * member_radius
    acceptance = config["static_acceptance"]

    with index_path.open("r", newline="", encoding="utf-8") as stream:
        index_rows = list(csv.DictReader(stream))
    checks = []
    joint_topologies = set()
    generator_hashes = set()
    all_passed = True
    for row in index_rows:
        candidate_dir = campaign / row["candidate_id"]
        placement_path = candidate_dir / "placement.json"
        search_path = candidate_dir / "search_summary.json"
        candidate_completion_path = candidate_dir / "completion.json"
        placement = load_json(placement_path)
        search = load_json(search_path)
        candidate_completion = load_json(candidate_completion_path)
        local_checks = {
            "index_and_completion_hashes": (
                row["placement_sha256"] == digest(placement_path)
                and row["search_summary_sha256"] == digest(search_path)
                and candidate_completion["placement_sha256"] == digest(placement_path)
                and candidate_completion["search_summary_sha256"] == digest(search_path)
            ),
            "passed_two_fibre_geometry": bool(placement["passed"] and len(placement["fibres"]) == 2),
            "candidate08_not_used": placement.get("candidate08_read_or_used") is False,
            "authority_closed": (
                placement["authority"].get("host_python_geometry_generation_authorized") is True
                and not any(
                    placement["authority"].get(key, False)
                    for key in (
                        "candidate08_execution_authorized",
                        "yade_execution_authorized",
                        "free_release_authorized",
                        "rehydration_authorized",
                        "deformation_authorized",
                        "flow_authorized",
                        "permeability_claim_authorized",
                    )
                )
            ),
        }
        generator_hashes.add(placement["source_hashes"]["generator"])
        support_sets = []
        fibre_members = []
        for fibre in placement["fibres"]:
            members = np.asarray(fibre["member_centres_m"], dtype=float)
            fibre_members.append(members)
            clearances, delta = clearance(members, centres, radii, lengths, member_radius)
            minimum = clearances.min(axis=0)
            support_indices = np.flatnonzero(minimum <= threshold).tolist()
            support_ids = tuple(sorted(int(ids[index]) for index in support_indices))
            support_sets.append(support_ids)
            metrics = independent_metrics(
                members, support_indices, clearances, delta, member_radius
            )
            interior = sorted(
                set(index for index in metrics["support_member_indices"] if index not in (0, 36))
            )
            stored_support_ids = tuple(sorted(int(value) for value in fibre["support_sand_body_ids"]))
            fibre_ok = all(
                (
                    support_ids == stored_support_ids,
                    len(support_ids) >= acceptance["minimum_distinct_sand_supports_per_fibre"],
                    not excluded.intersection(support_ids),
                    support_ids not in exploratory_sets,
                    all(core[id_to_index[value]] for value in support_ids),
                    all(degrees[id_to_index[value]] >= acceptance["minimum_support_network_degree"] for value in support_ids),
                    float(minimum.min()) >= -maximum_penetration - 1e-12,
                    np.all(members - member_radius >= 0.0),
                    np.all(members + member_radius <= lengths),
                    len(set(metrics["support_member_indices"])) >= acceptance["minimum_distinct_support_member_indices"],
                    len(interior) >= 2,
                    interior[-1] - interior[0] >= acceptance["minimum_interior_support_member_separation"],
                    metrics["frictional_wrench_rank"] >= acceptance["minimum_frictional_wrench_rank"],
                    metrics["frictional_wrench_condition_ratio"] >= acceptance["minimum_frictional_wrench_condition_ratio"],
                    metrics["normal_span_condition_ratio"] >= acceptance["minimum_contact_normal_span_condition_ratio"],
                    metrics["equal_normal_force_residual_relative"] <= acceptance["maximum_equal_normal_force_residual_relative"],
                    metrics["equal_normal_moment_residual_relative"] <= acceptance["maximum_equal_normal_moment_residual_relative"],
                    metrics["support_member_indices"] == fibre["support_member_indices"],
                    abs(metrics["frictional_wrench_condition_ratio"] - fibre["frictional_wrench_condition_ratio"]) < 1e-12,
                    abs(metrics["normal_span_condition_ratio"] - fibre["normal_span_condition_ratio"]) < 1e-12,
                    abs(metrics["equal_normal_force_residual_relative"] - fibre["equal_normal_force_residual_relative"]) < 1e-12,
                    abs(metrics["equal_normal_moment_residual_relative"] - fibre["equal_normal_moment_residual_relative"]) < 1e-12,
                )
            )
            local_checks[f"fibre_{fibre['fibre_index']}_all_static_gates"] = fibre_ok
        delta = fibre_members[0][:, None, :] - fibre_members[1][None, :, :]
        delta -= np.round(delta / lengths) * lengths
        joint_clearance = float(np.linalg.norm(delta, axis=2).min() - 2.0 * member_radius)
        topology = tuple(sorted(support_sets))
        local_checks["joint_supports_disjoint"] = not set(support_sets[0]).intersection(support_sets[1])
        local_checks["joint_clearance_gate"] = joint_clearance >= acceptance["minimum_initial_fibre_fibre_clearance_m"]
        local_checks["joint_topology_unique"] = topology not in joint_topologies
        joint_topologies.add(topology)
        candidate_passed = all(local_checks.values())
        all_passed = all_passed and candidate_passed
        checks.append(
            {
                "candidate_id": row["candidate_id"],
                "passed": candidate_passed,
                "checks": local_checks,
                "support_sets": [list(value) for value in support_sets],
                "recomputed_minimum_fibre_fibre_clearance_m": joint_clearance,
                "search_local_contact_fit_count": int(search["local_contact_fit_count"]),
            }
        )
    campaign_passed = (
        all_passed
        and len(index_rows) == config["search_budget"]["candidate_count"]
        and sum(row["passed"].lower() == "true" for row in index_rows)
        >= config["campaign_acceptance"]["minimum_passing_two_fibre_candidates"]
        and len(joint_topologies) >= config["campaign_acceptance"]["minimum_distinct_joint_support_topologies"]
        and completion.get("candidate08_read_or_used") is False
        and completion.get("passed") is True
        and len(generator_hashes) == 1
    )
    output.mkdir(parents=True)
    evaluation = {
        "schema": "lbs.stage26f-robust-cage-campaign-audit.v1",
        "passed": campaign_passed,
        "status": "independently_verified_static_campaign" if campaign_passed else "static_campaign_audit_failed",
        "candidate_count": len(index_rows),
        "verified_passing_candidate_count": sum(bool(row["passed"]) for row in checks),
        "distinct_joint_support_topology_count": len(joint_topologies),
        "candidate08_read_or_used": False,
        "checks": checks,
        "source_hashes": {
            "config": digest(config_path),
            "campaign_completion": digest(completion_path),
            "candidate_index": digest(index_path),
            "network": digest(Path(config["sources"]["network"])),
            "exploratory_probe": digest(Path(config["sources"]["exploratory_multicontact_probe"])),
            "auditor": digest(Path(__file__)),
        },
        "authority": config["authority"],
        "claim_boundary": config["claim_boundary"],
    }
    exclusive_json(output / "evaluation.json", evaluation)
    print(json.dumps({"passed": campaign_passed, "candidate_count": len(index_rows), "distinct_joint_support_topology_count": len(joint_topologies), "evaluation_sha256": digest(output / "evaluation.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
